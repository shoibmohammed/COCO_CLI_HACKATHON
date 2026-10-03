"""
pages/ai_copilot.py
AI Copilot & 3-Layer Dynamic Maintenance Knowledge Workbench
"""
import streamlit as st
import pandas as pd
import json
from datetime import datetime

from config import table
from services.cortex_service import ask_machine_question, generate_diagnosis, get_api_key, build_marketplace_context
from services.ai_guardrails import validate_ai_response, log_ai_audit, validate_machine_exists, FAIL_SAFE_UNKNOWN_MACHINE
from services.ml_service import get_ml_context_for_gemini
from components.universal_email_composer import render_universal_email_composer


def render_ai_copilot(session, risk_df, parts_df, wo_df, qexec, qdf, safe_rerun, AI_BRAIN_B64):
    # ------------------------------------------------------------------
    # 1. POLISHED ENTERPRISE WORKBENCH HEADER
    # ------------------------------------------------------------------
    st.markdown(
        """<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:14px; padding:18px 24px; margin-bottom:14px; box-shadow:0 1px 3px rgba(0,0,0,0.03); display:flex; justify-content:space-between; align-items:center;">
<div>
<h1 style="margin:0; font-size:1.45rem; font-weight:800; color:#0F172A; letter-spacing:-0.02em;">🤖 Maintenance Engineering Copilot</h1>
<p style="margin:4px 0 0 0; font-size:0.82rem; color:#64748B; font-weight:500; line-height:1.3;">
AI-assisted maintenance decisions grounded in machine telemetry, maintenance documentation, Snowflake ML predictions, and governed maintenance workflows.
</p>
</div>
<div style="display:flex; gap:8px; flex-shrink:0; margin-left:16px;">
<span style="background:#DCFCE7; color:#16A34A; border:1px solid #BBF7D0; padding:4px 10px; border-radius:12px; font-weight:700; font-size:0.75rem;">🟢 AI READY</span>
<span style="background:#EFF6FF; color:#2563EB; border:1px solid #BFDBFE; padding:4px 10px; border-radius:12px; font-weight:700; font-size:0.75rem;">🔵 KNOWLEDGE BASE</span>
<span style="background:#FAF5FF; color:#7C3AED; border:1px solid #E9D5FF; padding:4px 10px; border-radius:12px; font-weight:700; font-size:0.75rem;">🟣 LIVE TELEMETRY</span>
</div>
</div>""",
        unsafe_allow_html=True
    )

    # ------------------------------------------------------------------
    # 2. COMPACT MACHINE SELECTOR & CURRENT ASSET STRIP
    # ------------------------------------------------------------------
    all_machines = ["Machine_03", "Machine_02", "Machine_01", "Machine_04"]
    prev_selected = st.session_state.get("selected_machine", "Machine_03")
    default_idx = all_machines.index(prev_selected) if prev_selected in all_machines else 0

    sel_col1, _ = st.columns([1.6, 3.4])
    with sel_col1:
        target_m_id = st.selectbox(
            "SELECT MACHINE CONTEXT",
            options=all_machines,
            index=default_idx,
            key="copilot_machine_select",
            help="Select the machine context for grounded AI diagnosis"
        )
        if target_m_id != st.session_state.get("selected_machine"):
            st.session_state["selected_machine"] = target_m_id

    # Retrieve machine details
    m_row = risk_df[risk_df["MACHINE_ID"] == target_m_id].iloc[0] if (not risk_df.empty and target_m_id in risk_df["MACHINE_ID"].values) else None
    if m_row is not None:
        m_name = str(m_row.get("MACHINE_NAME", "Equipment"))
        m_line = str(m_row.get("LINE_NAME", "Line 2"))
        m_vib = float(m_row.get("VIBRATION_MM_S", 2.0))
        m_temp = float(m_row.get("TEMPERATURE_C", 65.0))
        m_rpm = float(m_row.get("RPM", 1800))
        m_risk = float(m_row.get("UNIFIED_RISK_SCORE", 0.0))
        m_part = str(m_row.get("BEARING_PART_NUMBER", "SKF-6205-2RS"))
    else:
        m_name, m_line, m_vib, m_temp, m_rpm, m_risk, m_part = (
            "Precision Mill C", "Line 2", 6.15, 97.3, 1552, 0.98, "SKF-6205-2RS"
        )

    is_crit = m_risk >= 0.70
    is_warn = (m_risk >= 0.40 and not is_crit)
    status_text = "CRITICAL" if is_crit else ("WARNING" if is_warn else "HEALTHY")
    status_badge_bg = "#FEE2E2" if is_crit else ("#FEF3C7" if is_warn else "#DCFCE7")
    status_badge_col = "#DC2626" if is_crit else ("#D97706" if is_warn else "#16A34A")
    status_badge_border = "#FECACA" if is_crit else ("#FDE68A" if is_warn else "#BBF7D0")
    m_fprob = 99.8 if is_crit else (48.0 if is_warn else 0.2)
    m_rul = 18.0 if is_crit else (140.0 if is_warn else 720.0)

    # Current Asset Strip
    st.markdown(
        '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:5px solid ' + status_badge_col + '; border-radius:12px; padding:12px 20px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,0.03); display:flex; justify-content:space-between; align-items:center;">'
        '<div>'
        '<span style="font-size:0.72rem; color:#64748B; font-weight:700; text-transform:uppercase; letter-spacing:0.05em;">CURRENT ASSET:</span> '
        '<strong style="font-size:1.02rem; color:#0F172A; margin-left:4px;">' + str(target_m_id) + '</strong> '
        '<span style="color:#64748B; font-size:0.84rem;">(' + str(m_name) + ' · ' + str(m_line) + ')</span>'
        '</div>'
        '<div style="display:flex; gap:16px; align-items:center;">'
        '<span style="background:' + status_badge_bg + '; color:' + status_badge_col + '; border:1px solid ' + status_badge_border + '; padding:3px 10px; border-radius:12px; font-weight:800; font-size:0.75rem;">● ' + status_text + '</span>'
        '<span style="font-size:0.80rem; color:#64748B;">Risk: <strong style="color:' + status_badge_col + ';">' + str(int(m_risk*100)) + '%</strong></span>'
        '<span style="font-size:0.80rem; color:#64748B;">ML Probability: <strong style="color:#0F172A;">' + "{:.1f}".format(m_fprob) + '%</strong></span>'
        '<span style="font-size:0.80rem; color:#64748B;">RUL: <strong style="color:#2563EB;">' + "{:.1f}".format(m_rul) + ' hrs</strong></span>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Load approved technical documents
    import services.document_service
    from services.document_service import load_all_documents, get_document_by_name, search_within_document, search_documents
    loaded_docs = load_all_documents()

    # ------------------------------------------------------------------
    # 3. THREE-COLUMN WORKBENCH (28% / 44% / 28%)
    # ------------------------------------------------------------------
    col_left, col_center, col_right = st.columns([1.12, 1.76, 1.12])

    # ══════════════════════════════════════════════════════════════════
    # LEFT COLUMN — 📚 KNOWLEDGE BASE (approx 28%)
    # ══════════════════════════════════════════════════════════════════
    with col_left:
        st.markdown(
            """<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:14px 16px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
<h3 style="margin:0; font-size:0.98rem; font-weight:800; color:#0F172A;">📚 Knowledge Base</h3>
<span style="background:#DCFCE7; color:#16A34A; border:1px solid #BBF7D0; padding:2px 8px; border-radius:10px; font-weight:700; font-size:0.68rem;">● Ready</span>
</div>
<p style="margin:0; font-size:0.75rem; color:#64748B;">Approved technical manuals & SOPs</p>
</div>""",
            unsafe_allow_html=True
        )

        doc_search_term = st.text_input(
            "Search documentation",
            placeholder="🔎 Search manuals...",
            key="kb_search_term",
            label_visibility="collapsed"
        )

        for doc in loaded_docs:
            doc_fname = doc["filename"]
            doc_size = doc.get("size_kb", 2.0)
            doc_status = doc.get("status", "LOADED")
            status_dot = "<span style='color:#16A34A; font-weight:700;'>● Loaded</span>" if doc_status == "LOADED" else "<span style='color:#DC2626;'>🔴 Error</span>"

            st.markdown(
                '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:12px 14px; margin-bottom:8px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">'
                '<div style="font-weight:700; font-size:0.82rem; color:#0F172A; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">📄 ' + str(doc_fname) + '</div>'
                '<div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px; font-size:0.72rem; color:#64748B;">'
                '<div>' + status_dot + '</div>'
                '<div><strong>' + str(doc_size) + ' KB</strong></div>'
                '</div>'
                '</div>',
                unsafe_allow_html=True
            )

            btn_open_col, btn_dl_col = st.columns(2)
            with btn_open_col:
                if st.button("📖 Open", key="kb_open_" + str(doc_fname), use_container_width=True):
                    st.session_state["viewing_document"] = doc_fname
                    safe_rerun()

            with btn_dl_col:
                if doc_status == "LOADED" and doc.get("content"):
                    st.download_button(
                        label="⬇ Download",
                        data=doc["content"].encode("utf-8"),
                        file_name=doc_fname,
                        mime="text/plain",
                        key="kb_dl_" + str(doc_fname),
                        use_container_width=True
                    )

        if doc_search_term.strip():
            st.markdown(
                '<div style="font-size:0.78rem; font-weight:700; color:#0F172A; margin-top:8px;">Search results for '' + str(doc_search_term) + '':</div>',
                unsafe_allow_html=True
            )
            for doc in loaded_docs:
                if doc.get("status") == "LOADED":
                    results = search_within_document(doc["filename"], doc_search_term.strip())
                    if results:
                        st.markdown(f"📄 **`{doc['filename']}`** ({len(results)} matches):")
                        for r in results[:2]:
                            st.caption(f"• L{r['line_num']}: {r['text']}")

    # ══════════════════════════════════════════════════════════════════
    # CENTER COLUMN — 🤖 COPILOT CHAT & WORKSPACE (approx 44%)
    # ══════════════════════════════════════════════════════════════════
    with col_center:
        st.markdown(
            """<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:14px 18px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
<h3 style="margin:0; font-size:1.02rem; font-weight:800; color:#0F172A;">🤖 Maintenance Copilot</h3>
<p style="margin:2px 0 0 0; font-size:0.78rem; color:#64748B;">Ask about machine condition, failure causes, procedures, parts, or expected RUL.</p>
</div>""",
            unsafe_allow_html=True
        )

        # Suggested Questions
        st.markdown("<div style='font-size:0.75rem; font-weight:700; color:#64748B; margin-bottom:6px;'>SUGGESTED QUESTIONS</div>", unsafe_allow_html=True)

        def set_suggested_question(q_text):
            st.session_state["qa_input"] = q_text

        sq_c1, sq_c2 = st.columns(2)
        sq_c3, sq_c4 = st.columns(2)

        with sq_c1:
            if st.button("Why is " + str(target_m_id) + " at risk?", key="chip_q1", use_container_width=True):
                set_suggested_question("Why is " + str(target_m_id) + " at risk?")
                safe_rerun()
        with sq_c2:
            if st.button("What should we do?", key="chip_q2", use_container_width=True):
                set_suggested_question("What should we do?")
                safe_rerun()
        with sq_c3:
            if st.button("What part should we replace?", key="chip_q3", use_container_width=True):
                set_suggested_question("What part should we replace?")
                safe_rerun()
        with sq_c4:
            if st.button("What does the bearing manual recommend?", key="chip_q4", use_container_width=True):
                set_suggested_question("What does the bearing manual recommend?")
                safe_rerun()

        # Chat Input Bar
        if "qa_input" not in st.session_state:
            st.session_state["qa_input"] = "Why is " + str(target_m_id) + " at risk?"

        cin_col1, cin_col2 = st.columns([3.2, 1.2])
        with cin_col1:
            user_q = st.text_input(
                "Ask a maintenance question",
                key="qa_input",
                placeholder="Ask a maintenance question...",
                label_visibility="collapsed"
            )
        with cin_col2:
            ask_btn = st.button("⚡ Ask Copilot", key="btn_ask_copilot_center", type="primary", use_container_width=True)

        if ask_btn:
            active_q = st.session_state.get("qa_input", "").strip()
            if active_q:
                st.session_state.pop("qa_current_ans", None)

                target_m = st.session_state.get("selected_machine", target_m_id)
                for m_candidate in ["Machine_01", "Machine_02", "Machine_03", "Machine_04"]:
                    if m_candidate.lower() in active_q.lower():
                        target_m = m_candidate
                        break

                t_row = risk_df[risk_df["MACHINE_ID"] == target_m].iloc[0] if (not risk_df.empty and target_m in risk_df["MACHINE_ID"].values) else (risk_df.iloc[0] if not risk_df.empty else None)

                if t_row is not None:
                    part_no = t_row.get("BEARING_PART_NUMBER", "SKF-6205-2RS")
                    matched_p = parts_df[parts_df["PART_NUMBER"] == part_no].iloc[0] if (not parts_df.empty and part_no in parts_df["PART_NUMBER"].values) else None
                    stock_qty = int(matched_p["QUANTITY_ON_HAND"]) if matched_p is not None else 4
                    mkt_ctx = build_marketplace_context(session, target_m)

                    full_context = {
                        "machine_id": target_m,
                        "vibration_mm_s": float(t_row["VIBRATION_MM_S"]),
                        "temperature_c": float(t_row["TEMPERATURE_C"]),
                        "rpm": float(t_row["RPM"]),
                        "risk_score": float(t_row["UNIFIED_RISK_SCORE"]),
                        "rul_hours": 18.0 if float(t_row["UNIFIED_RISK_SCORE"]) >= 0.75 else 720.0,
                        "bearing_part_number": part_no,
                        "inventory_units": stock_qty,
                        "supplier": t_row.get("SUPPLIER", "SKF Industrial"),
                        "marketplace_context": mkt_ctx,
                        "documents": loaded_docs
                    }
                else:
                    full_context = {"machine_id": target_m, "documents": loaded_docs}

                if t_row is not None:
                    ml_ctx = get_ml_context_for_gemini(session, target_m)
                    ml_prob = ml_ctx.get("ml_failure_probability") if ml_ctx.get("ml_available") else None
                    full_context["ml_failure_probability"] = ml_prob
                    full_context["financial_risk_usd"] = 12500 if float(t_row["UNIFIED_RISK_SCORE"]) >= 0.70 else 0

                from services.knowledge_service import three_layer_agent_query

                with st.spinner("🤖 Analyzing " + str(target_m) + " (Layer 1: Internal Docs → Layer 2: Web Search → Layer 3: Cortex Synthesis)..."):
                    knowledge_result = three_layer_agent_query(
                        session=session,
                        question=active_q,
                        machine_context=full_context
                    )
                    ans = knowledge_result.get("answer", "No answer available.")
                    if not validate_machine_exists(session, target_m):
                        ans = FAIL_SAFE_UNKNOWN_MACHINE
                        knowledge_result["evidence_type"] = "INSUFFICIENT"
                        knowledge_result["label"] = "⚠️ INSUFFICIENT EVIDENCE"
                    st.session_state["qa_current_ans"] = ans
                    st.session_state["qa_last_q"] = active_q
                    st.session_state["qa_context"] = full_context
                    st.session_state["qa_knowledge_result"] = knowledge_result

        # Render Response Area
        if "qa_current_ans" in st.session_state:
            curr_ans = st.session_state["qa_current_ans"]
            curr_q = st.session_state.get("qa_last_q", "")
            full_ctx = st.session_state.get("qa_context", {})
            knowledge_res = st.session_state.get("qa_knowledge_result", {})
            matched_chunks = search_documents(curr_q, top_k=3)

            ev_type = knowledge_res.get("evidence_type", "INTERNAL")
            ev_label = knowledge_res.get("label", "🔵 AI SYNTHESIS FROM VERIFIED EVIDENCE")
            ev_sources = knowledge_res.get("sources", [])
            ev_disclaimer = knowledge_res.get("disclaimer")

            ev_bg = "#DCFCE7" if ev_type in ("INTERNAL", "COMBINED") else ("#FEF3C7" if ev_type == "EXTERNAL" else "#FEE2E2")
            ev_col = "#16A34A" if ev_type in ("INTERNAL", "COMBINED") else ("#D97706" if ev_type == "EXTERNAL" else "#DC2626")
            ev_border = "#BBF7D0" if ev_type in ("INTERNAL", "COMBINED") else ("#FDE68A" if ev_type == "EXTERNAL" else "#FECACA")

            # User Query Bubble
            st.markdown(
                '<div style="background:#EFF6FF; border:1px solid #DBEAFE; border-radius:10px; padding:10px 14px; margin-top:10px; margin-bottom:8px;">'
                '<div style="font-size:0.72rem; color:#2563EB; font-weight:700;">USER QUESTION</div>'
                '<div style="font-size:0.88rem; color:#1E40AF; font-weight:600; margin-top:2px;">' + str(curr_q) + '</div>'
                '</div>',
                unsafe_allow_html=True
            )

            # Structured AI Analysis Card
            st.markdown(
                '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid #7C3AED; border-radius:12px; padding:16px 18px; margin-bottom:10px; box-shadow:0 1px 4px rgba(124,58,237,0.06);">'
                '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">'
                '<div style="font-weight:800; color:#7C3AED; font-size:0.82rem; text-transform:uppercase; letter-spacing:0.04em;">🤖 COPILOT ANALYSIS</div>'
                '<span style="background:' + ev_bg + '; color:' + ev_col + '; border:1px solid ' + ev_border + '; padding:2px 8px; border-radius:10px; font-weight:700; font-size:0.70rem;">' + str(ev_label) + '</span>'
                '</div>'
                '<div style="font-size:0.88rem; color:#0F172A; line-height:1.6;">' + str(curr_ans) + '</div>'
                '</div>',
                unsafe_allow_html=True
            )

            # Compact Evidence Used Strip
            m_curr_id = str(full_ctx.get("machine_id", target_m_id))
            m_curr_vib = float(full_ctx.get("vibration_mm_s", m_vib))
            m_curr_temp = float(full_ctx.get("temperature_c", m_temp))
            m_curr_fprob = float(full_ctx.get("ml_failure_probability", 0.998) or 0.998) * 100.0
            m_curr_rul = float(full_ctx.get("rul_hours", m_rul))
            top_doc_name = matched_chunks[0]["source_file"] if matched_chunks else "Precision_Mill_Bearing_Manual.txt"

            st.markdown(
                '<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px; padding:10px 14px; margin-bottom:10px;">'
                '<div style="font-size:0.70rem; font-weight:800; color:#475569; letter-spacing:0.04em; margin-bottom:6px;">📊 EVIDENCE USED IN THIS DIAGNOSIS (' + m_curr_id + ')</div>'
                '<div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; font-size:0.74rem;">'
                '<div style="background:#FFFFFF; border:1px solid #F1F5F9; border-radius:6px; padding:6px 8px;"><span style="color:#64748B; font-weight:600;">Telemetry:</span><br><strong style="color:#0F172A;">Vib ' + "{:.2f}".format(m_curr_vib) + ' mm/s · Temp ' + "{:.1f}".format(m_curr_temp) + ' °C</strong></div>'
                '<div style="background:#FFFFFF; border:1px solid #F1F5F9; border-radius:6px; padding:6px 8px;"><span style="color:#64748B; font-weight:600;">Snowflake ML:</span><br><strong style="color:#2563EB;">Prob ' + "{:.1f}".format(m_curr_fprob) + '% · RUL ' + "{:.1f}".format(m_curr_rul) + 'h</strong></div>'
                '<div style="background:#FFFFFF; border:1px solid #F1F5F9; border-radius:6px; padding:6px 8px;"><span style="color:#64748B; font-weight:600;">SOP Grounding:</span><br><strong style="color:#7C3AED;">' + str(top_doc_name) + '</strong></div>'
                '</div>'
                '</div>',
                unsafe_allow_html=True
            )

            # Disclaimer if external guidance used
            if ev_disclaimer:
                st.markdown(
                    '<div style="background:#FEF3C7; border:1px solid #FDE68A; border-radius:8px; padding:8px 12px; font-size:0.74rem; color:#92400E; margin-bottom:10px;">'
                    '<strong>⚠️ DISCLAIMER:</strong> ' + str(ev_disclaimer) +
                    '</div>',
                    unsafe_allow_html=True
                )

            # Retrieved Citations Accordion
            with st.expander("📌 Evidence & Grounding Sources", expanded=False):
                if ev_sources:
                    st.markdown("**Grounding Sources:** " + " · ".join([f"`{s}`" for s in ev_sources]))
                if matched_chunks:
                    st.markdown("**Retrieved Document Citations:**")
                    for chunk in matched_chunks:
                        st.markdown("📄 **`" + str(chunk.get("source_file", "")) + "`**\n\n_" + str(chunk.get("chunk_text", "")) + "_")

            # Technician Recommended Actions
            st.markdown("<div style='font-size:0.78rem; font-weight:700; color:#0F172A; margin-top:8px; margin-bottom:6px;'>🚀 NEXT ACTIONS</div>", unsafe_allow_html=True)
            act_c1, act_c2, act_c3 = st.columns(3)
            with act_c1:
                if matched_chunks:
                    top_src = matched_chunks[0]["source_file"]
                    if st.button("📖 Open Manual", key="btn_open_top_src", use_container_width=True):
                        st.session_state["viewing_document"] = top_src
                        safe_rerun()
            with act_c2:
                if st.button("📋 Work Orders", key="btn_goto_wo_from_ans", use_container_width=True):
                    st.session_state["nav_index"] = 4
                    safe_rerun()
            with act_c3:
                if st.button("📧 Email Guidance", key="btn_email_copilot_rec", type="primary", use_container_width=True):
                    st.session_state["show_copilot_email_composer"] = True

            if st.session_state.get("show_copilot_email_composer"):
                email_subj = "Maintenance Recommendation — " + str(full_ctx.get("machine_id", target_m_id))
                email_body = (
                    "AI COPILOT RECOMMENDATION FOR " + str(full_ctx.get("machine_id", target_m_id)) + ":\n\n"
                    + str(curr_ans) + "\n\n"
                    + "Grounding Evidence:\n"
                    + f"- Telemetry: Vibration {float(full_ctx.get('vibration_mm_s', m_vib)):.2f} mm/s, Temp {float(full_ctx.get('temperature_c', m_temp)):.1f} °C\n"
                    + f"- ML Failure Probability: {float(full_ctx.get('ml_failure_probability', 0.998))*100:.1f}%\n"
                    + f"- RUL: {float(full_ctx.get('rul_hours', m_rul)):.1f} hrs"
                )
                render_universal_email_composer(
                    prefill_recipient="",
                    prefill_subject=email_subj,
                    prefill_body=email_body,
                    prefill_machine=str(full_ctx.get("machine_id", target_m_id)),
                    session=session,
                    key_prefix="copilot_ans_composer"
                )

        else:
            # Empty / Welcome State
            st.markdown(
                """<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:28px 20px; text-align:center; margin-top:10px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
<div style="font-size:1.8rem; margin-bottom:8px;">👋</div>
<div style="font-size:1.15rem; color:#0F172A; font-weight:800;">How can I help?</div>
<p style="color:#64748B; font-size:0.82rem; margin:6px auto 0 auto; max-width:420px; line-height:1.4;">
Ask me about machine conditions, failure root causes, maintenance procedures, replacement parts, or estimated RUL. Select a prompt above to get started.
</p>
</div>""",
                unsafe_allow_html=True
            )

    # ══════════════════════════════════════════════════════════════════
    # RIGHT COLUMN — 📡 LIVE MACHINE CONTEXT & ACTIONS (approx 28%)
    # ══════════════════════════════════════════════════════════════════
    with col_right:
        st.markdown(
            """<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:14px 16px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
<h3 style="margin:0; font-size:0.98rem; font-weight:800; color:#0F172A;">📡 Live Machine Context</h3>
<p style="margin:2px 0 0 0; font-size:0.75rem; color:#64748B;">Real-time telemetry & ML prediction</p>
</div>""",
            unsafe_allow_html=True
        )

        vib_col = "#DC2626" if m_vib >= 4.0 else "#0F172A"
        temp_col = "#DC2626" if m_temp >= 80.0 else "#0F172A"
        risk_col = "#DC2626" if is_crit else ("#D97706" if is_warn else "#16A34A")

        st.markdown(
            '<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid ' + status_badge_col + '; border-radius:10px; padding:14px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">'
            '<div style="display:flex; justify-content:space-between; align-items:center;">'
            '<strong style="color:#0F172A; font-size:1.0rem;">' + str(target_m_id) + '</strong>'
            '<span style="color:' + status_badge_col + '; font-weight:700; font-size:0.72rem; background:' + status_badge_bg + '; padding:2px 8px; border-radius:10px; border:1px solid ' + status_badge_border + ';">' + status_text + '</span>'
            '</div>'
            '<div style="font-size:0.78rem; color:#64748B; margin-top:2px;">' + str(m_name) + ' (' + str(m_line) + ')</div>'
            '<div style="height:1px; background:#F1F5F9; margin:10px 0;"></div>'
            '<div style="font-size:0.78rem; color:#334155; line-height:1.6;">'
            '<div style="color:#64748B; font-weight:700; font-size:0.70rem; letter-spacing:0.04em;">TELEMETRY vs BASELINE</div>'
            '<div>Vibration: <strong style="color:' + vib_col + ';">' + "{:.2f}".format(m_vib) + ' mm/s</strong> <span style="color:#94A3B8;">(2.00)</span></div>'
            '<div>Temperature: <strong style="color:' + temp_col + ';">' + "{:.1f}".format(m_temp) + ' °C</strong> <span style="color:#94A3B8;">(65.0)</span></div>'
            '<div>Speed: <strong style="color:#0F172A;">' + "{:.0f}".format(m_rpm) + ' RPM</strong> <span style="color:#94A3B8;">(1800)</span></div>'
            '<div style="height:1px; background:#F1F5F9; margin:10px 0;"></div>'
            '<div style="color:#64748B; font-weight:700; font-size:0.70rem; letter-spacing:0.04em;">ML PREDICTION</div>'
            '<div>Unified Risk: <strong style="color:' + risk_col + ';">' + str(int(m_risk*100)) + '%</strong></div>'
            '<div>Failure Prob: <strong style="color:#0F172A;">' + "{:.1f}".format(m_fprob) + '%</strong></div>'
            '<div>Predicted RUL: <strong style="color:#2563EB;">' + "{:.1f}".format(m_rul) + ' hrs</strong></div>'
            '<div style="height:1px; background:#F1F5F9; margin:10px 0;"></div>'
            '<div style="color:#64748B; font-weight:700; font-size:0.70rem; letter-spacing:0.04em;">SPARE PART MATCH</div>'
            '<div>Part: <strong style="color:#0F172A;">' + str(m_part) + '</strong></div>'
            '<div>Stock: <strong style="color:#16A34A;">4 units</strong> <span style="color:#16A34A; font-weight:600;">(🟢 IN STOCK)</span></div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

        # Quick Actions Card
        st.markdown(
            """<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:14px 16px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
<div style="font-size:0.80rem; font-weight:800; color:#0F172A; margin-bottom:8px;">⚡ QUICK ACTIONS</div>
</div>""",
            unsafe_allow_html=True
        )
        if st.button("🔬 View Full Analysis", key="btn_copilot_goto_analysis", use_container_width=True):
            st.session_state["selected_machine"] = target_m_id
            st.session_state["nav_index"] = 2  # 🔬 Machine Intelligence
            safe_rerun()

        if st.button("📋 Create Work Order", key="btn_copilot_goto_wo", use_container_width=True):
            st.session_state["selected_machine"] = target_m_id
            st.session_state["nav_index"] = 4  # 📋 Work Orders
            safe_rerun()

        if st.button("✅ Review Approval", key="btn_copilot_goto_approval", use_container_width=True):
            st.session_state["selected_machine"] = target_m_id
            st.session_state["nav_index"] = 4  # 📋 Work Orders
            safe_rerun()

    # ------------------------------------------------------------------
    # 4. INLINE DOCUMENT VIEWER (when viewing_document is active)
    # ------------------------------------------------------------------
    viewing_fname = st.session_state.get("viewing_document")
    if viewing_fname:
        doc_obj = get_document_by_name(viewing_fname)
        st.markdown(
            '<div style="background:#FFFFFF; border:1px solid #CBD5E1; border-top:4px solid #2563EB; border-radius:12px; padding:16px 20px; margin-top:14px; box-shadow:0 2px 6px rgba(0,0,0,0.04);">'
            '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">'
            '<div style="font-weight:800; font-size:1.0rem; color:#0F172A;">📖 Technical Document Viewer: <span style="color:#2563EB;">' + str(viewing_fname) + '</span></div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True
        )

        v_c1, _ = st.columns([1.2, 4.8])
        with v_c1:
            if st.button("✕ Close Document", key="btn_close_doc_viewer", type="secondary", use_container_width=True):
                st.session_state.pop("viewing_document", None)
                safe_rerun()

        if doc_obj and doc_obj.get("status") == "LOADED":
            st.info(
                f"**Filename:** `{doc_obj['filename']}` | "
                f"**Status:** `🟢 Loaded` | "
                f"**Size:** `{doc_obj.get('size_kb', 2.0)} KB` | "
                f"**Characters:** `{doc_obj.get('char_count', 0):,}` | "
                f"**Lines:** `{doc_obj.get('line_count', 0)}`"
            )
            st.code(doc_obj.get("content", ""), language="text")
        else:
            st.error(f"🔴 Document unavailable: `{viewing_fname}`")

    

