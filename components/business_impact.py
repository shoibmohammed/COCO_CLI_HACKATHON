"""
components/business_impact.py
Business Impact & Financial ROI UI Component using 100% native Streamlit calls.
"""

import streamlit as st
from typing import Dict, Any

def render_business_impact_card(scenario_data: Dict[str, Any]):
    potential_loss = int(scenario_data.get("potential_loss", 12500))
    est_downtime = float(scenario_data.get("estimated_downtime", 4.0) or 4.0)
    hourly_cost = int(scenario_data.get("hourly_downtime_cost", 3125) or (potential_loss / est_downtime if est_downtime > 0 else 0))
    rul_hours = float(scenario_data.get("rul_hours", 18.0) or 18.0)
    risk_level = scenario_data.get("risk_level", "CRITICAL")

    if risk_level in ("CRITICAL", "HIGH"):
        intervention = "IMMEDIATE (NOW)"
        inter_color = "red"
    elif risk_level == "MEDIUM":
        intervention = "NEXT SCHEDULED WINDOW"
        inter_color = "orange"
    else:
        intervention = "CONTINUE MONITORING"
        inter_color = "green"

    with st.container():
        c_h1, c_h2 = st.columns([3, 1])
        with c_h1:
            st.markdown("### 💰 BUSINESS IMPACT & FINANCIAL ROI")
            st.caption("Quantified Avoidable Downtime Loss & Production Risk ($ USD)")
        with c_h2:
            st.metric("Risk Level", risk_level)

        st.divider()

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Financial Risk Avoided", f"${potential_loss:,} USD")
        b2.metric("Hourly Downtime Cost", f"${hourly_cost:,} / hr")
        b3.metric("Predicted RUL", f"{rul_hours:.1f} Hours")
        b4.metric("Estimated Downtime", f"{est_downtime:.1f} Hours")

        st.divider()

        if inter_color == "red":
            st.error(f"🚨 **Recommended Intervention:** {intervention} — Immediate maintenance required to prevent ${potential_loss:,} loss.")
        elif inter_color == "orange":
            st.warning(f"🟡 **Recommended Intervention:** {intervention} — Plan repair within {rul_hours:.0f} hours.")
        else:
            st.success(f"🟢 **Recommended Intervention:** {intervention} — All telemetry nominal.")
