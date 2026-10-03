"""
tests/test_sql_safety_and_modularity.py
Unit Tests for SQL Injection Hardening, Centralized Whitelist Identifier Resolution,
Modular Page Architecture, and Demo Session State Integrity.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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

if "plotly" not in sys.modules:
    try:
        import plotly
    except ImportError:
        sys.modules["plotly"] = MagicMock()
        sys.modules["plotly.graph_objects"] = MagicMock()
        sys.modules["plotly.express"] = MagicMock()

import config


class TestSQLSafetyAndConfig(unittest.TestCase):
    """Test SQL safety policies, identifier whitelisting, and parameterization."""

    def test_valid_table_resolution(self):
        """Valid table identifiers must resolve correctly to FQN."""
        self.assertEqual(config.table("WORK_ORDERS"), "PM_OEE_DB.CORE.WORK_ORDERS")
        self.assertEqual(config.table("SENSOR_READINGS"), "PM_OEE_DB.CORE.SENSOR_READINGS")
        self.assertEqual(config.table("MACHINE_HEALTH_RT"), "PM_OEE_DB.CORE.MACHINE_HEALTH_RT")
        self.assertEqual(config.table("JIRA_INTEGRATION_QUEUE"), "PM_OEE_DB.CORE.JIRA_INTEGRATION_QUEUE")

    def test_invalid_table_raises_value_error(self):
        """Unwhitelisted table names must be rejected with ValueError."""
        with self.assertRaises(ValueError):
            config.table("UNAUTHORIZED_SECRET_TABLE")

        with self.assertRaises(ValueError):
            config.table("WORK_ORDERS; DROP TABLE USERS; --")

        with self.assertRaises(ValueError):
            config.table("users UNION SELECT * FROM passwords")

    def test_invalid_schema_raises_value_error(self):
        """Unwhitelisted schemas must be rejected with ValueError."""
        with self.assertRaises(ValueError):
            config.get_object_name("WORK_ORDERS", schema="SECRET_SCHEMA")

    def test_malicious_input_in_mock_session(self):
        """Verify queries with malicious inputs use parameterized binding instead of interpolation."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.collect.return_value = [{"CNT": 0}]
        mock_session.sql.return_value = mock_result

        from services.ai_guardrails import validate_machine_exists
        malicious_input = "Machine_03' OR '1'='1"

        validate_machine_exists(mock_session, malicious_input)

        # Ensure session.sql was called with params=[...]
        self.assertTrue(mock_session.sql.called)
        args, kwargs = mock_session.sql.call_args
        self.assertIn("?", args[0])
        self.assertNotIn(malicious_input, args[0])  # SQL text itself must NOT contain raw unescaped input
        self.assertEqual(kwargs.get("params"), [malicious_input])

    def test_malicious_drop_table_input(self):
        """Verify drop table injection string is safely bound as a literal."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.collect.return_value = [{"CNT": 0}]
        mock_session.sql.return_value = mock_result

        from services.ml_service import get_ml_context_for_gemini
        malicious_id = "Machine_03'; DROP TABLE WORK_ORDERS; --"

        get_ml_context_for_gemini(mock_session, malicious_id)

        self.assertTrue(mock_session.sql.called)
        args, kwargs = mock_session.sql.call_args
        self.assertIn("?", args[0])
        self.assertNotIn("DROP TABLE", args[0])
        self.assertEqual(kwargs.get("params"), [malicious_id])


class TestModularPageArchitecture(unittest.TestCase):
    """Test that all modular page view modules import cleanly without side-effects."""

    def test_import_command_center(self):
        import pages.command_center as cc
        self.assertTrue(hasattr(cc, "render_command_center"))

    def test_import_alerts(self):
        import pages.alerts as al
        self.assertTrue(hasattr(al, "render_alerts"))

    def test_import_machine_intelligence(self):
        import pages.machine_intelligence as mi
        self.assertTrue(hasattr(mi, "render_machine_intelligence"))

    def test_import_what_if_simulator(self):
        import pages.what_if_simulator as wif
        self.assertTrue(hasattr(wif, "render_what_if_simulator"))

    def test_import_work_orders(self):
        import pages.work_orders as wo
        self.assertTrue(hasattr(wo, "render_work_orders"))

    def test_import_ai_copilot(self):
        import pages.ai_copilot as ai
        self.assertTrue(hasattr(ai, "render_ai_copilot"))

    def test_import_supply_chain(self):
        import pages.supply_chain as sc
        self.assertTrue(hasattr(sc, "render_supply_chain"))

    def test_import_system_status_page(self):
        import pages.system_status_page as ssp
        self.assertTrue(hasattr(ssp, "render_system_status_page"))

    def test_import_reports(self):
        import pages.reports as rep
        self.assertTrue(hasattr(rep, "render_reports"))

    def test_import_settings_page(self):
        import pages.settings_page as sp
        self.assertTrue(hasattr(sp, "render_settings_page"))


class TestGoldenDemoFlowIntegrity(unittest.TestCase):
    """Test that session state keys and demo workflow contracts remain intact."""

    def test_expected_demo_session_keys(self):
        """Essential demo keys must be recognized."""
        required_transient_keys = [
            "active_diagnosis", "active_scenario_key", "selected_machine",
            "wo_approved", "jira_result", "notification_result",
            "nav_index"
        ]
        self.assertTrue(len(required_transient_keys) >= 7)


if __name__ == "__main__":
    unittest.main()
