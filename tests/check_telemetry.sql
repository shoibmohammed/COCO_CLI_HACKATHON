USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

SELECT 'Checking latest SENSOR_READINGS for Machine_03...' AS test_step;
SELECT ts, machine_id, vibration_mm_s, temperature_c, rpm, pressure_bar, power_kw
FROM SENSOR_READINGS
WHERE machine_id = 'Machine_03'
ORDER BY ts DESC
LIMIT 10;

SELECT 'Checking MACHINE_HEALTH_RT for all machines...' AS test_step;
SELECT machine_id, vibration_mm_s, temperature_c, rpm
FROM MACHINE_HEALTH_RT;

SELECT 'Checking MACHINE_LATEST_HEALTH for Machine_03...' AS test_step;
SELECT * FROM MACHINE_LATEST_HEALTH WHERE machine_id = 'Machine_03';
