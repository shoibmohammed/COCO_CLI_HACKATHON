---
name: mfg-work-order-drafting
description: >
  Draft governed maintenance work orders for machines detected as anomalous.
  Calls AGENTIC_REMEDIATION to diagnose the failure mode, check spare parts
  inventory, and create a PENDING_APPROVAL work order. Use when: user asks to
  create a work order, remediate a machine, draft maintenance, or respond to
  an anomaly.
version: "1.0.0"
---

# MFG Work Order Drafting Skill

Creates governed maintenance work orders through the agentic remediation pipeline.

## What this skill does

1. **Diagnose** — Analyzes live telemetry (vibration, temperature, RPM) against
   known failure signatures to determine the root cause:
   - High vibration + high temp → Bearing degradation
   - High temp only → Coolant/thermal overload
   - Low RPM or high vibration → Drive belt degradation
   - Other → Multi-sensor anomaly requiring inspection
2. **Check Inventory** — Queries `SPARE_PARTS` for the recommended part's
   on-hand quantity.
3. **Create Work Order** — Inserts into `WORK_ORDERS` with status
   `PENDING_APPROVAL`, priority (P1/P2/P3 based on risk), diagnosis,
   recommended action, required parts, and estimated downtime.
4. **Log Alert** — Records the event in `ALERT_LOG` with severity and the
   linked work order ID.

## SQL to execute

For a specific machine:
```sql
CALL PM_OEE_DB.CORE.AGENTIC_REMEDIATION('Machine_03');
```

For all critical machines (batch):
```sql
CALL PM_OEE_DB.CORE.AUTO_DRAFT_WORK_ORDERS();
```

To check the result:
```sql
SELECT work_order_id, machine_id, priority, status, diagnosis,
       recommended_action, parts_required, risk_score, rul_hours
FROM PM_OEE_DB.CORE.WORK_ORDERS
WHERE status = 'PENDING_APPROVAL'
ORDER BY created_at DESC;
```

## When to use

- "Create a work order for Machine_03"
- "Remediate the critical machines"
- "Draft maintenance orders"
- "What should we do about the anomalies?"
- "Auto-create work orders for at-risk machines"

## Output

Returns a JSON object per work order containing: work_order_id, machine_id,
priority, diagnosis, recommended_action, required part, inventory on hand,
and estimated RUL in hours. Work orders are always created as
`PENDING_APPROVAL` — human approval is required before any external ticket
(e.g. Jira) is created.

## Upstream / Downstream

- **Upstream**: Receives critical machine IDs from **anomaly-detection** skill.
- **Downstream**: Once work orders exist, **maintenance-notify** sends
  email + Slack notifications to the maintenance team.
