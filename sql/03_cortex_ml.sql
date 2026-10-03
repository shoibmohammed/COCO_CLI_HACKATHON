-- ============================================================
-- 03_cortex_ml.sql
-- Requires seed_demo_data.py to have populated SENSOR_READINGS.
-- Trains a native Snowflake ML classification model to predict
-- whether a failure is likely within the next six hours.
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

-- ------------------------------------------------------------
-- 1. Create a supervised training dataset from the synthetic history.
-- The target is deliberately constructed from the next 6 hours of
-- telemetry so the demo has a reproducible failure label.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE ML_TRAINING_DATA AS
WITH future AS (
  SELECT
    machine_id,
    ts,
    vibration_mm_s,
    temperature_c,
    rpm,
    pressure_bar,
    power_kw,
    MAX(vibration_mm_s) OVER (
      PARTITION BY machine_id
      ORDER BY ts
      ROWS BETWEEN CURRENT ROW AND 72 FOLLOWING
    ) AS future_max_vibration,
    MAX(temperature_c) OVER (
      PARTITION BY machine_id
      ORDER BY ts
      ROWS BETWEEN CURRENT ROW AND 72 FOLLOWING
    ) AS future_max_temperature,
    MIN(rpm) OVER (
      PARTITION BY machine_id
      ORDER BY ts
      ROWS BETWEEN CURRENT ROW AND 72 FOLLOWING
    ) AS future_min_rpm,
    MAX(ts) OVER (PARTITION BY machine_id) AS machine_max_ts
  FROM SENSOR_READINGS
)
SELECT
  machine_id,
  vibration_mm_s,
  temperature_c,
  rpm,
  pressure_bar,
  power_kw,
  IFF(
    future_max_vibration >= 5.0
    OR future_max_temperature >= 85.0
    OR future_min_rpm <= 1300.0,
    TRUE,
    FALSE
  ) AS failure_next_6h
FROM future
WHERE ts <= DATEADD('hour', -6, machine_max_ts);

-- ------------------------------------------------------------
-- 2. Native Snowflake ML classification model.
-- ------------------------------------------------------------
CREATE OR REPLACE SNOWFLAKE.ML.CLASSIFICATION PM_FAILURE_MODEL(
  INPUT_DATA => SYSTEM$REFERENCE('TABLE', 'PM_OEE_DB.CORE.ML_TRAINING_DATA'),
  TARGET_COLNAME => 'FAILURE_NEXT_6H',
  CONFIG_OBJECT => {'evaluate': TRUE}
);

-- Give the demo role permission to invoke predictions.
-- If your hackathon user is not PUBLIC, replace PUBLIC with its role.
GRANT SNOWFLAKE.ML.CLASSIFICATION ROLE PM_FAILURE_MODEL!mlconsumer TO ROLE PUBLIC;

-- ------------------------------------------------------------
-- 3. Latest prediction input and unified prediction table.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW ML_PREDICTION_INPUT AS
SELECT
  machine_id,
  vibration_mm_s,
  temperature_c,
  rpm,
  pressure_bar,
  power_kw
FROM MACHINE_HEALTH_RT;

CREATE OR REPLACE PROCEDURE REFRESH_ML_RISK()
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS OWNER
AS
$$
BEGIN
  TRUNCATE TABLE ML_RISK_PREDICTIONS;

  INSERT INTO ML_RISK_PREDICTIONS
    (machine_id, failure_class, failure_probability,
     model_version, vibration_mm_s, temperature_c, rpm)
  SELECT
    machine_id,
    prediction['class']::VARCHAR,
    COALESCE(
      prediction['probability']['True']::FLOAT,
      prediction['probability']['TRUE']::FLOAT,
      prediction['probability']['true']::FLOAT,
      0.0
    ),
    'PM_FAILURE_MODEL',
    vibration_mm_s,
    temperature_c,
    rpm
  FROM (
    SELECT
      p.*,
      PM_FAILURE_MODEL!PREDICT(INPUT_DATA => {*}) AS prediction
    FROM ML_PREDICTION_INPUT p
  );

  RETURN 'ML predictions refreshed';
END;
$$;

CREATE OR REPLACE VIEW MACHINE_RISK_UNIFIED AS
WITH latest_ml AS (
  SELECT *
  FROM ML_RISK_PREDICTIONS
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY machine_id ORDER BY scored_at DESC
  ) = 1
),
latest_stat AS (
  SELECT *
  FROM MACHINE_LATEST_RISK
)
SELECT
  s.machine_id,
  s.ts AS telemetry_ts,
  s.vibration_mm_s,
  s.temperature_c,
  s.rpm,
  s.z_vibration,
  s.z_temperature,
  s.z_rpm,
  s.risk_score AS statistical_risk_score,
  s.top_reason,
  m.failure_class,
  m.failure_probability AS ml_failure_probability,
  GREATEST(
    s.risk_score,
    COALESCE(m.failure_probability, 0)
  ) AS unified_risk_score
FROM latest_stat s
LEFT JOIN latest_ml m
  ON s.machine_id = m.machine_id;

-- Run the model once after creation.
CALL REFRESH_ML_RISK();

-- Model evaluation for the judge Q&A.
CALL PM_FAILURE_MODEL!SHOW_GLOBAL_EVALUATION_METRICS();
CALL PM_FAILURE_MODEL!SHOW_FEATURE_IMPORTANCE();

SELECT * FROM MACHINE_RISK_UNIFIED ORDER BY unified_risk_score DESC;
