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
import os
import logging
import logging.config

from dao.common import config

opts = [config.BoolOpt('common', 'debug', True),
        config.StrOpt('common', 'log_config', '')]
config.register(opts)
CONF = config.get_config()


def getLogger(name):
    """getting logger"""
    return logging.getLogger(name)


def setup(app_name):
    defaults = dict()
    defaults['app_name'] = app_name
    log_level = 'DEBUG' if CONF.common.debug else 'INFO'
    defaults['log_level'] = log_level
    path = os.path.join(CONF.common.log_config)
    logging.config.fileConfig(path, defaults=defaults)
