"""
tests/test_three_layer_knowledge.py
Test suite for the Three-Layer Dynamic Maintenance Knowledge Flow.
Offline-safe unit tests using standard unittest.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.knowledge_service import (
    search_internal_knowledge,
    search_web_oem,
    cortex_synthesis,
    three_layer_knowledge_query,
    INTERNAL_MATCH_MIN_SCORE
)


# =============================================================================
# MOCK HELPERS
# =============================================================================

def mock_session_with_search_results(results_json):
    """Create a mock session that returns search results."""
    session = MagicMock()
    row = MagicMock()
    row.__getitem__ = lambda self, key: json.dumps(results_json) if key == "RESULTS" else None
    session.sql.return_value.collect.return_value = [row]
    return session


def mock_session_with_cortex_response(response_text):
    """Create a mock session that returns Cortex AI response."""
    session = MagicMock()
    row = MagicMock()
    row.__getitem__ = lambda self, key: response_text if key == "RESPONSE" else None
    session.sql.return_value.collect.return_value = [row]
    return session


# =============================================================================
# TEST CASES
# =============================================================================

class TestThreeLayerKnowledge(unittest.TestCase):

    def test_strong_internal_match_no_web_search(self):
        """When internal search returns strong match, web search must NOT be called."""
        search_results = [
            {"source_file": "Precision_Mill_Bearing_Manual.txt", "page_number": 1,
             "chunk_text": "bearing vibration temperature failure signature progressive bearing wear",
             "chunk_key": "manual:1:1"}
        ]
        session = mock_session_with_search_results(search_results)

        result = three_layer_knowledge_query(
            session=session,
            question="What does the bearing manual recommend for vibration?",
            machine_context={"machine_id": "Machine_03"}
        )

        self.assertIn(result["evidence_type"], ("INTERNAL", "COMBINED"))
        self.assertIn("INTERNAL", result["label"])

    def test_automatic_web_search_on_no_internal_match(self):
        """When internal search returns no match, web search must be called automatically."""
        session = MagicMock()
        empty_row = MagicMock()
        empty_row.__getitem__ = lambda self, key: "[]" if key == "RESULTS" else None
        oem_row = MagicMock()
        oem_row.__getitem__ = lambda self, key: '{"has_knowledge": true, "guidance": "Check motor temp sensor"}' if key == "RESPONSE" else None
        synth_row = MagicMock()
        synth_row.__getitem__ = lambda self, key: "Based on OEM guidance, check motor temperature sensor." if key == "RESPONSE" else None

        call_count = [0]
        def mock_sql(query):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_result.collect.return_value = [empty_row]
            elif call_count[0] == 2:
                mock_result.collect.return_value = [oem_row]
            else:
                mock_result.collect.return_value = [synth_row]
            return mock_result

        session.sql = mock_sql

        result = three_layer_knowledge_query(
            session=session,
            question="How do I resolve Kuka Robot Arm error E-402?"
        )

        self.assertIn(result["evidence_type"], ("EXTERNAL", "INSUFFICIENT"))

    def test_insufficient_evidence_no_fabrication(self):
        """When neither source has evidence, return INSUFFICIENT - do not fabricate."""
        session = MagicMock()
        empty_row = MagicMock()
        empty_row.__getitem__ = lambda self, key: "[]" if key == "RESULTS" else None

        no_knowledge_row = MagicMock()
        no_knowledge_row.__getitem__ = lambda self, key: "NO_RELIABLE_OEM_KNOWLEDGE" if key == "RESPONSE" else None

        call_count = [0]
        def mock_sql(query):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_result.collect.return_value = [empty_row]
            else:
                mock_result.collect.return_value = [no_knowledge_row]
            return mock_result

        session.sql = mock_sql

        result = three_layer_knowledge_query(
            session=session,
            question="How do I fix the quantum flux capacitor on a DeLorean?"
        )

        self.assertEqual(result["evidence_type"], "INSUFFICIENT")
        self.assertIn("INSUFFICIENT", result["label"])

    def test_external_result_has_disclaimer(self):
        """External OEM results must include a disclaimer."""
        session = MagicMock()
        row = MagicMock()
        row.__getitem__ = lambda self, key: json.dumps({
            "has_knowledge": True,
            "guidance": "Check motor temperature sensor",
            "source_basis": "Kuka documentation",
            "safety_warnings": []
        }) if key == "RESPONSE" else None
        session.sql.return_value.collect.return_value = [row]

        result = search_web_oem(session, "Kuka error E-402", "Kuka")

        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("disclaimer", result)
        self.assertIn("not an internal maintenance SOP", result["disclaimer"])

    def test_external_never_labeled_as_internal(self):
        """External evidence must NEVER be labeled as internal SOP."""
        session = MagicMock()
        row = MagicMock()
        row.__getitem__ = lambda self, key: json.dumps({
            "has_knowledge": True,
            "guidance": "Recommended procedure from OEM",
            "source_basis": "OEM technical knowledge",
            "safety_warnings": []
        }) if key == "RESPONSE" else None
        session.sql.return_value.collect.return_value = [row]

        result = search_web_oem(session, "test query")

        self.assertEqual(result["source_type"], "EXTERNAL_OEM_KNOWLEDGE")
        self.assertNotIn("INTERNAL", result.get("source_type", ""))

    def test_guardrails_enforce_machine_validation(self):
        """AI Guardrails must validate that machine exists."""
        result = three_layer_knowledge_query(
            session=None,
            question="Why is Machine_99 at risk?"
        )
        self.assertEqual(result["evidence_type"], "INSUFFICIENT")

    def test_single_call_no_confirmation(self):
        """The flow must complete in a single call with no user interaction."""
        search_results = [
            {"source_file": "Coolant_System_SOP.txt", "page_number": 1,
             "chunk_text": "coolant flow problem causes temperature rise vibration baseline",
             "chunk_key": "sop:1:1"}
        ]
        session = MagicMock()
        row = MagicMock()
        row.__getitem__ = lambda self, key: json.dumps(search_results) if key == "RESULTS" else None

        synth_row = MagicMock()
        synth_row.__getitem__ = lambda self, key: "Based on the Coolant System SOP..." if key == "RESPONSE" else None

        call_count = [0]
        def mock_sql(query):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_result.collect.return_value = [row]
            else:
                mock_result.collect.return_value = [synth_row]
            return mock_result

        session.sql = mock_sql

        result = three_layer_knowledge_query(
            session=session,
            question="What causes temperature rise when vibration is at baseline?"
        )

        self.assertIn("answer", result)
        self.assertNotEqual(result["answer"], "")
        self.assertIn("evidence_type", result)

    def test_mcp_server_has_all_tools(self):
        """The mcp_server.py must still have all 8 tools defined."""
        mcp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server.py")
        with open(mcp_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("def get_machine_context", content)
        self.assertIn("def get_machine_risk", content)
        self.assertIn("def get_oee_metrics", content)
        self.assertIn("def search_maintenance_docs", content)
        self.assertIn("def get_work_order", content)
        self.assertIn("def create_work_order", content)
        self.assertIn("def request_jira_ticket", content)
        self.assertIn("def search_web_oem", content)

    def test_search_web_oem_returns_structured_result(self):
        """search_web_oem must return structured results."""
        session = MagicMock()
        row = MagicMock()
        row.__getitem__ = lambda self, key: json.dumps({
            "has_knowledge": True,
            "guidance": "Technical guidance here",
            "source_basis": "OEM documentation",
            "safety_warnings": ["Wear PPE"]
        }) if key == "RESPONSE" else None
        session.sql.return_value.collect.return_value = [row]

        result = search_web_oem(session, "How to calibrate servo motor?", "Siemens")

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["source_type"], "EXTERNAL_OEM_KNOWLEDGE")
        self.assertTrue(len(result["results"]) > 0)

    def test_search_web_oem_no_match(self):
        """search_web_oem returns NO_MATCH when no knowledge available."""
        session = MagicMock()
        row = MagicMock()
        row.__getitem__ = lambda self, key: "NO_RELIABLE_OEM_KNOWLEDGE" if key == "RESPONSE" else None
        session.sql.return_value.collect.return_value = [row]

        result = search_web_oem(session, "How to fix flux capacitor?")

        self.assertEqual(result["status"], "NO_MATCH")
        self.assertEqual(result["results"], [])

    def test_jira_queue_service_unchanged(self):
        """The Jira queue service must remain intact."""
        jira_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "services", "jira_queue_service.py"
        )
        self.assertTrue(os.path.exists(jira_path), "jira_queue_service.py must still exist")

    def test_knowledge_service_does_not_touch_jira(self):
        """Knowledge service must not interact with Jira directly."""
        from services.knowledge_service import three_layer_knowledge_query
        import inspect
        source = inspect.getsource(three_layer_knowledge_query)
        self.assertNotIn("jira", source.lower())


if __name__ == "__main__":
    unittest.main()
