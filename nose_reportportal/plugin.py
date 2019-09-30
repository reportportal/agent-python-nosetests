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

import sys
if sys.version_info.major == 2:
    import ConfigParser as configparser
else:
    import configparser
import logging
import traceback
import time
from nose.plugins.base import Plugin
from .service import NoseServiceClass

log = logging.getLogger(__name__)

class RPNoseLogHandler(logging.Handler):
    # Map loglevel codes from `logging` module to ReportPortal text names:
    _loglevel_map = {
        logging.NOTSET: 'TRACE',
        logging.DEBUG: 'DEBUG',
        logging.INFO: 'INFO',
        logging.WARNING: 'WARN',
        logging.ERROR: 'ERROR',
        logging.CRITICAL: 'ERROR',
    }
    _sorted_levelnos = sorted(_loglevel_map.keys(), reverse=True)

    def __init__(self, service,
                 level=logging.NOTSET,
                 endpoint=None):
        super(RPNoseLogHandler, self).__init__(level)
        self.service = service
        self.ignored_record_names = ('reportportal_client',)
        self.endpoint = endpoint

    def filter(self, record):
        # if self.filter_reportportal_client_logs is False:
        #    return True
        if record.name.startswith(self.ignored_record_names):
            return False
        if record.name == 'urllib3.connectionpool':
            # Filter the reportportal_client requests instance
            # urllib3 usage
            if self.endpoint in self.format(record):
                return False
        return True

    def emit(self, record):
        msg = ''

        try:
            msg = self.format(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            self.handleError(record)

        for level in self._sorted_levelnos:
            if level <= record.levelno:

                return self.service.post_log(msg, loglevel=self._loglevel_map[level],
                                        attachment=record.__dict__.get('attachment', None))


class ReportPortalPlugin(Plugin):
    can_configure = True
    score = 200
    status = {}
    enableOpt = None
    name = "reportportal"

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
                          default=None,
                          dest='rp_launch_description',
                          help='description of a lauch')

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
            self.clear = True
            if "base" in config.sections():
                self.rp_uuid = config.get("base", "rp_uuid")
                self.rp_endpoint = config.get("base", "rp_endpoint")
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
        # make sure there isn't one already
        # you can't simply use "if self.handler not in root_logger.handlers"
        # since at least in unit tests this doesn't work --
        # LogCapture() is instantiated for each test case while root_logger
        # is module global
        # so we always add new MyMemoryHandler instance
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

        #self.handler = RPNoseLogHandler(service=self.service, level=logging.DEBUG, endpoint=self.rp_endpoint)
        #self.setupLoghandler()

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
        test.status = None
        self.service.start_nose_item(self, test)

    def addDeprecated(self, test):
        """Called when a deprecated test is seen. DO NOT return a value
        unless you want to stop other plugins from seeing the deprecated
        test.

        .. warning :: DEPRECATED -- check error class in addError instead
        """
        test.status = "depricated"
        self.service.post_log("Deprecated test")

    def _sendError(self, test, err):
        etype, value, tb = err
        self.service.post_log(value)
        self.service.post_log(str(etype.__name__) + ":\n" +
                         "".join(traceback.format_tb(tb)), "ERROR")

    def addError(self, test,  err):
        """Called when a test raises an uncaught exception. DO NOT return a
        value unless you want to stop other plugins from seeing that the
        test has raised an error.

        :param test: the test case
        :type test: :class:`nose.case.Test`
        :param err: sys.exc_info() tuple
        :type err: 3-tuple
        """
        test.status = "error"
        self._sendError(test, err)

    def addFailure(self, test, err):
        """Called when a test fails. DO NOT return a value unless you
        want to stop other plugins from seeing that the test has failed.

        :param test: the test case
        :type test: :class:`nose.case.Test`
        :param err: 3-tuple
        :type err: sys.exc_info() tuple
        """
        test.status = "failed"
        self._sendError(test, err)

    def addSkip(self, test):
        """Called when a test is skipped. DO NOT return a value unless
        you want to stop other plugins from seeing the skipped test.

        .. warning:: DEPRECATED -- check error class in addError instead
        """
        test.status = "skipped"
        self.service.post_log("SKIPPED test")

    def addSuccess(self, test):
        """Called when a test passes. DO NOT return a value unless you
        want to stop other plugins from seeing the passing test.

        :param test: the test case
        :type test: :class:`nose.case.Test`
        """
        test.status = "success"
        self.service.post_log(message="OK")

    def stopTest(self, test):
        """Called after each test is run. DO NOT return a value unless
        you want to stop other plugins from seeing that the test has stopped.

        :param test: the test case
        :type test: :class:`nose.case.Test`
        """
        if test.capturedOutput:
            self.service.post_log(str(test.capturedOutput))

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
