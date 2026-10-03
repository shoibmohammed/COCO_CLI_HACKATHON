"""
check_submission_completeness.py
Validates that the repository contains all required artifacts for judge submission.
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_DIRS = [
    "pages", "components", "services", "scripts", "sql", "tests",
    "data", "assets", "local_jira_worker", "infra", ".github"
]

REQUIRED_FILES = [
    "streamlit_app.py", "config.py", "snowflake_connection.py",
    "requirements.txt", "snowflake.yml", "README.md", "DEPLOYMENT.md",
    ".gitignore", ".env.example", "credentials.example.json",
    "Dockerfile", "docker-compose.yml",
    "sql/deploy_all.sql", "sql/01_setup.sql", "sql/03_seed_data.sql",
    "sql/03_cortex_ml.sql", "sql/marketplace_ingestion.sql",
    "scripts/validate_python.py", "scripts/check_sql_safety.py",
    "scripts/verify_deployment.py", "scripts/validate_streamlit_deployment.py",
    "scripts/bootstrap_judge.sh", "scripts/bootstrap_judge.ps1",
]

FORBIDDEN_FILES = [
    ".env", "credentials.json", ".streamlit/secrets.toml",
    "local_jira_worker/.env"
]

# Files that must not contain real secrets (checked by content)
SECRET_CONTENT_FILES = [
    "local_jira_worker/.jira_demo.json"
]

def main():
    errors = []
    warnings = []
    
    print("=" * 70)
    print("SUBMISSION COMPLETENESS CHECK")
    print("MFG Predictive Maintenance & OEE Command Center")
    print("=" * 70)
    
    # Check required directories
    print("\n[1] Required Directories:")
    for d in REQUIRED_DIRS:
        path = os.path.join(PROJECT_ROOT, d)
        if os.path.isdir(path):
            print(f"  [PASS] {d}/")
        else:
            errors.append(f"Missing directory: {d}/")
            print(f"  [FAIL] {d}/ — NOT FOUND")
    
    # Check required files
    print("\n[2] Required Files:")
    for f in REQUIRED_FILES:
        path = os.path.join(PROJECT_ROOT, f)
        if os.path.isfile(path):
            print(f"  [PASS] {f}")
        else:
            errors.append(f"Missing file: {f}")
            print(f"  [FAIL] {f} — NOT FOUND")
    
    # Check forbidden files (secrets)
    print("\n[3] Secret Files (must NOT exist):")
    for f in FORBIDDEN_FILES:
        path = os.path.join(PROJECT_ROOT, f)
        if os.path.isfile(path):
            errors.append(f"SECRET FILE PRESENT: {f}")
            print(f"  [FAIL] {f} — REMOVE BEFORE SUBMISSION")
        else:
            print(f"  [PASS] {f} — not present (good)")
    
    for f in SECRET_CONTENT_FILES:
        path = os.path.join(PROJECT_ROOT, f)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            if any(tok in content for tok in ["ATATT3", "sk-", "xoxb-", "Bearer ", "gmail.com"]):
                errors.append(f"REAL SECRETS IN: {f}")
                print(f"  [FAIL] {f} — contains real secrets")
            else:
                print(f"  [PASS] {f} — template only (sanitized)")
        else:
            print(f"  [PASS] {f} — not present")
    
    # Check Python file count
    py_count = 0
    for root, dirs, files in os.walk(PROJECT_ROOT):
        if '__pycache__' in root or '.git' in root:
            continue
        for f in files:
            if f.endswith('.py'):
                py_count += 1
    print(f"\n[4] Python Files: {py_count}")
    
    # Check SQL file count
    sql_count = 0
    sql_dir = os.path.join(PROJECT_ROOT, "sql")
    if os.path.isdir(sql_dir):
        sql_count = len([f for f in os.listdir(sql_dir) if f.endswith('.sql')])
    print(f"[5] SQL Files: {sql_count}")
    
    # Check test count
    test_count = 0
    test_dir = os.path.join(PROJECT_ROOT, "tests")
    if os.path.isdir(test_dir):
        test_count = len([f for f in os.listdir(test_dir) if f.startswith('test_') and f.endswith('.py')])
    print(f"[6] Test Files: {test_count}")
    
    # Check pages count
    pages_count = 0
    pages_dir = os.path.join(PROJECT_ROOT, "pages")
    if os.path.isdir(pages_dir):
        pages_count = len([f for f in os.listdir(pages_dir) if f.endswith('.py') and not f.startswith('__')])
    print(f"[7] Streamlit Pages: {pages_count}")
    
    # Summary
    print("\n" + "=" * 70)
    if errors:
        print(f"RESULT: FAIL — {len(errors)} error(s)")
        for e in errors:
            print(f"  ERROR: {e}")
        sys.exit(1)
    else:
        print(f"RESULT: PASS")
        print(f"  Python: {py_count} files")
        print(f"  SQL: {sql_count} files")
        print(f"  Tests: {test_count} files")
        print(f"  Pages: {pages_count} files")
        print(f"  Secrets: 0 (clean)")
    print("=" * 70)

if __name__ == "__main__":
    main()
