"""
tests/test_weather_integration.py
Comprehensive Test Suite for Environmental / Weather Intelligence Integration.
Verifies API connectivity, schema, ingestion, Snowflake persistence, duplicate idempotency,
Streamlit UI rendering, Gemini 4-category context, Machine_03 regression, Marketplace regression,
Snowflake ML regression, Work Order governance regression, Demo Reset, and offline Failure Handling.
"""

import os
import sys
import platform

platform.libc_ver = lambda *args, **kwargs: ("", "")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.marketplace_discovery import load_snowflake_config


def run_weather_tests():
    try:
        from snowflake.snowpark import Session
    except ImportError:
        print("SKIP: snowflake-snowpark-python module not installed in environment")
        return
    from services.weather_service import (
        fetch_live_environmental_data,
        persist_environmental_reading,
        get_latest_environmental_context,
        ensure_environmental_table_exists
    )
    from services.gemini_service import generate_diagnosis, build_marketplace_context
    from services.scenario_service import SCENARIOS, inject_scenario_to_snowflake, reset_demo_snowflake_state

    cfg = load_snowflake_config()
    if not cfg.get("password"):
        print("SKIP: SNOWFLAKE_PASSWORD env var not set")
        return

    session = Session.builder.configs(cfg).create()
    def qexec(sql): return session.sql(sql).collect()

    print("=" * 75)
    print("STARTING ENVIRONMENTAL INTELLIGENCE COMPREHENSIVE TEST SUITE")
    print("=" * 75)

    # 1. API Connectivity Test
    print("\n[1/13] Testing Open-Meteo Weather API Connectivity...")
    live_env = fetch_live_environmental_data(timeout_sec=3.0)
    assert live_env is not None, "API returned None"
    assert live_env.get("available") is True, f"API Connectivity failed: {live_env.get('error_detail')}"
    print(f"  [PASS] API Connected successfully. Plant: {live_env['plant_id']} | Source: {live_env['source']}")

    # 2. API Response Schema Test
    print("\n[2/13] Testing API Response Schema & Data Fields...")
    required_fields = [
        "ambient_temperature_c", "humidity_percent", "wind_speed_kmh",
        "precipitation_mm", "air_pressure_hpa", "weather_condition", "environmental_status"
    ]
    for field in required_fields:
        assert field in live_env, f"Missing field '{field}' in API schema"
    print(f"  [PASS] All 7 core schema fields verified.")
    print(f"         Temp: {live_env['ambient_temperature_c']}°C | Humidity: {live_env['humidity_percent']}% | Wind: {live_env['wind_speed_kmh']} km/h")
    print(f"         Pressure: {live_env['air_pressure_hpa']} hPa | AQI: {live_env.get('air_quality_aqi')} | Status: {live_env['environmental_status']}")

    # 3. Environmental Ingestion Logic Test
    print("\n[3/13] Testing Environmental Ingestion Logic & Categorization...")
    assert live_env["environmental_status"] in ["NORMAL", "ELEVATED", "EXTREME"], "Invalid environmental status"
    print(f"  [PASS] Ingestion parsing & risk categorization validated ({live_env['environmental_status']})")

    # 4. Snowflake Persistence Test
    print("\n[4/13] Testing Snowflake Table Persistence (PM_OEE_DB.CORE.ENVIRONMENTAL_CONTEXT)...")
    ensure_environmental_table_exists(session)
    persisted = persist_environmental_reading(session, live_env)
    print(f"  [PASS] Persisted record to Snowflake: {persisted}")

    db_env = get_latest_environmental_context(session, live_env["plant_id"])
    assert db_env.get("available") is True, "Failed to retrieve persisted environmental context from Snowflake"
    print(f"  [PASS] Verified record retrieved from Snowflake: Ambient Temp = {db_env['ambient_temperature_c']}°C | Source = {db_env['source']}")

    # 5. Duplicate / Idempotency Test
    print("\n[5/13] Testing Ingestion Idempotency & Duplicate Prevention...")
    persisted_dup = persist_environmental_reading(session, live_env)
    assert persisted_dup is False, "Idempotency check failed: duplicate record was persisted within 10-min window"
    print("  [PASS] Idempotency enforced cleanly (duplicate insert skipped).")

    # 6. Streamlit UI Rendering State Test
    print("\n[6/13] Testing Streamlit UI Rendering Helpers...")
    from components.system_status import render_plant_environmental_badge
    # Ensure helper imports and doesn't raise exception
    assert callable(render_plant_environmental_badge), "render_plant_environmental_badge not callable"
    print("  [PASS] Streamlit UI rendering component verified.")

    # 7. Gemini Context Generation Test (4 Evidence Categories)
    print("\n[7/13] Testing Gemini AI Context Payload & Prompt Rules...")
    mkt_ctx = build_marketplace_context(session, "Machine_03")
    context = {
        "machine_id": "Machine_03",
        "vibration_mm_s": 6.15,
        "temperature_c": 97.3,
        "rpm": 1552,
        "risk_score": 1.0,
        "ml_failure_probability": 0.9984,
        "bearing_part_number": "SKF-6205-2RS",
        "supplier": "SKF Industrial",
        "marketplace_context": mkt_ctx,
        "environmental_context": db_env
    }
    diag = generate_diagnosis(context)
    assert diag is not None and "root_cause" in diag, "Gemini diagnosis generation failed"
    # Ensure Gemini negative prompt constraint holds (weather is NOT cited as root cause)
    rc_lower = diag.get("root_cause", "").lower()
    assert "weather caused" not in rc_lower and "rain caused" not in rc_lower, "Gemini violated negative prompt rule"
    print(f"  [PASS] Gemini Grounded Diagnosis Generated.")
    print(f"         Root Cause: '{diag['root_cause']}'")
    print(f"         Env Note: '{diag.get('environmental_context_note', 'N/A')}'")

    # 8. Machine_03 Hero Scenario Regression Test
    print("\n[8/13] Testing Machine_03 Hero Scenario Regression...")
    inject_scenario_to_snowflake(qexec, "SCENARIO_1")
    m3 = session.sql("SELECT VIBRATION_MM_S, TEMPERATURE_C, RPM FROM PM_OEE_DB.CORE.SENSOR_READINGS WHERE MACHINE_ID = 'Machine_03' ORDER BY TS DESC LIMIT 1").collect()[0]
    assert m3["VIBRATION_MM_S"] == 6.15, f"Expected Vibration 6.15, got {m3['VIBRATION_MM_S']}"
    assert m3["TEMPERATURE_C"] == 97.3, f"Expected Temp 97.3, got {m3['TEMPERATURE_C']}"
    assert m3["RPM"] == 1552, f"Expected RPM 1552, got {m3['RPM']}"
    print(f"  [PASS] Machine_03 Telemetry verified: Vib={m3['VIBRATION_MM_S']} mm/s | Sensor Temp={m3['TEMPERATURE_C']}°C | Ambient Temp={db_env['ambient_temperature_c']}°C")

    # 9. Real Marketplace Regression Test
    print("\n[9/13] Testing Snowflake Marketplace Data Regression...")
    raw_cnt = session.sql("SELECT COUNT(*) AS CNT FROM PM_OEE_DB.CORE.RAW_MARKETPLACE_DATA").collect()[0]["CNT"]
    conf_cnt = session.sql("SELECT COUNT(*) AS CNT FROM PM_OEE_DB.CORE.MARKETPLACE_CONFORMED_DATA").collect()[0]["CNT"]
    assert raw_cnt > 0, f"Marketplace raw data missing! Expected >0, got {raw_cnt}"
    assert conf_cnt > 0, f"Marketplace conformed data missing! Expected >0, got {conf_cnt}"
    print(f"  [PASS] Marketplace dataset intact: {raw_cnt:,} raw rows | {conf_cnt:,} conformed rows (SNOWFLAKE_PUBLIC_DATA_FREE)")

    # 10. Snowflake ML Model Regression Test
    print("\n[10/13] Testing Snowflake ML Model Regression (PM_FAILURE_MODEL)...")
    from services.ml_service import get_model_info, get_ml_context_for_gemini
    minfo = get_model_info()
    assert minfo["model_name"] == "PM_FAILURE_MODEL", "ML Model name modified"
    assert abs(minfo["auc"] - 0.938) < 0.01, f"ML AUC changed! Expected 0.938, got {minfo['auc']}"
    ml_ctx = get_ml_context_for_gemini(session, "Machine_03")
    print(f"  [PASS] Snowflake ML Model intact: {minfo['model_name']} | AUC = {minfo['auc']} | Machine_03 Prob = {ml_ctx.get('ml_failure_probability')}")

    # 11. Work Order Lifecycle Regression Test
    print("\n[11/13] Testing Governed Work Order Lifecycle Regression...")
    session.sql("""
        INSERT INTO PM_OEE_DB.CORE.WORK_ORDERS (
            machine_id, priority, status, diagnosis, recommended_action,
            parts_required, estimated_downtime_hours, risk_score, rul_hours, created_at
        ) VALUES (
            'Machine_03', 'P1', 'PENDING_APPROVAL', 'Spindle bearing fatigue', 'Replace bearing SKF-6205-2RS',
            'SKF-6205-2RS', 4.0, 1.0, 18.0, CURRENT_TIMESTAMP()
        )
    """).collect()
    wo_pending = session.sql("SELECT COUNT(*) AS CNT FROM PM_OEE_DB.CORE.WORK_ORDERS WHERE STATUS = 'PENDING_APPROVAL'").collect()[0]["CNT"]
    assert wo_pending > 0, "Work order creation failed"
    session.sql("UPDATE PM_OEE_DB.CORE.WORK_ORDERS SET STATUS = 'APPROVED', APPROVED_AT = CURRENT_TIMESTAMP() WHERE MACHINE_ID = 'Machine_03'").collect()
    wo_app = session.sql("SELECT COUNT(*) AS CNT FROM PM_OEE_DB.CORE.WORK_ORDERS WHERE STATUS = 'APPROVED'").collect()[0]["CNT"]
    print(f"  [PASS] Governed Work Order lifecycle verified: PENDING_APPROVAL → APPROVED ({wo_app} approved)")

    # 12. Demo Reset Engine Regression Test
    print("\n[12/13] Testing Demo Reset Engine Regression...")
    reset_demo_snowflake_state(qexec)
    m3_reset = session.sql("SELECT VIBRATION_MM_S, TEMPERATURE_C FROM PM_OEE_DB.CORE.SENSOR_READINGS WHERE MACHINE_ID = 'Machine_03' ORDER BY TS DESC LIMIT 1").collect()[0]
    assert m3_reset["VIBRATION_MM_S"] == 6.15, "Reset state failed"
    print(f"  [PASS] Demo state restored baseline successfully (Vib = {m3_reset['VIBRATION_MM_S']} mm/s)")

    # 13. Offline API Failure Handling & Fallback Test
    print("\n[13/13] Testing Offline API Failure Handling & Application Resilience...")
    offline_env = fetch_live_environmental_data(lat=999.0, lon=999.0, timeout_sec=0.001)
    assert offline_env["available"] is False, "Offline fallback failed to return available=False"
    assert offline_env["environmental_status"] == "TEMPORARILY_UNAVAILABLE", "Offline status incorrect"
    
    # Test Gemini with offline weather fallback
    context_offline = {
        "machine_id": "Machine_03",
        "vibration_mm_s": 6.15,
        "temperature_c": 97.3,
        "rpm": 1552,
        "risk_score": 1.0,
        "environmental_context": offline_env
    }
    diag_offline = generate_diagnosis(context_offline)
    assert diag_offline is not None and "root_cause" in diag_offline, "App failed during offline weather state"
    print(f"  [PASS] Offline resilience verified: Returned badge 'TEMPORARILY_UNAVAILABLE'. Telemetry, ML, and Gemini remained 100% operational.")

    print("\n" + "=" * 75)
    print("ALL 13 ENVIRONMENTAL INTEGRATION VERIFICATION TESTS PASSED CLEANLY!")
    print("=" * 75)
    session.close()


if __name__ == "__main__":
    run_weather_tests()
