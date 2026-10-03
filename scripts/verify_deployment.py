#!/usr/bin/env python3
"""
scripts/verify_deployment.py
Lightweight Deployment & Import Validator for MFG Predictive Maintenance Command Center.
Performs non-destructive syntax, structure, file presence, and safe module import checks.

DOES NOT perform ML retraining, Dynamic Table refreshes, heavy Cortex LLM calls,
Jira API tickets creation, or live email/Slack notification sends.
"""

import sys
import os
import importlib

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def run_verification():
    print("=" * 60)
    print("MFG COMMAND CENTER — LIGHTWEIGHT DEPLOYMENT VERIFICATION")
    print("=" * 60)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    sys.path.insert(0, project_root)
    
    errors = 0
    warnings = 0
    
    # 1. Essential File Verification
    print("\n[1/4] Checking Essential Core Files...")
    essential_files = [
        "README.md",
        "DEPLOYMENT.md",
        "GITHUB_SECURITY_REVIEW.md",
        "HACKATHON2_STREAMLIT_ONLY_READINESS.md",
        "assets/architecture.png",
        "streamlit_app.py",
        "mcp_server.py",
        "snowflake_connection.py",
        "requirements.txt",
        "credentials.example.json",
        ".streamlit/config.toml",
        "sql/deploy_all.sql",
        "sql/01_setup.sql",
        "sql/validate_deployment.sql",
        "scripts/validate_python.py",
        "scripts/validate_streamlit_deployment.py",
        "scripts/bootstrap_judge.ps1",
        "scripts/bootstrap_judge.sh",
        "local_jira_worker/worker.py",
        "local_jira_worker/config.py",
        "local_jira_worker/jira_client.py",
        "local_jira_worker/snowflake_client.py"
    ]
    
    for ef in essential_files:
        if os.path.exists(ef):
            print(f"  [PASS] {ef}")
        else:
            print(f"  [FAIL] Missing required file: {ef}")
            errors += 1
            
    # 2. Secret & Configuration Preservation Check
    print("\n[2/4] Checking Credential & Secret Preservation...")
    secret_files = [
        "credentials.json",
        ".streamlit/secrets.toml",
        ".streamlit/secrets.toml.example",
        "local_jira_worker/.env.example",
        "marketplace_selected_listing.json"
    ]
    for sf in secret_files:
        if os.path.exists(sf):
            print(f"  [PRESERVED] {sf}")
        else:
            print(f"  [WARN] Optional secret file not found: {sf}")
            warnings += 1

    # 3. Clean Repository Structure Check (No forbidden directories)
    print("\n[3/4] Verifying Repository Structure Boundaries...")
    forbidden_dirs = ["docs", "archive", "release_logs"]
    for fd in forbidden_dirs:
        if os.path.exists(fd):
            print(f"  [FAIL] Forbidden internal directory exists: {fd}/")
            errors += 1
        else:
            print(f"  [PASS] {fd}/ removed as required")

    # 4. Safe Module Imports Check (Excludes streamlit_app.py to prevent import-time UI init)
    print("\n[4/4] Checking Safe Python Module Imports...")
    safe_modules = [
        "mcp_server",
        "snowflake_connection",
        "services.ai_guardrails",
        "services.document_service",
        "services.email_provider",
        "services.email_service",
        "services.jira_mcp_service",
        "services.jira_queue_service",
        "services.jira_service",
        "services.knowledge_service",
        "services.marketplace_agent",
        "services.ml_service",
        "services.notification_service",
        "services.scenario_service",
        "services.slack_service",
        "services.snowflake_email_provider",
        "services.universal_email_service",
        "components.header",
        "components.kpi_card",
        "components.system_status",
        "components.diagnosis_card",
        "components.business_impact",
        "components.universal_email_composer"
    ]
    
    for mod in safe_modules:
        try:
            importlib.import_module(mod)
            print(f"  [PASS] {mod}")
        except Exception as e:
            print(f"  [WARN] Safe import failed for {mod}: {e}")
            warnings += 1

    print("\n" + "=" * 60)
    print(f"VERIFICATION SUMMARY: {errors} Errors, {warnings} Warnings")
    print("=" * 60)
    
    if errors > 0:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(run_verification())
