import sys
import unittest
import traceback
from unittest.mock import Mock
from unittest.mock import patch
from nose import SkipTest
from nose.plugins.deprecated import DeprecatedTest

from nose_reportportal.plugin import ReportPortalPlugin


class TestException(Exception):
    pass


class ReportPortalPluginTestCase(unittest.TestCase):

    def setUp(self) -> None:
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


if __name__ == '__main__':
    unittest.main()
