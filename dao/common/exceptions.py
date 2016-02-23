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


class DAOException(RuntimeError):
    def __init__(self, message='', status_code=None):
        self.status_code = status_code
        super(DAOException, self).__init__(message)


class DAOExecError(DAOException):
    def __init__(self, return_code, stdout, stderr):
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        msg = 'Execution error. Return code: {0}, stderr: {1}'
        super(DAOExecError, self).__init__(msg.format(return_code, stderr))


class DAOTimeout(DAOException):
    pass


class DAONotFound(DAOException):
    pass


class DAOManyFound(DAOException):
    pass


class DBDuplicateEntry(DAOException):
    pass


class DBDuplicateEntry(DAOException):
    pass


class DBDeadlock(DAOException):
    pass


class DBInvalidUnicodeParameter(DAOException):
    pass


class DBError(DAOException):
    pass


class DBConnectionError(DAOException):
    pass
