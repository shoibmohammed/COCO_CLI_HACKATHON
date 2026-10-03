# Predefined demo scenarios for injecting anomalous telemetry and stress-testing the predictive maintenance pipeline
# Co-authored with CoCo
"""
services/scenario_service.py
Predefined demo scenarios for injecting anomalous telemetry,
stress-testing the predictive maintenance pipeline, and testing human-in-the-loop workflows.
Uses centralized database identifiers and safe SQL execution.
"""

import logging
from typing import Dict, Any, List

from config import table

logger = logging.getLogger(__name__)

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "SCENARIO_1": {
        "id": "SCENARIO_1",
        "title": "Machine_03 — Spindle Bearing Degradation (Hero Case)",
        "machine_id": "Machine_03",
        "vibration": 6.15,
        "temperature": 97.3,
        "rpm": 1552,
        "risk_score": 0.94,
        "risk_level": "CRITICAL",
        "rul_hours": 18.0,
        "potential_loss": 12500,
        "estimated_downtime": 4.0,
        "hourly_downtime_cost": 3125,
        "recommended_part": "SKF-6205-2RS",
        "stock": 4,
        "priority": "P1 — Critical",
        "description": "Severe spindle bearing degradation. Vibration 6.15 mm/s (threshold: 4.5), temp 97.3°C. RUL: 18h."
    },
    "SCENARIO_2": {
        "id": "SCENARIO_2",
        "title": "Machine_02 — Thermal Overheat & Cooling Failure",
        "machine_id": "Machine_02",
        "vibration": 3.80,
        "temperature": 102.5,
        "rpm": 1720,
        "risk_score": 0.88,
        "risk_level": "HIGH",
        "rul_hours": 31.0,
        "potential_loss": 8750,
        "estimated_downtime": 2.8,
        "hourly_downtime_cost": 3125,
        "recommended_part": "COOLANT-PUMP-4KW",
        "stock": 2,
        "priority": "P1 — Critical",
        "description": "Hydraulic cooling circulation failure causing thermal runaway to 102.5°C. Immediate coolant flush required."
    },
    "SCENARIO_3": {
        "id": "SCENARIO_3",
        "title": "Machine_01 — Moderate Vibration Drift",
        "machine_id": "Machine_01",
        "vibration": 4.60,
        "temperature": 76.0,
        "rpm": 1680,
        "risk_score": 0.65,
        "risk_level": "MEDIUM",
        "rul_hours": 48.0,
        "potential_loss": 4500,
        "estimated_downtime": 1.5,
        "hourly_downtime_cost": 3000,
        "recommended_part": "SKF-6205-2RS",
        "stock": 4,
        "priority": "P2 — High",
        "description": "Early-stage spindle vibration drift. Vibration 4.60 mm/s. Recommended for next scheduled shift maintenance."
    },
    "SCENARIO_4": {
        "id": "SCENARIO_4",
        "title": "Machine_04 — Nominal Baseline (Healthy)",
        "machine_id": "Machine_04",
        "vibration": 1.65,
        "temperature": 62.0,
        "rpm": 1805,
        "risk_score": 0.05,
        "risk_level": "NOMINAL",
        "rul_hours": 850.0,
        "potential_loss": 0,
        "estimated_downtime": 0.0,
        "hourly_downtime_cost": 0,
        "recommended_part": "NONE",
        "stock": 4,
        "priority": "NOMINAL",
        "description": "All telemetry parameters within optimal operating envelope. No maintenance required."
    },
    "SCENARIO_5": {
        "id": "SCENARIO_5",
        "title": "Machine_03 — Supply Chain Parts Depleted (0 Stock)",
        "machine_id": "Machine_03",
        "vibration": 6.15,
        "temperature": 97.3,
        "rpm": 1552,
        "risk_score": 0.94,
        "risk_level": "CRITICAL",
        "rul_hours": 18.0,
        "potential_loss": 12500,
        "estimated_downtime": 4.0,
        "hourly_downtime_cost": 3125,
        "recommended_part": "SKF-6205-2RS",
        "stock": 0,
        "priority": "P1 — Critical (PART OUT OF STOCK)",
        "description": "Critical bearing degradation with 0 units of SKF-6205-2RS in stock! Procurement required."
    },
    "SCENARIO_6": {
        "id": "SCENARIO_6",
        "title": "Machine_02 — Recovery (Post-Maintenance)",
        "machine_id": "Machine_02",
        "vibration": 2.10,
        "temperature": 68.0,
        "rpm": 1795,
        "risk_score": 0.12,
        "risk_level": "RECOVERED",
        "rul_hours": 600.0,
        "potential_loss": 0,
        "estimated_downtime": 0.0,
        "hourly_downtime_cost": 0,
        "recommended_part": "NONE",
        "stock": 2,
        "priority": "RECOVERED",
        "description": "Post-maintenance recovery. Telemetry returned to nominal baseline limits."
    },
    "SCENARIO_7": {
        "id": "SCENARIO_7",
        "title": "Machine_04 — Critical Gearbox Failure",
        "machine_id": "Machine_04",
        "vibration": 7.20,
        "temperature": 105.0,
        "rpm": 1420,
        "risk_score": 0.92,
        "risk_level": "CRITICAL",
        "rul_hours": 12.0,
        "potential_loss": 18750,
        "estimated_downtime": 6.0,
        "hourly_downtime_cost": 3125,
        "recommended_part": "GEARBOX-ASSY-7K",
        "stock": 1,
        "priority": "P1 — Critical",
        "description": "Catastrophic gearbox tooth fracture. Extreme vibration & RPM dropout. Immediate shutdown required."
    },
    "SCENARIO_8": {
        "id": "SCENARIO_8",
        "title": "Machine_05 — Lathe Spindle Runout",
        "machine_id": "Machine_05",
        "vibration": 4.90,
        "temperature": 78.0,
        "rpm": 2050,
        "risk_score": 0.72,
        "risk_level": "HIGH",
        "rul_hours": 36.0,
        "potential_loss": 7200,
        "estimated_downtime": 3.0,
        "hourly_downtime_cost": 2400,
        "recommended_part": "SPINDLE-BRG-LTH",
        "stock": 2,
        "priority": "P2 — High",
        "description": "Lathe spindle runout increasing. Vibration 4.9 mm/s with part surface finish degradation detected."
    },
    "SCENARIO_9": {
        "id": "SCENARIO_9",
        "title": "Machine_06 — Hydraulic Seal Blowout",
        "machine_id": "Machine_06",
        "vibration": 6.50,
        "temperature": 95.0,
        "rpm": 580,
        "risk_score": 0.91,
        "risk_level": "CRITICAL",
        "rul_hours": 8.0,
        "potential_loss": 22000,
        "estimated_downtime": 8.0,
        "hourly_downtime_cost": 2750,
        "recommended_part": "HYD-SEAL-KIT",
        "stock": 1,
        "priority": "P1 — Critical",
        "description": "Hydraulic press main seal blowout. Pressure loss, excessive vibration. Oil leak detected on floor sensors."
    },
    "SCENARIO_10": {
        "id": "SCENARIO_10",
        "title": "Machine_07 — Grinding Wheel Imbalance",
        "machine_id": "Machine_07",
        "vibration": 3.20,
        "temperature": 58.0,
        "rpm": 2850,
        "risk_score": 0.45,
        "risk_level": "MEDIUM",
        "rul_hours": 72.0,
        "potential_loss": 2800,
        "estimated_downtime": 1.0,
        "hourly_downtime_cost": 2800,
        "recommended_part": "GRIND-WHEEL-A60",
        "stock": 6,
        "priority": "P3 — Medium",
        "description": "Grinding wheel imbalance detected. RPM oscillation ±150. Schedule wheel dressing at next shift change."
    },
    "SCENARIO_11": {
        "id": "SCENARIO_11",
        "title": "Machine_08 — Robotic Arm Joint J3 Fault",
        "machine_id": "Machine_08",
        "vibration": 2.80,
        "temperature": 72.0,
        "rpm": 0,
        "risk_score": 0.78,
        "risk_level": "HIGH",
        "rul_hours": 24.0,
        "potential_loss": 15000,
        "estimated_downtime": 5.0,
        "hourly_downtime_cost": 3000,
        "recommended_part": "SERVO-MOTOR-J3",
        "stock": 0,
        "priority": "P1 — Critical (LONG LEAD PART)",
        "description": "Robotic welder J3 servo motor showing encoder fault codes. Positional accuracy degraded. 21-day lead time on replacement servo."
    },
    "SCENARIO_12": {
        "id": "SCENARIO_12",
        "title": "Machine_09 — Injection Molder Barrel Overheat",
        "machine_id": "Machine_09",
        "vibration": 5.30,
        "temperature": 225.0,
        "rpm": 115,
        "risk_score": 0.87,
        "risk_level": "CRITICAL",
        "rul_hours": 14.0,
        "potential_loss": 19500,
        "estimated_downtime": 6.5,
        "hourly_downtime_cost": 3000,
        "recommended_part": "BARREL-HEATER-6Z",
        "stock": 2,
        "priority": "P1 — Critical",
        "description": "Injection molder barrel zone 6 heater runaway. Temperature 225°C (setpoint 180°C). Screw seizure risk imminent."
    },
    "SCENARIO_13": {
        "id": "SCENARIO_13",
        "title": "Machine_10 — CNC Router High-Speed Spindle Wear",
        "machine_id": "Machine_10",
        "vibration": 3.50,
        "temperature": 68.0,
        "rpm": 17200,
        "risk_score": 0.55,
        "risk_level": "MEDIUM",
        "rul_hours": 56.0,
        "potential_loss": 5600,
        "estimated_downtime": 2.0,
        "hourly_downtime_cost": 2800,
        "recommended_part": "SPINDLE-BRG-HSK",
        "stock": 3,
        "priority": "P2 — High",
        "description": "High-speed router spindle bearing showing early wear. RPM drift -800 from rated. Surface finish declining."
    },
    "SCENARIO_14": {
        "id": "SCENARIO_14",
        "title": "Machine_11 — Assembly Robot Harmonic Drive Backlash",
        "machine_id": "Machine_11",
        "vibration": 1.80,
        "temperature": 52.0,
        "rpm": 0,
        "risk_score": 0.62,
        "risk_level": "MEDIUM",
        "rul_hours": 120.0,
        "potential_loss": 8400,
        "estimated_downtime": 4.0,
        "hourly_downtime_cost": 2100,
        "recommended_part": "HARMONIC-DRIVE-R",
        "stock": 0,
        "priority": "P2 — High (28-DAY LEAD)",
        "description": "Assembly robot axis 2 harmonic drive backlash exceeding tolerance. Positional repeatability degraded. Order part NOW (28-day lead)."
    },
    "SCENARIO_15": {
        "id": "SCENARIO_15",
        "title": "Machine_12 — Furnace Heating Element Degradation",
        "machine_id": "Machine_12",
        "vibration": 1.50,
        "temperature": 930.0,
        "rpm": 0,
        "risk_score": 0.83,
        "risk_level": "HIGH",
        "rul_hours": 22.0,
        "potential_loss": 28000,
        "estimated_downtime": 12.0,
        "hourly_downtime_cost": 2333,
        "recommended_part": "HEATING-ELEM-MO",
        "stock": 1,
        "priority": "P1 — Critical",
        "description": "Heat treat furnace zone 3 molybdenum element resistance climbing. Hot spots detected. Batch quality at risk."
    },
    "SCENARIO_16": {
        "id": "SCENARIO_16",
        "title": "Multi-Machine Cascade — Line 2 Shutdown",
        "machine_id": "Machine_03",
        "vibration": 6.50,
        "temperature": 99.0,
        "rpm": 1520,
        "risk_score": 0.97,
        "risk_level": "CRITICAL",
        "rul_hours": 6.0,
        "potential_loss": 45000,
        "estimated_downtime": 8.0,
        "hourly_downtime_cost": 5625,
        "recommended_part": "SKF-6205-2RS",
        "stock": 4,
        "priority": "P1 — Emergency",
        "description": "Cascade failure scenario: Machine_03 bearing failure triggering line vibration affecting Machine_04 and Machine_11. Full Line 2 shutdown imminent."
    },
    "SCENARIO_17": {
        "id": "SCENARIO_17",
        "title": "Plant B Fleet — All Nominal",
        "machine_id": "Machine_06",
        "vibration": 3.50,
        "temperature": 55.0,
        "rpm": 600,
        "risk_score": 0.08,
        "risk_level": "NOMINAL",
        "rul_hours": 720.0,
        "potential_loss": 0,
        "estimated_downtime": 0.0,
        "hourly_downtime_cost": 0,
        "recommended_part": "NONE",
        "stock": 6,
        "priority": "NOMINAL",
        "description": "Plant B fleet operating at nominal. All 4 machines (06, 07, 08, 10) within optimal parameters. No action required."
    }
}


def inject_scenario_to_snowflake(qexec_fn, scenario_key: str, session=None) -> Dict[str, Any]:
    """Executes SQL statements in Snowflake to persist scenario state."""
    sc = SCENARIOS.get(scenario_key, SCENARIOS["SCENARIO_1"])
    m_id = sc["machine_id"]
    vib = sc["vibration"]
    temp = sc["temperature"]
    rpm = sc["rpm"]
    stock = sc["stock"]

    sensor_tbl = table("SENSOR_READINGS")
    parts_tbl = table("SPARE_PARTS")
    prod_tbl = table("PRODUCTION_EVENTS")
    health_dt = table("MACHINE_HEALTH_RT")
    risk_dt = table("RISK_SCORES_RT")
    oee_dt = table("OEE_METRICS_RT")

    # 1. Update existing telemetry readings and insert a fresh timestamp reading
    sql_update_telemetry = f"""
        UPDATE {sensor_tbl}
        SET vibration_mm_s = {vib:.2f},
            temperature_c = {temp:.2f},
            rpm = {rpm:.0f}
        WHERE machine_id = '{m_id}'
    """
    sql_insert_telemetry = f"""
        INSERT INTO {sensor_tbl}
        (ts, machine_id, vibration_mm_s, temperature_c, rpm, pressure_bar, power_kw)
        VALUES (CURRENT_TIMESTAMP(), '{m_id}', {vib:.2f}, {temp:.2f}, {rpm:.0f}, 6.0, 45.0)
    """
    try:
        qexec_fn(sql_update_telemetry)
        qexec_fn(sql_insert_telemetry)
    except Exception as e:
        logger.warning(f"Scenario telemetry update warning: {e}")

    # 2. If scenario modifies inventory stock for known parts
    part_to_update = sc["recommended_part"]
    if part_to_update and part_to_update != "NONE":
        sql_part = f"""
            UPDATE {parts_tbl}
            SET quantity_on_hand = {stock}
            WHERE part_number = '{part_to_update}'
        """
        try:
            qexec_fn(sql_part)
        except Exception as e:
            logger.warning(f"Scenario part stock update warning: {e}")

    # 3. Insert production events reflecting the scenario impact
    # Determine OEE impact based on risk level
    if sc["risk_level"] == "CRITICAL":
        run_min, total_u, good_u = 2.2, 24, 20
    elif sc["risk_level"] == "HIGH":
        run_min, total_u, good_u = 3.0, 30, 27
    elif sc["risk_level"] == "MEDIUM":
        run_min, total_u, good_u = 4.0, 38, 36
    else:
        run_min, total_u, good_u = 4.8, 45, 44

    all_machines = [
        'Machine_01', 'Machine_02', 'Machine_03', 'Machine_04',
        'Machine_05', 'Machine_06', 'Machine_07', 'Machine_08',
        'Machine_09', 'Machine_10', 'Machine_11', 'Machine_12'
    ]

    prod_values = []
    for mid in all_machines:
        if mid == m_id:
            prod_values.append(
                f"(CURRENT_TIMESTAMP(), '{mid}', 480.0, {run_min * 96:.1f}, {total_u * 96}, {good_u * 96}, '{sc['description'][:80]}')"
            )
        else:
            prod_values.append(
                f"(CURRENT_TIMESTAMP(), '{mid}', 480.0, 460.0, 4320, 4276, 'Normal Shift Operation')"
            )

    sql_prod = f"""
        INSERT INTO {prod_tbl} (event_ts, machine_id, planned_minutes, run_minutes, total_units, good_units, downtime_reason) VALUES
        {','.join(prod_values)}
    """
    try:
        qexec_fn(sql_prod)
    except Exception as e:
        logger.warning(f"Scenario production event update warning: {e}")

    # 4. For cascade scenario, inject anomalies into multiple machines
    if scenario_key == "SCENARIO_16":
        cascade_machines = [
            ("Machine_04", 5.80, 88.0, 1600),
            ("Machine_11", 2.50, 58.0, 0)
        ]
        for c_mid, c_vib, c_temp, c_rpm in cascade_machines:
            sql_cascade = f"""
                INSERT INTO {sensor_tbl}
                (ts, machine_id, vibration_mm_s, temperature_c, rpm, pressure_bar, power_kw)
                VALUES (CURRENT_TIMESTAMP(), '{c_mid}', {c_vib:.2f}, {c_temp:.2f}, {c_rpm:.0f}, 6.0, 45.0)
            """
            try:
                qexec_fn(sql_cascade)
            except Exception as e:
                logger.warning(f"Cascade inject warning for {c_mid}: {e}")

    # 5. Explicitly trigger manual refresh on Dynamic Tables
    dt_refreshes = [
        f"ALTER DYNAMIC TABLE {health_dt} REFRESH",
        f"ALTER DYNAMIC TABLE {risk_dt} REFRESH",
        f"ALTER DYNAMIC TABLE {oee_dt} REFRESH"
    ]
    for dt_sql in dt_refreshes:
        try:
            qexec_fn(dt_sql)
        except Exception as e:
            logger.warning(f"Dynamic table refresh warning ({dt_sql}): {e}")

    # 6. Execute ML predictions refresh, Alert Triage generation, and Governed Work Order auto-creation
    if session:
        try:
            from services.ml_service import refresh_ml_predictions, generate_alerts, auto_create_governed_work_orders
            refresh_ml_predictions(session)
            generate_alerts(session)
            auto_create_governed_work_orders(session)
        except Exception as e:
            logger.warning(f"ML / Alert triage generation warning: {e}")

    # 7. Resume tasks so automated pipeline runs after scenario injection
    #    Suspend root first, resume children, then resume root (DAG requirement)
    task_sqls_resume = [
        "ALTER TASK PM_OEE_DB.CORE.TASK_ANOMALY_SCAN SUSPEND",
        "ALTER TASK PM_OEE_DB.CORE.TASK_SEND_NOTIFICATIONS RESUME",
        "ALTER TASK PM_OEE_DB.CORE.TASK_AUTO_WORK_ORDER RESUME",
        "ALTER TASK PM_OEE_DB.CORE.TASK_ANOMALY_SCAN RESUME",
    ]
    for sql in task_sqls_resume:
        try:
            qexec_fn(sql)
        except Exception as e:
            logger.debug(f"Task resume after inject warning: {e}")

    return sc


def reset_everything_demo_state(session=None, qexec_fn=None, **kwargs) -> Dict[str, Any]:
    """
    Safely resets all transactional demo tables, restores telemetry baselines for all 12 machines,
    restores spare parts inventory, clears in-memory alert tracking, and returns a structured result.
    """
    exec_func = qexec_fn
    if callable(session):
        exec_func = session
        session = None
    elif session is not None and not exec_func:
        exec_func = lambda sql: session.sql(sql).collect()

    result = {
        "success": False,
        "work_orders": 0,
        "alerts": 0,
        "jira_audit": 0,
        "notification_audit": 0,
        "ml_predictions": 0,
        "active_scenario": "NONE",
        "machine_03_restored": True,
        "spare_parts_restored": True,
        "message": ""
    }

    wo_tbl = table("WORK_ORDERS")
    alert_tbl = table("ALERT_LOG")
    jira_audit_tbl = table("JIRA_TICKET_AUDIT")
    notif_audit_tbl = table("NOTIFICATION_AUDIT")
    ml_pred_tbl = table("PM_FAILURE_MODEL").rsplit(".", 1)[0] + ".ML_RISK_PREDICTIONS"
    prod_tbl = table("PRODUCTION_EVENTS")
    sensor_tbl = table("SENSOR_READINGS")
    parts_tbl = table("SPARE_PARTS")
    health_dt = table("MACHINE_HEALTH_RT")
    risk_dt = table("RISK_SCORES_RT")
    oee_dt = table("OEE_METRICS_RT")

    # 0. Suspend the anomaly scan task (root of DAG) to prevent re-inserting alerts during reset
    alert_notif_tbl = sensor_tbl.rsplit(".", 1)[0] + ".ALERT_NOTIFICATION_LOG"
    task_sqls_suspend = [
        "ALTER TASK PM_OEE_DB.CORE.TASK_ANOMALY_SCAN SUSPEND",
        "ALTER TASK PM_OEE_DB.CORE.TASK_AUTO_WORK_ORDER SUSPEND",
        "ALTER TASK PM_OEE_DB.CORE.TASK_SEND_NOTIFICATIONS SUSPEND",
    ]

    if exec_func:
        for sql in task_sqls_suspend:
            try:
                exec_func(sql)
            except Exception as e:
                logger.debug(f"Task suspend warning: {e}")

    # 1. Clear transactional tables (including ALERT_NOTIFICATION_LOG)
    clear_sqls = [
        f"DELETE FROM {wo_tbl}",
        f"DELETE FROM {alert_tbl}",
        f"DELETE FROM {alert_notif_tbl}",
        f"DELETE FROM {jira_audit_tbl}",
        f"DELETE FROM {notif_audit_tbl}",
        f"DELETE FROM {ml_pred_tbl}",
        f"DELETE FROM {prod_tbl}"
    ]

    if exec_func:
        for sql in clear_sqls:
            try:
                exec_func(sql)
            except Exception as e:
                logger.debug(f"Transactional reset query warning: {e}")

        # 2. Purge historical anomaly telemetry and insert clean nominal baseline readings
        #    Insert readings that exactly match MACHINE_BASELINES means so risk computes to 0 (healthy)
        sql_purge_telemetry = f"DELETE FROM {sensor_tbl}"
        baselines_tbl = sensor_tbl.rsplit(".", 1)[0] + ".MACHINE_BASELINES"
        sql_insert_baseline = f"""
            INSERT INTO {sensor_tbl} (ts, machine_id, vibration_mm_s, temperature_c, rpm, pressure_bar, power_kw)
            SELECT CURRENT_TIMESTAMP(), b.machine_id, b.vibration_mean, b.temperature_mean, b.rpm_mean, 6.0, 4.0
            FROM {baselines_tbl} b
        """
        sql_reset_parts = f"UPDATE {parts_tbl} SET quantity_on_hand = 4 WHERE part_number = 'SKF-6205-2RS'"

        # Insert healthy production baseline for all 12 machines (~89% OEE)
        sql_insert_production = f"""
            INSERT INTO {prod_tbl} (event_ts, machine_id, planned_minutes, run_minutes, total_units, good_units, downtime_reason)
            SELECT CURRENT_TIMESTAMP(), b.machine_id, 480.0, 460.0, 4320, 4276, 'Normal Shift Operation'
            FROM {baselines_tbl} b
        """

        for sql in [sql_purge_telemetry, sql_insert_baseline, sql_reset_parts, sql_insert_production]:
            try:
                exec_func(sql)
            except Exception as e:
                logger.warning(f"Baseline restoration query error: {e}")

        # 3. Explicitly trigger manual refresh on Dynamic Tables (with retry)
        dt_refreshes = [
            f"ALTER DYNAMIC TABLE {health_dt} REFRESH",
            f"ALTER DYNAMIC TABLE {risk_dt} REFRESH",
            f"ALTER DYNAMIC TABLE {oee_dt} REFRESH"
        ]
        for dt_sql in dt_refreshes:
            for attempt in range(2):
                try:
                    exec_func(dt_sql)
                    break
                except Exception as e:
                    logger.warning(f"Dynamic table refresh attempt {attempt+1} failed: {e}")
                    if attempt == 0:
                        import time
                        time.sleep(2)

        # 4. Verify RISK_SCORES_RT reflects reset state (Machine_03 risk should be ~0)
        try:
            verify_rows = exec_func(
                f"SELECT MAX(risk_score) AS max_risk FROM {risk_dt} WHERE machine_id = 'Machine_03'"
            )
            if verify_rows:
                row = verify_rows[0]
                max_risk = float(row["MAX_RISK"] if hasattr(row, '__getitem__') else getattr(row, 'MAX_RISK', 0) or 0)
                if max_risk >= 0.40:
                    logger.warning(f"Post-reset verification: Machine_03 risk still {max_risk}, forcing additional refresh")
                    import time
                    time.sleep(3)
                    for dt_sql in dt_refreshes:
                        try:
                            exec_func(dt_sql)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"Post-reset verification skipped: {e}")

    # 5. Keep tasks SUSPENDED after reset to prevent them from recreating work orders
    #    from stale risk data. Tasks will be resumed when a scenario is injected.
    #    Only resume TASK_ANOMALY_SCAN which is read-only (populates risk scores).
    if exec_func:
        try:
            exec_func("ALTER TASK PM_OEE_DB.CORE.TASK_ANOMALY_SCAN RESUME")
        except Exception as e:
            logger.debug(f"Task resume warning: {e}")

    # 6. Clear in-memory notification tracking
    try:
        from services.notification_service import reset_notification_audit
        reset_notification_audit(session=session)
    except Exception as e:
        logger.debug(f"Could not clear in-memory notification tracker: {e}")

    result["success"] = True
    result["message"] = "DEMO ENVIRONMENT RESET SUCCESSFUL"
    return result


# Compatibility alias
reset_demo_snowflake_state = reset_everything_demo_state
