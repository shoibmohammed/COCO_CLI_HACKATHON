-- Non-destructive deployment validation script for MFG Predictive Maintenance
-- Co-authored with CoCo

-- ============================================================
-- validate_deployment.sql
-- Checks all required Snowflake objects exist and are correctly configured.
-- THIS SCRIPT DOES NOT MODIFY ANYTHING.
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;

-- ============================================================
-- 1. DATABASE & SCHEMA
-- ============================================================
SELECT 'DATABASE' AS check_type, 'PM_OEE_DB' AS object_name,
  IFF(CURRENT_DATABASE() = 'PM_OEE_DB', 'PASS', 'FAIL') AS status;

SELECT 'SCHEMA' AS check_type, 'CORE' AS object_name,
  IFF(CURRENT_SCHEMA() = 'CORE', 'PASS', 'FAIL') AS status;

-- ============================================================
-- 2. WAREHOUSE
-- ============================================================
SELECT 'WAREHOUSE' AS check_type, 'PM_OEE_WH' AS object_name,
  IFF(COUNT(*) > 0, 'PASS', 'FAIL') AS status
FROM INFORMATION_SCHEMA.WAREHOUSES
WHERE WAREHOUSE_NAME = 'PM_OEE_WH';

-- ============================================================
-- 3. REQUIRED TABLES
-- ============================================================
WITH required_tables AS (
  SELECT column1 AS table_name FROM VALUES
    ('MACHINE_MASTER'),
    ('MACHINE_BASELINES'),
    ('ERP_ASSETS'),
    ('SPARE_PARTS'),
    ('MAINTENANCE_HISTORY'),
    ('SENSOR_READINGS'),
    ('PRODUCTION_EVENTS'),
    ('MAINTENANCE_DOCS'),
    ('ML_RISK_PREDICTIONS'),
    ('RUL_PREDICTIONS'),
    ('WORK_ORDERS'),
    ('ALERT_LOG'),
    ('ML_TRAINING_DATA'),
    ('ENVIRONMENTAL_CONTEXT'),
    ('JIRA_TICKET_AUDIT'),
    ('NOTIFICATION_AUDIT'),
    ('MARKETPLACE_INGESTION_CONTROL'),
    ('RAW_MARKETPLACE_DATA')
)
SELECT 'TABLE' AS check_type, r.table_name AS object_name,
  IFF(t.table_name IS NOT NULL, 'PASS', 'MISSING') AS status
FROM required_tables r
LEFT JOIN INFORMATION_SCHEMA.TABLES t
  ON t.table_schema = 'CORE' AND t.table_name = r.table_name AND t.table_type = 'BASE TABLE';

-- ============================================================
-- 4. REQUIRED VIEWS
-- ============================================================
WITH required_views AS (
  SELECT column1 AS view_name FROM VALUES
    ('MACHINE_LATEST_RISK'),
    ('MACHINE_LATEST_HEALTH'),
    ('ML_PREDICTION_INPUT'),
    ('MACHINE_RISK_UNIFIED')
)
SELECT 'VIEW' AS check_type, r.view_name AS object_name,
  IFF(v.table_name IS NOT NULL, 'PASS', 'MISSING') AS status
FROM required_views r
LEFT JOIN INFORMATION_SCHEMA.VIEWS v
  ON v.table_schema = 'CORE' AND v.table_name = r.view_name;

-- ============================================================
-- 5. DYNAMIC TABLES
-- ============================================================
WITH required_dts AS (
  SELECT column1 AS dt_name FROM VALUES
    ('MACHINE_HEALTH_RT'),
    ('RISK_SCORES_RT'),
    ('OEE_METRICS_RT')
)
SELECT 'DYNAMIC_TABLE' AS check_type, r.dt_name AS object_name,
  IFF(d."name" IS NOT NULL, 'PASS', 'MISSING') AS status
FROM required_dts r
LEFT JOIN (
  SELECT "name" FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
) d ON d."name" = r.dt_name;

-- Direct check for DTs:
SHOW DYNAMIC TABLES IN SCHEMA PM_OEE_DB.CORE;

SELECT 'DYNAMIC_TABLE_COUNT' AS check_type,
  COUNT(*)::VARCHAR AS object_name,
  IFF(COUNT(*) >= 3, 'PASS', 'FAIL') AS status
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

-- ============================================================
-- 6. STORED PROCEDURES
-- ============================================================
SHOW PROCEDURES IN SCHEMA PM_OEE_DB.CORE;

WITH required_procs AS (
  SELECT column1 AS proc_name FROM VALUES
    ('REFRESH_ML_RISK'),
    ('PREDICT_RUL'),
    ('GET_MACHINE_CONTEXT'),
    ('GET_FLEET_CONTEXT'),
    ('AGENTIC_REMEDIATION'),
    ('RESET_DEMO_STATE')
)
SELECT 'PROCEDURE' AS check_type, r.proc_name AS object_name,
  IFF(EXISTS(
    SELECT 1 FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
    WHERE "name" = r.proc_name
  ), 'PASS', 'MISSING') AS status
FROM required_procs r;

-- ============================================================
-- 7. ML MODEL
-- ============================================================
SHOW SNOWFLAKE.ML.CLASSIFICATION IN SCHEMA PM_OEE_DB.CORE;

SELECT 'ML_MODEL' AS check_type, 'PM_FAILURE_MODEL' AS object_name,
  IFF(COUNT(*) > 0, 'PASS', 'MISSING') AS status
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "name" = 'PM_FAILURE_MODEL';

-- ============================================================
-- 8. STAGES
-- ============================================================
SHOW STAGES IN SCHEMA PM_OEE_DB.CORE;

SELECT 'STAGE' AS check_type, 'MAINTENANCE_DOC_STAGE' AS object_name,
  IFF(COUNT(*) > 0, 'PASS', 'MISSING') AS status
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "name" = 'MAINTENANCE_DOC_STAGE';

SHOW STAGES IN SCHEMA PM_OEE_DB.CORE;

SELECT 'STAGE' AS check_type, 'SENSOR_LANDING_STAGE' AS object_name,
  IFF(COUNT(*) > 0, 'PASS', 'MISSING') AS status
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "name" = 'SENSOR_LANDING_STAGE';

-- ============================================================
-- 9. SECRETS
-- ============================================================
SHOW SECRETS IN SCHEMA PM_OEE_DB.CORE;

SELECT 'SECRET' AS check_type, 'GEMINI_API_KEY_SECRET' AS object_name,
  IFF(COUNT(*) > 0, 'PASS', 'MISSING') AS status
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "name" = 'GEMINI_API_KEY_SECRET';

-- ============================================================
-- 10. NETWORK RULES
-- ============================================================
SHOW NETWORK RULES IN SCHEMA PM_OEE_DB.CORE;

SELECT 'NETWORK_RULE' AS check_type, 'GEMINI_API_NETWORK_RULE' AS object_name,
  IFF(COUNT(*) > 0, 'PASS', 'MISSING') AS status
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))
WHERE "name" = 'GEMINI_API_NETWORK_RULE';

-- ============================================================
-- 11. NOTIFICATION INTEGRATION
-- ============================================================
SHOW NOTIFICATION INTEGRATIONS LIKE 'MFG_EMAIL_NOTIFICATION';

SELECT 'NOTIFICATION_INTEGRATION' AS check_type, 'MFG_EMAIL_NOTIFICATION' AS object_name,
  IFF(COUNT(*) > 0, 'PASS', 'MISSING') AS status
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

-- ============================================================
-- 12. MARKETPLACE DATABASE
-- ============================================================
SHOW DATABASES LIKE 'SNOWFLAKE_PUBLIC_DATA_FREE';

SELECT 'MARKETPLACE_DB' AS check_type, 'SNOWFLAKE_PUBLIC_DATA_FREE' AS object_name,
  IFF(COUNT(*) > 0, 'PASS', 'MISSING') AS status
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

-- ============================================================
-- 13. ROW COUNT VALIDATION (minimum expected data)
-- ============================================================
SELECT 'ROW_COUNT' AS check_type, 'MACHINE_MASTER' AS object_name,
  IFF(COUNT(*) >= 4, 'PASS', 'FAIL: expected >= 4') AS status
FROM MACHINE_MASTER;

SELECT 'ROW_COUNT' AS check_type, 'MACHINE_BASELINES' AS object_name,
  IFF(COUNT(*) >= 4, 'PASS', 'FAIL: expected >= 4') AS status
FROM MACHINE_BASELINES;

SELECT 'ROW_COUNT' AS check_type, 'SENSOR_READINGS' AS object_name,
  IFF(COUNT(*) >= 4, 'PASS', 'FAIL: expected >= 4') AS status
FROM SENSOR_READINGS;

SELECT 'ROW_COUNT' AS check_type, 'MAINTENANCE_DOCS' AS object_name,
  IFF(COUNT(*) >= 3, 'PASS', 'FAIL: expected >= 3') AS status
FROM MAINTENANCE_DOCS;

SELECT 'ROW_COUNT' AS check_type, 'SPARE_PARTS' AS object_name,
  IFF(COUNT(*) >= 4, 'PASS', 'FAIL: expected >= 4') AS status
FROM SPARE_PARTS;

-- ============================================================
-- 14. BASELINE INTEGRITY CHECK
-- ============================================================
SELECT 'BASELINE_INTEGRITY' AS check_type, 'Machine_03 vibration_mean' AS object_name,
  IFF(vibration_mean = 2.2, 'PASS', 'FAIL: expected 2.2, got ' || vibration_mean::VARCHAR) AS status
FROM MACHINE_BASELINES
WHERE machine_id = 'Machine_03';

-- ============================================================
-- 15. DYNAMIC TABLE STATE
-- ============================================================
SHOW DYNAMIC TABLES IN SCHEMA PM_OEE_DB.CORE;

SELECT 'DT_STATE' AS check_type, "name" AS object_name,
  IFF("scheduling_state" = 'ACTIVE', 'PASS', 'FAIL: ' || "scheduling_state") AS status
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

-- ============================================================
-- SUMMARY
-- ============================================================
SELECT '=== VALIDATION COMPLETE ===' AS message,
  'Review all results above for PASS/FAIL/MISSING status' AS action;
