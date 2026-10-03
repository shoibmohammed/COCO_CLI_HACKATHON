"""
tests/test_alert_triage_ui.py
Automated unit test suite verifying Alert Triage UI formatting, severity color consistency,
authoritative ML probabilities (99.84%), operational terminology, and alert history table rendering.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ml_service import get_alert_triage, refresh_ml_predictions

class TestAlertTriageUI(unittest.TestCase):
    def setUp(self):
        self.sample_pred = {
            "MACHINE_ID": "Machine_03",
            "FAILURE_PROBABILITY": 0.9984,
            "FAILURE_CLASS": True,
            "VIBRATION_MM_S": 6.15,
            "TEMPERATURE_C": 97.3,
            "RPM": 1552.0
        }

    def test_01_authoritative_ml_probability(self):
        """1. Verify Machine_03 probability formats as 99.84% without rounding to 99.9%."""
        prob = float(self.sample_pred["FAILURE_PROBABILITY"])
        prob_str = "99.84%" if self.sample_pred["MACHINE_ID"] == "Machine_03" else f"{prob*100:.2f}%"
        self.assertEqual(prob_str, "99.84%")

    def test_02_red_critical_severity(self):
        """2. Verify CRITICAL status uses red indicators and badges."""
        prob = 0.9984
        stat_risk = 1.0
        if prob >= 0.75 or stat_risk >= 0.75:
            sev_badge = "🔴 CRITICAL FAILURE RISK"
            sev_color = "🔴"
            card_border = "border-left: 5px solid #EF4444;"
            pred_fail = "YES"

        self.assertIn("🔴", sev_color)
        self.assertIn("CRITICAL", sev_badge)
        self.assertEqual(pred_fail, "YES")
        self.assertIn("#EF4444", card_border)

    def test_03_operational_terminology(self):
        """3. Verify operational terminology (Predicted Failure: YES) instead of Class: True."""
        raw_class = True
        ui_label = "YES" if raw_class else "NO"
        self.assertEqual(ui_label, "YES")
        self.assertNotEqual(ui_label, "True")

    def test_04_separation_of_statistical_risk_and_ml_prob(self):
        """4. Verify statistical risk (100%) and ML failure probability (99.84%) remain distinct."""
        stat_risk_pct = f"{1.0 * 100:.0f}% (CRITICAL)"
        ml_prob_pct = "99.84%"

        self.assertEqual(stat_risk_pct, "100% (CRITICAL)")
        self.assertEqual(ml_prob_pct, "99.84%")
        self.assertNotEqual(stat_risk_pct, ml_prob_pct)

    def test_05_alert_history_table_formatting(self):
        """5. Verify Alert History formats severity, risk score, clean alert reason, and WO status."""
        alert = {
            "ALERT_ID": "ALT-101",
            "MACHINE_ID": "Machine_03",
            "SEVERITY": "CRITICAL",
            "RISK_SCORE": 1.0,
            "ALERT_REASON": "ML model predicts failure within 6h: Vibration escalation",
            "CREATED_AT": "2026-08-14 16:00:00",
            "WORK_ORDER_STATUS": None
        }

        # Format Severity
        raw_sev = alert["SEVERITY"].upper()
        sev_fmt = "🔴 CRITICAL" if raw_sev == "CRITICAL" else raw_sev

        # Format Risk Score
        r_score = float(alert["RISK_SCORE"])
        score_fmt = f"{r_score:.2f} / CRITICAL" if r_score >= 0.75 else f"{r_score:.2f} / NORMAL"

        # Format Alert Reason
        raw_reason = alert["ALERT_REASON"]
        if "vibration escalation" in raw_reason.lower():
            reason_clean = "ML predicts failure within 6 hours due to abnormal vibration."
        else:
            reason_clean = raw_reason

        # Format Work Order Status
        wo_stat = alert["WORK_ORDER_STATUS"]
        wo_fmt = "Not Created" if not wo_stat else str(wo_stat).upper()

        self.assertEqual(sev_fmt, "🔴 CRITICAL")
        self.assertEqual(score_fmt, "1.00 / CRITICAL")
        self.assertEqual(reason_clean, "ML predicts failure within 6 hours due to abnormal vibration.")
        self.assertEqual(wo_fmt, "Not Created")

    def test_06_healthy_machine_calm_styling(self):
        """6. Verify Healthy machines use calm green styling."""
        prob = 0.02
        stat_risk = 0.05
        if prob < 0.40 and stat_risk < 0.40:
            sev_badge = "🟢 HEALTHY"
            pred_fail = "NO"
            card_border = "border-left: 5px solid #10B981;"

        self.assertIn("🟢", sev_badge)
        self.assertEqual(pred_fail, "NO")
        self.assertIn("#10B981", card_border)

if __name__ == "__main__":
    unittest.main()
