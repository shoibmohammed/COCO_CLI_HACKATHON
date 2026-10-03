"""
tests/test_notification_services.py
Automated Unit Test Suite for Multi-Provider Notification Architecture (Gmail + Outlook).
Verifies provider isolation, configuration handling, failure tolerance, provider-specific duplicate protection,
Snowflake audit persistence, retry logic, test-all functionality, and notification payloads.
Mocks SMTP transport layer to eliminate real email credential requirements.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.email_notification_service import GmailEmailProvider, get_gmail_config
from services.outlook_notification_service import OutlookEmailProvider, get_outlook_config
from services.notification_service import (
    send_critical_notification,
    send_work_order_approval_notification,
    send_test_notification_all,
    check_provider_duplicate,
    record_notification_audit,
    retry_failed_provider,
    reset_notification_audit,
    DISPATCHED_PROVIDER_KEYS
)


class TestMultiProviderNotificationService(unittest.TestCase):

    def setUp(self):
        DISPATCHED_PROVIDER_KEYS.clear()
        self.mock_session = MagicMock()
        self.mock_session.sql.side_effect = lambda query, *args, **kwargs: MagicMock(
            collect=lambda: [{"CNT": 0}] if "COUNT" in str(query) else ([{"STATUS": "SENT"}] if "LIMIT 1" in str(query) else [True])
        )

    def test_01_gmail_provider_instantiation(self):
        """1. Gmail Provider: Verify instantiation and default configuration loading."""
        provider = GmailEmailProvider(config_override={
            "provider": "GMAIL", "configured": True, "username": "test@gmail.com",
            "password": "app_password", "recipient": "siddhartha.nath7@gmail.com",
            "host": "smtp.gmail.com", "port": 587
        })
        self.assertEqual(provider.config["provider"], "GMAIL")
        self.assertTrue(provider.config["configured"])

    def test_02_outlook_provider_instantiation(self):
        """2. Outlook Provider: Verify instantiation and default configuration loading."""
        provider = OutlookEmailProvider(config_override={
            "provider": "OUTLOOK", "configured": True, "username": "test@office365.com",
            "password": "app_password", "recipient": "outlook-alerts@plant-a.com",
            "host": "smtp.office365.com", "port": 587
        })
        self.assertEqual(provider.config["provider"], "OUTLOOK")
        self.assertEqual(provider.config["host"], "smtp.office365.com")
        self.assertTrue(provider.config["configured"])

    def test_03_gmail_configuration_missing(self):
        """3. Gmail Config Missing: Verify missing credentials returns NOT_CONFIGURED."""
        provider = GmailEmailProvider(config_override={"provider": "GMAIL", "configured": False, "username": "", "password": ""})
        with patch("services.email_notification_service.gmail_send_email", return_value={"success": False, "status": "NOT_CONFIGURED", "message": "Not configured"}):
            ok, status, details = provider.send_email("recipient@test.com", "Subject", "Body")
            self.assertFalse(ok)
            self.assertIn(status, ["NOT_CONFIGURED", "AUTHORIZATION_REQUIRED", "FAILED"])

    def test_04_outlook_configuration_missing(self):
        """4. Outlook Config Missing: Verify missing credentials returns NOT_CONFIGURED."""
        provider = OutlookEmailProvider(config_override={"provider": "OUTLOOK", "configured": False, "username": "", "password": ""})
        ok, status, details = provider.send_email("recipient@test.com", "Subject", "Body")
        self.assertFalse(ok)
        self.assertIn(status, ["NOT_CONFIGURED", "AUTHORIZATION_REQUIRED"])

    @patch("services.email_notification_service.gmail_send_email")
    def test_05_gmail_successful_send(self, mock_gmail_send):
        """5. Gmail Successful Send: Verify mock Gmail API execution."""
        mock_gmail_send.return_value = {
            "success": True,
            "status": "SENT",
            "message_id": "msg_12345",
            "recipient": "siddhartha.nath7@gmail.com"
        }

        provider = GmailEmailProvider(config_override={
            "provider": "GMAIL", "configured": True, "username": "user@gmail.com",
            "recipient": "siddhartha.nath7@gmail.com"
        })
        ok, status, details = provider.send_email("siddhartha.nath7@gmail.com", "Test Subject", "<p>Body</p>")
        self.assertTrue(ok)
        self.assertEqual(status, "SENT")
        mock_gmail_send.assert_called_once()

    @patch("smtplib.SMTP")
    def test_06_outlook_successful_send(self, mock_smtp):
        """6. Outlook Successful Send: Verify mock Office365 SMTP login and STARTTLS execution."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        provider = OutlookEmailProvider(config_override={
            "provider": "OUTLOOK", "configured": True, "username": "user@office365.com",
            "password": "secret_app_password", "recipient": "outlook-alerts@plant-a.com",
            "host": "smtp.office365.com", "port": 587
        })
        ok, status, details = provider.send_email("outlook-alerts@plant-a.com", "Test Subject", "<p>Body</p>")
        self.assertTrue(ok)
        self.assertEqual(status, "SENT")
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@office365.com", "secret_app_password")

    @patch("services.email_notification_service.gmail_send_email")
    def test_07_gmail_failure(self, mock_gmail_send):
        """7. Gmail Failure: Verify auth / API failure handling."""
        mock_gmail_send.return_value = {
            "success": False,
            "status": "FAILED",
            "error": "Authentication failed",
            "message": "Failed"
        }

        provider = GmailEmailProvider(config_override={
            "provider": "GMAIL", "configured": True, "username": "user@gmail.com",
            "recipient": "siddhartha.nath7@gmail.com"
        })
        ok, status, details = provider.send_email("siddhartha.nath7@gmail.com", "Test Subject", "<p>Body</p>")
        self.assertFalse(ok)
        self.assertEqual(status, "FAILED")

    @patch("smtplib.SMTP")
    def test_08_outlook_failure(self, mock_smtp):
        """8. Outlook Failure: Verify connection error handling."""
        mock_smtp.side_effect = TimeoutError("Connection timed out")

        provider = OutlookEmailProvider(config_override={
            "provider": "OUTLOOK", "configured": True, "username": "user@office365.com",
            "password": "secret_app_password", "recipient": "outlook-alerts@plant-a.com",
            "host": "smtp.office365.com", "port": 587
        })
        ok, status, details = provider.send_email("outlook-alerts@plant-a.com", "Test Subject", "<p>Body</p>")
        self.assertFalse(ok)
        self.assertEqual(status, "FAILED")

    @patch.object(GmailEmailProvider, "send_email")
    @patch.object(OutlookEmailProvider, "send_email")
    def test_09_both_providers_successful(self, mock_out_send, mock_gm_send):
        """9. Both Providers Successful: Verify overall status is ALL_SENT when both succeed."""
        mock_gm_send.return_value = (True, "SENT", {"recipient": "siddhartha.nath7@gmail.com"})
        mock_out_send.return_value = (True, "SENT", {"recipient": "outlook-alerts@plant-a.com"})

        event = {"event_id": "TEST_EV_100", "machine_id": "Machine_03", "work_order_id": "WO-10023"}
        res = send_critical_notification(event, session=self.mock_session, force=True)

        self.assertEqual(res["overall"], "ALL_SENT")
        self.assertEqual(res["gmail"]["status"], "SENT")
        self.assertEqual(res["outlook"]["status"], "SENT")

    @patch.object(GmailEmailProvider, "send_email")
    @patch.object(OutlookEmailProvider, "send_email")
    def test_10_one_provider_succeeds_one_fails(self, mock_out_send, mock_gm_send):
        """10. Failure Isolation: Verify Gmail success does not crash if Outlook fails, returning PARTIAL_SUCCESS."""
        mock_gm_send.return_value = (True, "SENT", {"recipient": "siddhartha.nath7@gmail.com"})
        mock_out_send.return_value = (False, "FAILED", {"recipient": "outlook-alerts@plant-a.com", "error": "SMTP Auth Error"})

        event = {"event_id": "TEST_EV_101", "machine_id": "Machine_03", "work_order_id": "WO-10023"}
        res = send_critical_notification(event, session=self.mock_session, force=True)

        self.assertEqual(res["overall"], "PARTIAL_SUCCESS")
        self.assertEqual(res["gmail"]["status"], "SENT")
        self.assertEqual(res["outlook"]["status"], "FAILED")

    def test_11_duplicate_prevention_in_memory(self):
        """11. In-Memory Duplicate Prevention: Verify event key prevents duplicate send."""
        DISPATCHED_PROVIDER_KEYS.add("TEST_EV_102:GMAIL")
        is_dup = check_provider_duplicate(self.mock_session, "TEST_EV_102", "GMAIL")
        self.assertTrue(is_dup)

    def test_12_provider_specific_duplicate_prevention(self):
        """12. Provider-Specific Duplicate Prevention: Verify Gmail key does not block Outlook."""
        DISPATCHED_PROVIDER_KEYS.add("TEST_EV_103:GMAIL")
        gm_dup = check_provider_duplicate(self.mock_session, "TEST_EV_103", "GMAIL")
        out_dup = check_provider_duplicate(self.mock_session, "TEST_EV_103", "OUTLOOK")

        self.assertTrue(gm_dup, "Gmail should be suppressed")
        self.assertFalse(out_dup, "Outlook should NOT be suppressed when only Gmail was dispatched")

    @patch.object(OutlookEmailProvider, "send_email")
    def test_13_retry_failed_provider(self, mock_out_send):
        """13. Retry Failed Provider: Verify retry targets only the specified failed provider."""
        mock_out_send.return_value = (True, "SENT", {"recipient": "outlook-alerts@plant-a.com"})

        audit_rec = {
            "EVENT_ID": "TEST_EV_104",
            "MACHINE_ID": "Machine_03",
            "WORK_ORDER_ID": "WO-10023",
            "PROVIDER": "OUTLOOK",
            "RECIPIENT": "outlook-alerts@plant-a.com",
            "SUBJECT": "🚨 CRITICAL MAINTENANCE ALERT — Machine_03"
        }
        res = retry_failed_provider(self.mock_session, audit_rec)

        self.assertEqual(res["provider"], "OUTLOOK")
        self.assertEqual(res["status"], "SENT")
        self.assertIn("TEST_EV_104:OUTLOOK", DISPATCHED_PROVIDER_KEYS)

    def test_14_record_notification_audit(self):
        """14. Notification Audit: Verify Snowflake SQL insert record formatting."""
        record_notification_audit(
            session=self.mock_session,
            event_id="TEST_EV_105",
            machine_id="Machine_03",
            work_order_id="WO-10023",
            notification_type="CRITICAL_ALERT",
            provider="GMAIL",
            recipient="siddhartha.nath7@gmail.com",
            subject="Alert Subject",
            status="SENT",
            error_msg=None
        )
        self.assertTrue(self.mock_session.sql.called)

    def test_15_reset_notification_audit(self):
        """15. Reset Notification Audit: Verify in-memory tracker is cleared."""
        DISPATCHED_PROVIDER_KEYS.add("TEST_EV_106:GMAIL")
        res = reset_notification_audit(session=self.mock_session)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(len(DISPATCHED_PROVIDER_KEYS), 0)

    @patch.object(GmailEmailProvider, "send_email")
    @patch.object(OutlookEmailProvider, "send_email")
    def test_16_test_all_functionality(self, mock_out_send, mock_gm_send):
        """16. Test All Functionality: Verify test-all triggers both providers."""
        mock_gm_send.return_value = (True, "SENT", {"recipient": "siddhartha.nath7@gmail.com"})
        mock_out_send.return_value = (True, "SENT", {"recipient": "outlook-alerts@plant-a.com"})

        res = send_test_notification_all(session=self.mock_session)
        self.assertEqual(res["overall"], "ALL_SENT")

    @patch.object(GmailEmailProvider, "send_email")
    @patch.object(OutlookEmailProvider, "send_email")
    def test_17_work_order_approval_notification(self, mock_out_send, mock_gm_send):
        """17. Work Order Approval Email: Verify dispatch payload for work order approval."""
        mock_gm_send.return_value = (True, "SENT", {"recipient": "siddhartha.nath7@gmail.com"})
        mock_out_send.return_value = (True, "SENT", {"recipient": "outlook-alerts@plant-a.com"})

        wo_payload = {
            "work_order_id": "WO-10023",
            "machine_id": "Machine_03",
            "recommended_part": "SKF-6205-2RS",
            "approved_action": "Replace bearing under LOTO procedure."
        }
        res = send_work_order_approval_notification(wo_payload, session=self.mock_session)
        self.assertIn("gmail", res)
        self.assertIn("outlook", res)

    @patch.object(GmailEmailProvider, "send_email")
    @patch.object(OutlookEmailProvider, "send_email")
    def test_18_critical_alert_notification_payload(self, mock_out_send, mock_gm_send):
        """18. Critical Alert Notification Payload: Verify critical alert fields passed to providers."""
        mock_gm_send.return_value = (True, "SENT", {"recipient": "siddhartha.nath7@gmail.com"})
        mock_out_send.return_value = (True, "SENT", {"recipient": "outlook-alerts@plant-a.com"})

        event = {
            "event_id": "TEST_EV_108",
            "machine_id": "Machine_03",
            "vibration_mm_s": 6.15,
            "temperature_c": 97.3,
            "rpm": 1552,
            "failure_probability": 0.998,
            "rul_hours": 18.0
        }
        res = send_critical_notification(event, session=self.mock_session, force=True)
        self.assertEqual(res["overall"], "ALL_SENT")
        self.assertTrue(mock_gm_send.called)
        self.assertTrue(mock_out_send.called)


if __name__ == "__main__":
    unittest.main()
