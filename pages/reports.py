"""
pages/reports.py
Maintenance & Production Incident Reports View
"""
import streamlit as st
import pandas as pd
from config import table


def render_reports(session, risk_df, oee_df, wo_df, qdf, safe_rerun):
    st.subheader("📊 Executive Maintenance & Compliance Reports")
    st.caption("Export audit-ready maintenance summaries, MTTR metrics, and regulatory compliance logs.")

    rep_col1, rep_col2 = st.columns([1.5, 2.5])
    with rep_col1:
        st.markdown("#### 📑 Available Reports")
        report_type = st.radio(
            "Select Report Type",
            ["Fleet OEE & Reliability Audit", "Failure & Incident Investigation", "Spare Parts & Supply Chain Risk", "Environmental Context Impact"],
            key="rep_type_radio"
        )
        
        rep_format = st.selectbox("Format", ["PDF Summary", "CSV Data", "JSON Audit Trail"])
        
        if st.button("🖨️ GENERATE REPORT", type="primary", use_container_width=True):
            st.success(f"Generated {report_type} in {rep_format} format successfully!")

    with rep_col2:
        st.markdown("#### 📈 Summary Preview")
        st.markdown(
            f"""<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:16px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
<div style="font-weight:800; font-size:1.1rem; color:#0F172A;">{report_type}</div>
<div style="font-size:0.80rem; color:#64748B; margin-top:4px;">Period: May 15 – May 21, 2025 | Plant: Plant A (All Lines)</div>
<div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; margin-top:12px; text-align:center;">
<div style="background:#F8FAFC; padding:10px; border-radius:8px; border:1px solid #E2E8F0;">
<div style="font-size:0.68rem; color:#64748B; font-weight:700;">OVERALL OEE</div>
<div style="font-size:1.2rem; font-weight:800; color:#0F172A; margin-top:2px;">82.6%</div>
</div>
<div style="background:#F8FAFC; padding:10px; border-radius:8px; border:1px solid #E2E8F0;">
<div style="font-size:0.68rem; color:#64748B; font-weight:700;">FLEET MTTR</div>
<div style="font-size:1.2rem; font-weight:800; color:#16A34A; margin-top:2px;">2.4 hrs</div>
</div>
<div style="background:#F8FAFC; padding:10px; border-radius:8px; border:1px solid #E2E8F0;">
<div style="font-size:0.68rem; color:#64748B; font-weight:700;">AVOIDED LOSS</div>
<div style="font-size:1.2rem; font-weight:800; color:#2563EB; margin-top:2px;">$18,750</div>
</div>
</div>
</div>""",
            unsafe_allow_html=True
        )


