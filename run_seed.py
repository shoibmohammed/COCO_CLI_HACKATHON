import os
import sys
from datetime import datetime, timedelta
import random
import snowflake.connector

try:
    import toml
except ImportError:
    toml = None

sec_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
sf_sec = {}
if toml and os.path.exists(sec_path):
    try:
        sf_sec = toml.load(sec_path).get("snowflake", {})
    except Exception:
        pass

ACCOUNT = os.environ.get("SNOWFLAKE_ACCOUNT") or sf_sec.get("account") or ""
USER = os.environ.get("SNOWFLAKE_USER") or sf_sec.get("user") or ""
PASSWORD = os.environ.get("SNOWFLAKE_PASSWORD") or sf_sec.get("password") or ""
WAREHOUSE = os.environ.get("SNOWFLAKE_WAREHOUSE") or sf_sec.get("warehouse") or "PM_OEE_WH"
DATABASE = os.environ.get("SNOWFLAKE_DATABASE") or sf_sec.get("database") or "PM_OEE_DB"
SCHEMA = os.environ.get("SNOWFLAKE_SCHEMA") or sf_sec.get("schema") or "CORE"

print("Connecting to Snowflake...")
conn = snowflake.connector.connect(
    account=ACCOUNT,
    user=USER,
    password=PASSWORD,
    warehouse=WAREHOUSE,
    database=DATABASE,
    schema=SCHEMA,
    role="ACCOUNTADMIN"
)

cursor = conn.cursor()
print("Connected successfully. Seeding manufacturing plant data...")

MACHINES = [
    ("Machine_01", "CNC Spindle A", "Plant A", "Line 1", "CNC", 1500, 6, "MEDIUM"),
    ("Machine_02", "CNC Spindle B", "Plant A", "Line 1", "CNC", 1500, 6, "HIGH"),
    ("Machine_03", "Precision Mill C", "Plant A", "Line 2", "MILL", 1800, 5, "CRITICAL"),
    ("Machine_04", "Precision Mill D", "Plant A", "Line 2", "MILL", 1800, 5, "HIGH"),
]

# Reset tables
for table in [
    "SENSOR_READINGS", "PRODUCTION_EVENTS", "MAINTENANCE_HISTORY",
    "SPARE_PARTS", "ERP_ASSETS", "MACHINE_BASELINES", "MACHINE_MASTER",
    "ML_RISK_PREDICTIONS", "RUL_PREDICTIONS", "WORK_ORDERS", "ALERT_LOG"
]:
    cursor.execute(f"TRUNCATE TABLE IF EXISTS {table}")

# Master data
random.seed(7)
for mid, name, plant, line, mtype, rpm, cycle, criticality in MACHINES:
    comm_date = (datetime.now().date() - timedelta(days=random.randint(500, 1800))).strftime("%Y-%m-%d")
    cursor.execute(f"""
        INSERT INTO MACHINE_MASTER (machine_id, machine_name, plant, line_name, machine_type, rated_rpm, ideal_cycle_seconds, criticality, commissioned_date)
        VALUES ('{mid}', '{name}', '{plant}', '{line}', '{mtype}', {rpm}, {cycle}, '{criticality}', '{comm_date}')
    """)
    
    vib_mean = 2.0 if "CNC" in mtype else 2.2
    cursor.execute(f"""
        INSERT INTO MACHINE_BASELINES (machine_id, vibration_mean, vibration_std, temperature_mean, temperature_std, rpm_mean, rpm_std)
        VALUES ('{mid}', {vib_mean}, 0.30, 65.0, 3.0, {rpm}, 25.0)
    """)
    
    supplier = "SKF Industrial" if mid in ("Machine_02", "Machine_03") else "NTN Manufacturing"
    lead_days = 12 if mid == "Machine_03" else 5
    maint_date = (datetime.now().date() + timedelta(days=random.randint(5, 20))).strftime("%Y-%m-%d")
    warr_date = (datetime.now().date() + timedelta(days=280)).strftime("%Y-%m-%d")
    
    cursor.execute(f"""
        INSERT INTO ERP_ASSETS (machine_id, supplier, asset_model, warranty_end, next_planned_maintenance, bearing_part_number, bearing_lead_days, maintenance_contract)
        VALUES ('{mid}', '{supplier}', 'HX-{mid[-2:]}', '{warr_date}', '{maint_date}', 'SKF-6205-2RS', {lead_days}, 'Gold')
    """)

parts = [
    ("SKF-6205-2RS", "High precision sealed bearing", "SKF Industrial", 4, 6, 185.00, 12, "MILL"),
    ("SKF-6306-2RS", "Heavy-duty spindle bearing", "SKF Industrial", 5, 4, 68.00, 12, "MILL"),
    ("COOLANT-PUMP-4KW", "Coolant circulation pump", "FlowTech", 3, 2, 315.00, 7, "CNC"),
    ("DRIVE-BELT-HX", "Spindle drive belt", "MotionWorks", 8, 3, 95.00, 5, "CNC"),
]
for pnum, desc, supp, qty, reorder, cost, lead, mtype in parts:
    cursor.execute(f"""
        INSERT INTO SPARE_PARTS (part_number, part_description, supplier, quantity_on_hand, reorder_point, unit_cost_usd, lead_time_days, compatible_machine_type)
        VALUES ('{pnum}', '{desc}', '{supp}', {qty}, {reorder}, {cost}, {lead}, '{mtype}')
    """)

history = [
    ("Machine_03", (datetime.now()-timedelta(days=75)).strftime("%Y-%m-%d %H:%M:%S"), "E42", "Bearing wear", "Insufficient lubrication", "SKF-6205-2RS", 4.0, 840, "R. Sen", "Vibration rose before thermal excursion."),
    ("Machine_03", (datetime.now()-timedelta(days=190)).strftime("%Y-%m-%d %H:%M:%S"), "E42", "Bearing wear", "Raceway fatigue", "SKF-6205-2RS", 3.5, 760, "A. Roy", "High vibration and temperature were observed together."),
    ("Machine_02", (datetime.now()-timedelta(days=48)).strftime("%Y-%m-%d %H:%M:%S"), "T17", "Thermal overload", "Coolant flow restriction", "COOLANT-PUMP-4KW", 2.0, 510, "S. Das", "Temperature increased while vibration remained stable."),
    ("Machine_04", (datetime.now()-timedelta(days=32)).strftime("%Y-%m-%d %H:%M:%S"), "V09", "Drive vibration", "Belt tension drift", "DRIVE-BELT-HX", 2.5, 390, "M. Ghosh", "RPM oscillation and vibration increased intermittently."),
]
for mid, mts, fcode, ftype, root, part, dtime, cost, tech, notes in history:
    cursor.execute(f"""
        INSERT INTO MAINTENANCE_HISTORY (machine_id, maintenance_ts, failure_code, failure_type, root_cause, part_replaced, downtime_hours, repair_cost_usd, technician, notes)
        VALUES ('{mid}', '{mts}', '{fcode}', '{ftype}', '{root}', '{part}', {dtime}, {cost}, '{tech}', '{notes}')
    """)

now = datetime.now().replace(second=0, microsecond=0)
start = now - timedelta(days=3) # 3 days of 5-minute telemetry for high speed seeding

sensor_batch = []
prod_batch = []

for step in range(3 * 24 * 12):
    ts_dt = start + timedelta(minutes=5 * step)
    ts_str = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
    hours_from_now = (now - ts_dt).total_seconds() / 3600.0

    for mid, name, plant, line, mtype, rated_rpm, cycle, criticality in MACHINES:
        vib = 2.0 + random.gauss(0, 0.12)
        temp = 65.0 + random.gauss(0, 1.0)
        rpm = rated_rpm + random.gauss(0, 12)
        pressure = 6.0 + random.gauss(0, 0.15)
        power = 4.0 + random.gauss(0, 0.2)

        # Machine_03 degradation scenario
        if mid == "Machine_03" and hours_from_now <= 14:
            severity = min(1.0, max(0.0, (14 - hours_from_now) / 14))
            vib = 2.0 + severity * 4.2 + random.gauss(0, 0.20)
            temp = 65.0 + severity * 32.0 + random.gauss(0, 1.2)
            rpm = rated_rpm - severity * 240 + random.gauss(0, 18)
            pressure = 6.0 - severity * 0.8 + random.gauss(0, 0.1)
            power = 4.0 + severity * 1.3 + random.gauss(0, 0.15)

        # Machine_02 thermal scenario
        if mid == "Machine_02" and hours_from_now <= 6:
            severity = min(1.0, max(0.0, (6 - hours_from_now) / 6))
            vib = 2.0 + severity * 0.9 + random.gauss(0, 0.15)
            temp = 65.0 + severity * 28.0 + random.gauss(0, 1.0)
            rpm = rated_rpm - severity * 80 + random.gauss(0, 15)

        sensor_batch.append(f"('{ts_str}', '{mid}', {round(max(0.1, vib), 3)}, {round(max(20, temp), 2)}, {round(max(0, rpm), 1)}, {round(max(0, pressure), 2)}, {round(max(0, power), 2)})")

        risk_proxy = min(1.0, max(0.0, ((vib - 2.0) / 3.0) * 0.45 + ((temp - 65.0) / 20.0) * 0.35 + ((rated_rpm - rpm) / 200.0) * 0.20))
        planned = 5.0
        downtime = 0.0 if risk_proxy < 0.35 else min(4.0, 1.0 + risk_proxy * 3.0)
        run = max(0.0, planned - downtime)
        total_units = max(0, int(run * (60 / cycle) * 0.95))
        scrap_rate = min(0.15, 0.01 + risk_proxy * 0.10)
        good_units = max(0, int(total_units * (1 - scrap_rate)))
        reason = "Normal operation" if downtime == 0 else ("Predictive maintenance risk" if risk_proxy >= 0.55 else "Minor stoppage")

        prod_batch.append(f"('{mid}', '{ts_str}', {planned}, {round(run, 2)}, {total_units}, {good_units}, '{reason}')")

# Batch insert SENSOR_READINGS
for i in range(0, len(sensor_batch), 500):
    chunk = ", ".join(sensor_batch[i:i+500])
    cursor.execute(f"INSERT INTO SENSOR_READINGS (ts, machine_id, vibration_mm_s, temperature_c, rpm, pressure_bar, power_kw) VALUES {chunk}")

# Batch insert PRODUCTION_EVENTS
for i in range(0, len(prod_batch), 500):
    chunk = ", ".join(prod_batch[i:i+500])
    cursor.execute(f"INSERT INTO PRODUCTION_EVENTS (machine_id, event_ts, planned_minutes, run_minutes, total_units, good_units, downtime_reason) VALUES {chunk}")

conn.commit()
cursor.close()
conn.close()

print(f"Data seeding complete! Inserted {len(sensor_batch):,} telemetry records and {len(prod_batch):,} production events.")
print("Hero machine MACHINE_03 configured with bearing degradation (Vibration ~6.2 mm/s, Temp ~97°C, RPM ~1820).")
