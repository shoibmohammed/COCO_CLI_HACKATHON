"""
tests/test_jira_ui_ux.py
Tests for the Jira UI/UX redesign — governed human-in-the-loop flow.
"""

import os
import sys
import ast
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

STREAMLIT_PATH = os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py")


def read_streamlit():
    content = ""
    for path in [
        os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py"),
        os.path.join(os.path.dirname(__file__), "..", "pages", "work_orders.py"),
        os.path.join(os.path.dirname(__file__), "..", "pages", "machine_intelligence.py"),
    ]:
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                content += "\n" + f.read()
    return content


class TestPendingApproval(unittest.TestCase):
    """1-2. PENDING_APPROVAL → no Jira button, approve button visible."""

    def test_01_no_jira_button_before_approval(self):
        """PENDING_APPROVAL section does not render CREATE JIRA TICKET."""
        content = read_streamlit()
        # Find the PENDING APPROVAL section
        idx = content.find("PENDING APPROVAL")
        next_section = content.find("JIRA INTEGRATION", idx)
        between = content[idx:next_section] if next_section > idx else ""
        self.assertNotIn("CREATE JIRA TICKET", between)

    def test_02_approve_button_visible(self):
        content = read_streamlit()
        self.assertIn("APPROVE WORK ORDER", content)


class TestApproved(unittest.TestCase):
    """3-4. APPROVED → manager approved state, Jira section available."""

    def test_03_manager_approved_visible(self):
        content = read_streamlit()
        self.assertIn("Manager Approved", content)

    def test_04_jira_integration_section_exists(self):
        content = read_streamlit()
        self.assertIn("🎫 JIRA INTEGRATION", content)


class TestWorkerGuards(unittest.TestCase):
    """6-8. Worker offline/unavailable → create disabled."""

    def test_06_create_button_exists(self):
        content = read_streamlit()
        self.assertIn("CREATE JIRA TICKET", content)

    def test_07_worker_offline_disables(self):
        content = read_streamlit()
        self.assertIn("disabled=True", content)

    def test_08_worker_offline_message(self):
        content = read_streamlit()
        self.assertIn("Jira Worker offline", content)


class TestJiraStates(unittest.TestCase):
    """14-19. Jira queue states displayed correctly."""

    def test_14_pending_ui(self):
        content = read_streamlit()
        self.assertIn("JIRA REQUEST SUBMITTED", content)

    def test_15_processing_ui(self):
        content = read_streamlit()
        self.assertIn("JIRA TICKET PROCESSING", content)

    def test_16_success_ui(self):
        content = read_streamlit()
        self.assertIn("JIRA TICKET CREATED", content)

    def test_17_open_jira_button(self):
        content = read_streamlit()
        self.assertIn("OPEN JIRA", content)

    def test_18_no_broken_link(self):
        """Open Jira only shown when diag_jira_url exists."""
        content = read_streamlit()
        self.assertIn("if diag_jira_url:", content)

    def test_19_failed_retry(self):
        content = read_streamlit()
        self.assertIn("RETRY JIRA TICKET", content)


class TestNoDirectJira(unittest.TestCase):
    """13, 24, 25. No direct Jira HTTP, no hardcoded URL, no credentials."""

    def test_13_no_requests_post(self):
        content = read_streamlit()
        self.assertNotIn("requests.post", content)
        self.assertNotIn("requests.get", content)

    def test_24_no_hardcoded_jira_url(self):
        content = read_streamlit()
        self.assertNotIn("sidsn7-1786720131938", content)
        self.assertNotIn("atlassian.net", content)

    def test_25_no_jira_credentials(self):
        content = read_streamlit()
        self.assertNotIn("JIRA_API_TOKEN", content)
        self.assertNotIn("jira_api_token", content)


class TestApprovalSeparation(unittest.TestCase):
    """22-23. Multiple WOs, approval message not shown as error."""

    def test_22_section_separation(self):
        """Approval and Jira integration are in separate sections."""
        content = read_streamlit()
        approval_idx = content.find("SECTION 1: WORK ORDER APPROVAL")
        jira_idx = content.find("SECTION 2: JIRA INTEGRATION")
        self.assertGreater(jira_idx, approval_idx)

    def test_23_approval_not_error(self):
        """PENDING_APPROVAL shows as governance state, not error."""
        content = read_streamlit()
        # Should not show "blocked" or red error for normal pending state
        pending_section = content[content.find("PENDING APPROVAL"):content.find("PENDING APPROVAL") + 300]
        self.assertNotIn("🔴", pending_section)


class TestSyntax(unittest.TestCase):
    """Regression: file parses."""

    def test_syntax(self):
        content = read_streamlit()
        ast.parse(content)


if __name__ == "__main__":
    unittest.main()
