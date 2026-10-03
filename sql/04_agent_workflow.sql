-- ============================================================
-- 04_agent_workflow.sql
-- Creates the governed tools used by the Cortex Agent and MCP.
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

-- ------------------------------------------------------------
-- RUL prediction: trend-based degradation estimate.
-- This is deliberately transparent and auditable; it is not
-- presented as a trained RUL model.
-- ------------------------------------------------------------
CREATE OR REPLACE PROCEDURE PREDICT_RUL(P_MACHINE_ID VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
  v_current FLOAT;
  v_slope FLOAT;
  v_rul FLOAT;
  v_count NUMBER;
  v_confidence VARCHAR;
  v_status VARCHAR;
BEGIN
  WITH base AS (
    SELECT
      ts,
      risk_score,
      MIN(ts) OVER (PARTITION BY machine_id) AS min_ts
    FROM RISK_SCORES_RT
    WHERE machine_id = P_MACHINE_ID
      AND ts >= (
        SELECT DATEADD('hour', -12, MAX(ts))
        FROM RISK_SCORES_RT
        WHERE machine_id = P_MACHINE_ID
      )
  )
  SELECT
    MAX(risk_score),
    REGR_SLOPE(
      risk_score,
      DATEDIFF('second', min_ts, ts) / 3600.0
    ),
    COUNT(*)
  INTO :v_current, :v_slope, :v_count
  FROM base;

  v_current := COALESCE(v_current, 0.0);
  v_slope := COALESCE(v_slope, 0.0);

  IF (v_slope > 0.001) THEN
    v_rul := LEAST(720.0, GREATEST(1.0, (1.0 - v_current) / v_slope));
  ELSE
    v_rul := LEAST(720.0, GREATEST(24.0, (1.0 - v_current) * 168.0));
  END IF;

  IF (v_count >= 100 AND ABS(v_slope) > 0.001) THEN
    v_confidence := 'HIGH';
  ELSEIF (v_count >= 50) THEN
    v_confidence := 'MEDIUM';
  ELSE
    v_confidence := 'LOW';
  END IF;

  IF (v_rul <= 24) THEN
    v_status := 'IMMINENT';
  ELSEIF (v_rul <= 72) THEN
    v_status := 'CRITICAL';
  ELSEIF (v_rul <= 168) THEN
    v_status := 'WATCH';
  ELSE
    v_status := 'HEALTHY';
  END IF;

  INSERT INTO RUL_PREDICTIONS
    (machine_id, estimated_rul_hours, confidence,
     degradation_rate_per_hr, rul_status, basis)
  VALUES
    (P_MACHINE_ID, v_rul, v_confidence, v_slope, v_status,
     '12-hour risk trend extrapolated to failure threshold');

  RETURN OBJECT_CONSTRUCT(
    'machine_id', P_MACHINE_ID,
    'estimated_rul_hours', ROUND(v_rul, 1),
    'confidence', v_confidence,
    'degradation_rate_per_hour', ROUND(v_slope, 5),
    'rul_status', v_status,
    'basis', '12-hour risk trend extrapolation'
  )::VARCHAR;
END;
$$;

-- ------------------------------------------------------------
-- Structured context tool for the Cortex Agent.
-- ------------------------------------------------------------
CREATE OR REPLACE PROCEDURE GET_MACHINE_CONTEXT(P_MACHINE_ID VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
  v_context VARCHAR;
BEGIN
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
    'ml_failure_probability', r.ml_failure_probability,
    'unified_risk', r.unified_risk_score,
    'top_reason', r.top_reason,
    'failure_class', r.failure_class
  )::VARCHAR
  INTO :v_context
  FROM MACHINE_HEALTH_RT h
  LEFT JOIN MACHINE_RISK_UNIFIED r
    ON h.machine_id = r.machine_id
  WHERE h.machine_id = P_MACHINE_ID;

  RETURN COALESCE(v_context, OBJECT_CONSTRUCT(
    'machine_id', P_MACHINE_ID,
    'error', 'Machine not found'
  )::VARCHAR);
END;
$$;

CREATE OR REPLACE PROCEDURE GET_FLEET_CONTEXT()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
  v_context VARCHAR;
BEGIN
  SELECT OBJECT_CONSTRUCT(
    'machine_count', COUNT(*),
    'avg_risk', ROUND(AVG(unified_risk_score), 3),
    'critical_machines', COUNT_IF(unified_risk_score >= 0.75),
    'warning_machines', COUNT_IF(unified_risk_score >= 0.50 AND unified_risk_score < 0.75),
    'open_work_orders', (
      SELECT COUNT(*) FROM WORK_ORDERS
      WHERE status IN ('PENDING_APPROVAL','OPEN')
    ),
    'top_risk_machines',
      ARRAY_AGG(
        OBJECT_CONSTRUCT(
          'machine_id', machine_id,
          'risk', ROUND(unified_risk_score,3),
          'reason', top_reason
        )
      ) WITHIN GROUP (ORDER BY unified_risk_score DESC)
  )::VARCHAR
  INTO :v_context
  FROM MACHINE_RISK_UNIFIED;

  RETURN v_context;
END;
$$;

-- ------------------------------------------------------------
-- Agentic remediation:
-- diagnose → check inventory → create governed work order.
-- The work order is PENDING_APPROVAL: human approval remains in
-- the control loop before any external ticket is created.
-- ------------------------------------------------------------
CREATE OR REPLACE PROCEDURE AGENTIC_REMEDIATION(P_MACHINE_ID VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
DECLARE
  v_risk FLOAT;
  v_rul FLOAT;
  v_vib FLOAT;
  v_temp FLOAT;
  v_rpm FLOAT;
  v_machine_type VARCHAR;
  v_part VARCHAR;
  v_action VARCHAR;
  v_diagnosis VARCHAR;
  v_stock NUMBER;
  v_wo NUMBER;
BEGIN
  SELECT
    unified_risk_score, vibration_mm_s, temperature_c, rpm,
    mm.machine_type
  INTO :v_risk, :v_vib, :v_temp, :v_rpm, :v_machine_type
  FROM MACHINE_RISK_UNIFIED r
  JOIN MACHINE_MASTER mm ON r.machine_id = mm.machine_id
  WHERE r.machine_id = P_MACHINE_ID;

  SELECT COALESCE(
    (SELECT estimated_rul_hours
     FROM RUL_PREDICTIONS
     WHERE machine_id = P_MACHINE_ID
     ORDER BY scored_at DESC
     LIMIT 1),
    (1.0 - COALESCE(v_risk,0)) * 168.0
  )
  INTO :v_rul;

  IF (COALESCE(v_vib,0) >= 4.0 AND COALESCE(v_temp,0) >= 80.0) THEN
    v_diagnosis := 'Probable bearing degradation';
    v_part := 'SKF-6205-2RS';
    v_action := 'Stop/inspect spindle bearing, verify lubrication and alignment, replace bearing if play or raceway damage is confirmed.';
  ELSEIF (COALESCE(v_temp,0) >= 80.0) THEN
    v_diagnosis := 'Probable coolant-flow / thermal overload';
    v_part := 'COOLANT-PUMP-4KW';
    v_action := 'Inspect coolant level, filter, pump pressure and return flow; replace pump if flow remains below specification.';
  ELSEIF (COALESCE(v_rpm,99999) < 1350.0 OR COALESCE(v_vib,0) >= 4.0) THEN
    v_diagnosis := 'Probable spindle drive / belt degradation';
    v_part := 'DRIVE-BELT-HX';
    v_action := 'Inspect belt tension, pulley alignment and spindle speed stability; replace belt if wear or tension drift is confirmed.';
  ELSE
    v_diagnosis := 'Multi-sensor anomaly — technician inspection required';
    v_part := 'INSPECTION_ONLY';
    v_action := 'Perform guided inspection using the maintenance knowledge base before ordering parts.';
  END IF;

  SELECT COALESCE(MAX(quantity_on_hand),0)
  INTO :v_stock
  FROM SPARE_PARTS
  WHERE part_number = v_part;

  INSERT INTO WORK_ORDERS
    (machine_id, priority, status, diagnosis, recommended_action,
     parts_required, estimated_downtime_hours, risk_score, rul_hours,
     source_documents)
  VALUES
    (
      P_MACHINE_ID,
      IFF(COALESCE(v_risk,0) >= 0.75, 'P1',
          IFF(COALESCE(v_risk,0) >= 0.50, 'P2', 'P3')),
      'PENDING_APPROVAL',
      v_diagnosis,
      v_action,
      IFF(v_part = 'INSPECTION_ONLY',
          'No part order until diagnosis is confirmed',
          v_part || ' | On-hand=' || COALESCE(v_stock,0)::VARCHAR),
      IFF(v_diagnosis LIKE '%bearing%', 4.0,
          IFF(v_diagnosis LIKE '%coolant%', 2.0, 3.0)),
      COALESCE(v_risk,0),
      COALESCE(v_rul,168.0),
      'Cortex Search service: MAINTENANCE_DOCS_SEARCH'
    );

  SELECT MAX(work_order_id)
  INTO :v_wo
  FROM WORK_ORDERS
  WHERE machine_id = P_MACHINE_ID;

  INSERT INTO ALERT_LOG(machine_id, severity, risk_score, alert_reason, work_order_id)
  VALUES (
    P_MACHINE_ID,
    IFF(COALESCE(v_risk,0) >= 0.75, 'CRITICAL',
        IFF(COALESCE(v_risk,0) >= 0.50, 'WARNING', 'INFO')),
    COALESCE(v_risk,0),
    v_diagnosis,
    v_wo
  );

  RETURN OBJECT_CONSTRUCT(
    'work_order_id', v_wo,
    'machine_id', P_MACHINE_ID,
    'priority', IFF(COALESCE(v_risk,0) >= 0.75, 'P1',
                    IFF(COALESCE(v_risk,0) >= 0.50, 'P2', 'P3')),
    'status', 'PENDING_APPROVAL',
    'diagnosis', v_diagnosis,
    'recommended_action', v_action,
    'part', v_part,
    'inventory_on_hand', COALESCE(v_stock,0),
    'rul_hours', ROUND(COALESCE(v_rul,168),1)
  )::VARCHAR;
END;
$$;

GRANT USAGE ON PROCEDURE PREDICT_RUL(VARCHAR) TO ROLE PUBLIC;
GRANT USAGE ON PROCEDURE GET_MACHINE_CONTEXT(VARCHAR) TO ROLE PUBLIC;
GRANT USAGE ON PROCEDURE GET_FLEET_CONTEXT() TO ROLE PUBLIC;
GRANT USAGE ON PROCEDURE AGENTIC_REMEDIATION(VARCHAR) TO ROLE PUBLIC;

-- Verification
SHOW PROCEDURES IN SCHEMA PM_OEE_DB.CORE;
