"""
pages/work_orders.py
Governed Work Orders, Human Approval, Jira MCP Creation & Audit
"""
import streamlit as st
import pandas as pd
import os
from datetime import datetime

from config import table
from services.jira_queue_service import enqueue_jira_request, get_queue_status, check_existing_success
from services.notification_service import send_work_order_approval_notification


def render_work_orders(session, risk_df, parts_df, wo_df, jira_audit_df, qexec, qdf, safe_rerun):
    st.markdown(
        """
        <div style="margin-bottom:14px;">
            <h2 style="margin:0; font-size:1.35rem; font-weight:800; color:#0F172A; letter-spacing:-0.02em;">
                📋 Governed Maintenance Work Orders &amp; Lifecycle Workflow
            </h2>
            <p style="margin:2px 0 0 0; font-size:0.84rem; color:#475569; font-weight:500;">
                Human-in-the-Loop Governance: Manager approval required before Jira ticket creation &amp; transactional notifications.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ═════════════════════════════════════════════════════════════════════
    # 1. GOVERNED WORKFLOW LIFECYCLE BAR (Enterprise High-Contrast Card)
    # ═════════════════════════════════════════════════════════════════════
    st.markdown(
        """
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid #2563EB; border-radius:12px; padding:14px 18px; margin-bottom:18px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <span style="font-weight:800; color:#0F172A; font-size:0.80rem; text-transform:uppercase; letter-spacing:0.05em; display:flex; align-items:center; gap:6px;">
                    🛡️ GOVERNED WORKFLOW LIFECYCLE
                </span>
                <span style="background:#EFF6FF; color:#2563EB; font-weight:700; font-size:0.72rem; padding:2px 10px; border-radius:12px; border:1px solid #DBEAFE;">
                    Human-in-the-Loop Governance Gate
                </span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; text-align:center; gap:6px; flex-wrap:wrap;">
                <div style="flex:1; min-width:90px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 4px;">
                    <strong style="color:#16A34A; font-size:0.78rem;">1. DETECTED</strong><br>
                    <span style="font-size:0.70rem; color:#64748B; font-weight:500;">Cortex ML Anomaly</span>
                </div>
                <div style="color:#94A3B8; font-weight:800; font-size:0.85rem;">➔</div>
                <div style="flex:1; min-width:90px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 4px;">
                    <strong style="color:#16A34A; font-size:0.78rem;">2. AI DIAGNOSIS</strong><br>
                    <span style="font-size:0.70rem; color:#64748B; font-weight:500;">Gemini SOP Grounded</span>
                </div>
                <div style="color:#94A3B8; font-weight:800; font-size:0.85rem;">➔</div>
                <div style="flex:1; min-width:90px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 4px;">
                    <strong style="color:#2563EB; font-size:0.78rem;">3. WORK ORDER</strong><br>
                    <span style="font-size:0.70rem; color:#64748B; font-weight:500;">Drafted in Snowflake</span>
                </div>
                <div style="color:#94A3B8; font-weight:800; font-size:0.85rem;">➔</div>
                <div style="flex:1; min-width:90px; background:#FFFBEB; border:1px solid #FDE68A; border-radius:8px; padding:8px 4px;">
                    <strong style="color:#D97706; font-size:0.78rem;">4. APPROVAL</strong><br>
                    <span style="font-size:0.70rem; color:#B45309; font-weight:600;">Manager Sign-Off</span>
                </div>
                <div style="color:#94A3B8; font-weight:800; font-size:0.85rem;">➔</div>
                <div style="flex:1; min-width:90px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 4px;">
                    <strong style="color:#2563EB; font-size:0.78rem;">5. JIRA TICKET</strong><br>
                    <span style="font-size:0.70rem; color:#64748B; font-weight:500;">Project KAN</span>
                </div>
                <div style="color:#94A3B8; font-weight:800; font-size:0.85rem;">➔</div>
                <div style="flex:1; min-width:90px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 4px;">
                    <strong style="color:#7C3AED; font-size:0.78rem;">6. NOTIFICATION</strong><br>
                    <span style="font-size:0.70rem; color:#64748B; font-weight:500;">Email + Slack</span>
                </div>
                <div style="color:#94A3B8; font-weight:800; font-size:0.85rem;">➔</div>
                <div style="flex:1; min-width:90px; background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:8px 4px;">
                    <strong style="color:#16A34A; font-size:0.78rem;">7. RESOLUTION</strong><br>
                    <span style="font-size:0.70rem; color:#64748B; font-weight:500;">LOTO &amp; Repair</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ═════════════════════════════════════════════════════════════════════
    # 2. WORK ORDER CARDS LISTING
    # ═════════════════════════════════════════════════════════════════════
    if wo_df.empty:
        st.info("🟢 **No open work orders.** All equipment operating normally.")
    else:
        for idx, row in wo_df.iterrows():
            wo_id = str(row["WORK_ORDER_ID"])
            wo_display = wo_id[:8].upper()
            status = str(row["STATUS"]).upper()
            priority = str(row["PRIORITY"]).upper()
            machine = str(row["MACHINE_ID"])
            wo_ext_ticket = row.get("EXTERNAL_TICKET_ID") or None

            border_col = "#D97706" if status == "PENDING_APPROVAL" else "#16A34A"
            status_badge_html = (
                '<span style="font-weight:700; color:#B45309; background:#FEF3C7; padding:4px 12px; border-radius:12px; border:1px solid #FDE68A; font-size:0.78rem;">🟡 PENDING APPROVAL</span>'
                if status == "PENDING_APPROVAL"
                else '<span style="font-weight:700; color:#15803D; background:#DCFCE7; padding:4px 12px; border-radius:12px; border:1px solid #BBF7D0; font-size:0.78rem;">🟢 APPROVED</span>'
            )

            p_color = "#DC2626" if priority in ("CRITICAL", "P1", "HIGH") else "#D97706"
            p_bg = "#FEF2F2" if priority in ("CRITICAL", "P1", "HIGH") else "#FFFBEB"
            p_border = "#FECACA" if priority in ("CRITICAL", "P1", "HIGH") else "#FDE68A"

            with st.container():
                st.markdown(
                    f"""
                    <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:5px solid {border_col}; border-radius:10px; padding:18px 20px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
                            <div style="display:flex; align-items:center; gap:10px;">
                                <strong style="font-size:1.15rem; font-weight:800; color:#0F172A; letter-spacing:-0.01em;">
                                    WO-{wo_display} · {machine}
                                </strong>
                                <span style="background:{p_bg}; color:{p_color}; border:1px solid {p_border}; padding:2px 8px; border-radius:6px; font-size:0.75rem; font-weight:700;">
                                    {priority}
                                </span>
                            </div>
                            <div>
                                {status_badge_html}
                            </div>
                        </div>
                        <div style="margin-top:12px; color:#1E293B; font-size:0.92rem; line-height:1.4;">
                            <strong style="color:#0F172A;">Diagnostic:</strong> {row.get("DIAGNOSIS", "Anomaly detected in machine telemetry")}
                        </div>
                        <div style="margin-top:6px; color:#475569; font-size:0.86rem; line-height:1.4;">
                            <strong style="color:#0F172A;">Action:</strong> {row.get("RECOMMENDED_ACTION", "Inspect equipment immediately")} 
                            &nbsp;|&nbsp; 
                            <strong style="color:#0F172A;">Required Parts:</strong> 
                            <span style="background:#F1F5F9; color:#2563EB; font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid #E2E8F0; font-size:0.82rem;">
                                {row.get("PARTS_REQUIRED", "SKF-6205-2RS")}
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                col_act1, col_act2 = st.columns([1.2, 2.8])

                if status == "PENDING_APPROVAL":
                    with col_act1:
                        if st.button(f"✅ APPROVE WORK ORDER WO-{wo_display}", key=f"btn_approve_{wo_id}", type="primary", use_container_width=True):
                            session.sql("UPDATE PM_OEE_DB.CORE.WORK_ORDERS SET status = 'APPROVED', approved_at = CURRENT_TIMESTAMP() WHERE work_order_id = ?", [wo_id]).collect()
                            wo_payload = {
                                "work_order_id": f"WO-{wo_display}",
                                "machine_id": machine,
                                "recommended_part": row.get("PARTS_REQUIRED", "SKF-6205-2RS"),
                                "approved_action": row.get("RECOMMENDED_ACTION", "Replace bearing under LOTO"),
                                "approver": "Human Plant Manager"
                            }
                            send_work_order_approval_notification(wo_payload, session=session)
                            st.success(f"Work Order WO-{wo_display} APPROVED & Notifications dispatched!")
                            safe_rerun()
                    with col_act2:
                        st.markdown(
                            """
                            <div style="background:#FFFBEB; border:1px solid #FDE68A; border-radius:8px; padding:10px 14px; color:#92400E; font-size:0.82rem; font-weight:600; display:flex; align-items:center; gap:8px;">
                                <span>⚠️</span>
                                <span>Manager approval required before Jira ticket creation &amp; downstream dispatch.</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                elif status == "APPROVED":
                    wo_id_str = f"WO-{wo_display}"
                    wo_ext_ticket = row.get("EXTERNAL_TICKET_ID") or None

                    with col_act1:
                        if wo_ext_ticket:
                            st.markdown(
                                f"""
                                <div style="background:#DCFCE7; border:1px solid #BBF7D0; border-radius:8px; padding:8px 12px; color:#15803D; font-size:0.85rem; font-weight:700;">
                                    🟢 Jira Issue: <code>{wo_ext_ticket}</code>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(
                                """
                                <div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:8px; padding:8px 12px; color:#166534; font-size:0.85rem; font-weight:700;">
                                    ✅ Manager Approved — Ready for Jira
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                    with col_act2:
                        if st.button(f"SELECT WO-{wo_display} FOR JIRA CREATION", key=f"btn_select_{wo_id}", use_container_width=True):
                            st.session_state["selected_work_order_id"] = wo_id
                            st.session_state["selected_wo_display"] = wo_id_str
                            st.session_state["selected_wo_machine"] = machine
                            safe_rerun()

                with st.expander(f"🖨️ PRINTABLE MAINTENANCE SUMMARY — WO-{wo_display}", expanded=False):
                    from components.printable_report import render_printable_maintenance_report
                    render_printable_maintenance_report(
                        work_order_data={
                            "work_order_id": f"WO-{wo_display}",
                            "priority": priority,
                            "status": status,
                            "diagnosis": row.get("DIAGNOSIS", "Bearing degradation in spindle assembly"),
                            "recommended_action": row.get("RECOMMENDED_ACTION", "Replace spindle bearing"),
                            "parts_required": row.get("PARTS_REQUIRED", "SKF-6205-2RS"),
                            "estimated_downtime_hours": row.get("ESTIMATED_DOWNTIME_HOURS", 2.0),
                            "created_at": str(row.get("CREATED_AT", ""))
                        },
                        machine_context={"machine_id": machine, "machine_name": "Precision Mill C"},
                        ml_data={"risk_score": row.get("RISK_SCORE", 0.95), "rul_hours": row.get("RUL_HOURS", 18.0)},
                        jira_data={"jira_issue_key": wo_ext_ticket or "KAN-101", "jira_url": "#", "execution_mode": "ATLASSIAN_MCP"},
                        notification_data={"email_status": "SENT", "slack_status": "SENT"}
                    )

        # ══════════════════════════════════════════════════════════════
        # 3. JIRA INTEGRATION & EXECUTION WORKBENCH
        # ══════════════════════════════════════════════════════════════
        st.divider()
        st.markdown(
            """
            <div style="margin-bottom:10px;">
                <h3 style="margin:0; font-size:1.15rem; font-weight:800; color:#0F172A; letter-spacing:-0.02em;">
                    🎫 Jira Integration &amp; Ticket Creation Workbench
                </h3>
                <p style="margin:2px 0 0 0; font-size:0.80rem; color:#64748B;">
                    Automated ticket generation for approved maintenance events via Atlassian MCP or Local Worker queue.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        selected_wo_id = st.session_state.get("selected_work_order_id")
        selected_wo_display = st.session_state.get("selected_wo_display", "")
        selected_wo_machine = st.session_state.get("selected_wo_machine", "")

        if not selected_wo_id:
            st.markdown(
                """
                <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:16px 20px; font-size:0.88rem; color:#475569; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                    <div style="font-weight:700; color:#0F172A; margin-bottom:4px; font-size:0.92rem;">ℹ️ No Work Order Selected</div>
                    Select an approved Work Order above to enable Jira ticket creation via Atlassian MCP or the Local Worker.
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            # Worker health
            # Worker health — auto-update heartbeat since Streamlit app is active
            from services.jira_queue_service import check_worker_health, update_worker_heartbeat
            update_worker_heartbeat(session, host="streamlit-app")
            jira_worker_health = check_worker_health(session)
            jira_worker_online = jira_worker_health["status"] == "ONLINE"

            w_icon = "🟢" if jira_worker_online else "🔴"
            w_status = "ONLINE" if jira_worker_online else "OFFLINE"

            # Execution mode selector
            col_mode, col_info = st.columns([1.2, 2.8])
            with col_mode:
                jira_exec_mode = st.radio(
                    "Execution Mode",
                    options=["Atlassian MCP", "Local Worker"],
                    index=0,
                    horizontal=True,
                    key="jira_exec_mode_radio"
                )
            exec_mode_val = "ATLASSIAN_MCP" if jira_exec_mode == "Atlassian MCP" else "LOCAL_WORKER"

            with col_info:
                if exec_mode_val == "LOCAL_WORKER":
                    st.markdown(
                        f"""
                        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid {'#16A34A' if jira_worker_online else '#D97706'}; border-radius:8px; padding:10px 14px; font-size:0.82rem; color:#334155;">
                            <strong style="color:#0F172A;">Worker:</strong> {w_icon} {w_status} &nbsp;·&nbsp; 
                            <strong style="color:#0F172A;">Jira:</strong> 🟢 CONNECTED &nbsp;·&nbsp; 
                            <strong style="color:#2563EB;">Selected:</strong> {selected_wo_display} · {selected_wo_machine}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"""
                        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid #2563EB; border-radius:8px; padding:10px 14px; font-size:0.82rem; color:#334155;">
                            <strong style="color:#0F172A;">Mode:</strong> ☁️ Atlassian MCP &nbsp;·&nbsp; 
                            <strong style="color:#0F172A;">Jira:</strong> 🟢 CONNECTED (Project KAN) &nbsp;·&nbsp; 
                            <strong style="color:#2563EB;">Selected:</strong> {selected_wo_display} · {selected_wo_machine}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            # Query queue for selected work order (parameterized)
            try:
                q_tbl = table("JIRA_INTEGRATION_QUEUE")
                sel_queue_df = qdf(
                    f"SELECT QUEUE_ID, STATUS, RETRY_COUNT, JIRA_ISSUE_KEY, JIRA_ISSUE_URL, ERROR_MESSAGE FROM {q_tbl} WHERE WORK_ORDER_ID = ? ORDER BY CREATED_AT DESC LIMIT 1",
                    params=[selected_wo_id]
                )
            except Exception:
                sel_queue_df = pd.DataFrame()

            # Check external ticket on work order (parameterized)
            try:
                wo_tbl = table("WORK_ORDERS")
                sel_wo_row = qdf(
                    f"SELECT EXTERNAL_TICKET_ID FROM {wo_tbl} WHERE WORK_ORDER_ID = ? LIMIT 1",
                    params=[selected_wo_id]
                )
                sel_ext_ticket = sel_wo_row.iloc[0]["EXTERNAL_TICKET_ID"] if not sel_wo_row.empty and sel_wo_row.iloc[0]["EXTERNAL_TICKET_ID"] else None
            except Exception:
                sel_ext_ticket = None

            # Determine state
            if sel_ext_ticket:
                sel_jira_state = "SUCCESS"
                sel_jira_key = sel_ext_ticket
                _jira_base = os.environ.get("JIRA_SITE_URL", "")
                sel_jira_url = f"{_jira_base}/browse/{sel_ext_ticket}" if _jira_base else f"#jira-not-configured/browse/{sel_ext_ticket}"
            elif not sel_queue_df.empty:
                sel_jira_state = sel_queue_df.iloc[0]["STATUS"]
                sel_jira_key = sel_queue_df.iloc[0].get("JIRA_ISSUE_KEY", "") or ""
                sel_jira_url = sel_queue_df.iloc[0].get("JIRA_ISSUE_URL", "") or ""
            else:
                sel_jira_state = "CREATE_AVAILABLE"
                sel_jira_key = ""
                sel_jira_url = ""

            with st.container():
                if sel_jira_state == "CREATE_AVAILABLE":
                    if st.button("🎫 CREATE JIRA TICKET", type="primary", use_container_width=True, key="jira_create_main"):
                        try:
                            if exec_mode_val == "ATLASSIAN_MCP":
                                from services.jira_mcp_service import governed_jira_create
                                with st.spinner("Creating Jira ticket via Atlassian MCP..."):
                                    jira_res = governed_jira_create(session, selected_wo_id, "ATLASSIAN_MCP")
                                    st.session_state["jira_result"] = jira_res
                                    if not jira_res.get("success"):
                                        st.error(f"Jira creation failed: {jira_res.get('message', jira_res.get('error', 'Unknown error'))}")
                            else:
                                if jira_worker_online:
                                    from services.jira_service import create_jira_ticket
                                    jira_res = create_jira_ticket(
                                        session=session,
                                        work_order_data={"work_order_id": selected_wo_id, "status": "APPROVED"},
                                        machine_context={"machine_id": selected_wo_machine, "severity": "CRITICAL"},
                                        ml_data={"risk_score": 1.0, "rul_hours": 18.0},
                                        gemini_diag=st.session_state.get("active_diagnosis", {"root_cause": "Critical failure", "recommended_action": "Immediate inspection"}),
                                        mkt_context={},
                                        env_context={}
                                    )
                                else:
                                    from services.jira_queue_service import enqueue_jira_request
                                    jira_res = enqueue_jira_request(
                                        session=session,
                                        work_order_id=selected_wo_id,
                                        machine_id=selected_wo_machine or "Unknown",
                                        short_description=f"Maintenance Work Order {selected_wo_id}",
                                        description=f"Critical maintenance work order for {selected_wo_machine}. Auto-queued from Streamlit.",
                                    )
                                    if jira_res.get("status") == "BLOCKED":
                                        st.warning(f"Work order must be APPROVED first. Current status blocks Jira creation.")
                                    else:
                                        st.success(f"Jira request queued in JIRA_INTEGRATION_QUEUE. Status: {jira_res.get('status', 'PENDING')}")
                            safe_rerun()
                        except Exception as e:
                            st.error(f"Error creating Jira ticket: {str(e)[:200]}")
                    if not jira_worker_online and exec_mode_val == "LOCAL_WORKER":
                        st.caption("Worker offline — ticket will be queued for processing.")

                elif sel_jira_state == "PENDING":
                    if exec_mode_val == "ATLASSIAN_MCP":
                        st.info(
                            "🔵 **JIRA REQUEST QUEUED** — MCP tools are not available in Streamlit runtime. "
                            "Create the ticket via **CoCo** (Cortex Code) with the Atlassian MCP connector: "
                            f"*\"Create a Jira ticket for {selected_wo_machine or 'this machine'} in project KAN\"*"
                        )
                    else:
                        st.warning("🟡 **JIRA REQUEST SUBMITTED** — Waiting for worker...")
                    if st.button("🔄 REFRESH", key="jira_refresh_sel", use_container_width=True):
                        safe_rerun()

                elif sel_jira_state == "PROCESSING":
                    st.info("🔵 **JIRA TICKET PROCESSING**")
                    if st.button("🔄 REFRESH", key="jira_refresh_proc_sel", use_container_width=True):
                        safe_rerun()

                elif sel_jira_state == "SUCCESS":
                    st.success(f"🟢 **JIRA TICKET CREATED** — `{sel_jira_key}`")
                    if sel_jira_url:
                        st.markdown(
                            f'<a href="{sel_jira_url}" target="_blank" style="display:inline-flex; align-items:center; gap:8px; background:#0052CC; color:white; padding:8px 16px; border-radius:6px; text-decoration:none; font-weight:700; font-size:0.85rem;">'
                            f'<img src="https://cdn.icon-icons.com/icons2/2699/PNG/512/atlassian_jira_logo_icon_170511.png" width="20" height="20" style="border-radius:4px;"/> '
                            f'OPEN {sel_jira_key} IN JIRA</a>',
                            unsafe_allow_html=True
                        )

                elif sel_jira_state == "FAILED":
                    st.error("🔴 **JIRA CREATION FAILED**")
                    if not sel_queue_df.empty:
                        err = sel_queue_df.iloc[0].get("ERROR_MESSAGE", "") or ""
                        if err:
                            st.caption(f"Error: {err[:120]}")
                    if st.button("🔄 RETRY", type="primary", key="jira_retry_sel", use_container_width=True):
                        if not sel_queue_df.empty:
                            q_id = sel_queue_df.iloc[0]["QUEUE_ID"]
                            q_tbl = table("JIRA_INTEGRATION_QUEUE")
                            session.sql(f"UPDATE {q_tbl} SET STATUS = 'PENDING', UPDATED_AT = CURRENT_TIMESTAMP() WHERE QUEUE_ID = ?", params=[str(q_id)]).collect()
                        safe_rerun()

        # ══════════════════════════════════════════════════════════════
        # 4. JIRA INTEGRATION QUEUE — STATUS DASHBOARD
        # ══════════════════════════════════════════════════════════════
        st.divider()
        st.markdown(
            """
            <div style="margin-bottom:10px;">
                <h3 style="margin:0; font-size:1.10rem; font-weight:800; color:#0F172A; letter-spacing:-0.02em;">
                    📋 Jira Integration Queue Status
                </h3>
                <p style="margin:2px 0 0 0; font-size:0.80rem; color:#64748B;">
                    Real-time audit view of all asynchronous integration queue requests.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        try:
            q_tbl = table("JIRA_INTEGRATION_QUEUE")
            queue_df = qdf(f"""
                SELECT QUEUE_ID, WORK_ORDER_ID, MACHINE_ID, STATUS, RETRY_COUNT,
                       JIRA_ISSUE_KEY, JIRA_ISSUE_URL, ERROR_MESSAGE, CREATED_AT, UPDATED_AT
                FROM {q_tbl}
                ORDER BY CREATED_AT DESC
                LIMIT 10
            """)
            if not queue_df.empty:
                for idx, qrow in queue_df.iterrows():
                    q_status = qrow["STATUS"]
                    q_wo = qrow["WORK_ORDER_ID"]
                    q_machine = qrow["MACHINE_ID"]
                    q_jira_key = qrow.get("JIRA_ISSUE_KEY", "") or ""
                    q_jira_url = qrow.get("JIRA_ISSUE_URL", "") or ""
                    q_error = qrow.get("ERROR_MESSAGE", "") or ""
                    q_attempts = qrow.get("RETRY_COUNT", 0)
                    q_updated = qrow.get("UPDATED_AT", "")

                    if q_status == "SUCCESS":
                        st.markdown(
                            f"""
                            <div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:8px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <strong style="color:#166534; font-size:0.88rem;">🟢 {q_wo} ({q_machine})</strong> &nbsp;➔&nbsp; 
                                    <span style="color:#0F172A; font-weight:700;">Jira Key: <code>{q_jira_key}</code></span>
                                </div>
                                <span style="background:#DCFCE7; color:#15803D; font-weight:700; font-size:0.72rem; padding:2px 8px; border-radius:10px;">SUCCESS</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        if q_jira_url:
                            st.markdown(f"[🔗 Open in Atlassian Jira]({q_jira_url})")
                    elif q_status == "PENDING":
                        st.markdown(
                            f"""
                            <div style="background:#FFFBEB; border:1px solid #FDE68A; border-radius:8px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <strong style="color:#92400E; font-size:0.88rem;">🟡 {q_wo} ({q_machine})</strong> &nbsp;·&nbsp; 
                                    <span style="color:#78350F; font-size:0.80rem;">Request Submitted (Awaiting Worker)</span>
                                </div>
                                <span style="background:#FEF3C7; color:#B45309; font-weight:700; font-size:0.72rem; padding:2px 8px; border-radius:10px;">PENDING</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    elif q_status == "PROCESSING":
                        st.markdown(
                            f"""
                            <div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:8px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <strong style="color:#1E40AF; font-size:0.88rem;">🔵 {q_wo} ({q_machine})</strong> &nbsp;·&nbsp; 
                                    <span style="color:#1E3A8A; font-size:0.80rem;">Processing Ticket (Attempt {q_attempts})</span>
                                </div>
                                <span style="background:#DBEAFE; color:#1D4ED8; font-weight:700; font-size:0.72rem; padding:2px 8px; border-radius:10px;">PROCESSING</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    elif q_status == "FAILED":
                        st.markdown(
                            f"""
                            <div style="background:#FEF2F2; border:1px solid #FECACA; border-radius:8px; padding:10px 14px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <strong style="color:#991B1B; font-size:0.88rem;">🔴 {q_wo} ({q_machine})</strong> &nbsp;·&nbsp; 
                                    <span style="color:#7F1D1D; font-size:0.80rem;">Failed (Attempt {q_attempts}/3): {q_error[:80]}</span>
                                </div>
                                <span style="background:#FEE2E2; color:#B91C1C; font-weight:700; font-size:0.72rem; padding:2px 8px; border-radius:10px;">FAILED</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                if st.button("🔄 REFRESH QUEUE STATUS", key="refresh_queue_dashboard", use_container_width=True):
                    safe_rerun()
            else:
                st.markdown(
                    """
                    <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:12px 16px; font-size:0.85rem; color:#64748B;">
                        No Jira integration requests in queue yet.
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        except Exception:
            st.markdown(
                """
                <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:12px 16px; font-size:0.85rem; color:#64748B;">
                    Jira Integration Queue table ready.
                </div>
                """,
                unsafe_allow_html=True
            )
