"""
scripts/run_marketplace_ingestion.py
Executes sql/marketplace_ingestion.sql in Snowflake to ingest TPC-H supply chain data
from the SNOWFLAKE_SAMPLE_DATA Data Share.
Validates table creation, row counts, and data quality metrics.
"""
import os
import sys

def row_to_dict(row):
    try: return row.as_dict()
    except: pass
    try: return dict(row)
    except: return {"raw": str(row)}

def main():
    from snowflake.snowpark import Session
    cfg = {
        "account": os.environ.get("SNOWFLAKE_ACCOUNT", ""),
        "user": os.environ.get("SNOWFLAKE_USER", ""),
        "password": os.environ.get("SNOWFLAKE_PASSWORD", ""),
        "role": os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "PM_OEE_WH"),
        "database": os.environ.get("SNOWFLAKE_DATABASE", "PM_OEE_DB"),
        "schema": os.environ.get("SNOWFLAKE_SCHEMA", "CORE"),
    }
    if not cfg["password"]:
        print("ERROR: SNOWFLAKE_PASSWORD is required.")
        sys.exit(1)

    session = Session.builder.configs(cfg).create()
    print("=== EXECUTING MARKETPLACE / DATA SHARE INGESTION SQL ===\n")

    sql_file = os.path.join(os.path.dirname(__file__), "..", "sql", "marketplace_ingestion.sql")
    with open(sql_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Split SQL file into statements
    statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

    for i, stmt in enumerate(statements):
        print(f"[{i+1}/{len(statements)}] Executing: {stmt[:60]}...")
        try:
            res = session.sql(stmt).collect()
            if res:
                d = row_to_dict(res[0])
                print(f"    Result: {d}")
        except Exception as e:
            print(f"    ERROR executing statement: {e}")
            sys.exit(1)

    print("\n=== VALIDATING INGESTION RESULTS & DATA QUALITY ===\n")

    # 1. Raw table validation
    raw_cnt = session.sql("SELECT COUNT(*) AS CNT FROM PM_OEE_DB.CORE.RAW_MARKETPLACE_SUPPLY_CHAIN").collect()[0]["CNT"]
    print(f"  RAW_MARKETPLACE_SUPPLY_CHAIN rows: {raw_cnt}")

    # 2. Conformed catalog validation
    cat_cnt = session.sql("SELECT COUNT(*) AS CNT FROM PM_OEE_DB.CORE.MARKETPLACE_PART_CATALOG").collect()[0]["CNT"]
    print(f"  MARKETPLACE_PART_CATALOG rows: {cat_cnt}")

    # 3. Data quality checks
    dq_null_parts = session.sql("SELECT COUNT(*) AS CNT FROM PM_OEE_DB.CORE.RAW_MARKETPLACE_SUPPLY_CHAIN WHERE PART_NAME IS NULL").collect()[0]["CNT"]
    dq_suppliers = session.sql("SELECT COUNT(DISTINCT SUPPLIER_KEY) AS CNT FROM PM_OEE_DB.CORE.RAW_MARKETPLACE_SUPPLY_CHAIN").collect()[0]["CNT"]
    dq_avg_cost = session.sql("SELECT AVG(SUPPLY_COST_USD) AS AVG_COST FROM PM_OEE_DB.CORE.RAW_MARKETPLACE_SUPPLY_CHAIN").collect()[0]["AVG_COST"]

    print(f"  DQ — Null part names: {dq_null_parts}")
    print(f"  DQ — Unique suppliers ingested: {dq_suppliers}")
    print(f"  DQ — Average supply cost: ${float(dq_avg_cost):.2f}")

    print("\n=== INGESTION SUCCESSFUL! ===")
    session.close()

if __name__ == "__main__":
    main()
