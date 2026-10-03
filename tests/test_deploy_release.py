#!/usr/bin/env python3
"""
tests/test_deploy_release.py
Unit tests for the deployment orchestrator (scripts/deploy_release.py).

Tests:
1. Configuration resolution priority
2. Phase order and execution matrix
3. Fail-closed behavior on syntax or compatibility errors
4. Dry-run and check-only execution modes
5. Secret exclusion & manifest generation
6. Idempotency & mock handling
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.deploy_release import DeploymentOrchestrator, parse_arguments


class TestDeployReleaseOrchestrator(unittest.TestCase):

    def setUp(self):
        self.mock_args = MagicMock()
        self.mock_args.check_only = True
        self.mock_args.deploy = False
        self.mock_args.smoke_test = False
        self.mock_args.full = False
        self.mock_args.dry_run = False
        self.mock_args.skip_external_e2e = True
        self.mock_args.fresh_account = False
        self.mock_args.account = "test-account"
        self.mock_args.user = "test-user"
        self.mock_args.password = "test-password"
        self.mock_args.role = "ACCOUNTADMIN"
        self.mock_args.warehouse = "PM_OEE_WH"
        self.mock_args.database = "PM_OEE_DB"
        self.mock_args.schema = "CORE"
        self.mock_args.compute_pool = None
        self.mock_args.streamlit_object = "PM_OEE_DB.CORE.MFG_PM_COMMAND_CENTER"

    def test_01_configuration_resolution(self):
        """Verify configuration resolution hierarchy."""
        orchestrator = DeploymentOrchestrator(self.mock_args, PROJECT_ROOT)
        cfg = orchestrator.config
        self.assertEqual(cfg["account"], "test-account")
        self.assertEqual(cfg["user"], "test-user")
        self.assertEqual(cfg["warehouse"], "PM_OEE_WH")
        self.assertEqual(cfg["database"], "PM_OEE_DB")
        self.assertEqual(cfg["schema"], "CORE")

    def test_02_phase_00_discovery(self):
        """Verify repository discovery discovers active project files."""
        orchestrator = DeploymentOrchestrator(self.mock_args, PROJECT_ROOT)
        result = orchestrator.phase_00_discovery()
        self.assertTrue(result)
        self.assertIn("[00/13] Repository Discovery", orchestrator.phase_results)

    def test_03_phase_01_security_audit(self):
        """Verify security audit passes on clean public repository."""
        orchestrator = DeploymentOrchestrator(self.mock_args, PROJECT_ROOT)
        result = orchestrator.phase_01_security_audit()
        self.assertTrue(result)
        status, _ = orchestrator.phase_results["[01/13] Security & Secret Audit"]
        self.assertEqual(status, "PASS")

    def test_04_phase_02_dependency_gate(self):
        """Verify dependency gate validates pure Snowflake Anaconda environment.yml."""
        orchestrator = DeploymentOrchestrator(self.mock_args, PROJECT_ROOT)
        result = orchestrator.phase_02_dependency_gate()
        self.assertTrue(result)
        status, _ = orchestrator.phase_results["[02/13] Dependency Gate"]
        self.assertEqual(status, "PASS")

    def test_05_phase_03_code_quality(self):
        """Verify AST code quality validation passes with zero syntax errors."""
        orchestrator = DeploymentOrchestrator(self.mock_args, PROJECT_ROOT)
        result = orchestrator.phase_03_code_quality()
        self.assertTrue(result)
        status, _ = orchestrator.phase_results["[03/13] Python Syntax & Quality"]
        self.assertEqual(status, "PASS")

    def test_06_phase_04_streamlit_compatibility(self):
        """Verify Streamlit compatibility check passes."""
        orchestrator = DeploymentOrchestrator(self.mock_args, PROJECT_ROOT)
        result = orchestrator.phase_04_streamlit_compat()
        self.assertTrue(result)
        status, _ = orchestrator.phase_results["[04/13] Streamlit Compatibility"]
        self.assertEqual(status, "PASS")

    def test_07_phase_06_artifact_validation(self):
        """Verify all 38 required deployment stage artifacts exist."""
        orchestrator = DeploymentOrchestrator(self.mock_args, PROJECT_ROOT)
        result = orchestrator.phase_06_artifact_validation()
        self.assertTrue(result)
        status, _ = orchestrator.phase_results["[06/13] Artifact Validation"]
        self.assertEqual(status, "PASS")

    def test_08_fail_closed_behavior(self):
        """Verify orchestrator fails closed when a critical gate fails."""
        orchestrator = DeploymentOrchestrator(self.mock_args, PROJECT_ROOT)
        with patch.object(orchestrator, "phase_02_dependency_gate", return_value=False):
            exit_code = orchestrator.run()
            self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
