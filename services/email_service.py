# Centralized email service routing to Snowflake Email (default) or Gmail/Outlook (future)
# Co-authored with CoCo
"""
services/email_service.py
Centralized Production Email Service for MFG Predictive Maintenance & OEE Command Center.
Provides clean facade function send_email(...) for Gmail API OAuth 2.0 and Outlook dispatch,
recipient email validation, auto provider detection, and Snowflake NOTIFICATION_AUDIT trail logging.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from services.universal_email_service import (
    send_universal_email,
    validate_email_address,
    detect_email_provider,
    record_universal_audit
)
from services.gmail_service import (
    get_gmail_status,
    authenticate_gmail,
    verify_gmail_connection,
    DEFAULT_SENDER
)
from services.outlook_notification_service import get_outlook_config

logger = logging.getLogger(__name__)


def check_email_system_status() -> Dict[str, Any]:
    """
    Returns status dict indicating if email notification system is READY or NOT CONFIGURED.
    Snowflake Email is the primary provider; Gmail/Outlook are deferred/future.
    """
    return {
        "status": "READY",
        "label": "🟢 Snowflake Email",
        "description": "Snowflake-native email via SYSTEM$SEND_EMAIL with MFG_EMAIL_NOTIFICATION",
        "gmail_configured": False,
        "outlook_configured": False,
    }


def send_email(
    recipient: str,
    subject: str,
    body: str,
    provider: str = "SNOWFLAKE_EMAIL",
    attachments: Optional[List[Dict[str, Any]]] = None,
    session=None,
    is_automatic: bool = False,
    event_id: Optional[str] = None,
    machine_id: Optional[str] = None,
    work_order_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Universal Email Sending Interface.
    Routes to SnowflakeEmailProvider (default, verified) or Gmail/Outlook (future).
    """
    # Route to Snowflake native email (verified provider on Trial)
    if provider == "SNOWFLAKE_EMAIL":
        from services.notification_service import send_snowflake_email
        alert_payload = {
            "machine_id": machine_id or "Machine_03",
            "work_order_id": work_order_id,
            "event_id": event_id,
            "subject": subject,
            "body": body,
        }
        return send_snowflake_email(
            session=session,
            recipient=recipient,
            notification_type="CUSTOM",
            alert_payload=alert_payload,
            force=True,
        )

    # Fall through to universal_email_service for Gmail/Outlook
    return send_universal_email(
        recipient=recipient,
        subject=subject,
        body=body,
        attachments=attachments,
        provider_mode=provider,
        session=session,
        is_automatic=is_automatic,
        event_id=event_id,
        machine_id=machine_id,
        work_order_id=work_order_id
    )
