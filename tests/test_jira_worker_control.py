"""
tests/test_jira_worker_control.py
Unit tests for the Local Jira Worker Control Center.
All OS process operations are mocked — no real processes started.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))

from jira_worker_control import WorkerProcess, WORKER_DIR, WORKER_SCRIPT


class TestWorkerStart(unittest.TestCase):
    """Tests for START behavior."""

    def setUp(self):
        self.wp = WorkerProcess()
        self.wp._pid_file = Path("/tmp/test_worker.pid")

    def tearDown(self):
        if self.wp._pid_file.exists():
            self.wp._pid_file.unlink()

    @patch("jira_worker_control.subprocess.Popen")
    @patch("jira_worker_control.WORKER_SCRIPT")
    def test_start_success(self, mock_script, mock_popen):
        """START launches the worker subprocess."""
        mock_script.exists.return_value = True
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc
        self.wp._process = None

        with patch.object(WorkerProcess, "is_running", new_callable=PropertyMock, return_value=False):
            ok, msg = self.wp.start()

        self.assertTrue(ok)
        self.assertIn("12345", msg)

    def test_start_duplicate_prevention(self):
        """START does not launch a second worker if already running."""
        with patch.object(WorkerProcess, "is_running", new_callable=PropertyMock, return_value=True):
            wp = WorkerProcess()
            ok, msg = wp.start()
        self.assertFalse(ok)
        self.assertIn("already running", msg)

    @patch("jira_worker_control.WORKER_SCRIPT")
    def test_start_missing_script(self, mock_script):
        """START fails gracefully if worker.py doesn't exist."""
        mock_script.exists.return_value = False
        with patch.object(WorkerProcess, "is_running", new_callable=PropertyMock, return_value=False):
            wp = WorkerProcess()
            ok, msg = wp.start()
        self.assertFalse(ok)
        self.assertIn("not found", msg)


class TestWorkerStop(unittest.TestCase):
    """Tests for STOP behavior."""

    def test_stop_running_process(self):
        """STOP terminates the running worker."""
        wp = WorkerProcess()
        wp._process = MagicMock()
        wp._process.poll.return_value = None
        wp._process.wait.return_value = None
        wp._pid_file = Path("/tmp/test_stop.pid")

        ok, msg = wp.stop()
        self.assertTrue(ok)
        self.assertIn("stopped", msg.lower())

    def test_stop_not_running(self):
        """STOP when worker not running returns appropriate message."""
        wp = WorkerProcess()
        wp._process = None
        wp._pid_file = Path("/tmp/nonexistent_pid.pid")

        ok, msg = wp.stop()
        self.assertFalse(ok)
        self.assertIn("not running", msg)


class TestWorkerRestart(unittest.TestCase):
    """Tests for RESTART behavior."""

    @patch("jira_worker_control.subprocess.Popen")
    @patch("jira_worker_control.WORKER_SCRIPT")
    def test_restart_stops_then_starts(self, mock_script, mock_popen):
        """RESTART = STOP + START."""
        mock_script.exists.return_value = True
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        wp = WorkerProcess()
        wp._process = MagicMock()
        wp._process.poll.return_value = None
        wp._process.wait.return_value = None
        wp._pid_file = Path("/tmp/test_restart.pid")

        # Stop
        ok_stop, _ = wp.stop()
        self.assertTrue(ok_stop)

        # Start
        with patch.object(WorkerProcess, "is_running", new_callable=PropertyMock, return_value=False):
            ok_start, msg = wp.start()
        self.assertTrue(ok_start)


class TestHealthCheck(unittest.TestCase):
    """Tests for HEALTH CHECK."""

    def test_health_running(self):
        """Health check reports RUNNING when process exists."""
        wp = WorkerProcess()
        wp._process = MagicMock()
        wp._process.poll.return_value = None
        self.assertTrue(wp.is_running)

    def test_health_stopped(self):
        """Health check reports STOPPED when no process."""
        wp = WorkerProcess()
        wp._process = None
        wp._pid_file = Path("/tmp/nonexistent.pid")
        self.assertFalse(wp.is_running)


class TestMissingEnvironment(unittest.TestCase):
    """Tests for missing venv/environment."""

    @patch("jira_worker_control.VENV_PYTHON")
    @patch("jira_worker_control.WORKER_SCRIPT")
    @patch("jira_worker_control.subprocess.Popen")
    def test_missing_venv_uses_system_python(self, mock_popen, mock_script, mock_venv):
        """If venv doesn't exist, falls back to sys.executable."""
        mock_script.exists.return_value = True
        mock_venv.exists.return_value = False
        mock_proc = MagicMock()
        mock_proc.pid = 111
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        wp = WorkerProcess()
        wp._process = None
        wp._pid_file = Path("/tmp/test_novenv.pid")

        with patch.object(WorkerProcess, "is_running", new_callable=PropertyMock, return_value=False):
            ok, msg = wp.start()
        self.assertTrue(ok)


class TestWorkerCrash(unittest.TestCase):
    """Tests for worker crash detection."""

    def test_process_exited_shows_stopped(self):
        """If subprocess exited, is_running returns False."""
        wp = WorkerProcess()
        wp._process = MagicMock()
        wp._process.poll.return_value = 1  # exited with code 1
        wp._pid_file = Path("/tmp/crashed.pid")
        self.assertFalse(wp.is_running)


class TestSecurity(unittest.TestCase):
    """Tests: no credentials exposed."""

    def test_no_credentials_in_source(self):
        """Control center source has no hardcoded credentials."""
        script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "jira_worker_control.py")
        with open(script_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertNotIn("JIRA_API_TOKEN", content)
        self.assertNotIn("SNOWFLAKE_PASSWORD", content)
        self.assertNotIn("client_secret", content)
        self.assertNotIn("Bearer", content)


if __name__ == "__main__":
    unittest.main()
