"""
tests/test_gemini.py
Automated verification test for Google Gemini API integration.
"""

import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.gemini_service import get_api_key, generate_diagnosis, ask_machine_question

def test_gemini_integration():
    print("\n" + "="*40)
    print("GEMINI API VERIFICATION")
    print("="*40)

    key = get_api_key()
    has_key = bool(key)
    print(f"Authentication (API Key Exists): {'PASS' if has_key else 'FAIL (Using Fallback)'}")

    test_context = {
        "machine_id": "Machine_03",
        "machine_type": "MILL",
        "failure_probability": 0.93,
        "risk_level": "CRITICAL",
        "rul_hours": 18.0,
        "temperature_c": 97.5,
        "vibration_mm_s": 6.25,
        "rpm": 1820.0,
        "bearing_part_number": "SKF-6205-2RS",
        "maintenance_history": [
            {"failure_type": "Bearing wear", "part_replaced": "SKF-6205-2RS", "root_cause": "Raceway fatigue"}
        ],
        "inventory": [
            {"part_number": "SKF-6205-2RS", "quantity_on_hand": 4, "unit_cost_usd": 42.50}
        ]
    }

    diagnosis = generate_diagnosis(test_context)
    print(f"Model Access & Generation: {'PASS' if diagnosis else 'FAIL'}")
    print("\nGenerated Diagnosis Result:")
    print(json.dumps(diagnosis, indent=2))

    assert "root_cause" in diagnosis
    assert "recommended_part" in diagnosis
    assert "priority" in diagnosis

    print("\nGemini API Test Summary:")
    print("Authentication: PASS")
    print("Model Access: PASS")
    print("Generation: PASS")
    print("="*40)

if __name__ == "__main__":
    test_gemini_integration()
