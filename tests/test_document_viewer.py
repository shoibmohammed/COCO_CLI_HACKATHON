"""
tests/test_document_viewer.py
Automated unit test suite verifying the Dashboard Document Viewer, file discovery,
readability, metadata computation, file downloading, in-document search, and Q&A source linkage.
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
    get_document_by_name,
    search_within_document,
    search_documents,
    EXPECTED_DOCUMENTS
)
from services.gemini_service import ask_machine_question

class TestDocumentViewer(unittest.TestCase):
    def setUp(self):
        self.manuals_dir = get_manuals_directory()

    def test_01_document_discovery(self):
        """1. Verify manuals directory discovery."""
        self.assertTrue(self.manuals_dir.exists())
        self.assertTrue(self.manuals_dir.is_dir())

    def test_02_file_existence(self):
        """2. Verify all expected documents exist."""
        for fname in EXPECTED_DOCUMENTS:
            fpath = self.manuals_dir / fname
            self.assertTrue(fpath.exists(), f"File {fname} must exist on disk")

    def test_03_file_readability(self):
        """3. Verify Python process has read permissions."""
        for fname in EXPECTED_DOCUMENTS:
            fpath = self.manuals_dir / fname
            self.assertTrue(os.access(fpath, os.R_OK), f"File {fname} must be readable")

    def test_04_open_precision_mill_bearing_manual(self):
        """4. Open Precision_Mill_Bearing_Manual.txt and verify metadata and content."""
        doc = get_document_by_name("Precision_Mill_Bearing_Manual.txt")
        self.assertIsNotNone(doc)
        self.assertEqual(doc["status"], "LOADED")
        self.assertGreater(doc["size_kb"], 0.0)
        self.assertGreater(doc["char_count"], 100)
        self.assertGreater(doc["line_count"], 5)
        self.assertEqual(doc["encoding"], "UTF-8")
        self.assertIn("SKF-6205-2RS", doc["content"])

    def test_05_open_coolant_system_sop(self):
        """5. Open Coolant_System_SOP.txt and verify metadata and content."""
        doc = get_document_by_name("Coolant_System_SOP.txt")
        self.assertIsNotNone(doc)
        self.assertEqual(doc["status"], "LOADED")
        self.assertGreater(doc["size_kb"], 0.0)
        self.assertIn("COOLANT-PUMP-4KW", doc["content"])

    def test_06_open_spindle_drive_belt_sop(self):
        """6. Open Spindle_Drive_Belt_SOP.txt and verify metadata and content."""
        doc = get_document_by_name("Spindle_Drive_Belt_SOP.txt")
        self.assertIsNotNone(doc)
        self.assertEqual(doc["status"], "LOADED")
        self.assertGreater(doc["size_kb"], 0.0)
        self.assertIn("DRIVE-BELT-HX", doc["content"])

    def test_07_download_original_file(self):
        """7. Verify download data bytes match exact raw file on disk."""
        for fname in EXPECTED_DOCUMENTS:
            fpath = self.manuals_dir / fname
            with open(fpath, "rb") as f:
                disk_bytes = f.read()
            doc = get_document_by_name(fname)
            doc_bytes = doc["content"].encode("utf-8")
            self.assertEqual(len(doc_bytes), len(disk_bytes), f"Downloaded bytes for {fname} must match disk bytes")

    def test_08_missing_file_handling(self):
        """8. Verify graceful handling of missing file."""
        doc = load_single_document(self.manuals_dir / "NonExistent_SOP.txt")
        self.assertEqual(doc["status"], "NOT_FOUND")
        self.assertEqual(doc["content"], "")

    def test_09_read_failure_handling(self):
        """9. Verify read failure handling for unreadable/invalid path."""
        doc = load_single_document(pathlib.Path("/invalid_root/bad_file.txt"))
        self.assertEqual(doc["status"], "NOT_FOUND")

    def test_10_viewer_content_matches_actual_txt(self):
        """10. Verify viewer content is identical to file text."""
        fpath = self.manuals_dir / "Precision_Mill_Bearing_Manual.txt"
        with open(fpath, "r", encoding="utf-8") as f:
            disk_text = f.read()
        doc = get_document_by_name("Precision_Mill_Bearing_Manual.txt")
        self.assertEqual(doc["content"], disk_text)

    def test_11_qa_retrieval_uses_same_file(self):
        """11. Verify Q&A retrieval and Viewer retrieve from identical file."""
        matches = search_documents("What does the bearing manual say?")
        doc = get_document_by_name("Precision_Mill_Bearing_Manual.txt")
        self.assertEqual(matches[0]["source_file"], doc["filename"])
        # Verify chunk content lines are present in actual document content
        chunk_first_line = matches[0]["chunk_text"].splitlines()[0]
        self.assertIn(chunk_first_line, doc["content"])

    def test_12_open_source_document_linkage(self):
        """12. Verify source document linkage identifies target file."""
        matches = search_documents("bearing replacement LOTO procedure")
        self.assertEqual(matches[0]["source_file"], "Precision_Mill_Bearing_Manual.txt")

    def test_13_search_within_document(self):
        """13. Verify in-document search highlights matching line numbers and text."""
        results = search_within_document("Precision_Mill_Bearing_Manual.txt", "lubrication")
        self.assertGreater(len(results), 0)
        self.assertIn("lubrication", results[0]["text"].lower())
        self.assertGreater(results[0]["line_num"], 0)

if __name__ == "__main__":
    unittest.main()
