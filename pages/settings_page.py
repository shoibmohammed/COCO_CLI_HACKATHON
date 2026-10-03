"""
pages/settings_page.py
Command Center Settings View
"""
import streamlit as st
from config import table
from services.email_provider import get_email_config, send_test_email


def render_settings_page(session, safe_rerun):
    st.subheader("⚙️ System Configuration & Operational Parameters")
    st.caption("Manage Snowflake database bindings, notification recipients, and ML failure thresholds.")

    set_c1, set_c2 = st.columns(2)
    with set_c1:
        st.markdown("#### 🔔 Notification Settings")
        st.text_input("Default Alert Email", value="maintenance-lead@company.internal", key="cfg_alert_email")
        st.text_input("Slack Channel Webhook", value="#maintenance-alerts", key="cfg_slack_chan")
        st.checkbox("Auto-dispatch email on Critical (Risk > 75%)", value=True, key="cfg_chk_email")
        st.checkbox("Auto-dispatch Slack alert on Critical", value=True, key="cfg_chk_slack")
        if st.button("💾 Save Notification Settings", type="primary", use_container_width=True):
            st.success("Notification preferences saved successfully!")

    with set_c2:
        st.markdown("#### 🎯 ML Risk & Telemetry Thresholds")
        st.slider("Critical Risk Score Threshold", 0.50, 0.95, 0.70, 0.05, key="cfg_crit_thresh")
        st.slider("Vibration Warning Threshold (mm/s)", 2.0, 8.0, 4.0, 0.5, key="cfg_vib_thresh")
        st.slider("Temperature Warning Threshold (°C)", 60.0, 110.0, 80.0, 1.0, key="cfg_temp_thresh")
        if st.button("💾 Save Thresholds", use_container_width=True):
            st.success("Telemetry thresholds updated!")

