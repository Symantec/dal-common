# Copyright 2016 Symantec, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import eventlet
import time
import traceback
from eventlet.green import zmq
from dao.common import config
from dao.common import exceptions
from dao.common import log

opts = [
    config.StrOpt('zmq', 'ip',
                  help='IP Address of the current host on management network.'),
    config.StrOpt('zmq', 'url_pattern', default='tcp://{ip}:{port}',
                  help='URL pattern to be used by RPC.'),
    config.IntOpt('zmq', 'rcv_timeout', default=20,
                  help='Timeout for rcv_pyobj message'),
    config.IntOpt('zmq', 'send_timeout', default=20,
                  help='Timeout for rcv_pyobj message'),
]
config.register(opts)
CONF = config.get_config()

logger = log.getLogger(__name__)
context = zmq.Context()


def build_url(ip, port):
    url = CONF.zmq.url_pattern.format(ip=ip, port=port)
    if port is None:
        url = url.rsplit(':', 1)[0]
    return url


class ZMQSocket(object):

    sockets_pool = []
    cnt = 0

    def __init__(self, sock_type):
        self.sock_type = sock_type
        self.sock = None
        self.finished = False
        self.sock_id = ZMQSocket.cnt
        ZMQSocket.cnt += 1
        self.sockets_pool.append((time.time(), self))
        self._clean_up()

    def __enter__(self):
        self.sock = context.socket(self.sock_type)
        self.sock.setsockopt(zmq.LINGER, CONF.zmq.send_timeout)
        logger.debug('Socket entered: %s', self.sock_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finished = True

    @classmethod
    def _clean_up(cls):
        current = time.time()
        logger.debug('CleanUp. Queue len: %s', len(cls.sockets_pool))
        for sock_time, socket in cls.sockets_pool:
            if socket.finished:
                if socket.sock is None:
                    cls.sockets_pool.remove((sock_time, socket))
                else:
                    close = (socket.sock_type == zmq.PULL or
                             (current-sock_time) > CONF.zmq.send_timeout)
                    if close:
                        socket.sock.close()
                        cls.sockets_pool.remove((sock_time, socket))
                        logger.debug('Close socket %s', socket.sock_id)

    def connect(self, connect_url):
        self.sock.connect(connect_url)
        logger.info('Connection url: %s', connect_url)

    def bind_random(self):
        bind_url = build_url(CONF.zmq.ip, None)
        reply_port = self.sock.bind_to_random_port(bind_url)
        return build_url(CONF.zmq.ip, reply_port)

    def recv_pyobj(self, timeout=None):
        if timeout is None:
            return self.sock.recv_pyobj()
        else:
            with eventlet.timeout.Timeout(timeout, exceptions.DAOTimeout):
                return self.sock.recv_pyobj()


class RPCApi(object):
    def __init__(self, connect_url=None, ip=None, port=None, timeout=None):
        """Open socket for RPC communications

        Requires either `connect_url` or pair of `ip` and `port`.
        If `connect_url` is used, it might be full URI of the form:

            tcp://{ip}:{port}

        """
        if connect_url:
            self.connect_url = connect_url
        elif ip and port:
            self.connect_url = build_url(ip, port)
        else:
            raise exceptions.DAOException('No url parameters provided')
        self.timeout = timeout or CONF.zmq.rcv_timeout

    def call(self, func, *args, **kwargs):
        logger.info('Call sent: %s', func)
        with ZMQSocket(zmq.PUSH) as push:
            with ZMQSocket(zmq.PULL) as pull:
                push.connect(self.connect_url)
                reply_url = pull.bind_random()
                push.sock.send_pyobj({'reply_addr': reply_url,
                                      'function': func,
                                      'args': args,
                                      'kwargs': kwargs})
                return pull.recv_pyobj(self.timeout)

    def send(self, func, *args, **kwargs):
        with ZMQSocket(zmq.PUSH) as push:
            push.connect(self.connect_url)
            logger.info('Send sent: %s', func)
            push.sock.send_pyobj({'function': func,
                                  'args': args,
                                  'kwargs': kwargs})


class RPCServer(object):
    def __init__(self, port):
        self.pool = eventlet.GreenPool(10000)
        self.socket = context.socket(zmq.PULL)
        self.url = build_url(CONF.zmq.ip, port)
        self.socket.bind(self.url)

    def do_main(self):
        while True:
            try:
                logger.debug('Waiting RPC request')
                request = self.socket.recv_pyobj()
                try:
                    reply_addr = request.get('reply_addr', None)
                    func_name = request['function']
                    args = request['args']
                    kwargs = request['kwargs']
                    self._spawn(reply_addr, func_name, args, kwargs)
                except IndexError:
                    logger.warning(traceback.format_exc())
            except Exception:
                logger.warning(traceback.format_exc())

    def _call(self, reply_addr, func_name, args, kwargs):
        try:
            logger.debug('Request is: %r', repr(locals()))
            response = getattr(self, func_name)(*args, **kwargs)
            logger.debug('Response is: %r', repr(response))
        except Exception, exc:
            response = exc
            logger.warning(traceback.format_exc())

        if reply_addr is not None:
            with ZMQSocket(zmq.PUSH) as socket:
                socket.connect(reply_addr)
                socket.sock.send_pyobj(response)

    def _spawn(self, reply_addr, func_name, args, kwargs):
        logger.debug('Spawning thread for %s, pool: %s',
                     func_name, self.pool.free())
        self.pool.spawn_n(self._call, reply_addr, func_name, args, kwargs)
