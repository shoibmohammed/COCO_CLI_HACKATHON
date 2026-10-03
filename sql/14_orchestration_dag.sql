-- ============================================================
-- 14_orchestration_dag.sql
-- Three-stage Task DAG that chains the predictive maintenance
-- workflow: Anomaly Detection → Work Order Drafting → Notify.
--
-- Replaces the standalone AUTOMATIC_NOTIFICATION_TASK with a
-- governed pipeline where notifications only fire AFTER
-- anomalies are detected and work orders are drafted.
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

-- ============================================================
-- STAGE 1: SCAN_AND_DETECT_ANOMALIES
-- Refreshes dynamic tables, runs ML inference, inserts new
-- critical alerts into ALERT_LOG for machines not already
-- alerted in the last hour.
-- ============================================================
CREATE OR REPLACE PROCEDURE PM_OEE_DB.CORE.SCAN_AND_DETECT_ANOMALIES()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
BEGIN
    -- Refresh dynamic tables for latest telemetry
    ALTER DYNAMIC TABLE PM_OEE_DB.CORE.MACHINE_HEALTH_RT REFRESH;
    ALTER DYNAMIC TABLE PM_OEE_DB.CORE.RISK_SCORES_RT REFRESH;
    ALTER DYNAMIC TABLE PM_OEE_DB.CORE.OEE_METRICS_RT REFRESH;

    -- Run ML inference
    CALL PM_OEE_DB.CORE.REFRESH_ML_RISK();

    -- Insert new critical alerts for machines above threshold
    -- that have not been alerted in the last hour
    LET alert_count INT := 0;

    INSERT INTO PM_OEE_DB.CORE.ALERT_LOG (machine_id, severity, risk_score, alert_reason)
    SELECT
        r.machine_id,
        CASE
            WHEN r.unified_risk_score >= 0.75 THEN 'CRITICAL'
            WHEN r.unified_risk_score >= 0.50 THEN 'WARNING'
            ELSE 'INFO'
        END,
        r.unified_risk_score,
        COALESCE(r.top_reason, 'Multi-sensor anomaly detected')
    FROM PM_OEE_DB.CORE.MACHINE_RISK_UNIFIED r
    WHERE r.unified_risk_score >= 0.65
      AND NOT EXISTS (
          SELECT 1 FROM PM_OEE_DB.CORE.ALERT_LOG a
          WHERE a.machine_id = r.machine_id
            AND a.severity IN ('CRITICAL', 'WARNING')
            AND a.created_at >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
      );

    alert_count := SQLROWCOUNT;

    RETURN 'Anomaly scan complete: ' || alert_count || ' new alert(s) logged';
END;

-- ============================================================
-- STAGE 2: AUTO_DRAFT_WORK_ORDERS
-- For each critical alert in the last 10 minutes that does NOT
-- already have a PENDING or OPEN work order, call
-- AGENTIC_REMEDIATION to create a governed work order.
-- ============================================================
CREATE OR REPLACE PROCEDURE PM_OEE_DB.CORE.AUTO_DRAFT_WORK_ORDERS()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
BEGIN
    LET wo_count INT := 0;

    LET critical_machines CURSOR FOR
        SELECT DISTINCT a.machine_id
        FROM PM_OEE_DB.CORE.ALERT_LOG a
        WHERE a.severity = 'CRITICAL'
          AND a.created_at >= DATEADD('minute', -10, CURRENT_TIMESTAMP())
          AND NOT EXISTS (
              SELECT 1 FROM PM_OEE_DB.CORE.WORK_ORDERS w
              WHERE w.machine_id = a.machine_id
                AND w.status IN ('PENDING_APPROVAL', 'OPEN', 'APPROVED')
                AND w.created_at >= DATEADD('hour', -2, CURRENT_TIMESTAMP())
          );

    FOR machine IN critical_machines DO
        CALL PM_OEE_DB.CORE.AGENTIC_REMEDIATION(machine.machine_id);
        wo_count := wo_count + 1;
    END FOR;

    RETURN 'Work order drafting complete: ' || wo_count || ' order(s) created';
END;

-- ============================================================
-- TASK DAG: Three-stage pipeline
--
--   pm_anomaly_scan_task (ROOT, every 5 min)
--       └─► pm_work_order_task (AFTER anomaly scan)
--              └─► pm_notify_task (AFTER work orders)
-- ============================================================

-- Suspend the old standalone notification task if it exists
ALTER TASK IF EXISTS PM_OEE_DB.CORE.AUTOMATIC_NOTIFICATION_TASK SUSPEND;

-- IMPORTANT: Create tasks bottom-up (leaf first) per Snowflake DAG rules.
-- Child tasks must exist before the parent references them with AFTER.

-- Stage 3 (leaf): Notify
CREATE OR REPLACE TASK PM_OEE_DB.CORE.PM_NOTIFY_TASK
    WAREHOUSE = PM_OEE_WH
    AFTER PM_OEE_DB.CORE.PM_WORK_ORDER_TASK
    COMMENT = 'DAG Stage 3: Send email + Slack notifications for new critical alerts'
AS
    CALL PM_OEE_DB.CORE.PROCESS_AUTOMATIC_NOTIFICATIONS();

-- Stage 2 (middle): Draft work orders
CREATE OR REPLACE TASK PM_OEE_DB.CORE.PM_WORK_ORDER_TASK
    WAREHOUSE = PM_OEE_WH
    AFTER PM_OEE_DB.CORE.PM_ANOMALY_SCAN_TASK
    COMMENT = 'DAG Stage 2: Auto-draft governed work orders for critical machines'
AS
    CALL PM_OEE_DB.CORE.AUTO_DRAFT_WORK_ORDERS();

-- Stage 1 (root): Anomaly scan
CREATE OR REPLACE TASK PM_OEE_DB.CORE.PM_ANOMALY_SCAN_TASK
    WAREHOUSE = PM_OEE_WH
    SCHEDULE = '5 MINUTE'
    COMMENT = 'DAG Stage 1 (root): Refresh DTs, run ML inference, detect anomalies'
AS
    CALL PM_OEE_DB.CORE.SCAN_AND_DETECT_ANOMALIES();

-- ============================================================
-- Resume tasks (bottom-up: children first, root last)
-- ============================================================
ALTER TASK PM_OEE_DB.CORE.PM_NOTIFY_TASK RESUME;
ALTER TASK PM_OEE_DB.CORE.PM_WORK_ORDER_TASK RESUME;
ALTER TASK PM_OEE_DB.CORE.PM_ANOMALY_SCAN_TASK RESUME;

-- ============================================================
-- Verification
-- ============================================================
SHOW TASKS IN SCHEMA PM_OEE_DB.CORE;

SELECT
    name,
    state,
    schedule,
    predecessors,
    comment
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE name LIKE 'PM_%_TASK'
ORDER BY name;
