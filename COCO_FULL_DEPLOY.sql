-- ============================================================
-- COCO_FULL_DEPLOY.sql
-- ONE-SCRIPT FULL DEPLOYMENT via CoCo CLI
-- 
-- PURPOSE: Deploy the entire MFG Predictive Maintenance project
-- to a fresh Snowflake account using ONLY CoCo. No Snowsight
-- worksheets, no manual steps (except Atlassian callback URL).
--
-- USAGE IN COCO:
--   Paste this entire script into CoCo and say "run this"
--   OR ask CoCo: "Deploy my MFG PM project from scratch"
--   and point it to this file.
--
-- PREREQUISITES:
--   - ACCOUNTADMIN role
--   - A compute pool must exist (or will be created)
--   - For Jira MCP: Register callback URL at admin.atlassian.com
--     → Apps → AI Settings → Rovo MCP Server → Add Domain:
--     https://identity.snowflake.com/oauth2/callback
--
-- ESTIMATED TIME: ~5 minutes
-- ESTIMATED CREDITS: < 1 credit
-- ============================================================

-- ============================================================
-- PHASE 1: INFRASTRUCTURE
-- ============================================================

-- 1.1 Warehouse
CREATE WAREHOUSE IF NOT EXISTS PM_OEE_WH
  WAREHOUSE_SIZE = 'X-SMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE;

USE WAREHOUSE PM_OEE_WH;

-- 1.2 Database & Schema
CREATE DATABASE IF NOT EXISTS PM_OEE_DB;
CREATE SCHEMA IF NOT EXISTS PM_OEE_DB.CORE;
USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;

-- ============================================================
-- PHASE 2: RUN SQL SCRIPTS IN ORDER
-- ============================================================
-- 
-- CoCo: Execute each SQL file in this order. Each is idempotent.
--
-- STEP 1: sql/01_setup.sql
--   Creates: MACHINE_MASTER, ERP_ASSETS, SPARE_PARTS,
--   SENSOR_READINGS, PRODUCTION_EVENTS, MAINTENANCE_HISTORY,
--   WORK_ORDERS, ALERT_LOG, MACHINE_BASELINES,
--   Dynamic Tables (MACHINE_HEALTH_RT, RISK_SCORES_RT, OEE_METRICS_RT)
--
-- STEP 2: sql/02_documents_and_cortex_search.sql
--   Creates: MAINTENANCE_DOCS table, MAINTENANCE_DOCS_SEARCH service
--
-- STEP 3: sql/03_seed_data.sql (OR generate inline — see Phase 3)
--   Populates: SENSOR_READINGS (576+ rows), PRODUCTION_EVENTS
--
-- STEP 4: sql/03_cortex_ml.sql
--   Creates: ML_TRAINING_DATA, PM_FAILURE_MODEL, REFRESH_ML_RISK()
--
-- STEP 5: sql/04_agent_workflow.sql
--   Creates: PREDICT_RUL, GET_MACHINE_CONTEXT, GET_FLEET_CONTEXT,
--   AGENTIC_REMEDIATION procedures
--
-- STEP 6: sql/05_cortex_agent.sql
--   Creates: PM_AGENT with 4 tools
--
-- STEP 7: sql/07_alerts.sql
--   Creates: Alert thresholds and log structure
--
-- STEP 8: sql/09_jira_mcp_integration.sql
--   Creates: Jira queue governance objects
--
-- STEP 9: sql/10_jira_integration_queue.sql
--   Creates: JIRA_INTEGRATION_QUEUE with approval enforcement
--
-- STEP 10: sql/11_notification_integration.sql
--   Creates: MFG_EMAIL_NOTIFICATION
--   ** UPDATE ALLOWED_RECIPIENTS with your team emails **
--
-- STEP 11: sql/14_orchestration_dag.sql
--   Creates: 3-stage Task DAG
--
-- STEP 12: sql/15_atlassian_mcp_connector.sql
--   Creates: ATLASSIAN_MCP_SERVER (Jira, no EAI needed)

-- ============================================================
-- PHASE 3: BOOST SENSOR DATA TO 3,456+ ROWS (4-DIGIT)
-- ============================================================
-- Run this AFTER sql/01_setup.sql and sql/03_seed_data.sql

INSERT INTO PM_OEE_DB.CORE.SENSOR_READINGS
  (ts, machine_id, vibration_mm_s, temperature_c, rpm, pressure_bar, power_kw)
WITH machines AS (
  SELECT column1 AS machine_id, column2 AS base_vib, column3 AS base_temp,
         column4 AS base_rpm, column5 AS degrade
  FROM VALUES
    ('Machine_01', 1.8, 62.0, 1500, 0),
    ('Machine_02', 2.2, 72.0, 1480, 1),
    ('Machine_03', 3.5, 78.0, 1460, 1),
    ('Machine_04', 1.6, 60.0, 1510, 0)
),
time_series AS (
  SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1 AS idx
  FROM TABLE(GENERATOR(ROWCOUNT => 720))
)
SELECT
  DATEADD('minute', -t.idx * 5, CURRENT_TIMESTAMP()),
  m.machine_id,
  ROUND(m.base_vib + (CASE WHEN m.degrade=1 THEN t.idx*0.004 ELSE 0 END)
    + UNIFORM(-0.3, 0.3, RANDOM()), 2),
  ROUND(m.base_temp + (CASE WHEN m.degrade=1 THEN t.idx*0.03 ELSE 0 END)
    + UNIFORM(-2.0, 2.0, RANDOM()), 1),
  ROUND(m.base_rpm - (CASE WHEN m.degrade=1 THEN t.idx*0.15 ELSE 0 END)
    + UNIFORM(-20, 20, RANDOM())),
  ROUND(5.0 + UNIFORM(-0.5, 0.5, RANDOM()), 2),
  ROUND(12.0 + UNIFORM(-1.0, 1.0, RANDOM()), 2)
FROM machines m CROSS JOIN time_series t;

-- ============================================================
-- PHASE 4: MARKETPLACE DATA
-- ============================================================

INSERT INTO PM_OEE_DB.CORE.MARKETPLACE_PART_SUPPLIER_ENRICHMENT
  (MACHINE_ID, MACHINE_NAME, MACHINE_TYPE, BEARING_PART_NUMBER, SUPPLIER,
   LEAD_TIME_DAYS, QUANTITY_ON_HAND, UNIT_COST_USD, COPPER_PRICE_USD,
   ALUMINUM_PRICE_USD, NICKEL_PRICE_USD, IRON_ORE_PRICE_USD,
   INDUSTRIAL_PROD_IDX, SUPPLY_CHAIN_RISK)
VALUES
  ('Machine_01','CNC Spindle A','CNC_LATHE','SKF-6205-2RS','SKF Industrial',5,12,42.50,9150,2380,16200,108.5,103.2,'LOW'),
  ('Machine_02','CNC Spindle B','CNC_LATHE','SKF-6205-2RS','SKF Industrial',5,8,42.50,9150,2380,16200,108.5,103.2,'MEDIUM'),
  ('Machine_03','Precision Mill C','PRECISION_MILL','SKF-6205-2RS','NTN Bearings',7,4,45.00,9150,2380,16200,108.5,103.2,'HIGH'),
  ('Machine_04','Precision Mill D','PRECISION_MILL','DRIVE-BELT-HX','Gates Industrial',3,6,85.00,9150,2380,16200,108.5,103.2,'LOW');

-- ============================================================
-- PHASE 5: REFRESH ML + DYNAMIC TABLES
-- ============================================================

ALTER DYNAMIC TABLE PM_OEE_DB.CORE.MACHINE_HEALTH_RT REFRESH;
ALTER DYNAMIC TABLE PM_OEE_DB.CORE.RISK_SCORES_RT REFRESH;
ALTER DYNAMIC TABLE PM_OEE_DB.CORE.OEE_METRICS_RT REFRESH;
CALL PM_OEE_DB.CORE.REFRESH_ML_RISK();

-- ============================================================
-- PHASE 6: NOTIFICATION INTEGRATIONS
-- ============================================================

-- Email (update ALLOWED_RECIPIENTS with your team's verified emails)
CREATE OR REPLACE NOTIFICATION INTEGRATION MFG_EMAIL_NOTIFICATION
  TYPE = EMAIL
  ENABLED = TRUE
  ALLOWED_RECIPIENTS = ('YOUR_EMAIL@company.com')
  COMMENT = 'MFG PM critical alerts';

GRANT USAGE ON INTEGRATION MFG_EMAIL_NOTIFICATION TO ROLE PUBLIC;

-- Slack (update WEBHOOK_URL with your Slack incoming webhook)
CREATE OR REPLACE NOTIFICATION INTEGRATION MFG_SLACK_NOTIFICATION
  TYPE = WEBHOOK
  ENABLED = TRUE
  WEBHOOK_URL = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
  WEBHOOK_BODY_TEMPLATE = '{"text": "SNOWFLAKE_WEBHOOK_MESSAGE"}'
  WEBHOOK_HEADERS = ('Content-Type'='application/json');

GRANT USAGE ON INTEGRATION MFG_SLACK_NOTIFICATION TO ROLE PUBLIC;

-- ============================================================
-- PHASE 7: JIRA MCP CONNECTOR (No EAI needed)
-- ============================================================

CREATE API INTEGRATION IF NOT EXISTS JIRA_MCP_API_INTEGRATION
  API_PROVIDER = external_mcp
  API_ALLOWED_PREFIXES = ('https://mcp.atlassian.com')
  API_USER_AUTHENTICATION = (
    TYPE = OAUTH_DYNAMIC_CLIENT,
    OAUTH_RESOURCE_URL = 'https://mcp.atlassian.com/v1/mcp'
  )
  ENABLED = TRUE;

CREATE EXTERNAL MCP SERVER IF NOT EXISTS PM_OEE_DB.CORE.ATLASSIAN_MCP_SERVER
  WITH DISPLAY_NAME = 'Atlassian (Jira & Confluence)'
  URL = 'https://mcp.atlassian.com/v1/mcp'
  API_INTEGRATION = JIRA_MCP_API_INTEGRATION;

GRANT USAGE ON EXTERNAL MCP SERVER PM_OEE_DB.CORE.ATLASSIAN_MCP_SERVER TO ROLE PUBLIC;
GRANT USAGE ON INTEGRATION JIRA_MCP_API_INTEGRATION TO ROLE PUBLIC;

-- ============================================================
-- PHASE 8: PYPI ACCESS (for Enterprise accounts only)
-- ============================================================
-- Uncomment if NOT on a trial account:
-- GRANT DATABASE ROLE SNOWFLAKE.PYPI_REPOSITORY_USER TO ROLE ACCOUNTADMIN;

-- ============================================================
-- PHASE 9: RESUME TASK DAG
-- ============================================================

ALTER TASK PM_OEE_DB.CORE.PM_NOTIFY_TASK RESUME;
ALTER TASK PM_OEE_DB.CORE.PM_WORK_ORDER_TASK RESUME;
ALTER TASK PM_OEE_DB.CORE.PM_ANOMALY_SCAN_TASK RESUME;

-- ============================================================
-- PHASE 10: RUN FULL DAG CYCLE (validate everything works)
-- ============================================================

CALL PM_OEE_DB.CORE.SCAN_AND_DETECT_ANOMALIES();
CALL PM_OEE_DB.CORE.AUTO_DRAFT_WORK_ORDERS();
CALL PM_OEE_DB.CORE.PROCESS_AUTOMATIC_NOTIFICATIONS();

-- ============================================================
-- PHASE 11: VERIFICATION
-- ============================================================

-- Check all tables populated
SELECT 'SENSOR_READINGS' AS TBL, COUNT(*) AS CNT FROM PM_OEE_DB.CORE.SENSOR_READINGS
UNION ALL SELECT 'WORK_ORDERS', COUNT(*) FROM PM_OEE_DB.CORE.WORK_ORDERS
UNION ALL SELECT 'ALERT_LOG', COUNT(*) FROM PM_OEE_DB.CORE.ALERT_LOG
UNION ALL SELECT 'ML_RISK_PREDICTIONS', COUNT(*) FROM PM_OEE_DB.CORE.ML_RISK_PREDICTIONS
UNION ALL SELECT 'NOTIFICATION_AUDIT', COUNT(*) FROM PM_OEE_DB.CORE.NOTIFICATION_AUDIT;

-- Check risk scores
SELECT machine_id, ROUND(unified_risk_score, 3) AS risk, failure_class
FROM PM_OEE_DB.CORE.MACHINE_RISK_UNIFIED ORDER BY risk DESC;

-- Check tasks
SHOW TASKS IN SCHEMA PM_OEE_DB.CORE;

-- Check agent
SHOW AGENTS IN SCHEMA PM_OEE_DB.CORE;

-- ============================================================
-- DONE! 
-- 
-- Next steps:
-- 1. Upload Streamlit app folder to a Workspace
-- 2. Verify pyproject.toml has ONLY streamlit[snowflake]>=1.54.0
-- 3. Click Run in Snowsight
-- 4. Connect Atlassian MCP in CoCo Settings → MCP Connectors
-- ============================================================
