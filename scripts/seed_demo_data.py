"""
seed_demo_data.py
Run this from a Snowsight Python worksheet with "Run" so it uses
the active Snowflake session. It creates a realistic 7-day manufacturing
history and a degrading failure scenario for the demo.
"""
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from snowflake.snowpark.context import get_active_session
    session = get_active_session()
except Exception:
    from snowflake_connection import get_snowflake_session
    session, status_msg, _ = get_snowflake_session()
    if not session:
        raise RuntimeError(f"Could not connect to Snowflake: {status_msg}")

session.sql("USE DATABASE PM_OEE_DB").collect()
from datetime import datetime, timedelta
import random
import math

random.seed(7)

MACHINES = [
    ("Machine_01", "CNC Spindle A", "Plant A", "Line 1", "CNC", 1500, 6, "MEDIUM"),
    ("Machine_02", "CNC Spindle B", "Plant A", "Line 1", "CNC", 1500, 6, "HIGH"),
    ("Machine_03", "Precision Mill C", "Plant A", "Line 2", "MILL", 1800, 5, "CRITICAL"),
    ("Machine_04", "Precision Mill D", "Plant A", "Line 2", "MILL", 1800, 5, "HIGH"),
]

# Reset demo data. Knowledge documents and ML model are handled by their own scripts.
for table in [
    "SENSOR_READINGS", "PRODUCTION_EVENTS", "MAINTENANCE_HISTORY",
    "SPARE_PARTS", "ERP_ASSETS", "MACHINE_BASELINES", "MACHINE_MASTER",
    "ML_RISK_PREDICTIONS", "RUL_PREDICTIONS", "WORK_ORDERS", "ALERT_LOG"
]:
    session.sql(f"TRUNCATE TABLE {table}").collect()

# Master data
master_rows = []
baseline_rows = []
erp_rows = []
for mid, name, plant, line, mtype, rpm, cycle, criticality in MACHINES:
    master_rows.append({
        "MACHINE_ID": mid, "MACHINE_NAME": name, "PLANT": plant,
        "LINE_NAME": line, "MACHINE_TYPE": mtype, "RATED_RPM": rpm,
        "IDEAL_CYCLE_SECONDS": cycle, "CRITICALITY": criticality,
        "COMMISSIONED_DATE": datetime.now().date() - timedelta(days=random.randint(500, 1800))
    })
    baseline_rows.append({
        "MACHINE_ID": mid,
        "VIBRATION_MEAN": 2.0 if "CNC" in mtype else 2.2,
        "VIBRATION_STD": 0.30,
        "TEMPERATURE_MEAN": 65.0,
        "TEMPERATURE_STD": 3.0,
        "RPM_MEAN": float(rpm),
        "RPM_STD": 25.0
    })
    erp_rows.append({
        "MACHINE_ID": mid,
        "SUPPLIER": "SKF Industrial" if mid in ("Machine_02", "Machine_03") else "NTN Manufacturing",
        "ASSET_MODEL": "HX-" + mid[-2:],
        "WARRANTY_END": datetime.now().date() + timedelta(days=280),
        "NEXT_PLANNED_MAINTENANCE": datetime.now().date() + timedelta(days=random.randint(5, 20)),
        "BEARING_PART_NUMBER": "SKF-6205-2RS",
        "BEARING_LEAD_DAYS": 12 if mid == "Machine_03" else 5,
        "MAINTENANCE_CONTRACT": "Gold"
    })

session.create_dataframe(master_rows).write.mode("append").save_as_table("MACHINE_MASTER")
session.create_dataframe(baseline_rows).write.mode("append").save_as_table("MACHINE_BASELINES")
session.create_dataframe(erp_rows).write.mode("append").save_as_table("ERP_ASSETS")

parts = [
    ("SKF-6205-2RS", "High precision sealed bearing", "SKF Industrial", 14, 6, 42.50, 12, "CNC"),
    ("SKF-6306-2RS", "Heavy-duty spindle bearing", "SKF Industrial", 5, 4, 68.00, 12, "MILL"),
    ("COOLANT-PUMP-4KW", "Coolant circulation pump", "FlowTech", 3, 2, 315.00, 7, "CNC"),
    ("DRIVE-BELT-HX", "Spindle drive belt", "MotionWorks", 8, 3, 95.00, 5, "CNC"),
]
session.create_dataframe(parts, schema=[
    "PART_NUMBER","PART_DESCRIPTION","SUPPLIER","QUANTITY_ON_HAND",
    "REORDER_POINT","UNIT_COST_USD","LEAD_TIME_DAYS","COMPATIBLE_MACHINE_TYPE"
]).write.mode("append").save_as_table("SPARE_PARTS")

# Maintenance history: deliberately include similar bearing failures for RAG.
history = [
    ("Machine_03", datetime.now()-timedelta(days=75), "E42", "Bearing wear", "Insufficient lubrication", "SKF-6205-2RS", 4.0, 840, "R. Sen", "Vibration rose before thermal excursion."),
    ("Machine_03", datetime.now()-timedelta(days=190), "E42", "Bearing wear", "Raceway fatigue", "SKF-6205-2RS", 3.5, 760, "A. Roy", "High vibration and temperature were observed together."),
    ("Machine_02", datetime.now()-timedelta(days=48), "T17", "Thermal overload", "Coolant flow restriction", "COOLANT-PUMP-4KW", 2.0, 510, "S. Das", "Temperature increased while vibration remained stable."),
    ("Machine_04", datetime.now()-timedelta(days=32), "V09", "Drive vibration", "Belt tension drift", "DRIVE-BELT-HX", 2.5, 390, "M. Ghosh", "RPM oscillation and vibration increased intermittently."),
]
session.create_dataframe(history, schema=[
    "MACHINE_ID","MAINTENANCE_TS","FAILURE_CODE","FAILURE_TYPE","ROOT_CAUSE",
    "PART_REPLACED","DOWNTIME_HOURS","REPAIR_COST_USD","TECHNICIAN","NOTES"
]).write.mode("append").save_as_table("MAINTENANCE_HISTORY")

# 7 days of 5-minute telemetry
now = datetime.now().replace(second=0, microsecond=0)
start = now - timedelta(days=7)
sensor_rows = []
production_rows = []

for step in range(7 * 24 * 12):
    ts = start + timedelta(minutes=5 * step)
    hours_from_now = (now - ts).total_seconds() / 3600.0

    for mid, name, plant, line, mtype, rated_rpm, cycle, criticality in MACHINES:
        vib = 2.0 + random.gauss(0, 0.12)
        temp = 65.0 + random.gauss(0, 1.0)
        rpm = rated_rpm + random.gauss(0, 12)
        pressure = 6.0 + random.gauss(0, 0.15)
        power = 4.0 + random.gauss(0, 0.2)

        # Machine_03: progressive bearing degradation during the last 14 hours.
        if mid == "Machine_03" and hours_from_now <= 14:
            severity = min(1.0, max(0.0, (14 - hours_from_now) / 14))
            vib = 2.0 + severity * 5.2 + random.gauss(0, 0.20)
            temp = 65.0 + severity * 27.0 + random.gauss(0, 1.2)
            rpm = rated_rpm - severity * 260 + random.gauss(0, 18)
            pressure = 6.0 - severity * 0.8 + random.gauss(0, 0.1)
            power = 4.0 + severity * 1.3 + random.gauss(0, 0.15)

        # Machine_02: thermal/coolant issue during the last 6 hours.
        if mid == "Machine_02" and hours_from_now <= 6:
            severity = min(1.0, max(0.0, (6 - hours_from_now) / 6))
            vib = 2.0 + severity * 0.9 + random.gauss(0, 0.15)
            temp = 65.0 + severity * 30.0 + random.gauss(0, 1.0)
            rpm = rated_rpm - severity * 80 + random.gauss(0, 15)
            pressure = 6.0 - severity * 1.5 + random.gauss(0, 0.1)
            power = 4.0 + severity * 0.9 + random.gauss(0, 0.15)

        # Machine_04: intermittent vibration warning.
        if mid == "Machine_04" and hours_from_now <= 10 and (step % 9 in (0, 1, 2)):
            vib += 2.0
            rpm -= 80
            power += 0.5

        sensor_rows.append({
            "TS": ts, "MACHINE_ID": mid,
            "VIBRATION_MM_S": round(max(0.1, vib), 3),
            "TEMPERATURE_C": round(max(20, temp), 2),
            "RPM": round(max(0, rpm), 1),
            "PRESSURE_BAR": round(max(0, pressure), 2),
            "POWER_KW": round(max(0, power), 2),
        })

        # Synthetic production/OEE event correlated to machine health.
        risk_proxy = min(1.0, max(
            0.0,
            ((vib - 2.0) / 3.0) * 0.45 +
            ((temp - 65.0) / 20.0) * 0.35 +
            ((rated_rpm - rpm) / 200.0) * 0.20
        ))
        risk_proxy = max(0.0, risk_proxy)

        planned = 5.0
        downtime = 0.0 if risk_proxy < 0.35 else min(4.0, 1.0 + risk_proxy * 3.0)
        run = max(0.0, planned - downtime)
        total_units = max(0, int(run * (60 / cycle) * 0.95))
        scrap_rate = min(0.15, 0.01 + risk_proxy * 0.10)
        good_units = max(0, int(total_units * (1 - scrap_rate)))
        reason = "Normal operation" if downtime == 0 else ("Predictive maintenance risk" if risk_proxy >= 0.55 else "Minor stoppage")
        production_rows.append({
            "MACHINE_ID": mid, "EVENT_TS": ts, "PLANNED_MINUTES": planned,
            "RUN_MINUTES": round(run, 2), "TOTAL_UNITS": total_units,
            "GOOD_UNITS": good_units, "DOWNTIME_REASON": reason
        })

# Write in manageable chunks
for i in range(0, len(sensor_rows), 5000):
    session.create_dataframe(sensor_rows[i:i+5000]).write.mode("append").save_as_table("SENSOR_READINGS")
for i in range(0, len(production_rows), 5000):
    session.create_dataframe(production_rows[i:i+5000]).write.mode("append").save_as_table("PRODUCTION_EVENTS")

print(f"Seeded {len(sensor_rows):,} sensor readings and {len(production_rows):,} production events.")
print("Machine_03 = progressive bearing degradation")
print("Machine_02 = thermal/coolant degradation")
print("Machine_04 = intermittent vibration")
print("Machine_01 = healthy baseline")
