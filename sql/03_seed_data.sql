-- ============================================================
-- 03_seed_data.sql
-- Direct SQL data seeder for 4 machines, degradation scenario, ERP, spare parts, and OEE
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

-- Clear existing data
TRUNCATE TABLE MACHINE_MASTER;
TRUNCATE TABLE MACHINE_BASELINES;
TRUNCATE TABLE ERP_ASSETS;
TRUNCATE TABLE SPARE_PARTS;
TRUNCATE TABLE MAINTENANCE_HISTORY;
TRUNCATE TABLE SENSOR_READINGS;
TRUNCATE TABLE PRODUCTION_EVENTS;
TRUNCATE TABLE WORK_ORDERS;
TRUNCATE TABLE ALERT_LOG;
TRUNCATE TABLE RUL_PREDICTIONS;

-- 1. Master machines
INSERT INTO MACHINE_MASTER (machine_id, machine_name, plant, line_name, machine_type, rated_rpm, ideal_cycle_seconds, criticality, commissioned_date)
VALUES
  ('Machine_01', 'CNC Spindle A', 'Plant A', 'Line 1', 'CNC', 1500, 6, 'MEDIUM', '2022-03-15'),
  ('Machine_02', 'CNC Spindle B', 'Plant A', 'Line 1', 'CNC', 1500, 6, 'HIGH', '2021-08-20'),
  ('Machine_03', 'Precision Mill C', 'Plant A', 'Line 2', 'MILL', 1800, 5, 'CRITICAL', '2020-11-10'),
  ('Machine_04', 'Precision Mill D', 'Plant A', 'Line 2', 'MILL', 1800, 5, 'HIGH', '2023-01-05');

-- 2. Baselines
INSERT INTO MACHINE_BASELINES (machine_id, vibration_mean, vibration_std, temperature_mean, temperature_std, rpm_mean, rpm_std)
VALUES
  ('Machine_01', 2.0, 0.30, 65.0, 3.0, 1500, 25.0),
  ('Machine_02', 2.0, 0.30, 65.0, 3.0, 1500, 25.0),
  ('Machine_03', 2.2, 0.30, 65.0, 3.0, 1800, 25.0),
  ('Machine_04', 2.2, 0.30, 65.0, 3.0, 1800, 25.0);

-- 3. ERP Assets
INSERT INTO ERP_ASSETS (machine_id, supplier, asset_model, warranty_end, next_planned_maintenance, bearing_part_number, bearing_lead_days, maintenance_contract)
VALUES
  ('Machine_01', 'NTN Manufacturing', 'HX-01', '2027-05-10', '2026-08-25', 'NTN-6204', 5, 'Gold'),
  ('Machine_02', 'SKF Industrial', 'HX-02', '2027-04-15', '2026-08-20', 'SKF-6306-2RS', 7, 'Gold'),
  ('Machine_03', 'SKF Industrial', 'HX-03', '2027-03-30', '2026-08-18', 'SKF-6205-2RS', 12, 'Gold'),
  ('Machine_04', 'NTN Manufacturing', 'HX-04', '2027-06-01', '2026-08-28', 'DRIVE-BELT-HX', 5, 'Gold');

-- 4. Spare Parts
INSERT INTO SPARE_PARTS (part_number, part_description, supplier, quantity_on_hand, reorder_point, unit_cost_usd, lead_time_days, compatible_machine_type)
VALUES
  ('SKF-6205-2RS', 'High precision sealed bearing', 'SKF Industrial', 4, 6, 185.00, 12, 'MILL'),
  ('SKF-6306-2RS', 'Heavy-duty spindle bearing', 'SKF Industrial', 5, 4, 68.00, 12, 'MILL'),
  ('COOLANT-PUMP-4KW', 'Coolant circulation pump', 'FlowTech', 3, 2, 315.00, 7, 'CNC'),
  ('DRIVE-BELT-HX', 'Spindle drive belt', 'MotionWorks', 8, 3, 95.00, 5, 'CNC');

-- 5. Maintenance History
INSERT INTO MAINTENANCE_HISTORY (machine_id, maintenance_ts, failure_code, failure_type, root_cause, part_replaced, downtime_hours, repair_cost_usd, technician, notes)
VALUES
  ('Machine_03', '2026-05-28 10:00:00', 'E42', 'Bearing wear', 'Insufficient lubrication', 'SKF-6205-2RS', 4.0, 840.00, 'R. Sen', 'Vibration rose before thermal excursion.'),
  ('Machine_03', '2026-02-01 14:30:00', 'E42', 'Bearing wear', 'Raceway fatigue', 'SKF-6205-2RS', 3.5, 760.00, 'A. Roy', 'High vibration and temperature were observed together.'),
  ('Machine_02', '2026-06-20 09:15:00', 'T17', 'Thermal overload', 'Coolant flow restriction', 'COOLANT-PUMP-4KW', 2.0, 510.00, 'S. Das', 'Temperature increased while vibration remained stable.'),
  ('Machine_04', '2026-07-10 11:00:00', 'V09', 'Drive vibration', 'Belt tension drift', 'DRIVE-BELT-HX', 2.5, 390.00, 'M. Ghosh', 'RPM oscillation and vibration increased intermittently.');

-- 6. Generate Telemetry (576 records)
INSERT INTO SENSOR_READINGS (ts, machine_id, vibration_mm_s, temperature_c, rpm, pressure_bar, power_kw)
SELECT
  DATEADD('minute', -5 * seq.seq, CURRENT_TIMESTAMP()) AS ts,
  m.machine_id,
  CASE
    WHEN m.machine_id = 'Machine_03' AND seq.seq <= 144
      THEN ROUND(2.1 + (144 - seq.seq)/144.0 * 4.1 + UNIFORM(-0.15, 0.15, RANDOM()), 2)
    WHEN m.machine_id = 'Machine_02' AND seq.seq <= 72
      THEN ROUND(2.0 + UNIFORM(-0.1, 0.1, RANDOM()), 2)
    ELSE ROUND(2.0 + UNIFORM(-0.2, 0.2, RANDOM()), 2)
  END AS vibration_mm_s,
  CASE
    WHEN m.machine_id = 'Machine_03' AND seq.seq <= 144
      THEN ROUND(65.0 + (144 - seq.seq)/144.0 * 32.5 + UNIFORM(-0.8, 0.8, RANDOM()), 1)
    WHEN m.machine_id = 'Machine_02' AND seq.seq <= 72
      THEN ROUND(65.0 + (72 - seq.seq)/72.0 * 28.0 + UNIFORM(-0.8, 0.8, RANDOM()), 1)
    ELSE ROUND(65.0 + UNIFORM(-1.0, 1.0, RANDOM()), 1)
  END AS temperature_c,
  CASE
    WHEN m.machine_id = 'Machine_03' AND seq.seq <= 144
      THEN ROUND(m.rated_rpm - (144 - seq.seq)/144.0 * 250.0 + UNIFORM(-10, 10, RANDOM()), 0)
    ELSE ROUND(m.rated_rpm + UNIFORM(-12, 12, RANDOM()), 0)
  END AS rpm,
  ROUND(6.0 + UNIFORM(-0.2, 0.2, RANDOM()), 2) AS pressure_bar,
  ROUND(4.0 + UNIFORM(-0.2, 0.2, RANDOM()), 2) AS power_kw
FROM MACHINE_MASTER m
CROSS JOIN (
  SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1 AS seq
  FROM TABLE(GENERATOR(ROWCOUNT => 144))
) seq;

-- 7. Generate Production Events for OEE
INSERT INTO PRODUCTION_EVENTS (machine_id, event_ts, planned_minutes, run_minutes, total_units, good_units, downtime_reason)
SELECT
  m.machine_id,
  DATEADD('minute', -5 * seq.seq, CURRENT_TIMESTAMP()) AS event_ts,
  5.0 AS planned_minutes,
  CASE
    WHEN m.machine_id = 'Machine_03' AND seq.seq <= 144 THEN 2.2
    WHEN m.machine_id = 'Machine_02' AND seq.seq <= 72 THEN 3.0
    ELSE 4.8
  END AS run_minutes,
  CASE
    WHEN m.machine_id = 'Machine_03' AND seq.seq <= 144 THEN 24
    ELSE 45
  END AS total_units,
  CASE
    WHEN m.machine_id = 'Machine_03' AND seq.seq <= 144 THEN 20
    ELSE 44
  END AS good_units,
  CASE
    WHEN m.machine_id = 'Machine_03' AND seq.seq <= 144 THEN 'Bearing vibration degradation'
    WHEN m.machine_id = 'Machine_02' AND seq.seq <= 72 THEN 'Coolant thermal warning'
    ELSE 'Normal operation'
  END AS downtime_reason
FROM MACHINE_MASTER m
CROSS JOIN (
  SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1 AS seq
  FROM TABLE(GENERATOR(ROWCOUNT => 144))
) seq;

-- Seed initial pending Work Order for Machine_03
INSERT INTO WORK_ORDERS
  (machine_id, priority, status, diagnosis, recommended_action, parts_required, estimated_downtime_hours, risk_score, rul_hours, source_documents)
VALUES
  (
    'Machine_03', 'P1', 'PENDING_APPROVAL',
    'Probable bearing degradation in spindle assembly',
    'Stop spindle, inspect bearing raceway and lubrication, replace bearing.',
    'SKF-6205-2RS | Stock=4',
    3.0, 0.93, 18.0,
    'Precision_Mill_Bearing_Manual.txt'
  );

SELECT '03_seed_data.sql complete' AS status;
