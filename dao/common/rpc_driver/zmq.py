#
# Copyright 2016 Symantec.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
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
from dao.common.rpc_driver import base

CONF = config.get_config()

logger = log.getLogger(__name__)
context = zmq.Context()


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
        self.sock.setsockopt(zmq.LINGER, CONF.rpc.send_timeout)
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
                             (current-sock_time) > CONF.rpc.send_timeout)
                    if close:
                        socket.sock.close()
                        cls.sockets_pool.remove((sock_time, socket))
                        logger.debug('Close socket %s', socket.sock_id)

    def connect(self, connect_url):
        self.sock.connect(connect_url)
        logger.info('Connection url: %s', connect_url)

    def bind_random(self):
        bind_url = base.build_url(CONF.rpc.ip, None)
        reply_port = self.sock.bind_to_random_port(bind_url)
        return base.build_url(CONF.rpc.ip, reply_port)

    def recv_pyobj(self, timeout=None):
        if timeout is None:
            return self.sock.recv_pyobj()
        else:
            with eventlet.timeout.Timeout(timeout, exceptions.DAOTimeout):
                return self.sock.recv_pyobj()


class Client(base.Client):
    def call(self, func, *args, **kwargs):
        logger.info('Call sent: %s', func)
        with ZMQSocket(zmq.PUSH) as push:
            with ZMQSocket(zmq.PULL) as pull:
                push.connect(self.connect_url)
                reply_url = pull.bind_random()
                push.sock.send_pyobj({'reply_to': reply_url,
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


class Server(base.Server):
    def __init__(self, port):
        super(Server, self).__init__(port)
        self.socket = context.socket(zmq.PULL)
        self.socket.bind(self.url)

    def get_request(self):
        return self.socket.recv_pyobj()

    def send_reply(self, reply_to, data):
        with ZMQSocket(zmq.PUSH) as socket:
            socket.connect(reply_to)
            socket.sock.send_pyobj(data)
