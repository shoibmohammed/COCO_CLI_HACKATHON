#!/usr/bin/env python3
"""
scripts/diagnose_automatic_notification.py
Diagnostic tool for the automatic notification pipeline.
Reports the state of critical alerts, notifications, and channels.

Usage (from Snowpark session):
    python scripts/diagnose_automatic_notification.py --machine-id Machine_03
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def diagnose(session, machine_id: str):
    print(f"{'='*60}")
    print(f"AUTOMATIC NOTIFICATION DIAGNOSTICS")
    print(f"{'='*60}")
    print(f"MACHINE: {machine_id}")
    print()

    from config import table, DATABASE, SCHEMA
    # Current risk
    try:
        rows = session.sql(f"""
            SELECT MACHINE_ID, UNIFIED_RISK_SCORE, FAILURE_CLASS, TOP_REASON
            FROM {DATABASE}.{SCHEMA}.MACHINE_RISK_UNIFIED
            WHERE MACHINE_ID = ? LIMIT 1
        """, params=[machine_id]).collect()
        if rows:
            r = rows[0]
            risk = float(r.get("UNIFIED_RISK_SCORE", 0))
            print(f"CURRENT RISK:          {risk*100:.0f}%")
            print(f"FAILURE CLASS:         {r.get('FAILURE_CLASS', 'N/A')}")
            print(f"TOP REASON:            {r.get('TOP_REASON', 'N/A')}")
            print(f"CRITICAL (>=75%):      {'YES' if risk >= 0.75 else 'NO'}")
        else:
            print(f"CURRENT RISK:          NOT FOUND in MACHINE_RISK_UNIFIED")
    except Exception as e:
        print(f"RISK QUERY ERROR:      {str(e)[:100]}")
    print()

    # Recent alerts
    try:
        alert_tbl = table("ALERT_LOG")
        alerts = session.sql(f"""
            SELECT SEVERITY, RISK_SCORE, ALERT_REASON, CREATED_AT
            FROM {alert_tbl}
            WHERE MACHINE_ID = ?
            ORDER BY CREATED_AT DESC LIMIT 3
        """, params=[machine_id]).collect()
        print(f"RECENT ALERTS:         {len(alerts)} found")
        for a in alerts:
            print(f"  {a.get('SEVERITY')} | {a.get('RISK_SCORE')} | {str(a.get('CREATED_AT',''))[:19]}")
    except Exception as e:
        print(f"ALERT QUERY ERROR:     {str(e)[:100]}")
    print()

    # Notification audit
    try:
        audit_tbl = table("NOTIFICATION_AUDIT")
        notifs = session.sql(f"""
            SELECT EVENT_ID, NOTIFICATION_TYPE, PROVIDER, STATUS, CREATED_AT
            FROM {audit_tbl}
            WHERE MACHINE_ID = ?
            ORDER BY CREATED_AT DESC LIMIT 5
        """, params=[machine_id]).collect()
        print(f"NOTIFICATION AUDIT:    {len(notifs)} records")
        for n in notifs:
            evid = str(n.get("EVENT_ID", ""))[:30]
            print(f"  {n.get('PROVIDER')} | {n.get('STATUS')} | {evid} | {str(n.get('CREATED_AT',''))[:19]}")
        if not notifs:
            print("  (none — no notifications dispatched for this machine)")
    except Exception as e:
        print(f"AUDIT QUERY ERROR:     {str(e)[:100]}")
    print()

    # Automatic trigger check
    try:
        audit_tbl = table("NOTIFICATION_AUDIT")
        auto_notifs = session.sql(f"""
            SELECT COUNT(*) AS CNT FROM {audit_tbl}
            WHERE MACHINE_ID = ? AND EVENT_ID LIKE 'AUTO-%'
        """, params=[machine_id]).collect()
        cnt = auto_notifs[0]["CNT"] if auto_notifs else 0
        print(f"AUTOMATIC EVENTS:      {cnt}")
    except Exception:
        print(f"AUTOMATIC EVENTS:      ERROR")

    # Snowflake Alert status
    try:
        alerts_obj = session.sql("SHOW ALERTS LIKE 'HIGH_RISK_MACHINE_ALERT' IN SCHEMA PM_OEE_DB.CORE").collect()
        if alerts_obj:
            state = alerts_obj[0].get("state", alerts_obj[0].get("STATE", "UNKNOWN"))
            print(f"SF ALERT OBJECT:       {state}")
        else:
            print(f"SF ALERT OBJECT:       NOT FOUND")
    except Exception:
        print(f"SF ALERT OBJECT:       ERROR/NOT AUTHORIZED")
    print()

    print(f"{'='*60}")
    print(f"TRIGGER MECHANISM:")
    print(f"  1. generate_alerts() in ml_service.py")
    print(f"     → inserts CRITICAL alerts into ALERT_LOG")
    print(f"     → calls _dispatch_automatic_notifications()")
    print(f"     → dispatches Email + Slack via dual-channel")
    print(f"  2. Snowflake ALERT: HIGH_RISK_MACHINE_ALERT (5 min)")
    print(f"     → inserts into ALERT_LOG only (no notification)")
    print(f"  Streamlit RUN FRESH TRIAGE button triggers (1)")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine-id", required=True)
    args = parser.parse_args()

    try:
        from snowflake.snowpark.context import get_active_session
        session = get_active_session()
    except Exception:
        print("ERROR: No active Snowpark session.")
        sys.exit(1)

    diagnose(session, args.machine_id)
