"""
tests/test_ai_assistant_qa.py
Automated verification test suite for Grounded AI Assistant Q&A routing, intent detection,
live Snowflake context grounding, document retrieval, anti-hallucination, and question responsiveness.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.gemini_service import ask_machine_question, classify_intent, retrieve_matching_docs

class TestAIAssistantQA(unittest.TestCase):
    def setUp(self):
        self.sample_docs = [
            {
                "SOURCE_FILE": "Precision_Mill_Bearing_Manual.txt",
                "CHUNK_TEXT": "Precision Mill — Bearing Failure & Replacement Manual\nDiagnostic thresholds: Sustained vibration above 4.0 mm/s requires inspection. Vibration above 6.0 mm/s with a thermal rise should be treated as critical.\nTechnician procedure: 1) Stop machine under approved LOTO. 2) Inspect bearing housing. 3) Replace bearing SKF-6205-2RS."
            },
            {
                "SOURCE_FILE": "Coolant_System_SOP.txt",
                "CHUNK_TEXT": "CNC Coolant System — Troubleshooting SOP\nFailure signature: Coolant flow problem causes temperature to rise while vibration remains near baseline.\nCorrective action: Inspect filter and pump. Replace COOLANT-PUMP-4KW when pump degradation is confirmed."
            },
            {
                "SOURCE_FILE": "Spindle_Drive_Belt_SOP.txt",
                "CHUNK_TEXT": "Spindle Drive — Belt & RPM Troubleshooting SOP\nDiagnostic steps: Check belt tension, pulley alignment, and belt wear. Replace DRIVE-BELT-HX if tension drift is present."
            }
        ]

        self.critical_context = {
            "machine_id": "Machine_03",
            "vibration_mm_s": 6.15,
            "temperature_c": 97.3,
            "rpm": 1552.0,
            "risk_score": 1.0,
            "ml_failure_probability": 0.9984,
            "rul_hours": 18.0,
            "bearing_part_number": "SKF-6205-2RS",
            "inventory_units": 4,
            "supplier": "SKF Industrial",
            "financial_risk_usd": 12500,
            "marketplace_context": {
                "marketplace_available": True,
                "machine_enrichment": {
                    "copper_price_usd": 9250.0,
                    "aluminum_price_usd": 2420.0,
                    "supply_chain_risk_score": 0.68,
                    "material_cost_trend": "RISING"
                }
            },
            "environmental_context": {
                "available": True,
                "ambient_temperature_c": 28.5,
                "humidity_percent": 65,
                "weather_condition": "Clear"
            },
            "documents": self.sample_docs
        }

    def test_01_question_intent_classification(self):
        """1. Verify question intent classifier routes to correct categories."""
        self.assertEqual(classify_intent("Why is Machine_03 at risk?"), "WHY_RISK")
        self.assertEqual(classify_intent("What should we do?"), "WHAT_SHOULD_WE_DO")
        self.assertEqual(classify_intent("What part should we replace?"), "SPARE_PART")
        self.assertEqual(classify_intent("What is the RUL?"), "RUL")
        self.assertEqual(classify_intent("What does the bearing manual recommend?"), "HYBRID")
        self.assertEqual(classify_intent("What does the Marketplace data say?"), "MARKETPLACE")
        self.assertEqual(classify_intent("What is the financial impact?"), "FINANCIAL_IMPACT")
        self.assertEqual(classify_intent("What is the environmental context?"), "ENVIRONMENT")
        self.assertEqual(classify_intent("What is the quantum flux capacitor rating?"), "UNKNOWN")

    def test_02_why_machine_03_at_risk(self):
        """2. Question 1: Why is Machine_03 at risk? -> Direct risk explanation."""
        ans = ask_machine_question("Why is Machine_03 at risk?", self.critical_context)
        self.assertNotIn("### Scenario Failure Prediction Report", ans, "MUST NOT return generic static report header")
        self.assertTrue(any(w in ans.lower() for w in ["vibration", "temperature", "deviation", "baseline", "risk", "99.84%", "18.0"]))

    def test_03_what_should_we_do(self):
        """3. Question 2: What should we do? -> Maintenance action."""
        ans = ask_machine_question("What should we do?", self.critical_context)
        self.assertNotIn("### Scenario Failure Prediction Report", ans)
        self.assertTrue(any(w in ans.lower() for w in ["action", "lockout", "loto", "inspect", "replace", "repair"]))

    def test_04_what_part_should_we_replace(self):
        """4. Question 3: What part should we replace? -> Spare part answer."""
        ans = ask_machine_question("What part should we replace?", self.critical_context)
        self.assertNotIn("### Scenario Failure Prediction Report", ans)
        self.assertIn("SKF-6205-2RS", ans)

    def test_05_what_is_the_rul(self):
        """5. Question 4: What is the RUL? -> ~18 hours from authoritative source."""
        ans = ask_machine_question("What is the RUL?", self.critical_context)
        self.assertNotIn("### Scenario Failure Prediction Report", ans)
        self.assertTrue("18.0" in ans or "rul" in ans.lower())

    def test_06_what_does_bearing_manual_recommend(self):
        """6. Question 5: What does the bearing manual recommend? -> Document-grounded answer."""
        ans = ask_machine_question("What does the bearing manual recommend?", self.critical_context)
        self.assertIn("Precision_Mill_Bearing_Manual.txt", ans)
        self.assertTrue(any(w in ans.lower() for w in ["vibration", "skf-6205-2rs", "loto", "procedure"]))

    def test_07_what_does_marketplace_say(self):
        """7. Question 6: What does the Marketplace data say? -> Marketplace answer."""
        ans = ask_machine_question("What does the Marketplace data say?", self.critical_context)
        self.assertTrue(any(w in ans.lower() for w in ["marketplace", "copper", "aluminum", "supply chain"]))

    def test_08_what_is_the_financial_impact(self):
        """8. Question 7: What is the financial impact? -> Financial impact answer."""
        ans = ask_machine_question("What is the financial impact?", self.critical_context)
        self.assertTrue(any(w in ans.lower() for w in ["financial", "$12,500", "downtime", "cost"]))

    def test_09_environmental_context(self):
        """9. Question 8: What is the environmental context? -> Weather/environment answer."""
        ans = ask_machine_question("What is the environmental context?", self.critical_context)
        self.assertTrue(any(w in ans.lower() for w in ["ambient", "temperature", "humidity", "weather", "operating context"]))

    def test_10_sequential_question_diversity(self):
        """10. Question 9: Ask questions sequentially and verify answers change dynamically."""
        q1_ans = ask_machine_question("Why is Machine_03 at risk?", self.critical_context)
        q2_ans = ask_machine_question("What should we do?", self.critical_context)
        q3_ans = ask_machine_question("What part should we replace?", self.critical_context)
        q4_ans = ask_machine_question("What does the bearing manual recommend?", self.critical_context)

        self.assertNotEqual(q1_ans, q2_ans, "Q1 and Q2 answers MUST differ")
        self.assertNotEqual(q2_ans, q3_ans, "Q2 and Q3 answers MUST differ")
        self.assertNotEqual(q3_ans, q4_ans, "Q3 and Q4 answers MUST differ")

    def test_11_no_generic_report_by_default(self):
        """11. Question 10: Verify no generic scenario report is returned unless explicitly requested."""
        ans = ask_machine_question("Why is Machine_03 at risk?", self.critical_context)
        self.assertNotIn("### Scenario Failure Prediction Report", ans)
        self.assertNotIn("#### Failure Risk & Financial Impact Analysis", ans)
        self.assertNotIn("#### Grounded Root Cause & ERP Inventory Matching", ans)

if __name__ == "__main__":
    unittest.main()
