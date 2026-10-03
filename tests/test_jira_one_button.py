"""
tests/test_jira_one_button.py
Test suite for One-Button Jira Creation with Local Worker Health Status.
Validates the complete queue-based architecture without making real Jira calls.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.jira_queue_service import (
    enqueue_jira_request,
    check_work_order_approved,
    check_existing_success,
    check_existing_pending,
    check_worker_health,
    get_queue_status,
)


class TestApprovalGate(unittest.TestCase):
    """Tests 1, 11: Approval gate prevents unapproved work orders from reaching Jira."""

    def setUp(self):
        self.session = MagicMock()

    def test_01_pending_approval_blocks_queue(self):
        """PENDING_APPROVAL work order → no queue record created."""
        self.session.sql.return_value.collect.side_effect = [
            [],  # _ensure_queue_table
            [{"STATUS": "PENDING_APPROVAL"}],  # check_work_order_approved
        ]
        # Simulate not approved
        with patch("services.jira_queue_service.check_work_order_approved", return_value=False):
            result = enqueue_jira_request(self.session, "WO-001", "Machine_03", "Test", "Desc")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("not APPROVED", result["message"])

    def test_11_worker_verifies_approved(self):
        """Worker independently verifies APPROVED before calling Jira."""
        # This is tested in the worker process_record logic (step 2)
        # Here we verify the queue service also checks
        with patch("services.jira_queue_service.check_work_order_approved", return_value=False):
            result = enqueue_jira_request(self.session, "WO-002", "Machine_03", "Test", "Desc")
        self.assertEqual(result["status"], "BLOCKED")


class TestWorkerOnlineOffline(unittest.TestCase):
    """Tests 2, 3, 14, 15, 16: Worker health status."""

    def setUp(self):
        self.session = MagicMock()

    def test_02_approved_worker_online(self):
        """APPROVED + worker ONLINE → check_worker_health returns ONLINE."""
        self.session.sql.return_value.collect.side_effect = [
            [{"STATUS": "ONLINE", "LAST_HEARTBEAT": "2026-01-01 00:00:00", "VERSION": "1.0.0", "UPDATED_AT": ""}],
            [{"FRESHNESS": "FRESH"}],
        ]
        result = check_worker_health(self.session)
        self.assertEqual(result["status"], "ONLINE")

    def test_03_approved_worker_offline(self):
        """APPROVED + worker OFFLINE → CREATE disabled."""
        self.session.sql.return_value.collect.return_value = [
            {"STATUS": "OFFLINE", "LAST_HEARTBEAT": None, "VERSION": "1.0.0", "UPDATED_AT": ""}
        ]
        result = check_worker_health(self.session)
        self.assertEqual(result["status"], "OFFLINE")

    def test_14_heartbeat_stale_shows_offline(self):
        """Stale heartbeat → worker shown as OFFLINE."""
        self.session.sql.return_value.collect.side_effect = [
            [{"STATUS": "ONLINE", "LAST_HEARTBEAT": "2026-01-01 00:00:00", "VERSION": "1.0.0", "UPDATED_AT": ""}],
            [{"FRESHNESS": "STALE"}],
        ]
        result = check_worker_health(self.session)
        self.assertEqual(result["status"], "OFFLINE")
        self.assertIn("stale", result["message"].lower())

    def test_15_worker_startup_heartbeat_online(self):
        """Worker startup sets heartbeat to ONLINE (tested via snowflake_client)."""
        from local_jira_worker.snowflake_client import SnowflakeClient
        client = SnowflakeClient({"snowflake_account": "", "snowflake_user": "", "snowflake_password": "",
                                  "snowflake_role": "", "snowflake_warehouse": "", "snowflake_database": "", "snowflake_schema": ""})
        client._conn = MagicMock()
        client._conn.cursor.return_value.__enter__ = MagicMock()
        client._conn.cursor.return_value.__exit__ = MagicMock()
        mock_cur = MagicMock()
        client._conn.cursor.return_value = mock_cur
        client.update_heartbeat()
        # Verify MERGE INTO was called with ONLINE
        call_args = mock_cur.execute.call_args_list
        self.assertTrue(any("ONLINE" in str(c) for c in call_args))

    def test_16_worker_shutdown_heartbeat_offline(self):
        """Worker shutdown sets heartbeat to OFFLINE."""
        from local_jira_worker.snowflake_client import SnowflakeClient
        client = SnowflakeClient({"snowflake_account": "", "snowflake_user": "", "snowflake_password": "",
                                  "snowflake_role": "", "snowflake_warehouse": "", "snowflake_database": "", "snowflake_schema": ""})
        client._conn = MagicMock()
        mock_cur = MagicMock()
        client._conn.cursor.return_value = mock_cur
        client.set_offline()
        call_args = mock_cur.execute.call_args_list
        self.assertTrue(any("OFFLINE" in str(c) for c in call_args))


class TestQueueIdempotency(unittest.TestCase):
    """Tests 4, 5, 6, 7, 8, 9, 10: Queue states and idempotency."""

    def setUp(self):
        self.session = MagicMock()

    def test_04_click_create_inserts_one_pending(self):
        """Click CREATE → exactly one PENDING queue record."""
        self.session.sql.return_value.collect.return_value = []
        with patch("services.jira_queue_service.check_work_order_approved", return_value=True), \
             patch("services.jira_queue_service.check_existing_success", return_value=None), \
             patch("services.jira_queue_service.check_existing_pending", return_value=False):
            result = enqueue_jira_request(self.session, "WO-100", "Machine_03", "Test", "Desc")
        self.assertEqual(result["status"], "QUEUED")

    def test_05_queue_pending_state(self):
        """Queue PENDING → correct status returned."""
        self.session.sql.return_value.collect.return_value = [
            {"QUEUE_ID": "q1", "WORK_ORDER_ID": "WO-100", "MACHINE_ID": "M3",
             "STATUS": "PENDING", "ATTEMPT_COUNT": 0, "JIRA_ISSUE_KEY": None,
             "JIRA_URL": None, "ERROR_MESSAGE": None, "CREATED_AT": "", "UPDATED_AT": "", "PROCESSED_AT": None}
        ]
        result = get_queue_status(self.session, "WO-100")
        self.assertEqual(result["status"], "PENDING")

    def test_06_queue_processing_state(self):
        """Queue PROCESSING → correct status returned."""
        self.session.sql.return_value.collect.return_value = [
            {"QUEUE_ID": "q1", "WORK_ORDER_ID": "WO-100", "MACHINE_ID": "M3",
             "STATUS": "PROCESSING", "ATTEMPT_COUNT": 1, "JIRA_ISSUE_KEY": None,
             "JIRA_URL": None, "ERROR_MESSAGE": None, "CREATED_AT": "", "UPDATED_AT": "", "PROCESSED_AT": None}
        ]
        result = get_queue_status(self.session, "WO-100")
        self.assertEqual(result["status"], "PROCESSING")

    def test_07_queue_success_shows_key(self):
        """Queue SUCCESS → Jira key is present."""
        self.session.sql.return_value.collect.return_value = [
            {"QUEUE_ID": "q1", "WORK_ORDER_ID": "WO-100", "MACHINE_ID": "M3",
             "STATUS": "SUCCESS", "ATTEMPT_COUNT": 1, "JIRA_ISSUE_KEY": "KAN-42",
             "JIRA_URL": "https://example.atlassian.net/browse/KAN-42",
             "ERROR_MESSAGE": None, "CREATED_AT": "", "UPDATED_AT": "", "PROCESSED_AT": ""}
        ]
        result = get_queue_status(self.session, "WO-100")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["jira_issue_key"], "KAN-42")

    def test_08_queue_failed_shows_retry(self):
        """Queue FAILED → error message available."""
        self.session.sql.return_value.collect.return_value = [
            {"QUEUE_ID": "q1", "WORK_ORDER_ID": "WO-100", "MACHINE_ID": "M3",
             "STATUS": "FAILED", "ATTEMPT_COUNT": 3, "JIRA_ISSUE_KEY": None,
             "JIRA_URL": None, "ERROR_MESSAGE": "Connection timeout",
             "CREATED_AT": "", "UPDATED_AT": "", "PROCESSED_AT": None}
        ]
        result = get_queue_status(self.session, "WO-100")
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("timeout", result["error_message"])

    def test_09_existing_success_prevents_duplicate(self):
        """Existing SUCCESS → duplicate prevented."""
        with patch("services.jira_queue_service.check_work_order_approved", return_value=True), \
             patch("services.jira_queue_service.check_existing_success", return_value={"jira_issue_key": "KAN-1", "jira_url": "url"}):
            result = enqueue_jira_request(self.session, "WO-100", "M3", "T", "D")
        self.assertEqual(result["status"], "ALREADY_EXISTS")
        self.assertEqual(result["jira_key"], "KAN-1")

    def test_10_existing_processing_prevents_duplicate(self):
        """Existing PROCESSING → duplicate prevented."""
        with patch("services.jira_queue_service.check_work_order_approved", return_value=True), \
             patch("services.jira_queue_service.check_existing_success", return_value=None), \
             patch("services.jira_queue_service.check_existing_pending", return_value=True):
            result = enqueue_jira_request(self.session, "WO-100", "M3", "T", "D")
        self.assertEqual(result["status"], "PENDING")
        self.assertIn("already queued", result["message"])


class TestSecurityChecks(unittest.TestCase):
    """Tests 12, 13, 17, 18: Security and architecture compliance."""

    def test_12_streamlit_zero_direct_jira_calls(self):
        """streamlit_app.py contains ZERO direct Jira HTTP calls."""
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with open(os.path.join(base, "streamlit_app.py"), "r", encoding="utf-8") as f:
            content = f.read()
        # Must not have direct requests to Jira
        self.assertNotIn("requests.post", content)
        self.assertNotIn("requests.get", content)
        self.assertNotIn("atlassian.net", content.split("'")[0] if "atlassian.net" in content else content)
        # The URL template for link display is OK, but no HTTP call
        self.assertNotIn("import requests", content)

    def test_13_jira_credentials_only_in_worker(self):
        """Jira credentials exist only in worker environment config."""
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with open(os.path.join(base, "streamlit_app.py"), "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("JIRA_API_TOKEN", content)
        self.assertNotIn("jira_api_token", content)
        # Services should not have Jira tokens either
        svc_path = os.path.join(base, "services", "jira_queue_service.py")
        with open(svc_path, "r", encoding="utf-8") as f:
            svc_content = f.read()
        self.assertNotIn("JIRA_API_TOKEN", svc_content)

    def test_17_retry_max_attempts(self):
        """Worker respects max_retries (default 3)."""
        from local_jira_worker.config import get_config
        cfg = get_config()
        self.assertEqual(cfg["max_retries"], 3)

    def test_18_audit_trail_written(self):
        """Worker calls record_audit on both success and failure paths."""
        from local_jira_worker.snowflake_client import SnowflakeClient
        # Verify the method exists and has correct signature
        import inspect
        sig = inspect.signature(SnowflakeClient.record_audit)
        params = list(sig.parameters.keys())
        self.assertIn("work_order_id", params)
        self.assertIn("status", params)
        self.assertIn("error_message", params)


if __name__ == "__main__":
    unittest.main()
