"""
tests/test_dual_channel_notifications.py
Tests for Dual-Channel Notification Architecture (Snowflake Email + Slack).
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.notification_service import dispatch_dual_channel_notification, record_notification_audit


class TestAutomaticEmail(unittest.TestCase):
    """1. Automatic critical alert → email."""

    @patch("services.notification_service.send_snowflake_email")
    @patch("services.slack_service.check_slack_configuration", return_value={"status": "NOT_CONFIGURED"})
    def test_auto_email_dispatched(self, mock_slack, mock_send):
        mock_send.return_value = {"status": "SENT", "message": "Delivered"}
        session = MagicMock()
        session.sql.return_value.collect.return_value = []

        res = dispatch_dual_channel_notification(
            session=session, event_id="AUTO-001", machine_id="Machine_03",
            notification_type="CRITICAL_ALERT", trigger_type="AUTOMATIC",
            alert_payload={"machine_id": "Machine_03"}, recipient="admin@co.com", mode="LIVE"
        )
        self.assertEqual(res["email"]["status"], "SENT")


class TestAutomaticSlack(unittest.TestCase):
    """2. Automatic critical alert → Slack."""

    @patch("services.slack_service.send_slack_notification", return_value=(True, "SENT", {"message": "OK"}))
    @patch("services.slack_service.format_critical_alert", return_value="msg")
    @patch("services.slack_service.check_slack_configuration", return_value={"status": "READY"})
    def test_auto_slack_dispatched(self, mock_cfg, mock_fmt, mock_send):
        session = MagicMock()
        session.sql.return_value.collect.return_value = []

        res = dispatch_dual_channel_notification(
            session=session, event_id="AUTO-002", machine_id="Machine_03",
            notification_type="CRITICAL_ALERT", trigger_type="AUTOMATIC",
            alert_payload={"machine_id": "Machine_03"}, recipient="", mode="LIVE"
        )
        self.assertEqual(res["slack"]["status"], "SENT")


class TestManualEmail(unittest.TestCase):
    """3. Manual critical alert → email."""

    @patch("services.notification_service.send_snowflake_email")
    @patch("services.slack_service.check_slack_configuration", return_value={"status": "NOT_CONFIGURED"})
    def test_manual_email(self, mock_slack, mock_send):
        mock_send.return_value = {"status": "SENT", "message": "Delivered"}
        session = MagicMock()
        session.sql.return_value.collect.return_value = []

        res = dispatch_dual_channel_notification(
            session=session, event_id="MANUAL-003", machine_id="Machine_03",
            notification_type="CRITICAL_ALERT", trigger_type="MANUAL",
            alert_payload={"machine_id": "Machine_03"}, recipient="test@co.com", mode="LIVE"
        )
        self.assertEqual(res["email"]["status"], "SENT")


class TestManualSlack(unittest.TestCase):
    """4. Manual critical alert → Slack."""

    @patch("services.slack_service.send_slack_notification", return_value=(True, "SENT", {"message": "OK"}))
    @patch("services.slack_service.format_critical_alert", return_value="msg")
    @patch("services.slack_service.check_slack_configuration", return_value={"status": "READY"})
    def test_manual_slack(self, mock_cfg, mock_fmt, mock_send):
        session = MagicMock()
        session.sql.return_value.collect.return_value = []

        res = dispatch_dual_channel_notification(
            session=session, event_id="MANUAL-004", machine_id="Machine_03",
            notification_type="CRITICAL_ALERT", trigger_type="MANUAL",
            alert_payload={"machine_id": "Machine_03"}, recipient="", mode="LIVE"
        )
        self.assertEqual(res["slack"]["status"], "SENT")


class TestChannelIndependence(unittest.TestCase):
    """7-8. One channel fails, other still works."""

    @patch("services.notification_service.send_snowflake_email")
    @patch("services.slack_service.send_slack_notification", return_value=(True, "SENT", {"message": "OK"}))
    @patch("services.slack_service.format_critical_alert", return_value="msg")
    @patch("services.slack_service.check_slack_configuration", return_value={"status": "READY"})
    def test_email_fails_slack_succeeds(self, mock_cfg, mock_fmt, mock_slack, mock_email):
        mock_email.return_value = {"status": "ERROR", "message": "Failed"}
        session = MagicMock()
        session.sql.return_value.collect.return_value = []

        res = dispatch_dual_channel_notification(
            session=session, event_id="IND-005", machine_id="Machine_03",
            notification_type="CRITICAL_ALERT", trigger_type="MANUAL",
            alert_payload={"machine_id": "Machine_03"}, recipient="x@co.com", mode="LIVE"
        )
        self.assertEqual(res["slack"]["status"], "SENT")
        self.assertEqual(res["overall"], "PARTIAL_SUCCESS")


class TestBothUnavailable(unittest.TestCase):
    """9. Both unavailable → audit records NOT_CONFIGURED."""

    @patch("services.slack_service.check_slack_configuration", return_value={"status": "NOT_CONFIGURED"})
    def test_both_not_configured(self, mock_slack):
        session = MagicMock()
        session.sql.return_value.collect.return_value = []

        res = dispatch_dual_channel_notification(
            session=session, event_id="NONE-006", machine_id="Machine_03",
            notification_type="CRITICAL_ALERT", trigger_type="AUTOMATIC",
            alert_payload={"machine_id": "Machine_03"}, recipient="", mode="LIVE"
        )
        self.assertEqual(res["email"]["status"], "NOT_CONFIGURED")
        self.assertEqual(res["slack"]["status"], "NOT_CONFIGURED")
        self.assertEqual(res["overall"], "ALL_FAILED")


class TestDemoMode(unittest.TestCase):
    """10. Demo mode records audit without real send."""

    @patch("services.slack_service.check_slack_configuration", return_value={"status": "READY"})
    def test_demo_no_real_send(self, mock_slack):
        session = MagicMock()
        session.sql.return_value.collect.return_value = []

        res = dispatch_dual_channel_notification(
            session=session, event_id="DEMO-007", machine_id="Machine_03",
            notification_type="CRITICAL_ALERT", trigger_type="MANUAL",
            alert_payload={"machine_id": "Machine_03"}, recipient="", mode="DEMO"
        )
        self.assertEqual(res["email"]["status"], "DEMO_SUCCESS")
        self.assertEqual(res["slack"]["status"], "DEMO_SUCCESS")
        self.assertEqual(res["overall"], "ALL_SUCCESS")


class TestNoSecrets(unittest.TestCase):
    """13. No secrets in audit/logs."""

    def test_no_secrets_in_dispatch(self):
        src_path = os.path.join(os.path.dirname(__file__), "..", "services", "notification_service.py")
        with open(src_path, encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("ATATT", content)
        self.assertNotIn("@merkle.com", content)


class TestSameService(unittest.TestCase):
    """14. Same Notification Service used by both paths."""

    def test_dispatch_function_exists(self):
        from services.notification_service import dispatch_dual_channel_notification
        import inspect
        sig = inspect.signature(dispatch_dual_channel_notification)
        self.assertIn("trigger_type", sig.parameters)
        self.assertIn("mode", sig.parameters)


if __name__ == "__main__":
    unittest.main()
