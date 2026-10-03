"""
tests/test_suggested_questions.py
Automated unit test suite verifying suggested technician question button routing,
Streamlit session state management, input updating, stale answer clearing, and Q&A execution.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.document_service import load_all_documents, search_documents
from services.gemini_service import ask_machine_question, classify_intent

class TestSuggestedQuestions(unittest.TestCase):
    def setUp(self):
        self.session_state = {}
        self.sample_context = {
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
            "documents": load_all_documents()
        }

    def set_suggested_question(self, q_text):
        """Simulates clicking a suggested question button."""
        self.session_state["qa_input"] = q_text
        self.session_state["qa_trigger"] = True
        self.session_state.pop("qa_current_ans", None)
        self.session_state.pop("qa_last_q", None)

    def execute_qa_flow(self):
        """Simulates Streamlit execution flow."""
        should_run = self.session_state.get("qa_trigger", False)
        if should_run:
            self.session_state["qa_trigger"] = False
            active_q = self.session_state.get("qa_input", "").strip()
            if active_q:
                self.session_state.pop("qa_current_ans", None)
                ans = ask_machine_question(active_q, self.sample_context)
                self.session_state["qa_current_ans"] = ans
                self.session_state["qa_last_q"] = active_q
                return ans
        return self.session_state.get("qa_current_ans", None)

    def test_01_suggested_why_machine_03_at_risk(self):
        """1. Click 'Why is Machine_03 at risk?' -> input updated, QA executed, answer generated."""
        self.set_suggested_question("Why is Machine_03 at risk?")
        self.assertEqual(self.session_state["qa_input"], "Why is Machine_03 at risk?")
        ans = self.execute_qa_flow()
        self.assertIsNotNone(ans)
        self.assertTrue(any(w in ans.lower() for w in ["risk", "vibration", "99.84%", "temperature"]))

    def test_02_suggested_what_should_we_do(self):
        """2. Click 'What should we do?' -> different action-focused answer generated."""
        self.set_suggested_question("What should we do?")
        self.assertEqual(self.session_state["qa_input"], "What should we do?")
        ans = self.execute_qa_flow()
        self.assertIsNotNone(ans)
        self.assertTrue(any(w in ans.lower() for w in ["loto", "lockout", "inspect", "intervention"]))

    def test_03_suggested_what_part_should_we_replace(self):
        """3. Click 'What part should we replace?' -> part-focused answer generated."""
        self.set_suggested_question("What part should we replace?")
        ans = self.execute_qa_flow()
        self.assertIsNotNone(ans)
        self.assertIn("SKF-6205-2RS", ans)

    def test_04_suggested_bearing_manual_say(self):
        """4. Click 'What does the bearing manual say?' -> actual document retrieval + answer."""
        self.set_suggested_question("What does the bearing manual say?")
        ans = self.execute_qa_flow()
        self.assertIsNotNone(ans)
        self.assertIn("Precision_Mill_Bearing_Manual.txt", ans)

    def test_05_manual_question_path(self):
        """5. Enter a manual question and trigger execution -> manual path still works."""
        self.session_state["qa_input"] = "What does the coolant SOP say?"
        self.session_state["qa_trigger"] = True
        ans = self.execute_qa_flow()
        self.assertIsNotNone(ans)
        self.assertIn("Coolant_System_SOP.txt", ans)

    def test_06_sequential_question_replacement(self):
        """6. Click one suggested question, then another -> second answer replaces first."""
        self.set_suggested_question("Why is Machine_03 at risk?")
        ans1 = self.execute_qa_flow()

        self.set_suggested_question("What should we do?")
        ans2 = self.execute_qa_flow()

        self.assertNotEqual(ans1, ans2, "Second suggested question must generate a new answer")

    def test_07_prevent_stale_answers(self):
        """7. Verify previous answer is not incorrectly reused when switching questions."""
        self.set_suggested_question("Why is Machine_03 at risk?")
        self.execute_qa_flow()

        # Switch question
        self.set_suggested_question("What does the bearing manual say?")
        # Prior to execution, qa_current_ans must be cleared
        self.assertNotIn("qa_current_ans", self.session_state, "Previous answer must be cleared upon click")

        ans2 = self.execute_qa_flow()
        self.assertEqual(self.session_state["qa_last_q"], "What does the bearing manual say?")
        self.assertIn("Precision_Mill_Bearing_Manual.txt", ans2)

if __name__ == "__main__":
    unittest.main()
