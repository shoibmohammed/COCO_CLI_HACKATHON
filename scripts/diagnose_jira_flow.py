#!/usr/bin/env python3
"""
scripts/diagnose_jira_flow.py
Safe diagnostic tool for the one-button Jira creation flow.
Reads Snowflake state without modifying anything. No credentials printed.

Usage:
    Run from Streamlit/Snowpark context or with Snowflake connection:
    python scripts/diagnose_jira_flow.py --work-order WO-B3E93984
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def diagnose(session, work_order_display: str):
    """Run diagnostics against Snowflake for the given work order."""
    wo_prefix = work_order_display.replace("WO-", "")

    print(f"{'='*60}")
    print(f"JIRA FLOW DIAGNOSTICS")
    print(f"{'='*60}")
    print(f"WORK ORDER (display):  {work_order_display}")

    from config import table
    wo_tbl = table("WORK_ORDERS")
    q_tbl = table("JIRA_INTEGRATION_QUEUE")

    # 1. Resolve actual DB ID
    rows = session.sql(f"""
        SELECT WORK_ORDER_ID, STATUS, EXTERNAL_TICKET_ID
        FROM {wo_tbl}
        WHERE WORK_ORDER_ID = ? OR WORK_ORDER_ID LIKE ?
        ORDER BY CREATED_AT DESC LIMIT 1
    """, params=[wo_prefix, f"{wo_prefix}%"]).collect()

    if not rows:
        print(f"ACTUAL DATABASE ID:    NOT FOUND")
        print(f"WORK ORDER STATUS:     N/A")
        print(f"NEXT ACTION:           Create a work order first")
        return

    row = rows[0]
    actual_id = row["WORK_ORDER_ID"]
    wo_status = row["STATUS"]
    ext_ticket = row.get("EXTERNAL_TICKET_ID")

    print(f"ACTUAL DATABASE ID:    {actual_id}")
    print(f"WORK ORDER STATUS:     {wo_status}")
    if ext_ticket:
        print(f"EXTERNAL TICKET:       {ext_ticket}")
    print()

    # 2. Queue status
    queue_rows = session.sql(f"""
        SELECT QUEUE_ID, STATUS, ATTEMPT_COUNT, JIRA_ISSUE_KEY, JIRA_URL, ERROR_MESSAGE, CREATED_AT, UPDATED_AT
        FROM {q_tbl}
        WHERE WORK_ORDER_ID = ?
        ORDER BY CREATED_AT DESC LIMIT 1
    """, params=[work_order_display]).collect()

    if not queue_rows:
        print(f"QUEUE:                 NONE (no queue record)")
        print(f"JIRA ISSUE:            NONE")
    else:
        qr = queue_rows[0]
        print(f"QUEUE ID:              {qr['QUEUE_ID']}")
        print(f"QUEUE STATUS:          {qr['STATUS']}")
        print(f"ATTEMPT COUNT:         {qr['ATTEMPT_COUNT']}")
        jira_key = qr.get("JIRA_ISSUE_KEY") or "NONE"
        jira_url = qr.get("JIRA_URL") or "NONE"
        print(f"JIRA ISSUE:            {jira_key}")
        if jira_key != "NONE":
            print(f"JIRA URL:              {jira_url}")
        err = qr.get("ERROR_MESSAGE")
        if err:
            print(f"LAST ERROR:            {str(err)[:200]}")
    print()

    # 3. Worker health
    try:
        hb_rows = session.sql("""
            SELECT STATUS, LAST_HEARTBEAT, VERSION,
                   DATEDIFF('second', LAST_HEARTBEAT, CURRENT_TIMESTAMP()) AS AGE_SECONDS
            FROM PM_OEE_DB.CORE.JIRA_WORKER_HEARTBEAT
            WHERE WORKER_ID = 'LOCAL_JIRA_WORKER_01' LIMIT 1
        """).collect()
        if hb_rows:
            hb = hb_rows[0]
            age = hb["AGE_SECONDS"]
            status = "ONLINE" if hb["STATUS"] == "ONLINE" and age <= 300 else "OFFLINE"
            print(f"WORKER:                {status}")
            print(f"LAST HEARTBEAT:        {hb['LAST_HEARTBEAT']} ({age}s ago)")
            print(f"VERSION:               {hb['VERSION']}")
        else:
            print(f"WORKER:                OFFLINE (no heartbeat record)")
    except Exception as e:
        print(f"WORKER:                UNKNOWN (heartbeat table error)")
    print()

    # 4. Recommendation
    print(f"{'='*60}")
    if ext_ticket:
        print(f"NEXT ACTION:           Done — Jira ticket {ext_ticket} exists")
    elif queue_rows and queue_rows[0]["STATUS"] == "SUCCESS":
        print(f"NEXT ACTION:           Done — refresh Streamlit UI")
    elif queue_rows and queue_rows[0]["STATUS"] == "PENDING":
        print(f"NEXT ACTION:           Start Local Jira Worker to process queue")
    elif queue_rows and queue_rows[0]["STATUS"] == "PROCESSING":
        print(f"NEXT ACTION:           Wait for worker to complete Jira call")
    elif queue_rows and queue_rows[0]["STATUS"] == "FAILED":
        print(f"NEXT ACTION:           Click RETRY or investigate error above")
    elif wo_status != "APPROVED":
        print(f"NEXT ACTION:           Approve the work order first")
    else:
        print(f"NEXT ACTION:           Click CREATE JIRA TICKET in Streamlit")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnose Jira flow for a work order")
    parser.add_argument("--work-order", required=True, help="Work order display ID (e.g. WO-B3E93984)")
    args = parser.parse_args()

    # Try to get Snowpark session
    try:
        from snowflake.snowpark.context import get_active_session
        session = get_active_session()
    except Exception:
        print("ERROR: No active Snowpark session. Run from Snowsight or provide connection.")
        sys.exit(1)

    diagnose(session, args.work_order)
