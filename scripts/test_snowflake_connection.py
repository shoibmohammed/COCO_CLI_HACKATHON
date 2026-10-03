"""
scripts/test_snowflake_connection.py
Diagnostic tool to verify Snowflake connection and environment readiness.
Run: python scripts/test_snowflake_connection.py
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure root folder is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from snowflake_connection import get_snowflake_session

def main():
    print("=" * 60)
    print(" Snowflake Connection & Project Readiness Diagnostic Tool ")
    print("=" * 60)

    session, status_msg, is_local = get_snowflake_session()
    print(f"Status: {status_msg}")

    if not session:
        print("\n❌ Could not connect to Snowflake automatically.")
        print("\nTo connect locally:")
        print(" 1. Copy .streamlit/secrets.toml.example to .streamlit/secrets.toml")
        print(" 2. Enter your account, user, password, role, warehouse, database, schema.")
        print(" OR set environment variables: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD.")
        sys.exit(1)

    print("✅ Successfully established Snowflake Session!")
    
    try:
        current_db = session.sql("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE(), CURRENT_ROLE()").collect()[0]
        print(f"   - Database:  {current_db[0]}")
        print(f"   - Schema:    {current_db[1]}")
        print(f"   - Warehouse: {current_db[2]}")
        print(f"   - Role:      {current_db[3]}")
    except Exception as e:
        print(f"⚠️ Warning retrieving current session context: {e}")

    # Check key project tables
    tables = [
        "MACHINE_MASTER", "SENSOR_READINGS", "PRODUCTION_EVENTS",
        "MAINTENANCE_HISTORY", "SPARE_PARTS", "WORK_ORDERS"
    ]
    from config import table
    print("\nChecking database tables in PM_OEE_DB.CORE:")
    for tbl_name in tables:
        try:
            full_tbl = table(tbl_name)
            count = session.sql(f"SELECT COUNT(*) FROM {full_tbl}").collect()[0][0]
            print(f"  [✓] {tbl_name:22s} : {count:6d} rows")
        except Exception:
            print(f"  [✗] {tbl_name:22s} : TABLE NOT FOUND (Run sql/01_setup.sql and scripts/seed_demo_data.py)")

    print("\n=" * 60)
    print(" Diagnostic Complete ")
    print("=" * 60)

if __name__ == "__main__":
    main()
