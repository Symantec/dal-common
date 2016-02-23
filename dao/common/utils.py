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

import collections
import functools
import time
import yaml
from eventlet import timeout
from eventlet import semaphore
from eventlet.green import subprocess
from dao.common import log
from dao.common import exceptions

logger = log.getLogger(__name__)


def singleton(cls):
    def get_create(*args, **kwargs):
        if not hasattr(cls, 'instance'):
            cls.instance = cls(*args, **kwargs)
        return cls.instance
    return get_create


class Popen(subprocess.Popen):
    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self.stdout:
            self.stdout.close()
        if self.stderr:
            self.stderr.close()
        if self.stdin:
            self.stdin.close()
        # Wait for the process to terminate, to avoid zombies.
        self.wait()


def run_sh(args):
    logger.debug('Run cmd: %s', ' '.join(args))
    with Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as p:
        stdout, stderr = p.communicate()
        if p.returncode == 0:
            return stdout
        else:
            msg = 'Ret code: {0}, msg: {1}'.format(p.returncode, stderr)
            logger.info(msg)
            raise exceptions.DAOExecError(p.returncode, stdout, stderr)


class Timed(timeout.Timeout):
    def __init__(self, time):
        super(Timed, self).__init__(time, exceptions.DAOTimeout)


class Synchronized(object):
    lock_objects = collections.defaultdict(semaphore.Semaphore)

    def __init__(self, key):
        self.lock_object = self.lock_objects[key]

    def __call__(self, f):
        @functools.wraps(f)
        def inner(*args, **kwargs):
            logger.debug('get lock %s', f.__name__)
            with self.lock_object:
                logger.debug('lock acquired: %s', f.__name__)
                result = f(*args, **kwargs)
            logger.debug('lock released %s', f.__name__)
            return result
        return inner


class CacheIt(object):
    """ Memoize With Timeout and eventlet sync"""

    def __init__(self, timeout=None, ignore_self=True):
        self.timeout = timeout
        self.ignore_self = ignore_self
        self.cache = collections.defaultdict(dict)

    def _key_from_args(self, args, kwargs):
        key_args = args
        if self.ignore_self:
            key_args = key_args[1:]
        return yaml.dump((key_args, tuple(sorted(kwargs.items()))))

    def evict(self, *args, **kwargs):
        key = self._key_from_args(args, kwargs)
        if key in self.cache:
            del self.cache[key]

    def __call__(self, f):
        cache = self.cache[f]

        @Synchronized(f)
        @functools.wraps(f)
        def func(*args, **kwargs):
            key = self._key_from_args(args, kwargs)
            try:
                v = cache[key]
                if self.timeout is not None and \
                   (time.time() - v[1]) > self.timeout:
                    raise KeyError
            except KeyError:
                logger.debug('Create new key for %s: %s', f.__name__, key)
                v = cache[key] = f(*args, **kwargs), time.time()
            return v[0]

        func.cache = self

        return func
