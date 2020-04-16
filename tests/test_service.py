import sys
import unittest
from delayed_assert import delayed_assert, expect, assert_expectations


if sys.version_info >= (3, 3):
    from unittest.mock import Mock, patch
else:
    from mock import Mock, patch

from nose_reportportal.service import NoseServiceClass


class TestException(Exception) :
    pass


class NoseServiceClassTestCase(unittest.TestCase):

    def setUp(self):
        self.service = NoseServiceClass()

    @patch('nose_reportportal.service.log')
    def test_init_service_with_RP_already_exists(self, mocked_log):
        self.service.rp = Mock()
        params = {
            'endpoint': Mock(),
            'project': Mock(),
            'token': Mock()
        }

        rp = self.service.init_service(**params)

        expect(lambda: self.assertIsNotNone(rp))
        expect(lambda: mocked_log.debug.assert_called_once_with('The pytest is already initialized'))
        assert_expectations()

    @patch('reportportal_client.service.requests')
    @patch('nose_reportportal.service.log')
    def test_init_service_with_no_RP_exists(self, mocked_log, mocked_requests):
        self.service.rp = None
        params = {
            'endpoint': 'http://test_endpoint',
            'project': 'test_project',
            'token': 'test_token'
        }

        rp = self.service.init_service(**params)

        expect(lambda: self.assertIsNotNone(rp))
        expect(lambda: self.assertEqual(params['endpoint'], self.service.rp.endpoint))
        expect(lambda: self.assertEqual(params['project'], self.service.rp.project))
        expect(lambda: self.assertEqual(params['token'], self.service.rp.token))

        expect(lambda: mocked_log.debug.assert_called_once_with(
            'ReportPortal - Init service: endpoint=%s, project=%s, uuid=%s',
            params['endpoint'], params['project'], params['token']
        ))
        assert_expectations()


    def test_terminate_service(self):
        params = {
            'endpoint': Mock(),
            'project': Mock(),
            'token': Mock()
        }

        self.service.init_service(**params)

        self.service.terminate_service()

        self.assertIsNone(self.service.rp)

    @patch('nose_reportportal.service.timestamp')
    def test_start_launch(self, mocked_timestamp):
        name = 'test_name'
        time = 123456789
        mocked_timestamp.return_value = time
        self.service.rp = Mock()

        self.service.start_launch(name=name)

        self.service.rp.start_launch.assert_called_once_with(
            name=name,
            start_time=time,
            description=None,
            mode=None,
            tags=None
        )

    @patch('nose_reportportal.service.timestamp')
    def test_start_nose_item(self, mocked_timestamp):
        self.service.rp = Mock()
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

        expect(lambda: self.service.rp.start_test_item.assert_called_once_with(
            name=name,
            description=ev.describeTest(),
            tags=test.test.suites,
            start_time=mocked_timestamp(),
            item_type='TEST',
            parameters=None
        ))
        expect(lambda: self.service.post_log.assert_called_once_with(name))

        self.service.post_log = service_post_log
        assert_expectations()

    @patch('nose_reportportal.service.timestamp')
    def test_finish_nose_item(self, mocked_timestamp):
        self.service.rp = Mock()
        service_post_log = self.service.post_log
        self.service.post_log = Mock()
        time = 123456789
        mocked_timestamp.return_value = time
        status = 'test_status'
        issue = 'test_issue'
        item_id = 0

        self.service.finish_nose_item(test_item=item_id, status=status, issue=issue)

        expect(lambda: self.service.rp.finish_test_item.assert_called_once_with(
            end_time=time, issue=issue, item_id=item_id, status=status
        ))
        expect(lambda: self.service.post_log.assert_called_once_with(status))
        assert_expectations()

        self.service.post_log = service_post_log

    @patch('nose_reportportal.service.timestamp')
    def test_finish_launch(self, mocked_timestamp):
        self.service.rp = Mock()
        status = 'test_status'
        time = 123456789
        mocked_timestamp.return_value = time

        self.service.finish_launch(status=status)

        self.service.rp.finish_launch.assert_called_once_with(
            end_time=time,
            status=status
        )

    @patch('nose_reportportal.service.timestamp')
    def test_post_log(self, mocked_timestamp):
        self.service.rp = Mock()
        message = 'test_message'
        time = 123456789
        mocked_timestamp.return_value = time

        self.service.post_log(message=message)

        self.service.rp.log.assert_called_once_with(
            message=message,
            time=time,
            level='INFO',
            attachment=None,
        )

    def test_get_issue_types_with_no_project_settiings(self):
        self.service.project_settings = None

        issue_types = self.service.get_issue_types()

        self.assertEqual({}, issue_types)

    def test_get_issue_types_with_project_settings(self):
        self.service.project_settings = {
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
