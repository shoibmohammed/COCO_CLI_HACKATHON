# services/jira_queue_recovery.py
# Diagnostic and safe crash recovery service for Jira integration queue requests.
# Co-authored with CoCo
"""
services/jira_queue_recovery.py
Provides find_stuck_jira_requests() and recover_stuck_jira_request()
to recover stale PROCESSING queue records safely without creating duplicate Jira tickets.
Uses parameterized queries and centralized identifier resolution.
"""

import logging
from typing import List, Dict, Any, Optional

from config import table

logger = logging.getLogger(__name__)


def find_stuck_jira_requests(session, timeout_minutes: int = 5) -> List[Dict[str, Any]]:
    """
    Finds queue items in 'PROCESSING' state whose UPDATED_AT is older than timeout_minutes (parameterized).
    """
    if not session:
        return []

    try:
        q_tbl = table("JIRA_INTEGRATION_QUEUE")
        query = f"""
            SELECT QUEUE_ID, WORK_ORDER_ID, MACHINE_ID, STATUS, RETRY_COUNT,
                   JIRA_ISSUE_KEY, ERROR_MESSAGE, CREATED_AT, UPDATED_AT
            FROM {q_tbl}
            WHERE STATUS = 'PROCESSING'
              AND UPDATED_AT < DATEADD('minute', -?, CURRENT_TIMESTAMP())
            ORDER BY UPDATED_AT ASC
        """
        rows = session.sql(query, params=[int(timeout_minutes)]).collect()
        stuck = []
        for r in rows:
            stuck.append({
                "queue_id": r["QUEUE_ID"],
                "work_order_id": r["WORK_ORDER_ID"],
                "machine_id": r["MACHINE_ID"],
                "status": r["STATUS"],
                "attempt_count": r.get("RETRY_COUNT", 0),
                "jira_issue_key": r.get("JIRA_ISSUE_KEY", ""),
                "updated_at": r.get("UPDATED_AT")
            })
        return stuck
    except Exception as e:
        logger.error(f"Error finding stuck Jira requests: {e}")
        return []


def recover_stuck_jira_request(session, queue_id: str) -> Dict[str, Any]:
    """
    Safely recovers a stuck PROCESSING request using parameterized queries.
    
    Idempotency Protocol:
    1. Checks if a Jira ticket key already exists in WORK_ORDERS or JIRA_TICKET_AUDIT.
    2. If ticket exists: updates JIRA_INTEGRATION_QUEUE status = 'SUCCESS' and writes back key.
    3. If no ticket exists: checks attempt count. If attempts < 3, resets to 'PENDING'. Otherwise sets to 'FAILED'.
    """
    result = {"queue_id": queue_id, "recovered": False, "action": "NONE", "message": ""}
    if not session or not queue_id:
        result["message"] = "Invalid session or queue_id"
        return result

    try:
        q_tbl = table("JIRA_INTEGRATION_QUEUE")
        wo_tbl = table("WORK_ORDERS")
        audit_tbl = table("JIRA_TICKET_AUDIT")

        # Fetch queue details
        q_rows = session.sql(f"""
            SELECT QUEUE_ID, WORK_ORDER_ID, MACHINE_ID, RETRY_COUNT, STATUS
            FROM {q_tbl}
            WHERE QUEUE_ID = ?
            LIMIT 1
        """, params=[str(queue_id)]).collect()

        if not q_rows:
            result["message"] = f"Queue record {queue_id} not found."
            return result

        q_row = q_rows[0]
        wo_id = q_row["WORK_ORDER_ID"]
        wo_id_raw = str(wo_id).replace("WO-", "").strip()
        attempts = q_row.get("RETRY_COUNT", 0)

        # 1. Check if Jira issue key already exists in WORK_ORDERS
        wo_rows = session.sql(f"""
            SELECT EXTERNAL_TICKET_ID FROM {wo_tbl}
            WHERE (LOWER(WORK_ORDER_ID) = LOWER(?) OR LOWER(WORK_ORDER_ID) LIKE LOWER(?))
              AND EXTERNAL_TICKET_ID IS NOT NULL
            LIMIT 1
        """, params=[wo_id_raw, f"{wo_id_raw}%"]).collect()

        existing_key = None
        if wo_rows and wo_rows[0]["EXTERNAL_TICKET_ID"]:
            existing_key = wo_rows[0]["EXTERNAL_TICKET_ID"]

        # 2. Check JIRA_TICKET_AUDIT if not found in WORK_ORDERS
        if not existing_key:
            audit_rows = session.sql(f"""
                SELECT JIRA_TICKET_KEY AS JIRA_ISSUE_KEY FROM {audit_tbl}
                WHERE (LOWER(WORK_ORDER_ID) = LOWER(?) OR LOWER(WORK_ORDER_ID) LIKE LOWER(?))
                  AND STATUS = 'SUCCESS' AND JIRA_TICKET_KEY IS NOT NULL
                ORDER BY CREATED_AT DESC LIMIT 1
            """, params=[wo_id_raw, f"{wo_id_raw}%"]).collect()
            if audit_rows and audit_rows[0]["JIRA_ISSUE_KEY"]:
                existing_key = audit_rows[0]["JIRA_ISSUE_KEY"]

        # 3. Action decision
        if existing_key:
            session.sql(f"""
                UPDATE {q_tbl}
                SET STATUS = 'SUCCESS',
                    JIRA_ISSUE_KEY = ?,
                    UPDATED_AT = CURRENT_TIMESTAMP()
                WHERE QUEUE_ID = ?
            """, params=[str(existing_key), str(queue_id)]).collect()
            result["recovered"] = True
            result["action"] = "RESOLVED_TO_SUCCESS"
            result["message"] = f"Ticket already exists ({existing_key}). Recovered status to SUCCESS."
        else:
            if attempts < 3:
                # Requeue for retry
                session.sql(f"""
                    UPDATE {q_tbl}
                    SET STATUS = 'PENDING',
                        ERROR_MESSAGE = 'Recovered from stale PROCESSING state',
                        UPDATED_AT = CURRENT_TIMESTAMP()
                    WHERE QUEUE_ID = ?
                """, params=[str(queue_id)]).collect()
                result["recovered"] = True
                result["action"] = "REQUEUED_PENDING"
                result["message"] = f"Requeued request {queue_id} to PENDING for safe retry."
            else:
                # Exceeded max attempts — mark FAILED
                session.sql(f"""
                    UPDATE {q_tbl}
                    SET STATUS = 'FAILED',
                        ERROR_MESSAGE = 'Max retries exceeded during crash recovery',
                        UPDATED_AT = CURRENT_TIMESTAMP()
                    WHERE QUEUE_ID = ?
                """, params=[str(queue_id)]).collect()
                result["recovered"] = True
                result["action"] = "MARKED_FAILED"
                result["message"] = f"Request {queue_id} exceeded max retries. Marked FAILED."

    except Exception as e:
        logger.error(f"Error recovering Jira request {queue_id}: {e}")
        result["message"] = f"Recovery failed: {str(e)[:200]}"

    return result
