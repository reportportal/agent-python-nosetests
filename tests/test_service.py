import unittest
from unittest.mock import Mock
from unittest.mock import patch
from six.moves import queue

from nose_reportportal.service import NoseServiceClass


class TestException(Exception):
    pass


class NoseServiceClassTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.service = NoseServiceClass()

    @patch('nose_reportportal.service.log')
    def test_init_service_with_RP_already_exists(self, mocked_log):
        self.service.RP = Mock()
        params = {
            'endpoint': Mock(),
            'project': Mock(),
            'token': Mock()
        }

        rp = self.service.init_service(**params)

        self.assertIsNotNone(rp)
        mocked_log.debug.assert_called_once_with('The pytest is already initialized')

    @patch('reportportal_client.service.requests')
    @patch('nose_reportportal.service.log')
    def test_init_service_with_no_RP_exists(self, mocked_log, mocked_requests):
        self.service.RP = None
        params = {
            'endpoint': ' http://test_endpoint',
            'project': 'test_project',
            'token': 'test_token'
        }

        rp = self.service.init_service(**params)

        self.assertIsNotNone(rp)
        self.assertEqual(params['endpoint'], self.service.RP.rp_client.endpoint)
        self.assertEqual(params['project'], self.service.RP.rp_client.project)
        self.assertEqual(params['token'], self.service.RP.rp_client.token)

        mocked_log.debug.assert_called_once_with(
            'ReportPortal - Init service: endpoint=%s, project=%s, uuid=%s'
            % (params['endpoint'], params['project'], params['token'])
        )

    @patch.object(NoseServiceClass, 'terminate_service')
    def test_async_error_handler(self, mocked_terminate_service):
        exc_info = (TestException, TestException('test exception info'), Mock())
        self.service._errors = Mock()
        self.service.async_error_handler(exc_info)

        mocked_terminate_service.assert_called_once_with(nowait=True)
        self.service._errors.put_nowait.assert_called_once_with(exc_info)
        self.assertIsNone(self.service.RP)

        self.service._errors = queue.Queue()

    def test_terminate_service(self):
        params = {
            'endpoint': Mock(),
            'project': Mock(),
            'token': Mock()
        }

        self.service.init_service(**params)

        self.service.terminate_service()

        self.assertIsNone(self.service.RP)

    @patch('nose_reportportal.service.timestamp')
    def test_start_launch(self, mocked_timestamp):
        name = 'test_name'
        time = 123456789
        mocked_timestamp.return_value = time
        self.service.RP = Mock()

        self.service.start_launch(name=name)

        self.service.RP.start_launch.assert_called_once_with(
            name=name,
            start_time=time,
            description=None,
            mode=None,
            tags=None
        )

    @patch('nose_reportportal.service.timestamp')
    def test_start_nose_item(self, mocked_timestamp):
        self.service.RP = Mock()
        service_post_log = self.service.post_log
        self.service.post_log = Mock()
        time = 123456789
        mocked_timestamp.return_value = time
        test = Mock()
        test.test.suites = ['test_tag_1', 'test_tag_2']
        name = str(test)
        ev = Mock()
        ev.describeTest.return_value = 'test_description'

        self.service.start_nose_item(ev=ev, test=test)

        self.service.RP.start_test_item.assert_called_once_with(
            name=name,
            description=ev.describeTest(),
            tags=test.test.suites,
            start_time=mocked_timestamp(),
            item_type='TEST',
            parameters={}
        )
        self.service.post_log.assert_called_once_with(name)

        self.service.post_log = service_post_log

    @patch('nose_reportportal.service.timestamp')
    def test_finish_nose_item(self, mocked_timestamp):
        self.service.RP = Mock()
        service_post_log = self.service.post_log
        self.service.post_log = Mock()
        time = 123456789
        mocked_timestamp.return_value = time
        status = 'test_status'
        issue = 'test_issue'

        self.service.finish_nose_item(status=status, issue=issue)

        self.service.RP.finish_test_item.assert_called_once_with(
            end_time=time,
            status=status,
            issue=issue
        )
        self.service.post_log.assert_called_once_with(status)

        self.service.post_log = service_post_log

    @patch('nose_reportportal.service.timestamp')
    def test_finish_launch(self, mocked_timestamp):
        self.service.RP = Mock()
        status = 'test_status'
        time = 123456789
        mocked_timestamp.return_value = time

        self.service.finish_launch(status=status)

        self.service.RP.finish_launch.assert_called_once_with(
            end_time=time,
            status=status
        )

    @patch('nose_reportportal.service.timestamp')
    def test_post_log(self, mocked_timestamp):
        self.service.RP = Mock()
        message = 'test_message'
        time = 123456789
        mocked_timestamp.return_value = time

        self.service.post_log(message=message)

        self.service.RP.log.assert_called_once_with(
            message=message,
            time=time,
            level='INFO',
            attachment=None,
        )

    @patch('nose_reportportal.service.sys')
    @patch('nose_reportportal.service.traceback')
    def test__stop_if_necessary(self, mocked_traceback, mocked_sys):
        exc = (TestException, TestException('test exception info'), Mock())
        self.service._errors.put(exc)
        self.service.ignore_errors = False

        self.service._stop_if_necessary()

        mocked_traceback.print_exception.assert_called_once_with(exc[0], exc[1], exc[2])
        mocked_sys.exit.assert_called_once_with(exc[1])

    def test_get_issue_types_with_no_project_settiings(self):
        self.service.project_settiings = None

        issue_types = self.service.get_issue_types()

        self.assertEqual({}, issue_types)

    def test_get_issue_types_with_project_settiings(self):
        self.service.project_settiings = {
            'subTypes': {
                'AUTOMATION_BUG': [{'shortName': 'AUTOMATION_BUG_shortName_1', 'locator': 'AUTOMATION_BUG_locator_1'}],
                'PRODUCT_BUG': [{'shortName': 'PRODUCT_BUG_shortName_1', 'locator': 'PRODUCT_BUG_locator_1'}],
                'SYSTEM_ISSUE': [{'shortName': 'SYSTEM_ISSUE_shortName_1', 'locator': 'SYSTEM_ISSUE_locator_1'}],
                'NO_DEFECT': [{'shortName': 'NO_DEFECT_shortName_1', 'locator': 'NO_DEFECT_locator_1'}],
                'TO_INVESTIGATE': [{'shortName': 'TO_INVESTIGATE_shortName_1', 'locator': 'TO_INVESTIGATE_locator_1'}]
            }
        }

        expected_issue_types = {
            'AUTOMATION_BUG_shortName_1': 'AUTOMATION_BUG_locator_1',
            'PRODUCT_BUG_shortName_1': 'PRODUCT_BUG_locator_1',
            'SYSTEM_ISSUE_shortName_1': 'SYSTEM_ISSUE_locator_1',
            'NO_DEFECT_shortName_1': 'NO_DEFECT_locator_1',
            'TO_INVESTIGATE_shortName_1': 'TO_INVESTIGATE_locator_1',
        }

        issue_types = self.service.get_issue_types()

        self.assertEqual(expected_issue_types, issue_types)


if __name__ == '__main__':
    unittest.main()
