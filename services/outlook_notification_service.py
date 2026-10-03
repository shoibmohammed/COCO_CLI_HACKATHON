"""
services/outlook_notification_service.py
Outlook Email Provider implementation for MFG Predictive Maintenance.
Supports authenticated STARTTLS/SMTP via smtp.office365.com:587 and optional file attachments.
Strict configuration detection enforcing BOTH sender and credential presence.
"""

import os
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger(__name__)

def get_outlook_config() -> Dict[str, Any]:
    """
    Loads Outlook configuration securely from Streamlit secrets or environment variables.
    Checks for sender (OUTLOOK_USERNAME) AND credential (OUTLOOK_APP_PASSWORD).
    Never logs or exposes passwords.
    """
    username = os.environ.get("OUTLOOK_USERNAME") or ""
    password = os.environ.get("OUTLOOK_APP_PASSWORD") or os.environ.get("OUTLOOK_PASSWORD") or ""
    recipient = os.environ.get("OUTLOOK_NOTIFICATION_EMAIL") or os.environ.get("OUTLOOK_TO") or ""
    host = os.environ.get("OUTLOOK_SMTP_HOST") or "smtp.office365.com"
    
    try:
        port = int(os.environ.get("OUTLOOK_SMTP_PORT") or 587)
    except ValueError:
        port = 587

    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if "OUTLOOK_USERNAME" in st.secrets:
                username = str(st.secrets["OUTLOOK_USERNAME"])
            if "OUTLOOK_APP_PASSWORD" in st.secrets:
                password = str(st.secrets["OUTLOOK_APP_PASSWORD"])
            elif "OUTLOOK_PASSWORD" in st.secrets:
                password = str(st.secrets["OUTLOOK_PASSWORD"])
            if "OUTLOOK_NOTIFICATION_EMAIL" in st.secrets:
                recipient = str(st.secrets["OUTLOOK_NOTIFICATION_EMAIL"])

            if "outlook" in st.secrets:
                o_sec = st.secrets["outlook"]
                username = str(o_sec.get("username") or o_sec.get("sender") or username)
                password = str(o_sec.get("app_password") or o_sec.get("password") or password)
                recipient = str(o_sec.get("recipient_email") or o_sec.get("to") or recipient)
    except Exception as e:
        logger.debug(f"Streamlit secrets read for Outlook skipped: {e}")

    sender_configured = bool(username and username.strip())
    credential_configured = bool(password and password.strip())
    configured = sender_configured and credential_configured

    missing_fields = []
    if not sender_configured:
        missing_fields.append("OUTLOOK_USERNAME (or [outlook].sender)")
    if not credential_configured:
        missing_fields.append("OUTLOOK_APP_PASSWORD (or [outlook].app_password)")

    return {
        "provider": "OUTLOOK",
        "configured": configured,
        "sender_configured": sender_configured,
        "credential_configured": credential_configured,
        "missing_fields": missing_fields,
        "username": username.strip(),
        "password": password.strip(),
        "recipient": recipient.strip(),
        "host": host.strip(),
        "port": port
    }


class OutlookEmailProvider:
    """Independent Outlook SMTP Email Provider (smtp.office365.com:587 with STARTTLS)."""

    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        self.config = config_override or get_outlook_config()

    def send_email(
        self,
        recipient: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Sends an email via Outlook Office365 SMTP (smtp.office365.com:587).
        Requires configured OUTLOOK_APP_PASSWORD.
        Returns (success: bool, status_msg: str, details_dict: dict).
        """
        cfg = self.config
        target_to = (recipient or cfg.get("recipient") or "outlook-alerts@plant-a.com").strip()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        if not cfg.get("configured") or not cfg.get("password"):
            missing_str = ", ".join(cfg.get("missing_fields", ["OUTLOOK_APP_PASSWORD"]))
            msg = f"Outlook credentials not configured. Missing {missing_str} in .streamlit/secrets.toml or environment variables."
            logger.warning(f"Outlook send attempted without configuration: {msg}")
            return False, "NOT_CONFIGURED", {
                "provider": "OUTLOOK",
                "status": "NOT_CONFIGURED",
                "recipient": target_to,
                "message": msg,
                "missing_fields": cfg.get("missing_fields"),
                "timestamp": timestamp
            }

        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"MFG Predictive Maintenance <{cfg['username']}>"
        msg["To"] = target_to

        body_part = MIMEMultipart("alternative")
        if text_body:
            body_part.attach(MIMEText(text_body, "plain", "utf-8"))
        body_part.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(body_part)

        if attachments:
            for att in attachments:
                fname = att.get("filename", "attachment.bin")
                content = att.get("content", b"")
                part = MIMEBase("application", "octet-stream")
                part.set_payload(content)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
                msg.attach(part)

        try:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=12) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(cfg["username"], cfg["password"])
                server.sendmail(cfg["username"], [target_to], msg.as_string())

            logger.info(f"Outlook notification sent successfully to {target_to}")
            return True, "SENT", {
                "provider": "OUTLOOK",
                "status": "SENT",
                "recipient": target_to,
                "message": "Outlook notification dispatched successfully via Office365 TLS.",
                "timestamp": timestamp
            }
        except smtplib.SMTPAuthenticationError as e:
            err_msg = "Outlook SMTP authentication failed. Check OUTLOOK_APP_PASSWORD credential in .streamlit/secrets.toml."
            logger.error(f"Outlook auth error: {e}")
            return False, "FAILED", {
                "provider": "OUTLOOK",
                "status": "FAILED",
                "recipient": target_to,
                "message": err_msg,
                "error": str(e),
                "timestamp": timestamp
            }
        except Exception as e:
            err_msg = f"Outlook delivery failed: {str(e)[:200]}"
            logger.error(f"Outlook send error: {e}")
            return False, "FAILED", {
                "provider": "OUTLOOK",
                "status": "FAILED",
                "recipient": target_to,
                "message": err_msg,
                "error": str(e),
                "timestamp": timestamp
            }
