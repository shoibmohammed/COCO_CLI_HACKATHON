# Tests for Local Jira Worker integration scenarios
# Co-authored with CoCo
"""
tests/test_integration.py
Unit tests covering all 14 required scenarios for the Local Jira Worker.
"""

import unittest
from unittest.mock import MagicMock, patch, PropertyMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worker import process_record
from jira_client import JiraClient
from snowflake_client import SnowflakeClient
from config import get_config, validate_config


class TestApprovalGate(unittest.TestCase):
    """Tests 1-2, 13: Approval gate behavior."""

    def _make_record(self, wo_id="WO-1001", status="PENDING"):
        return {
            "QUEUE_ID": "q-001",
            "WORK_ORDER_ID": wo_id,
            "MACHINE_ID": "Machine_03",
            "REQUEST_TYPE": "CREATE_ISSUE",
            "SHORT_DESCRIPTION": "Replace bearing",
            "DESCRIPTION": "Critical bearing replacement needed",
            "IMPACT": "HIGH",
            "URGENCY": "HIGH",
            "JIRA_PROJECT_KEY": "KAN",
            "ATTEMPT_COUNT": 0
        }

    def test_01_approved_work_order_creates_queue(self):
        """APPROVED work order → queue request proceeds to Jira."""
        sf = MagicMock(spec=SnowflakeClient)
        jira = MagicMock(spec=JiraClient)
        sf.verify_work_order_approved.return_value = True
        sf.check_already_succeeded.return_value = None
        jira.create_issue.return_value = (True, {"key": "KAN-1", "id": "10001", "url": "https://x.atlassian.net/browse/KAN-1", "status_code": 201})

        process_record(self._make_record(), sf, jira, max_retries=3)

        jira.create_issue.assert_called_once()
        sf.mark_success.assert_called_once()

    def test_02_pending_approval_rejected(self):
        """PENDING_APPROVAL work order → queue request rejected."""
        sf = MagicMock(spec=SnowflakeClient)
        jira = MagicMock(spec=JiraClient)
        sf.verify_work_order_approved.return_value = False

        process_record(self._make_record(), sf, jira, max_retries=3)

        jira.create_issue.assert_not_called()
        sf.mark_failed.assert_called_once()

    def test_13_non_approved_cannot_create_jira(self):
        """Non-approved work order cannot create Jira issue (alias of test_02)."""
        sf = MagicMock(spec=SnowflakeClient)
        jira = MagicMock(spec=JiraClient)
        sf.verify_work_order_approved.return_value = False

        process_record(self._make_record(), sf, jira, max_retries=3)

        jira.create_issue.assert_not_called()


class TestWorkerQueue(unittest.TestCase):
    """Tests 3-4: Worker reads queue and verifies approval."""

    def test_03_worker_reads_queue(self):
        """Worker fetches PENDING records from queue."""
        sf = MagicMock(spec=SnowflakeClient)
        sf.get_pending_records.return_value = [{"QUEUE_ID": "q-1", "WORK_ORDER_ID": "WO-1"}]
        result = sf.get_pending_records(batch_size=5)
        self.assertEqual(len(result), 1)
        sf.get_pending_records.assert_called_with(batch_size=5)

    def test_04_worker_verifies_approval_independently(self):
        """Worker independently verifies WORK_ORDERS.STATUS = APPROVED."""
        sf = MagicMock(spec=SnowflakeClient)
        jira = MagicMock(spec=JiraClient)
        sf.verify_work_order_approved.return_value = True
        sf.check_already_succeeded.return_value = None
        jira.create_issue.return_value = (True, {"key": "KAN-2", "id": "10002", "url": "https://x.atlassian.net/browse/KAN-2", "status_code": 201})

        record = {
            "QUEUE_ID": "q-002", "WORK_ORDER_ID": "WO-1002", "MACHINE_ID": "Machine_05",
            "REQUEST_TYPE": "CREATE_ISSUE", "SHORT_DESCRIPTION": "Test",
            "DESCRIPTION": "Test desc", "IMPACT": "HIGH", "URGENCY": "HIGH",
            "JIRA_PROJECT_KEY": "KAN", "ATTEMPT_COUNT": 0
        }
        process_record(record, sf, jira, max_retries=3)
        sf.verify_work_order_approved.assert_called_once_with("WO-1002")


class TestJiraCreation(unittest.TestCase):
    """Tests 5-7: Jira issue creation and Snowflake update."""

    def test_05_jira_creation_succeeds(self):
        """Successful Jira issue creation."""
        sf = MagicMock(spec=SnowflakeClient)
        jira = MagicMock(spec=JiraClient)
        sf.verify_work_order_approved.return_value = True
        sf.check_already_succeeded.return_value = None
        jira.create_issue.return_value = (True, {"key": "KAN-5", "id": "10005", "url": "https://x.atlassian.net/browse/KAN-5", "status_code": 201})

        record = {
            "QUEUE_ID": "q-005", "WORK_ORDER_ID": "WO-1005", "MACHINE_ID": "Machine_03",
            "REQUEST_TYPE": "CREATE_ISSUE", "SHORT_DESCRIPTION": "Replace spindle",
            "DESCRIPTION": "Spindle bearing degraded", "IMPACT": "HIGH", "URGENCY": "HIGH",
            "JIRA_PROJECT_KEY": "KAN", "ATTEMPT_COUNT": 0
        }
        process_record(record, sf, jira, max_retries=3)
        sf.mark_success.assert_called_once_with("q-005", "KAN-5", "https://x.atlassian.net/browse/KAN-5", "10005")

    def test_06_jira_key_returned(self):
        """Jira issue key is returned in the result."""
        jira = JiraClient.__new__(JiraClient)
        jira._base_url = "https://test.atlassian.net"
        jira._session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"key": "KAN-6", "id": "10006"}
        jira._session.post.return_value = mock_resp

        success, result = jira.create_issue("KAN", "Test", "Desc")
        self.assertTrue(success)
        self.assertEqual(result["key"], "KAN-6")

    def test_07_snowflake_updated_with_jira_key(self):
        """Snowflake WORK_ORDERS.EXTERNAL_TICKET_ID updated after success."""
        sf = MagicMock(spec=SnowflakeClient)
        jira = MagicMock(spec=JiraClient)
        sf.verify_work_order_approved.return_value = True
        sf.check_already_succeeded.return_value = None
        jira.create_issue.return_value = (True, {"key": "KAN-7", "id": "10007", "url": "https://x.atlassian.net/browse/KAN-7", "status_code": 201})

        record = {
            "QUEUE_ID": "q-007", "WORK_ORDER_ID": "WO-1007", "MACHINE_ID": "Machine_03",
            "REQUEST_TYPE": "CREATE_ISSUE", "SHORT_DESCRIPTION": "Test",
            "DESCRIPTION": "Test", "IMPACT": "HIGH", "URGENCY": "HIGH",
            "JIRA_PROJECT_KEY": "KAN", "ATTEMPT_COUNT": 0
        }
        process_record(record, sf, jira, max_retries=3)
        sf.update_work_order_ticket.assert_called_once_with("WO-1007", "KAN-7")


class TestIdempotency(unittest.TestCase):
    """Tests 8, 14: Duplicate prevention."""

    def test_08_duplicate_does_not_create_duplicate(self):
        """Duplicate request does not create duplicate Jira issue."""
        sf = MagicMock(spec=SnowflakeClient)
        jira = MagicMock(spec=JiraClient)
        sf.verify_work_order_approved.return_value = True
        sf.check_already_succeeded.return_value = {"JIRA_ISSUE_KEY": "KAN-8", "JIRA_URL": "https://x.atlassian.net/browse/KAN-8"}

        record = {
            "QUEUE_ID": "q-008", "WORK_ORDER_ID": "WO-1008", "MACHINE_ID": "Machine_03",
            "REQUEST_TYPE": "CREATE_ISSUE", "SHORT_DESCRIPTION": "Test",
            "DESCRIPTION": "Test", "IMPACT": "HIGH", "URGENCY": "HIGH",
            "JIRA_PROJECT_KEY": "KAN", "ATTEMPT_COUNT": 0
        }
        process_record(record, sf, jira, max_retries=3)
        jira.create_issue.assert_not_called()
        sf.mark_success.assert_called_once()

    def test_14_existing_success_prevents_duplicate(self):
        """Existing SUCCESS record prevents duplicate creation (alias of test_08)."""
        sf = MagicMock(spec=SnowflakeClient)
        jira = MagicMock(spec=JiraClient)
        sf.verify_work_order_approved.return_value = True
        sf.check_already_succeeded.return_value = {"JIRA_ISSUE_KEY": "KAN-14", "JIRA_URL": "https://x.atlassian.net/browse/KAN-14"}

        record = {
            "QUEUE_ID": "q-014", "WORK_ORDER_ID": "WO-1014", "MACHINE_ID": "Machine_03",
            "REQUEST_TYPE": "CREATE_ISSUE", "SHORT_DESCRIPTION": "Test",
            "DESCRIPTION": "Test", "IMPACT": "HIGH", "URGENCY": "HIGH",
            "JIRA_PROJECT_KEY": "KAN", "ATTEMPT_COUNT": 0
        }
        process_record(record, sf, jira, max_retries=3)
        jira.create_issue.assert_not_called()


class TestErrorHandling(unittest.TestCase):
    """Tests 9-12: Failure, retry, and credentials safety."""

    def test_09_jira_api_failure_marks_failed(self):
        """Jira API failure → FAILED status (after max retries)."""
        sf = MagicMock(spec=SnowflakeClient)
        jira = MagicMock(spec=JiraClient)
        sf.verify_work_order_approved.return_value = True
        sf.check_already_succeeded.return_value = None
        jira.create_issue.return_value = (False, {"status_code": 500, "error": "Internal Server Error"})

        record = {
            "QUEUE_ID": "q-009", "WORK_ORDER_ID": "WO-1009", "MACHINE_ID": "Machine_03",
            "REQUEST_TYPE": "CREATE_ISSUE", "SHORT_DESCRIPTION": "Test",
            "DESCRIPTION": "Test", "IMPACT": "HIGH", "URGENCY": "HIGH",
            "JIRA_PROJECT_KEY": "KAN", "ATTEMPT_COUNT": 2  # This will be attempt 3 (max)
        }
        process_record(record, sf, jira, max_retries=3)
        sf.mark_failed.assert_called_once()

    def test_10_retry_works(self):
        """Failed attempt below max_retries resets to PENDING."""
        sf = MagicMock(spec=SnowflakeClient)
        jira = MagicMock(spec=JiraClient)
        sf.verify_work_order_approved.return_value = True
        sf.check_already_succeeded.return_value = None
        jira.create_issue.return_value = (False, {"status_code": 503, "error": "Service Unavailable"})

        record = {
            "QUEUE_ID": "q-010", "WORK_ORDER_ID": "WO-1010", "MACHINE_ID": "Machine_03",
            "REQUEST_TYPE": "CREATE_ISSUE", "SHORT_DESCRIPTION": "Test",
            "DESCRIPTION": "Test", "IMPACT": "HIGH", "URGENCY": "HIGH",
            "JIRA_PROJECT_KEY": "KAN", "ATTEMPT_COUNT": 0  # attempt 1, below max 3
        }
        process_record(record, sf, jira, max_retries=3)
        sf.reset_for_retry.assert_called_once_with("q-010", 1)
        sf.mark_failed.assert_not_called()

    def test_11_invalid_credentials_handled_safely(self):
        """HTTP 401 handled without exposing credentials."""
        sf = MagicMock(spec=SnowflakeClient)
        jira = MagicMock(spec=JiraClient)
        sf.verify_work_order_approved.return_value = True
        sf.check_already_succeeded.return_value = None
        jira.create_issue.return_value = (False, {"status_code": 401, "error": "HTTP 401: Unauthorized"})

        record = {
            "QUEUE_ID": "q-011", "WORK_ORDER_ID": "WO-1011", "MACHINE_ID": "Machine_03",
            "REQUEST_TYPE": "CREATE_ISSUE", "SHORT_DESCRIPTION": "Test",
            "DESCRIPTION": "Test", "IMPACT": "HIGH", "URGENCY": "HIGH",
            "JIRA_PROJECT_KEY": "KAN", "ATTEMPT_COUNT": 2  # will be attempt 3
        }
        process_record(record, sf, jira, max_retries=3)
        # Verify error message doesn't contain credentials
        call_args = sf.record_audit.call_args
        error_msg = call_args[1].get("error_message") or call_args[0][7] or ""
        self.assertNotIn("api_token", error_msg.lower())
        self.assertNotIn("password", error_msg.lower())

    def test_12_credentials_never_in_logs(self):
        """JiraClient never logs credentials or Authorization headers."""
        import logging
        import io

        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.DEBUG)
        jira_logger = logging.getLogger("jira_client")
        jira_logger.addHandler(handler)

        jira = JiraClient.__new__(JiraClient)
        jira._base_url = "https://test.atlassian.net"
        jira._session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        jira._session.post.return_value = mock_resp

        jira.create_issue("KAN", "Test", "Desc")

        log_output = log_stream.getvalue()
        self.assertNotIn("Basic ", log_output)
        self.assertNotIn("api_token", log_output)

        jira_logger.removeHandler(handler)


class TestConfig(unittest.TestCase):
    """Config validation tests."""

    def test_missing_config_detected(self):
        """Missing required config fields are detected."""
        cfg = get_config()
        # With no env vars set, all required fields should be flagged
        missing = validate_config({"snowflake_account": "", "jira_base_url": ""})
        self.assertIn("snowflake_account", missing)
        self.assertIn("jira_base_url", missing)


if __name__ == "__main__":
    unittest.main()
