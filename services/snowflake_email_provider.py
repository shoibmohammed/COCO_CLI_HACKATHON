# Snowflake native email provider using SYSTEM$SEND_EMAIL and MFG_EMAIL_NOTIFICATION integration
# Co-authored with CoCo
"""
services/snowflake_email_provider.py
Snowflake-native email provider for MFG Predictive Maintenance.
Uses SYSTEM$SEND_EMAIL with the MFG_EMAIL_NOTIFICATION integration.
This is the default and verified provider for the Trial account.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

INTEGRATION_NAME = "MFG_EMAIL_NOTIFICATION"
DEFAULT_RECIPIENT = "Pragati.Jaju@merkle.com"


class SnowflakeEmailProvider:
    """
    Sends emails via Snowflake's native SYSTEM$SEND_EMAIL.
    Requires MFG_EMAIL_NOTIFICATION notification integration.
    Recipients must be account-verified email addresses.
    """

    def __init__(self):
        self.integration = INTEGRATION_NAME
        self.provider_name = "SNOWFLAKE_EMAIL"

    def get_status(self) -> Dict[str, Any]:
        """Returns provider readiness status."""
        return {
            "provider": self.provider_name,
            "integration": self.integration,
            "status": "READY",
            "label": "Snowflake Email",
            "description": "Native Snowflake email via SYSTEM$SEND_EMAIL",
            "requires_eai": False,
        }

    def send_email(
        self,
        session,
        recipient: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Sends an email via SYSTEM$SEND_EMAIL.

        Args:
            session: Snowflake Snowpark session
            recipient: Email address (must be account-verified)
            subject: Email subject line
            body: Plain text body (used by SYSTEM$SEND_EMAIL)
            html_body: Ignored — SYSTEM$SEND_EMAIL uses plain text only

        Returns:
            Tuple of (success: bool, status: str, details: dict)
        """
        if not session:
            return False, "NO_SESSION", {
                "message": "No Snowflake session available",
                "provider": self.provider_name,
            }

        if not recipient:
            return False, "NO_RECIPIENT", {
                "message": "No recipient configured. Enter a verified Snowflake recipient email.",
                "provider": self.provider_name,
            }

        # Execute parameterized call to SYSTEM$SEND_EMAIL
        try:
            result = session.sql(
                "CALL SYSTEM$SEND_EMAIL(?, ?, ?, ?)",
                params=[self.integration, recipient.strip(), subject.strip(), body.strip()]
            ).collect()
            return_val = str(result[0][0]) if result else ""
            timestamp = datetime.utcnow().isoformat() + "Z"

            # SYSTEM$SEND_EMAIL succeeds if no exception is thrown.
            # It may return an empty string, "Email sent", or similar confirmation.
            return True, "SENT", {
                "provider": self.provider_name,
                "integration": self.integration,
                "recipient": recipient,
                "subject": subject,
                "timestamp": timestamp,
                "message": "Email dispatched via Snowflake SYSTEM$SEND_EMAIL",
                "system_send_email_result": return_val,
            }

        except Exception as e:
            error_msg = str(e)[:500]
            return False, "ERROR", {
                "provider": self.provider_name,
                "recipient": recipient,
                "message": f"SYSTEM$SEND_EMAIL failed: {error_msg}",
                "error": error_msg,
            }

    def send_critical_alert(
        self,
        session,
        recipient: str,
        machine_id: str,
        alert_payload: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Sends a formatted critical maintenance alert."""
        vib = float(alert_payload.get("vibration_mm_s", 0))
        temp = float(alert_payload.get("temperature_c", 0))
        rpm = float(alert_payload.get("rpm", 0))
        risk = float(alert_payload.get("risk_score", 0))
        ml_prob = float(alert_payload.get("ml_failure_probability", 0))
        rul = float(alert_payload.get("rul_hours", 0))
        part = alert_payload.get("recommended_part", "N/A")
        action = alert_payload.get("recommended_action", "Inspect machine immediately.")

        subject = f"CRITICAL ALERT — {machine_id} Failure Imminent"
        body = (
            f"MFG PREDICTIVE MAINTENANCE — CRITICAL ALERT\n"
            f"{'=' * 50}\n\n"
            f"Machine: {machine_id}\n"
            f"Severity: CRITICAL\n\n"
            f"CURRENT READINGS:\n"
            f"  Vibration: {vib:.2f} mm/s\n"
            f"  Temperature: {temp:.1f} C\n"
            f"  RPM: {rpm:.0f}\n\n"
            f"PREDICTIVE INTELLIGENCE:\n"
            f"  Statistical Risk: {risk*100:.0f}%\n"
            f"  ML Failure Probability: {ml_prob*100:.1f}%\n"
            f"  Estimated RUL: {rul:.1f} hours\n\n"
            f"RECOMMENDED ACTION:\n"
            f"  {action}\n"
            f"  Required Part: {part}\n\n"
            f"{'=' * 50}\n"
            f"MFG Predictive Maintenance & OEE Command Center\n"
        )

        return self.send_email(session, recipient, subject, body)

    def send_incident_report(
        self,
        session,
        recipient: str,
        machine_id: str,
        report_summary: str,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Sends an incident report summary."""
        subject = f"Incident Report — {machine_id}"
        body = (
            f"MFG PREDICTIVE MAINTENANCE — INCIDENT REPORT\n"
            f"{'=' * 50}\n\n"
            f"Machine: {machine_id}\n\n"
            f"{report_summary}\n\n"
            f"{'=' * 50}\n"
            f"MFG Predictive Maintenance & OEE Command Center\n"
        )

        return self.send_email(session, recipient, subject, body)
