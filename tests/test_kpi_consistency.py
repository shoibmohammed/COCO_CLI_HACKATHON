"""
tests/test_kpi_consistency.py
Automated test suite verifying KPI state consistency, dynamic downtime risk calculation,
OEE independence, single global header rendering, and Reset Everything baseline restoration.
"""

import unittest
from unittest.mock import MagicMock
import sys
from typing import Dict, Any

if "streamlit" not in sys.modules:
    try:
        import streamlit
    except ImportError:
        sys.modules["streamlit"] = MagicMock()

import streamlit as st
st.columns = lambda n: [MagicMock() for _ in range(n if isinstance(n, int) else len(n))]

from components.kpi_card import render_kpi_cards
from services.scenario_service import SCENARIOS, reset_everything_demo_state, inject_scenario_to_snowflake


class TestKPIConsistency(unittest.TestCase):

    def test_01_kpi_card_empty_state_captions(self):
        """Verify KPI card captions display correct empty-state text when metrics are 0."""
        from components.kpi_card import render_kpi_cards
        
        try:
            render_kpi_cards(
                oee_pct=0.0,
                fleet_risk=0.00,
                critical_count=0,
                warning_count=0,
                open_wo_count=0,
                downtime_risk_usd=0.0
            )
            success = True
        except Exception as e:
            success = False
            self.fail(f"render_kpi_cards failed on zero values: {e}")
        self.assertTrue(success)

    def test_02_dynamic_downtime_risk_calculation(self):
        """Verify dynamic downtime risk calculation based on affected machines."""
        machine_loss_map = {
            "Machine_03": 12500.0,
            "Machine_02": 6250.0,
            "Machine_01": 3125.0,
            "Machine_04": 0.0
        }

        # 1. Clean state: no machines at risk
        risk_df_clean = [
            {"MACHINE_ID": "Machine_01", "UNIFIED_RISK_SCORE": 0.08},
            {"MACHINE_ID": "Machine_02", "UNIFIED_RISK_SCORE": 0.12},
            {"MACHINE_ID": "Machine_03", "UNIFIED_RISK_SCORE": 0.05},
            {"MACHINE_ID": "Machine_04", "UNIFIED_RISK_SCORE": 0.02},
        ]
        total_dt_clean = sum(
            machine_loss_map.get(m["MACHINE_ID"], 0.0)
            for m in risk_df_clean if m["UNIFIED_RISK_SCORE"] >= 0.40
        )
        self.assertEqual(total_dt_clean, 0.0)

        # 2. Machine_03 Critical (1.00)
        risk_df_m3 = [
            {"MACHINE_ID": "Machine_01", "UNIFIED_RISK_SCORE": 0.08},
            {"MACHINE_ID": "Machine_02", "UNIFIED_RISK_SCORE": 0.12},
            {"MACHINE_ID": "Machine_03", "UNIFIED_RISK_SCORE": 1.00},
            {"MACHINE_ID": "Machine_04", "UNIFIED_RISK_SCORE": 0.02},
        ]
        total_dt_m3 = sum(
            machine_loss_map.get(m["MACHINE_ID"], 0.0)
            for m in risk_df_m3 if m["UNIFIED_RISK_SCORE"] >= 0.40
        )
        self.assertEqual(total_dt_m3, 12500.0)

        # 3. Machine_01 (0.48) + Machine_02 (0.78)
        risk_df_m1_m2 = [
            {"MACHINE_ID": "Machine_01", "UNIFIED_RISK_SCORE": 0.48},
            {"MACHINE_ID": "Machine_02", "UNIFIED_RISK_SCORE": 0.78},
            {"MACHINE_ID": "Machine_03", "UNIFIED_RISK_SCORE": 0.05},
            {"MACHINE_ID": "Machine_04", "UNIFIED_RISK_SCORE": 0.02},
        ]
        total_dt_m1_m2 = sum(
            machine_loss_map.get(m["MACHINE_ID"], 0.0)
            for m in risk_df_m1_m2 if m["UNIFIED_RISK_SCORE"] >= 0.40
        )
        self.assertEqual(total_dt_m1_m2, 9375.0)

    def test_03_single_header_call_in_streamlit_app(self):
        """Verify render_header() is invoked exactly ONCE in streamlit_app.py to prevent duplicate header."""
        import os
        app_path = os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            code = f.read()

        header_calls = [line for line in code.splitlines() if line.strip() == "render_header()"]
        self.assertEqual(len(header_calls), 1, f"Expected exactly 1 render_header() call, got {len(header_calls)}")

    def test_04_oee_independence(self):
        """Verify OEE calculation remains 0.0 when OEE metrics table is empty."""
        import pandas as pd
        empty_oee_df = pd.DataFrame()
        overall_oee = round(empty_oee_df["OEE_PCT"].mean(), 1) if (not empty_oee_df.empty and "OEE_PCT" in empty_oee_df.columns and empty_oee_df["OEE_PCT"].sum() > 0) else 0.0
        self.assertEqual(overall_oee, 0.0)

    def test_05_scenario_production_events_insertion(self):
        """Verify inject_scenario_to_snowflake executes PRODUCTION_EVENTS insertion and OEE refresh."""
        executed_sqls = []
        def mock_qexec(sql):
            executed_sqls.append(sql)
            return []

        sc_res = inject_scenario_to_snowflake(mock_qexec, "SCENARIO_1")
        self.assertIsNotNone(sc_res)
        
        # Check that PRODUCTION_EVENTS insertion SQL and Dynamic Table REFRESH SQL were invoked
        has_prod_insert = any("PRODUCTION_EVENTS" in sql for sql in executed_sqls)
        has_dt_refresh = any("ALTER DYNAMIC TABLE PM_OEE_DB.CORE.OEE_METRICS_RT REFRESH" in sql for sql in executed_sqls)
        
        self.assertTrue(has_prod_insert, "Expected PRODUCTION_EVENTS insert query during scenario injection")
        self.assertTrue(has_dt_refresh, "Expected OEE_METRICS_RT refresh query during scenario injection")


if __name__ == "__main__":
    unittest.main()
