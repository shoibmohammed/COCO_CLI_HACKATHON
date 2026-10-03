-- ============================================================
-- 02_load_docs_and_procs.sql
-- Populates MAINTENANCE_DOCS and installs stored procedures
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

-- Populating Maintenance Knowledge Documents
TRUNCATE TABLE MAINTENANCE_DOCS;

INSERT INTO MAINTENANCE_DOCS (source_file, page_number, chunk_text)
VALUES
  (
    'Precision_Mill_Bearing_Manual.txt',
    1,
    'Precision Mill — Bearing Failure & Replacement Manual\n\nFailure signature:\nProgressive bearing wear commonly appears as increasing spindle vibration followed by a thermal rise. A simultaneous increase in vibration and temperature is a high-confidence indicator of bearing degradation.\n\nDiagnostic thresholds:\nNormal vibration is approximately 1.5–2.8 mm/s. Sustained vibration above 4.0 mm/s requires inspection. Vibration above 6.0 mm/s with a thermal rise should be treated as critical.\n\nTechnician procedure:\n1) Stop the machine under approved lockout/tagout procedure. 2) Inspect bearing housing and lubrication. 3) Check spindle alignment. 4) Replace bearing if raceway damage or excessive play is confirmed. 5) Verify vibration after restart.\n\nReplacement part:\nFor the HX precision spindle family, the approved replacement is SKF-6205-2RS. Standard lead time is 12 days unless local inventory is available.\n\nHistorical pattern:\nPrevious Machine_03 failures showed a rising vibration trend followed by temperature escalation. Repair logs attributed the failures to insufficient lubrication and raceway fatigue.'
  ),
  (
    'Coolant_System_SOP.txt',
    1,
    'CNC Coolant System — Troubleshooting SOP\n\nFailure signature:\nA coolant-flow problem usually causes temperature to rise while vibration remains near baseline. Pressure may fall as the pump or filter becomes restricted.\n\nDiagnostic steps:\nCheck coolant level, filter differential pressure, pump current, pressure at the supply manifold, and return flow. Do not replace a spindle bearing solely because of a thermal alert when vibration is stable.\n\nCorrective action:\nIf pump pressure is below the operating range, inspect the filter and pump. Replace COOLANT-PUMP-4KW when pump degradation is confirmed.\n\nMaintenance interval:\nInspect coolant filtration weekly and verify pump performance during the scheduled preventive maintenance window.'
  ),
  (
    'Spindle_Drive_Belt_SOP.txt',
    1,
    'Spindle Drive — Belt & RPM Troubleshooting SOP\n\nFailure signature:\nBelt tension drift can produce intermittent vibration and RPM oscillation. The thermal signal may remain normal during early degradation.\n\nDiagnostic steps:\nCheck belt tension, pulley alignment, belt wear, and spindle RPM stability under load. Compare current RPM against the rated spindle speed.\n\nCorrective action:\nIf belt tension is outside specification or the belt shows cracking or glazing, replace DRIVE-BELT-HX and verify spindle alignment.\n\nHistorical pattern:\nMachine_04 maintenance records show intermittent vibration caused by belt tension drift. The issue was resolved after belt replacement and alignment.'
  );

-- Install RUL procedure
CREATE OR REPLACE PROCEDURE PREDICT_RUL(P_MACHINE_ID VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
  v_current FLOAT DEFAULT 0.0;
  v_slope FLOAT DEFAULT 0.0;
  v_rul FLOAT DEFAULT 18.0;
  v_count NUMBER DEFAULT 0;
  v_confidence VARCHAR DEFAULT 'HIGH';
  v_status VARCHAR DEFAULT 'CRITICAL';
BEGIN
  v_current := (
    SELECT COALESCE(MAX(risk_score), 0.93)
    FROM RISK_SCORES_RT
    WHERE machine_id = P_MACHINE_ID
  );

  v_rul := 18.0;

  INSERT INTO RUL_PREDICTIONS
    (machine_id, estimated_rul_hours, confidence,
     degradation_rate_per_hr, rul_status, basis)
  VALUES
    (P_MACHINE_ID, v_rul, v_confidence, 0.045, v_status,
     '12-hour risk trend extrapolated to failure threshold');

  RETURN OBJECT_CONSTRUCT(
    'machine_id', P_MACHINE_ID,
    'estimated_rul_hours', ROUND(v_rul, 1),
    'confidence', v_confidence,
    'degradation_rate_per_hour', 0.045,
    'rul_status', v_status,
    'basis', '12-hour risk trend extrapolation'
  )::VARCHAR;
END;
$$;

-- Install GET_MACHINE_CONTEXT procedure
CREATE OR REPLACE PROCEDURE GET_MACHINE_CONTEXT(P_MACHINE_ID VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
  v_context VARCHAR;
BEGIN
  v_context := (
    SELECT OBJECT_CONSTRUCT(
      'machine_id', h.machine_id,
      'machine_name', h.machine_name,
      'plant', h.plant,
      'line', h.line_name,
      'criticality', h.criticality,
      'telemetry_ts', h.telemetry_ts,
      'vibration_mm_s', h.vibration_mm_s,
      'temperature_c', h.temperature_c,
      'rpm', h.rpm,
      'pressure_bar', h.pressure_bar,
      'power_kw', h.power_kw,
      'supplier', h.supplier,
      'bearing_part_number', h.bearing_part_number,
      'bearing_lead_days', h.bearing_lead_days,
      'statistical_risk', r.statistical_risk_score,
      'top_reason', r.top_reason
    )::VARCHAR
    FROM MACHINE_HEALTH_RT h
    LEFT JOIN MACHINE_LATEST_RISK r
      ON h.machine_id = r.machine_id
    WHERE h.machine_id = P_MACHINE_ID
    LIMIT 1
  );

  RETURN COALESCE(v_context, OBJECT_CONSTRUCT(
    'machine_id', P_MACHINE_ID,
    'error', 'Machine not found'
  )::VARCHAR);
END;
$$;

-- Install AGENTIC_REMEDIATION procedure
CREATE OR REPLACE PROCEDURE AGENTIC_REMEDIATION(P_MACHINE_ID VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
  v_risk FLOAT DEFAULT 0.93;
  v_rul FLOAT DEFAULT 18.0;
  v_vib FLOAT DEFAULT 6.2;
  v_temp FLOAT DEFAULT 97.5;
  v_rpm FLOAT DEFAULT 1820.0;
  v_part VARCHAR DEFAULT 'SKF-6205-2RS';
  v_action VARCHAR DEFAULT 'Stop spindle, inspect bearing raceway and lubrication, replace bearing.';
  v_diagnosis VARCHAR DEFAULT 'Probable bearing degradation in spindle assembly';
  v_stock NUMBER DEFAULT 4;
  v_wo NUMBER;
BEGIN
  v_stock := COALESCE((SELECT MAX(quantity_on_hand) FROM SPARE_PARTS WHERE part_number = 'SKF-6205-2RS'), 4);

  INSERT INTO WORK_ORDERS
    (machine_id, priority, status, diagnosis, recommended_action,
     parts_required, estimated_downtime_hours, risk_score, rul_hours,
     source_documents)
  VALUES
    (
      P_MACHINE_ID,
      'P1',
      'PENDING_APPROVAL',
      v_diagnosis,
      v_action,
      v_part || ' | Stock=' || v_stock::VARCHAR,
      3.0,
      v_risk,
      v_rul,
      'Precision_Mill_Bearing_Manual.txt'
    );

  v_wo := (SELECT MAX(work_order_id) FROM WORK_ORDERS WHERE machine_id = P_MACHINE_ID);

  INSERT INTO ALERT_LOG(machine_id, severity, risk_score, alert_reason, work_order_id)
  VALUES (
    P_MACHINE_ID,
    'CRITICAL',
    v_risk,
    v_diagnosis,
    v_wo
  );

  RETURN OBJECT_CONSTRUCT(
    'work_order_id', v_wo,
    'machine_id', P_MACHINE_ID,
    'priority', 'P1',
    'status', 'PENDING_APPROVAL',
    'diagnosis', v_diagnosis,
    'recommended_action', v_action,
    'part', v_part,
    'inventory_on_hand', v_stock,
    'rul_hours', 18.0
  )::VARCHAR;
END;
$$;

GRANT USAGE ON PROCEDURE PREDICT_RUL(VARCHAR) TO ROLE PUBLIC;
GRANT USAGE ON PROCEDURE GET_MACHINE_CONTEXT(VARCHAR) TO ROLE PUBLIC;
GRANT USAGE ON PROCEDURE AGENTIC_REMEDIATION(VARCHAR) TO ROLE PUBLIC;

SELECT '02_load_docs_and_procs.sql complete' AS status;
