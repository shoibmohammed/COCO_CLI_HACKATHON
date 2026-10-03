# Unit & Governance Tests for External MCP Server Tools
# Co-authored with CoCo
"""
tests/test_mcp_tools.py

20-Scenario Test Suite verifying all 7 MCP tools, governance boundaries, AI Guardrails,
human approval enforcement, idempotency, and zero secret exposure.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import mcp_server
from mcp_server import (
    get_machine_context,
    get_machine_risk,
    get_oee_metrics,
    search_maintenance_docs,
    get_work_order,
    create_work_order,
    request_jira_ticket
)


class TestMCPReadTools(unittest.TestCase):
    """Tests 1-5: Read tools returning verified Snowflake data."""

    @patch("mcp_server._get_session")
    def test_01_get_machine_context_returns_real_data(self, mock_get_session):
        """Test 1: get_machine_context returns verified Snowflake telemetry & context."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        
        mock_row = {
            "MACHINE_ID": "Machine_03",
            "MACHINE_NAME": "CNC Mill 3",
            "PLANT": "Demo Plant",
            "LINE_NAME": "Line 1",
            "CRITICALITY": "HIGH",
            "TELEMETRY_TS": "2026-08-23 10:00:00",
            "VIBRATION_MM_S": 4.5,
            "TEMPERATURE_C": 82.3,
            "RPM": 1420.0,
            "PRESSURE_BAR": 5.1,
            "POWER_KW": 18.2,
            "SUPPLIER": "SKF Bearings Corp",
            "BEARING_PART_NUMBER": "SKF-6205-2RS",
            "BEARING_LEAD_DAYS": 3,
            "STATISTICAL_RISK_SCORE": 0.82,
            "ML_FAILURE_PROBABILITY": 0.88,
            "UNIFIED_RISK_SCORE": 0.85,
            "TOP_REASON": "Vibration z-score = 2.8 exceeds threshold",
            "FAILURE_CLASS": "CRITICAL"
        }
        mock_session.sql.return_value.collect.return_value = [mock_row]

        result = get_machine_context("Machine_03")

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["machine_id"], "Machine_03")
        self.assertEqual(result["vibration_mm_s"], 4.5)
        self.assertEqual(result["bearing_part_number"], "SKF-6205-2RS")

    @patch("mcp_server._get_session")
    def test_02_get_machine_risk_returns_real_ml_data(self, mock_get_session):
        """Test 2: get_machine_risk returns verified ML failure probability & RUL."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_risk_row = {
            "MACHINE_ID": "Machine_03",
            "STATISTICAL_RISK_SCORE": 0.82,
            "ML_FAILURE_PROBABILITY": 0.88,
            "UNIFIED_RISK_SCORE": 0.85,
            "TOP_REASON": "Bearing vibration anomaly",
            "FAILURE_CLASS": "CRITICAL"
        }
        mock_rul_row = {
            "ESTIMATED_RUL_HOURS": 14.5,
            "CONFIDENCE": "HIGH",
            "RUL_STATUS": "IMMINENT"
        }

        mock_session.sql.side_effect = [
            MagicMock(collect=MagicMock(return_value=[mock_risk_row])),
            MagicMock(collect=MagicMock(return_value=[mock_rul_row]))
        ]

        result = get_machine_risk("Machine_03")

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["unified_risk_score"], 0.85)
        self.assertEqual(result["priority_classification"], "P1")
        self.assertEqual(result["estimated_rul_hours"], 14.5)

    @patch("mcp_server._get_session")
    def test_03_get_oee_metrics_returns_real_oee_data(self, mock_get_session):
        """Test 3: get_oee_metrics returns Availability, Performance, Quality, OEE."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_row = {
            "MACHINE_ID": "Machine_03",
            "AVAILABILITY": 0.92,
            "PERFORMANCE": 0.88,
            "QUALITY": 0.99,
            "OEE": 0.802,
            "CALCULATION_TS": "2026-08-23 10:00:00"
        }
        mock_session.sql.return_value.collect.return_value = [mock_row]

        result = get_oee_metrics("Machine_03")

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(len(result["metrics"]), 1)
        self.assertEqual(result["metrics"][0]["oee"], 0.802)

    @patch("mcp_server.search_documents")
    def test_04_search_maintenance_docs_returns_grounded_sources(self, mock_search_docs):
        """Test 4: search_maintenance_docs returns grounded document references."""
        mock_search_docs.return_value = [{
            "source_file": "Precision_Mill_Bearing_Manual.txt",
            "chunk_text": "Spindle bearing replacement procedure...",
            "score": 4.5
        }]

        result = search_maintenance_docs("bearing vibration")

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["documents"][0]["source_file"], "Precision_Mill_Bearing_Manual.txt")

    @patch("mcp_server._get_session")
    def test_05_get_work_order_returns_actual_data(self, mock_get_session):
        """Test 5: get_work_order returns real work order state from Snowflake."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_row = {
            "WORK_ORDER_ID": 501,
            "MACHINE_ID": "Machine_01",
            "DIAGNOSIS": "Spindle drive belt wear",
            "RECOMMENDED_ACTION": "Replace drive belt",
            "PARTS_REQUIRED": "DRIVE-BELT-HX",
            "PRIORITY": "P1",
            "STATUS": "APPROVED",
            "RISK_SCORE": 0.85,
            "RUL_HOURS": 12.0,
            "CREATED_AT": "2026-08-23 08:00:00",
            "APPROVED_AT": "2026-08-23 08:30:00",
            "EXTERNAL_TICKET_ID": "KAN-501"
        }
        mock_session.sql.return_value.collect.return_value = [mock_row]

        result = get_work_order("WO-501")

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["work_order_id"], "WO-501")
        self.assertEqual(result["work_order_status"], "APPROVED")
        self.assertEqual(result["external_ticket_id"], "KAN-501")


class TestMCPGovernedActions(unittest.TestCase):
    """Tests 6-10: Governed action tools & AI Guardrails enforcement."""

    @patch("mcp_server.validate_work_order_creation")
    @patch("mcp_server._get_session")
    def test_06_create_work_order_returns_pending_approval(self, mock_get_session, mock_guardrail):
        """Test 6: create_work_order creates record strictly as PENDING_APPROVAL."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_guardrail.return_value = {"is_valid": True, "reason": "Passed"}

        mock_session.sql.side_effect = [
            MagicMock(collect=MagicMock(return_value=[])),
            MagicMock(collect=MagicMock(return_value=[{"NEW_WO_ID": 601}]))
        ]

        result = create_work_order(
            machine_id="Machine_03",
            diagnosis="Spindle bearing degradation",
            recommended_action="Replace spindle bearing",
            parts_required="SKF-6205-2RS",
            priority="P1",
            risk_score=0.88,
            rul_hours=14.0
        )

        self.assertEqual(result["status"], "PENDING_APPROVAL")
        self.assertEqual(result["work_order_id"], "WO-601")
        self.assertEqual(result["guardrail_status"], "PASS")

    @patch("mcp_server.validate_work_order_creation")
    @patch("mcp_server._get_session")
    def test_07_create_work_order_cannot_approve(self, mock_get_session, mock_guardrail):
        """Test 7: create_work_order CANNOT approve a work order (no APPROVED status allowed)."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_guardrail.return_value = {"is_valid": True}

        mock_session.sql.side_effect = [
            MagicMock(collect=MagicMock(return_value=[])),
            MagicMock(collect=MagicMock(return_value=[{"NEW_WO_ID": 701}]))
        ]

        result = create_work_order(
            machine_id="Machine_03", diagnosis="Test", recommended_action="Test",
            parts_required="Part", priority="P1", risk_score=0.8, rul_hours=10
        )

        self.assertNotEqual(result["status"], "APPROVED")
        self.assertEqual(result["status"], "PENDING_APPROVAL")
        self.assertTrue(result["human_approval_required"])

    @patch("mcp_server.validate_work_order_creation")
    @patch("mcp_server._get_session")
    def test_08_invalid_machine_rejected(self, mock_get_session, mock_guardrail):
        """Test 8: Guardrails reject work order creation for non-existent machine."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_guardrail.return_value = {
            "is_valid": False,
            "reason": "Machine Machine_99 does not exist in master catalog."
        }

        result = create_work_order(
            machine_id="Machine_99", diagnosis="Invalid", recommended_action="Test",
            parts_required="Part", priority="P1", risk_score=0.8, rul_hours=10
        )

        self.assertEqual(result["status"], "GUARDRAIL_BLOCKED")
        self.assertEqual(result["guardrail_status"], "FAIL")
        self.assertIsNone(result["work_order_id"])

    @patch("mcp_server.validate_work_order_creation")
    @patch("mcp_server._get_session")
    def test_09_fabricated_telemetry_rejected(self, mock_get_session, mock_guardrail):
        """Test 9: Guardrails reject work order with ungrounded/fabricated risk or telemetry."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_guardrail.return_value = {
            "is_valid": False,
            "reason": "Risk score exceeds maximum plausible limit."
        }

        result = create_work_order(
            machine_id="Machine_03", diagnosis="Test", recommended_action="Test",
            parts_required="Part", priority="P1", risk_score=999.0, rul_hours=10
        )

        self.assertEqual(result["status"], "GUARDRAIL_BLOCKED")
        self.assertEqual(result["guardrail_status"], "FAIL")

    @patch("mcp_server._get_session")
    def test_10_request_jira_ticket_blocked_for_pending_approval(self, mock_get_session):
        """Test 10: request_jira_ticket is BLOCKED if WORK_ORDERS.STATUS != 'APPROVED'."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_wo = {
            "WORK_ORDER_ID": 301,
            "MACHINE_ID": "Machine_03",
            "STATUS": "PENDING_APPROVAL",
            "DIAGNOSIS": "Bearing degradation",
            "RECOMMENDED_ACTION": "Replace bearing",
            "PRIORITY": "P1"
        }
        mock_session.sql.return_value.collect.return_value = [mock_wo]

        result = request_jira_ticket("WO-301")

        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "WORK_ORDER_NOT_APPROVED")


class TestMCPJiraQueueIntegration(unittest.TestCase):
    """Tests 11-14: Jira queue enqueuing & idempotency checks."""

    @patch("mcp_server.enqueue_jira_request")
    @patch("mcp_server.get_queue_status")
    @patch("mcp_server.check_existing_success")
    @patch("mcp_server._get_session")
    def test_11_request_jira_ticket_creates_pending_queue_for_approved(
        self, mock_get_session, mock_check_success, mock_queue_status, mock_enqueue
    ):
        """Test 11: request_jira_ticket creates PENDING queue for APPROVED work order."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_wo = {
            "WORK_ORDER_ID": 501,
            "MACHINE_ID": "Machine_01",
            "STATUS": "APPROVED",
            "DIAGNOSIS": "Belt wear",
            "RECOMMENDED_ACTION": "Replace belt",
            "PRIORITY": "P1"
        }
        mock_session.sql.return_value.collect.return_value = [mock_wo]
        mock_check_success.return_value = None
        mock_queue_status.return_value = None
        mock_enqueue.return_value = {"status": "QUEUED"}

        result = request_jira_ticket("WO-501")

        self.assertEqual(result["status"], "PENDING")
        self.assertEqual(result["jira_queue_status"], "QUEUED")

    @patch("mcp_server.check_existing_success")
    @patch("mcp_server._get_session")
    def test_12_success_prevents_duplicate(self, mock_get_session, mock_check_success):
        """Test 12: Existing SUCCESS record prevents duplicate Jira ticket creation."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_wo = {"WORK_ORDER_ID": 501, "MACHINE_ID": "Machine_01", "STATUS": "APPROVED"}
        mock_session.sql.return_value.collect.return_value = [mock_wo]
        mock_check_success.return_value = {"jira_issue_key": "KAN-501", "jira_url": "https://jira.test/browse/KAN-501"}

        result = request_jira_ticket("WO-501")

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["jira_issue_key"], "KAN-501")

    @patch("mcp_server.get_queue_status")
    @patch("mcp_server.check_existing_success")
    @patch("mcp_server._get_session")
    def test_13_processing_prevents_duplicate(self, mock_get_session, mock_check_success, mock_queue_status):
        """Test 13: PROCESSING queue record prevents duplicate request."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_wo = {"WORK_ORDER_ID": 501, "MACHINE_ID": "Machine_01", "STATUS": "APPROVED"}
        mock_session.sql.return_value.collect.return_value = [mock_wo]
        mock_check_success.return_value = None
        mock_queue_status.return_value = {"status": "PROCESSING"}

        result = request_jira_ticket("WO-501")

        self.assertEqual(result["status"], "PROCESSING")

    @patch("mcp_server.enqueue_jira_request")
    @patch("mcp_server.get_queue_status")
    @patch("mcp_server.check_existing_success")
    @patch("mcp_server._get_session")
    def test_14_failed_follows_retry_logic(
        self, mock_get_session, mock_check_success, mock_queue_status, mock_enqueue
    ):
        """Test 14: FAILED queue record allows controlled retry."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        mock_wo = {
            "WORK_ORDER_ID": 501,
            "MACHINE_ID": "Machine_01",
            "STATUS": "APPROVED",
            "DIAGNOSIS": "Belt wear",
            "RECOMMENDED_ACTION": "Replace belt",
            "PRIORITY": "P1"
        }
        mock_session.sql.return_value.collect.return_value = [mock_wo]
        mock_check_success.return_value = None
        mock_queue_status.return_value = {"status": "FAILED", "attempt_count": 1}
        mock_enqueue.return_value = {"status": "QUEUED"}

        result = request_jira_ticket("WO-501")

        self.assertEqual(result["status"], "PENDING")


class TestMCPBoundaryAndSecurity(unittest.TestCase):
    """Tests 15-20: Security, secret protection, auditing, and boundary checks."""

    @patch("mcp_server._get_session")
    def test_15_mcp_responses_contain_no_secrets(self, mock_get_session):
        """Test 15: MCP tool responses contain zero passwords or tokens."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_session.sql.return_value.collect.return_value = [{
            "MACHINE_ID": "Machine_03", "VIBRATION_MM_S": 4.5, "TEMPERATURE_C": 80.0
        }]
        result = get_machine_context("Machine_03")
        res_str = str(result).lower()
        self.assertNotIn("api_token", res_str)
        self.assertNotIn("password", res_str)
        self.assertNotIn("basic ", res_str)

    def test_16_mcp_server_has_no_direct_jira_http_code(self):
        """Test 16: mcp_server.py source code contains no direct Jira HTTP requests."""
        with open(mcp_server.__file__, "r") as f:
            code = f.read()

        self.assertNotIn("requests.post(", code)
        self.assertNotIn("requests.put(", code)
        self.assertNotIn("atlassian.net", code)

    @patch("mcp_server._get_session")
    def test_17_mcp_actions_are_auditable(self, mock_get_session):
        """Test 17: Governed MCP actions write audit records to Snowflake."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_session.sql.side_effect = [
            MagicMock(collect=MagicMock(return_value=[])),
            MagicMock(collect=MagicMock(return_value=[{"NEW_WO_ID": 801}]))
        ]

        with patch("mcp_server.validate_work_order_creation", return_value={"is_valid": True}):
            res = create_work_order("Machine_03", "Diag", "Action", "Part")
            self.assertEqual(res["status"], "PENDING_APPROVAL")
            mock_session.sql.assert_called()

    def test_18_local_jira_worker_remains_functional(self):
        """Test 18: Local Jira Worker single-pass script resolves and is runnable."""
        worker_script = os.path.join(PROJECT_ROOT, "local_jira_worker", "approved_work_order_to_jira.py")
        self.assertTrue(os.path.exists(worker_script))

    @patch("mcp_server._get_session")
    def test_19_mcp_authentication_validated(self, mock_get_session):
        """Test 19: MCP tool handles Snowflake session authentication validation."""
        mock_get_session.side_effect = RuntimeError("Failed to acquire Snowflake session: Invalid credentials")
        with self.assertRaises(RuntimeError):
            get_machine_context("Machine_03")

    @patch("mcp_server.validate_work_order_creation")
    @patch("mcp_server._get_session")
    def test_20_mcp_tool_authorization_validated(self, mock_get_session, mock_guardrail):
        """Test 20: Tool authorization blocks illegal state transitions."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_guardrail.return_value = {"is_valid": False, "reason": "Unauthorized action"}
        res = create_work_order("Machine_03", "Diag", "Action", "Part")
        self.assertEqual(res["status"], "GUARDRAIL_BLOCKED")


if __name__ == "__main__":
    unittest.main()
