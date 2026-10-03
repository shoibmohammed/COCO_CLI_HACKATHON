# services/notification_templates.py
# Centralized Notification Template Registry for Email & Slack Dispatches
# Co-authored with CoCo
"""
services/notification_templates.py
Provides a centralized registry of safe, structured notification templates
for CRITICAL_ALERT, WORK_ORDER_CREATED, WORK_ORDER_APPROVED, JIRA_TICKET_CREATED, and INCIDENT_REPORT.
Templates contain NO passwords, API tokens, webhooks, or sensitive keys.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

TEMPLATES: Dict[str, Dict[str, str]] = {
    "CRITICAL_ALERT": {
        "subject": "🚨 [CRITICAL ALERT] Anomaly Detected on {machine_id} (Risk: {risk_percent}%)",
        "email_body": """
====================================================================
MFG COMMAND CENTER — CRITICAL EQUIPMENT ALERT
====================================================================

Target Machine:       {machine_id}
Failure Probability:  {risk_percent}%
Est. Remaining Life:  {rul_hours} Hours
Detection Timestamp:  {timestamp}

DIAGNOSIS & ROOT CAUSE:
{root_cause}

RECOMMENDED ACTION:
{recommended_action}

====================================================================
This is an automated notification dispatched via Snowflake Command Center.
""",
        "slack_body": "🚨 *CRITICAL ALERT* | *Machine:* `{machine_id}` | *Risk:* `{risk_percent}%` | *RUL:* `{rul_hours}h`\n> *Diagnosis:* {root_cause}\n> *Action:* {recommended_action}"
    },

    "WORK_ORDER_CREATED": {
        "subject": "📋 [WORK ORDER CREATED] {work_order_id} Pending Approval for {machine_id}",
        "email_body": """
====================================================================
MFG COMMAND CENTER — WORK ORDER DRAFTED
====================================================================

Work Order ID:  {work_order_id}
Machine ID:     {machine_id}
Status:         PENDING_APPROVAL
Priority:       HIGH

RECOMMENDED ACTION:
{recommended_action}

REQUIRED PARTS:
{parts_required}

ESTIMATED DOWNTIME:
{estimated_downtime_hours} Hours

Please log into Streamlit Command Center to approve or reject this request.
""",
        "slack_body": "📋 *WORK ORDER CREATED* | `{work_order_id}` for `{machine_id}` | *Status:* 🟡 PENDING_APPROVAL\n> *Action:* {recommended_action}\n> *Parts:* {parts_required}"
    },

    "WORK_ORDER_APPROVED": {
        "subject": "✅ [WORK ORDER APPROVED] {work_order_id} Approved by Manager",
        "email_body": """
====================================================================
MFG COMMAND CENTER — WORK ORDER APPROVED
====================================================================

Work Order ID:  {work_order_id}
Machine ID:     {machine_id}
Approver:       {approver}
Approval Time:  {timestamp}

Status:         APPROVED (Ready for Jira Cloud Ticketing)

RECOMMENDED ACTION:
{recommended_action}

PARTS ALLOCATED:
{parts_required}
""",
        "slack_body": "✅ *WORK ORDER APPROVED* | `{work_order_id}` (`{machine_id}`) | *Approver:* {approver}\n> Ready for Jira Ticket Creation & Maintenance Execution."
    },

    "JIRA_TICKET_CREATED": {
        "subject": "🎫 [JIRA TICKET CREATED] {jira_issue_key} for Work Order {work_order_id}",
        "email_body": """
====================================================================
MFG COMMAND CENTER — JIRA CLOUD TICKET GENERATED
====================================================================

Jira Ticket Key:  {jira_issue_key}
Work Order ID:    {work_order_id}
Machine ID:       {machine_id}
Jira Ticket URL:  {jira_url}

EXECUTION MODE:
{execution_mode}

SUMMARY:
Maintenance issue created for {machine_id}. Open Jira ticket to track resolution status.
""",
        "slack_body": "🎫 *JIRA TICKET CREATED* | Ticket: *{jira_issue_key}* | Work Order: `{work_order_id}`\n> *Jira URL:* {jira_url}"
    },

    "INCIDENT_REPORT": {
        "subject": "📄 [INCIDENT REPORT] Maintenance Summary for {machine_id}",
        "email_body": """
====================================================================
MFG COMMAND CENTER — INCIDENT SUMMARY REPORT
====================================================================

Machine ID:     {machine_id}
Report Date:    {timestamp}
Risk Level:     {risk_level}

SUMMARY FINDINGS:
{summary}

ACTION ITEMS:
{action_items}

====================================================================
Report generated from Snowflake Predictive Maintenance Command Center.
""",
        "slack_body": "📄 *INCIDENT REPORT* | *Machine:* `{machine_id}` | *Risk Level:* `{risk_level}`\n> *Summary:* {summary}"
    }
}


def get_notification_template(template_name: str) -> Optional[Dict[str, str]]:
    """Retrieves a template definition by name."""
    return TEMPLATES.get(template_name.upper())


def render_notification_template(template_name: str, context: Dict[str, Any]) -> Dict[str, str]:
    """
    Renders subject, email_body, and slack_body for the given template_name using context parameters.
    Returns a dictionary with keys 'subject', 'email_body', and 'slack_body'.
    Fallback strings are supplied for missing parameters.
    """
    tmpl = get_notification_template(template_name)
    if not tmpl:
        logger.warning(f"Template '{template_name}' not found. Using generic fallback.")
        tmpl = {
            "subject": f"Notification: {template_name}",
            "email_body": "Notification payload for {machine_id}.\nContext: {context_str}",
            "slack_body": "Notification `{template_name}` payload for `{machine_id}`."
        }

    # Prepare safe context formatting
    safe_ctx = {
        "machine_id": context.get("machine_id", "N/A"),
        "risk_percent": f"{float(context.get('risk_score', context.get('risk', 0.0))) * 100:.1f}" if isinstance(context.get('risk_score', context.get('risk')), (int, float)) else str(context.get("risk_percent", "N/A")),
        "rul_hours": str(context.get("rul_hours", context.get("rul", "N/A"))),
        "root_cause": str(context.get("root_cause", context.get("diagnosis", "Inspection required."))),
        "recommended_action": str(context.get("recommended_action", context.get("approved_action", "Proceed with standard SOP protocol."))),
        "work_order_id": str(context.get("work_order_id", "N/A")),
        "parts_required": str(context.get("parts_required", context.get("recommended_part", "Standard Spare Parts"))),
        "estimated_downtime_hours": str(context.get("estimated_downtime_hours", "2.0")),
        "approver": str(context.get("approver", "Human Plant Manager")),
        "jira_issue_key": str(context.get("jira_issue_key", "KAN-101")),
        "jira_url": str(context.get("jira_url", "https://jira.atlassian.net")),
        "execution_mode": str(context.get("execution_mode", "ATLASSIAN_MCP")),
        "risk_level": str(context.get("risk_level", "HIGH")),
        "summary": str(context.get("summary", "Telemetry breach detected.")),
        "action_items": str(context.get("action_items", "Schedule repair window.")),
        "timestamp": str(context.get("timestamp", "2026-08-25")),
        "context_str": str(context)
    }

    try:
        subject = tmpl["subject"].format(**safe_ctx)
    except Exception as e:
        logger.debug(f"Subject format error: {e}")
        subject = f"Notification: {template_name} ({safe_ctx['machine_id']})"

    try:
        email_body = tmpl["email_body"].format(**safe_ctx)
    except Exception as e:
        logger.debug(f"Email body format error: {e}")
        email_body = f"Notification body for {template_name}."

    try:
        slack_body = tmpl["slack_body"].format(**safe_ctx)
    except Exception as e:
        logger.debug(f"Slack body format error: {e}")
        slack_body = f"Notification for {template_name} on {safe_ctx['machine_id']}."

    return {
        "subject": subject,
        "email_body": email_body,
        "slack_body": slack_body
    }
