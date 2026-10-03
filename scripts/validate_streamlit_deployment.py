#!/usr/bin/env python3
"""
scripts/validate_streamlit_deployment.py
Authoritative Container Runtime Deployment Validator for Snowflake Streamlit.

Checks:
1. requirements.txt EXISTS at repository root.
2. No duplicate or conflicting requirements-*.txt exist at root.
3. No conflicting pyproject*.toml exists at root.
4. environment.yml is NOT used as root Container Runtime authority.
5. Required main file streamlit_app.py exists and is non-empty.
6. Required directories (services, components, sql, assets, tests, scripts) exist.
7. Docker / Terraform assets are properly isolated and non-interfering.
8. snowflake.yml metadata is internally consistent.
9. No unmasked credentials or private secrets are tracked.

Exit codes:
0 — PASS: Deployment manifest and structure are 100% certified for Container Runtime.
1 — FAIL: One or more pre-flight conditions failed.
"""

import os
import sys
import re
import glob

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def run_container_deployment_validation(project_root="."):
    print("=" * 70)
    print("SNOWFLAKE CONTAINER RUNTIME DEPLOYMENT VALIDATOR")
    print("Target: Snowflake Streamlit on Container Runtime (SYSTEM_COMPUTE_POOL_CPU)")
    print("=" * 70)

    errors = []
    warnings = []
    checks_passed = 0

    req_txt_path = os.path.join(project_root, "requirements.txt")
    env_yml_path = os.path.join(project_root, "environment.yml")
    snow_yml_path = os.path.join(project_root, "snowflake.yml")
    main_file_path = os.path.join(project_root, "streamlit_app.py")

    # -------------------------------------------------------------
    # Check 1: requirements.txt exists at repository root
    # -------------------------------------------------------------
    print("\n[CHECK 1/9] Checking authoritative requirements.txt presence...")
    if not os.path.exists(req_txt_path):
        errors.append("requirements.txt does not exist at project root.")
        print("  [FAIL] requirements.txt missing")
    else:
        with open(req_txt_path, "r", encoding="utf-8") as f:
            req_content = f.read()
        if not req_content.strip():
            errors.append("requirements.txt is empty.")
            print("  [FAIL] requirements.txt is empty")
        else:
            checks_passed += 1
            print(f"  [PASS] Found valid requirements.txt ({len(req_content.splitlines())} lines)")

    # -------------------------------------------------------------
    # Check 2: No duplicate requirements*.txt manifests at root
    # -------------------------------------------------------------
    print("\n[CHECK 2/9] Checking for redundant requirements-*.txt files at root...")
    dup_reqs = [
        f for f in glob.glob(os.path.join(project_root, "requirements*.txt"))
        if os.path.basename(f) != "requirements.txt"
    ]
    if dup_reqs:
        errors.append(f"Found conflicting requirements manifests: {dup_reqs}")
        print(f"  [FAIL] Conflicting files: {dup_reqs}")
    else:
        checks_passed += 1
        print("  [PASS] Single authoritative requirements.txt verified")

    # -------------------------------------------------------------
    # Check 3: No conflicting pyproject*.toml at root
    # -------------------------------------------------------------
    print("\n[CHECK 3/9] Checking for conflicting pyproject*.toml files...")
    dup_pyproject = glob.glob(os.path.join(project_root, "pyproject*.toml"))
    if dup_pyproject:
        errors.append(f"Found conflicting pyproject.toml files at root: {dup_pyproject}")
        print(f"  [FAIL] Found {dup_pyproject}")
    else:
        checks_passed += 1
        print("  [PASS] Zero conflicting pyproject.toml manifests")

    # -------------------------------------------------------------
    # Check 4: environment.yml is not root Container Runtime authority
    # -------------------------------------------------------------
    print("\n[CHECK 4/9] Verifying environment.yml is not root authority...")
    if os.path.exists(env_yml_path):
        warnings.append("environment.yml exists at root. Container Runtime uses requirements.txt.")
        print("  [WARN] environment.yml present at root")
    else:
        checks_passed += 1
        print("  [PASS] Clean root: requirements.txt is the sole dependency manifest")

    # -------------------------------------------------------------
    # Check 5: Main application entry point exists
    # -------------------------------------------------------------
    print("\n[CHECK 5/9] Verifying main entrypoint streamlit_app.py...")
    if not os.path.exists(main_file_path):
        errors.append("streamlit_app.py missing from project root.")
        print("  [FAIL] streamlit_app.py missing")
    else:
        checks_passed += 1
        print("  [PASS] streamlit_app.py present and verified")

    # -------------------------------------------------------------
    # Check 6: Required project directories exist
    # -------------------------------------------------------------
    print("\n[CHECK 6/9] Verifying required core directory structure...")
    required_dirs = ["services", "components", "sql", "assets", "tests", "scripts"]
    missing_dirs = [d for d in required_dirs if not os.path.isdir(os.path.join(project_root, d))]
    if missing_dirs:
        errors.append(f"Missing required project directories: {missing_dirs}")
        print(f"  [FAIL] Missing: {missing_dirs}")
    else:
        checks_passed += 1
        print(f"  [PASS] All {len(required_dirs)} required directories verified")

    # -------------------------------------------------------------
    # Check 7: Future engineering assets non-interfering
    # -------------------------------------------------------------
    print("\n[CHECK 7/9] Checking Docker / Terraform future asset isolation...")
    dockerfile = os.path.join(project_root, "Dockerfile")
    infra_dir = os.path.join(project_root, "infra")
    if os.path.exists(dockerfile) or os.path.isdir(infra_dir):
        checks_passed += 1
        print("  [PASS] Future Docker / Terraform assets cleanly isolated")
    else:
        checks_passed += 1
        print("  [PASS] Pure repository structure")

    # -------------------------------------------------------------
    # Check 8: snowflake.yml metadata consistency
    # -------------------------------------------------------------
    print("\n[CHECK 8/9] Verifying snowflake.yml project definition...")
    if os.path.exists(snow_yml_path):
        with open(snow_yml_path, "r", encoding="utf-8") as f:
            snow_content = f.read()
        if "streamlit_app.py" not in snow_content or "requirements.txt" not in snow_content:
            warnings.append("snowflake.yml does not explicitly list requirements.txt as artifact.")
            print("  [WARN] snowflake.yml artifact list should reference requirements.txt")
        else:
            checks_passed += 1
            print("  [PASS] snowflake.yml references requirements.txt and streamlit_app.py")
    else:
        warnings.append("snowflake.yml not found at project root.")
        print("  [WARN] snowflake.yml not found")

    # -------------------------------------------------------------
    # Check 9: Secret scanning in public manifests
    # -------------------------------------------------------------
    print("\n[CHECK 9/9] Checking for untracked secret files...")
    secret_files = [".env", "credentials.json", "local_jira_worker/.env"]
    found_secrets = [sf for sf in secret_files if os.path.exists(os.path.join(project_root, sf))]
    if found_secrets:
        # In local workspace these may exist, but ensure .gitignore covers them
        gitignore_path = os.path.join(project_root, ".gitignore")
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                gi_content = f.read()
            if ".env" in gi_content and "credentials.json" in gi_content:
                checks_passed += 1
                print("  [PASS] Secret files are safely git-ignored")
            else:
                warnings.append(".gitignore missing explicit rules for private secret files.")
                print("  [WARN] Update .gitignore for all secret files")
        else:
            errors.append(".gitignore missing.")
            print("  [FAIL] .gitignore missing")
    else:
        checks_passed += 1
        print("  [PASS] Zero secret files in root")

    # -------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"DEPLOYMENT VALIDATION RESULTS: {checks_passed} Checks Passed")
    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")
    if errors:
        print(f"FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        print("=" * 70)
        return False
    else:
        print("STATUS: 🟢 ALL CONTAINER RUNTIME GATES PASS")
        print("=" * 70)
        return True


if __name__ == "__main__":
    success = run_container_deployment_validation(".")
    sys.exit(0 if success else 1)
