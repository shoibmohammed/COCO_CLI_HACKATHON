"""
tests/test_email_notification.py
Comprehensive test suite for Email Notification UX in MFG Predictive Maintenance.
Validates:
 1. Integration exists + recipient valid → send allowed
 2. Integration missing → send blocked gracefully → no email call
 3. Recipient unverified/empty → send blocked gracefully → no email call
 4. Trial limitation → graceful unavailable state
 5. Page load → ZERO email calls
 6. User clicks SEND → send attempted exactly once
 7. Send failure → sanitized error
 8. No personal hardcoded recipient
 9. Provider label = Snowflake Email
10. Core application continues if email unavailable
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.snowflake_email_provider import SnowflakeEmailProvider, DEFAULT_RECIPIENT, INTEGRATION_NAME
from services.notification_service import check_email_readiness, send_snowflake_email


class TestEmailNotificationUX(unittest.TestCase):

    def setUp(self):
        self.mock_session = MagicMock()
        self.provider = SnowflakeEmailProvider()

    # ---------------------------------------------------------------
    # 1. Integration exists + recipient valid → send allowed
    # ---------------------------------------------------------------
    def test_01_send_allowed_with_valid_integration_and_recipient(self):
        """Integration exists and recipient provided → email send is attempted."""
        self.mock_session.sql.return_value.collect.return_value = [MagicMock(**{"__getitem__": lambda s, i: "Email sent"})]
        ok, status, details = self.provider.send_email(
            session=self.mock_session,
            recipient="verified@company.com",
            subject="Test Alert",
            body="Test body"
        )
        self.assertTrue(ok)
        self.assertEqual(status, "SENT")
        self.assertEqual(details["provider"], "SNOWFLAKE_EMAIL")
        self.mock_session.sql.assert_called_once()

    # ---------------------------------------------------------------
    # 2. Integration missing → send blocked gracefully
    # ---------------------------------------------------------------
    def test_02_integration_missing_readiness_check(self):
        """check_email_readiness returns NOT_CONFIGURED when integration doesn't exist."""
        self.mock_session.sql.return_value.collect.return_value = []
        result = check_email_readiness(self.mock_session)
        self.assertEqual(result["state"], "NOT_CONFIGURED")
        self.assertFalse(result["integration_exists"])
        self.assertIn("not configured", result["message"].lower())

    # ---------------------------------------------------------------
    # 3. Recipient empty → send blocked gracefully
    # ---------------------------------------------------------------
    def test_03_empty_recipient_blocks_send(self):
        """Empty recipient returns NO_RECIPIENT status without calling SYSTEM$SEND_EMAIL."""
        ok, status, details = self.provider.send_email(
            session=self.mock_session,
            recipient="",
            subject="Test",
            body="Body"
        )
        self.assertFalse(ok)
        self.assertEqual(status, "NO_RECIPIENT")
        self.mock_session.sql.assert_not_called()

    def test_03b_none_recipient_blocks_send(self):
        """None recipient returns NO_RECIPIENT status."""
        ok, status, details = self.provider.send_email(
            session=self.mock_session,
            recipient=None,
            subject="Test",
            body="Body"
        )
        self.assertFalse(ok)
        self.assertEqual(status, "NO_RECIPIENT")

    # ---------------------------------------------------------------
    # 4. Trial limitation → graceful unavailable
    # ---------------------------------------------------------------
    def test_04_trial_limitation_graceful(self):
        """Insufficient privileges → UNAVAILABLE state."""
        self.mock_session.sql.return_value.collect.side_effect = Exception("insufficient privileges")
        result = check_email_readiness(self.mock_session)
        self.assertEqual(result["state"], "UNAVAILABLE")
        self.assertIn("unavailable", result["message"].lower())

    # ---------------------------------------------------------------
    # 5. Page load → ZERO email calls
    # ---------------------------------------------------------------
    def test_05_readiness_check_no_email_sent(self):
        """check_email_readiness does NOT call SYSTEM$SEND_EMAIL (only SHOW INTEGRATIONS)."""
        self.mock_session.sql.return_value.collect.return_value = []
        check_email_readiness(self.mock_session)
        sql_call = self.mock_session.sql.call_args[0][0]
        self.assertNotIn("SYSTEM$SEND_EMAIL", sql_call.upper())
        self.assertIn("SHOW NOTIFICATION INTEGRATIONS", sql_call.upper())

    # ---------------------------------------------------------------
    # 6. User clicks SEND → send attempted exactly once
    # ---------------------------------------------------------------
    def test_06_send_called_exactly_once(self):
        """send_snowflake_email calls provider.send_email exactly once."""
        row_mock = MagicMock()
        row_mock.__getitem__ = lambda s, i: "Email sent"
        self.mock_session.sql.return_value.collect.return_value = [row_mock]

        result = send_snowflake_email(
            session=self.mock_session,
            recipient="user@company.com",
            notification_type="CUSTOM",
            alert_payload={"machine_id": "Machine_03", "subject": "Test", "body": "Body"},
            force=True,
        )
        # The SQL call for SYSTEM$SEND_EMAIL should happen (plus audit)
        sql_calls = [call[0][0] for call in self.mock_session.sql.call_args_list]
        send_calls = [c for c in sql_calls if "SYSTEM$SEND_EMAIL" in c.upper()]
        self.assertEqual(len(send_calls), 1)

    # ---------------------------------------------------------------
    # 7. Send failure → sanitized error
    # ---------------------------------------------------------------
    def test_07_send_failure_sanitized_error(self):
        """When SYSTEM$SEND_EMAIL throws, error is returned but truncated."""
        long_error = "SQL execution error: " + "x" * 1000
        self.mock_session.sql.return_value.collect.side_effect = Exception(long_error)
        ok, status, details = self.provider.send_email(
            session=self.mock_session,
            recipient="user@company.com",
            subject="Test",
            body="Body"
        )
        self.assertFalse(ok)
        self.assertEqual(status, "ERROR")
        # Error is truncated to 500 chars
        self.assertLessEqual(len(details["error"]), 500)

    # ---------------------------------------------------------------
    # 8. No personal hardcoded recipient
    # ---------------------------------------------------------------
    def test_08_no_personal_hardcoded_recipient(self):
        """DEFAULT_RECIPIENT must not contain any personal email address."""
        self.assertEqual(DEFAULT_RECIPIENT, "")
        self.assertNotIn("@merkle.com", DEFAULT_RECIPIENT)
        self.assertNotIn("@gmail.com", DEFAULT_RECIPIENT)
        self.assertNotIn("siddharthasankar", DEFAULT_RECIPIENT)
        self.assertNotIn("siddhartha", DEFAULT_RECIPIENT)
        self.assertNotIn("shoib", DEFAULT_RECIPIENT)

    # ---------------------------------------------------------------
    # 9. Provider label = Snowflake Email
    # ---------------------------------------------------------------
    def test_09_provider_label_snowflake_email(self):
        """Provider status label must be 'Snowflake Email', not 'Gmail API'."""
        status = self.provider.get_status()
        self.assertEqual(status["label"], "Snowflake Email")
        self.assertNotIn("Gmail", status["label"])
        self.assertEqual(status["provider"], "SNOWFLAKE_EMAIL")

    # ---------------------------------------------------------------
    # 10. Core application continues if email unavailable
    # ---------------------------------------------------------------
    def test_10_no_session_returns_graceful_error(self):
        """Provider returns NO_SESSION gracefully when session is None."""
        ok, status, details = self.provider.send_email(
            session=None,
            recipient="user@company.com",
            subject="Test",
            body="Body"
        )
        self.assertFalse(ok)
        self.assertEqual(status, "NO_SESSION")
        self.assertIn("No Snowflake session", details["message"])

    def test_10b_readiness_check_no_session(self):
        """check_email_readiness returns UNAVAILABLE when session is None."""
        result = check_email_readiness(None)
        self.assertEqual(result["state"], "UNAVAILABLE")


class TestSecurityScan(unittest.TestCase):
    """Verify no personal emails are hardcoded in key source files."""

    def _read_file(self, relative_path):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        full_path = os.path.join(base, relative_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        return ""

    def test_no_merkle_email_in_streamlit_app(self):
        content = self._read_file("streamlit_app.py")
        self.assertNotIn("siddharthasankar.nath@merkle.com", content)
        self.assertNotIn("shoib.mohammed@merkle.com", content)

    def test_no_personal_gmail_in_snowflake_email_provider(self):
        content = self._read_file("services/snowflake_email_provider.py")
        self.assertNotIn("@merkle.com", content)
        self.assertNotIn("@gmail.com", content)

    def test_no_personal_default_in_notification_service(self):
        content = self._read_file("services/notification_service.py")
        self.assertNotIn("siddhartha.nath7@gmail.com", content)
        self.assertNotIn("siddharthasankar.nath@merkle.com", content)

    def test_no_personal_default_in_universal_email_composer(self):
        content = self._read_file("components/universal_email_composer.py")
        self.assertNotIn("siddhartha.nath7@gmail.com", content)
        self.assertNotIn("siddharthasankar.nath@merkle.com", content)


if __name__ == "__main__":
    unittest.main()
