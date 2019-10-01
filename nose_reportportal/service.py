#  Copyright (c) 2019 http://reportportal.io
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from six import with_metaclass
from six.moves import queue
from reportportal_client import ReportPortalServiceAsync
import sys
import traceback
import pkg_resources
import logging
from time import time, sleep

LAUNCH_WAIT_TIMEOUT = 30

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

def timestamp():
    return str(int(time() * 1000))

class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class NoseServiceClass(with_metaclass(Singleton, object)):

    def __init__(self):
        self.RP = None
        try:
            pkg_resources.get_distribution('reportportal_client >= 3.2.0')
            self.RP_SUPPORTS_PARAMETERS = True
        except pkg_resources.VersionConflict:
            self.RP_SUPPORTS_PARAMETERS = False

        self.ignore_errors = True
        self.ignored_tags = []

        self._errors = queue.Queue()
        self._loglevels = ('TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR')

    def init_service(self, endpoint, project, token, ignore_errors=True,
                     ignored_tags=[], log_batch_size=20, queue_get_timeout=5, retries=0):
        self._errors = queue.Queue()
        if self.RP is None:
            self.ignore_errors = ignore_errors
            if self.RP_SUPPORTS_PARAMETERS:
                self.ignored_tags = list(set(ignored_tags).union({'parametrize'}))
            else:
                self.ignored_tags = ignored_tags
            log.debug('ReportPortal - Init service: endpoint=%s, '
                      'project=%s, uuid=%s', endpoint, project, token)
            self.RP = ReportPortalServiceAsync(
                endpoint=endpoint,
                project=project,
                token=token,
                error_handler=self.async_error_handler,
                queue_get_timeout=queue_get_timeout,
                retries=retries,
                log_batch_size=log_batch_size,
                # verify_ssl=verify_ssl
            )
            if self.RP and hasattr(self.RP.rp_client, "get_project_settings"):
                 self.project_settiings = self.RP.rp_client.get_project_settings()
            else:
                 self.project_settiings = None
            self.issue_types = self.get_issue_types()
        else:
            log.debug('The pytest is already initialized')
        return self.RP

    def async_error_handler(self, exc_info):
        self.terminate_service(nowait=True)
        self.RP = None
        self._errors.put_nowait(exc_info)

    def terminate_service(self, nowait=False):
        if self.RP is not None:
            self.RP.terminate(nowait)
            self.RP = None

    def start_launch(self, name,
                     mode=None,
                     tags=None,
                     description=None):
        self._stop_if_necessary()
        if self.RP is None:
            return

        sl_pt = {
            'name': name,
            'start_time': timestamp(),
            'description': description,
            'mode': mode,
            'tags': tags,
        }
        self.RP.start_launch(**sl_pt)

    def start_nose_item(self, ev, test=None):
        self._stop_if_necessary()
        if self.RP is None:
            return
        tags = []
        try:
            tags = test.test.suites
        except AttributeError:
            pass
        name = str(test)
        start_rq = {
            "name": name,
            "description": ev.describeTest(test),
            "tags": tags,
            "start_time": timestamp(),
            "item_type": "TEST",
            "parameters": {},
        }
        self.RP.start_test_item(**start_rq)
        self.post_log(name)

    def finish_nose_item(self, status, issue=None):
        self._stop_if_necessary()
        if self.RP is None:
            return

        self.post_log(status)
        fta_rq = {
            'end_time': timestamp(),
            'status': status,
            'issue': issue,
        }

        self.RP.finish_test_item(**fta_rq)

    def finish_launch(self, launch=None, status='rp_launch'):
        self._stop_if_necessary()
        if self.RP is None:
            return

        # To finish launch session str parameter is needed
        fl_rq = {
            'end_time': timestamp(),
            'status': status,
        }
        self.RP.finish_launch(**fl_rq)

    def terminate_service(self, nowait=False):
        if self.RP is not None:
            self.RP.terminate(nowait)
            self.RP = None

    def post_log(self, message, loglevel='INFO', attachment=None):
        self._stop_if_necessary()
        if self.RP is None:
            return

        if loglevel not in self._loglevels:
            log.warning('Incorrect loglevel = %s. Force set to INFO. '
                        'Available levels: %s.', loglevel, self._loglevels)
            loglevel = 'INFO'

        sl_rq = {
            'time': timestamp(),
            'message': message,
            'level': loglevel,
            'attachment': attachment,
        }
        self.RP.log(**sl_rq)

    def _stop_if_necessary(self):
        try:
            exc, msg, tb = self._errors.get(False)
            traceback.print_exception(exc, msg, tb)
            sys.stderr.flush()
            if not self.ignore_errors:
                sys.exit(msg)
        except queue.Empty:
            pass

    def get_issue_types(self):
        issue_types = {}
        if not self.project_settiings:
             return issue_types

        for item_type in ("AUTOMATION_BUG", "PRODUCT_BUG", "SYSTEM_ISSUE", "NO_DEFECT", "TO_INVESTIGATE"):
            for item in self.project_settiings["subTypes"][item_type]:
                issue_types[item["shortName"]] = item["locator"]

        return issue_types