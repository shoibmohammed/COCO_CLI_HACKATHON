-- ============================================================
-- 13_automatic_notifications.sql
-- Snowflake Task that automatically sends notifications when
-- new critical alerts are detected in ALERT_LOG.
-- Does NOT require Streamlit to be open.
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

-- Add TRIGGER_TYPE column to NOTIFICATION_AUDIT if missing
ALTER TABLE PM_OEE_DB.CORE.NOTIFICATION_AUDIT
  ADD COLUMN IF NOT EXISTS TRIGGER_TYPE VARCHAR(20) DEFAULT 'MANUAL';

-- Track which alerts have been notified to prevent duplicates
CREATE TABLE IF NOT EXISTS PM_OEE_DB.CORE.ALERT_NOTIFICATION_LOG (
    ALERT_ID VARCHAR(50),
    MACHINE_ID VARCHAR(50),
    NOTIFICATION_SENT_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    EMAIL_STATUS VARCHAR(20),
    SLACK_STATUS VARCHAR(20)
);

-- Stored procedure: sends notifications for unprocessed critical alerts
CREATE OR REPLACE PROCEDURE PM_OEE_DB.CORE.PROCESS_AUTOMATIC_NOTIFICATIONS()
RETURNS VARCHAR
LANGUAGE SQL
AS
BEGIN
    -- Find alerts not yet notified (within last hour, not in notification log)
    LET new_alerts CURSOR FOR
        SELECT a.ALERT_ID, a.MACHINE_ID, a.SEVERITY, a.RISK_SCORE, a.ALERT_REASON, a.CREATED_AT
        FROM PM_OEE_DB.CORE.ALERT_LOG a
        WHERE a.CREATED_AT >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
          AND a.SEVERITY = 'CRITICAL'
          AND NOT EXISTS (
              SELECT 1 FROM PM_OEE_DB.CORE.ALERT_NOTIFICATION_LOG n
              WHERE n.ALERT_ID = a.ALERT_ID
          );

    LET notified_count INT := 0;

    FOR alert IN new_alerts DO
        LET :alert_id := alert.ALERT_ID;
        LET :machine_id := alert.MACHINE_ID;
        LET :risk_score := alert.RISK_SCORE;
        LET :reason := alert.ALERT_REASON;

        -- Attempt Snowflake Email
        LET :email_status := 'NOT_CONFIGURED';
        BEGIN
            CALL SYSTEM$SEND_EMAIL(
                'MFG_EMAIL_NOTIFICATION',
                (SELECT LISTAGG(ALLOWED_RECIPIENTS, ',') FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))),
                'CRITICAL ALERT — ' || :machine_id || ' — Risk ' || ROUND(:risk_score * 100) || '%',
                'AUTOMATIC CRITICAL MAINTENANCE ALERT\n\nMachine: ' || :machine_id || '\nRisk: ' || ROUND(:risk_score * 100) || '%\nReason: ' || :reason || '\n\nThis is an automated alert from MFG Predictive Maintenance.'
            );
            :email_status := 'SENT';
        EXCEPTION
            WHEN OTHER THEN
                :email_status := 'FAILED';
        END;

        -- Attempt Slack
        LET :slack_status := 'NOT_CONFIGURED';
        BEGIN
            CALL SYSTEM$SEND_SNOWFLAKE_NOTIFICATION(
                'MFG_SLACK_NOTIFICATION',
                '{"text": "🚨 AUTOMATIC CRITICAL ALERT — ' || :machine_id || ' — Risk ' || ROUND(:risk_score * 100) || '% — ' || :reason || '"}'
            );
            :slack_status := 'SENT';
        EXCEPTION
            WHEN OTHER THEN
                :slack_status := 'FAILED';
        END;

        -- Record in notification log (idempotency)
        INSERT INTO PM_OEE_DB.CORE.ALERT_NOTIFICATION_LOG (ALERT_ID, MACHINE_ID, EMAIL_STATUS, SLACK_STATUS)
        VALUES (:alert_id, :machine_id, :email_status, :slack_status);

        -- Record in NOTIFICATION_AUDIT
        INSERT INTO PM_OEE_DB.CORE.NOTIFICATION_AUDIT
            (EVENT_ID, MACHINE_ID, NOTIFICATION_TYPE, PROVIDER, RECIPIENT, SUBJECT, STATUS, TRIGGER_TYPE)
        VALUES
            (:alert_id, :machine_id, 'CRITICAL_ALERT', 'SNOWFLAKE_EMAIL', 'configured_recipient', 'Critical Alert — ' || :machine_id, :email_status, 'AUTOMATIC');

        INSERT INTO PM_OEE_DB.CORE.NOTIFICATION_AUDIT
            (EVENT_ID, MACHINE_ID, NOTIFICATION_TYPE, PROVIDER, RECIPIENT, SUBJECT, STATUS, TRIGGER_TYPE)
        VALUES
            (:alert_id, :machine_id, 'CRITICAL_ALERT', 'SLACK', 'mfg-alerts-channel', 'Critical Alert — ' || :machine_id, :slack_status, 'AUTOMATIC');

        :notified_count := :notified_count + 1;
    END FOR;

    RETURN 'Processed ' || :notified_count || ' automatic notification(s)';
END;

-- Task: runs every 5 minutes, processes new alerts
CREATE OR REPLACE TASK PM_OEE_DB.CORE.AUTOMATIC_NOTIFICATION_TASK
  WAREHOUSE = PM_OEE_WH
  SCHEDULE = '5 MINUTE'
  COMMENT = 'Sends automatic email/Slack notifications for new critical machine alerts'
AS
  CALL PM_OEE_DB.CORE.PROCESS_AUTOMATIC_NOTIFICATIONS();

-- Resume the task
ALTER TASK PM_OEE_DB.CORE.AUTOMATIC_NOTIFICATION_TASK RESUME;

-- Verify
SHOW TASKS IN SCHEMA PM_OEE_DB.CORE;
