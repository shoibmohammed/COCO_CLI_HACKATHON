"""
tests/test_scenarios.py
Automated test suite verifying Snowflake scenario injection and demo reset logic.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.scenario_service import SCENARIOS, inject_scenario_to_snowflake, reset_demo_snowflake_state

def mock_qexec(sql):
    print(f"[SQL EXEC] {sql.strip()[:100]}...")
    return []

def test_scenarios():
    print("Testing scenario injection logic...")
    for sc_key in SCENARIOS:
        sc = inject_scenario_to_snowflake(mock_qexec, sc_key)
        assert sc["id"] == sc_key
        print(f"  [PASS] Injected {sc_key}: {sc['title']}")

    print("\nTesting demo state reset logic...")
    res = reset_demo_snowflake_state(mock_qexec)
    assert res is True or (isinstance(res, dict) and res.get("success") is True)
    print("  [PASS] Demo state reset successful!")
    print("\nALL SCENARIO TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_scenarios()
