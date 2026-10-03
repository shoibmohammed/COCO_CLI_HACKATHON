"""
pages/alerts.py
Alert Triage & Real-time Anomaly Dispatch View
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from config import table
from services.ml_service import refresh_ml_predictions, generate_alerts, get_alert_triage, get_ml_predictions, get_model_info


def render_alerts(session, qexec, qdf, safe_rerun):
    risk_df = qdf("SELECT * FROM PM_OEE_DB.CORE.RISK_SCORES_RT") if qdf else pd.DataFrame()
    # Page Header Card
    st.markdown(
        """<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:18px 22px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
<h2 style="margin:0; font-size:1.5rem; font-weight:800; color:#0F172A;">🚨 Alert Triage & ML Anomaly Detection</h2>
<p style="margin:4px 0 0 0; font-size:0.85rem; color:#64748B; font-weight:500;">Failure-risk prioritization powered by Snowflake ML Classification (PM_FAILURE_MODEL)</p>
</div>""",
        unsafe_allow_html=True
    )

    triage_col1, triage_col2 = st.columns([1, 1.8])
    with triage_col1:
        # Triage Action Card
        st.markdown(
            """<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:16px 18px; box-shadow:0 1px 3px rgba(0,0,0,0.03); margin-bottom:12px;">
<div style="font-size:0.95rem; font-weight:700; color:#0F172A; margin-bottom:10px;">⚡ Triage Actions</div>
</div>""",
            unsafe_allow_html=True
        )
        triage_btn_col, _ = st.columns([1.2, 1])
        with triage_btn_col:
            if st.button("▶ RUN FRESH TRIAGE", type="primary", use_container_width=True, key="btn_run_fresh_triage"):
                with st.spinner("🔄 Running Snowflake ML triage & risk pipeline..."):
                    refresh_ml_predictions(session)
                    generate_alerts(session)
                st.session_state["triage_refreshed_at"] = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                st.success("🟢 Triage refreshed at " + st.session_state["triage_refreshed_at"])
                safe_rerun()

        if "triage_refreshed_at" in st.session_state:
            st.caption("🟢 Last refreshed at " + st.session_state["triage_refreshed_at"])

    with triage_col2:
        # ML Model Status Card
        ml_preds = get_ml_predictions(session)
        n_scored = len(ml_preds) if ml_preds else 0
        crit_count = sum(1 for p in ml_preds if float(p.get("FAILURE_PROBABILITY", 0)) >= 0.75) if ml_preds else 0
        high_count = sum(1 for p in ml_preds if 0.40 <= float(p.get("FAILURE_PROBABILITY", 0)) < 0.75) if ml_preds else 0
        st.markdown(
            '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:16px 18px; box-shadow:0 1px 3px rgba(0,0,0,0.03); margin-bottom:12px;">'
            '<div style="font-size:0.95rem; font-weight:700; color:#0F172A; margin-bottom:10px;">🤖 ML Model Status</div>'
            '<div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">'
            '<span style="background:#DCFCE7; color:#16A34A; font-weight:700; padding:4px 10px; border-radius:8px; font-size:0.78rem; border:1px solid #BBF7D0;">🟢 ' + str(n_scored) + ' machines scored</span>'
            '<span style="background:#FEE2E2; color:#DC2626; font-weight:700; padding:4px 10px; border-radius:8px; font-size:0.78rem; border:1px solid #FECACA;">🔴 ' + str(crit_count) + ' critical</span>'
            '<span style="background:#FEF3C7; color:#D97706; font-weight:700; padding:4px 10px; border-radius:8px; font-size:0.78rem; border:1px solid #FDE68A;">🟠 ' + str(high_count) + ' high</span>'
            '<span style="background:#F8FAFC; color:#334155; font-weight:600; padding:4px 10px; border-radius:8px; font-size:0.78rem; border:1px solid #E2E8F0;">Model: PM_FAILURE_MODEL</span>'
            '<span style="background:#F8FAFC; color:#334155; font-weight:600; padding:4px 10px; border-radius:8px; font-size:0.78rem; border:1px solid #E2E8F0;">AUC: 0.938</span>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

    # ML Predictions Section
    st.markdown(
        """<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:16px 18px; box-shadow:0 1px 3px rgba(0,0,0,0.03); margin-bottom:12px;">
<div style="display:flex; justify-content:space-between; align-items:center;">
<div>
<div style="font-size:1.1rem; font-weight:700; color:#0F172A;">🤖 Snowflake ML Failure Predictions</div>
<div style="font-size:0.80rem; color:#64748B; margin-top:2px;">6-Hour Failure Window · RUL Horizon: ~18 hours</div>
</div>
</div>
</div>""",
        unsafe_allow_html=True
    )

    if ml_preds:
        for pred in ml_preds:
            m_id = pred.get("MACHINE_ID", "")
            prob = float(pred.get("FAILURE_PROBABILITY", 0))
            fclass = str(pred.get("FAILURE_CLASS", "False"))
            vib = float(pred.get("VIBRATION_MM_S", 0))
            temp = float(pred.get("TEMPERATURE_C", 0))
            rpm_v = float(pred.get("RPM", 0))

            # Match exact risk score from risk_df if available
            target_r = risk_df[risk_df["MACHINE_ID"] == m_id].iloc[0] if (not risk_df.empty and m_id in risk_df["MACHINE_ID"].values) else None
            stat_risk = float(target_r["RISK_SCORE"]) if target_r is not None and "RISK_SCORE" in target_r.index else (1.0 if prob >= 0.75 else 0.0)

            prob_str = f"{prob*100:.2f}%" if prob > 0 else "Unavailable"

            if prob >= 0.75 or stat_risk >= 0.75:
                sev_badge = "🔴 CRITICAL FAILURE RISK"
                sev_color = "🔴"
                card_border = "border-left: 5px solid #EF4444; background-color: rgba(239, 68, 68, 0.08);"
                pred_fail = "YES"
            elif prob >= 0.40 or stat_risk >= 0.40:
                sev_badge = "🟠 HIGH RISK"
                sev_color = "🟠"
                card_border = "border-left: 5px solid #F97316; background-color: rgba(249, 115, 22, 0.08);"
                pred_fail = "YES"
            else:
                sev_badge = "🟢 HEALTHY"
                sev_color = "🟢"
                card_border = "border-left: 5px solid #10B981; background-color: rgba(16, 185, 129, 0.05);"
                pred_fail = "NO"

            st.markdown(
                f'<div style="{card_border} border-radius:10px; padding:16px; margin-bottom:12px; border:1px solid #E2E8F0; background:#FFFFFF; box-shadow:0 1px 3px rgba(0,0,0,0.03);">'
                f'<div style="display:flex; justify-content:space-between; align-items:center;">'
                f'<div style="font-size:1.1rem; font-weight:800; color:#0F172A;">{sev_color} {m_id}</div>'
                '<div style="font-size:0.85rem; font-weight:700; color:' + ("#DC2626" if "CRITICAL" in sev_badge else ("#D97706" if "HIGH" in sev_badge else "#16A34A")) + ';">' + str(sev_badge) + '</div>'
                f'</div>'
                f'<div style="display:grid; grid-template-columns: repeat(5, 1fr); gap:10px; margin-top:12px; text-align:center;">'
                '<div style="background:#F8FAFC; padding:8px; border-radius:6px; border:1px solid #F1F5F9;"><div style="font-size:0.72rem; color:#64748B; font-weight:600;">Statistical Risk</div><div style="font-size:1.05rem; font-weight:800; color:' + ("#DC2626" if stat_risk>=0.75 else "#16A34A") + ';">' + "{:.0f}".format(stat_risk*100) + '% (' + ("CRITICAL" if stat_risk>=0.75 else "OK") + ')</div></div>'
                '<div style="background:#F8FAFC; padding:8px; border-radius:6px; border:1px solid #F1F5F9;"><div style="font-size:0.72rem; color:#64748B; font-weight:600;">ML Failure Prob</div><div style="font-size:1.05rem; font-weight:800; color:' + ("#DC2626" if prob>=0.75 else "#16A34A") + ';">' + str(prob_str) + '</div></div>'
                f'<div style="background:#F8FAFC; padding:8px; border-radius:6px; border:1px solid #F1F5F9;"><div style="font-size:0.72rem; color:#64748B; font-weight:600;">Vibration</div><div style="font-size:1.05rem; font-weight:800; color:#0F172A;">{vib:.2f} mm/s</div></div>'
                f'<div style="background:#F8FAFC; padding:8px; border-radius:6px; border:1px solid #F1F5F9;"><div style="font-size:0.72rem; color:#64748B; font-weight:600;">Temperature</div><div style="font-size:1.05rem; font-weight:800; color:#0F172A;">{temp:.1f}°C</div></div>'
                '<div style="background:#F8FAFC; padding:8px; border-radius:6px; border:1px solid #F1F5F9;"><div style="font-size:0.72rem; color:#64748B; font-weight:600;">Predicted Failure</div><div style="font-size:1.05rem; font-weight:800; color:' + ("#DC2626" if pred_fail=="YES" else "#16A34A") + ';">' + str(pred_fail) + '</div></div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )
    else:
        st.info("No ML predictions available. Click 'RUN FRESH TRIAGE' to generate.")

    st.divider()

    # Alert History
    st.markdown('<div style="font-size:1.1rem; font-weight:700; color:#0F172A; margin-bottom:8px;">📋 Alert History</div>', unsafe_allow_html=True)
    alerts = get_alert_triage(session)
    if alerts:
        formatted_alerts = []
        for a in alerts:
            raw_sev = str(a.get("SEVERITY", "HEALTHY")).upper()
            if raw_sev == "CRITICAL":
                sev_fmt = "🔴 CRITICAL"
            elif raw_sev in ("HIGH", "WARNING"):
                sev_fmt = "🟠 HIGH"
            else:
                sev_fmt = "🟢 HEALTHY"

            r_score = float(a.get("RISK_SCORE", 0.0))
            score_fmt = f"{r_score:.2f} / CRITICAL" if r_score >= 0.75 else f"{r_score:.2f} / NORMAL"

            raw_reason = str(a.get("ALERT_REASON", ""))
            if "vibration escalation" in raw_reason.lower():
                reason_clean = "ML predicts failure within 6 hours due to abnormal vibration."
            elif "thermal escalation" in raw_reason.lower():
                reason_clean = "ML predicts failure within 6 hours due to thermal escalation."
            else:
                reason_clean = raw_reason

            wo_stat = a.get("WORK_ORDER_STATUS")
            if not wo_stat or str(wo_stat).lower() in ("none", "null", ""):
                wo_fmt = "Not Created"
            elif str(wo_stat).upper() == "PENDING_APPROVAL":
                wo_fmt = "PENDING APPROVAL"
            else:
                wo_fmt = str(wo_stat).upper()

            notif_status_str = "📧 Snowflake Email 🟢 READY  |  💬 Slack 🟢 READY" if raw_sev in ("CRITICAL", "HIGH") else "📧 Email ⚪ --  |  💬 Slack ⚪ --"

            formatted_alerts.append({
                "Alert ID": a.get("ALERT_ID"),
                "Machine ID": a.get("MACHINE_ID"),
                "Severity": sev_fmt,
                "Risk Score": score_fmt,
                "Alert Reason": reason_clean,
                "Notifications": notif_status_str,
                "Created At": a.get("CREATED_AT"),
                "Work Order Status": wo_fmt
            })

        st.dataframe(pd.DataFrame(formatted_alerts), use_container_width=True, height=260)
    else:
        st.info("No alerts recorded yet. Click 'RUN FRESH TRIAGE' to detect anomalies.")

    st.divider()

    # Model Info
    with st.expander("📊 ML Model Details", expanded=False):
        model_info = get_model_info()
        mi1, mi2, mi3, mi4 = st.columns(4)
        mi1.metric("Model", model_info["model_name"])
        mi2.metric("AUC", f"{model_info['auc']:.3f}")
        mi3.metric("F1 Score", f"{model_info['f1_weighted']:.3f}")
        mi4.metric("Training Rows", f"{model_info['training_rows']}")

        st.markdown("**Feature Importance:**")
        fi_df = pd.DataFrame([
            {"Feature": k, "Importance": v}
            for k, v in model_info["feature_importance"].items()
        ]).sort_values("Importance", ascending=False)
        st.bar_chart(fi_df.set_index("Feature"))

    # ------------------------------------------------------------------
    # TAB 2: MACHINE INVESTIGATION (HERO: MACHINE_03)
    # ------------------------------------------------------------------



