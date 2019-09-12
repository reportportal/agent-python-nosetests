import logging
import re
import sys
import os
import subprocess
import traceback
from mimetypes import guess_type
import configparser

from reportportal_client import ReportPortalServiceAsync, ReportPortalService

from nose.plugins.base import Plugin
from nose.util import src, tolist
from time import time



log = logging.getLogger(__name__)

def timestamp():
    return str(int(time() * 1000))


def my_error_handler(exc_info):
    """
    This callback function will be called by async service client when error occurs.
    Return True if error is not critical and you want to continue work.
    :param exc_info: result of sys.exc_info() -> (type, value, traceback)
    :return:
    """
    print("Error occurred: {}".format(exc_info[1]))
    traceback.print_exception(*exc_info)


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
        #if self.filter_reportportal_client_logs is False:
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

                return self.service.log(timestamp(), msg, level=self._loglevel_map[level],
                    attachment=record.__dict__.get('attachment', None)
                )

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
                          default=None,
                          dest='rp_mode',
                          help='level of logging')

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
            config = configparser.ConfigParser()
            config.read(self.rp_config)

            if options.rp_launch:
                slaunch = options.rp_launch
            else:
                slaunch = "(unit tests)"
                if "type=integration" in options.attr:
                    slaunch ="(integration tests)"
                elif "type=component" in options.attr:
                    slaunch = "(component tests)"

            self.rp_mode = options.rp_mode or "DEBUG"
            self.clear = True
            if "base" in config:
                self.rp_uuid = config.get("base", "rp_uuid", fallback="")
                self.rp_endpoint = config.get("base", "rp_endpoint", fallback="")
                self.rp_project = config.get("base", "rp_project", fallback="")
                self.rp_launch = config.get("base", "rp_launch", fallback="{}").format(slaunch)
                self.rp_launch_tags = config.get("base", "rp_launch_tags", fallback="")
                self.rp_launch_description = config.get("base", "rp_launch_description", fallback="")

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
        self.service = ReportPortalServiceAsync(endpoint=self.rp_endpoint, project=self.rp_project,
                                                   token=self.rp_uuid, error_handler=my_error_handler, queue_get_timeout=20)

        log.setLevel(logging.DEBUG)

        # Start launch.
        self.launch = self.service.start_launch(name=self.rp_launch,
                                      start_time=timestamp(),
                                      description=self.rp_launch_description, mode=self.rp_mode)
        self.handler = RPNoseLogHandler(service=self.service, level=logging.DEBUG,endpoint=self.rp_endpoint)
        self.setupLoghandler()


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
        self.service.finish_launch(end_time=timestamp())

        # Due to async nature of the service we need to call terminate() method which
        # ensures all pending requests to server are processed.
        # Failure to call terminate() may result in lost data.
        self.service.terminate()


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

        self.service.start_test_item(name=str(test),
                                       description=test.test._testMethodDoc,
                                       tags=test.test.suites,
                                       start_time=timestamp(),
                                       item_type='TEST',
                                       parameters={})
        self.setupLoghandler()
        self.service.log(timestamp(), str(test), "INFO")


    def addDeprecated(self, test):
        """Called when a deprecated test is seen. DO NOT return a value
        unless you want to stop other plugins from seeing the deprecated
        test.

        .. warning :: DEPRECATED -- check error class in addError instead
        """
        self.service.log(timestamp(), "Deprecated test", "INFO")

    def _sendError(self, test, err):
        etype, value, tb = err
        self.service.log(timestamp(), value, "INFO")
        self.service.log(timestamp(), str(etype.__name__) + ":\n" +
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
        self._sendError(test, err)


    def addFailure(self, test, err):
        """Called when a test fails. DO NOT return a value unless you
        want to stop other plugins from seeing that the test has failed.

        :param test: the test case
        :type test: :class:`nose.case.Test`
        :param err: 3-tuple
        :type err: sys.exc_info() tuple
        """
        self._sendError(test, err)


    def addSkip(self, test):
        """Called when a test is skipped. DO NOT return a value unless
        you want to stop other plugins from seeing the skipped test.

        .. warning:: DEPRECATED -- check error class in addError instead
        """
        self.service.log(timestamp(), "SKIPPED test", "INFO")


    def addSuccess(self, test):
        """Called when a test passes. DO NOT return a value unless you
        want to stop other plugins from seeing the passing test.

        :param test: the test case
        :type test: :class:`nose.case.Test`
        """
        self.service.log(time=timestamp(), message="OK", level="INFO")


    def stopTest(self, test):
        """Called after each test is run. DO NOT return a value unless
        you want to stop other plugins from seeing that the test has stopped.

        :param test: the test case
        :type test: :class:`nose.case.Test`
        """
        if test.capturedOutput:
            self.service.log(timestamp(), str(test.capturedOutput), "INFO")

        if test.test._outcome.skipped:
            self.service.finish_test_item(end_time=timestamp(), status="SKIPPED")
        elif test.test._outcome.success:
            self.service.finish_test_item(end_time=timestamp(), status="PASSED")
        else:
            self.service.finish_test_item(end_time=timestamp(), status="FAILED")