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

import json
import os
import ConfigParser

CONFIG_PATH_SYSTEM = '/etc/dao'
CONFIG_PATH_USER = '{home}/.dao'.format(home=os.environ.get('HOME'))
CONFIG_PATH_LOCAL = '{cwd}/etc'.format(cwd=os.getcwd())


class ConfOpt(object):

    def __init__(self, section, name, default=None, help=''):
        self.section = section
        self.name = name
        self.default = default
        self.help = help

    def raw2value(self, value):
        return self._get_value(value)

    def _get_value(self, value):
        return value

    def __hash__(self):
        return hash((self.section, self.name))

    def __eq__(self, other):
        return self.section == other.section and self.name == other.name


class StrOpt(ConfOpt):

    def _get_value(self, value):
        return str(value)


class JSONOpt(ConfOpt):

    def _get_value(self, value):
        return json.loads(value)


class BoolOpt(ConfOpt):

    def _get_value(self, value):
        value = str(value).lower()
        return value == 'true' or value == '1'


class IntOpt(ConfOpt):

    def _get_value(self, value):
        return int(value)


class NamedList(dict):
    def __getattr__(self, item):
        return self[item]


class ConfigLoader(object):
    def __init__(self):
        self._options = set()
        self._source = None
        self._config = NamedList()

    def register(self, opts):
        if self._source is None:
            raise RuntimeError('Configuration file is not loaded yet')
        for opt in opts:
            self._options.add(opt)
            try:
                value = self._source.get(opt.section, opt.name, raw=True)
                value = opt.raw2value(value)
            except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
                value = opt.default
            if opt.section not in self._config:
                self._config[opt.section] = NamedList()
            self._config[opt.section][opt.name] = value

    def get_config(self):
        return self._config

    def get_options(self):
        return self._options

    def load_config(self, application):
        """Load app configuration from available files.o

        Search for configuration in following dorectories priority:
            1. System-wide settings (/etc);
            2. User-specific settings ($HOME/.dao);
            3. Local settings (current working dir).

        Each DAO components has its own configuration file located in any of the
        above directories. For example `dao-control` will look for config file
        `control.cfg` while `dao-cli` will look for `cli.cfg`.

        """
        paths = [CONFIG_PATH_SYSTEM, CONFIG_PATH_USER, CONFIG_PATH_LOCAL]
        configs = ['{path}/{app}.cfg'.format(path=cfg, app=application)
                   for cfg in paths]
        source = ConfigParser.ConfigParser()
        source.read(configs)
        self._source = source
