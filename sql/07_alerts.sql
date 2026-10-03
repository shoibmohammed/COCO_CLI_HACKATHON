-- ============================================================
-- 07_alerts.sql
-- Optional Snowflake Alert layer. It logs new high-risk events.
-- External ticket creation remains governed by the agent/MCP path.
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

CREATE OR REPLACE ALERT HIGH_RISK_MACHINE_ALERT
  WAREHOUSE = PM_OEE_WH
  SCHEDULE = '5 MINUTE'
  IF (EXISTS (
      SELECT 1
      FROM MACHINE_RISK_UNIFIED r
      WHERE r.unified_risk_score >= 0.75
        AND NOT EXISTS (
          SELECT 1
          FROM ALERT_LOG a
          WHERE a.machine_id = r.machine_id
            AND a.created_at >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
        )
  ))
  THEN
    INSERT INTO ALERT_LOG(machine_id, severity, risk_score, alert_reason)
    SELECT
      machine_id,
      'CRITICAL',
      unified_risk_score,
      'Automated high-risk alert: ' || COALESCE(top_reason,'Multi-sensor anomaly')
    FROM MACHINE_RISK_UNIFIED r
    WHERE r.unified_risk_score >= 0.75
      AND NOT EXISTS (
        SELECT 1
        FROM ALERT_LOG a
        WHERE a.machine_id = r.machine_id
          AND a.created_at >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
      );

ALTER ALERT HIGH_RISK_MACHINE_ALERT RESUME;

SHOW ALERTS IN SCHEMA PM_OEE_DB.CORE;
