# Copyright 2016 Symantec.
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

import abc
import eventlet
from dao.common import config
from dao.common import exceptions
from dao.common import log

opts = [
    config.StrOpt('rpc', 'ip',
                  help='IP Address of the current host on management network.'),
    config.StrOpt('rpc', 'url_pattern', default='tcp://{ip}:{port}',
                  help='URL pattern to be used by RPC'),
    config.IntOpt('rpc', 'rcv_timeout', default=20,
                  help='Receive message timeout'),
    config.IntOpt('rpc', 'send_timeout', default=20,
                  help='Send message timeout'),
    config.StrOpt('rpc', 'driver', default='dao.common.rpc_driver.amqp',
                  help='PRC driver implementation'),
]
config.register(opts)
CONF = config.get_config()

LOG = log.getLogger(__name__)


def build_url(ip, port):
    url = CONF.rpc.url_pattern.format(ip=ip, port=port)
    if port is None:
        url = url.rsplit(':', 1)[0]
    return url


class Loadable(object):
    @classmethod
    def get_backend(cls, *args, **kwargs):
        """
        :rtype: cls.__name__
        """
        module = CONF.rpc.driver
        LOG.debug('Load client from %s', module)
        module = eventlet.import_patched(module)
        return getattr(module, cls.__name__)(*args, **kwargs)


class Client(Loadable):
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
        self.timeout = timeout or CONF.rpc.rcv_timeout

    @abc.abstractmethod
    def call(self, func, *args, **kwargs):
        pass

    @abc.abstractmethod
    def send(self, func, *args, **kwargs):
        pass


class Server(Loadable):
    def __init__(self, port):
        self.url = build_url(CONF.rpc.ip, port)

    @abc.abstractmethod
    def get_request(self):
        """
        :return: dict, keys are: function, args, kwargs, reply_to (optional)
        """
        pass

    @abc.abstractmethod
    def send_reply(self, reply_to, data):
        pass
