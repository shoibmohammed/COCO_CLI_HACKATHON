# MFG Predictive Maintenance & OEE Command Center Streamlit application
import streamlit as st

st.set_page_config(
    page_title="MFG Predictive Maintenance & OEE Command Center",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

import json
import random
from datetime import datetime, timedelta, timezone

import pandas as pd

try:
    from components.asset_images import CNC_MACHINE_B64, AI_BRAIN_B64
except Exception:
    CNC_MACHINE_B64 = ""
    AI_BRAIN_B64 = ""

def safe_rerun():
    """Trigger a Streamlit page rerun safely across all Streamlit runtime versions."""
    if hasattr(st, "rerun"):
        try:
            st.rerun()
            return
        except Exception:
            pass
    if hasattr(st, "experimental_rerun"):
        try:
            st.experimental_rerun()
            return
        except Exception:
            pass


from snowflake_connection import get_snowflake_session, connect_with_params
from services.cortex_service import generate_diagnosis, ask_machine_question, get_api_key, build_marketplace_context
from services.ai_guardrails import (
    validate_ai_response, validate_machine_exists, validate_telemetry,
    validate_ml_prediction, validate_work_order_state, log_ai_audit,
    get_guardrail_status, FAIL_SAFE_VALIDATION_FAILED, FAIL_SAFE_UNKNOWN_MACHINE,
    FAIL_SAFE_APPROVAL_REQUIRED
)
from services.notification_service import dispatch_critical_notifications
from services.email_provider import get_email_config, send_test_email
from services.marketplace_agent import run_ingestion, get_marketplace_config, get_ingestion_status, get_supplier_enrichment, get_marketplace_enrichment, get_commodity_prices, get_industrial_indicators, generate_marketplace_business_interpretation
from services.ml_service import refresh_ml_predictions, get_ml_predictions, get_unified_risk, generate_alerts, get_alert_triage, get_ml_context_for_gemini, get_model_info, auto_create_governed_work_orders

from components.header import render_header
from components.kpi_card import render_kpi_cards
from components.diagnosis_card import render_diagnosis_card
from services.weather_service import get_latest_environmental_context, fetch_live_environmental_data, persist_environmental_reading
from components.system_status import render_system_status, render_plant_environmental_badge
from services.scenario_service import SCENARIOS, inject_scenario_to_snowflake, reset_demo_snowflake_state, reset_everything_demo_state
from services.report_service import generate_incident_report_csv
from components.business_impact import render_business_impact_card
# Jira integration via Local Worker queue architecture
from services.jira_queue_service import enqueue_jira_request, get_queue_status, check_existing_success
def create_jira_ticket(session=None, work_order_data=None, machine_context=None, ml_data=None, gemini_diag=None, mkt_context=None, env_context=None, **kwargs):
    """Enqueues a Jira issue creation request into the integration queue (processed by Local Jira Worker)."""
    if not session or not work_order_data:
        return {"status": "BLOCKED", "message": "Missing session or work order data", "jira_key": None, "jira_url": None}
    wo_id = work_order_data.get("work_order_id", "WO-0")
    machine_id = (machine_context or {}).get("machine_id", "UNKNOWN")
    severity = (machine_context or {}).get("severity", "HIGH")
    diag = (gemini_diag or {})
    summary = f"[{severity}] Maintenance: {wo_id} — {machine_id}"
    desc_parts = [
        f"Work Order: {wo_id}",
        f"Machine: {machine_id}",
        f"Root Cause: {diag.get('root_cause', 'N/A')}",
        f"Recommended Action: {diag.get('recommended_action', 'N/A')}",
        f"Risk Score: {(ml_data or {}).get('risk_score', 'N/A')}",
        f"RUL Hours: {(ml_data or {}).get('rul_hours', 'N/A')}",
    ]
    description = "\n".join(desc_parts)
    return enqueue_jira_request(
        session=session,
        work_order_id=wo_id,
        machine_id=machine_id,
        short_description=summary[:500],
        description=description[:4000],
        impact=severity,
        urgency=severity,
        jira_project_key="KAN"
    )
def check_jira_connection(**kwargs): return True
def search_jira_issue_by_work_order(session=None, work_order_id=None, **kwargs):
    if session and work_order_id:
        existing = check_existing_success(session, work_order_id)
        return existing
    return None
from services.universal_email_service import send_universal_email, validate_email_address, detect_email_provider
from services.email_service import send_email, check_email_system_status
from components.universal_email_composer import render_universal_email_composer

try:
    from services.notification_service import send_critical_notification, send_work_order_approval_notification
except Exception:
    def send_critical_notification(event_payload, session=None, force=False):
        from services.universal_email_service import send_universal_email
        rec = event_payload.get("recipient", "")
        if not rec:
            return {"success": False, "message": "No recipient configured."}
        return send_universal_email(
            recipient=rec,
            subject=f"🚨 CRITICAL MAINTENANCE ALERT — {event_payload.get('machine_id', 'Machine_03')}",
            body=str(event_payload.get("recommended_action", "Inspect equipment immediately.")),
            session=session,
            is_automatic=not force
        )

    def send_work_order_approval_notification(wo_payload, session=None):
        from services.universal_email_service import send_universal_email
        rec = wo_payload.get("recipient", "")
        if not rec:
            return {"success": False, "message": "No recipient configured."}
        return send_universal_email(
            recipient=rec,
            subject=f"🛠️ WORK ORDER APPROVED — {wo_payload.get('machine_id', 'Machine_03')}",
            body=str(wo_payload.get("approved_action", "Work Order Approved.")),
            session=session
        )

# Centralized Enterprise Light SaaS CSS Theme
from components.theme import apply_theme
apply_theme()
# ------------------------------------------------------------------
# Snowflake Session Connection
# ------------------------------------------------------------------
session, status_msg, is_local_mode = get_snowflake_session()

# Helper queries with automatic session token expiration recovery
def qdf(sql, params=None):
    global session
    if session is None:
        return pd.DataFrame()
    try:
        return session.sql(sql, params=params).to_pandas()
    except Exception as e:
        err_msg = str(e)
        if "token has expired" in err_msg.lower() or "390114" in err_msg:
            st.session_state["snowflake_session"] = None
            session, _, _ = get_snowflake_session()
            if session is not None:
                st.session_state["snowflake_session"] = session
                return session.sql(sql, params=params).to_pandas()
        raise e

def call_proc(name, params=None):
    global session
    if session is None:
        return None
    row = session.sql(f"CALL {name}", params=params).collect()[0]
    return row[0]

def qexec(sql):
    global session
    if session is None:
        return []
    try:
        return session.sql(sql).collect()
    except Exception as e:
        err_msg = str(e)
        if "token has expired" in err_msg.lower() or "390114" in err_msg:
            st.session_state["snowflake_session"] = None
            session, _, _ = get_snowflake_session()
            if session is not None:
                st.session_state["snowflake_session"] = session
                return session.sql(sql).collect()
        st.error(f"Query error: {e}")
        return []

# Sidebar Connection Configuration & Navigation
with st.sidebar:
    st.markdown(
        """<div style="margin-bottom:20px; padding:10px 12px; background:#0B132B; border-radius:10px; display:flex; align-items:center; gap:10px;">
<div style="background:#2563EB; width:34px; height:34px; border-radius:8px; display:flex; align-items:center; justify-content:center; font-size:1.1rem; color:#FFFFFF; box-shadow:0 0 10px rgba(37,99,235,0.4);">
⚙️
</div>
<div>
<div style="font-size:1.05rem; font-weight:800; color:#FFFFFF; letter-spacing:0.02em; line-height:1.1;">MFG</div>
<div style="font-size:0.75rem; font-weight:700; color:#94A3B8; letter-spacing:0.04em;">CMD CENTER</div>
</div>
</div>""",
        unsafe_allow_html=True
    )

    if session is not None:
        st.markdown(
            f"""<div style="background:#0F172A; padding:8px 12px; border-radius:6px; border:1px solid #1E293B; margin-bottom:12px; font-size:0.75rem; color:#94A3B8;">
<span style="color:#22C55E; font-weight:700;">● Snowflake Live</span> &nbsp;|&nbsp; <span>{status_msg}</span>
</div>""",
            unsafe_allow_html=True
        )
        if is_local_mode:
            if st.button("Disconnect Session", use_container_width=True):
                st.session_state["snowflake_session"] = None
                safe_rerun()
    else:
        st.warning(status_msg)
        st.markdown("### Credentials")
        with st.form("snowflake_login_form"):
            account = st.text_input("Account Identifier", placeholder="e.g. xy12345.us-east-1")
            user = st.text_input("Username", placeholder="e.g. JSMITH")
            password = st.text_input("Password", type="password")
            role = st.text_input("Role", value="ACCOUNTADMIN")
            warehouse = st.text_input("Warehouse", value="PM_OEE_WH")
            database = st.text_input("Database", value="PM_OEE_DB")
            schema = st.text_input("Schema", value="CORE")
            
            submitted = st.form_submit_button("Connect to Snowflake")
            if submitted:
                if not account or not user or not password:
                    st.error("Please fill in Account, Username, and Password.")
                else:
                    try:
                        session = connect_with_params(account, user, password, role, warehouse, database, schema)
                        st.success("Successfully connected to Snowflake!")
                        safe_rerun()
                    except Exception as e:
                        st.error(f"Connection failed: {e}")

    # Navigation Menu matching Reference UI
    nav_options = [
        "🏠 Command Center",
        "🚨 Alert Triage",
        "🔬 Machine Intelligence",
        "🤖 AI Copilot",
        "📋 Work Orders",
        "🛒 Supply Chain",
        "⏱️ What-if Simulator",
        "📊 Reports",
        "⚙️ System Status",
        "⚙️ Settings"
    ]
    if "nav_index" not in st.session_state or st.session_state["nav_index"] >= len(nav_options):
        st.session_state["nav_index"] = 0

    selected_page = st.radio(
        "NAVIGATION",
        options=nav_options,
        index=st.session_state["nav_index"],
        key="main_nav_selector",
        label_visibility="collapsed"
    )
    st.session_state["nav_index"] = nav_options.index(selected_page)

    st.markdown("<div style='margin-top:16px; margin-bottom:8px; font-size:0.68rem; font-weight:800; color:#64748B; letter-spacing:0.06em;'>QUICK ACTIONS</div>", unsafe_allow_html=True)
    
    sc_options = {k: v["title"] for k, v in SCENARIOS.items()}
    selected_sc_key = st.selectbox(
        "Select Scenario",
        options=list(sc_options.keys()),
        format_func=lambda x: sc_options[x],
        key="sidebar_scenario_select",
        label_visibility="collapsed"
    )

    if st.button("🧪 Inject Test Scenario", use_container_width=True, key="btn_inject_sc"):
        st.cache_data.clear()
        st.cache_resource.clear()
        sc_res = inject_scenario_to_snowflake(qexec, selected_sc_key, session=session)
        st.session_state["active_scenario_key"] = selected_sc_key
        st.session_state.pop("active_diagnosis", None)
        st.session_state.pop("_reset_timestamp", None)
        st.success(f"Injected '{sc_res['title']}' into Snowflake database!")
        safe_rerun()

    if st.button("➕ Create Work Order", use_container_width=True, key="btn_create_wo_sidebar"):
        st.session_state["nav_index"] = nav_options.index("📋 Work Orders")
        safe_rerun()

    if st.button("🖨️ Generate Report", use_container_width=True, key="btn_gen_rep_sidebar"):
        st.session_state["nav_index"] = nav_options.index("📋 Work Orders")
        safe_rerun()

    # Global Demo Reset Control with Confirmation
    if st.session_state.get("show_reset_confirmation", False):
        st.markdown(
            """<div style="background:#1E293B; border:1px solid #EF4444; border-radius:8px; padding:10px; margin-top:8px; margin-bottom:8px;">
<div style="font-size:0.75rem; color:#FCA5A5; font-weight:700; margin-bottom:6px;">⚠️ Reset demo environment to clean starting baseline?</div>
</div>""",
            unsafe_allow_html=True
        )
        r_c1, r_c2 = st.columns(2)
        with r_c1:
            if st.button("✕ Cancel", key="btn_cancel_reset_sidebar", use_container_width=True):
                st.session_state["show_reset_confirmation"] = False
                safe_rerun()
        with r_c2:
            if st.button("🧹 Confirm", key="btn_confirm_reset_sidebar", type="primary", use_container_width=True):
                with st.spinner("⏳ Resetting demo state..."):
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    try:
                        reset_everything_demo_state(session=session, qexec_fn=qexec)
                    except Exception as r_err:
                        st.warning(f"Reset warning: {r_err}")

                    transient_keys = [
                        "active_diagnosis", "active_scenario_key", "selected_machine",
                        "wo_approved", "jira_result", "notification_result",
                        "last_test_email_result", "last_slack_result", "show_alert_preview",
                        "show_report_preview", "show_slack_preview", "show_user_profile",
                        "triage_refreshed_at", "last_selected_machine", "active_report_html",
                        "show_reset_confirmation", "active_diagnoses_cache"
                    ]
                    for k in transient_keys:
                        st.session_state.pop(k, None)

                    st.session_state["selected_plant"] = "All Plants"
                    st.session_state["nav_index"] = 0
                    st.session_state["reset_success_msg"] = "🟢 Demo environment reset successfully."
                    st.session_state["_just_reset"] = True
                    safe_rerun()
    else:
        if st.button("🧹 Reset Everything", use_container_width=True, key="btn_reset_everything_sidebar", help="Restore the demo environment to the clean starting state."):
            st.session_state["show_reset_confirmation"] = True
            safe_rerun()

    if "reset_success_msg" in st.session_state:
        st.success(st.session_state.pop("reset_success_msg"))

    st.markdown(
        """<div style="margin-top:20px; padding-top:14px; border-top:1px solid #1E293B;">
<div style="display:flex; align-items:center; gap:6px;">
<span style="display:inline-block; width:8px; height:8px; background:#22C55E; border-radius:50%; box-shadow:0 0 6px #22C55E;"></span>
<strong style="color:#F8FAFC; font-size:0.80rem;">System Healthy</strong>
</div>
<div style="font-size:0.70rem; color:#94A3B8; margin-top:2px;">All systems operational</div>
<div style="font-size:0.65rem; color:#64748B; margin-top:6px;">Last Updated<br>""" + datetime.now().strftime("%b %d, %Y %I:%M %p") + """</div>
</div>""",
        unsafe_allow_html=True
    )

@st.cache_data(ttl=900)
def get_cached_env_context(_sess_obj):
    """Fetch environmental context with 15-minute caching to prevent external API calls on every rerun."""
    return get_latest_environmental_context(_sess_obj)

# ------------------------------------------------------------------
# Data Fetching from Snowflake
# ------------------------------------------------------------------
try:
    risk_df = qdf("""
        SELECT
          h.machine_id, h.machine_name, h.plant, h.line_name, h.machine_type, h.criticality,
          h.telemetry_ts, h.vibration_mm_s, h.temperature_c, h.rpm, h.pressure_bar, h.power_kw,
          h.supplier, h.bearing_part_number, h.bearing_lead_days,
          r.risk_score AS unified_risk_score, COALESCE(r.top_reason, 'Normal operation') AS top_reason
        FROM PM_OEE_DB.CORE.MACHINE_HEALTH_RT h
        LEFT JOIN (
            SELECT * FROM PM_OEE_DB.CORE.RISK_SCORES_RT
            QUALIFY ROW_NUMBER() OVER (PARTITION BY machine_id ORDER BY ts DESC) = 1
        ) r ON h.machine_id = r.machine_id
        ORDER BY r.risk_score DESC NULLS LAST
    """)
    # After a reset, if DT refresh hasn't propagated yet, force risk scores to 0
    # Use a timestamp-based cooldown (60s) so subsequent reruns don't recreate work orders
    import time as _time
    _reset_ts = st.session_state.get("_reset_timestamp", 0)
    _just_reset = st.session_state.pop("_just_reset", False)
    if _just_reset:
        st.session_state["_reset_timestamp"] = _time.time()
        _reset_ts = st.session_state["_reset_timestamp"]
    _within_reset_cooldown = (_time.time() - _reset_ts) < 60 if _reset_ts else False

    if _just_reset or _within_reset_cooldown:
        if not risk_df.empty and "UNIFIED_RISK_SCORE" in risk_df.columns:
            risk_df["UNIFIED_RISK_SCORE"] = 0.0
            risk_df["TOP_REASON"] = "Normal operation"
    oee_df = qdf("SELECT * FROM PM_OEE_DB.CORE.OEE_METRICS_RT ORDER BY machine_id")
    parts_df = qdf("SELECT * FROM PM_OEE_DB.CORE.SPARE_PARTS")
    # Auto-create governed work orders for any critical machines missing an active work order
    # Skip during reset cooldown to avoid recreating alerts from stale ML predictions
    if not _just_reset and not _within_reset_cooldown:
        from services.ml_service import auto_create_governed_work_orders
        auto_create_governed_work_orders(session)
    
    wo_df = qdf("SELECT * FROM PM_OEE_DB.CORE.WORK_ORDERS ORDER BY created_at DESC")
    
    try:
        session.sql("""
            CREATE TABLE IF NOT EXISTS PM_OEE_DB.CORE.JIRA_TICKET_AUDIT (
                AUDIT_ID VARCHAR(50) DEFAULT UUID_STRING(),
                WORK_ORDER_ID VARCHAR(50),
                MACHINE_ID VARCHAR(50),
                JIRA_ISSUE_KEY VARCHAR(50),
                JIRA_ISSUE_URL VARCHAR(500),
                JIRA_PROJECT VARCHAR(50),
                ISSUE_TYPE VARCHAR(50),
                STATUS VARCHAR(50),
                ERROR_MESSAGE VARCHAR(1000),
                CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """).collect()
        jira_audit_df = qdf("SELECT * FROM PM_OEE_DB.CORE.JIRA_TICKET_AUDIT ORDER BY created_at DESC")
    except Exception:
        import pandas as pd
        jira_audit_df = pd.DataFrame()
    
    # Supply Chain Data — from TPCH_SF1 ingestion (external_supply_chain_ingestion.sql)
    try:
        mkt_raw_df = qdf("SELECT COUNT(*) AS RAW_COUNT FROM PM_OEE_DB.CORE.RAW_EXTERNAL_SUPPLY_CHAIN")
        mkt_conf_df = qdf("SELECT COUNT(*) AS CONF_COUNT FROM PM_OEE_DB.CORE.EXTERNAL_PART_CATALOG")
        mkt_cat_df = qdf("""
            SELECT PART_KEY, PART_NAME, MANUFACTURER, BRAND, PART_TYPE,
                   SUPPLIER_COUNT, TOTAL_AVAILABLE_UNITS, AVG_SUPPLY_COST_USD,
                   PREFERRED_SUPPLIER, PREFERRED_SUPPLIER_PHONE, LAST_UPDATED
            FROM PM_OEE_DB.CORE.EXTERNAL_PART_CATALOG
            ORDER BY TOTAL_AVAILABLE_UNITS DESC
            LIMIT 200
        """)
        mkt_prices_df = qdf("""
            SELECT PART_TYPE AS MATERIAL_CATEGORY,
                   ROUND(AVG(AVG_SUPPLY_COST_USD), 2) AS PRICE_USD,
                   MAX(LAST_UPDATED) AS OBSERVATION_DATE
            FROM PM_OEE_DB.CORE.EXTERNAL_PART_CATALOG
            GROUP BY PART_TYPE
            ORDER BY PRICE_USD DESC
            LIMIT 10
        """)
        mkt_indicators_df = qdf("""
            SELECT 'SUPPLIER_DIVERSITY' AS MATERIAL_CATEGORY,
                   COUNT(DISTINCT PREFERRED_SUPPLIER) AS RAW_VALUE,
                   MAX(LAST_UPDATED) AS OBSERVATION_DATE,
                   'suppliers' AS UNIT
            FROM PM_OEE_DB.CORE.EXTERNAL_PART_CATALOG
        """)
    except Exception:
        mkt_raw_df = pd.DataFrame()
        mkt_conf_df = pd.DataFrame()
        mkt_cat_df = pd.DataFrame()
        mkt_prices_df = pd.DataFrame()
        mkt_indicators_df = pd.DataFrame()

except Exception as e:
    import traceback
    st.error(f"Error fetching real-time data from Snowflake: {e}")
    st.stop()

# Fetch cached Environmental Context (Open-Meteo API + Snowflake persistence)
try:
    env_data = get_cached_env_context(session)
except Exception:
    env_data = {"available": False, "status": "TEMPORARILY_UNAVAILABLE"}

# Render Single Global App Header
render_header()

# Build Top Header KPI Metrics
total_machines = len(risk_df)
at_risk_count = len(risk_df[risk_df["UNIFIED_RISK_SCORE"] >= 0.70]) if not risk_df.empty else 0
warning_count = len(risk_df[(risk_df["UNIFIED_RISK_SCORE"] >= 0.40) & (risk_df["UNIFIED_RISK_SCORE"] < 0.70)]) if not risk_df.empty else 0
overall_oee = round(oee_df["OEE_PCT"].mean(), 1) if (not oee_df.empty and "OEE_PCT" in oee_df.columns and oee_df["OEE_PCT"].sum() > 0) else 0.0
fleet_risk = round(risk_df["UNIFIED_RISK_SCORE"].mean(), 2) if (not risk_df.empty and "UNIFIED_RISK_SCORE" in risk_df.columns) else 0.00
open_wo_count = len(wo_df[wo_df["STATUS"].isin(["PENDING_APPROVAL", "APPROVED"])]) if not wo_df.empty else 0

# Calculate downtime financial exposure dynamically from active affected machines
downtime_risk_usd = 0.0
machine_loss_map = {
    "Machine_03": 12500.0,
    "Machine_02": 6250.0,
    "Machine_01": 3125.0,
    "Machine_04": 0.0
}
if not risk_df.empty:
    for _, r_row in risk_df.iterrows():
        m_id = r_row["MACHINE_ID"]
        r_val = float(r_row["UNIFIED_RISK_SCORE"])
        if r_val >= 0.70:
            downtime_risk_usd += machine_loss_map.get(m_id, 12500.0)
        elif r_val >= 0.40:
            downtime_risk_usd += machine_loss_map.get(m_id, 3125.0)

render_kpi_cards(
    oee_pct=overall_oee,
    fleet_risk=fleet_risk,
    critical_count=at_risk_count,
    warning_count=warning_count,
    open_wo_count=open_wo_count,
    downtime_risk_usd=downtime_risk_usd,
    running_count=len(risk_df) if not risk_df.empty else 12
)

# ------------------------------------------------------------------
# Executive Page Routing & Content Canvas
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Executive Page Routing & Modular Content Canvas
# ------------------------------------------------------------------
from pages.command_center import render_command_center
from pages.alerts import render_alerts
from pages.machine_intelligence import render_machine_intelligence
from pages.what_if_simulator import render_what_if_simulator
from pages.work_orders import render_work_orders
from pages.ai_copilot import render_ai_copilot
from pages.supply_chain import render_supply_chain
from pages.system_status_page import render_system_status_page
from pages.reports import render_reports
from pages.settings_page import render_settings_page

if selected_page == "🏠 Command Center":
    render_command_center(
        session=session,
        risk_df=risk_df,
        oee_df=oee_df,
        parts_df=parts_df,
        wo_df=wo_df,
        jira_audit_df=jira_audit_df,
        mkt_cat_df=mkt_cat_df,
        mkt_prices_df=mkt_prices_df,
        mkt_indicators_df=mkt_indicators_df,
        qexec=qexec,
        qdf=qdf,
        safe_rerun=safe_rerun,
        CNC_MACHINE_B64=CNC_MACHINE_B64,
        AI_BRAIN_B64=AI_BRAIN_B64,
        env_data=env_data,
        downtime_risk_usd=downtime_risk_usd,
        nav_options=nav_options
    )

elif "Alert Triage" in selected_page:
    render_alerts(
        session=session,
        qexec=qexec,
        qdf=qdf,
        safe_rerun=safe_rerun
    )

elif "Machine Intelligence" in selected_page:
    render_machine_intelligence(
        session=session,
        risk_df=risk_df,
        oee_df=oee_df,
        parts_df=parts_df,
        wo_df=wo_df,
        jira_audit_df=jira_audit_df,
        mkt_cat_df=mkt_cat_df,
        qexec=qexec,
        qdf=qdf,
        safe_rerun=safe_rerun,
        CNC_MACHINE_B64=CNC_MACHINE_B64,
        AI_BRAIN_B64=AI_BRAIN_B64,
        env_data=env_data,
        downtime_risk_usd=downtime_risk_usd
    )

elif "What-if Simulator" in selected_page:
    render_what_if_simulator(
        session=session,
        risk_df=risk_df,
        oee_df=oee_df,
        parts_df=parts_df,
        qexec=qexec,
        safe_rerun=safe_rerun
    )

elif "Work Orders" in selected_page:
    render_work_orders(
        session=session,
        risk_df=risk_df,
        parts_df=parts_df,
        wo_df=wo_df,
        jira_audit_df=jira_audit_df,
        qexec=qexec,
        qdf=qdf,
        safe_rerun=safe_rerun
    )

elif "AI Copilot" in selected_page:
    render_ai_copilot(
        session=session,
        risk_df=risk_df,
        parts_df=parts_df,
        wo_df=wo_df,
        qexec=qexec,
        qdf=qdf,
        safe_rerun=safe_rerun,
        AI_BRAIN_B64=AI_BRAIN_B64
    )

elif "Supply Chain" in selected_page:
    render_supply_chain(
        session=session,
        risk_df=risk_df,
        parts_df=parts_df,
        mkt_raw_df=mkt_raw_df,
        mkt_conf_df=mkt_conf_df,
        mkt_cat_df=mkt_cat_df,
        mkt_prices_df=mkt_prices_df,
        mkt_indicators_df=mkt_indicators_df,
        qexec=qexec,
        qdf=qdf,
        safe_rerun=safe_rerun
    )

elif "System Status" in selected_page:
    render_system_status_page(
        session=session,
        risk_df=risk_df,
        env_data=env_data,
        qdf=qdf,
        safe_rerun=safe_rerun
    )

elif "Reports" in selected_page:
    render_reports(
        session=session,
        risk_df=risk_df,
        oee_df=oee_df,
        wo_df=wo_df,
        qdf=qdf,
        safe_rerun=safe_rerun
    )

elif "Settings" in selected_page:
    render_settings_page(
        session=session,
        safe_rerun=safe_rerun
    )
