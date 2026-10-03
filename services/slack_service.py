# Snowflake-native Slack notification provider using SYSTEM$SEND_SNOWFLAKE_NOTIFICATION
# Co-authored with CoCo
"""
services/slack_service.py
Snowflake-native Slack notification provider for MFG Predictive Maintenance.
Uses SYSTEM$SEND_SNOWFLAKE_NOTIFICATION with the MFG_SLACK_NOTIFICATION webhook integration.
No external HTTP calls or EAI required.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

INTEGRATION_NAME = "MFG_SLACK_NOTIFICATION"
SECRET_NAME = "PM_OEE_DB.CORE.SLACK_WEBHOOK_SECRET"


def check_slack_configuration(session) -> Dict[str, Any]:
    """Verifies the Slack webhook notification integration exists and is enabled."""
    if not session:
        return {"configured": False, "status": "NO_SESSION", "message": "No Snowflake session"}
    try:
        rows = session.sql(
            f"SHOW NOTIFICATION INTEGRATIONS LIKE '{INTEGRATION_NAME}'"
        ).collect()
        if rows:
            enabled = rows[0]["enabled"] if "enabled" in rows[0].asDict() else str(rows[0]["ENABLED"])
            return {
                "configured": True,
                "status": "READY" if str(enabled).upper() == "TRUE" else "DISABLED",
                "integration": INTEGRATION_NAME,
                "message": "Slack webhook integration active" if str(enabled).upper() == "TRUE" else "Integration disabled",
            }
        return {"configured": False, "status": "NOT_FOUND", "message": f"Integration {INTEGRATION_NAME} not found"}
    except Exception as e:
        return {"configured": False, "status": "ERROR", "message": str(e)[:150]}


def format_critical_alert(payload: Dict[str, Any]) -> str:
    """Formats a critical maintenance alert for Slack."""
    machine_id = payload.get("machine_id", "Unknown")
    priority = payload.get("priority", "P1")
    vib = float(payload.get("vibration_mm_s", 0))
    temp = float(payload.get("temperature_c", 0))
    rpm = float(payload.get("rpm", 0))
    risk = float(payload.get("risk_score", payload.get("failure_probability", 0)))
    ml_prob = float(payload.get("ml_failure_probability", 0))
    rul = float(payload.get("rul_hours", 0))
    diagnosis = payload.get("diagnosis", payload.get("root_cause", "Pending diagnosis"))
    action = payload.get("recommended_action", "Inspect equipment immediately")
    part = payload.get("recommended_part", "N/A")
    wo_id = payload.get("work_order_id", "N/A")
    timestamp = payload.get("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))

    return (
        f"🚨 CRITICAL MAINTENANCE ALERT\n\n"
        f"Machine: {machine_id}\n"
        f"Priority: {priority}\n\n"
        f"Vibration: {vib:.2f} mm/s\n"
        f"Temperature: {temp:.1f} °C\n"
        f"RPM: {rpm:.0f}\n\n"
        f"Statistical Risk: {risk*100:.0f}%\n"
        f"ML Failure Probability: {ml_prob*100:.2f}%\n\n"
        f"Diagnosis: {diagnosis}\n\n"
        f"Recommended Action: {action}\n"
        f"Required Part: {part}\n"
        f"Work Order: {wo_id}\n"
        f"Status: PENDING_APPROVAL\n\n"
        f"Timestamp: {timestamp}"
    )


def format_work_order_created(payload: Dict[str, Any]) -> str:
    """Formats a work order creation notification for Slack."""
    wo_id = payload.get("work_order_id", "N/A")
    machine_id = payload.get("machine_id", "Unknown")
    priority = payload.get("priority", "P1")
    action = payload.get("recommended_action", "")
    part = payload.get("recommended_part", "N/A")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    return (
        f"🛠️ WORK ORDER CREATED\n\n"
        f"Work Order: {wo_id}\n"
        f"Machine: {machine_id}\n"
        f"Priority: {priority}\n"
        f"Status: PENDING_APPROVAL\n\n"
        f"Action: {action}\n"
        f"Required Part: {part}\n\n"
        f"Awaiting manager approval.\n"
        f"Timestamp: {timestamp}"
    )


def format_work_order_approved(payload: Dict[str, Any]) -> str:
    """Formats a work order approval notification for Slack."""
    wo_id = payload.get("work_order_id", "N/A")
    machine_id = payload.get("machine_id", "Unknown")
    approver = payload.get("approver", "Plant Manager")
    action = payload.get("approved_action", payload.get("recommended_action", ""))
    part = payload.get("recommended_part", "N/A")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return (
        f"✅ WORK ORDER APPROVED\n\n"
        f"Work Order: {wo_id}\n"
        f"Machine: {machine_id}\n"
        f"Approved By: {approver}\n"
        f"Status: APPROVED\n\n"
        f"Action: {action}\n"
        f"Required Part: {part}\n\n"
        f"Maintenance team dispatched.\n"
        f"Timestamp: {timestamp}"
    )


def send_slack_notification(session, message: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Sends a Slack notification via Snowflake's native SYSTEM$SEND_SNOWFLAKE_NOTIFICATION.
    Returns (success, status_label, details_dict).
    """
    if not session:
        return False, "NO_SESSION", {"message": "No Snowflake session available"}

    try:
        # Escape for JSON inside SQL string literal.
        # The webhook template is {"text": "SNOWFLAKE_WEBHOOK_MESSAGE"}.
        # We need valid JSON inside a SQL string, so:
        #   backslash → \\, quote → \", newline → \n (JSON escape), then ' → '' for SQL.
        msg_escaped = (
            message
            .replace("\\", "\\\\")    # backslash → double backslash (JSON)
            .replace('"', '\\"')      # double quote → escaped quote (JSON)
            .replace("\n", "\\n")     # newline → \n literal (JSON newline escape)
            .replace("\r", "\\r")     # CR → \r literal
            .replace("\t", "\\t")     # tab → \t literal
            .replace("'", "''")       # SQL single-quote escaping
        )
        result = session.sql(f"""
            CALL SYSTEM$SEND_SNOWFLAKE_NOTIFICATION(
                SNOWFLAKE.NOTIFICATION.TEXT_PLAIN('{msg_escaped}'),
                SNOWFLAKE.NOTIFICATION.INTEGRATION('{INTEGRATION_NAME}')
            )
        """).collect()

        response = str(result[0][0]) if result else "Unknown"
        if "enqueued" in response.lower() or "notification" in response.lower():
            return True, "SENT", {
                "message": "Slack notification enqueued",
                "response": response,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
        else:
            return False, "UNEXPECTED_RESPONSE", {
                "message": f"Unexpected response: {response}",
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
    except Exception as e:
        error_msg = str(e)[:200]
        logger.error(f"Slack notification failed: {error_msg}")
        return False, "FAILED", {
            "message": error_msg,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
