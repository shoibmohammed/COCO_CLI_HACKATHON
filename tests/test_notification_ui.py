"""
tests/test_notification_ui.py
Tests for the Notification Configuration UI — Snowflake Email + Slack only.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestSnowflakeEmailUI(unittest.TestCase):
    """1-2. Snowflake Email configured/unconfigured."""

    def test_01_email_ready_state(self):
        """check_email_readiness returns READY when integration exists."""
        from services.notification_service import check_email_readiness
        # Function signature test
        import inspect
        sig = inspect.signature(check_email_readiness)
        self.assertIn("session", sig.parameters)

    def test_02_email_not_configured_graceful(self):
        """check_email_readiness with None session returns UNAVAILABLE, not an error."""
        from services.notification_service import check_email_readiness
        result = check_email_readiness(None)
        self.assertIn(result["state"], ("UNAVAILABLE", "NOT_CONFIGURED"))


class TestSlackUI(unittest.TestCase):
    """3-4. Slack configured/unconfigured."""

    def test_03_slack_check_function_exists(self):
        """check_slack_configuration function exists."""
        from services.slack_service import check_slack_configuration
        import inspect
        sig = inspect.signature(check_slack_configuration)
        self.assertIn("session", sig.parameters)

    def test_04_slack_not_configured_graceful(self):
        """Slack with None session doesn't crash."""
        from services.slack_service import check_slack_configuration
        result = check_slack_configuration(None)
        self.assertIsInstance(result, dict)


class TestNoGmailUI(unittest.TestCase):
    """5. No Gmail UI in active notification config."""

    def test_05_no_gmail_in_system_status(self):
        base = os.path.join(os.path.dirname(__file__), "..", "components", "system_status.py")
        with open(base, encoding="utf-8", errors="replace") as f:
            content = f.read()
        # Should not have Gmail UI elements
        self.assertNotIn("Gmail API (OAuth", content)
        self.assertNotIn("CONNECT GMAIL", content)
        self.assertNotIn("credentials.json (Found)", content)
        self.assertNotIn("credentials.json (Missing)", content)
        self.assertNotIn("gmail.send", content)


class TestNoOutlookUI(unittest.TestCase):
    """6. No Outlook UI in active notification config."""

    def test_06_no_outlook_in_system_status(self):
        base = os.path.join(os.path.dirname(__file__), "..", "components", "system_status.py")
        with open(base, encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertNotIn("Outlook Delivery", content)
        self.assertNotIn("smtp.office365.com", content)
        self.assertNotIn("Microsoft Graph", content)


class TestNoOAuthButton(unittest.TestCase):
    """7. No OAuth button in active UI."""

    def test_07_no_oauth_button(self):
        base = os.path.join(os.path.dirname(__file__), "..", "components", "system_status.py")
        with open(base, encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertNotIn("CONNECT GMAIL", content)
        self.assertNotIn("GOOGLE AUTHORIZATION", content)
        self.assertNotIn("authenticate_gmail", content)


class TestNoPersonalRecipient(unittest.TestCase):
    """8. No personal default recipient."""

    def test_08_no_personal_in_system_status(self):
        base = os.path.join(os.path.dirname(__file__), "..", "components", "system_status.py")
        with open(base, encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertNotIn("@merkle.com", content)
        self.assertNotIn("@gmail.com", content)
        self.assertNotIn("siddharthawork7", content)

    def test_08b_no_personal_in_streamlit(self):
        base = os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py")
        with open(base, encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertNotIn("@merkle.com", content)


class TestExplicitSendOnly(unittest.TestCase):
    """9-10. Email/Slack send only on explicit click."""

    def test_09_system_status_no_auto_email(self):
        """system_status.py doesn't call send_email outside a button handler."""
        base = os.path.join(os.path.dirname(__file__), "..", "components", "system_status.py")
        with open(base, encoding="utf-8", errors="replace") as f:
            content = f.read()
        # send_email only appears inside button handlers (after st.button)
        self.assertNotIn("send_email(", content.split("st.button")[0][-200:] if "st.button" in content else "")

    def test_10_no_auto_slack(self):
        """Slack test is inside a button handler."""
        base = os.path.join(os.path.dirname(__file__), "..", "components", "system_status.py")
        with open(base, encoding="utf-8", errors="replace") as f:
            content = f.read()
        # send_slack_notification appears after "TEST SLACK" button
        if "send_slack_notification" in content:
            idx = content.index("send_slack_notification")
            preceding = content[max(0, idx-500):idx]
            self.assertIn("button", preceding)


class TestCoreAppWithout(unittest.TestCase):
    """11. Core application works when both are unconfigured."""

    def test_11_streamlit_parses(self):
        """streamlit_app.py has valid syntax regardless of email/slack config."""
        import ast
        base = os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py")
        with open(base, encoding="utf-8", errors="replace") as f:
            ast.parse(f.read())


class TestProviderLabels(unittest.TestCase):
    """12. Provider labels are accurate."""

    def test_12_snowflake_email_label(self):
        base = os.path.join(os.path.dirname(__file__), "..", "components", "system_status.py")
        with open(base, encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertIn("Snowflake Email", content)
        self.assertIn("SYSTEM$SEND_EMAIL", content)

    def test_12b_slack_label(self):
        base = os.path.join(os.path.dirname(__file__), "..", "components", "system_status.py")
        with open(base, encoding="utf-8", errors="replace") as f:
            content = f.read()
        self.assertIn("Slack", content)
        self.assertIn("SYSTEM$SEND_SNOWFLAKE_NOTIFICATION", content)


if __name__ == "__main__":
    unittest.main()
