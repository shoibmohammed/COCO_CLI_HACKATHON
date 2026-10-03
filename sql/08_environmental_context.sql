-- ============================================================
-- 08_environmental_context.sql
-- Environmental Context table for external Weather & Air Quality API data
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

CREATE TABLE IF NOT EXISTS PM_OEE_DB.CORE.ENVIRONMENTAL_CONTEXT (
    reading_id              NUMBER AUTOINCREMENT PRIMARY KEY,
    plant_id                VARCHAR(100) NOT NULL,
    observed_at             TIMESTAMP_NTZ NOT NULL,
    ambient_temperature_c   FLOAT,
    humidity_percent        FLOAT,
    wind_speed_kmh          FLOAT,
    precipitation_mm        FLOAT,
    air_pressure_hpa        FLOAT,
    air_quality_aqi         FLOAT,
    weather_condition       VARCHAR(100),
    environmental_status    VARCHAR(100),
    source                  VARCHAR(100),
    ingested_at             TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
