"""
tests/test_marketplace_ui.py
Unit test suite verifying Marketplace UI business context interpretation generation,
data source separation, empty state handling, and Reset Everything compatibility.
"""

import unittest
from typing import Dict, Any

from services.marketplace_agent import (
    get_marketplace_config,
    generate_marketplace_business_interpretation
)
from services.scenario_service import reset_demo_snowflake_state


class TestMarketplaceUI(unittest.TestCase):

    def test_01_marketplace_config_metadata(self):
        """Verify get_marketplace_config returns expected listing metadata."""
        cfg = get_marketplace_config()
        self.assertIsNotNone(cfg)
        self.assertIn("database", cfg)
        self.assertEqual(cfg.get("database"), "SNOWFLAKE_PUBLIC_DATA_FREE")
        self.assertEqual(cfg.get("global_name"), "GZTSZ290BV255")

    def test_02_business_interpretation_available_stock(self):
        """Verify dynamic business interpretation when ERP stock is available."""
        enrich_rec = {
            "MACHINE_ID": "Machine_03",
            "PART_NUMBER": "SKF-6205-2RS",
            "ERP_SUPPLIER": "SKF Industrial",
            "INTERNAL_STOCK_QTY": 4,
            "COPPER_PRICE_USD": 9250.00,
            "NICKEL_PRICE_USD": 16450.00,
            "SUPPLY_CHAIN_RISK_SCORE": 0.40,
            "MATERIAL_COST_TREND": "STABLE"
        }
        interp = generate_marketplace_business_interpretation(enrich_rec, risk_score=0.9984)
        self.assertIn("SKF-6205-2RS", interp)
        self.assertIn("available in internal ERP inventory", interp)
        self.assertIn("STABLE", interp)
        self.assertIn("MODERATE", interp)
        self.assertIn("Maintenance can therefore proceed immediately", interp)

    def test_03_business_interpretation_out_of_stock(self):
        """Verify dynamic business interpretation when ERP stock is zero (out of stock)."""
        enrich_rec = {
            "MACHINE_ID": "Machine_02",
            "PART_NUMBER": "COOLANT-PUMP-4KW",
            "ERP_SUPPLIER": "Grundfos Industrial",
            "INTERNAL_STOCK_QTY": 0,
            "COPPER_PRICE_USD": 9250.00,
            "NICKEL_PRICE_USD": 16450.00,
            "SUPPLY_CHAIN_RISK_SCORE": 0.75,
            "MATERIAL_COST_TREND": "RISING"
        }
        interp = generate_marketplace_business_interpretation(enrich_rec, risk_score=0.85)
        self.assertIn("OUT OF STOCK", interp)
        self.assertIn("RISING", interp)
        self.assertIn("ELEVATED", interp)
        self.assertIn("Procurement must immediately be initiated", interp)

    def test_04_business_interpretation_empty_state(self):
        """Verify fallback when enrichment record is missing or None."""
        interp = generate_marketplace_business_interpretation(None)
        self.assertIn("Marketplace context unavailable", interp)
        self.assertIn("Maintenance predictions continue", interp)

    def test_05_grounded_document_missing_phrase(self):
        """Verify grounded assistant returns standard grounding missing phrase when docs fail."""
        from services.gemini_service import _question_responsive_fallback
        res = _question_responsive_fallback("What does the bearing manual say?", "DOCUMENT_SOP", {}, [])
        self.assertEqual(res, "The retrieved maintenance documents do not provide sufficient information to answer this.")


if __name__ == "__main__":
    unittest.main()
