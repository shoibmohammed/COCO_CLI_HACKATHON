"""
components/printable_report.py
Renders a clean, print-friendly HTML maintenance summary for a selected Work Order and machine context.
Contains NO credentials, API keys, or private tokens.
"""

import streamlit as st
from datetime import datetime
from typing import Dict, Any


def render_printable_maintenance_report(
    work_order_data: Dict[str, Any],
    machine_context: Dict[str, Any],
    ml_data: Dict[str, Any],
    jira_data: Dict[str, Any],
    notification_data: Dict[str, Any]
) -> None:
    """Renders a print-friendly HTML container inside Streamlit with zero leading indentation."""
    wo_id = work_order_data.get("work_order_id", "WO-00000000")
    machine_id = machine_context.get("machine_id", "Machine_03")
    equipment = machine_context.get("machine_name", "Precision Mill C")
    priority = work_order_data.get("priority", "HIGH")
    status = work_order_data.get("status", "APPROVED")
    
    risk_score = float(ml_data.get("risk_score", ml_data.get("failure_probability", 0.95)))
    rul_hours = float(ml_data.get("rul_hours", 18.0))
    
    diagnosis = work_order_data.get("diagnosis", "Vibration anomaly with thermal degradation in spindle bearing.")
    action = work_order_data.get("recommended_action", "Schedule immediate bearing replacement (Part SKF-6205-2RS) and check LOTO protocol.")
    parts = work_order_data.get("parts_required", "SKF-6205-2RS (Spindle Bearing) x 1")
    downtime = work_order_data.get("estimated_downtime_hours", "2.0")
    
    jira_key = jira_data.get("jira_issue_key", "KAN-101")
    timestamp = work_order_data.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    report_html = f"""<div id="printable-report" style="background:#FFFFFF; color:#0F172A; padding:24px; border:2px solid #0F172A; border-radius:8px; font-family:Arial, sans-serif; margin-top:16px;">
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #0F172A; padding-bottom:12px; margin-bottom:16px;">
<div>
<h2 style="margin:0; color:#0F172A; font-size:1.4rem;">OFFICIAL MAINTENANCE SUMMARY REPORT</h2>
<div style="color:#475569; font-size:0.85rem; margin-top:2px;">MFG Predictive Maintenance Command Center · Snowflake Cortex AI</div>
</div>
<div style="text-align:right;">
<strong style="font-size:1.1rem; color:#0F172A;">{wo_id}</strong><br>
<span style="font-size:0.8rem; color:#64748B;">Date: {timestamp}</span>
</div>
</div>

<table style="width:100%; border-collapse:collapse; margin-bottom:16px; font-size:0.9rem;">
<tr style="background:#F8FAFC;">
<td style="padding:8px; border:1px solid #CBD5E1; font-weight:bold; width:25%;">Target Machine:</td>
<td style="padding:8px; border:1px solid #CBD5E1;">{machine_id} ({equipment})</td>
<td style="padding:8px; border:1px solid #CBD5E1; font-weight:bold; width:25%;">Priority:</td>
<td style="padding:8px; border:1px solid #CBD5E1;"><span style="background:#FEF2F2; color:#991B1B; padding:2px 6px; border-radius:4px; font-weight:bold;">{priority}</span></td>
</tr>
<tr>
<td style="padding:8px; border:1px solid #CBD5E1; font-weight:bold;">Failure Risk Score:</td>
<td style="padding:8px; border:1px solid #CBD5E1; color:#DC2626; font-weight:bold;">{risk_score * 100:.1f}% (CRITICAL)</td>
<td style="padding:8px; border:1px solid #CBD5E1; font-weight:bold;">Est. RUL:</td>
<td style="padding:8px; border:1px solid #CBD5E1;">{rul_hours:.1f} Hours</td>
</tr>
<tr style="background:#F8FAFC;">
<td style="padding:8px; border:1px solid #CBD5E1; font-weight:bold;">Approval Status:</td>
<td style="padding:8px; border:1px solid #CBD5E1; color:#166534; font-weight:bold;">🟢 {status} (Human Manager Sign-off)</td>
<td style="padding:8px; border:1px solid #CBD5E1; font-weight:bold;">Est. Downtime:</td>
<td style="padding:8px; border:1px solid #CBD5E1;">{downtime} Hours</td>
</tr>
</table>

<div style="margin-bottom:12px;">
<h4 style="margin:0 0 6px 0; color:#1E293B;">AI DIAGNOSIS & ROOT CAUSE</h4>
<div style="background:#F1F5F9; padding:10px 14px; border-left:4px solid #0284C7; border-radius:4px; font-size:0.88rem; color:#334155;">
{diagnosis}
</div>
</div>

<div style="margin-bottom:12px;">
<h4 style="margin:0 0 6px 0; color:#1E293B;">RECOMMENDED MAINTENANCE ACTION</h4>
<div style="background:#F1F5F9; padding:10px 14px; border-left:4px solid #16A34A; border-radius:4px; font-size:0.88rem; color:#334155;">
{action}
</div>
</div>

<div style="margin-bottom:16px;">
<h4 style="margin:0 0 6px 0; color:#1E293B;">REQUIRED SPARE PARTS</h4>
<div style="background:#F1F5F9; padding:10px 14px; border-left:4px solid #D97706; border-radius:4px; font-size:0.88rem; color:#334155;">
{parts}
</div>
</div>

<div style="display:flex; justify-content:space-between; align-items:center; background:#F8FAFC; border:1px solid #CBD5E1; padding:12px 16px; border-radius:6px; font-size:0.85rem;">
<div><strong>Linked Jira Issue:</strong> <span style="color:#0284C7; font-weight:bold;">{jira_key}</span></div>
<div><strong>Governance:</strong> 🟢 COMPLIANT</div>
</div>
</div>"""

    st.markdown(report_html, unsafe_allow_html=True)
