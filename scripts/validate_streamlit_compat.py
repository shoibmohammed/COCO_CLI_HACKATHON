#!/usr/bin/env python3
"""
scripts/validate_streamlit_compat.py
Streamlit Runtime Compatibility Scanner for Snowflake Native Streamlit.

Validates that active Python files do not invoke Streamlit APIs or keyword
arguments unsupported by Snowflake's Native Streamlit runtime environment.

Checked incompatibilities:
1. Direct st.rerun() calls (must use safe_rerun() helper)
2. Direct streamlit.rerun() calls
3. st.container(border=...) unsupported in older runtimes
"""

import ast
import os
import sys
import re

TARGET_DIRS = ["components", "services"]
TARGET_FILES = ["streamlit_app.py", "snowflake_connection.py"]


def check_file_ast(filepath):
    """AST check for direct st.rerun calls outside safe_rerun definitions and invalid keywords."""
    issues = []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as e:
        return [(filepath, e.lineno, f"Syntax Error: {e.msg}")]

    class StreamlitCallVisitor(ast.NodeVisitor):
        def __init__(self):
            self.in_safe_rerun = False

        def visit_FunctionDef(self, node):
            prev = self.in_safe_rerun
            if node.name == "safe_rerun":
                self.in_safe_rerun = True
            self.generic_visit(node)
            self.in_safe_rerun = prev

        def visit_Call(self, node):
            # Check for direct st.rerun() calls
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "rerun" and isinstance(node.func.value, ast.Name) and node.func.value.id in ("st", "streamlit"):
                    if not self.in_safe_rerun:
                        issues.append((filepath, node.lineno, "Direct st.rerun() call found outside safe_rerun() helper. Use safe_rerun()."))
                # Check for container(border=...)
                elif node.func.attr == "container" and isinstance(node.func.value, ast.Name) and node.func.value.id in ("st", "streamlit"):
                    for kw in node.keywords:
                        if kw.arg == "border":
                            issues.append((filepath, node.lineno, "st.container(border=...) unsupported in Snowflake runtime. Use st.container()."))
            self.generic_visit(node)

    visitor = StreamlitCallVisitor()
    visitor.visit(tree)

    return issues


def validate_streamlit_compatibility(project_root="."):
    all_issues = []
    files_checked = 0

    # Check root target files
    for fname in TARGET_FILES:
        fpath = os.path.join(project_root, fname)
        if os.path.exists(fpath):
            files_checked += 1
            all_issues.extend(check_file_ast(fpath))

    # Check target directories
    for dname in TARGET_DIRS:
        dp = os.path.join(project_root, dname)
        if os.path.exists(dp):
            for root, _, files in os.walk(dp):
                for f in files:
                    if f.endswith(".py"):
                        files_checked += 1
                        all_issues.extend(check_file_ast(os.path.join(root, f)))

    deduped = sorted(list(set(all_issues)))
    return files_checked, deduped


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    count, issues = validate_streamlit_compatibility(root)

    print("=" * 70)
    print("STREAMLIT RUNTIME COMPATIBILITY VALIDATOR")
    print(f"Scanned {count} active application files")
    print("=" * 70)

    if issues:
        print(f"FAIL: {len(issues)} compatibility issue(s) detected:\n")
        for path, lineno, msg in issues:
            print(f"  [FAIL] {os.path.relpath(path, root)}:{lineno} -- {msg}")
        sys.exit(1)
    else:
        print(f"PASS: All {count} files are 100% compatible with Snowflake Native Streamlit.")
        sys.exit(0)


if __name__ == "__main__":
    main()
