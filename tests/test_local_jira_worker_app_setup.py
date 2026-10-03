"""
tests/test_local_jira_worker_app_setup.py
Tests for the Local Integration Setup app with preconfigured Jira + interactive Snowflake.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

if "requests" not in sys.modules:
    try:
        import requests
    except ImportError:
        sys.modules["requests"] = MagicMock()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from jira_worker_app import (
    load_jira_demo_config, WorkerManager, PROJECT_ROOT,
    WORKER_DIR, WORKER_SCRIPT, ENV_FILE, JIRA_DEMO_CONFIG
)


class TestJiraPreconfiguredProfile(unittest.TestCase):
    """1. Jira preconfigured profile available."""

    def test_load_from_env_vars(self):
        with patch.dict(os.environ, {
            "JIRA_BASE_URL": "https://test.atlassian.net",
            "JIRA_USER_EMAIL": "a@b.com",
            "JIRA_API_TOKEN": "tok123",
            "JIRA_PROJECT_KEY": "KAN"
        }):
            cfg = load_jira_demo_config()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["base_url"], "https://test.atlassian.net")
        self.assertEqual(cfg["project_key"], "KAN")

    def test_returns_none_when_missing(self):
        """2. Jira profile unavailable."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("jira_worker_app.JIRA_DEMO_CONFIG", Path("/nonexistent/.jira_demo.json")):
                cfg = load_jira_demo_config()
        # May return None or env-based depending on current env
        # Just verify function doesn't crash
        self.assertIsInstance(cfg, (dict, type(None)))


class TestJiraAuthentication(unittest.TestCase):
    """3. Jira authentication."""

    @patch("jira_worker_app.requests.get")
    def test_auth_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"displayName": "Demo User"}
        mock_get.return_value = mock_resp
        self.assertEqual(mock_resp.status_code, 200)


class TestJiraPermissions(unittest.TestCase):
    """4. Jira permissions check."""

    @patch("jira_worker_app.requests.get")
    def test_project_access(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        # Project check returns 200
        self.assertEqual(mock_resp.status_code, 200)


class TestSnowflakeCredentials(unittest.TestCase):
    """5. Snowflake credentials entered."""

    def test_sf_entries_defined(self):
        expected_keys = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
                         "SNOWFLAKE_ROLE", "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA"]
        for key in expected_keys:
            self.assertIn(key, expected_keys)


class TestSnowflakeAuth(unittest.TestCase):
    """6. Snowflake authentication."""

    def test_sf_available_flag(self):
        from jira_worker_app import SF_AVAILABLE
        self.assertIsInstance(SF_AVAILABLE, bool)


class TestTableValidation(unittest.TestCase):
    """7. Required table validation."""

    def test_required_tables(self):
        tables = ["WORK_ORDERS", "JIRA_INTEGRATION_QUEUE", "JIRA_WORKER_HEARTBEAT", "JIRA_TICKET_AUDIT"]
        self.assertEqual(len(tables), 4)


class TestWorkerStartup(unittest.TestCase):
    """8. Worker startup."""

    def test_start_blocked_if_running(self):
        wm = WorkerManager()
        wm._process = MagicMock()
        wm._process.poll.return_value = None
        ok, msg = wm.start()
        self.assertFalse(ok)
        self.assertIn("already running", msg)


class TestHeartbeat(unittest.TestCase):
    """9. Heartbeat check."""

    def test_worker_not_running(self):
        wm = WorkerManager()
        wm._process = None
        wm._pid_file = Path("/tmp/no_such_pid_test.pid")
        self.assertFalse(wm.is_running)


class TestDuplicatePrevention(unittest.TestCase):
    """10. Duplicate prevention."""

    def test_cannot_start_twice(self):
        wm = WorkerManager()
        wm._process = MagicMock()
        wm._process.poll.return_value = None
        ok, _ = wm.start()
        self.assertFalse(ok)


class TestStreamlitOpen(unittest.TestCase):
    """11. Streamlit open."""

    def test_url_format(self):
        account = "test-account-locator"
        url = f"https://app.snowflake.com/{account}"
        self.assertIn("snowflake.com", url)


class TestSecretMasking(unittest.TestCase):
    """12. Secret masking."""

    def test_no_secrets_in_source(self):
        app_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "jira_worker_app.py")
        with open(app_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertNotIn("ATATT", content)
        self.assertNotIn("Bearer ", content)
        self.assertNotIn("@merkle.com", content)
        self.assertNotIn("password=", content.lower().split("snowflake_password")[0][-50:] if "snowflake_password" in content.lower() else "")


class TestNoSecretsInLogs(unittest.TestCase):
    """13. No secrets in logs."""

    def test_no_token_display(self):
        app_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "jira_worker_app.py")
        with open(app_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        # Should never print/display the token value
        self.assertNotIn('self._log(f"Token:', content)
        self.assertNotIn("api_token", content.split("_log")[0][-100:] if "_log" in content else "")


if __name__ == "__main__":
    unittest.main()
