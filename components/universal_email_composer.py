"""
components/universal_email_composer.py
Reusable Universal Email Composer UI Component for MFG Predictive Maintenance.
Renders interactive recipient input, real-time provider detection, provider override selector,
email preview, optional file attachments, and audit trail feedback.
"""

import os
import streamlit as st

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


from typing import Optional, Dict, Any
from services.universal_email_service import (
    validate_email_address,
    detect_email_provider,
    send_universal_email
)
from services.document_service import load_all_documents


def render_universal_email_composer(
    prefill_recipient: str = "",
    prefill_subject: str = "🚨 CRITICAL MAINTENANCE ALERT — Machine_03",
    prefill_body: str = "",
    prefill_machine: str = "Machine_03",
    prefill_work_order: Optional[str] = None,
    session=None,
    key_prefix: str = "composer"
) -> Optional[Dict[str, Any]]:
    """
    Renders the Universal Email Composer box.
    Returns result dictionary if email was sent during this interaction.
    """
    st.markdown(
        """
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid #2563EB; border-radius:10px; padding:16px 20px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
            <div style="font-size:1.1rem; font-weight:800; color:#0F172A; margin-bottom:4px;">📧 Send Maintenance Email</div>
            <div style="font-size:0.82rem; color:#64748B;">Universal Multi-Provider Dispatch Engine (Auto Provider Detection & Custom Domains)</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 1. Recipient Input
    recipient_in = st.text_input(
        "Recipient Email Address",
        value=prefill_recipient,
        placeholder="e.g. verified-user@company.com",
        key=f"{key_prefix}_rec_input"
    ).strip()

    # 2. Live Provider Detection Badge
    if recipient_in:
        is_valid = validate_email_address(recipient_in)
        if not is_valid:
            st.markdown("<span style='color:#EF4444; font-weight:700; font-size:0.85rem;'>🔴 INVALID EMAIL ADDRESS</span>", unsafe_allow_html=True)
            detected_code, detected_label = "NONE", "🔴 Invalid Email"
        else:
            detected_code, detected_label = detect_email_provider(recipient_in)
            st.markdown(f"<span style='color:#38BDF8; font-size:0.85rem;'>Provider detected: <strong>{detected_label}</strong></span>", unsafe_allow_html=True)
    else:
        detected_code, detected_label = "NONE", ""

    st.write("")

    # 3. Delivery Provider Selector
    prov_choice = st.radio(
        "Delivery Provider Mode",
        options=["AUTO", "GMAIL", "OUTLOOK"],
        format_func=lambda x: "Auto (Detected)" if x == "AUTO" else ("Gmail (smtp.gmail.com)" if x == "GMAIL" else "Microsoft Outlook (smtp.office365.com)"),
        horizontal=True,
        key=f"{key_prefix}_prov_radio"
    )

    # 4. Subject & Body Text Area
    subject_in = st.text_input("Subject", value=prefill_subject, key=f"{key_prefix}_sub_input")

    default_body = prefill_body or (
        f"MFG PREDICTIVE MAINTENANCE\n\n"
        f"Machine: {prefill_machine}\n"
        f"Severity: 🔴 CRITICAL\n"
        f"Failure Probability: 99.8%\n"
        f"Unified Risk: 100%\n"
        f"Vibration: 6.15 mm/s (Baseline: 2.00 mm/s)\n"
        f"Temperature: 97.3 °C (Baseline: 65.0 °C)\n"
        f"RPM: 1552 (Baseline: 1800)\n"
        f"Estimated RUL: 18 hours\n"
        f"Required Part: SKF-6205-2RS (4 units in stock)\n\n"
        f"Recommended Action:\n"
        f"Inspect spindle bearing immediately and follow approved LOTO procedure.\n"
    )

    body_in = st.text_area("Message Body", value=default_body, height=140, key=f"{key_prefix}_body_input")

    # 5. Optional File Attachment Selector
    st.markdown("##### 📎 Attachment (Optional)")
    att_source = st.radio("Attachment Source", ["None", "Technical Documentation Manuals", "Upload Custom File"], horizontal=True, key=f"{key_prefix}_att_source")

    attachment_payload = None

    if att_source == "Technical Documentation Manuals":
        loaded_docs = load_all_documents()
        doc_names = [d["filename"] for d in loaded_docs if d["status"] == "LOADED"]
        selected_doc = st.selectbox("Select Documentation Manual to Attach", doc_names, key=f"{key_prefix}_doc_select")
        if selected_doc:
            for d in loaded_docs:
                if d["filename"] == selected_doc and d["content"]:
                    attachment_payload = {
                        "filename": d["filename"],
                        "content": d["content"].encode("utf-8"),
                        "size_kb": d["size_kb"]
                    }
                    st.caption(f"📎 Attached: `{d['filename']}` ({d['size_kb']} KB)")
                    break

    elif att_source == "Upload Custom File":
        uploaded_file = st.file_uploader("Upload File (.txt, .pdf, .csv, .xlsx, .png, .jpg)", type=["txt", "pdf", "csv", "xlsx", "png", "jpg"], key=f"{key_prefix}_file_upload")
        if uploaded_file is not None:
            file_bytes = uploaded_file.read()
            attachment_payload = {
                "filename": uploaded_file.name,
                "content": file_bytes,
                "size_kb": round(len(file_bytes) / 1024, 1)
            }
            st.caption(f"📎 Attached Custom File: `{uploaded_file.name}` ({attachment_payload['size_kb']} KB)")

    st.divider()

    # 6. Email Preview Box
    with st.expander("📧 EMAIL PREVIEW", expanded=False):
        effective_prov = detected_label if prov_choice == "AUTO" else ("🟢 Gmail" if prov_choice == "GMAIL" else "🔵 Microsoft Outlook")
        st.markdown(f"**To:** `{recipient_in}`")
        st.markdown(f"**Provider:** {effective_prov}")
        st.markdown(f"**Subject:** {subject_in}")
        if attachment_payload:
            st.markdown(f"**Attachment:** 📄 `{attachment_payload['filename']}` ({attachment_payload['size_kb']} KB)")
        st.markdown("**Message:**")
        st.code(body_in, language="text")

    # 7. Action Button
    send_col, cancel_col = st.columns([1.5, 3])
    sent_result = None

    if send_col.button("📧 SEND EMAIL", key=f"{key_prefix}_btn_send", type="primary", use_container_width=True):
        if not recipient_in:
            st.error("🔴 Please enter a recipient email address.")
        elif not validate_email_address(recipient_in):
            st.error(f"🔴 INVALID EMAIL ADDRESS: '{recipient_in}' is not a valid email syntax.")
        else:
            with st.spinner("Connecting to email provider & dispatching..."):
                atts_list = [attachment_payload] if attachment_payload else None
                res = send_universal_email(
                    recipient=recipient_in,
                    subject=subject_in,
                    body=body_in,
                    attachments=atts_list,
                    provider_mode=prov_choice,
                    session=session,
                    is_automatic=False,
                    machine_id=prefill_machine,
                    work_order_id=prefill_work_order
                )
                st.session_state[f"{key_prefix}_last_result"] = res
                sent_result = res
                safe_rerun()

    # 8. Render Result Box
    last_res = st.session_state.get(f"{key_prefix}_last_result")
    if last_res:
        if last_res.get("success"):
            st.success(f"{last_res.get('message')}")
            res_c1, res_c2, res_c3 = st.columns(3)
            res_c1.markdown(f"**To:** `{last_res.get('recipient')}`")
            res_c2.markdown(f"**Provider:** `{last_res.get('provider_display')}`")
            res_c3.markdown(f"**Timestamp:** `{last_res.get('timestamp')}`")
        else:
            st.error(f"{last_res.get('message')}")
            if last_res.get("error"):
                with st.expander("🔍 View Error Details"):
                    st.json(last_res)

    return sent_result
