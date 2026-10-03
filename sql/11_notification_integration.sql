-- Snowflake Email Notification Integration for MFG Predictive Maintenance
-- Co-authored with CoCo

-- ============================================================
-- 11_notification_integration.sql
-- Creates the MFG_EMAIL_NOTIFICATION integration for SYSTEM$SEND_EMAIL.
-- Idempotent: uses CREATE IF NOT EXISTS where supported.
-- ============================================================

USE ROLE ACCOUNTADMIN;
USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;

-- ============================================================
-- 1. NOTIFICATION INTEGRATION
-- ============================================================
-- Snowflake does not support IF NOT EXISTS for notification integrations.
-- This script uses CREATE OR REPLACE which is safe for fresh deployments.
-- On existing accounts: verify integration does not already exist before running.
--
-- To check: SHOW NOTIFICATION INTEGRATIONS LIKE 'MFG_EMAIL_NOTIFICATION';
-- ============================================================

CREATE OR REPLACE NOTIFICATION INTEGRATION MFG_EMAIL_NOTIFICATION
  TYPE = EMAIL
  ENABLED = TRUE
  ALLOWED_RECIPIENTS = ('hackathon2@snowflake.com')
  COMMENT = 'MFG Predictive Maintenance - Snowflake native email for critical alerts and work order notifications';

-- ============================================================
-- 2. GRANT USAGE
-- ============================================================
-- The integration must be usable by the role running the Streamlit app.
-- ACCOUNTADMIN owns the integration; grant usage to PUBLIC for demo.

GRANT USAGE ON INTEGRATION MFG_EMAIL_NOTIFICATION TO ROLE PUBLIC;

-- ============================================================
-- 3. NOTIFICATION AUDIT TABLE
-- ============================================================
-- Tracks all email dispatches for compliance and debugging.

CREATE TABLE IF NOT EXISTS PM_OEE_DB.CORE.NOTIFICATION_AUDIT (
    AUDIT_ID            VARCHAR(50) DEFAULT UUID_STRING(),
    NOTIFICATION_TYPE   VARCHAR(50),
    PROVIDER            VARCHAR(50),
    RECIPIENT           VARCHAR(200),
    SUBJECT             VARCHAR(500),
    STATUS              VARCHAR(50),
    ERROR_MESSAGE       VARCHAR(2000),
    MACHINE_ID          VARCHAR(50),
    WORK_ORDER_ID       VARCHAR(50),
    DISPATCHED_AT       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ============================================================
-- 4. VERIFICATION
-- ============================================================
SHOW NOTIFICATION INTEGRATIONS LIKE 'MFG_EMAIL_NOTIFICATION';

-- ============================================================
-- MANUAL CONFIGURATION NOTES
-- ============================================================
-- 1. ALLOWED_RECIPIENTS: Update the list to include actual recipient
--    email addresses for the target environment.
--    Snowflake only permits sending to verified addresses in this list.
--
-- 2. The sender address is determined by the Snowflake account and
--    cannot be customized. Emails come from no-reply@snowflakecomputing.com.
--
-- 3. SYSTEM$SEND_EMAIL usage:
--    CALL SYSTEM$SEND_EMAIL(
--      'MFG_EMAIL_NOTIFICATION',
--      'recipient@example.com',
--      'Subject Line',
--      'Email body text or HTML',
--      'text/html'  -- optional MIME type
--    );
--
-- 4. Rate limits: Snowflake enforces per-account email rate limits.
--    For production volumes, consider supplementing with an external
--    email provider via External Access Integration (Enterprise only).
-- ============================================================
