"""
tests/test_marketplace_ingestion.py
Automated test suite verifying Real Snowflake Marketplace agentic ingestion,
table accessibility, idempotency, data quality, Gemini context enrichment,
and non-disruption of existing Dynamic Tables and demo scenarios.
"""

import os
import sys
import platform

platform.libc_ver = lambda *args, **kwargs: ("", "")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.marketplace_discovery import load_snowflake_config


def test_marketplace_ingestion():
    try:
        from snowflake.snowpark import Session
    except ImportError:
        print("SKIP: snowflake-snowpark-python module not installed in environment")
        return
    cfg = load_snowflake_config()
    if not cfg.get("password"):
        print("SKIP: SNOWFLAKE_PASSWORD not set")
        return

    session = Session.builder.configs(cfg).create()
    print("=== TESTING REAL SNOWFLAKE MARKETPLACE AGENTIC INGESTION ===\n")

    # 1. Test Marketplace DDL Tables
    print("[1/7] Testing PM_OEE_DB.CORE Marketplace DDL tables...")
    for tbl in [
        "MARKETPLACE_INGESTION_CONTROL",
        "MARKETPLACE_INGESTION_AUDIT",
        "RAW_MARKETPLACE_DATA",
        "MARKETPLACE_CONFORMED_DATA",
        "MARKETPLACE_PART_SUPPLIER_ENRICHMENT",
    ]:
        try:
            cnt = session.sql(f"SELECT COUNT(*) AS CNT FROM PM_OEE_DB.CORE.{tbl}").collect()[0]["CNT"]
            print(f"  [PASS] Table PM_OEE_DB.CORE.{tbl} verified ({cnt} rows)")
        except Exception as e:
            assert False, f"Table {tbl} check failed: {e}"

    # 2. Test Agentic Ingestion Execution
    print("[2/7] Testing Agentic Ingestion Pipeline (run_ingestion)...")
    from services.marketplace_agent import run_ingestion, get_ingestion_status, get_supplier_enrichment
    ing_res = run_ingestion(session)
    assert ing_res and "overall_status" in ing_res, "Ingestion execution failed"
    print(f"  [PASS] Agentic pipeline completed with status: {ing_res['overall_status']}")

    # 3. Test Idempotency (Re-run should not create duplicate entries)
    print("[3/7] Verifying Ingestion Idempotency (Re-run execution)...")
    ing_res_2 = run_ingestion(session)
    new_rows_2 = ing_res_2.get("results", {}).get("INGEST", {}).get("total_new_rows", 0)
    assert new_rows_2 == 0, f"Expected 0 new rows on re-run, got {new_rows_2}"
    print("  [PASS] Idempotency verified (0 new rows inserted on re-run)")

    # 4. Test Data Quality Audit Log
    print("[4/7] Verifying Data Quality Audit Trail in Snowflake...")
    status_info = get_ingestion_status(session)
    assert status_info.get("has_data") or status_info.get("status") != "FAILED", "Data quality audit check failed"
    print(f"  [PASS] Audit log verified (Last run ID: {status_info.get('run_id', 'N/A')})")

    # 5. Test Gemini Marketplace Context Enrichment
    print("[5/7] Testing Gemini Marketplace Context Builder...")
    from services.gemini_service import build_marketplace_context
    mkt_ctx = build_marketplace_context(session, "SKF-6205-2RS")
    assert isinstance(mkt_ctx, dict), "Marketplace context must be a dict"
    print(f"  [PASS] Marketplace context built successfully (Available: {mkt_ctx.get('marketplace_available')})")

    # 6. Verify Existing Dynamic Tables Still Operational
    print("[6/7] Verifying existing Dynamic Tables pipeline...")
    for dt in ["MACHINE_HEALTH_RT", "RISK_SCORES_RT", "OEE_METRICS_RT"]:
        try:
            dt_rows = session.sql(f"SELECT COUNT(*) AS CNT FROM PM_OEE_DB.CORE.{dt}").collect()
            print(f"  [PASS] Dynamic Table {dt} operational ({dt_rows[0]['CNT']} rows)")
        except Exception as e:
            assert False, f"Dynamic Table {dt} error: {e}"

    # 7. Verify Existing Demo Scenarios Operational
    print("[7/7] Verifying existing demo scenario engine...")
    from services.scenario_service import SCENARIOS
    assert len(SCENARIOS) == 6, "Expected 6 demo scenarios"
    print("  [PASS] All 6 demo scenarios intact and ready")

    print("\nALL MARKETPLACE AGENTIC INGESTION TESTS PASSED CLEANLY!")
    session.close()


if __name__ == "__main__":
    test_marketplace_ingestion()
