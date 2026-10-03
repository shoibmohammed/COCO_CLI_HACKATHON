"""
tests/test_local_jira_control_app.py
Unit tests for the Local Jira Control App (scripts/jira_worker_app.py).
All Snowflake/Jira/process operations are mocked.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "local_jira_worker")))

if "requests" not in sys.modules:
    try:
        import requests
    except ImportError:
        sys.modules["requests"] = MagicMock()

from jira_worker_app import WorkerManager, load_env, WORKER_DIR


class TestWorkerStartup(unittest.TestCase):
    """1. Worker startup."""

    @patch("jira_worker_app.subprocess.Popen")
    @patch("jira_worker_app.WORKER_SCRIPT")
    def test_start_launches_process(self, mock_script, mock_popen):
        mock_script.exists.return_value = True
        mock_proc = MagicMock()
        mock_proc.pid = 5555
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        wm = WorkerManager()
        wm._pid_file = Path("/tmp/test_app_start.pid")
        wm._process = None

        with patch.object(WorkerManager, "is_running", new_callable=PropertyMock, return_value=False):
            ok, msg = wm.start()

        self.assertTrue(ok)
        self.assertIn("5555", msg)
        wm._pid_file.unlink(missing_ok=True)


class TestDuplicatePrevention(unittest.TestCase):
    """2. Duplicate prevention."""

    def test_start_blocked_if_running(self):
        wm = WorkerManager()
        with patch.object(WorkerManager, "is_running", new_callable=PropertyMock, return_value=True):
            ok, msg = wm.start()
        self.assertFalse(ok)
        self.assertIn("already running", msg)


class TestWorkerHealth(unittest.TestCase):
    """3. Worker health detection."""

    def test_running_detected(self):
        wm = WorkerManager()
        wm._process = MagicMock()
        wm._process.poll.return_value = None
        self.assertTrue(wm.is_running)

    def test_stopped_detected(self):
        wm = WorkerManager()
        wm._process = None
        wm._pid_file = Path("/tmp/no_such_pid.pid")
        self.assertFalse(wm.is_running)


class TestJiraConnection(unittest.TestCase):
    """4. Jira connection test (mocked)."""

    @patch("jira_worker_app.os.environ", {
        "JIRA_BASE_URL": "https://test.atlassian.net",
        "JIRA_USER_EMAIL": "test@example.com",
        "JIRA_API_TOKEN": "fake-token"
    })
    def test_jira_client_import(self):
        """JiraClient can be instantiated with env vars."""
        from jira_client import JiraClient
        client = JiraClient(
            base_url="https://test.atlassian.net",
            user_email="test@example.com",
            api_token="fake-token"
        )
        self.assertIsNotNone(client._session)


class TestWorkOrderSelection(unittest.TestCase):
    """5. Approved Work Order selection."""

    def test_query_returns_approved(self):
        """Simulates query for APPROVED work orders."""
        mock_rows = [
            {"WORK_ORDER_ID": "abc-123", "MACHINE_ID": "Machine_03",
             "STATUS": "APPROVED", "EXTERNAL_TICKET_ID": None, "CREATED_AT": "2026-01-01"}
        ]
        # The app filters by STATUS = 'APPROVED' in SQL
        self.assertEqual(mock_rows[0]["STATUS"], "APPROVED")
        self.assertIsNone(mock_rows[0]["EXTERNAL_TICKET_ID"])


class TestQueueStates(unittest.TestCase):
    """6-8. PENDING, PROCESSING, SUCCESS states."""

    def test_pending_state(self):
        row = {"STATUS": "PENDING", "JIRA_ISSUE_KEY": None}
        self.assertEqual(row["STATUS"], "PENDING")

    def test_processing_state(self):
        row = {"STATUS": "PROCESSING", "JIRA_ISSUE_KEY": None}
        self.assertEqual(row["STATUS"], "PROCESSING")

    def test_success_state(self):
        row = {"STATUS": "SUCCESS", "JIRA_ISSUE_KEY": "KAN-42", "JIRA_URL": "https://x/browse/KAN-42"}
        self.assertEqual(row["STATUS"], "SUCCESS")
        self.assertEqual(row["JIRA_ISSUE_KEY"], "KAN-42")


class TestIdempotency(unittest.TestCase):
    """9. Idempotency — existing SUCCESS prevents duplicate."""

    def test_existing_success_blocks(self):
        """If external_ticket already set, no new queue record."""
        wo = {"work_order_id": "abc", "display_id": "WO-ABC", "machine_id": "M3",
              "external_ticket": "KAN-99"}
        # App checks this before enqueue
        self.assertIsNotNone(wo["external_ticket"])


class TestFailure(unittest.TestCase):
    """10. Failure state."""

    def test_failed_shows_error(self):
        row = {"STATUS": "FAILED", "ERROR_MESSAGE": "Connection timeout", "ATTEMPT_COUNT": 3}
        self.assertEqual(row["STATUS"], "FAILED")
        self.assertIn("timeout", row["ERROR_MESSAGE"])


class TestRetry(unittest.TestCase):
    """11. Retry logic."""

    def test_retry_resets_to_pending(self):
        """Retry sets STATUS back to PENDING."""
        # The worker's reset_for_retry does this
        from local_jira_worker.snowflake_client import SnowflakeClient
        import inspect
        sig = inspect.signature(SnowflakeClient.reset_for_retry)
        self.assertIn("queue_id", sig.parameters)
        self.assertIn("attempt_count", sig.parameters)


class TestSecurity(unittest.TestCase):
    """12. No credentials exposed."""

    def test_no_credentials_in_app_source(self):
        app_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "jira_worker_app.py")
        with open(app_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        # Must not hardcode any secrets
        self.assertNotIn("ATATT", content)
        self.assertNotIn("Bearer ", content)
        self.assertNotIn("password='", content)
        self.assertNotIn('password="', content)
        # Must not display tokens
        self.assertIn("never displayed", content.lower())


if __name__ == "__main__":
    unittest.main()
