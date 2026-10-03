#!/usr/bin/env python3
"""
scripts/validate_python.py
Pre-submission syntax validation for all Python files in the project.
Recursively discovers .py files, parses them with ast, and reports failures.

Usage:
    python scripts/validate_python.py

Exit code:
    0 — all files pass
    1 — one or more files have syntax errors
"""

import ast
import os
import sys


SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv"}


def validate_all(root_dir="."):
    errors = []
    checked = 0

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            filepath = os.path.join(dirpath, fname)
            checked += 1
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    source = f.read()
                ast.parse(source, filename=filepath)
            except SyntaxError as e:
                errors.append((filepath, e.lineno, e.msg))

    return checked, errors


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    checked, errors = validate_all(".")

    if errors:
        print(f"FAIL: {len(errors)} syntax error(s) in {checked} files checked:\n")
        for path, lineno, msg in errors:
            print(f"  {path}:{lineno} — {msg}")
        sys.exit(1)
    else:
        print(f"PASS: All {checked} Python files have valid syntax.")
        sys.exit(0)


if __name__ == "__main__":
    main()
