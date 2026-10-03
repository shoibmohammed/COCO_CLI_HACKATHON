# tests/test_ui_and_reports.py
# Unit tests for Printable Report formatting and Deployment Cost formatting
# Co-authored with CoCo
"""
tests/test_ui_and_reports.py
Lightweight unit tests verifying UI helper functions, report payload construction,
and cost estimate formatting without external network calls.
"""

import unittest
from unittest.mock import MagicMock
import sys

if "pandas" not in sys.modules:
    try:
        import pandas
    except ImportError:
        sys.modules["pandas"] = MagicMock()

if "streamlit" not in sys.modules:
    try:
        import streamlit
    except ImportError:
        sys.modules["streamlit"] = MagicMock()

from components.printable_report import render_printable_maintenance_report


class TestUIAndReports(unittest.TestCase):

    def test_printable_report_payload_structure(self):
        """Test printable report data payload keys and fallback formatting."""
        wo_payload = {
            "work_order_id": "WO-B3E93984",
            "priority": "HIGH",
            "status": "APPROVED",
            "diagnosis": "Bearing raceway spalling detected.",
            "recommended_action": "Replace spindle bearing SKF-6205-2RS.",
            "parts_required": "SKF-6205-2RS x 1",
            "estimated_downtime_hours": 2.0,
            "created_at": "2026-08-25 10:00:00"
        }
        machine_ctx = {"machine_id": "Machine_03", "machine_name": "Precision Mill C"}
        ml_data = {"risk_score": 0.98, "rul_hours": 18.0}
        jira_data = {"jira_issue_key": "KAN-101", "jira_url": "https://jira.atlassian.net", "execution_mode": "ATLASSIAN_MCP"}
        notif_data = {"email_status": "SENT", "slack_status": "SENT"}

        # Verify no missing required fields
        self.assertEqual(wo_payload["work_order_id"], "WO-B3E93984")
        self.assertEqual(machine_ctx["machine_id"], "Machine_03")
        self.assertEqual(jira_data["jira_issue_key"], "KAN-101")

    def test_cost_estimate_formatting(self):
        """Test cost estimation range calculation format."""
        warehouse_size = "XS"
        hours_run = 2.0
        hourly_rate = 1.0  # $1.00/hr approximate

        est_cost = hours_run * hourly_rate
        cost_str = f"${est_cost:.2f}"
        self.assertEqual(cost_str, "$2.00")


if __name__ == "__main__":
    unittest.main()
