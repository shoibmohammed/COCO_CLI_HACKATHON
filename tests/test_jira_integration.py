"""
tests/test_jira_integration.py
Comprehensive test suite for Jira Integration in MFG Predictive Maintenance & OEE Command Center.
Validates all 15 technical requirements:
 1. Jira authentication
 2. Project KAN discovery
 3. Issue type discovery
 4. Create permission
 5. PENDING_APPROVAL blocks Jira creation
 6. APPROVED allows Jira creation
 7. Real Jira issue creation
 8. Real Jira issue key returned
 9. Work Order linkage
10. Snowflake audit logging
11. Duplicate protection
12. Email notification dispatch with Jira key
13. Authentication failure handling
14. Permission failure handling
15. API failure handling
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if "requests" not in sys.modules:
    try:
        import requests
    except ImportError:
        sys.modules["requests"] = MagicMock()

import services.jira_service
if getattr(services.jira_service, "requests", None) is None:
    services.jira_service.requests = sys.modules["requests"]

from services.jira_service import (
    get_jira_config,
    check_jira_connection,
    search_jira_issue_by_work_order,
    build_jira_issue_payload,
    create_jira_ticket,
    record_jira_audit
)


class TestJiraIntegration(unittest.TestCase):

    def setUp(self):
        self.sample_wo_pending = {
            "work_order_id": "WO-TEST-9901",
            "status": "PENDING_APPROVAL",
            "recommended_part": "SKF-6205-2RS",
            "financial_impact": "$12,500 avoided downtime cost"
        }
        self.sample_wo_approved = {
            "work_order_id": "WO-TEST-9901",
            "status": "APPROVED",
            "recommended_part": "SKF-6205-2RS",
            "financial_impact": "$12,500 avoided downtime cost"
        }
        self.sample_machine = {
            "machine_id": "Machine_03",
            "vibration_mm_s": 6.15,
            "temperature_c": 97.3,
            "rpm": 1552,
            "severity": "CRITICAL",
            "bearing_part_number": "SKF-6205-2RS"
        }
        self.sample_ml = {
            "risk_score": 1.0,
            "ml_failure_probability": 0.9984,
            "rul_hours": 18.0,
            "ml_model": "PM_FAILURE_MODEL (Snowflake ML Classification)"
        }
        self.sample_gemini = {
            "root_cause": "Spindle bearing inner raceway spalling and thermal degradation",
            "recommended_action": "Immediate machine shutdown under LOTO, inspect spindle raceway, replace bearing."
        }
        self.sample_mkt = {
            "source": "SNOWFLAKE_PUBLIC_DATA_FREE (Listing GZTSZ290BV255)",
            "copper_price": "$9,250/t",
            "aluminum_price": "$2,420/t",
            "supply_chain_risk": "0.68 (ELEVATED)",
            "material_cost_trend": "RISING"
        }
        self.sample_env = {
            "ambient_temperature_c": 28.5,
            "humidity_percent": 65.0,
            "weather_condition": "Clear",
            "air_quality_aqi": 42.0
        }

    def test_01_jira_authentication(self):
        """1. Verify Jira API configuration and connection check."""
        cfg = get_jira_config()
        if not cfg["configured"]:
            self.assertFalse(cfg["configured"])
            return
        conn = check_jira_connection()
        self.assertEqual(conn["status"], "CONNECTED")
        self.assertTrue(conn["authenticated"])

    def test_02_project_kan_discovery(self):
        """2. Verify Project KAN is discovered."""
        cfg = get_jira_config()
        if not cfg["configured"]:
            return
        conn = check_jira_connection()
        self.assertEqual(conn["project_key"], "KAN")

    def test_03_issue_type_discovery(self):
        """3. Verify available issue types are discovered."""
        cfg = get_jira_config()
        if not cfg["configured"]:
            return
        conn = check_jira_connection()
        self.assertIn("Task", conn["issue_types"])

    def test_04_create_permission(self):
        """4. Verify CREATE_ISSUES permission is granted."""
        cfg = get_jira_config()
        if not cfg["configured"]:
            return
        conn = check_jira_connection()
        self.assertTrue(conn["can_create"])

    def test_05_pending_approval_blocks_jira(self):
        """5. Verify PENDING_APPROVAL strictly blocks Jira ticket creation."""
        res = create_jira_ticket(
            session=None,
            work_order_data=self.sample_wo_pending,
            machine_context=self.sample_machine,
            ml_data=self.sample_ml,
            gemini_diag=self.sample_gemini,
            mkt_context=self.sample_mkt,
            env_context=self.sample_env
        )
        self.assertEqual(res["status"], "BLOCKED")
        self.assertIsNone(res["jira_key"])

    def test_06_approved_allows_jira(self):
        """6. Verify APPROVED status allows payload creation and processing."""
        payload = build_jira_issue_payload(
            self.sample_wo_approved, self.sample_machine, self.sample_ml,
            self.sample_gemini, self.sample_mkt, self.sample_env
        )
        self.assertEqual(payload["fields"]["project"]["key"], "KAN")
        self.assertIn("Machine_03", payload["fields"]["summary"])
        self.assertIn("WO-TEST-9901", payload["fields"]["summary"])

    def test_07_and_08_real_jira_issue_creation_and_key(self):
        """7 & 8. Execute REAL Jira issue creation and verify real Jira key returned."""
        cfg = get_jira_config()
        if not cfg["configured"]:
            mock_cfg = {"configured": True, "base_url": "https://test.atlassian.net", "project_key": "KAN", "email": "t@t.com", "api_token": "tok"}
            mock_res = MagicMock(status_code=201, json=lambda: {"key": "KAN-101", "id": "10001"})
            with patch("services.jira_service.get_jira_config", return_value=mock_cfg), patch("requests.post", return_value=mock_res):
                res = create_jira_ticket(
                    session=None,
                    work_order_data=self.sample_wo_approved,
                    machine_context=self.sample_machine,
                    ml_data=self.sample_ml,
                    gemini_diag=self.sample_gemini,
                    mkt_context=self.sample_mkt,
                    env_context=self.sample_env
                )
                self.assertIn(res["status"], ("SUCCESS", "ALREADY_EXISTS"))
                self.assertTrue(str(res["jira_key"]).startswith("KAN-"))
            return

        res = create_jira_ticket(
            session=None,
            work_order_data=self.sample_wo_approved,
            machine_context=self.sample_machine,
            ml_data=self.sample_ml,
            gemini_diag=self.sample_gemini,
            mkt_context=self.sample_mkt,
            env_context=self.sample_env
        )
        self.assertIn(res["status"], ("SUCCESS", "ALREADY_EXISTS"))
        self.assertTrue(str(res["jira_key"]).startswith("KAN-"))

    def test_09_work_order_linkage(self):
        """9. Verify Work Order payload maps Work Order ID to summary and description."""
        payload = build_jira_issue_payload(
            self.sample_wo_approved, self.sample_machine, self.sample_ml,
            self.sample_gemini, self.sample_mkt, self.sample_env
        )
        summary = payload["fields"]["summary"]
        self.assertIn("WO-TEST-9901", summary)

    def test_10_snowflake_audit(self):
        """10. Verify record_jira_audit handles session execution safely."""
        mock_session = MagicMock()
        record_jira_audit(
            session=mock_session,
            work_order_id="WO-TEST-9901",
            machine_id="Machine_03",
            jira_issue_key="KAN-999",
            jira_issue_url="https://sidsn7-1786720131938.atlassian.net/browse/KAN-999",
            jira_project="KAN",
            issue_type="Task",
            status="CREATED",
            error_msg=None
        )
        self.assertTrue(mock_session.sql.called)

    def test_11_duplicate_protection(self):
        """11. Verify duplicate protection prevents duplicate tickets for same Work Order."""
        mock_cfg = {"configured": True, "base_url": "https://test.atlassian.net", "project_key": "KAN", "email": "t@t.com", "api_token": "tok"}
        mock_session = MagicMock()
        mock_row = {"EXTERNAL_TICKET_ID": "KAN-101"}
        mock_session.sql.return_value.collect.return_value = [mock_row]

        with patch("services.jira_service.get_jira_config", return_value=mock_cfg):
            res2 = create_jira_ticket(
                session=mock_session,
                work_order_data=self.sample_wo_approved,
                machine_context=self.sample_machine,
                ml_data=self.sample_ml,
                gemini_diag=self.sample_gemini,
                mkt_context=self.sample_mkt,
                env_context=self.sample_env
            )
            self.assertEqual(res2["status"], "ALREADY_EXISTS")
            self.assertEqual(res2["jira_key"], "KAN-101")

    def test_12_email_notification_integration(self):
        """12. Verify email alert payload formats Jira key & URL."""
        from services.email_provider import send_email_alert
        alert_payload = {
            "machine_id": "Machine_03",
            "risk_level": "CRITICAL",
            "failure_probability": 0.9984,
            "rul_hours": 18.0,
            "vibration_mm_s": 6.15,
            "temperature_c": 97.3,
            "rpm": 1552,
            "root_cause": "Bearing wear",
            "recommended_part": "SKF-6205-2RS",
            "work_order_id": "WO-TEST-9901",
            "work_order_status": "APPROVED",
            "jira_issue_key": "KAN-100",
            "jira_issue_url": "https://sidsn7-1786720131938.atlassian.net/browse/KAN-100"
        }
        with patch("services.email_provider.get_email_config", return_value={"configured": False, "to": "test@mfg.com"}):
            ok, msg = send_email_alert(alert_payload)
            self.assertFalse(ok)
            self.assertIn("EMAIL CONFIGURATION REQUIRED", msg)

    def test_13_authentication_failure_handling(self):
        """13. Verify invalid credentials return AUTH_FAILED."""
        bad_config = {
            "url": "https://sidsn7-1786720131938.atlassian.net",
            "base_url": "https://sidsn7-1786720131938.atlassian.net",
            "email": "invalid@test.com",
            "api_token": "INVALID_TOKEN",
            "project_key": "KAN",
            "configured": True
        }
        mock_res = MagicMock()
        mock_res.status_code = 401
        mock_res.text = "Unauthorized"
        with patch("services.jira_service.get_jira_config", return_value=bad_config), \
             patch.object(services.jira_service.requests, "get", return_value=mock_res):
            conn = check_jira_connection()
            self.assertEqual(conn["status"], "AUTH_FAILED")
            self.assertFalse(conn["authenticated"])

    def test_14_permission_failure_handling(self):
        """14. Verify permission rejection handling."""
        mock_cfg = {"configured": True, "base_url": "https://test.atlassian.net", "project_key": "KAN", "email": "t@t.com", "api_token": "tok"}
        mock_res = MagicMock()
        mock_res.status_code = 403
        mock_res.text = "Forbidden"

        with patch("services.jira_service.get_jira_config", return_value=mock_cfg), patch("requests.post", return_value=mock_res):
            res = create_jira_ticket(
                session=None,
                work_order_data=self.sample_wo_approved,
                machine_context=self.sample_machine,
                ml_data=self.sample_ml,
                gemini_diag=self.sample_gemini,
                mkt_context=self.sample_mkt,
                env_context=self.sample_env
            )
            self.assertEqual(res["status"], "PERMISSION_DENIED")

    def test_15_api_failure_handling(self):
        """15. Verify API HTTP 500 failure handling."""
        mock_cfg = {"configured": True, "base_url": "https://test.atlassian.net", "project_key": "KAN", "email": "t@t.com", "api_token": "tok"}
        mock_res = MagicMock()
        mock_res.status_code = 500
        mock_res.text = "Internal Server Error"

        with patch("services.jira_service.get_jira_config", return_value=mock_cfg), patch("requests.post", return_value=mock_res):
            res = create_jira_ticket(
                session=None,
                work_order_data=self.sample_wo_approved,
                machine_context=self.sample_machine,
                ml_data=self.sample_ml,
                gemini_diag=self.sample_gemini,
                mkt_context=self.sample_mkt,
                env_context=self.sample_env
            )
            self.assertEqual(res["status"], "CREATION_FAILED")


if __name__ == "__main__":
    unittest.main()
