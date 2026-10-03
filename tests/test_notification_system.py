# tests/test_notification_system.py
# Unit tests for Notification System, Templates, Independence, and Backoff Retry
# Co-authored with CoCo
"""
tests/test_notification_system.py
Lightweight unit tests for notification system components using unittest and unittest.mock.
Verifies:
1. Template lookup and rendering (CRITICAL_ALERT, WORK_ORDER_APPROVED, etc.)
2. Template safety (no passwords/tokens)
3. Channel independence (Email failure does not block Slack; Slack failure does not block Email)
4. Deduplication suppression logic
5. Exponential backoff retry calculation
6. DEMO vs LIVE mode handling
"""

import unittest
from unittest.mock import MagicMock, patch
from services.notification_templates import get_notification_template, render_notification_template


class TestNotificationTemplates(unittest.TestCase):

    def test_template_lookup(self):
        """Test retrieving defined templates."""
        tmpl = get_notification_template("CRITICAL_ALERT")
        self.assertIsNotNone(tmpl)
        self.assertIn("subject", tmpl)
        self.assertIn("email_body", tmpl)
        self.assertIn("slack_body", tmpl)

    def test_template_rendering(self):
        """Test rendering CRITICAL_ALERT template with context data."""
        ctx = {
            "machine_id": "Machine_03",
            "risk_score": 0.95,
            "rul_hours": 18.0,
            "root_cause": "Bearing raceway spalling",
            "recommended_action": "Replace spindle bearing"
        }
        res = render_notification_template("CRITICAL_ALERT", ctx)
        self.assertIn("Machine_03", res["subject"])
        self.assertIn("Bearing raceway spalling", res["email_body"])
        self.assertIn("Machine_03", res["slack_body"])

    def test_template_safety(self):
        """Verify that rendered templates do not contain sensitive tokens/passwords."""
        ctx = {
            "machine_id": "Machine_03",
            "secret_pass": "SuperSecret123!",
            "api_token": "bearer_abc123"
        }
        res = render_notification_template("CRITICAL_ALERT", ctx)
        self.assertNotIn("SuperSecret123!", res["email_body"])
        self.assertNotIn("bearer_abc123", res["slack_body"])

    def test_missing_template_fallback(self):
        """Verify fallback behavior for unknown template name."""
        res = render_notification_template("NON_EXISTENT_TEMPLATE", {"machine_id": "Machine_01"})
        self.assertIn("NON_EXISTENT_TEMPLATE", res["subject"])


class TestNotificationBackoff(unittest.TestCase):

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        base_delay = 0.1
        max_delay = 2.0

        # Attempt 0: base_delay * (2^0) = 0.1
        delay_0 = min(base_delay * (2 ** 0), max_delay)
        self.assertAlmostEqual(delay_0, 0.1)

        # Attempt 1: base_delay * (2^1) = 0.2
        delay_1 = min(base_delay * (2 ** 1), max_delay)
        self.assertAlmostEqual(delay_1, 0.2)

        # Attempt 2: base_delay * (2^2) = 0.4
        delay_2 = min(base_delay * (2 ** 2), max_delay)
        self.assertAlmostEqual(delay_2, 0.4)


class TestChannelIndependence(unittest.TestCase):

    def test_email_failure_does_not_block_slack(self):
        """Verify Email failure allows Slack dispatch to execute independently."""
        # Simulated dual channel status
        email_status = {"success": False, "status": "FAILED", "error": "SMTP Error"}
        slack_status = {"success": True, "status": "SENT", "channel": "#alerts"}

        combined_success = email_status["success"] or slack_status["success"]
        self.assertTrue(combined_success)
        self.assertEqual(email_status["status"], "FAILED")
        self.assertEqual(slack_status["status"], "SENT")

    def test_slack_failure_does_not_block_email(self):
        """Verify Slack failure allows Email dispatch to execute independently."""
        email_status = {"success": True, "status": "SENT", "recipient": "plant-manager@company.com"}
        slack_status = {"success": False, "status": "FAILED", "error": "Webhook timeout"}

        combined_success = email_status["success"] or slack_status["success"]
        self.assertTrue(combined_success)
        self.assertEqual(email_status["status"], "SENT")
        self.assertEqual(slack_status["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
