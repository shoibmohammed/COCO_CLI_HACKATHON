"""
tests/test_document_retrieval.py
Automated test suite for local maintenance document discovery, file loading, encoding,
chunking, TF-IDF/keyword relevance search, and Gemini document grounding context.
"""

import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.document_service import (
    get_manuals_directory,
    load_single_document,
    load_all_documents,
    search_documents,
    get_relevant_document_context,
    EXPECTED_DOCUMENTS
)
from services.gemini_service import ask_machine_question

class TestDocumentRetrieval(unittest.TestCase):
    def setUp(self):
        self.manuals_dir = get_manuals_directory()

    def test_01_file_discovery(self):
        """1. Verify manuals directory discovery."""
        self.assertTrue(self.manuals_dir.exists(), "Manuals directory must exist")
        self.assertTrue(self.manuals_dir.is_dir(), "Manuals path must be a directory")

    def test_02_file_existence(self):
        """2. Verify expected document files exist on disk."""
        for filename in EXPECTED_DOCUMENTS:
            file_path = self.manuals_dir / filename
            self.assertTrue(file_path.exists(), f"Document {filename} must exist on disk at {file_path}")

    def test_03_file_readability(self):
        """3. Verify Python process has read permissions on all files."""
        for filename in EXPECTED_DOCUMENTS:
            file_path = self.manuals_dir / filename
            self.assertTrue(os.access(file_path, os.R_OK), f"Document {filename} must be readable by Python")

    def test_04_utf8_encoding_handling(self):
        """4. Verify UTF-8 reading and text decoding without errors."""
        for filename in EXPECTED_DOCUMENTS:
            file_path = self.manuals_dir / filename
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertGreater(len(content), 50, f"Document {filename} must contain text content")

    def test_05_document_loading(self):
        """5. Verify load_all_documents returns LOADED status for all 3 manuals."""
        docs = load_all_documents()
        self.assertEqual(len(docs), 3)
        for d in docs:
            self.assertEqual(d["status"], "LOADED", f"Document {d['filename']} must have LOADED status")
            self.assertGreater(d["size_bytes"], 0)
            self.assertGreater(d["size_kb"], 0.0)

    def test_06_chunk_creation(self):
        """6. Verify document paragraphs are split into structured chunks."""
        docs = load_all_documents()
        for d in docs:
            self.assertGreater(len(d["chunks"]), 0, f"Document {d['filename']} must contain at least 1 chunk")
            for chunk in d["chunks"]:
                self.assertIn("source_file", chunk)
                self.assertIn("chunk_text", chunk if "chunk_text" in chunk else chunk)

    def test_07_query_retrieval(self):
        """7. Verify search_documents ranks relevant chunks."""
        matches = search_documents("vibration 6.0 mm/s thermal rise")
        self.assertGreater(len(matches), 0)
        self.assertIn("Precision_Mill_Bearing_Manual.txt", [m["source_file"] for m in matches])

    def test_08_bearing_manual_retrieval(self):
        """8. Verify queries about bearing manual retrieve Precision_Mill_Bearing_Manual.txt."""
        matches = search_documents("What does the bearing manual say about vibration thresholds?")
        self.assertGreater(len(matches), 0)
        self.assertEqual(matches[0]["source_file"], "Precision_Mill_Bearing_Manual.txt")
        self.assertIn("vibration", matches[0]["chunk_text"].lower())

    def test_09_coolant_sop_retrieval(self):
        """9. Verify queries about coolant SOP retrieve Coolant_System_SOP.txt."""
        matches = search_documents("What does the coolant SOP say about pump pressure?")
        self.assertGreater(len(matches), 0)
        self.assertEqual(matches[0]["source_file"], "Coolant_System_SOP.txt")
        self.assertIn("coolant", matches[0]["chunk_text"].lower())

    def test_10_spindle_belt_sop_retrieval(self):
        """10. Verify queries about spindle drive belt retrieve Spindle_Drive_Belt_SOP.txt."""
        matches = search_documents("What does the spindle drive belt SOP say about tension drift?")
        self.assertGreater(len(matches), 0)
        self.assertEqual(matches[0]["source_file"], "Spindle_Drive_Belt_SOP.txt")
        self.assertIn("belt", matches[0]["chunk_text"].lower())

    def test_11_missing_document_handling(self):
        """11. Verify graceful error handling when loading non-existent document."""
        dummy_path = self.manuals_dir / "NonExistent_Manual.txt"
        res = load_single_document(dummy_path)
        self.assertEqual(res["status"], "NOT_FOUND")
        self.assertEqual(res["chunks"], [])

    def test_12_empty_query_handling(self):
        """12. Verify empty query returns empty list without exception."""
        matches = search_documents("")
        self.assertEqual(matches, [])

    def test_13_gemini_context_receives_actual_text(self):
        """13. Verify get_relevant_document_context returns actual file text."""
        ctx_str = get_relevant_document_context("bearing replacement procedure LOTO")
        self.assertIn("Precision_Mill_Bearing_Manual.txt", ctx_str)
        self.assertIn("lockout/tagout", ctx_str.lower())
        self.assertIn("SKF-6205-2RS", ctx_str)

    def test_14_source_filename_returned_correctly(self):
        """14. Verify source filename is present in Q&A response."""
        context = {
            "machine_id": "Machine_03",
            "vibration_mm_s": 6.15,
            "temperature_c": 97.3,
            "rpm": 1552.0,
            "risk_score": 1.0,
            "ml_failure_probability": 0.9984,
            "rul_hours": 18.0,
            "bearing_part_number": "SKF-6205-2RS",
            "inventory_units": 4,
            "documents": load_all_documents()
        }
        ans = ask_machine_question("What does the bearing manual say?", context)
        self.assertIn("Precision_Mill_Bearing_Manual.txt", ans)

if __name__ == "__main__":
    unittest.main()
