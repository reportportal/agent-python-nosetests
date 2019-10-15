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
import os
import sys
if sys.version_info.major == 2:
    import ConfigParser as configparser
    from StringIO import StringIO
else:
    import configparser
    from io import StringIO

import threading
import logging
import traceback
from nose.plugins.base import Plugin
from nose.plugins.logcapture import MyMemoryHandler
from nose import SkipTest
from nose.plugins.skip import Skip
from nose.plugins.logcapture import LogCapture
from nose.plugins.deprecated import DeprecatedTest
from .service import NoseServiceClass

from nose.pyversion import exc_to_unicode, force_unicode
from nose.util import safe_str, isclass


log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
# Disabled because we've already had a overloaded capturing of the logs
LogCapture.enabled = False


class RPNoseLogHandler(MyMemoryHandler):
    def __init__(self, extended_filters=None):
        logformat = '%(name)s: %(levelname)s: %(message)s'
        logdatefmt = None
        filters = ['-nose', '-reportportal_client.service_async',
                   '-reportportal_client.service', '-nose_reportportal.plugin',
                   '-nose_reportportal.service']
        if extended_filters:
            filters.extend(extended_filters)
        super(RPNoseLogHandler, self).__init__(logformat, logdatefmt, filters)


class ReportPortalPlugin(Plugin):
    can_configure = True
    score = Skip.score + 1
    status = {}
    enableOpt = None
    name = "reportportal"

    def __init__(self):
        super(ReportPortalPlugin, self).__init__()
        self.stdout = []
        self._buf = None
        self.filters = None

    def options(self, parser, env):
        """
        Add options to command line.
        """
        super(ReportPortalPlugin, self).options(parser, env)
        parser.add_option('--rp-config-file',
                          action='store',
                          default=env.get('NOSE_RP_CONFIG_FILE'),
                          dest='rp_config',
                          help='config file path')

        parser.add_option('--rp-launch',
                          action='store',
                          default=None,
                          dest='rp_launch',
                          help='postfix of launch name in report portal')

        parser.add_option('--rp-mode',
                          action='store',
                          default="DEFAULT",
                          dest='rp_mode',
                          help='level of logging')

        parser.add_option('--rp-launch-description',
                          action='store',
                          default="",
                          dest='rp_launch_description',
                          help='description of a launch')

        parser.add_option('--ignore-loggers',
                          action='store',
                          default=[],
                          dest='ignore_loggers',
                          help='logger filter')


    def configure(self, options, conf):
        """
        Configure plugin.
        """
        try:
            self.status.pop('active')
        except KeyError:
            pass
        super(ReportPortalPlugin, self).configure(options, conf)

        if self.enabled:

            self.conf = conf
            self.rp_config = options.rp_config
            config = configparser.ConfigParser(
                defaults={
                    'rp_uuid': '',
                    'rp_endpoint': '',
                    'rp_project': '',
                    'rp_launch': '{}',
                    'rp_launch_tags': '',
                    'rp_launch_description': ''
                }
            )
            config.read(self.rp_config)

            if options.rp_launch:
                slaunch = options.rp_launch
            else:
                slaunch = "(unit tests)"
                if options.attr:
                    if "type=integration" in options.attr:
                        slaunch = "(integration tests)"
                    elif "type=component" in options.attr:
                        slaunch = "(component tests)"

            self.rp_mode = options.rp_mode if options.rp_mode in ("DEFAULT", "DEBUG") else "DEFAULT"

            if options.ignore_loggers and isinstance(options.ignore_loggers, basestring):
                self.filters = [x.strip() for x in options.ignore_loggers.split(",")]

            self.clear = True
            if "base" in config.sections():
                self.rp_uuid = config.get("base", "rp_uuid")
                self.rp_endpoint = config.get("base", "rp_endpoint")
                os.environ["RP_ENDPOINT"] = self.rp_endpoint
                self.rp_project = config.get("base", "rp_project")
                self.rp_launch = config.get("base", "rp_launch").format(slaunch)
                self.rp_launch_tags = config.get("base", "rp_launch_tags")
                self.rp_launch_description = options.rp_launch_description or config.get("base", "rp_launch_description")

    def setupLoghandler(self):
        # setup our handler with root logger
        root_logger = logging.getLogger()
        if self.clear:
            if hasattr(root_logger, "handlers"):
                for handler in root_logger.handlers:
                    root_logger.removeHandler(handler)
            for logger in logging.Logger.manager.loggerDict.values():
                if hasattr(logger, "handlers"):
                    for handler in logger.handlers:
                        logger.removeHandler(handler)
        for handler in root_logger.handlers[:]:
            if isinstance(handler, RPNoseLogHandler):
                root_logger.handlers.remove(handler)
        root_logger.addHandler(self.handler)
        # Also patch any non-propagating loggers in the tree
        for logger in logging.Logger.manager.loggerDict.values():
            if not getattr(logger, 'propagate', True) and hasattr(logger, "addHandler"):
                for handler in logger.handlers[:]:
                    if isinstance(handler, RPNoseLogHandler):
                        logger.handlers.remove(handler)
                logger.addHandler(self.handler)
        # to make sure everything gets captured
        loglevel = getattr(self, "loglevel", "NOTSET")
        root_logger.setLevel(getattr(logging, loglevel))

    def begin(self):
        """Called before any tests are collected or run. Use this to
        perform any setup needed before testing begins.
        """
        self.service = NoseServiceClass()

        self.service.init_service(endpoint=self.rp_endpoint,
                                  project=self.rp_project,
                                  token=self.rp_uuid,
                                  ignore_errors=False)


        # Start launch.
        self.launch = self.service.start_launch(name=self.rp_launch,
                                                description=self.rp_launch_description,
                                                mode=self.rp_mode)

        self.handler = RPNoseLogHandler(self.filters if self.filters else None)
        self.setupLoghandler()

    def _restore_stdout(self):
        """Restore stdout.
        """
        while self.stdout:
            self.end()

    def finalize(self, result):
        """Called after all report output, including output from all
        plugins, has been sent to the stream. Use this to print final
        test results or perform final cleanup. Return None to allow
        other plugins to continue printing, or any other value to stop
        them.

        :param result: test result object

        .. Note:: When tests are run under a test runner other than
           :class:`nose.core.TextTestRunner`, such as
           via ``python setup.py test``, this method may be called
           **before** the default report output is sent.
        """

        # Finish launch.
        self.service.finish_launch()

        # Due to async nature of the service we need to call terminate() method which
        # ensures all pending requests to server are processed.
        # Failure to call terminate() may result in lost data.
        self.service.terminate_service()
        self._restore_stdout()

    def startTest(self, test):
        """Prepare or wrap an individual test case. Called before
        execution of the test. The test passed here is a
        nose.case.Test instance; the case to be executed is in the
        test attribute of the passed case. To modify the test to be
        run, you should return a callable that takes one argument (the
        test result object) -- it is recommended that you *do not*
        side-effect the nose.case.Test instance you have been passed.

        Keep in mind that when you replace the test callable you are
        replacing the run() method of the test case -- including the
        exception handling and result calls, etc.

        :param test: the test case
        :type test: :class:`nose.case.Test`
        """
        self.start()
        test.status = None
        test.errors = None
        self.service.start_nose_item(self, test)
        self.setupLoghandler()

    def addDeprecated(self, test):
        """Called when a deprecated test is seen. DO NOT return a value
        unless you want to stop other plugins from seeing the deprecated
        test.

        .. warning :: DEPRECATED -- check error class in addError instead
        """
        test.status = "deprecated"
        self.service.post_log("DEPRECATED")

    def _addError(self, test, err):
        etype, value, tb = err
        test.errors = []

        test.errors.append(value)
        test.errors.append(str(etype.__name__) + ":\n" + "".join(traceback.format_tb(tb)))

    def _filterErrorForSkip(self, err):
        if isinstance(err, tuple) and isclass(err[0]):
            if issubclass(err[0], SkipTest):
                return True
        return False

    def _filterErrorForDepricated(self, err):
        if isinstance(err, tuple) and isclass(err[0]):
            if issubclass(err[0], DeprecatedTest):
                return True
        return False

    def addError(self, test,  err):
        """Called when a test raises an uncaught exception. DO NOT return a
        value unless you want to stop other plugins from seeing that the
        test has raised an error.
        Calling addSkip() and addDeprecated() from base plugin was
        deprecated and there is need to handle skipped and deprecated tests inside addError().

        :param test: the test case
        :type test: :class:`nose.case.Test`
        :param err: sys.exc_info() tuple
        :type err: 3-tuple
        """

        if self._filterErrorForSkip(err):
            self.addSkip(test)
        elif self._filterErrorForDepricated(err):
            self.addDeprecated(test)
        else:
            test.status = "error"
            self._addError(test, err)

    def addFailure(self, test, err):
        """Called when a test fails. DO NOT return a value unless you
        want to stop other plugins from seeing that the test has failed.

        :param test: the test case
        :type test: :class:`nose.case.Test`
        :param err: 3-tuple
        :type err: sys.exc_info() tuple
        """
        test.status = "failed"
        self._addError(test, err)

    def addSkip(self, test):
        """Called when a test is skipped. DO NOT return a value unless
        you want to stop other plugins from seeing the skipped test.

        .. warning:: DEPRECATED -- check error class in addError instead
        """
        test.status = "skipped"

    def addSuccess(self, test):
        """Called when a test passes. DO NOT return a value unless you
        want to stop other plugins from seeing the passing test.

        :param test: the test case
        :type test: :class:`nose.case.Test`
        """
        test.status = "success"

    def beforeTest(self, test):
        """Clear buffers and handlers before test.
        """
        self.setupLoghandler()

    def afterTest(self, test):
        """Clear capture buffer.
        """
        self.end()
        self._buf = None
        self.handler.truncate()

    def formatLogRecords(self):
        return list(map(safe_str, self.handler.buffer))

    def formatError(self, test, err):
        """Add captured output to error report.
        """
        test.capturedOutput = output = self.buffer
        self._buf = None
        if not output:
            # Don't return None as that will prevent other
            # formatters from formatting and remove earlier formatters
            # formats, instead return the err we got
            return err
        ec, ev, tb = err
        return (ec, self.addCaptureToErr(ev, output), tb)

    def formatFailure(self, test, err):
        """Add captured output to failure report.
        """
        return self.formatError(test, err)

    def start(self):
        self.stdout.append(sys.stdout)
        self._buf = StringIO()
        # Python 3's StringIO objects don't support setting encoding or errors
        # directly and they're already set to None.  So if the attributes
        # already exist, skip adding them.
        if (not hasattr(self._buf, 'encoding') and
                hasattr(sys.stdout, 'encoding')):
            self._buf.encoding = sys.stdout.encoding
        if (not hasattr(self._buf, 'errors') and
                hasattr(sys.stdout, 'errors')):
            self._buf.errors = sys.stdout.errors
        sys.stdout = self._buf

    def end(self):
        if self.stdout:
            sys.stdout = self.stdout.pop()

    def _get_buffer(self):
        if self._buf is not None:
            return self._buf.getvalue()

    buffer = property(_get_buffer, None, None, """Captured stdout output.""")

    def addCaptureToErr(self, ev, output):
        ev = exc_to_unicode(ev)
        output = force_unicode(output)
        return u'\n'.join([ev, output])

    def stopTest(self, test):
        """Called after each test is run. DO NOT return a value unless
        you want to stop other plugins from seeing that the test has stopped.

        :param test: the test case
        :type test: :class:`nose.case.Test`
        """
        test.capturedOutput = self.buffer
        test.capturedLogging = self.formatLogRecords()

        if test.capturedOutput:
            try: 
                self.service.post_log(safe_str(test.capturedOutput))
            except Exception:
                log.exception('Unexpected error during sending capturedOutput.')

        if test.capturedLogging:
            for x in test.capturedLogging:
                try: 
                    self.service.post_log(safe_str(x))
                except Exception:
                    log.exception('Unexpected error during sending capturedLogging.')

        if test.errors:
            try: 
                self.service.post_log(safe_str(test.errors[0]))
                self.service.post_log(safe_str(test.errors[1]), loglevel="ERROR")
            except Exception:
                log.exception('Unexpected error during sending errors.')

        if sys.version_info.major == 2:
            self._stop_test_2(test)
        elif sys.version_info.major == 3:
            self._stop_test_3(test)


    def _stop_test_2(self, test):
        if test.status == "skipped":
            self.service.finish_nose_item(status="SKIPPED")
        elif test.status == "success":
            self.service.finish_nose_item(status="PASSED")
        else:
            self.service.finish_nose_item(status="FAILED")

    def describeTest(self, test):
        return test.test._testMethodDoc

    def _stop_test_3(self, test):
        if test.test._outcome.skipped:
            self.service.finish_nose_item(status="SKIPPED")
        elif test.test._outcome.success:
            self.service.finish_nose_item(status="PASSED")
        else:
            self.service.finish_nose_item(status="FAILED")
