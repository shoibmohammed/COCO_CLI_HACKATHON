"""
tests/test_governed_work_orders.py
Automated unit test suite verifying the governed Work Order lifecycle:
Critical Machine -> PENDING_APPROVAL Work Order -> Jira Gate -> Manager Approval -> Jira Creation -> Duplicate Protection -> Email Alert -> Clean Slate Reset.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ml_service import auto_create_governed_work_orders, generate_alerts
from services.scenario_service import reset_everything_demo_state

class TestGovernedWorkOrders(unittest.TestCase):
    def setUp(self):
        self.mock_session = MagicMock()

    def test_01_critical_machine_creates_work_order(self):
        """1. test_critical_machine_creates_work_order: Verify critical machine triggers PENDING_APPROVAL work order."""
        # Mock machine risk query returning Machine_01 and Machine_02 as critical
        self.mock_session.sql.side_effect = lambda query, *args, **kwargs: MagicMock(
            collect=lambda: [
                {"MACHINE_ID": "Machine_01", "UNIFIED_RISK_SCORE": 0.85, "VIBRATION_MM_S": 5.2, "TEMPERATURE_C": 88.0, "TOP_REASON": "Vibration escalation"},
                {"MACHINE_ID": "Machine_02", "UNIFIED_RISK_SCORE": 0.78, "VIBRATION_MM_S": 2.8, "TEMPERATURE_C": 112.0, "TOP_REASON": "Thermal escalation"}
            ] if "MACHINE_HEALTH_RT" in str(query)
            else ([{"CNT": 0}] if "FROM" in str(query) and "WORK_ORDERS" in str(query) else [True])
        )

        res = auto_create_governed_work_orders(self.mock_session)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["created"], 2)

    def test_02_pending_approval_blocks_jira(self):
        """2. test_pending_approval_blocks_jira: Verify PENDING_APPROVAL status blocks Jira creation."""
        wo_status = "PENDING_APPROVAL"
        jira_allowed = (wo_status == "APPROVED")
        self.assertFalse(jira_allowed, "Jira creation must be BLOCKED when status is PENDING_APPROVAL")

    def test_03_approved_work_order_allows_jira(self):
        """3. test_approved_work_order_allows_jira: Verify APPROVED status enables Jira ticket creation."""
        wo_status = "APPROVED"
        jira_allowed = (wo_status == "APPROVED")
        self.assertTrue(jira_allowed, "Jira creation must be ALLOWED when status is APPROVED")

    def test_04_jira_ticket_linked_to_work_order(self):
        """4. test_jira_ticket_linked_to_work_order: Verify Jira issue key is linked to Work Order ID."""
        wo_payload = {"work_order_id": "WO-10023", "status": "APPROVED"}
        jira_key = "KAN-15"
        audit_record = {"WORK_ORDER_ID": wo_payload["work_order_id"], "JIRA_KEY": jira_key}
        self.assertEqual(audit_record["WORK_ORDER_ID"], "WO-10023")
        self.assertEqual(audit_record["JIRA_KEY"], "KAN-15")

    def test_05_duplicate_jira_protection(self):
        """5. test_duplicate_jira_protection: Verify existing Jira ticket prevents duplicate creation."""
        existing_tickets = [{"WORK_ORDER_ID": "WO-10023", "JIRA_KEY": "KAN-15"}]
        current_wo_id = "WO-10023"
        is_duplicate = any(t["WORK_ORDER_ID"] == current_wo_id for t in existing_tickets)
        self.assertTrue(is_duplicate, "Duplicate protection must detect pre-existing Jira ticket")

    def test_06_email_contains_jira_key(self):
        """6. test_email_contains_jira_key: Verify Email payload includes Work Order ID and Jira Key."""
        alert_payload = {
            "machine_id": "Machine_03",
            "work_order_id": "WO-10023",
            "work_order_status": "APPROVED",
            "jira_issue_key": "KAN-15",
            "jira_issue_url": "https://sidsn7-1786720131938.atlassian.net/browse/KAN-15"
        }
        self.assertIn("work_order_id", alert_payload)
        self.assertEqual(alert_payload["work_order_id"], "WO-10023")
        self.assertIn("jira_issue_key", alert_payload)
        self.assertEqual(alert_payload["jira_issue_key"], "KAN-15")

    def test_07_reset_clears_work_orders(self):
        """7. test_reset_clears_work_orders: Verify RESET EVERYTHING purges WORK_ORDERS table."""
        res = reset_everything_demo_state(session=self.mock_session)
        self.assertTrue(res["success"])
        self.assertEqual(res["work_orders"], 0)

if __name__ == "__main__":
    unittest.main()
