-- ============================================================
-- MFG Predictive Maintenance & OEE Command Center — V2
-- 01_setup.sql
-- Run as ACCOUNTADMIN (or a role with equivalent CREATE privileges).
-- ============================================================

CREATE WAREHOUSE IF NOT EXISTS PM_OEE_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE DATABASE IF NOT EXISTS PM_OEE_DB;
CREATE SCHEMA IF NOT EXISTS PM_OEE_DB.CORE;

USE WAREHOUSE PM_OEE_WH;
USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;

-- ------------------------------------------------------------
-- 1. Master / business context
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE MACHINE_MASTER (
    machine_id              VARCHAR(50) PRIMARY KEY,
    machine_name            VARCHAR(100),
    plant                   VARCHAR(100),
    line_name               VARCHAR(100),
    machine_type            VARCHAR(100),
    rated_rpm               FLOAT,
    ideal_cycle_seconds     FLOAT,
    criticality              VARCHAR(20),
    commissioned_date       DATE
);

CREATE OR REPLACE TABLE MACHINE_BASELINES (
    machine_id              VARCHAR(50) PRIMARY KEY,
    vibration_mean          FLOAT,
    vibration_std           FLOAT,
    temperature_mean        FLOAT,
    temperature_std         FLOAT,
    rpm_mean                FLOAT,
    rpm_std                 FLOAT
);

CREATE OR REPLACE TABLE ERP_ASSETS (
    machine_id              VARCHAR(50) PRIMARY KEY,
    supplier                 VARCHAR(100),
    asset_model              VARCHAR(100),
    warranty_end             DATE,
    next_planned_maintenance DATE,
    bearing_part_number      VARCHAR(100),
    bearing_lead_days        NUMBER,
    maintenance_contract     VARCHAR(100)
);

CREATE OR REPLACE TABLE SPARE_PARTS (
    part_number             VARCHAR(100) PRIMARY KEY,
    part_description        VARCHAR(300),
    supplier                 VARCHAR(100),
    quantity_on_hand        NUMBER,
    reorder_point           NUMBER,
    unit_cost_usd           NUMBER(12,2),
    lead_time_days           NUMBER,
    compatible_machine_type VARCHAR(100)
);

CREATE OR REPLACE TABLE MAINTENANCE_HISTORY (
    maintenance_id          NUMBER AUTOINCREMENT,
    machine_id              VARCHAR(50),
    maintenance_ts          TIMESTAMP_NTZ,
    failure_code             VARCHAR(50),
    failure_type             VARCHAR(200),
    root_cause               VARCHAR(500),
    part_replaced             VARCHAR(100),
    downtime_hours           FLOAT,
    repair_cost_usd          NUMBER(12,2),
    technician               VARCHAR(100),
    notes                    VARCHAR(2000)
);

-- ------------------------------------------------------------
-- 2. IoT telemetry
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE SENSOR_READINGS (
    reading_id       NUMBER AUTOINCREMENT PRIMARY KEY,
    ts               TIMESTAMP_NTZ NOT NULL,
    machine_id       VARCHAR(50) NOT NULL,
    vibration_mm_s   FLOAT,
    temperature_c    FLOAT,
    rpm              FLOAT,
    pressure_bar     FLOAT,
    power_kw         FLOAT,
    loaded_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ------------------------------------------------------------
-- 3. Production/OEE events
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE PRODUCTION_EVENTS (
    event_id              NUMBER AUTOINCREMENT PRIMARY KEY,
    machine_id            VARCHAR(50),
    event_ts              TIMESTAMP_NTZ,
    planned_minutes       FLOAT,
    run_minutes           FLOAT,
    total_units           NUMBER,
    good_units            NUMBER,
    downtime_reason       VARCHAR(200)
);

-- ------------------------------------------------------------
-- 4. Knowledge base
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE MAINTENANCE_DOCS (
    chunk_id              NUMBER AUTOINCREMENT PRIMARY KEY,
    source_file            VARCHAR(500),
    page_number            NUMBER,
    chunk_text             VARCHAR(10000),
    file_url               VARCHAR(2000),
    loaded_at              TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE STAGE MAINTENANCE_DOC_STAGE
  ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
  DIRECTORY = (ENABLE = TRUE);

-- ------------------------------------------------------------
-- 5. Prediction / action tables
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE ML_RISK_PREDICTIONS (
    scored_at               TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    machine_id              VARCHAR(50),
    failure_class            VARCHAR(50),
    failure_probability      FLOAT,
    model_version            VARCHAR(100),
    vibration_mm_s           FLOAT,
    temperature_c            FLOAT,
    rpm                      FLOAT
);

CREATE OR REPLACE TABLE RUL_PREDICTIONS (
    scored_at               TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    machine_id              VARCHAR(50),
    estimated_rul_hours      FLOAT,
    confidence               VARCHAR(20),
    degradation_rate_per_hr  FLOAT,
    rul_status               VARCHAR(50),
    basis                    VARCHAR(1000)
);

CREATE OR REPLACE TABLE WORK_ORDERS (
    work_order_id            NUMBER AUTOINCREMENT PRIMARY KEY,
    machine_id               VARCHAR(50),
    priority                 VARCHAR(10),
    status                   VARCHAR(30) DEFAULT 'PENDING_APPROVAL',
    diagnosis                VARCHAR(500),
    recommended_action       VARCHAR(1000),
    parts_required           VARCHAR(2000),
    estimated_downtime_hours FLOAT,
    risk_score               FLOAT,
    rul_hours                FLOAT,
    source_documents         VARCHAR(2000),
    external_ticket_id       VARCHAR(200),
    created_at               TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    approved_at              TIMESTAMP_NTZ
) COMMENT = 'Governed maintenance work orders generated from predictive risk.';

CREATE OR REPLACE TABLE ALERT_LOG (
    alert_id                NUMBER AUTOINCREMENT PRIMARY KEY,
    machine_id              VARCHAR(50),
    severity                VARCHAR(20),
    risk_score               FLOAT,
    alert_reason             VARCHAR(1000),
    created_at                TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    work_order_id            NUMBER
) COMMENT = 'System alert events triggered by ML and statistical risk thresholds.';

CREATE OR REPLACE TABLE MODEL_DRIFT_LOG (
    drift_id                NUMBER AUTOINCREMENT PRIMARY KEY,
    model_name              VARCHAR(100),
    feature_name            VARCHAR(100),
    baseline_start          TIMESTAMP_NTZ,
    baseline_end            TIMESTAMP_NTZ,
    current_start           TIMESTAMP_NTZ,
    current_end             TIMESTAMP_NTZ,
    baseline_mean           FLOAT,
    current_mean            FLOAT,
    drift_score             FLOAT,
    drift_status            VARCHAR(20),
    calculated_at           TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Feature-distribution drift observations used for model-health monitoring.';

-- ------------------------------------------------------------
-- 6. Sensor landing stage + Snowpipe
-- ------------------------------------------------------------
CREATE FILE FORMAT IF NOT EXISTS SENSOR_CSV_FORMAT
  TYPE = 'CSV'
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  NULL_IF = ('', 'NULL');

CREATE OR REPLACE STAGE SENSOR_LANDING_STAGE
  FILE_FORMAT = SENSOR_CSV_FORMAT
  COMMENT = 'IoT telemetry landing stage';

CREATE OR REPLACE PIPE SENSOR_INGEST_PIPE
  AUTO_INGEST = FALSE
  COMMENT = 'Hackathon demo pipe; ALTER PIPE ... REFRESH triggers ingestion'
  AS
  COPY INTO SENSOR_READINGS
    (ts, machine_id, vibration_mm_s, temperature_c, rpm, pressure_bar, power_kw)
  FROM (
    SELECT
      $1::TIMESTAMP_NTZ,
      $2::VARCHAR,
      $3::FLOAT,
      $4::FLOAT,
      $5::FLOAT,
      $6::FLOAT,
      $7::FLOAT
    FROM @SENSOR_LANDING_STAGE
  );

-- ------------------------------------------------------------
-- 7. Dynamic Tables — the unified OT/IT layer
-- ------------------------------------------------------------
CREATE OR REPLACE DYNAMIC TABLE MACHINE_HEALTH_RT
  TARGET_LAG = '1 minute'
  WAREHOUSE = PM_OEE_WH
AS
WITH latest AS (
    SELECT *
    FROM SENSOR_READINGS
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY machine_id ORDER BY ts DESC, reading_id DESC
    ) = 1
)
SELECT
    l.machine_id,
    m.machine_name,
    m.plant,
    m.line_name,
    m.machine_type,
    m.criticality,
    l.ts AS telemetry_ts,
    l.vibration_mm_s,
    l.temperature_c,
    l.rpm,
    l.pressure_bar,
    l.power_kw,
    e.supplier,
    e.asset_model,
    e.next_planned_maintenance,
    e.bearing_part_number,
    e.bearing_lead_days,
    e.maintenance_contract
FROM latest l
JOIN MACHINE_MASTER m ON l.machine_id = m.machine_id
LEFT JOIN ERP_ASSETS e ON l.machine_id = e.machine_id;

CREATE OR REPLACE DYNAMIC TABLE RISK_SCORES_RT
  TARGET_LAG = '1 minute'
  WAREHOUSE = PM_OEE_WH
AS
SELECT
    s.reading_id,
    s.ts,
    s.machine_id,
    s.vibration_mm_s,
    s.temperature_c,
    s.rpm,
    (s.vibration_mm_s - b.vibration_mean) / NULLIF(b.vibration_std, 0) AS z_vibration,
    (s.temperature_c - b.temperature_mean) / NULLIF(b.temperature_std, 0) AS z_temperature,
    (s.rpm - b.rpm_mean) / NULLIF(b.rpm_std, 0) AS z_rpm,
    LEAST(
      1.0,
      GREATEST(
        0.0,
        (
          GREATEST(0, (s.vibration_mm_s - b.vibration_mean) / NULLIF(b.vibration_std, 0)) * 0.45
          + GREATEST(0, (s.temperature_c - b.temperature_mean) / NULLIF(b.temperature_std, 0)) * 0.35
          + GREATEST(0, (b.rpm_mean - s.rpm) / NULLIF(b.rpm_std, 0)) * 0.20
        ) / 6.0
      )
    ) AS risk_score,
    CASE
      WHEN GREATEST(0, (s.vibration_mm_s - b.vibration_mean) / NULLIF(b.vibration_std, 0))
           >= GREATEST(
                GREATEST(0, (s.temperature_c - b.temperature_mean) / NULLIF(b.temperature_std, 0)),
                GREATEST(0, (b.rpm_mean - s.rpm) / NULLIF(b.rpm_std, 0))
              )
        THEN 'Vibration escalation'
      WHEN GREATEST(0, (s.temperature_c - b.temperature_mean) / NULLIF(b.temperature_std, 0))
           >= GREATEST(0, (b.rpm_mean - s.rpm) / NULLIF(b.rpm_std, 0))
        THEN 'Thermal escalation'
      ELSE 'RPM degradation'
    END AS top_reason
FROM SENSOR_READINGS s
JOIN MACHINE_BASELINES b
  ON s.machine_id = b.machine_id;

CREATE OR REPLACE DYNAMIC TABLE OEE_METRICS_RT
  TARGET_LAG = '1 minute'
  WAREHOUSE = PM_OEE_WH
AS
WITH recent AS (
    SELECT *
    FROM PRODUCTION_EVENTS
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY machine_id ORDER BY event_ts DESC, event_id DESC
    ) <= 288
),
agg AS (
    SELECT
      machine_id,
      SUM(planned_minutes) AS planned_minutes,
      SUM(run_minutes) AS run_minutes,
      SUM(total_units) AS total_units,
      SUM(good_units) AS good_units,
      SUM(
        CASE
          WHEN planned_minutes - run_minutes > 0
          THEN planned_minutes - run_minutes
          ELSE 0
        END
      ) AS downtime_minutes
    FROM recent
    GROUP BY machine_id
)
SELECT
  a.machine_id,
  ROUND(100 * a.run_minutes / NULLIF(a.planned_minutes, 0), 2) AS availability_pct,
  ROUND(
    100 * (a.total_units * 6.0) /
    NULLIF(a.run_minutes * 60.0, 0),
    2
  ) AS performance_pct,
  ROUND(100 * a.good_units / NULLIF(a.total_units, 0), 2) AS quality_pct,
  ROUND(
    (
      a.run_minutes / NULLIF(a.planned_minutes, 0)
    )
    *
    LEAST(1.0, (a.total_units * 6.0) / NULLIF(a.run_minutes * 60.0, 0))
    *
    (a.good_units / NULLIF(a.total_units, 0))
    * 100,
    2
  ) AS oee_pct,
  ROUND(a.downtime_minutes, 2) AS downtime_minutes
FROM agg a;

-- ------------------------------------------------------------
-- 8. Useful views
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW MACHINE_LATEST_RISK AS
SELECT *
FROM RISK_SCORES_RT
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY machine_id ORDER BY ts DESC, reading_id DESC
) = 1;

CREATE OR REPLACE VIEW MACHINE_LATEST_HEALTH AS
SELECT
  h.*,
  r.risk_score AS statistical_risk_score,
  r.top_reason,
  r.z_vibration,
  r.z_temperature,
  r.z_rpm
FROM MACHINE_HEALTH_RT h
LEFT JOIN MACHINE_LATEST_RISK r
  ON h.machine_id = r.machine_id;

-- ------------------------------------------------------------
-- 9. Baseline/master grants for demo
-- ------------------------------------------------------------
GRANT USAGE ON WAREHOUSE PM_OEE_WH TO ROLE PUBLIC;
GRANT USAGE ON DATABASE PM_OEE_DB TO ROLE PUBLIC;
GRANT USAGE ON SCHEMA PM_OEE_DB.CORE TO ROLE PUBLIC;
GRANT SELECT ON ALL TABLES IN SCHEMA PM_OEE_DB.CORE TO ROLE PUBLIC;
GRANT SELECT ON ALL VIEWS IN SCHEMA PM_OEE_DB.CORE TO ROLE PUBLIC;

-- Required for Cortex Search / Agent / ML setup.
-- If the hackathon role is not ACCOUNTADMIN, grant these explicitly
-- from an administrator:
-- GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE <hackathon_role>;
-- GRANT CREATE CORTEX SEARCH SERVICE ON SCHEMA PM_OEE_DB.CORE TO ROLE <hackathon_role>;
-- GRANT CREATE AGENT ON SCHEMA PM_OEE_DB.CORE TO ROLE <hackathon_role>;
-- GRANT CREATE SNOWFLAKE.ML.CLASSIFICATION ON SCHEMA PM_OEE_DB.CORE TO ROLE <hackathon_role>;

SELECT '01_setup.sql complete' AS status;
