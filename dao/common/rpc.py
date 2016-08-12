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
import traceback
from dao.common import config
from dao.common import log
from dao.common.rpc_driver import base as rpc_base


CONF = config.get_config()
LOG = log.getLogger(__name__)


def build_url(ip, port):
    url = CONF.rpc.url_pattern.format(ip=ip, port=port)
    if port is None:
        url = url.rsplit(':', 1)[0]
    return url


class RPCApi(object):
    def __init__(self, connect_url=None, ip=None, port=None, timeout=None):
        """RPC Client object.
        Requires either `connect_url` or pair of `ip` and `port`.

        TODO: get rid of connect_url as soon as dao-client uses REST
        """
        self.backend = \
            rpc_base.Client.get_backend(connect_url, ip, port, timeout)

    def call(self, func, *args, **kwargs):
        self.backend.call(func, *args, **kwargs)

    def send(self, func, *args, **kwargs):
        self.backend.send(func, *args, **kwargs)


class RPCServer(object):
    def __init__(self, port):
        self.pool = eventlet.GreenPool(10000)
        self.backend = rpc_base.Server.get_backend(port)
        self.url = self.backend.url

    def do_main(self):
        while True:
            try:
                LOG.debug('Waiting RPC request')
                request = self.backend.get_request()
                try:
                    reply_to = request.get('reply_to', None)
                    func_name = request['function']
                    args = request['args']
                    kwargs = request['kwargs']
                    self._spawn(reply_to, func_name, args, kwargs)
                except IndexError:
                    LOG.warning(traceback.format_exc())
            except Exception:
                LOG.warning(traceback.format_exc())

    def _call(self, reply_to, func_name, args, kwargs):
        try:
            LOG.debug('Request is: %r', repr(locals()))
            response = getattr(self, func_name)(*args, **kwargs)
            LOG.debug('Response is: %r', repr(response))
        except Exception, exc:
            response = exc
            LOG.warning(traceback.format_exc())

        if reply_to is not None:
            self.backend.send_reply(reply_to, response)

    def _spawn(self, reply_to, func_name, args, kwargs):
        LOG.debug('Spawning thread for %s, pool: %s',
                  func_name, self.pool.free())
        self.pool.spawn_n(self._call, reply_to, func_name, args, kwargs)
