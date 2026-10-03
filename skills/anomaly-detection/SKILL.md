---
name: mfg-anomaly-detection
description: >
  Detect machine anomalies by refreshing Dynamic Tables, running Cortex ML
  inference, and scanning MACHINE_RISK_UNIFIED for machines above the risk
  threshold. Logs new critical alerts to ALERT_LOG. Use when: user asks to
  scan for anomalies, check machine health, detect failures, run anomaly
  detection, or refresh risk scores.
version: "1.0.0"
---

# MFG Anomaly Detection Skill

Refreshes the ML pipeline and identifies machines at risk of imminent failure.

## What this skill does

1. **Refresh Dynamic Tables** — Triggers `ALTER DYNAMIC TABLE ... REFRESH` on
   `MACHINE_HEALTH_RT`, `RISK_SCORES_RT`, and `OEE_METRICS_RT` to pull the
   latest sensor readings.
2. **Run ML Inference** — Calls `REFRESH_ML_RISK()` to score all machines
   against the trained `PM_FAILURE_MODEL` classification model.
3. **Scan for Anomalies** — Queries `MACHINE_RISK_UNIFIED` for machines where
   `unified_risk_score >= 0.65` (configurable threshold).
4. **Log Alerts** — Inserts new alerts into `ALERT_LOG` for any critical or
   warning-level machines not already alerted in the last hour.

## SQL to execute

```sql
-- Step 1: Refresh dynamic tables
ALTER DYNAMIC TABLE PM_OEE_DB.CORE.MACHINE_HEALTH_RT REFRESH;
ALTER DYNAMIC TABLE PM_OEE_DB.CORE.RISK_SCORES_RT REFRESH;
ALTER DYNAMIC TABLE PM_OEE_DB.CORE.OEE_METRICS_RT REFRESH;

-- Step 2: Run ML inference
CALL PM_OEE_DB.CORE.REFRESH_ML_RISK();

-- Step 3: Scan for anomalies and return results
SELECT
  machine_id,
  ROUND(unified_risk_score, 3) AS risk_score,
  ROUND(statistical_risk_score, 3) AS stat_risk,
  ROUND(ml_failure_probability, 3) AS ml_risk,
  failure_class,
  top_reason,
  vibration_mm_s,
  temperature_c,
  rpm
FROM PM_OEE_DB.CORE.MACHINE_RISK_UNIFIED
WHERE unified_risk_score >= 0.65
ORDER BY unified_risk_score DESC;
```

## When to use

- "Scan for anomalies"
- "Check machine health"
- "Are any machines at risk?"
- "Run anomaly detection"
- "Refresh risk scores"
- "Which machines need attention?"

## Output

Returns a table of machines above the risk threshold with their risk scores,
failure class, top contributing factor, and current telemetry readings. If no
machines are above threshold, reports that the fleet is healthy.

## Downstream

Pass critical machines to the **work-order-drafting** skill to create governed
maintenance work orders.
