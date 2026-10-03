---
name: mfg-maintenance-notify
description: >
  Send multi-channel notifications (Snowflake Email + Slack) for critical
  maintenance alerts and newly created work orders. Deduplicates against
  ALERT_NOTIFICATION_LOG. Use when: user asks to notify the team, send alerts,
  push Slack notifications, email maintenance, or process pending notifications.
version: "1.0.0"
---

# MFG Maintenance Notification Skill

Sends email and Slack notifications for critical alerts and work orders.

## What this skill does

1. **Scan for Unnotified Alerts** — Queries `ALERT_LOG` for critical alerts
   from the last hour that are not yet in `ALERT_NOTIFICATION_LOG`.
2. **Send Email** — Calls `SYSTEM$SEND_EMAIL('MFG_EMAIL_NOTIFICATION', ...)`
   with alert details (machine ID, risk score, diagnosis).
3. **Send Slack** — Calls `SYSTEM$SEND_SNOWFLAKE_NOTIFICATION('MFG_SLACK_NOTIFICATION', ...)`
   with a formatted alert message.
4. **Audit** — Records each notification attempt (success/failure per channel)
   in `ALERT_NOTIFICATION_LOG` and `NOTIFICATION_AUDIT` with
   `TRIGGER_TYPE = 'AUTOMATIC'`.

## SQL to execute

```sql
-- Process all pending notifications
CALL PM_OEE_DB.CORE.PROCESS_AUTOMATIC_NOTIFICATIONS();

-- Check notification audit trail
SELECT EVENT_ID, MACHINE_ID, PROVIDER, STATUS, TRIGGER_TYPE, CREATED_AT
FROM PM_OEE_DB.CORE.NOTIFICATION_AUDIT
WHERE TRIGGER_TYPE = 'AUTOMATIC'
ORDER BY CREATED_AT DESC
LIMIT 20;
```

## Prerequisites

These notification integrations must exist in the account:
- `MFG_EMAIL_NOTIFICATION` — Snowflake email integration (`sql/11_notification_integration.sql`)
- `MFG_SLACK_NOTIFICATION` — Snowflake webhook integration for Slack

If either is not configured, the skill logs the failure and continues with the
other channel.

## When to use

- "Notify the maintenance team"
- "Send alerts for critical machines"
- "Push Slack notifications"
- "Email the maintenance crew"
- "Process pending notifications"
- "Did the team get notified?"

## Output

Returns the count of notifications processed. Each notification is recorded in
the audit log with per-channel status (SENT / FAILED / NOT_CONFIGURED).

## Upstream

- **Upstream**: Triggered after **work-order-drafting** creates new work orders
  and alerts, or independently when new critical alerts appear in `ALERT_LOG`.
