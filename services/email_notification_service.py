"""
services/email_notification_service.py
Gmail Email Provider implementation for MFG Predictive Maintenance.
Delegates email dispatch to official Gmail API OAuth 2.0 Desktop Client (services/gmail_service.py).
Fully isolated from Outlook and business logic.
"""

import logging
from typing import Dict, Any, Tuple, Optional, List
from services.gmail_service import (
    is_gmail_configured,
    get_gmail_status,
    send_email as gmail_send_email,
    DEFAULT_SENDER
)

logger = logging.getLogger(__name__)

def get_gmail_config() -> Dict[str, Any]:
    """Returns Gmail API OAuth configuration and status dictionary."""
    st = get_gmail_status()
    return {
        "provider": "GMAIL",
        "configured": (st.get("status") == "READY"),
        "username": st.get("account", DEFAULT_SENDER),
        "recipient": st.get("account", DEFAULT_SENDER),
        "status_details": st
    }


class GmailEmailProvider:
    """Gmail API OAuth 2.0 Provider."""

    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        self.config = config_override or get_gmail_config()

    def send_email(
        self,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Dispatches email via Google Gmail API users.messages.send.
        Returns (success: bool, status_msg: str, details_dict: dict).
        """
        body_content = text_body or subject
        res = gmail_send_email(
            to=recipient,
            subject=subject,
            body=body_content,
            html_body=html_body,
            attachments=attachments
        )
        status_code = res.get("status", "FAILED" if not res.get("success") else "SENT")
        return res.get("success", False), status_code, res
