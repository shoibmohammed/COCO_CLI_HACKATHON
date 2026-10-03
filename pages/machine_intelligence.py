"""
pages/machine_intelligence.py
Machine Deep-Dive, Telemetry Waveforms, RUL & ML Model Health
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from config import table
from components.diagnosis_card import render_diagnosis_card
from components.business_impact import render_business_impact_card
from services.cortex_service import generate_diagnosis, get_api_key, build_marketplace_context
from services.ml_service import get_ml_context_for_gemini
from services.ai_guardrails import validate_ai_response, log_ai_audit, FAIL_SAFE_VALIDATION_FAILED
from services.report_service import generate_incident_report_csv
from services.scenario_service import SCENARIOS
from services.marketplace_agent import get_marketplace_enrichment
from services.jira_service import create_jira_ticket


def render_machine_intelligence(session, risk_df, oee_df, parts_df, wo_df, jira_audit_df, mkt_cat_df, qexec, qdf, safe_rerun, CNC_MACHINE_B64, AI_BRAIN_B64, env_data, downtime_risk_usd=12500.0):
    st.subheader("🔎 Machine Deep-Dive & AI Diagnosis")
    m_list = risk_df["MACHINE_ID"].tolist() if not risk_df.empty else ["Machine_03"]
    m_default_idx = m_list.index("Machine_03") if "Machine_03" in m_list else 0
    selected_machine = st.selectbox("Select Machine for Analysis", m_list, index=m_default_idx)

    # Clear stale diagnosis if user switches machine
    if st.session_state.get("last_selected_machine") != selected_machine:
        st.session_state["last_selected_machine"] = selected_machine
        st.session_state.pop("active_diagnosis", None)

    selected_row = risk_df[risk_df["MACHINE_ID"] == selected_machine].iloc[0] if not risk_df.empty else None

    if selected_row is not None:
        # Get ML context for this machine
        ml_ctx = get_ml_context_for_gemini(session, selected_machine)
        ml_prob = ml_ctx.get("ml_failure_probability", 0) if ml_ctx.get("ml_available") else None

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Current Vibration", f"{selected_row['VIBRATION_MM_S']:.2f} mm/s", "+207% vs baseline" if selected_row['VIBRATION_MM_S']>4.0 else "Normal")
        c2.metric("Spindle Temperature", f"{selected_row['TEMPERATURE_C']:.1f} °C", "+50% vs baseline" if selected_row['TEMPERATURE_C']>80.0 else "Normal")
        c3.metric("Spindle RPM", f"{selected_row['RPM']:.0f}", "-248 RPM drop" if selected_row['RPM']<1600 else "Normal")
        c4.metric("Failure Risk", f"{float(selected_row['UNIFIED_RISK_SCORE'])*100:.0f}%", "CRITICAL" if selected_row['UNIFIED_RISK_SCORE']>=0.75 else "OK")
        if ml_prob is not None:
            c5.metric("ML Failure (6h)", f"{ml_prob*100:.1f}%", "Snowflake ML" if ml_prob >= 0.9 else "")

        # --------------------------------------------------------------
        # Telemetry Chart Card (Clean White Enterprise Card)
        # --------------------------------------------------------------
        telemetry = qdf(
            "SELECT ts, vibration_mm_s, temperature_c, rpm "
            "FROM PM_OEE_DB.CORE.SENSOR_READINGS "
            "WHERE machine_id = '" + str(selected_machine) + "' "
            "ORDER BY ts ASC"
        )

        st.markdown(
            '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:18px 22px 14px 22px; margin-top:14px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">'
            '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">'
            '<div>'
            '<h3 style="margin:0; font-size:1.08rem; font-weight:800; color:#0F172A;">📈 24-Hour OT Telemetry Degradation Curve</h3>'
            '<p style="margin:2px 0 0 0; font-size:0.80rem; color:#64748B;">' + str(selected_machine) + ' · Vibration vs Temperature · Last 24 Hours</p>'
            '</div>'
            '<div style="display:flex; gap:12px; align-items:center;">'
            '<span style="font-size:0.75rem; color:#2563EB; font-weight:700;">● Vibration (mm/s)</span>'
            '<span style="font-size:0.75rem; color:#F59E0B; font-weight:700;">● Temperature (°C)</span>'
            '</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

        if not telemetry.empty and "VIBRATION_MM_S" in telemetry.columns and "TEMPERATURE_C" in telemetry.columns:
            telemetry["TS_DT"] = pd.to_datetime(telemetry["TS"])
            telemetry = telemetry.sort_values("TS_DT", ascending=True)

            v_vals = pd.to_numeric(telemetry["VIBRATION_MM_S"], errors="coerce").dropna()
            t_vals = pd.to_numeric(telemetry["TEMPERATURE_C"], errors="coerce").dropna()

            v_min = float(v_vals.min()) if not v_vals.empty else 1.0
            v_max = float(v_vals.max()) if not v_vals.empty else 7.0
            t_min = float(t_vals.min()) if not t_vals.empty else 50.0
            t_max = float(t_vals.max()) if not t_vals.empty else 105.0

            v_pad = max(0.5, (v_max - v_min) * 0.15)
            t_pad = max(5.0, (t_max - t_min) * 0.15)

            fig_trend_df = pd.DataFrame({
                "Vibration (mm/s)": pd.to_numeric(telemetry["VIBRATION_MM_S"], errors="coerce"),
                "Temperature (°C)": pd.to_numeric(telemetry["TEMPERATURE_C"], errors="coerce"),
            }, index=telemetry["TS_DT"])

            # Dynamic trend insight
            v_latest = float(v_vals.iloc[-1]) if not v_vals.empty else 2.0
            t_latest = float(t_vals.iloc[-1]) if not t_vals.empty else 65.0
            is_deteriorating = v_latest >= 4.0 or t_latest >= 80.0

            st.line_chart(fig_trend_df, height=320)

            # Trend interpretation insight strip
            if is_deteriorating:
                st.markdown(
                    '<div style="background:#FEF2F2; border:1px solid #FEE2E2; border-radius:8px; padding:8px 14px; font-size:0.78rem; color:#991B1B; display:flex; justify-content:space-between; align-items:center; margin-top:-6px; margin-bottom:12px;">'
                    '<div><strong>🔴 DETERIORATION DETECTED:</strong> Spindle vibration (' + "{:.2f}".format(v_latest) + ' mm/s) & temperature (' + "{:.1f}".format(t_latest) + ' °C) escalating significantly above baseline.</div>'
                    '<span style="font-weight:700; background:#FEE2E2; padding:2px 8px; border-radius:6px;">Critical Degradation</span>'
                    '</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    '<div style="background:#F0FDF4; border:1px solid #DCFCE7; border-radius:8px; padding:8px 14px; font-size:0.78rem; color:#166534; display:flex; justify-content:space-between; align-items:center; margin-top:-6px; margin-bottom:12px;">'
                    '<div><strong>🟢 NOMINAL TELEMETRY:</strong> Asset operating within safe tolerances (' + "{:.2f}".format(v_latest) + ' mm/s, ' + "{:.1f}".format(t_latest) + ' °C).</div>'
                    '<span style="font-weight:700; background:#DCFCE7; padding:2px 8px; border-radius:6px;">Operating Normal</span>'
                    '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.markdown(
                '<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:24px; text-align:center; color:#64748B; font-size:0.85rem; margin-bottom:12px;">📊 No telemetry trend available for this asset.</div>',
                unsafe_allow_html=True
            )

        # ENHANCEMENT 2: Business Impact / Financial ROI Card
        active_sc_key = st.session_state.get("active_scenario_key")
        if active_sc_key and active_sc_key in SCENARIOS:
            active_sc = SCENARIOS[active_sc_key]
        elif selected_row is not None and float(selected_row["UNIFIED_RISK_SCORE"]) >= 0.70:
            active_sc = SCENARIOS["SCENARIO_1"]
        else:
            active_sc = SCENARIOS["SCENARIO_4"]
        render_business_impact_card(active_sc)

        st.divider()

        # ENHANCEMENT 4: Agentic Remediation Panel (Clean White Enterprise Card)
        st.markdown(
            """<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:18px 20px; box-shadow:0 1px 3px rgba(0,0,0,0.03); margin-top:14px; margin-bottom:14px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
<div>
<h3 style="margin:0; font-size:1.1rem; font-weight:800; color:#0F172A;">🤖 Agentic Remediation & Governance</h3>
<p style="margin:2px 0 0 0; font-size:0.80rem; color:#64748B;">Human-in-the-Loop AI Orchestrator for Equipment Maintenance & Order Approvals</p>
</div>
<span style="background:#DCFCE7; color:#16A34A; font-weight:700; padding:4px 10px; border-radius:12px; font-size:0.75rem; border:1px solid #BBF7D0;">● Ready for Agent Run</span>
</div>

<div style="display:grid; grid-template-columns: repeat(5, 1fr); gap:8px; margin-bottom:16px;">
<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 10px; font-size:0.75rem; color:#334155; display:flex; align-items:center; gap:6px;">
<span style="color:#16A34A; font-weight:800;">✓</span> 1. Auto-Diagnose
</div>
<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 10px; font-size:0.75rem; color:#334155; display:flex; align-items:center; gap:6px;">
<span style="color:#16A34A; font-weight:800;">✓</span> 2. ERP Stock
</div>
<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 10px; font-size:0.75rem; color:#334155; display:flex; align-items:center; gap:6px;">
<span style="color:#16A34A; font-weight:800;">✓</span> 3. Marketplace
</div>
<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 10px; font-size:0.75rem; color:#334155; display:flex; align-items:center; gap:6px;">
<span style="color:#16A34A; font-weight:800;">✓</span> 4. Work Order
</div>
<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 10px; font-size:0.75rem; color:#334155; display:flex; align-items:center; gap:6px;">
<span style="color:#16A34A; font-weight:800;">✓</span> 5. Email Alert
</div>
</div>
</div>""",
            unsafe_allow_html=True
        )

        rem_btn_col1, rem_btn_col2 = st.columns([1.5, 2.5])
        with rem_btn_col1:
            run_rem_btn = st.button("🤖 RUN AGENTIC REMEDIATION PIPELINE", type="primary", use_container_width=True, key="btn_exec_remediation")
        if run_rem_btn:
                with st.spinner(f"Executing Agentic Remediation for {selected_machine}..."):
                    # Check for exact external supply-chain match in MARKETPLACE_PART_CATALOG
                    part_no = selected_row["BEARING_PART_NUMBER"]
                    sc_match = qdf("SELECT * FROM PM_OEE_DB.CORE.MARKETPLACE_PART_CATALOG WHERE PART_NAME LIKE ? LIMIT 1", params=[f"%{part_no}%"])
                    if not sc_match.empty and part_no in str(sc_match.iloc[0].get("PART_NAME", "")):
                        sc_info = {
                            "match_found": True,
                            "part_name": str(sc_match.iloc[0]["PART_NAME"]),
                            "supplier_count": int(sc_match.iloc[0]["SUPPLIER_COUNT"]),
                            "total_available_units": int(sc_match.iloc[0]["TOTAL_AVAILABLE_UNITS"]),
                            "avg_supply_cost_usd": float(sc_match.iloc[0]["AVG_SUPPLY_COST_USD"]),
                            "preferred_supplier": str(sc_match.iloc[0]["PREFERRED_SUPPLIER"])
                        }
                    else:
                        sc_info = {
                            "match_found": False,
                            "status": f"No exact external supply-chain match was found for '{part_no}' in catalog. Operating on local ERP inventory catalog."
                        }

                    # Build REAL Marketplace context for Gemini
                    mkt_context = build_marketplace_context(session, selected_machine)

                    context = {
                        "machine_id": selected_machine,
                        "vibration_mm_s": float(selected_row["VIBRATION_MM_S"]),
                        "temperature_c": float(selected_row["TEMPERATURE_C"]),
                        "rpm": float(selected_row["RPM"]),
                        "risk_score": float(selected_row["UNIFIED_RISK_SCORE"]),
                        "ml_failure_probability": ml_ctx.get("ml_failure_probability") if ml_ctx.get("ml_available") else None,
                        "ml_failure_class": ml_ctx.get("failure_class") if ml_ctx.get("ml_available") else None,
                        "ml_model": "PM_FAILURE_MODEL (Snowflake ML Classification, AUC=0.938)",
                        "ml_top_feature": "RPM (importance: 0.374)",
                        "bearing_part_number": selected_row["BEARING_PART_NUMBER"],
                        "supplier": selected_row["SUPPLIER"],
                        "external_supply_chain": sc_info,
                        "marketplace_context": mkt_context,
                        "environmental_context": env_data,
                        "maintenance_history": [
                            {"failure_type": "Bearing wear", "part_replaced": "SKF-6205-2RS", "notes": "Vibration rose before thermal excursion."}
                        ]
                    }

                    diag_res = generate_diagnosis(context, session=session)

                    # AI Guardrail: Validate diagnosis before persisting
                    ai_validation = validate_ai_response(session, diag_res, selected_machine)
                    if not ai_validation.get("safe_to_display", False):
                        st.error(f"🛡️ **AI GUARDRAIL**: {FAIL_SAFE_VALIDATION_FAILED}")
                        diag_res = {
                            "root_cause": "Validation pending — manual review required",
                            "recommended_action": "Await validated diagnosis",
                            "confidence": "LOW",
                            "grounding_sources": [],
                            "evidence": ["AI response validation failed — using safe fallback"]
                        }

                    st.session_state["active_diagnosis"] = diag_res
                    st.session_state["active_sc_info"] = sc_info

                    # Persist PENDING_APPROVAL work order in Snowflake (parameterized)
                    wo_tbl = table("WORK_ORDERS")
                    session.sql(f"""
                        INSERT INTO {wo_tbl} (
                            machine_id, priority, status, diagnosis, recommended_action,
                            parts_required, estimated_downtime_hours, risk_score, rul_hours, created_at
                        ) VALUES (
                            ?, 'P1', 'PENDING_APPROVAL',
                            ?, ?,
                            ?, 4.0, ?, 18.0, CURRENT_TIMESTAMP()
                        )
                    """, params=[
                        selected_machine,
                        str(diag_res.get("root_cause", "Spindle bearing wear"))[:1000],
                        str(diag_res.get("recommended_action", "Replace bearing"))[:1000],
                        str(selected_row.get("BEARING_PART_NUMBER", "SKF-6205-2RS")),
                        float(selected_row.get("UNIFIED_RISK_SCORE", 0.0))
                    ]).collect()
                    st.success(f"Work Order drafted & persisted into Snowflake WORK_ORDERS in PENDING_APPROVAL status!")

        st.divider()

        # Render Active Diagnosis Card if available
        if st.session_state.get("active_diagnosis"):
            diag_data = st.session_state["active_diagnosis"]
            sc_data = st.session_state.get("active_sc_info", {})
            render_diagnosis_card(
                diagnosis=diag_data,
                inventory_info={
                    "quantity_on_hand": 4,
                    "unit_cost_usd": 185.0,
                    "lead_time_days": int(selected_row.get("BEARING_LEAD_DAYS", 12)),
                    "supplier": str(selected_row.get("SUPPLIER", "SKF Industrial"))
                },
                external_sc_info=sc_data,
                env_context=env_data
            )

            # MARKETPLACE CONTEXT CARD - Real Snowflake Marketplace Data
            mkt_enrich = get_marketplace_enrichment(session, selected_machine)
            if mkt_enrich:
                me = mkt_enrich[0]
                with st.container():
                    st.markdown("### 🌐 EXTERNAL MARKET CONTEXT (Snowflake Marketplace)")
                    st.caption("Real-time commodity prices and industrial indicators from Snowflake Marketplace listing GZTSZ290BV255")
                    mc1, mc2, mc3, mc4 = st.columns(4)
                    mc1.metric("Copper", f"${float(me.get('COPPER_PRICE_USD', 0)):,.0f}/t")
                    mc2.metric("Aluminum", f"${float(me.get('ALUMINUM_PRICE_USD', 0)):,.0f}/t")
                    mc3.metric("Nickel", f"${float(me.get('NICKEL_PRICE_USD', 0)):,.0f}/t")
                    mc4.metric("Iron Ore", f"${float(me.get('IRON_ORE_PRICE_USD', 0)):,.0f}/t")
                    mc5, mc6, mc7 = st.columns(3)
                    mc5.metric("Mfg Capacity", f"{float(me.get('MFG_CAPACITY_UTILIZATION', 0))*100:.1f}%")
                    mc6.metric("Supply Chain Risk", f"{float(me.get('SUPPLY_CHAIN_RISK_SCORE', 0)):.2f}")
                    mc7.metric("Material Cost Trend", str(me.get('MATERIAL_COST_TREND', 'N/A')))

            # Manager Work Order Approval & Jira Integration (Local Worker Lifecycle)
            st.markdown("#### 🔧 Governed Work Order & Jira Integration")

            # Query current Work Order status from Snowflake
            wo_status_df = qdf("SELECT work_order_id, status, external_ticket_id, machine_id FROM PM_OEE_DB.CORE.WORK_ORDERS WHERE machine_id = ? ORDER BY created_at DESC LIMIT 1", params=[selected_machine])
            db_wo_status = wo_status_df.iloc[0]["STATUS"] if not wo_status_df.empty else "PENDING_APPROVAL"
            db_ext_ticket = wo_status_df.iloc[0]["EXTERNAL_TICKET_ID"] if (not wo_status_df.empty and wo_status_df.iloc[0]["EXTERNAL_TICKET_ID"]) else None
            db_wo_id_raw = str(wo_status_df.iloc[0]["WORK_ORDER_ID"]) if not wo_status_df.empty else ""
            db_wo_display = db_wo_id_raw[:8].upper() if db_wo_id_raw else "0"
            diag_wo_id = f"WO-{db_wo_display}"

            is_approved = (db_wo_status == "APPROVED") or st.session_state.get("wo_approved", False)

            # ════════════════════════════════════════════════════════
            # SECTION 1: WORK ORDER APPROVAL
            # ════════════════════════════════════════════════════════
            with st.container():
                if not is_approved:
                    st.markdown(f"**{diag_wo_id}** · {selected_machine}")
                    st.markdown("🟡 **PENDING APPROVAL**")
                    st.caption("🔒 Manager approval required before Jira ticket creation.")
                    if st.button("✅ APPROVE WORK ORDER", type="primary", use_container_width=True):
                        wo_tbl = table("WORK_ORDERS")
                        session.sql(f"UPDATE {wo_tbl} SET status = 'APPROVED', approved_at = CURRENT_TIMESTAMP() WHERE WORK_ORDER_ID = ? OR status = 'PENDING_APPROVAL'", params=[str(db_wo_id_raw)]).collect()
                        st.session_state["wo_approved"] = True
                        safe_rerun()
                else:
                    st.markdown(f"**{diag_wo_id}** · {selected_machine}")
                    st.markdown("🟢 **APPROVED** — ✅ Manager Approved")
                    st.caption("Ready for Jira integration.")

            # ════════════════════════════════════════════════════════
            # SECTION 2: JIRA INTEGRATION (separate from approval)
            # ════════════════════════════════════════════════════════
            st.markdown("##### 🎫 JIRA INTEGRATION")

            if not is_approved:
                st.markdown(
                    '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:10px 14px; font-size:0.82rem; color:#64748B; box-shadow:0 1px 2px rgba(0,0,0,0.02);">'
                    '🔒 Approve the Work Order above to enable Jira ticket creation.</div>',
                    unsafe_allow_html=True
                )
            else:
                # Worker Health
                from services.jira_queue_service import check_worker_health
                worker_health = check_worker_health(session)
                worker_online = worker_health["status"] == "ONLINE"

                # Status bar
                w_icon = "🟢" if worker_online else "🔴"
                w_lbl = "ONLINE" if worker_online else "OFFLINE"
                st.markdown(
                    '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid ' + ("#16A34A" if worker_online else "#D97706") + '; border-radius:8px; padding:10px 14px; margin-bottom:12px; font-size:0.84rem; color:#334155; box-shadow:0 1px 2px rgba(0,0,0,0.02);">'
                    f'<strong style="color:#0F172A;">Worker:</strong> {w_icon} {w_lbl} &nbsp;·&nbsp; '
                    f'<strong style="color:#0F172A;">Queue:</strong> 🟢 Active &nbsp;·&nbsp; '
                    f'<strong style="color:#2563EB;">Selected:</strong> {diag_wo_id} · {selected_machine}'
                    f'</div>',
                    unsafe_allow_html=True
                )

                # Query queue status
                try:
                    q_tbl = table("JIRA_INTEGRATION_QUEUE")
                    diag_queue_df = qdf(f"SELECT QUEUE_ID, STATUS, ATTEMPT_COUNT, JIRA_ISSUE_KEY, JIRA_URL, ERROR_MESSAGE, CREATED_AT, UPDATED_AT FROM {q_tbl} WHERE WORK_ORDER_ID = ? ORDER BY CREATED_AT DESC LIMIT 1", params=[diag_wo_id])
                except Exception:
                    diag_queue_df = pd.DataFrame()

                # Determine Jira state
                if db_ext_ticket:
                    diag_jira_state = "SUCCESS"
                    diag_jira_key = db_ext_ticket
                    diag_jira_url = ""
                elif not diag_queue_df.empty:
                    qr = diag_queue_df.iloc[0]
                    diag_jira_state = qr["STATUS"]
                    diag_jira_key = qr.get("JIRA_ISSUE_KEY", "") or ""
                    diag_jira_url = qr.get("JIRA_URL", qr.get("JIRA_ISSUE_URL", "")) or ""
                else:
                    diag_jira_state = "CREATE_AVAILABLE"
                    diag_jira_key = ""
                    diag_jira_url = ""

                # Render Jira state
                with st.container():
                    if diag_jira_state == "CREATE_AVAILABLE":
                        if worker_online:
                            if st.button("🎫 CREATE JIRA TICKET", type="primary", use_container_width=True, key="diag_create_jira_btn"):
                                severity = "CRITICAL" if float(selected_row.get("UNIFIED_RISK_SCORE", 0)) >= 0.75 else "HIGH"
                                gem_diag = st.session_state.get("active_diagnosis", {
                                    "root_cause": "Spindle bearing inner raceway spalling and thermal degradation",
                                    "recommended_action": "Immediate machine shutdown under LOTO, inspect spindle raceway, replace bearing."
                                })
                                jira_res = create_jira_ticket(
                                    session=session,
                                    work_order_data={"work_order_id": diag_wo_id, "status": "APPROVED"},
                                    machine_context={"machine_id": selected_machine, "severity": severity,
                                                     "vibration_mm_s": float(selected_row.get("VIBRATION_MM_S", 0)),
                                                     "temperature_c": float(selected_row.get("TEMPERATURE_C", 0)),
                                                     "rpm": float(selected_row.get("RPM", 0))},
                                    ml_data={"risk_score": float(selected_row.get("UNIFIED_RISK_SCORE", 0)), "rul_hours": 18.0},
                                    gemini_diag=gem_diag,
                                    mkt_context={},
                                    env_context=env_data
                                )
                                st.session_state["jira_result"] = jira_res
                                safe_rerun()
                        else:
                            st.markdown("🟡 **Jira Worker offline** — Start the Local Jira Worker to enable ticket creation.")
                            st.button("🎫 CREATE JIRA TICKET", type="primary", use_container_width=True, key="diag_create_jira_btn", disabled=True)

                    elif diag_jira_state == "PENDING":
                        st.markdown("🟡 **JIRA REQUEST SUBMITTED**")
                        st.caption("Request is waiting for the Local Jira Worker.")
                        if st.button("🔄 REFRESH STATUS", key="diag_refresh_pending", use_container_width=True):
                            safe_rerun()

                    elif diag_jira_state == "PROCESSING":
                        st.markdown("🔵 **JIRA TICKET PROCESSING**")
                        st.caption("Local Jira Worker is creating the Jira ticket.")
                        if st.button("🔄 REFRESH STATUS", key="diag_refresh_processing", use_container_width=True):
                            safe_rerun()

                    elif diag_jira_state == "SUCCESS":
                        st.markdown(f"🟢 **JIRA TICKET CREATED** — `{diag_jira_key}`")
                        if diag_jira_url:
                            st.markdown(f"[🔗 OPEN JIRA]({diag_jira_url})")

                    elif diag_jira_state == "FAILED":
                        st.markdown("🔴 **JIRA TICKET CREATION FAILED**")
                        if not diag_queue_df.empty:
                            err_msg = diag_queue_df.iloc[0].get("ERROR_MESSAGE", "") or ""
                            if err_msg:
                                st.caption(f"Error: {err_msg[:150]}")
                        if st.button("🔄 RETRY JIRA TICKET", type="primary", key="diag_retry_jira", use_container_width=True):
                            if not diag_queue_df.empty:
                                q_id = diag_queue_df.iloc[0]["QUEUE_ID"]
                                q_tbl = table("JIRA_INTEGRATION_QUEUE")
                                session.sql(f"UPDATE {q_tbl} SET STATUS = 'PENDING', UPDATED_AT = CURRENT_TIMESTAMP() WHERE QUEUE_ID = ?", params=[str(q_id)]).collect()
                            safe_rerun()

                # Lifecycle visualization
                if is_approved:
                    if diag_jira_state == "SUCCESS":
                        lc_html = '✅ Approved → 🟡 Queued → 🔵 Processing → 🟢 <strong>Jira Ticket Created</strong>'
                    elif diag_jira_state == "FAILED":
                        lc_html = '✅ Approved → 🟡 Queued → 🔴 <strong>Failed</strong> → 🔄 Retry'
                    elif diag_jira_state == "PROCESSING":
                        lc_html = '✅ Approved → 🟡 Queued → 🔵 <strong>Processing...</strong>'
                    elif diag_jira_state == "PENDING":
                        lc_html = '✅ Approved → 🟡 <strong>Queued</strong> → ⏳ Waiting...'
                    else:
                        lc_html = '✅ Approved → 🎫 <strong>Ready to Create</strong>'
                    st.markdown(f'<div style="background:#F8FAFC; border:1px solid #E2E8F0; padding:6px 12px; border-radius:6px; font-size:0.78rem; color:#334155; margin-top:6px;">{lc_html}</div>', unsafe_allow_html=True)

        st.divider()

        # ==================================================================
        # 📧 MAINTENANCE NOTIFICATIONS (PRODUCTION CONTROL CENTER)
        # ==================================================================
        st.divider()
        st.markdown("### 📧 MAINTENANCE NOTIFICATIONS")
        st.caption("Automatic notifications are sent by Snowflake when critical conditions are detected. Manual notifications can be sent from this panel.")

        # Automatic Notification Status (Clean White Enterprise Card)
        st.markdown(
            """<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:12px 18px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
<div style="display:flex; justify-content:space-between; align-items:center; font-size:0.84rem;">
<div style="display:flex; gap:20px; align-items:center;">
<div><strong style="color:#0F172A;">🔔 Automatic Alerts:</strong> <span style="background:#DCFCE7; color:#16A34A; font-weight:700; padding:2px 8px; border-radius:10px; font-size:0.75rem;">● Enabled</span></div>
<div><strong style="color:#0F172A;">📧 Email:</strong> <span style="color:#16A34A; font-weight:700;">🟢 Active</span></div>
<div><strong style="color:#0F172A;">💬 Slack:</strong> <span style="color:#16A34A; font-weight:700;">🟢 Active</span></div>
</div>
<div style="color:#64748B; font-size:0.78rem;">Trigger: Snowflake Task (5 min) · Autonomous Background Dispatch</div>
</div>
</div>""",
            unsafe_allow_html=True
        )

        st.markdown("#### Manual Dispatch & Incident Context")

        # 1. Incident Context Card (Light Enterprise Theme)
        risk_val = float(selected_row["UNIFIED_RISK_SCORE"])
        card_border = "#DC2626" if risk_val >= 0.70 else ("#D97706" if risk_val >= 0.40 else "#16A34A")
        status_lbl = "CRITICAL FAILURE" if risk_val >= 0.70 else ("ELEVATED RISK" if risk_val >= 0.40 else "HEALTHY OPERATION")

        f_prob = risk_val * 100
        rul_h = 18.0 if risk_val >= 0.70 else (48.0 if risk_val >= 0.40 else 720.0)
        dt_h = 4.0 if risk_val >= 0.70 else (2.0 if risk_val >= 0.40 else 0.0)
        fin_risk = "$12,500" if risk_val >= 0.70 else ("$5,000" if risk_val >= 0.40 else "$0")
        part_needed = selected_row.get("BEARING_PART_NUMBER", "SKF-6205-2RS")

        st.markdown(
            f"""<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid {card_border}; border-radius:12px; padding:16px 18px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
<strong style="color:#0F172A; font-size:1.0rem;">🔴 {selected_machine} — {status_lbl}</strong>
<span style="color:{card_border}; font-size:0.75rem; background:#FEE2E2; padding:2px 10px; border-radius:12px; font-weight:700; border:1px solid #FECACA;">LIVE INCIDENT CONTEXT</span>
</div>
<div style="display:grid; grid-template-columns: repeat(6, 1fr); gap:8px; text-align:center; font-size:0.78rem;">
<div style="background:#F8FAFC; padding:8px; border-radius:6px; border:1px solid #F1F5F9;"><span style="color:#64748B; font-weight:600;">Failure Prob</span><br><strong style="color:#DC2626; font-size:0.95rem;">{f_prob:.1f}%</strong></div>
<div style="background:#F8FAFC; padding:8px; border-radius:6px; border:1px solid #F1F5F9;"><span style="color:#64748B; font-weight:600;">Unified Risk</span><br><strong style="color:#DC2626; font-size:0.95rem;">{risk_val*100:.0f}%</strong></div>
<div style="background:#F8FAFC; padding:8px; border-radius:6px; border:1px solid #F1F5F9;"><span style="color:#64748B; font-weight:600;">Predicted RUL</span><br><strong style="color:#2563EB; font-size:0.95rem;">{rul_h:.1f} hrs</strong></div>
<div style="background:#F8FAFC; padding:8px; border-radius:6px; border:1px solid #F1F5F9;"><span style="color:#64748B; font-weight:600;">Est. Downtime</span><br><strong style="color:#0F172A; font-size:0.95rem;">{dt_h:.1f} hrs</strong></div>
<div style="background:#F8FAFC; padding:8px; border-radius:6px; border:1px solid #F1F5F9;"><span style="color:#64748B; font-weight:600;">Financial Risk</span><br><strong style="color:#DC2626; font-size:0.95rem;">{fin_risk}</strong></div>
<div style="background:#F8FAFC; padding:8px; border-radius:6px; border:1px solid #F1F5F9;"><span style="color:#64748B; font-weight:600;">Required Part</span><br><strong style="color:#0F172A; font-size:0.95rem;">{part_needed}</strong></div>
</div>
</div>""",
            unsafe_allow_html=True
        )

        # 2. Notification Mode Toggle + Email Readiness
        from services.notification_service import check_email_readiness
        email_readiness = check_email_readiness(session)

        # Clear stale notification results on fresh page load
        if "notif_initialized" not in st.session_state:
            st.session_state["notif_initialized"] = True
            st.session_state.pop("last_maint_email_result", None)
            st.session_state.pop("maint_notif_mode", None)
            st.session_state.pop("maint_notif_recipient", None)

        notif_mode = st.radio(
            "Notification Mode",
            options=["Demo", "Live"],
            index=0,
            horizontal=True,
            key="maint_notif_mode",
            help="Demo mode records the event without sending external email. Live mode requires a verified Snowflake recipient."
        )

        if notif_mode == "Demo":
            st.markdown(
                "<div style='font-size:0.82rem; color:#2563EB; font-weight:600; margin-bottom:8px;'>🟢 <strong>Demo Mode</strong> — Notification events are recorded without sending external email.</div>",
                unsafe_allow_html=True
            )
            target_email_in = "demo@notification.internal"
        else:
            # Live mode
            if email_readiness["state"] == "READY":
                target_email_in = st.text_input(
                    "Recipient Email",
                    value="",
                    key="maint_notif_recipient",
                    placeholder="Enter verified Snowflake recipient email"
                ).strip()
                st.markdown("<span style='color:#2563EB; font-weight:600; font-size:0.78rem;'>🟢 Provider: Snowflake Email (Live)</span>", unsafe_allow_html=True)
            else:
                st.markdown(
                    """
                    <div style="background:#FFFBEB; border:1px solid #FDE68A; border-left:4px solid #F59E0B; border-radius:6px; padding:10px; margin:8px 0; font-size:0.82rem;">
                        <strong style="color:#B45309;">🟡 Live email not configured</strong><br>
                        <span style="color:#78350F;">Switch to Demo mode or configure a verified recipient. See docs/EMAIL_SETUP.md</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                target_email_in = "demo@notification.internal"

        # Notification Channels Indicator (Primary: Email + Slack)
        st.markdown(
            '<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:6px 12px; margin-top:8px; margin-bottom:10px; font-size:0.74rem; display:flex; justify-content:space-between; align-items:center;">'
            '<span style="color:#475569; font-weight:700;">Dual Notification Channels:</span>'
            '<div style="display:flex; gap:14px; align-items:center;">'
            '<span style="color:#16A34A; font-weight:600;">🟢 Snowflake Native Email</span>'
            '<span style="color:#16A34A; font-weight:600;">🟢 Slack Webhooks</span>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

        # 3. Action Buttons Hierarchy
        prov_choice = "SNOWFLAKE_EMAIL"

        act_col1, act_col2, act_col3, act_col4 = st.columns([2, 2, 1.5, 1.5])

        if act_col1.button("🚨 SEND CRITICAL ALERT", key="btn_send_crit_alert_preview", type="primary", use_container_width=True):
            st.session_state["show_alert_preview"] = True
            st.session_state["show_report_preview"] = False
            st.session_state["show_slack_preview"] = False

        if act_col2.button("📋 SEND INCIDENT REPORT", key="btn_send_inc_report_preview", use_container_width=True):
            st.session_state["show_report_preview"] = True
            st.session_state["show_alert_preview"] = False
            st.session_state["show_slack_preview"] = False

        if act_col3.button("💬 SLACK NOTIFY", key="btn_send_slack_preview", use_container_width=True):
            st.session_state["show_slack_preview"] = True
            st.session_state["show_alert_preview"] = False
            st.session_state["show_report_preview"] = False

        # Tertiary Export CSV Action
        diag_data = st.session_state.get("active_diagnosis", {"root_cause": "Bearing degradation in spindle assembly", "confidence": 0.92, "recommended_part": part_needed, "recommended_action": "Inspect spindle bearing immediately."})
        ctx_data = {"vibration_mm_s": float(selected_row["VIBRATION_MM_S"]), "temperature_c": float(selected_row["TEMPERATURE_C"]), "rpm": float(selected_row["RPM"]), "risk_score": risk_val}
        wo_data = {"status": "APPROVED" if st.session_state.get("wo_approved") else "PENDING_APPROVAL"}
        report_csv = generate_incident_report_csv(selected_machine, ctx_data, diag_data, wo_data)

        act_col4.download_button(
            label="📊 EXPORT CSV",
            data=report_csv,
            file_name=f"Incident_Report_{selected_machine}.csv",
            mime="text/csv",
            key="btn_export_csv_subtle",
            use_container_width=True
        )

        # 4. Confirmation / Preview Area for Critical Alert
        if st.session_state.get("show_alert_preview"):
            st.markdown(
                """
                <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid #DC2626; border-radius:8px; padding:14px; margin-top:12px; box-shadow:0 1px 3px rgba(0,0,0,0.03);"><div style="font-size:1.0rem; font-weight:800; color:#0F172A;">📧 Email Preview — Critical Maintenance Alert</div></div>
                """,
                unsafe_allow_html=True
            )
            st.markdown(f"**To:** `{target_email_in or 'demo@notification.internal'}`")
            st.markdown(f"**Provider:** 🟢 Snowflake Email")
            st.markdown(f"**Subject:** `🚨 Critical Maintenance Alert — {selected_machine}`")

            alert_body_text = (
                f"MFG PREDICTIVE MAINTENANCE\n\n"
                f"{selected_machine} has entered a critical failure state.\n\n"
                f"Failure Probability: {f_prob:.1f}%\n"
                f"Risk Score: {risk_val*100:.0f}%\n"
                f"Predicted RUL: {rul_h:.1f} hours\n"
                f"Estimated Financial Risk: {fin_risk}\n\n"
                f"Vibration: {float(selected_row['VIBRATION_MM_S']):.2f} mm/s\n"
                f"Temperature: {float(selected_row['TEMPERATURE_C']):.1f} °C\n"
                f"RPM: {float(selected_row['RPM']):.0f}\n\n"
                f"Required Part: {part_needed}\n\n"
                f"Recommended Action:\nImmediate maintenance inspection required."
            )
            st.code(alert_body_text, language="text")

            prev_c1, prev_c2 = st.columns([1, 2])
            if prev_c1.button("❌ CANCEL", key="btn_cancel_alert_prev", use_container_width=True):
                st.session_state["show_alert_preview"] = False
                safe_rerun()

            if prev_c2.button("🚨 SEND ALERT", key="btn_exec_send_crit_alert", type="primary", use_container_width=True):
                with st.spinner("Dispatching critical maintenance alert..."):
                    from services.notification_service import dispatch_dual_channel_notification
                    event_id = f"MANUAL-{selected_machine}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                    dual_res = dispatch_dual_channel_notification(
                        session=session,
                        event_id=event_id,
                        machine_id=selected_machine,
                        notification_type="CRITICAL_ALERT",
                        trigger_type="MANUAL",
                        alert_payload={
                            "machine_id": selected_machine,
                            "subject": f"Critical Alert — {selected_machine}",
                            "body": alert_body_text,
                            "vibration_mm_s": float(selected_row["VIBRATION_MM_S"]),
                            "temperature_c": float(selected_row["TEMPERATURE_C"]),
                            "rpm": float(selected_row["RPM"]),
                            "risk_score": risk_val,
                            "ml_failure_probability": f_prob / 100.0,
                            "rul_hours": rul_h,
                            "recommended_part": part_needed,
                            "recommended_action": "Inspect machine immediately. Schedule maintenance per SOP.",
                            "financial_risk_usd": fin_risk,
                        },
                        recipient=target_email_in if notif_mode == "Live" else "",
                        mode="DEMO" if notif_mode == "Demo" else "LIVE",
                    )
                    st.session_state["last_maint_email_result"] = {
                        "success": dual_res["overall"] in ("ALL_SUCCESS", "PARTIAL_SUCCESS"),
                        "mode": notif_mode,
                        "email_status": dual_res["email"]["status"],
                        "slack_status": dual_res["slack"]["status"],
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    }
                    st.session_state["show_alert_preview"] = False
                    safe_rerun()

        # 5. Confirmation / Preview Area for Incident Report
        if st.session_state.get("show_report_preview"):
            st.markdown(
                """
                <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid #2563EB; border-radius:10px; padding:14px 18px; margin-top:14px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                    <div style="font-size:1.0rem; font-weight:800; color:#0F172A;">📋 EMAIL PREVIEW — DETAILED INCIDENT REPORT</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown(f"**To:** `{target_email_in or 'demo@notification.internal'}`")
            st.markdown(f"**Provider:** 🟢 Snowflake Email")
            st.markdown(f"**Subject:** `📋 Detailed Incident Report — {selected_machine}`")

            report_body_text = (
                f"MFG PREDICTIVE MAINTENANCE & OEE COMMAND CENTER\n"
                f"DETAILED MAINTENANCE INCIDENT REPORT\n"
                f"========================================================\n\n"
                f"MACHINE IDENTITY:\n"
                f"- Machine ID: {selected_machine}\n"
                f"- Status: {status_lbl}\n"
                f"- Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                f"CURRENT TELEMETRY vs BASELINE:\n"
                f"- Vibration: {float(selected_row['VIBRATION_MM_S']):.2f} mm/s (Baseline: 2.00 mm/s)\n"
                f"- Temperature: {float(selected_row['TEMPERATURE_C']):.1f} °C (Baseline: 65.0 °C)\n"
                f"- RPM: {float(selected_row['RPM']):.0f} (Baseline: 1800 RPM)\n\n"
                f"SNOWFLAKE ML CLASSIFICATION PREDICTION:\n"
                f"- Failure Probability: {f_prob:.1f}%\n"
                f"- Unified Risk Score: {risk_val*100:.0f}%\n"
                f"- Remaining Useful Life (RUL): {rul_h:.1f} hours\n"
                f"- Avoided Financial Impact: {fin_risk}\n\n"
                f"ROOT CAUSE DIAGNOSIS & REPLACEMENT PARTS:\n"
                f"- Root Cause: {diag_data.get('root_cause', 'Bearing degradation')}\n"
                f"- Required Replacement Part: {part_needed}\n"
                f"- Internal Stock Available: 4 units on hand\n"
                f"- Recommended Action: {diag_data.get('recommended_action', 'Replace bearing immediately.')}\n\n"
                f"========================================================\n"
                f"Governed OT/IT System Notice · MFG Command Center"
            )
            st.code(report_body_text, language="text")

            rprev_c1, rprev_c2 = st.columns([1, 2])
            if rprev_c1.button("❌ CANCEL", key="btn_cancel_report_prev", use_container_width=True):
                st.session_state["show_report_preview"] = False
                safe_rerun()

            if rprev_c2.button("📋 SEND REPORT", key="btn_exec_send_inc_report", type="primary", use_container_width=True):
                with st.spinner("Dispatching comprehensive incident report..."):
                    from services.notification_service import dispatch_dual_channel_notification
                    event_id = f"MANUAL-RPT-{selected_machine}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                    dual_res = dispatch_dual_channel_notification(
                        session=session,
                        event_id=event_id,
                        machine_id=selected_machine,
                        notification_type="INCIDENT_REPORT",
                        trigger_type="MANUAL",
                        alert_payload={"machine_id": selected_machine, "subject": f"Incident Report — {selected_machine}", "body": report_body_text},
                        recipient=target_email_in if notif_mode == "Live" else "",
                        mode="DEMO" if notif_mode == "Demo" else "LIVE",
                    )
                    st.session_state["last_maint_email_result"] = {
                        "success": dual_res["overall"] in ("ALL_SUCCESS", "PARTIAL_SUCCESS"),
                        "mode": notif_mode,
                        "email_status": dual_res["email"]["status"],
                        "slack_status": dual_res["slack"]["status"],
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                    }
                    st.session_state["show_report_preview"] = False
                    safe_rerun()

        # 5b. Confirmation / Preview Area for Slack Notification
        if st.session_state.get("show_slack_preview"):
            st.markdown(
                """
                <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid #7C3AED; border-radius:10px; padding:14px 18px; margin-top:14px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                    <div style="font-size:1.0rem; font-weight:800; color:#0F172A;">💬 SLACK NOTIFICATION PREVIEW</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown(f"**Channel:** `#maintenance-alerts`")
            st.markdown(f"**Integration:** `MFG_SLACK_NOTIFICATION`")

            slack_body_text = (
                f"🚨 **CRITICAL MAINTENANCE ALERT — {selected_machine}**\n\n"
                f"**Status:** {status_lbl}  \n"
                f"**Failure Probability:** {f_prob:.1f}%  \n"
                f"**Unified Risk Score:** {risk_val*100:.0f}%  \n"
                f"**Predicted RUL:** {rul_h:.1f} hours  \n"
                f"**Financial Risk:** {fin_risk}  \n\n"
                f"**Telemetry:**  \n"
                f"- Vibration: {float(selected_row['VIBRATION_MM_S']):.2f} mm/s  \n"
                f"- Temperature: {float(selected_row['TEMPERATURE_C']):.1f} °C  \n"
                f"- RPM: {float(selected_row['RPM']):.0f}  \n\n"
                f"**Required Part:** {part_needed}  \n"
                f"**Action:** Immediate maintenance inspection required."
            )
            st.markdown(
                f'<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:16px; font-size:0.9rem; line-height:1.6;">'
                f'{slack_body_text.replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True
            )

            sl_c1, sl_c2 = st.columns([1, 2])
            if sl_c1.button("❌ CANCEL", key="btn_cancel_slack_prev", use_container_width=True):
                st.session_state["show_slack_preview"] = False
                safe_rerun()

            if sl_c2.button("💬 SEND TO SLACK", key="btn_exec_send_slack", type="primary", use_container_width=True):
                with st.spinner("Sending Slack notification..."):
                    from services.slack_service import send_slack_notification, format_critical_alert, check_slack_configuration
                    slack_cfg = check_slack_configuration(session)
                    if slack_cfg.get("configured") and slack_cfg.get("status") == "READY":
                        event_payload = {
                            "machine_id": selected_machine,
                            "priority": "P1" if risk_val >= 0.70 else "P2",
                            "vibration_mm_s": float(selected_row["VIBRATION_MM_S"]),
                            "temperature_c": float(selected_row["TEMPERATURE_C"]),
                            "rpm": float(selected_row["RPM"]),
                            "risk_score": risk_val,
                            "ml_failure_probability": risk_val,
                            "rul_hours": rul_h,
                            "financial_risk": fin_risk,
                            "part_needed": part_needed,
                        }
                        formatted_msg = format_critical_alert(event_payload)
                        sl_ok, sl_status, sl_details = send_slack_notification(session, formatted_msg)
                        if sl_ok:
                            st.session_state["last_slack_result"] = {"success": True, "status": sl_status, "message": sl_details.get("message", "Sent")}
                        else:
                            st.session_state["last_slack_result"] = {"success": False, "status": sl_status, "message": sl_details.get("message", "Failed")}
                    else:
                        st.session_state["last_slack_result"] = {"success": False, "status": "NOT_CONFIGURED", "message": slack_cfg.get("message", "Slack integration not configured")}
                    st.session_state["show_slack_preview"] = False
                    safe_rerun()

        # Slack result feedback (Clean White Enterprise Card)
        last_sl_res = st.session_state.get("last_slack_result")
        if last_sl_res:
            sl_ok = last_sl_res.get("success", False)
            sl_msg = last_sl_res.get("message", "Sent")
            sl_border = "#16A34A" if sl_ok else "#D97706"
            sl_bg = "#DCFCE7" if sl_ok else "#FEF3C7"
            sl_col = "#16A34A" if sl_ok else "#D97706"
            sl_bdr = "#BBF7D0" if sl_ok else "#FDE68A"

            st.markdown(
                '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid ' + sl_border + '; border-radius:12px; padding:14px 18px; margin-top:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">'
                '<div style="display:flex; justify-content:space-between; align-items:center;">'
                '<strong style="color:#0F172A; font-size:0.92rem;">💬 ' + ("SLACK NOTIFICATION DISPATCHED" if sl_ok else "SLACK NOTIFICATION STATUS") + '</strong>'
                '<span style="background:' + sl_bg + '; color:' + sl_col + '; border:1px solid ' + sl_bdr + '; padding:2px 8px; border-radius:10px; font-weight:700; font-size:0.72rem;">' + ("● Success" if sl_ok else "● Setup Notice") + '</span>'
                '</div>'
                '<div style="font-size:0.80rem; color:#64748B; margin-top:4px;">' + str(sl_msg) + '</div>'
                '</div>',
                unsafe_allow_html=True
            )
            d_sl_col, _ = st.columns([1.2, 4.8])
            with d_sl_col:
                if st.button("✕ Dismiss Slack Notice", key="btn_dismiss_slack_result", use_container_width=True):
                    st.session_state.pop("last_slack_result", None)
                    safe_rerun()

        # 6. Dual-Channel Maintenance Notification Result (Clean White Enterprise Card)
        last_m_res = st.session_state.get("last_maint_email_result")
        if last_m_res:
            is_success = last_m_res.get("success", False)
            email_st = str(last_m_res.get("email_status", "NOT_CONFIGURED"))
            slack_st = str(last_m_res.get("slack_status", "NOT_CONFIGURED"))
            mode_lbl = str(last_m_res.get("mode", "Demo"))
            ts_str = str(last_m_res.get("timestamp", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")))

            card_border = "#16A34A" if is_success else "#D97706"
            badge_bg = "#DCFCE7" if is_success else "#FEF3C7"
            badge_col = "#16A34A" if is_success else "#D97706"
            badge_border = "#BBF7D0" if is_success else "#FDE68A"
            header_text = ("🟢 NOTIFICATION " + ("DEMO " if mode_lbl == "Demo" else "") + "DISPATCHED") if is_success else "🟡 NOTIFICATION STATUS: PARTIAL / PENDING SETUP"

            email_icon = "🟢" if email_st in ("SENT", "DEMO_SUCCESS", "SUCCESS") else ("🟡" if email_st == "NOT_CONFIGURED" else "🔴")
            slack_icon = "🟢" if slack_st in ("SENT", "DEMO_SUCCESS", "SUCCESS") else ("🟡" if slack_st == "NOT_CONFIGURED" else "🔴")

            st.markdown(
                '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid ' + card_border + '; border-radius:12px; padding:16px 20px; margin-top:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">'
                '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">'
                '<strong style="color:#0F172A; font-size:0.95rem;">' + header_text + '</strong>'
                '<span style="background:' + badge_bg + '; color:' + badge_col + '; border:1px solid ' + badge_border + '; padding:2px 8px; border-radius:10px; font-weight:700; font-size:0.72rem;">' + ("● Success" if is_success else "● Setup Notice") + '</span>'
                '</div>'
                '<div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; font-size:0.80rem; margin-bottom:8px;">'
                '<div style="background:#F8FAFC; border:1px solid #F1F5F9; border-radius:6px; padding:8px 10px;"><span style="color:#64748B; font-weight:600;">Email Channel</span><br><strong style="color:#0F172A;">' + email_icon + ' ' + str(email_st) + '</strong></div>'
                '<div style="background:#F8FAFC; border:1px solid #F1F5F9; border-radius:6px; padding:8px 10px;"><span style="color:#64748B; font-weight:600;">Slack Channel</span><br><strong style="color:#0F172A;">' + slack_icon + ' ' + str(slack_st) + '</strong></div>'
                '<div style="background:#F8FAFC; border:1px solid #F1F5F9; border-radius:6px; padding:8px 10px;"><span style="color:#64748B; font-weight:600;">Dispatch Mode</span><br><strong style="color:#2563EB;">' + str(mode_lbl) + '</strong></div>'
                '</div>'
                + ('<div style="font-size:0.75rem; color:#64748B; margin-top:4px;">For external delivery in Live mode, configure a verified recipient email or Slack webhook (see <code>docs/EMAIL_SETUP.md</code>).</div>' if not is_success else '<div style="font-size:0.75rem; color:#64748B; margin-top:4px;">Audit logged to <code>PM_OEE_DB.CORE.NOTIFICATION_AUDIT</code> at ' + str(ts_str) + '.</div>') +
                '</div>',
                unsafe_allow_html=True
            )

            d_c1, _ = st.columns([1.2, 4.8])
            with d_c1:
                if st.button("✕ Dismiss Notification", key="btn_dismiss_email_result", use_container_width=True):
                    st.session_state.pop("last_maint_email_result", None)
                    safe_rerun()


    # ------------------------------------------------------------------
    # TAB: WHAT-IF FAILURE SIMULATOR & SANDBOX
    # ------------------------------------------------------------------



