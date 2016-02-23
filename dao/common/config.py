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

from dao.common.config_opts import *


CONFIG = None


def _init_config():
    global CONFIG
    if CONFIG is None:
        CONFIG = ConfigLoader()
    return CONFIG


def register(opts):
    """Loads sections from config file and emulate dotted access"""
    config = _init_config()
    config.register(opts)


def get_config():
    """Loads sections from config file and emulate dotted access"""
    config = _init_config()
    return config.get_config()


def setup(application, opts=[]):
    """Initialize app configuration

    Look for application-specific configuration files and import config values.
    The directories to search in are:
        - /etc/dao
        - ${HOME}/dao
        - ${CWD}/etc

    Each configuration file named after application, so for example
    `dao-control` will look for file `control.cfg` in the above directories.
    """
    config = _init_config()
    config.load_config(application)
    if opts:
        config.register(opts)
