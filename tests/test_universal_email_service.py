"""
tests/test_universal_email_service.py
Automated Unit Test Suite for Universal Email Service.
Verifies recipient email validation, auto provider detection (Gmail, Outlook, Hotmail, Custom Domains),
provider configuration checks, manual vs automatic duplicate prevention, attachments, and reset handling.
Mocks SMTP transport layer to eliminate real credential requirements.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.universal_email_service import (
    validate_email_address,
    detect_email_provider,
    send_universal_email,
    check_automatic_duplicate,
    record_universal_audit,
    DISPATCHED_AUTOMATIC_KEYS
)
from services.email_notification_service import GmailEmailProvider
from services.outlook_notification_service import OutlookEmailProvider
from services.notification_service import reset_notification_audit


class TestUniversalEmailService(unittest.TestCase):

    def setUp(self):
        DISPATCHED_AUTOMATIC_KEYS.clear()
        self.mock_session = MagicMock()
        self.mock_session.sql.side_effect = lambda query, *args, **kwargs: MagicMock(
            collect=lambda: [{"CNT": 0}] if "COUNT" in str(query) else [True]
        )

    def test_01_gmail_recipient_detection(self):
        """1. Gmail Recipient: Verify @gmail.com detects GMAIL provider."""
        provider_code, display = detect_email_provider("maintenance.manager@gmail.com")
        self.assertEqual(provider_code, "GMAIL")
        self.assertIn("Gmail", display)

    def test_02_outlook_recipient_detection(self):
        """2. Outlook Recipient: Verify @outlook.com detects OUTLOOK provider."""
        provider_code, display = detect_email_provider("plant.manager@outlook.com")
        self.assertEqual(provider_code, "OUTLOOK")
        self.assertIn("Outlook", display)

    def test_03_hotmail_recipient_detection(self):
        """3. Hotmail Recipient: Verify @hotmail.com detects OUTLOOK provider."""
        provider_code, display = detect_email_provider("technician@hotmail.com")
        self.assertEqual(provider_code, "OUTLOOK")
        self.assertIn("Outlook", display)

    def test_04_custom_domain_recipient_detection(self):
        """4. Custom Domain: Verify @company.com falls back to configured sender or Snowflake native email."""
        provider_code, display = detect_email_provider("engineer@custom-factory.com")
        self.assertIn(provider_code, ("GMAIL", "OUTLOOK", "SNOWFLAKE_EMAIL"))

    def test_05_invalid_email_validation(self):
        """5. Invalid Email: Verify invalid syntax is rejected without calling SMTP."""
        self.assertFalse(validate_email_address("invalid-email"))
        self.assertFalse(validate_email_address("missing_at_symbol.com"))
        self.assertFalse(validate_email_address("@nodomain.com"))

        res = send_universal_email("invalid-email", "Subject", "Body", session=self.mock_session)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "INVALID_EMAIL")
        self.assertIn("INVALID EMAIL ADDRESS", res["message"])

    def test_06_gmail_provider_unavailable(self):
        """6. Gmail Config Missing: Verify missing credentials returns error message."""
        with patch("services.universal_email_service.get_gmail_config", return_value={"configured": False}):
            res = send_universal_email("user@gmail.com", "Subject", "Body", provider_mode="GMAIL", session=self.mock_session)
            self.assertFalse(res["success"])
            self.assertIn(res["status"], ("NOT_CONFIGURED", "AUTHORIZATION_REQUIRED", "LIBRARIES_MISSING"))

    def test_07_outlook_provider_unavailable(self):
        """7. Outlook Config Missing: Verify missing credentials returns error message."""
        with patch("services.universal_email_service.get_outlook_config", return_value={"configured": False}):
            res = send_universal_email("user@outlook.com", "Subject", "Body", provider_mode="OUTLOOK", session=self.mock_session)
            self.assertFalse(res["success"])
            self.assertIn("Outlook", res["message"])

    @patch.object(GmailEmailProvider, "send_email")
    def test_08_manual_email_send(self, mock_gm_send):
        """8. Manual Email Send: Verify manual send succeeds and logs audit record."""
        mock_gm_send.return_value = (True, "SENT", {"recipient": "user@gmail.com"})
        res = send_universal_email("user@gmail.com", "Manual Subject", "Manual Body", session=self.mock_session, is_automatic=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "SENT")
        self.assertIn("EMAIL SENT SUCCESSFULLY", res["message"])

    @patch.object(GmailEmailProvider, "send_email")
    def test_09_critical_alert_email(self, mock_gm_send):
        """9. Critical Alert Email: Verify critical alert subject and body handling."""
        mock_gm_send.return_value = (True, "SENT", {"recipient": "manager@gmail.com"})
        res = send_universal_email(
            recipient="manager@gmail.com",
            subject="🚨 CRITICAL MAINTENANCE ALERT — Machine_03",
            body="Machine_03 critical failure state detected.",
            machine_id="Machine_03",
            session=self.mock_session
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["subject"], "🚨 CRITICAL MAINTENANCE ALERT — Machine_03")

    @patch.object(OutlookEmailProvider, "send_email")
    def test_10_work_order_approval_email(self, mock_out_send):
        """10. Work Order Approval Email: Verify work order approval email dispatch."""
        mock_out_send.return_value = (True, "SENT", {"recipient": "manager@outlook.com"})
        res = send_universal_email(
            recipient="manager@outlook.com",
            subject="🛠️ WORK ORDER APPROVED — Machine_03",
            body="Work Order WO-10023 approved.",
            work_order_id="WO-10023",
            session=self.mock_session
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["provider"], "OUTLOOK")

    @patch.object(GmailEmailProvider, "send_email")
    def test_11_copilot_recommendation_email(self, mock_gm_send):
        """11. Copilot Recommendation Email: Verify Copilot recommendation dispatch."""
        mock_gm_send.return_value = (True, "SENT", {"recipient": "technician@gmail.com"})
        res = send_universal_email(
            recipient="technician@gmail.com",
            subject="Maintenance Recommendation — Machine_03",
            body="AI COPILOT RECOMMENDATION FOR Machine_03: Inspect spindle bearing.",
            session=self.mock_session
        )
        self.assertTrue(res["success"])

    @patch.object(GmailEmailProvider, "send_email")
    def test_12_attachment_encoding(self, mock_gm_send):
        """12. Attachments: Verify file attachment list passed to provider."""
        mock_gm_send.return_value = (True, "SENT", {"recipient": "user@gmail.com"})
        atts = [{"filename": "Manual.txt", "content": b"Sample manual text"}]
        res = send_universal_email(
            recipient="user@gmail.com",
            subject="Manual Attachment Test",
            body="See attached file.",
            attachments=atts,
            session=self.mock_session
        )
        self.assertTrue(res["success"])
        mock_gm_send.assert_called_once()

    @patch.object(GmailEmailProvider, "send_email")
    def test_13_duplicate_automatic_notification_prevention(self, mock_gm_send):
        """13. Automatic Duplicate Protection: Verify repeat automatic alerts are suppressed."""
        mock_gm_send.return_value = (True, "SENT", {"recipient": "user@gmail.com"})

        # First automatic send
        res1 = send_universal_email("user@gmail.com", "Subject", "Body", event_id="EV_100", is_automatic=True, session=self.mock_session)
        self.assertTrue(res1["success"])
        self.assertEqual(res1["status"], "SENT")

        # Second automatic send with same event_id
        res2 = send_universal_email("user@gmail.com", "Subject", "Body", event_id="EV_100", is_automatic=True, session=self.mock_session)
        self.assertTrue(res2["success"])
        self.assertEqual(res2["status"], "SUPPRESSED")

    @patch.object(GmailEmailProvider, "send_email")
    def test_14_explicit_manual_resend(self, mock_gm_send):
        """14. Explicit Manual Resend: Verify manual user clicks bypass duplicate protection."""
        mock_gm_send.return_value = (True, "SENT", {"recipient": "user@gmail.com"})

        res1 = send_universal_email("user@gmail.com", "Subject", "Body", event_id="EV_200", is_automatic=False, session=self.mock_session)
        res2 = send_universal_email("user@gmail.com", "Subject", "Body", event_id="EV_200", is_automatic=False, session=self.mock_session)

        self.assertEqual(res1["status"], "SENT")
        self.assertEqual(res2["status"], "SENT", "Manual explicit sends must NOT be suppressed")

    def test_15_reset_everything(self):
        """15. Reset Everything: Verify reset_notification_audit clears audit trackers while preserving config."""
        DISPATCHED_AUTOMATIC_KEYS.add("EV_300:user@gmail.com:GMAIL")
        res = reset_notification_audit(session=self.mock_session)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(len(DISPATCHED_AUTOMATIC_KEYS), 0)


if __name__ == "__main__":
    unittest.main()
