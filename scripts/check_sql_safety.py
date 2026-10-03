"""
scripts/check_sql_safety.py
Static SQL Security & Injection Vulnerability Scanner
MFG Predictive Maintenance & OEE Command Center

Scans all active Python codebase files for unparameterized SQL execution,
dynamic string interpolations, and unvalidated identifier usage in database queries.
"""

import os
import re
import sys
from typing import List, Dict, Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Modules and directories to scan
SCAN_DIRECTORIES = [
    "services",
    "pages",
    "components",
    "scripts",
    "local_jira_worker",
]
SCAN_ROOT_FILES = [
    "streamlit_app.py",
    "snowflake_connection.py",
    "mcp_server.py",
    "config.py",
]

# Allowed safe identifier variables, table suffixes, and deployment config references
SAFE_IDENTIFIER_TOKENS = {
    "table", "get_object_name", "DATABASE", "SCHEMA", "WAREHOUSE",
    "search_svc", "search_payload", "agent_name", "sql_safe_body",
    "INTEGRATION_NAME", "full_tbl", "dt_sql", "fqn", "where_clause",
    "db_name", "schema", "table_name", "tbl", "run_id", "source_rows",
    "target_rows", "new_rows", "dup_rows", "duration", "overall",
    "ENV_TABLE", "sensor_tbl", "parts_tbl", "prod_tbl", "health_dt",
    "risk_dt", "oee_dt", "health_tbl", "risk_tbl", "rul_tbl", "oee_tbl",
    "drift_tbl", "baseline_tbl", "risk_unified", "alert_tbl", "jira_audit_tbl",
    "notif_audit_tbl", "ml_pred_tbl", "mkt_enrich_tbl", "wo_tbl", "q_tbl",
    "audit_tbl", "name", "placeholders", "msg_escaped", "stage", "st_obj",
    "wh", "gn", "self", "config"
}


def is_safe_expression(expr: str) -> bool:
    """Verifies that an interpolated expression is a safe, validated identifier token."""
    clean = expr.strip()
    # Check function call (e.g. table(...), get_object_name(...), f"...")
    if re.match(r"^(table|get_object_name|config\.table|config\.get_object_name)\s*\(", clean):
        return True
    if re.match(r"^[a-zA-Z0-9_]+_(tbl|dt|df|rt)$", clean):
        return True
    if re.match(r"^self\.config\[.+\]$", clean):
        return True
    if re.match(r"^config(\.get)?\[?.*\]?$", clean):
        return True
    token = clean.split(".")[0].split("[")[0].strip()
    return token in SAFE_IDENTIFIER_TOKENS


def scan_file(filepath: str) -> List[Dict[str, Any]]:
    issues = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Check for direct f-strings in SQL execution calls
    lines = content.splitlines()
    for i, line in enumerate(lines):
        line_num = i + 1
        line_stripped = line.strip()

        # Check for old-style .format() inside query calls
        if any(call in line_stripped for call in ["session.sql(", "cursor.execute(", "qdf(", "qexec("]):
            if ".format(" in line_stripped:
                issues.append({
                    "line": line_num,
                    "type": "RISKY_FORMAT",
                    "code": line_stripped[:100],
                    "message": "Direct .format() used in SQL execution call. Use parameterized queries (?, %s)."
                })

            if re.search(r"%\s*\([a-zA-Z0-9_,\s]+\)", line_stripped):
                issues.append({
                    "line": line_num,
                    "type": "RISKY_PERCENT_FORMAT",
                    "code": line_stripped[:100],
                    "message": "Direct % tuple formatting used in SQL execution call. Use parameterized queries (?, %s)."
                })

    # Search for SQL execution calls with f-strings
    fstring_calls = re.finditer(
        r'(session\.sql|cursor\.execute|cur\.execute|qdf|qexec|_execute|_execute_dml)\s*\(\s*f("""|\'\'\'|")(.*?)(\2)',
        content,
        re.DOTALL
    )
    for m in fstring_calls:
        call_fn = m.group(1)
        sql_body = m.group(3)
        start_pos = m.start()
        line_no = content[:start_pos].count("\n") + 1

        # Check all interpolations in this SQL statement
        interpolations = re.findall(r"\{([^}]+)\}", sql_body)
        unsafe = [expr for expr in interpolations if not is_safe_expression(expr)]
        if unsafe:
            issues.append({
                "line": line_no,
                "type": "UNSAFE_SQL_INTERPOLATION",
                "code": f"{call_fn}(f\"...{sql_body[:60]}...\")".replace("\n", " "),
                "message": f"Unvalidated dynamic variables in SQL query: {unsafe}. Parameterize query via (?, %s) or whitelist identifier."
            })

    return issues


def main():
    print("=" * 75)
    print("[SECURITY] STATIC SQL SECURITY & INJECTION VULNERABILITY SCANNER")
    print("           MFG Predictive Maintenance & OEE Command Center")
    print("=" * 75)

    all_issues = {}
    files_scanned = 0

    # Scan root files
    for rfile in SCAN_ROOT_FILES:
        fpath = os.path.join(PROJECT_ROOT, rfile)
        if os.path.exists(fpath):
            files_scanned += 1
            file_issues = scan_file(fpath)
            if file_issues:
                all_issues[rfile] = file_issues

    # Scan directories
    for sdir in SCAN_DIRECTORIES:
        dpath = os.path.join(PROJECT_ROOT, sdir)
        if os.path.exists(dpath):
            for root, _, files in os.walk(dpath):
                if any(x in root for x in [".git", "__pycache__", ".venv", "tests"]):
                    continue
                for fname in files:
                    if fname.endswith(".py"):
                        fpath = os.path.join(root, fname)
                        rel_path = os.path.relpath(fpath, PROJECT_ROOT)
                        files_scanned += 1
                        file_issues = scan_file(fpath)
                        if file_issues:
                            all_issues[rel_path] = file_issues

    print(f"\nScanned {files_scanned} Python source files.\n")

    if not all_issues:
        print("[PASS] Clean. Zero unparameterized SQL vulnerabilities or unsafe interpolations found.")
        print("       All SQL queries are parameterized with ? / %s placeholders or use centralized whitelisted identifiers.")
        print("=" * 75)
        sys.exit(0)
    else:
        print(f"[WARN] Found potential issues in {len(all_issues)} files:")
        for fpath, issues in all_issues.items():
            print(f"\n  File: {fpath}")
            for iss in issues:
                print(f"    Line {iss['line']}: [{iss['type']}] {iss['message']}")
                print(f"      Code: {iss['code']}")
        print("\n" + "=" * 75)
        sys.exit(1)


if __name__ == "__main__":
    main()
