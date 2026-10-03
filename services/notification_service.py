# Fixed f-string backslash SyntaxError in audit SQL escaping
# Co-authored with CoCo
"""
services/notification_service.py
Unified Multi-Provider Notification Orchestrator supporting Snowflake Email, Gmail, and Outlook.
Enforces independent channel execution, provider-specific duplicate protection,
Snowflake audit trail persistence, and retry handling.
"""

import os
import time
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List, Set

from services.email_notification_service import GmailEmailProvider, get_gmail_config
from services.outlook_notification_service import OutlookEmailProvider, get_outlook_config
from services.snowflake_email_provider import SnowflakeEmailProvider
from services.slack_service import send_slack_notification, format_critical_alert, format_work_order_approved, check_slack_configuration

logger = logging.getLogger(__name__)

# In-memory tracking for duplicate protection across Streamlit reruns
DISPATCHED_PROVIDER_KEYS: Set[str] = set()

def _init_audit_table(session) -> None:
    """Ensures PM_OEE_DB.CORE.NOTIFICATION_AUDIT table exists with complete multi-provider schema."""
    if not session:
        return
    try:
        session.sql("""
            CREATE TABLE IF NOT EXISTS PM_OEE_DB.CORE.NOTIFICATION_AUDIT (
                AUDIT_ID VARCHAR(50) DEFAULT UUID_STRING(),
                EVENT_ID VARCHAR(100),
                WORK_ORDER_ID VARCHAR(50),
                MACHINE_ID VARCHAR(50),
                NOTIFICATION_TYPE VARCHAR(50),
                PROVIDER VARCHAR(50),
                RECIPIENT VARCHAR(200),
                SUBJECT VARCHAR(500),
                STATUS VARCHAR(50),
                ERROR_MESSAGE VARCHAR(2000),
                TRIGGER_TYPE VARCHAR(20) DEFAULT 'MANUAL',
                DISPATCHED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """).collect()
    except Exception as e:
        logger.warning(f"Could not initialize NOTIFICATION_AUDIT table in Snowflake: {e}")


def check_provider_duplicate(session, event_id: str, provider: str) -> bool:
    """
    Checks if a successful notification dispatch already exists for EVENT_ID + PROVIDER.
    Returns True if already sent (duplicate detected).
    """
    prov_key = f"{event_id}:{provider.upper()}"
    if prov_key in DISPATCHED_PROVIDER_KEYS:
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
              AND PROVIDER = ? 
              AND STATUS IN ('SENT', 'DELIVERY_ACCEPTED', 'ACCEPTED')
        """
        rows = session.sql(sql, params=[str(event_id), str(provider).upper()]).collect()
        return rows[0]["CNT"] > 0
    except Exception as e:
        logger.warning(f"Duplicate dispatch check failed for {prov_key}: {e}")
        return False


def record_notification_audit(
    session,
    event_id: str,
    machine_id: str,
    work_order_id: str,
    notification_type: str,
    provider: str,
    recipient: str,
    subject: str,
    status: str,
    error_msg: Optional[str] = None,
    trigger_type: str = "MANUAL"
) -> None:
    """Persists a transactional audit log record into Snowflake NOTIFICATION_AUDIT table using parameterized query."""
    if not session:
        return
    try:
        _init_audit_table(session)
        from config import table
        audit_tbl = table("NOTIFICATION_AUDIT")
        sql = f"""
            INSERT INTO {audit_tbl} (
                EVENT_ID, WORK_ORDER_ID, MACHINE_ID, NOTIFICATION_TYPE,
                PROVIDER, RECIPIENT, SUBJECT, STATUS, ERROR_MESSAGE, TRIGGER_TYPE
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?
            )
        """
        session.sql(sql, params=[
            str(event_id),
            str(work_order_id) if work_order_id else None,
            str(machine_id) if machine_id else None,
            str(notification_type),
            str(provider).upper(),
            str(recipient) if recipient else "",
            str(subject) if subject else "",
            str(status) if status else "",
            str(error_msg)[:950] if error_msg else None,
            str(trigger_type) if trigger_type else "MANUAL",
        ]).collect()
    except Exception as e:
        logger.warning(f"Could not record notification audit log into Snowflake: {e}")


def build_critical_alert_html(alert_payload: Dict[str, Any]) -> str:
    """Builds standard rich HTML body for Gmail and Outlook critical alerts."""
    machine_id = alert_payload.get("machine_id", "Machine_03")
    equipment = alert_payload.get("machine_name", "Precision Mill C")
    line = alert_payload.get("line_name", "Line 2")
    vib = float(alert_payload.get("vibration_mm_s", 6.15))
    temp = float(alert_payload.get("temperature_c", 97.3))
    rpm = float(alert_payload.get("rpm", 1552))
    risk_score = float(alert_payload.get("failure_probability", alert_payload.get("risk_score", 1.0)))
    fprob = float(alert_payload.get("ml_failure_probability", 0.998))
    rul = float(alert_payload.get("rul_hours", 18.0))
    dt_risk = alert_payload.get("financial_risk_usd", "$12,500")
    part = alert_payload.get("recommended_part", "SKF-6205-2RS")
    stock = alert_payload.get("inventory_on_hand", 4)
    action = alert_payload.get("recommended_action", "Inspect spindle bearing immediately and follow approved maintenance procedure.")
    app_url = os.environ.get("APP_BASE_URL", "http://localhost:8501")

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #0F172A; color: #F8FAFC; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: #1E293B; border-radius: 8px; border: 1px solid #334155; padding: 24px;">
            <div style="border-bottom: 2px solid #EF4444; padding-bottom: 12px; margin-bottom: 16px;">
                <h2 style="color: #EF4444; margin: 0;">🚨 CRITICAL FAILURE ALERT</h2>
                <div style="color: #94A3B8; font-size: 0.9rem; margin-top: 4px;">MFG Predictive Maintenance Command Center</div>
            </div>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 0.9rem;">
                <tr><td style="color: #94A3B8; padding: 4px 0;">Machine:</td><td><strong style="color: #F8FAFC;">{machine_id}</strong></td></tr>
                <tr><td style="color: #94A3B8; padding: 4px 0;">Equipment:</td><td>{equipment}</td></tr>
                <tr><td style="color: #94A3B8; padding: 4px 0;">Line:</td><td>{line}</td></tr>
                <tr><td style="color: #94A3B8; padding: 4px 0;">Severity:</td><td><span style="color: #EF4444; font-weight: bold;">🔴 CRITICAL</span></td></tr>
            </table>

            <div style="background: #0F172A; padding: 12px; border-radius: 6px; border: 1px solid #334155; margin-bottom: 16px;">
                <h4 style="color: #38BDF8; margin: 0 0 8px 0;">LIVE TELEMETRY vs BASELINE</h4>
                <div style="font-size: 0.88rem; line-height: 1.6;">
                    <div>Vibration: <strong style="color: #EF4444;">{vib:.2f} mm/s</strong> (Baseline: 2.00 mm/s)</div>
                    <div>Temperature: <strong style="color: #EF4444;">{temp:.1f} °C</strong> (Baseline: 65.0 °C)</div>
                    <div>Speed: <strong>{rpm:.0f} RPM</strong> (Baseline: 1800 RPM)</div>
                </div>
            </div>

            <div style="background: #0F172A; padding: 12px; border-radius: 6px; border: 1px solid #334155; margin-bottom: 16px;">
                <h4 style="color: #A855F7; margin: 0 0 8px 0;">PREDICTIVE RISK (SNOWFLAKE ML)</h4>
                <div style="font-size: 0.88rem; line-height: 1.6;">
                    <div>Failure Probability: <strong style="color: #EF4444;">{fprob*100:.1f}%</strong></div>
                    <div>Unified Risk Score: <strong>{risk_score*100:.0f}%</strong></div>
                    <div>Estimated RUL: <strong style="color: #38BDF8;">{rul:.1f} hours</strong></div>
                </div>
            </div>

            <div style="background: #0F172A; padding: 12px; border-radius: 6px; border: 1px solid #334155; margin-bottom: 16px;">
                <h4 style="color: #F59E0B; margin: 0 0 8px 0;">MAINTENANCE IMPACT</h4>
                <div style="font-size: 0.88rem; line-height: 1.6;">
                    <div>Potential Downtime Risk: <strong style="color: #EF4444;">{dt_risk}</strong></div>
                    <div>Required Part: <strong>{part}</strong></div>
                    <div>Inventory: <strong>{stock} units</strong> (<span style="color: #22C55E; font-weight: bold;">🟢 IN STOCK</span>)</div>
                </div>
            </div>

            <div style="background: #450A0A; border-left: 4px solid #EF4444; padding: 12px; border-radius: 4px; margin-bottom: 20px;">
                <h4 style="color: #EF4444; margin: 0 0 4px 0;">RECOMMENDED ACTION</h4>
                <p style="margin: 0; font-size: 0.88rem; color: #FCA5A5;">{action}</p>
            </div>

            <div style="text-align: center; margin-top: 24px;">
                <a href="{app_url}" style="background: #2563EB; color: #FFFFFF; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">OPEN COMMAND CENTER</a>
            </div>

            <div style="margin-top: 24px; border-top: 1px solid #334155; padding-top: 12px; text-align: center; font-size: 0.75rem; color: #64748B;">
                MFG Predictive Maintenance & OEE Command Center · Governed OT/IT System
            </div>
        </div>
    </body>
    </html>
    """


def build_work_order_approval_html(wo_payload: Dict[str, Any]) -> str:
    """Builds rich HTML email body for Work Order Approval events."""
    wo_id = wo_payload.get("work_order_id", "WO-10023")
    machine_id = wo_payload.get("machine_id", "Machine_03")
    part = wo_payload.get("recommended_part", "SKF-6205-2RS")
    action = wo_payload.get("approved_action", "Approved for immediate LOTO maintenance & bearing replacement.")
    approver = wo_payload.get("approver", "Human Plant Manager")
    app_url = os.environ.get("APP_BASE_URL", "http://localhost:8501")

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #0F172A; color: #F8FAFC; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: #1E293B; border-radius: 8px; border: 1px solid #334155; padding: 24px;">
            <div style="border-bottom: 2px solid #22C55E; padding-bottom: 12px; margin-bottom: 16px;">
                <h2 style="color: #22C55E; margin: 0;">🛠️ WORK ORDER APPROVED</h2>
                <div style="color: #94A3B8; font-size: 0.9rem; margin-top: 4px;">MFG Governed Work Order Governance</div>
            </div>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 0.9rem;">
                <tr><td style="color: #94A3B8; padding: 4px 0;">Work Order ID:</td><td><strong style="color: #F8FAFC;">{wo_id}</strong></td></tr>
                <tr><td style="color: #94A3B8; padding: 4px 0;">Machine:</td><td><strong style="color: #F8FAFC;">{machine_id}</strong></td></tr>
                <tr><td style="color: #94A3B8; padding: 4px 0;">Status:</td><td><span style="color: #22C55E; font-weight: bold;">🟢 APPROVED</span></td></tr>
                <tr><td style="color: #94A3B8; padding: 4px 0;">Approver:</td><td>{approver}</td></tr>
                <tr><td style="color: #94A3B8; padding: 4px 0;">Required Part:</td><td><strong>{part}</strong></td></tr>
            </table>

            <div style="background: #062C1B; border-left: 4px solid #22C55E; padding: 12px; border-radius: 4px; margin-bottom: 20px;">
                <h4 style="color: #22C55E; margin: 0 0 4px 0;">APPROVED ACTION PLAN</h4>
                <p style="margin: 0; font-size: 0.88rem; color: #86EFAC;">{action}</p>
            </div>

            <div style="text-align: center; margin-top: 24px;">
                <a href="{app_url}" style="background: #2563EB; color: #FFFFFF; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">VIEW WORK ORDER IN COMMAND CENTER</a>
            </div>
        </div>
    </body>
    </html>
    """


def send_critical_notification(event_payload: Dict[str, Any], session=None, force: bool = False) -> Dict[str, Any]:
    """
    Dispatches Critical Maintenance Notifications via Snowflake Email (primary), Gmail, Outlook, and Slack.
    Applies provider-specific duplicate protection (`EVENT_ID + ":" + PROVIDER`).
    Logs status into Snowflake `NOTIFICATION_AUDIT` table.
    """
    machine_id = str(event_payload.get("machine_id", "Machine_03"))
    wo_id = str(event_payload.get("work_order_id", "WO-10023"))
    event_id = str(event_payload.get("event_id") or f"ALERT-{wo_id}-{machine_id}")
    subject = f"🚨 CRITICAL MAINTENANCE ALERT — {machine_id}"
    html_body = build_critical_alert_html(event_payload)
    plain_body = f"CRITICAL ALERT: {machine_id}\nVibration: {event_payload.get('vibration_mm_s', 'N/A')} mm/s\nTemperature: {event_payload.get('temperature_c', 'N/A')} C\nRisk: {event_payload.get('failure_probability', 'N/A')}\nRUL: {event_payload.get('rul_hours', 'N/A')} hours"

    gmail_provider = GmailEmailProvider()
    outlook_provider = OutlookEmailProvider()

    results = {
        "event_id": event_id,
        "machine_id": machine_id,
        "work_order_id": wo_id,
        "snowflake_email": {"status": "NOT_RUN", "message": ""},
        "gmail": {"status": "NOT_RUN", "message": ""},
        "outlook": {"status": "NOT_RUN", "message": ""},
        "slack": {"status": "NOT_RUN", "message": ""},
        "overall": "FAILED"
    }

    # 0. Snowflake Email (primary — always works in this environment)
    if session:
        sf_dup = check_provider_duplicate(session, event_id, "SNOWFLAKE_EMAIL") if not force else False
        if sf_dup:
            results["snowflake_email"] = {"status": "SUPPRESSED", "message": f"Snowflake email already sent for {event_id}."}
        else:
            sf_provider = SnowflakeEmailProvider()
            from services.snowflake_email_provider import DEFAULT_RECIPIENT
            sf_ok, sf_status, sf_det = sf_provider.send_email(session, DEFAULT_RECIPIENT, subject, plain_body)
            results["snowflake_email"] = {"status": sf_status, "message": sf_det.get("message", "")}
            if sf_ok:
                DISPATCHED_PROVIDER_KEYS.add(f"{event_id}:SNOWFLAKE_EMAIL")
            record_notification_audit(session, event_id, machine_id, wo_id, "CRITICAL_ALERT", "SNOWFLAKE_EMAIL", DEFAULT_RECIPIENT, subject, sf_status, sf_det.get("error"))

    # 1. Gmail Dispatch
    gmail_dup = check_provider_duplicate(session, event_id, "GMAIL") if not force else False
    if gmail_dup:
        results["gmail"] = {"status": "SUPPRESSED", "message": f"Gmail alert already dispatched for {event_id}."}
    else:
        g_ok, g_status, g_details = gmail_provider.send_email(
            recipient=gmail_provider.config.get("recipient", ""),
            subject=subject,
            html_body=html_body
        )
        results["gmail"] = {"status": g_status, "message": g_details.get("message", "")}
        if g_ok:
            DISPATCHED_PROVIDER_KEYS.add(f"{event_id}:GMAIL")
        record_notification_audit(
            session=session,
            event_id=event_id,
            machine_id=machine_id,
            work_order_id=wo_id,
            notification_type="CRITICAL_ALERT",
            provider="GMAIL",
            recipient=g_details.get("recipient", ""),
            subject=subject,
            status=g_status,
            error_msg=g_details.get("error")
        )

    # 2. Outlook Dispatch (Independent from Gmail failure)
    outlook_dup = check_provider_duplicate(session, event_id, "OUTLOOK") if not force else False
    if outlook_dup:
        results["outlook"] = {"status": "SUPPRESSED", "message": f"Outlook alert already dispatched for {event_id}."}
    else:
        o_ok, o_status, o_details = outlook_provider.send_email(
            recipient=outlook_provider.config.get("recipient", ""),
            subject=subject,
            html_body=html_body
        )
        results["outlook"] = {"status": o_status, "message": o_details.get("message", "")}
        if o_ok:
            DISPATCHED_PROVIDER_KEYS.add(f"{event_id}:OUTLOOK")
        record_notification_audit(
            session=session,
            event_id=event_id,
            machine_id=machine_id,
            work_order_id=wo_id,
            notification_type="CRITICAL_ALERT",
            provider="OUTLOOK",
            recipient=o_details.get("recipient", ""),
            subject=subject,
            status=o_status,
            error_msg=o_details.get("error")
        )

    # 3. Slack Dispatch (Independent from Email failures)
    results["slack"] = {"status": "NOT_RUN", "message": ""}
    slack_dup = check_provider_duplicate(session, event_id, "SLACK") if not force else False
    if slack_dup:
        results["slack"] = {"status": "SUPPRESSED", "message": f"Slack alert already dispatched for {event_id}."}
    else:
        slack_msg = format_critical_alert(event_payload)
        sl_ok, sl_status, sl_details = send_slack_notification(session, slack_msg)
        results["slack"] = {"status": sl_status, "message": sl_details.get("message", "")}
        if sl_ok:
            DISPATCHED_PROVIDER_KEYS.add(f"{event_id}:SLACK")
        record_notification_audit(
            session=session,
            event_id=event_id,
            machine_id=machine_id,
            work_order_id=wo_id,
            notification_type="CRITICAL_ALERT",
            provider="SLACK",
            recipient="slack-channel",
            subject=f"Critical Alert - {machine_id}",
            status=sl_status,
            error_msg=sl_details.get("message") if not sl_ok else None
        )

    # Aggregate Overall Status
    sf_s = results.get("snowflake_email", {}).get("status", "NOT_RUN")
    g_s = results["gmail"]["status"]
    o_s = results["outlook"]["status"]
    sl_s = results.get("slack", {}).get("status", "NOT_RUN")
    sent_statuses = ("SENT", "DELIVERY_ACCEPTED")
    if sf_s in sent_statuses or sl_s == "SENT" or (g_s in sent_statuses and o_s in sent_statuses):
        results["overall"] = "ALL_SENT"
    elif sf_s in sent_statuses or sl_s == "SENT" or g_s in sent_statuses or o_s in sent_statuses:
        results["overall"] = "PARTIAL_SUCCESS"
    elif g_s == "SUPPRESSED" and o_s == "SUPPRESSED" and sl_s == "SUPPRESSED":
        results["overall"] = "SUPPRESSED"
    else:
        results["overall"] = "FAILED"

    return results


def send_work_order_approval_notification(wo_payload: Dict[str, Any], session=None) -> Dict[str, Any]:
    """Dispatches Work Order Approval Notification via Snowflake Email (primary), Gmail, Outlook, and Slack."""
    wo_id = str(wo_payload.get("work_order_id", "WO-10023"))
    machine_id = str(wo_payload.get("machine_id", "Machine_03"))
    event_id = f"WO_APPROVE-{wo_id}-{machine_id}"
    subject = f"🛠️ WORK ORDER APPROVED — {machine_id}"
    html_body = build_work_order_approval_html(wo_payload)
    plain_body = f"Work Order {wo_id} for {machine_id} has been APPROVED.\nAction: {wo_payload.get('approved_action', 'N/A')}\nParts: {wo_payload.get('recommended_part', 'N/A')}\nApprover: {wo_payload.get('approver', 'Plant Manager')}"

    results = {"event_id": event_id, "snowflake_email": {}, "gmail": {}, "outlook": {}, "slack": {}}

    # Snowflake Email (primary — always works in this environment)
    if session and not check_provider_duplicate(session, event_id, "SNOWFLAKE_EMAIL"):
        sf_provider = SnowflakeEmailProvider()
        from services.snowflake_email_provider import DEFAULT_RECIPIENT
        sf_ok, sf_status, sf_det = sf_provider.send_email(session, DEFAULT_RECIPIENT, subject, plain_body)
        results["snowflake_email"] = {"status": sf_status, "message": sf_det.get("message", "")}
        if sf_ok:
            DISPATCHED_PROVIDER_KEYS.add(f"{event_id}:SNOWFLAKE_EMAIL")
        record_notification_audit(session, event_id, machine_id, wo_id, "WO_APPROVAL", "SNOWFLAKE_EMAIL", DEFAULT_RECIPIENT, subject, sf_status, sf_det.get("error"))

    gmail_provider = GmailEmailProvider()
    outlook_provider = OutlookEmailProvider()

    # Gmail
    if not check_provider_duplicate(session, event_id, "GMAIL"):
        g_ok, g_status, g_det = gmail_provider.send_email(
            recipient=gmail_provider.config.get("recipient"),
            subject=subject,
            html_body=html_body
        )
        results["gmail"] = {"status": g_status, "message": g_det.get("message")}
        if g_ok:
            DISPATCHED_PROVIDER_KEYS.add(f"{event_id}:GMAIL")
        record_notification_audit(session, event_id, machine_id, wo_id, "WO_APPROVAL", "GMAIL", g_det.get("recipient", ""), subject, g_status, g_det.get("error"))

    # Outlook
    if not check_provider_duplicate(session, event_id, "OUTLOOK"):
        o_ok, o_status, o_det = outlook_provider.send_email(
            recipient=outlook_provider.config.get("recipient"),
            subject=subject,
            html_body=html_body
        )
        results["outlook"] = {"status": o_status, "message": o_det.get("message")}
        if o_ok:
            DISPATCHED_PROVIDER_KEYS.add(f"{event_id}:OUTLOOK")
        record_notification_audit(session, event_id, machine_id, wo_id, "WO_APPROVAL", "OUTLOOK", o_det.get("recipient", ""), subject, o_status, o_det.get("error"))

    # Slack
    if not check_provider_duplicate(session, event_id, "SLACK"):
        slack_msg = format_work_order_approved(wo_payload)
        sl_ok, sl_status, sl_details = send_slack_notification(session, slack_msg)
        results["slack"] = {"status": sl_status, "message": sl_details.get("message", "")}
        if sl_ok:
            DISPATCHED_PROVIDER_KEYS.add(f"{event_id}:SLACK")
        record_notification_audit(session, event_id, machine_id, wo_id, "WO_APPROVAL", "SLACK", "slack-channel", subject, sl_status, sl_details.get("message") if not sl_ok else None)

    return results


def send_test_notification_all(session=None) -> Dict[str, Any]:
    """Sends one test notification through every configured provider (Gmail + Outlook)."""
    test_event = {
        "event_id": f"TEST-{int(time.time())}",
        "machine_id": "Machine_03",
        "work_order_id": "WO-TEST",
        "vibration_mm_s": 6.15,
        "temperature_c": 97.3,
        "rpm": 1552,
        "failure_probability": 0.998,
        "rul_hours": 18.0,
        "financial_risk_usd": "$12,500",
        "recommended_part": "SKF-6205-2RS",
        "inventory_on_hand": 4,
        "recommended_action": "System Status Diagnostic Test Email Notification."
    }
    return send_critical_notification(test_event, session=session, force=True)


def retry_failed_provider(session, audit_record: Dict[str, Any]) -> Dict[str, Any]:
    """Retries ONLY the failed provider for a specific notification event."""
    provider = str(audit_record.get("PROVIDER", "GMAIL")).upper()
    event_id = str(audit_record.get("EVENT_ID", f"RETRY-{int(time.time())}"))
    machine_id = str(audit_record.get("MACHINE_ID", "Machine_03"))
    wo_id = str(audit_record.get("WORK_ORDER_ID", "WO-10023"))
    subject = str(audit_record.get("SUBJECT", f"🚨 CRITICAL MAINTENANCE ALERT — {machine_id}"))
    
    event_payload = {
        "machine_id": machine_id,
        "work_order_id": wo_id,
        "vibration_mm_s": 6.15,
        "temperature_c": 97.3,
        "rpm": 1552,
        "failure_probability": 0.998,
        "rul_hours": 18.0,
        "recommended_part": "SKF-6205-2RS",
        "inventory_on_hand": 4,
        "recommended_action": "Retry dispatch for failed provider notification."
    }
    html_body = build_critical_alert_html(event_payload)

    if provider == "GMAIL":
        p = GmailEmailProvider()
    else:
        p = OutlookEmailProvider()

    ok, status, details = p.send_email(
        recipient=audit_record.get("RECIPIENT") or p.config.get("recipient"),
        subject=subject,
        html_body=html_body
    )

    if ok:
        DISPATCHED_PROVIDER_KEYS.add(f"{event_id}:{provider}")

    record_notification_audit(
        session=session,
        event_id=event_id,
        machine_id=machine_id,
        work_order_id=wo_id,
        notification_type="RETRY_DISPATCH",
        provider=provider,
        recipient=details.get("recipient", ""),
        subject=subject,
        status=status,
        error_msg=details.get("error")
    )

    return {"provider": provider, "status": status, "message": details.get("message")}


def reset_notification_audit(session=None) -> Dict[str, Any]:
    """Purges demo audit records from NOTIFICATION_AUDIT without resetting credentials."""
    DISPATCHED_PROVIDER_KEYS.clear()
    try:
        from services.universal_email_service import DISPATCHED_AUTOMATIC_KEYS
        DISPATCHED_AUTOMATIC_KEYS.clear()
    except Exception:
        pass
    if session:
        try:
            from config import table
            audit_tbl = table("NOTIFICATION_AUDIT")
            session.sql(f"DELETE FROM {audit_tbl}").collect()
        except Exception as e:
            logger.warning(f"Failed to clear NOTIFICATION_AUDIT table in Snowflake: {e}")
    return {"status": "SUCCESS", "message": "Cleared demo notification audit records. Provider credentials preserved."}

# Backwards compatibility aliases
dispatch_critical_notifications = send_critical_notification


def send_snowflake_email(
    session,
    recipient: str,
    notification_type: str,
    alert_payload: Dict[str, Any],
    force: bool = False,
) -> Dict[str, Any]:
    """
    Sends notification via Snowflake native SYSTEM$SEND_EMAIL.
    This is the default verified provider for the Trial account.

    Args:
        session: Snowflake Snowpark session
        recipient: Verified email address
        notification_type: 'CRITICAL_ALERT' or 'INCIDENT_REPORT'
        alert_payload: Machine context dict
        force: Skip duplicate check

    Returns:
        Dict with status, provider, recipient, timestamp
    """
    provider = SnowflakeEmailProvider()
    machine_id = str(alert_payload.get("machine_id", "Machine_03"))
    event_id = str(alert_payload.get("event_id") or f"SF-{machine_id}-{int(time.time())}")

    # Duplicate check
    if not force:
        sf_dup = check_provider_duplicate(session, event_id, "SNOWFLAKE_EMAIL")
        if sf_dup:
            return {
                "status": "SUPPRESSED",
                "provider": "SNOWFLAKE_EMAIL",
                "message": f"Snowflake email already sent for {event_id}",
            }

    if notification_type == "CRITICAL_ALERT":
        ok, status, details = provider.send_critical_alert(
            session=session,
            recipient=recipient,
            machine_id=machine_id,
            alert_payload=alert_payload,
        )
    elif notification_type == "INCIDENT_REPORT":
        report_summary = alert_payload.get("report_summary", "Incident report generated.")
        ok, status, details = provider.send_incident_report(
            session=session,
            recipient=recipient,
            machine_id=machine_id,
            report_summary=report_summary,
        )
    else:
        # Generic email
        subject = alert_payload.get("subject", f"MFG Alert — {machine_id}")
        body = alert_payload.get("body", str(alert_payload))
        ok, status, details = provider.send_email(session, recipient, subject, body)

    if ok:
        DISPATCHED_PROVIDER_KEYS.add(f"{event_id}:SNOWFLAKE_EMAIL")

    # Audit
    record_notification_audit(
        session=session,
        event_id=event_id,
        machine_id=machine_id,
        work_order_id=alert_payload.get("work_order_id"),
        notification_type=notification_type,
        provider="SNOWFLAKE_EMAIL",
        recipient=recipient,
        subject=details.get("subject", ""),
        status=status,
        error_msg=details.get("error"),
    )

    return {
        "status": status,
        "success": ok,
        "provider": "SNOWFLAKE_EMAIL",
        "recipient": recipient,
        "timestamp": details.get("timestamp", ""),
        "message": details.get("message", ""),
    }


def get_provider_status() -> Dict[str, Dict[str, Any]]:
    """Returns status of all notification providers."""
    sf_provider = SnowflakeEmailProvider()
    gmail_cfg = get_gmail_config()
    outlook_cfg = get_outlook_config()

    return {
        "snowflake_email": {
            "status": "READY",
            "label": "Snowflake Email",
            "icon": "🟢",
            "description": "Native SYSTEM$SEND_EMAIL via MFG_EMAIL_NOTIFICATION",
            "requires_eai": False,
            "active": True,
        },
        "gmail": {
            "status": "EAI_REQUIRED",
            "label": "Gmail API",
            "icon": "🟡",
            "description": "FUTURE — Requires External Access Integration (Enterprise account)",
            "requires_eai": True,
            "active": False,
        },
        "outlook": {
            "status": "EAI_REQUIRED",
            "label": "Outlook / MS Graph",
            "icon": "🟡",
            "description": "FUTURE — Requires External Access Integration (Enterprise account)",
            "requires_eai": True,
            "active": False,
        },
        "slack": {
            "status": "READY",
            "label": "Slack Webhook",
            "icon": "🟢",
            "description": "Native SYSTEM$SEND_SNOWFLAKE_NOTIFICATION via MFG_SLACK_NOTIFICATION",
            "requires_eai": False,
            "active": True,
        },
    }

def send_email_alert(alert_payload: Dict[str, Any], recipient_override: Optional[str] = None) -> Tuple[bool, str]:
    """Legacy helper function delegating to send_critical_notification or send_universal_email."""
    from services.universal_email_service import send_universal_email
    recipient = recipient_override or ""
    if not recipient:
        return {"success": False, "message": "No recipient configured."}
    res = send_universal_email(
        recipient=recipient,
        subject=f"🚨 CRITICAL MAINTENANCE ALERT — {alert_payload.get('machine_id', 'Machine_03')}",
        body=str(alert_payload.get('recommended_action', 'Inspect equipment immediately.')),
        is_automatic=False
    )
    return res.get("success", False), res.get("message", "")


def check_email_readiness(session) -> Dict[str, Any]:
    """
    Lightweight email readiness check. Does NOT send any email.
    Returns state: READY, NOT_CONFIGURED, UNAVAILABLE, or NO_RECIPIENT.
    """
    result = {
        "state": "NOT_CONFIGURED",
        "integration_exists": False,
        "integration_enabled": False,
        "provider_label": "Snowflake Email",
        "message": "",
        "hint": "See docs/EMAIL_SETUP.md",
    }

    if not session:
        result["state"] = "UNAVAILABLE"
        result["message"] = "No Snowflake session available."
        return result

    try:
        rows = session.sql(
            "SHOW NOTIFICATION INTEGRATIONS LIKE 'MFG_EMAIL_NOTIFICATION'"
        ).collect()
        if rows and len(rows) > 0:
            result["integration_exists"] = True
            row_dict = rows[0].as_dict() if hasattr(rows[0], 'as_dict') else {k: rows[0][k] for k in range(len(rows[0]))}
            enabled_val = str(row_dict.get("enabled", row_dict.get("ENABLED", ""))).upper()
            result["integration_enabled"] = enabled_val in ("TRUE", "YES", "1")
        else:
            result["state"] = "NOT_CONFIGURED"
            result["message"] = "Snowflake Email notification integration is not configured in this environment."
            return result
    except Exception as e:
        err_str = str(e).lower()
        if "does not exist" in err_str or "not authorized" in err_str:
            result["state"] = "NOT_CONFIGURED"
            result["message"] = "Snowflake Email notification integration is not configured in this environment."
        elif "insufficient privileges" in err_str:
            result["state"] = "UNAVAILABLE"
            result["message"] = "Email notification delivery is unavailable in the current Snowflake account."
        else:
            result["state"] = "UNAVAILABLE"
            result["message"] = "Email notification delivery is unavailable in the current Snowflake account."
        return result

    if result["integration_exists"] and result["integration_enabled"]:
        result["state"] = "READY"
        result["message"] = "Snowflake Email integration is active. Enter a verified recipient to send alerts."
    elif result["integration_exists"] and not result["integration_enabled"]:
        result["state"] = "NOT_CONFIGURED"
        result["message"] = "MFG_EMAIL_NOTIFICATION integration exists but is not enabled."

    return result


def dispatch_dual_channel_notification(
    session,
    event_id: str,
    machine_id: str,
    notification_type: str,
    trigger_type: str,
    alert_payload: Dict[str, Any],
    recipient: str = "",
    mode: str = "MANUAL",
) -> Dict[str, Any]:
    """
    Dual-channel notification dispatcher. Sends to Email AND Slack independently.
    Returns combined result with per-channel status.

    Args:
        session: Snowflake session
        event_id: Unique event ID for idempotency
        machine_id: Machine identifier
        notification_type: CRITICAL_ALERT or INCIDENT_REPORT
        trigger_type: AUTOMATIC or MANUAL
        alert_payload: Context data
        recipient: Email recipient (empty = skip email or use demo)
        mode: DEMO or LIVE
    """
    from services.slack_service import send_slack_notification, format_critical_alert, check_slack_configuration

    results = {"email": None, "slack": None, "overall": "PARTIAL"}

    # --- EMAIL CHANNEL ---
    if mode == "DEMO":
        record_notification_audit(
            session=session, event_id=event_id, machine_id=machine_id,
            work_order_id=alert_payload.get("work_order_id", ""),
            notification_type=notification_type, provider="SNOWFLAKE_EMAIL",
            recipient="demo@notification.internal",
            subject=f"{notification_type} — {machine_id}",
            status="DEMO_SUCCESS", error_msg=None, trigger_type=trigger_type
        )
        results["email"] = {"status": "DEMO_SUCCESS", "message": "Demo recorded"}
    elif recipient:
        sf_result = send_snowflake_email(
            session=session, recipient=recipient,
            notification_type=notification_type,
            alert_payload=alert_payload, force=False
        )
        results["email"] = {"status": sf_result.get("status", "ERROR"), "message": sf_result.get("message", "")}
    else:
        results["email"] = {"status": "NOT_CONFIGURED", "message": "No recipient configured"}
        record_notification_audit(
            session=session, event_id=event_id, machine_id=machine_id,
            work_order_id=alert_payload.get("work_order_id", ""),
            notification_type=notification_type, provider="SNOWFLAKE_EMAIL",
            recipient="", subject=f"{notification_type} — {machine_id}",
            status="NOT_CONFIGURED", error_msg="No recipient", trigger_type=trigger_type
        )

    # --- SLACK CHANNEL ---
    slack_cfg = check_slack_configuration(session)
    if mode == "DEMO":
        record_notification_audit(
            session=session, event_id=f"{event_id}-SLACK", machine_id=machine_id,
            work_order_id=alert_payload.get("work_order_id", ""),
            notification_type=notification_type, provider="SLACK",
            recipient="slack-channel",
            subject=f"{notification_type} — {machine_id}",
            status="DEMO_SUCCESS", error_msg=None, trigger_type=trigger_type
        )
        results["slack"] = {"status": "DEMO_SUCCESS", "message": "Demo recorded"}
    elif slack_cfg.get("status") == "READY":
        slack_msg = format_critical_alert(alert_payload)
        sl_ok, sl_status, sl_details = send_slack_notification(session, slack_msg)
        results["slack"] = {"status": sl_status, "message": sl_details.get("message", "")}
        record_notification_audit(
            session=session, event_id=f"{event_id}-SLACK", machine_id=machine_id,
            work_order_id=alert_payload.get("work_order_id", ""),
            notification_type=notification_type, provider="SLACK",
            recipient="slack-channel",
            subject=f"{notification_type} — {machine_id}",
            status=sl_status, error_msg=sl_details.get("message") if not sl_ok else None,
            trigger_type=trigger_type
        )
    else:
        results["slack"] = {"status": "NOT_CONFIGURED", "message": "Slack not configured"}

    # --- OVERALL ---
    email_ok = results["email"]["status"] in ("SENT", "DEMO_SUCCESS", "SUCCESS")
    slack_ok = results["slack"]["status"] in ("SENT", "DEMO_SUCCESS", "SUCCESS")
    if email_ok and slack_ok:
        results["overall"] = "ALL_SUCCESS"
    elif email_ok or slack_ok:
        results["overall"] = "PARTIAL_SUCCESS"
    else:
        results["overall"] = "ALL_FAILED"

    return results


# Alias for backward compatibility
dispatch_critical_notifications = send_critical_notification
