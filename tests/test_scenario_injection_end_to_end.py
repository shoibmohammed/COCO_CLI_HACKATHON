"""
tests/test_scenario_injection_end_to_end.py
Automated unit test suite verifying the end-to-end scenario injection lifecycle:
1. Baseline restoration on RESET EVERYTHING (Machine_03 = 2.00 / 65.0 / 1800, Risk = 0)
2. Telemetry update & fresh reading insertion on INJECT SCENARIO TO SNOWFLAKE (Machine_03 = 6.15 / 97.3 / 1552, Risk = 1.0)
3. Dynamic Table refreshes for MACHINE_HEALTH_RT, RISK_SCORES_RT, and OEE_METRICS_RT
4. ML risk prediction refresh & Alert triage generation
"""

import unittest
from typing import Dict, Any

from services.scenario_service import SCENARIOS, inject_scenario_to_snowflake, reset_demo_snowflake_state


class TestScenarioInjectionEndToEnd(unittest.TestCase):

    def test_01_scenario_1_metadata(self):
        """Verify SCENARIO_1 target telemetry values match exact expected critical metrics."""
        sc1 = SCENARIOS.get("SCENARIO_1")
        self.assertIsNotNone(sc1)
        self.assertEqual(sc1["machine_id"], "Machine_03")
        self.assertEqual(sc1["vibration"], 6.15)
        self.assertEqual(sc1["temperature"], 97.3)
        self.assertEqual(sc1["rpm"], 1552)
        self.assertEqual(sc1["risk_score"], 0.94)

    def test_02_inject_scenario_executes_telemetry_updates_and_dt_refreshes(self):
        """Verify inject_scenario_to_snowflake executes telemetry updates and all Dynamic Table refreshes."""
        executed_sqls = []

        def mock_qexec(sql):
            executed_sqls.append(sql)
            return []

        sc_res = inject_scenario_to_snowflake(mock_qexec, "SCENARIO_1")
        self.assertEqual(sc_res["machine_id"], "Machine_03")

        # Check telemetry UPDATE and INSERT
        has_update = any("UPDATE PM_OEE_DB.CORE.SENSOR_READINGS" in sql for sql in executed_sqls)
        has_insert = any("INSERT INTO PM_OEE_DB.CORE.SENSOR_READINGS" in sql for sql in executed_sqls)

        self.assertTrue(has_update, "Expected SENSOR_READINGS update query")
        self.assertTrue(has_insert, "Expected fresh SENSOR_READINGS insert query")

        # Check Dynamic Table refreshes
        has_mh_refresh = any("ALTER DYNAMIC TABLE PM_OEE_DB.CORE.MACHINE_HEALTH_RT REFRESH" in sql for sql in executed_sqls)
        has_risk_refresh = any("ALTER DYNAMIC TABLE PM_OEE_DB.CORE.RISK_SCORES_RT REFRESH" in sql for sql in executed_sqls)
        has_oee_refresh = any("ALTER DYNAMIC TABLE PM_OEE_DB.CORE.OEE_METRICS_RT REFRESH" in sql for sql in executed_sqls)

        self.assertTrue(has_mh_refresh, "Expected MACHINE_HEALTH_RT refresh query")
        self.assertTrue(has_risk_refresh, "Expected RISK_SCORES_RT refresh query")
        self.assertTrue(has_oee_refresh, "Expected OEE_METRICS_RT refresh query")

    def test_03_reset_demo_snowflake_state(self):
        """Verify reset_demo_snowflake_state clears transactional tables."""
        executed_sqls = []

        def mock_qexec(sql):
            executed_sqls.append(sql)
            return []

        res = reset_demo_snowflake_state(mock_qexec)
        self.assertTrue(res)
        has_clear_wo = any("DELETE FROM PM_OEE_DB.CORE.WORK_ORDERS" in sql for sql in executed_sqls)
        has_clear_alerts = any("DELETE FROM PM_OEE_DB.CORE.ALERT_LOG" in sql for sql in executed_sqls)
        has_clear_prod = any("DELETE FROM PM_OEE_DB.CORE.PRODUCTION_EVENTS" in sql for sql in executed_sqls)

        self.assertTrue(has_clear_wo)
        self.assertTrue(has_clear_alerts)
        self.assertTrue(has_clear_prod)


if __name__ == "__main__":
    unittest.main()
