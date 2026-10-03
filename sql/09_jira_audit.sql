-- ============================================================
-- sql/09_jira_audit.sql
-- Transactional Audit Table for Jira Integration in PM_OEE_DB
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;

CREATE TABLE IF NOT EXISTS PM_OEE_DB.CORE.JIRA_TICKET_AUDIT (
    AUDIT_ID VARCHAR(50) DEFAULT UUID_STRING(),
    WORK_ORDER_ID VARCHAR(50),
    MACHINE_ID VARCHAR(50),
    JIRA_ISSUE_KEY VARCHAR(50),
    JIRA_ISSUE_URL VARCHAR(500),
    JIRA_PROJECT VARCHAR(50),
    ISSUE_TYPE VARCHAR(50),
    EXECUTION_MODE VARCHAR(50) DEFAULT 'ATLASSIAN_MCP',
    STATUS VARCHAR(50),
    ERROR_MESSAGE VARCHAR(1000),
    CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Immutable audit trail of Jira creation and execution mode.';
