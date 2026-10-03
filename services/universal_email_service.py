# Fixed f-string backslash SyntaxError in audit SQL escaping
# Co-authored with CoCo
"""
services/universal_email_service.py
Universal Email Dispatch Engine for MFG Predictive Maintenance.
Validates email addresses, dispatches via Gmail API OAuth 2.0 or Outlook, and logs audit records to Snowflake.
"""

import os
import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from services.email_notification_service import GmailEmailProvider, get_gmail_config
from services.outlook_notification_service import OutlookEmailProvider, get_outlook_config

logger = logging.getLogger(__name__)

# Global set for in-memory duplicate tracking of automatic alerts
DISPATCHED_AUTOMATIC_KEYS = set()

# Regular Expression for Email Syntax Validation
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_email_address(email: str) -> bool:
    """Validates email format using strict regex match."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def detect_email_provider(recipient: str) -> Tuple[str, str]:
    """
    Detects recommended provider based on recipient email domain.
    Returns tuple: (provider_code, provider_display_name).
    """
    domain = recipient.split("@")[-1].lower() if "@" in recipient else ""
    
    if "gmail.com" in domain:
        return "GMAIL", "🟢 Gmail"
    elif any(d in domain for d in ["outlook.com", "hotmail.com", "live.com", "msn.com"]):
        return "OUTLOOK", "🔵 Microsoft Outlook"
    else:
        return "SNOWFLAKE_EMAIL", "🟢 Snowflake Email"


def _init_audit_table(session) -> None:
    """Ensures NOTIFICATION_AUDIT table exists in Snowflake DB."""
    if not session:
        return
    try:
        session.sql("""
            CREATE TABLE IF NOT EXISTS PM_OEE_DB.CORE.NOTIFICATION_AUDIT (
                NOTIFICATION_ID STRING DEFAULT UUID_STRING(),
                EVENT_ID STRING,
                WORK_ORDER_ID STRING,
                MACHINE_ID STRING,
                NOTIFICATION_TYPE STRING,
                PROVIDER STRING,
                RECIPIENT STRING,
                SUBJECT STRING,
                STATUS STRING,
                ERROR_MESSAGE STRING,
                CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """).collect()
    except Exception as e:
        logger.warning(f"Failed to initialize NOTIFICATION_AUDIT table: {e}")


def check_automatic_duplicate(session, event_id: str, recipient: str, provider: str) -> bool:
    """Checks if an automatic notification was already sent for the given event (parameterized)."""
    cache_key = f"{event_id}:{recipient}:{provider}"
    if cache_key in DISPATCHED_AUTOMATIC_KEYS:
        return True

    if not session or not event_id:
        return False

    try:
        _init_audit_table(session)
        from config import table
        audit_tbl = table("NOTIFICATION_AUDIT")
        sql = f"""
            SELECT COUNT(*) AS CNT 
            FROM {audit_tbl} 
            WHERE EVENT_ID = ? 
              AND RECIPIENT = ?
              AND PROVIDER = ? 
              AND STATUS IN ('SENT', 'DELIVERY_ACCEPTED', 'ACCEPTED')
        """
        rows = session.sql(sql, params=[str(event_id), str(recipient), str(provider).upper()]).collect()
        return rows[0]["CNT"] > 0
    except Exception as e:
        logger.warning(f"Duplicate check error: {e}")
        return False


def record_universal_audit(
    session,
    event_id: Optional[str],
    machine_id: Optional[str],
    work_order_id: Optional[str],
    notification_type: str,
    provider: str,
    recipient: str,
    subject: str,
    status: str,
    message_id: Optional[str] = None,
    error_msg: Optional[str] = None
) -> None:
    """Persists notification dispatch record into Snowflake NOTIFICATION_AUDIT (parameterized)."""
    if not session:
        return
    try:
        _init_audit_table(session)
        from config import table
        audit_tbl = table("NOTIFICATION_AUDIT")
        err_val = message_id or error_msg
        err_str = str(err_val)[:950] if err_val else None

        sql = f"""
            INSERT INTO {audit_tbl} (
                EVENT_ID, WORK_ORDER_ID, MACHINE_ID, NOTIFICATION_TYPE,
                PROVIDER, RECIPIENT, SUBJECT, STATUS, ERROR_MESSAGE
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
        """
        session.sql(sql, params=[
            str(event_id) if event_id else None,
            str(work_order_id) if work_order_id else None,
            str(machine_id) if machine_id else None,
            str(notification_type),
            str(provider).upper(),
            str(recipient),
            str(subject),
            str(status),
            err_str
        ]).collect()
        logger.info(f"Recorded NOTIFICATION_AUDIT record for {recipient}")
    except Exception as e:
        logger.error(f"Failed to record NOTIFICATION_AUDIT: {e}")


def build_default_html_body(subject: str, text_body: str) -> str:
    """Wraps plain text body in clean industrial HTML template."""
    body_formatted = text_body.replace("\n", "<br>")
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0F172A; color: #F8FAFC; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #1E293B; border-radius: 8px; border: 1px solid #334155; padding: 24px; }}
            .header {{ border-bottom: 2px solid #EF4444; padding-bottom: 12px; margin-bottom: 20px; }}
            .title {{ font-size: 18px; font-weight: bold; color: #EF4444; text-transform: uppercase; letter-spacing: 0.5px; }}
            .content {{ font-size: 14px; line-height: 1.6; color: #E2E8F0; }}
            .footer {{ margin-top: 24px; pt-3; border-top: 1px solid #334155; font-size: 12px; color: #94A3B8; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title">{subject}</div>
            </div>
            <div class="content">
                {body_formatted}
            </div>
            <div class="footer">
                MFG Predictive Maintenance & OEE Command Center · Governed OT/IT System Notice
            </div>
        </div>
    </body>
    </html>
    """


def send_universal_email(
    recipient: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    provider_mode: str = "AUTO",
    session=None,
    is_automatic: bool = False,
    event_id: Optional[str] = None,
    machine_id: Optional[str] = None,
    work_order_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Universal Email Dispatch Engine.
    Accepts ANY recipient email address, validates syntax, determines provider,
    executes send via Gmail API or Outlook, and logs audit records into Snowflake.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    clean_recipient = (recipient or "").strip()

    # 1. Email Format Validation
    if not validate_email_address(clean_recipient):
        err_msg = f"🔴 INVALID EMAIL ADDRESS: '{clean_recipient}' is not a valid email syntax."
        return {
            "success": False,
            "status": "INVALID_EMAIL",
            "provider": "NONE",
            "provider_display": "🔴 Invalid Email",
            "recipient": clean_recipient,
            "subject": subject,
            "timestamp": timestamp,
            "message": err_msg,
            "error": "Syntax Error"
        }

    # 2. Determine Provider
    mode_upper = (provider_mode or "AUTO").upper()
    if mode_upper == "GMAIL":
        provider_code = "GMAIL"
        provider_display = "🟢 Gmail API"
    elif mode_upper in ("OUTLOOK", "MICROSOFT"):
        provider_code = "OUTLOOK"
        provider_display = "🔵 Microsoft Outlook"
    else:
        provider_code, provider_display = detect_email_provider(clean_recipient)

    # 3. Duplicate Protection (Automatic background alerts only)
    if is_automatic and event_id:
        if check_automatic_duplicate(session, event_id, clean_recipient, provider_code):
            return {
                "success": True,
                "status": "SUPPRESSED",
                "provider": provider_code,
                "provider_display": provider_display,
                "recipient": clean_recipient,
                "subject": subject,
                "timestamp": timestamp,
                "message": f"Duplicate automatic notification suppressed for {event_id}."
            }

    # 4. Build HTML content if missing
    final_html = html_body or build_default_html_body(subject, body)

    # 5. Execute Dispatch via Selected Provider
    if provider_code == "GMAIL":
        provider = GmailEmailProvider()
    else:
        provider = OutlookEmailProvider()

    ok, status_code, details = provider.send_email(
        recipient=clean_recipient,
        subject=subject,
        html_body=final_html,
        text_body=body,
        attachments=attachments
    )

    # Record in-memory tracker if automatic
    if is_automatic and event_id and ok:
        DISPATCHED_AUTOMATIC_KEYS.add(f"{event_id}:{clean_recipient}:{provider_code}")

    msg_id = details.get("message_id") if isinstance(details, dict) else None
    err_txt = details.get("error") if isinstance(details, dict) else None

    # 6. Record Audit Trail in Snowflake
    notif_type = "AUTOMATIC_ALERT" if is_automatic else "MANUAL_EMAIL"
    record_universal_audit(
        session=session,
        event_id=event_id,
        machine_id=machine_id,
        work_order_id=work_order_id,
        notification_type=notif_type,
        provider=provider_code,
        recipient=clean_recipient,
        subject=subject,
        status=status_code,
        message_id=msg_id,
        error_msg=err_txt or details.get("message")
    )

    if ok:
        success_msg = f"🟢 EMAIL SENT SUCCESSFULLY to {clean_recipient} via {provider_display}"
        return {
            "success": True,
            "status": "SENT",
            "provider": provider_code,
            "provider_display": provider_display,
            "recipient": clean_recipient,
            "subject": subject,
            "message_id": msg_id,
            "timestamp": timestamp,
            "message": success_msg,
            "details": details
        }
    else:
        fail_msg = details.get("message") if isinstance(details, dict) else f"🔴 EMAIL DELIVERY FAILED: {status_code}"
        return {
            "success": False,
            "status": status_code,
            "provider": provider_code,
            "provider_display": provider_display,
            "recipient": clean_recipient,
            "subject": subject,
            "timestamp": timestamp,
            "message": fail_msg,
            "details": details
        }
