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

import amqpy
import eventlet
import yaml
import uuid
import time

from dao.common import config
from dao.common import exceptions
from dao.common import log
from dao.common.rpc_driver import base


opts = [
    config.StrOpt('rabbit', 'host', default='127.0.0.1',
                  help='IP Address of the rabbit'),
    config.StrOpt('rabbit', 'user', default='guest',
                  help='Rabbit user to use'),
    config.StrOpt('rabbit', 'password', default='guest',
                  help='Rabbit password to use'),
    config.IntOpt('rabbit', 'port', default=5672,
                  help='Rabbit port to use'),
    config.IntOpt('rabbit', 'keep_alive', default=60,
                  help='Keep alive heardbeat'),
    config.IntOpt('rabbit', 'reconnect_on', default=2,
                  help='Reconnect timeout'),
]
config.register(opts)
CONF = config.get_config()
logger = log.getLogger(__name__)


def get_connection():
    return amqpy.Connection(
        host=CONF.rabbit.host,
        port=CONF.rabbit.port,
        userid=CONF.rabbit.user,
        password=CONF.rabbit.password,
        heartbeat=CONF.rabbit.keep_alive
    )


class Channel(object):
    def __init__(self):
        self.channel = None
        self.connection = None

    def __enter__(self):
        self.connection = get_connection()
        self.channel = self.connection.channel()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.channel.close()
        self.connection.close()


class Exchange(object):
    def __init__(self, name, _type, channel):
        self.name = name
        self.type = _type
        self.channel = channel

    def __enter__(self):
        self.channel.exchange_declare(self.name, self.type)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.channel.exchange_delete(self.name)


class Queue(object):
    def __init__(self, name, channel, exclusive=True):
        self.name = name
        self.channel = channel
        self.exclusive = exclusive
        self.queue = None

    def __enter__(self):
        self.queue = self.channel.queue_declare(self.name,
                                                exclusive=self.exclusive)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.channel.queue_delete(self.name)


class Client(base.Client):
    def __init__(self, connect_url=None, ip=None, port=None, timeout=None):
        # In order to keep compatibility with the code that uses ZMQ
        # there is an assumption that queues are named like ZMQ urls.
        super(Client, self).__init__(connect_url, ip, port, timeout)
        self.message = None

    def _get_exchange_name(self):
        return '_'.join((str(uuid.uuid4()), self.connect_url))

    def send(self, func, *args, **kwargs):
        data = {'function': func,
                'args': args,
                'kwargs': kwargs}
        with Channel() as channel:
            self._send(channel, data)

    def call(self,  func, *args, **kwargs):
        # Queue name for reply_to
        rq_name = 'client_' + uuid.uuid4().hex
        data = {'reply_to': rq_name,
                'function': func,
                'args': args,
                'kwargs': kwargs}
        with eventlet.Timeout(self.timeout):
            with Channel() as channel:
                return self._call(channel, data)

    def _send(self, channel, data):
        ch = channel.channel
        with Exchange(self._get_exchange_name(), 'direct', ch) as exchange:
            try:
                ch.queue_bind(self.connect_url, exchange=exchange.name)
            except amqpy.NotFound:
                raise exceptions.DAONotFound('Unable to connect to {0}'.
                                             format(self.connect_url))
            ch.basic_publish(amqpy.Message(yaml.dump(data)),
                             exchange=exchange.name,
                             mandatory=True)

    def _call(self, channel, data):
        ch = channel.channel
        self.message = None
        with Queue(data['reply_to'], ch) as reply_to:
            ch.basic_consume(data['reply_to'], callback=self.on_message)
            self._send(channel, data)
            while True:
                channel.connection.drain_events(timeout=None)
                if self.message:
                    return yaml.load(self.message.body)

    def on_message(self, msg):
            self.message = msg


class Server(base.Server):
    def __init__(self, port):
        super(Server, self).__init__(port)
        self.conn = None
        self.ch = None
        self.consumer = None
        self.message = None
        self.setup_connection()
        self.setup_queue()

    def get_request(self):
        self.message = None
        while True:
            try:
                self.conn.drain_events(timeout=None)
                if self.message is not None:
                    return yaml.load(self.message.body)
            except Exception, exc:
                # Hot fix, reconnect on amqp errors
                logger.warning('While draining events: {0}'.format(repr(exc)))
                # Try to delete old staff
                try:
                    self.ch.queue_delete(self.url)
                    self.conn.close()
                except Exception, exc:
                    logger.info('While closing old connection: {0}'.
                                format(repr(exc)))
                # Recreate new one
                try:
                    if not self.conn.connected:
                        self.setup_connection()
                        self.setup_queue()
                except Exception, exc:
                    logger.info('While setuping connection: {0}'.format(
                        repr(exc)))
                    time.sleep(CONF.rabbit.reconnect_on)
                    raise

    def setup_connection(self):
        self.conn = get_connection()
        self.ch = self.conn.channel()

    def setup_queue(self):
        self.ch.queue_declare(self.url)
        self.consumer = self.ch.basic_consume(self.url,
                                              callback=self.on_event,
                                              no_ack=True)

    def on_event(self, msg):
        print 'message received'
        self.message = msg

    def send_reply(self, reply_to, data):
        self.ch.basic_publish(amqpy.Message(yaml.dump(data)),
                              routing_key=reply_to)
