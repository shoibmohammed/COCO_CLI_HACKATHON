-- ============================================================
-- sql/10_reset_demo_state.sql
-- Snowflake Stored Procedure for Safe True Clean-Slate Demo Reset
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;

CREATE OR REPLACE PROCEDURE PM_OEE_DB.CORE.RESET_DEMO_STATE()
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
BEGIN
    -- 1. Safely clear transactional demo tables
    DELETE FROM PM_OEE_DB.CORE.WORK_ORDERS;
    DELETE FROM PM_OEE_DB.CORE.ALERT_LOG;
    DELETE FROM PM_OEE_DB.CORE.JIRA_TICKET_AUDIT;
    DELETE FROM PM_OEE_DB.CORE.NOTIFICATION_AUDIT;

    -- Clear ML_RISK_PREDICTIONS table if it exists
    BEGIN
        DELETE FROM PM_OEE_DB.CORE.ML_RISK_PREDICTIONS;
    EXCEPTION
        WHEN OTHER THEN
            NULL;
    END;

    -- Clear PRODUCTION_EVENTS so OEE calculates as 0.0% / no production data
    BEGIN
        DELETE FROM PM_OEE_DB.CORE.PRODUCTION_EVENTS;
    EXCEPTION
        WHEN OTHER THEN
            NULL;
    END;

    -- 2. Clear historical anomaly telemetry from SENSOR_READINGS and insert clean nominal baseline readings
    --    Use MACHINE_BASELINES means so all risk scores compute to 0 (healthy state)
    DELETE FROM PM_OEE_DB.CORE.SENSOR_READINGS;

    INSERT INTO PM_OEE_DB.CORE.SENSOR_READINGS (ts, machine_id, vibration_mm_s, temperature_c, rpm, pressure_bar, power_kw)
    SELECT CURRENT_TIMESTAMP(), b.machine_id, b.vibration_mean, b.temperature_mean, b.rpm_mean, 6.0, 4.0
    FROM PM_OEE_DB.CORE.MACHINE_BASELINES b;

    -- 3. Restore spare-parts inventory baseline (SKF-6205-2RS stock = 4)
    UPDATE PM_OEE_DB.CORE.SPARE_PARTS
    SET quantity_on_hand = 4
    WHERE part_number = 'SKF-6205-2RS';

    -- 4. Trigger immediate refresh on Dynamic Tables to eliminate target lag
    BEGIN
        ALTER DYNAMIC TABLE PM_OEE_DB.CORE.MACHINE_HEALTH_RT REFRESH;
        ALTER DYNAMIC TABLE PM_OEE_DB.CORE.RISK_SCORES_RT REFRESH;
        ALTER DYNAMIC TABLE PM_OEE_DB.CORE.OEE_METRICS_RT REFRESH;
    EXCEPTION
        WHEN OTHER THEN
            NULL;
    END;

    RETURN 'SUCCESS: Clean-slate demo reset complete.';
END;
$$;
