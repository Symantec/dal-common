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

"""
Read all available options from dao.control package.
Reading is implemented by scanning source tree for installed DAOF.
It:
1. Locate where DAOF is installed
2. Read all files, importing all that match *.py
3. Read config.CONF which is extended with 'register' during step 2
4. Remove repeating options (better to fix, now just workaround)
5. Print
"""
import argparse
import csv
import imp
import importlib
import os
import prettytable
import sys

from dao.common import config


def import_by_path(module_path):
    try:
        if module_path.endswith('.pyc'):
            imp.load_compiled('a', module_path)
        else:
            imp.load_source('a', module_path)
    except SyntaxError:
        sys.stdout.write('WARNING: Unable to load: %s' % module_path)


def import_all(module_path):
    import_by_path(module_path)
    dir_name = os.path.dirname(module_path)
    sub_items = os.listdir(dir_name)
    for item in sub_items:
        path = os.path.join(dir_name, item)
        if item.endswith('.py'):
            import_by_path(path)
        elif os.path.isdir(path):
            init_path = os.path.join(path, '__init__.py')
            if os.path.exists(init_path):
                import_all(init_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', default='')
    parser.add_argument('--default', action='store_true', default=False)
    parser.add_argument('--app-name', required=True)
    args = parser.parse_args()
    application = args.app_name
    #---------------
    config.setup(application)
    from dao.common import log
    log.setup('common')
    #---------------
    root = importlib.import_module(application)
    import_all(root.__file__)
    if args.default:
        header = ['section', 'name', 'default', 'help']
    else:
        header = ['section', 'name', 'value', 'help']
    opts = set()
    conf = config.get_config()
    for opt in config.CONFIG.get_options():
        value = opt.default if args.default \
            else conf[opt.section][opt.name]
        opts.add((opt.section, opt.name, value, opt.help))
    opts = sorted(opts)
    p = prettytable.PrettyTable(header)
    for opt in opts:
        p.add_row(opt)
    p.align = 'l'
    if args.csv:
        with open(args.csv, 'wb') as fout:
            writer = csv.writer(fout)
            writer.writerow(header)
            writer.writerows([opt for opt in opts])


if __name__ == '__main__':
    main()
