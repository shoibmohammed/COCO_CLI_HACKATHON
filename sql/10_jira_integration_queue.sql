-- Jira Integration Queue table for local worker polling architecture
-- Co-authored with CoCo
-- ============================================================
-- sql/10_jira_integration_queue.sql
-- Queue table for Local Jira Worker integration
-- Status lifecycle: PENDING → PROCESSING → SUCCESS | FAILED
-- Idempotency enforced at application/worker level
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;

CREATE TABLE IF NOT EXISTS PM_OEE_DB.CORE.JIRA_INTEGRATION_QUEUE (
    QUEUE_ID VARCHAR(50) DEFAULT UUID_STRING(),
    WORK_ORDER_ID VARCHAR(50) NOT NULL,
    MACHINE_ID VARCHAR(50),
    REQUEST_TYPE VARCHAR(50) DEFAULT 'CREATE_ISSUE',
    SHORT_DESCRIPTION VARCHAR(500),
    DESCRIPTION VARCHAR(4000),
    IMPACT VARCHAR(50),
    URGENCY VARCHAR(50),
    STATUS VARCHAR(20) DEFAULT 'PENDING',
    ATTEMPT_COUNT INT DEFAULT 0,
    JIRA_PROJECT_KEY VARCHAR(50),
    JIRA_ISSUE_KEY VARCHAR(50),
    JIRA_SYS_ID VARCHAR(100),
    JIRA_URL VARCHAR(500),
    ERROR_MESSAGE VARCHAR(2000),
    CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    UPDATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    PROCESSED_AT TIMESTAMP_NTZ
);
