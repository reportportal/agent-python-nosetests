import sys
import unittest
import traceback
import random

if sys.version_info >= (3, 3):
    from unittest.mock import Mock, MagicMock, patch
else:
    from mock import Mock, MagicMock, patch

from nose import SkipTest
from nose.plugins.deprecated import DeprecatedTest

from nose_reportportal.plugin import ReportPortalPlugin


class TestException(Exception):
    pass


class ReportPortalPluginTestCase(unittest.TestCase):

    def setUp(self):
        self.plugin = ReportPortalPlugin()
        self.test_object = Mock()
        self.test_object.status = None
        self.plugin.service = Mock()

    def test_addSuccess(self):
        self.plugin.addSuccess(self.test_object)

        self.assertEqual(self.test_object.status, 'success')

    def test_addDeprecated(self):
        self.plugin.addDeprecated(self.test_object)

        self.assertEqual(self.test_object.status, 'deprecated')
        self.plugin.service.post_log.assert_called_once_with('DEPRECATED')

    def test_addSkip(self):
        self.plugin.addSkip(self.test_object)

        self.assertEqual(self.test_object.status, 'skipped')

    @patch.object(ReportPortalPlugin, '_addError')
    def test_addError(self, mocked__addError):
        err = (TestException, TestException('test addError with an uncaught exception'), Mock())

        self.plugin.addError(self.test_object, err)

        self.assertEqual('error', self.test_object.status)
        mocked__addError.assert_called_once_with(self.test_object, err)

    @patch.object(ReportPortalPlugin, 'addSkip')
    def test_addError_with_SkipTest_exception(self, mocked_addSkip):
        err = (SkipTest, SkipTest('test addError with SkipTest exception'), Mock())

        self.plugin.addError(self.test_object, err)

        mocked_addSkip.assert_called_once_with(self.test_object)

    @patch.object(ReportPortalPlugin, 'addDeprecated')
    def test_addError_with_DeprecatedTest_exception(self, mocked_addDeprecated):
        err = (DeprecatedTest, DeprecatedTest('test addError with DeprecatedTest exception'), Mock())

        self.plugin.addError(self.test_object, err)

        mocked_addDeprecated.assert_called_once_with(self.test_object)

    def test__addError(self):
        try:
            raise TestException('')
        except TestException:
            err = sys.exc_info()
        expected_test_err_value = err[1]
        expected_test_err_info = str(err[0].__name__) + ":\n" + "".join(traceback.format_tb(err[2]))

        self.plugin._addError(self.test_object, err)

        self.assertEqual(expected_test_err_value, self.test_object.errors[0])
        self.assertEqual(expected_test_err_info, self.test_object.errors[1])

    @patch.object(ReportPortalPlugin, '_addError')
    def test_addFailure(self, mocked__addError):
        err = (TestException, TestException('test addError with an uncaught exception'), Mock())

        self.plugin.addFailure(self.test_object, err)

        self.assertEqual('failed', self.test_object.status)
        mocked__addError.assert_called_once_with(self.test_object, err)

    def test_end(self):
        self.plugin.stdout.append(MagicMock())

        self.plugin.end()

        self.assertEqual(0, len(self.plugin.stdout))

    def test___restore_stdout(self):
        for _ in range(random.randint(1, 10)):
            self.plugin.stdout.append(MagicMock())

        self.plugin._restore_stdout()

        self.assertEqual(0, len(self.plugin.stdout))

    @patch.object(ReportPortalPlugin, '_restore_stdout')
    def test_finalize(self, mocked__restore_stdout):
        self.plugin.finalize(result=Mock())

        self.plugin.service.finish_launch.assert_called_once_with()
        self.plugin.service.terminate_service.assert_called_once_with()
        mocked__restore_stdout.assert_called_once_with()

    @patch.object(ReportPortalPlugin, 'setupLoghandler')
    @patch.object(ReportPortalPlugin, 'start')
    def test_start_test(self, mocked_start, mocked_setupLoghandler):
        self.test_object.status = Mock()
        self.test_object.errors = Mock()

        self.plugin.startTest(self.test_object)

        self.assertIsNone(self.test_object.status)
        self.assertIsNone(self.test_object.errors)
        self.plugin.service.start_nose_item.assert_called_once_with(self.plugin, self.test_object)
        mocked_start.assert_called_once_with()
        mocked_setupLoghandler.assert_called_once_with()

    @patch.object(ReportPortalPlugin, 'setupLoghandler')
    def test_before_test(self, mocked_setupLoghandler):
        self.plugin.beforeTest(test=Mock())

        mocked_setupLoghandler.assert_called_once_with()

    @patch.object(ReportPortalPlugin, 'end')
    def test_afterTest(self, mocked_end):
        self.plugin._buf = Mock()
        self.plugin.handler = Mock()

        self.plugin.afterTest(test=Mock())

        self.assertIsNone(self.plugin._buf)
        self.plugin.handler.truncate.assert_called_once_with()
        mocked_end.assert_called_once_with()

    def test_formatLogRecords(self):
        self.plugin.handler = Mock()
        self.plugin.handler.buffer = ['val1', TestException('val2')]
        expected_result = ['val1', 'val2']

        result = self.plugin.formatLogRecords()

        self.assertEqual(expected_result, result)

    def test__stop_test_2_with_test_status_skipped(self):
        self.test_object.status = 'skipped'
        self.test_object.test_item = 0

        self.plugin._stop_test_2(self.test_object)

        self.plugin.service.finish_nose_item.assert_called_once_with(self.test_object.test_item, status='SKIPPED')

    def test__stop_test_2_with_test_status_success(self):
        self.test_object.status = 'success'
        self.test_object.test_item = 0

        self.plugin._stop_test_2(self.test_object)

        self.plugin.service.finish_nose_item.assert_called_once_with(self.test_object.test_item, status='PASSED')

    def test__stop_test_2_with_test_other_status(self):
        self.test_object.status = 'other'
        self.test_object.test_item = 0

        self.plugin._stop_test_2(self.test_object)

        self.plugin.service.finish_nose_item.assert_called_once_with(self.test_object.test_item, status='FAILED')

    def test__stop_test_3_with_test_status_skipped(self):
        self.test_object.test._outcome.skipped = True
        self.test_object.test._outcome.success = False
        self.test_object.test._outcome.other = False
        self.test_object.test_item = 0

        self.plugin._stop_test_3(self.test_object)

        self.plugin.service.finish_nose_item.assert_called_once_with(self.test_object.test_item, status='SKIPPED')

    def test__stop_test_3_with_test_status_success(self):
        self.test_object.test._outcome.skipped = False
        self.test_object.test._outcome.success = True
        self.test_object.test._outcome.other = False
        self.test_object.test_item = 0

        self.plugin._stop_test_3(self.test_object)

        self.plugin.service.finish_nose_item.assert_called_once_with(self.test_object.test_item, status='PASSED')

    def test__stop_test_3_with_test_other_status(self):
        self.test_object.test._outcome.skipped = False
        self.test_object.test._outcome.success = False
        self.test_object.test._outcome.other = True
        self.test_object.test_item = 0

        self.plugin._stop_test_3(self.test_object)

        self.plugin.service.finish_nose_item.assert_called_once_with(self.test_object.test_item, status='FAILED')


if __name__ == '__main__':
    unittest.main()