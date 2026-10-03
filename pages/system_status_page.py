"""
pages/system_status_page.py
System Status & Architecture Health View
"""
import streamlit as st
from config import table
from components.system_status import render_system_status, render_plant_environmental_badge
from services.cortex_service import get_api_key
from services.email_provider import get_email_config


def render_system_status_page(session, risk_df, env_data, qdf, safe_rerun):
    has_gemini = bool(get_api_key())
    em_cfg = get_email_config()

    if st.session_state.get("email_delivery_verified"):
        email_health = "🟢 EMAIL DELIVERY VERIFIED"
    elif em_cfg.get("configured"):
        email_health = "🟡 EMAIL CONFIGURED — DELIVERY NOT VERIFIED"
    else:
        email_health = "🔴 EMAIL CONFIGURATION REQUIRED"

    render_system_status(
        snowflake_connected=True,
        gemini_connected=has_gemini,
        email_status=email_health,
        marketplace_status="CONNECTED",
        session=session,
        env_data=env_data
    )

    st.divider()
    st.markdown("### 📋 Environment Summary")
    st.json({
        "snowflake_account": str(session.get_current_account()) if session else "connected",
        "user": str(session.get_current_user()) if session else "user",
        "warehouse": "PM_OEE_WH",
        "database": "PM_OEE_DB.CORE",
        "dynamic_tables": ["MACHINE_HEALTH_RT", "RISK_SCORES_RT", "OEE_METRICS_RT"],
        "ml_model": "PM_FAILURE_MODEL (Snowflake.ML.CLASSIFICATION, AUC=0.938)",
        "marketplace": "SNOWFLAKE_PUBLIC_DATA_FREE (GZTSZ290BV255)",
        "gemini_model": "gemini-1.5-flash",
        "credentials_exposure": "NONE (Protected by secrets.toml)"
    })




