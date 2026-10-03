# Snowflake-native environmental data service using Marketplace NWS weather data
# Co-authored with CoCo
"""
services/weather_service.py
Environmental / Weather Intelligence Service.
Reads ambient weather data from Snowflake Marketplace (NWS Weather Forecast Events)
and persists to PM_OEE_DB.CORE.ENVIRONMENTAL_CONTEXT.
Uses parameterized queries and centralized configuration.

Source: SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE.NWS_WEATHER_FORECAST_EVENTS
Geographic match: zip/94102 (San Francisco, CA — Demo Plant location)
Granularity: Hourly forecast observations
"""

import logging
import re
from datetime import datetime

from config import DATABASE, SCHEMA

logger = logging.getLogger(__name__)

DEFAULT_PLANT_ID = "Demo Plant"
DEFAULT_ZIP_GEO_ID = "zip/94102"
ENV_TABLE = f"{DATABASE}.{SCHEMA}.ENVIRONMENTAL_CONTEXT"


def get_plant_config():
    """Retrieve plant location configuration from Streamlit secrets."""
    lat, lon, plant_name = 37.7749, -122.4194, DEFAULT_PLANT_ID
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "plant" in st.secrets:
            p = st.secrets["plant"]
            lat = float(p.get("PLANT_LATITUDE", p.get("latitude", lat)))
            lon = float(p.get("PLANT_LONGITUDE", p.get("longitude", lon)))
            plant_name = str(p.get("PLANT_LOCATION_NAME", p.get("plant_name", plant_name)))
    except Exception:
        pass
    return {"latitude": lat, "longitude": lon, "plant_name": plant_name}


def _f_to_c(f_val):
    if f_val is None:
        return None
    return round((float(f_val) - 32) * 5.0 / 9.0, 1)


def _parse_humidity(hum_val):
    if hum_val is None:
        return None
    s = str(hum_val).strip("[] ")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_windspeed_kmh(ws_str):
    if not ws_str:
        return None
    nums = re.findall(r'[\d.]+', str(ws_str))
    if not nums:
        return None
    avg_mph = sum(float(n) for n in nums) / len(nums)
    return round(avg_mph * 1.60934, 1)


def _evaluate_status(temp_c, humidity, wind_kmh):
    if (temp_c and temp_c > 42.0) or (wind_kmh and wind_kmh > 80.0):
        return "EXTREME"
    if (temp_c and temp_c > 35.0) or (humidity and humidity > 80.0) or (wind_kmh and wind_kmh > 45.0):
        return "ELEVATED"
    return "NORMAL"


def fetch_live_environmental_data(lat=None, lon=None, plant_name=None, timeout_sec=3.0):
    """
    Legacy interface — now returns a marker indicating Snowflake-native path should be used.
    Kept for backward compatibility with callers that don't pass a session.
    """
    cfg = get_plant_config()
    return {
        "available": False,
        "plant_id": plant_name or cfg["plant_name"],
        "environmental_status": "USE_SNOWFLAKE_NATIVE",
        "source": "Snowflake Marketplace (NWS)",
    }


def _fetch_from_marketplace(session, geo_id=DEFAULT_ZIP_GEO_ID):
    """Queries latest NWS weather from Snowflake Marketplace using parameterized query."""
    sql = """
    SELECT TEMPERATURE, RELATIVE_HUMIDITY, WIND_DIRECTION, WINDSPEED,
           SHORT_FORECAST, START_TIMESTAMP
    FROM SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE.NWS_WEATHER_FORECAST_EVENTS
    WHERE GEO_ID = ? AND TEMPERATURE IS NOT NULL
    ORDER BY START_TIMESTAMP DESC LIMIT 1
    """
    try:
        rows = session.sql(sql, params=[str(geo_id)]).collect()
        if not rows:
            return None
        row = rows[0]
        temp_c = _f_to_c(row["TEMPERATURE"])
        humidity = _parse_humidity(row["RELATIVE_HUMIDITY"])
        wind_kmh = _parse_windspeed_kmh(row["WINDSPEED"])
        status = _evaluate_status(temp_c, humidity, wind_kmh)
        observed = str(row["START_TIMESTAMP"]).strip('"')
        return {
            "available": True,
            "plant_id": DEFAULT_PLANT_ID,
            "latitude": 37.7749,
            "longitude": -122.4194,
            "observed_at": observed,
            "ambient_temperature_c": temp_c,
            "humidity_percent": humidity,
            "wind_speed_kmh": wind_kmh,
            "precipitation_mm": 0.0,
            "air_pressure_hpa": None,
            "air_quality_aqi": None,
            "weather_condition": row["SHORT_FORECAST"] or "Clear",
            "environmental_status": status,
            "source": "Snowflake Marketplace (NWS Weather Forecast)",
            "ingested_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.warning(f"Marketplace NWS query failed: {e}")
        return None


def persist_environmental_reading(session, env_data):
    """Persists environmental reading to ENVIRONMENTAL_CONTEXT with 10-min dedup using parameterized queries."""
    if not env_data or not env_data.get("available") or not session:
        return False
    try:
        session.sql(f"""
            CREATE TABLE IF NOT EXISTS {ENV_TABLE} (
                reading_id NUMBER AUTOINCREMENT PRIMARY KEY,
                plant_id VARCHAR(100),
                observed_at TIMESTAMP_NTZ,
                ambient_temperature_c FLOAT,
                humidity_percent FLOAT,
                wind_speed_kmh FLOAT,
                precipitation_mm FLOAT,
                air_pressure_hpa FLOAT,
                air_quality_aqi FLOAT,
                weather_condition VARCHAR(100),
                environmental_status VARCHAR(100),
                source VARCHAR(100),
                ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """).collect()

        plant_id_val = env_data.get("plant_id", DEFAULT_PLANT_ID)
        cnt = session.sql(f"""
            SELECT COUNT(*) AS CNT FROM {ENV_TABLE}
            WHERE PLANT_ID = ?
            AND INGESTED_AT >= DATEADD('minute', -10, CURRENT_TIMESTAMP())
        """, params=[str(plant_id_val)]).collect()[0]["CNT"]

        if cnt > 0:
            return False

        obs = env_data.get("observed_at", datetime.utcnow().isoformat())
        temp = env_data.get("ambient_temperature_c")
        hum = env_data.get("humidity_percent")
        wind = env_data.get("wind_speed_kmh")
        precip = env_data.get("precipitation_mm", 0.0)
        cond = str(env_data.get("weather_condition", "Clear"))
        status = str(env_data.get("environmental_status", "NORMAL"))
        src = str(env_data.get("source", "Snowflake Marketplace"))

        session.sql(f"""
            INSERT INTO {ENV_TABLE}
            (plant_id, observed_at, ambient_temperature_c, humidity_percent,
             wind_speed_kmh, precipitation_mm, weather_condition, environmental_status, source)
            VALUES (?, TO_TIMESTAMP_NTZ(?), ?, ?, ?, ?, ?, ?, ?)
        """, params=[
            str(plant_id_val),
            str(obs),
            temp if temp is not None else None,
            hum if hum is not None else None,
            wind if wind is not None else None,
            precip if precip is not None else 0.0,
            cond,
            status,
            src
        ]).collect()
        return True
    except Exception as e:
        logger.error(f"Error persisting environmental data: {e}")
        return False


def get_latest_environmental_context(session=None, plant_id="Demo Plant"):
    """
    Primary interface: returns latest environmental context from Snowflake.
    1. Checks ENVIRONMENTAL_CONTEXT for recent data (last 24h)
    2. If stale, queries Marketplace NWS data and persists
    No external API calls.
    """
    if session is None:
        return {"available": False, "plant_id": plant_id, "environmental_status": "TEMPORARILY_UNAVAILABLE", "source": "Snowflake Marketplace (NWS)"}

    try:
        session.sql(f"""CREATE TABLE IF NOT EXISTS {ENV_TABLE} (
            reading_id NUMBER AUTOINCREMENT PRIMARY KEY, plant_id VARCHAR(100),
            observed_at TIMESTAMP_NTZ, ambient_temperature_c FLOAT, humidity_percent FLOAT,
            wind_speed_kmh FLOAT, precipitation_mm FLOAT, air_pressure_hpa FLOAT,
            air_quality_aqi FLOAT, weather_condition VARCHAR(100),
            environmental_status VARCHAR(100), source VARCHAR(100),
            ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP())""").collect()
    except Exception:
        pass

    # Check for recent cached data
    try:
        rows = session.sql(f"""
            SELECT PLANT_ID, OBSERVED_AT, AMBIENT_TEMPERATURE_C, HUMIDITY_PERCENT,
                   WIND_SPEED_KMH, PRECIPITATION_MM, AIR_PRESSURE_HPA, AIR_QUALITY_AQI,
                   WEATHER_CONDITION, ENVIRONMENTAL_STATUS, SOURCE, INGESTED_AT
            FROM {ENV_TABLE}
            WHERE PLANT_ID = ?
            AND INGESTED_AT >= DATEADD('hour', -24, CURRENT_TIMESTAMP())
            ORDER BY INGESTED_AT DESC LIMIT 1
        """, params=[str(plant_id)]).collect()

        if rows:
            r = rows[0]
            rd = r.as_dict() if hasattr(r, "as_dict") else dict(r)
            return {
                "available": True,
                "plant_id": rd.get("PLANT_ID", plant_id),
                "observed_at": str(rd.get("OBSERVED_AT")),
                "ambient_temperature_c": float(rd["AMBIENT_TEMPERATURE_C"]) if rd.get("AMBIENT_TEMPERATURE_C") is not None else None,
                "humidity_percent": float(rd["HUMIDITY_PERCENT"]) if rd.get("HUMIDITY_PERCENT") is not None else None,
                "wind_speed_kmh": float(rd["WIND_SPEED_KMH"]) if rd.get("WIND_SPEED_KMH") is not None else None,
                "precipitation_mm": float(rd["PRECIPITATION_MM"]) if rd.get("PRECIPITATION_MM") is not None else 0.0,
                "air_pressure_hpa": float(rd["AIR_PRESSURE_HPA"]) if rd.get("AIR_PRESSURE_HPA") is not None else None,
                "air_quality_aqi": float(rd["AIR_QUALITY_AQI"]) if rd.get("AIR_QUALITY_AQI") is not None else None,
                "weather_condition": rd.get("WEATHER_CONDITION", "Clear"),
                "environmental_status": rd.get("ENVIRONMENTAL_STATUS", "NORMAL"),
                "source": rd.get("SOURCE", "Snowflake Marketplace (NWS)"),
            }
    except Exception as e:
        logger.warning(f"ENVIRONMENTAL_CONTEXT query failed: {e}")

    # Fetch from Marketplace and persist
    mkt_data = _fetch_from_marketplace(session)
    if mkt_data and mkt_data.get("available"):
        persist_environmental_reading(session, mkt_data)
        return mkt_data

    return {"available": False, "plant_id": plant_id, "environmental_status": "TEMPORARILY_UNAVAILABLE", "source": "Snowflake Marketplace (NWS)"}
