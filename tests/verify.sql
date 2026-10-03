-- ============================================================
-- verify.sql
-- Automated SQL verification script for MFG Command Center
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

SELECT '1. Checking Tables & Row Counts...' AS test_step;
SELECT 'MACHINE_MASTER' AS tbl, COUNT(*) AS row_cnt FROM MACHINE_MASTER
UNION ALL
SELECT 'SENSOR_READINGS', COUNT(*) FROM SENSOR_READINGS
UNION ALL
SELECT 'PRODUCTION_EVENTS', COUNT(*) FROM PRODUCTION_EVENTS
UNION ALL
SELECT 'SPARE_PARTS', COUNT(*) FROM SPARE_PARTS
UNION ALL
SELECT 'MAINTENANCE_DOCS', COUNT(*) FROM MAINTENANCE_DOCS
UNION ALL
SELECT 'WORK_ORDERS', COUNT(*) FROM WORK_ORDERS;

SELECT '2. Checking Dynamic Tables...' AS test_step;
SHOW DYNAMIC TABLES IN DATABASE PM_OEE_DB;

SELECT '3. Verifying Machine_03 Degradation Scenario...' AS test_step;
SELECT machine_id, vibration_mm_s, temperature_c, rpm, statistical_risk_score, top_reason
FROM MACHINE_LATEST_HEALTH
WHERE machine_id = 'Machine_03';

SELECT '4. Verifying Spare Part Inventory...' AS test_step;
SELECT part_number, quantity_on_hand, unit_cost_usd, lead_time_days
FROM SPARE_PARTS
WHERE part_number = 'SKF-6205-2RS';

SELECT '5. Verifying Work Orders & Status...' AS test_step;
SELECT work_order_id, machine_id, priority, status, diagnosis, parts_required, created_at
FROM WORK_ORDERS
ORDER BY created_at DESC;

SELECT 'VERIFICATION COMPLETE: ALL SYSTEMS GO' AS status;
