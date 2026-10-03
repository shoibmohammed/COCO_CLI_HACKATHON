# Jira Integration Queue service for enqueuing requests from Streamlit to Snowflake
# Co-authored with CoCo
"""
services/jira_queue_service.py
Enqueues Jira issue creation requests into PM_OEE_DB.CORE.JIRA_INTEGRATION_QUEUE.
Enforces approval gate, application-level idempotency, and parameterized SQL execution.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from config import table

logger = logging.getLogger(__name__)


def _ensure_queue_table(session) -> None:
    """Creates the JIRA_INTEGRATION_QUEUE table if it does not exist."""
    q_tbl = table("JIRA_INTEGRATION_QUEUE")
    session.sql(f"""
        CREATE TABLE IF NOT EXISTS {q_tbl} (
            QUEUE_ID VARCHAR(50) DEFAULT UUID_STRING(),
            WORK_ORDER_ID VARCHAR(50) NOT NULL,
            MACHINE_ID VARCHAR(50),
            REQUEST_TYPE VARCHAR(50) DEFAULT 'CREATE_ISSUE',
            SHORT_DESCRIPTION VARCHAR(500),
            DESCRIPTION VARCHAR(4000),
            IMPACT VARCHAR(50),
            URGENCY VARCHAR(50),
            STATUS VARCHAR(20) DEFAULT 'PENDING',
            RETRY_COUNT INT DEFAULT 0,
            JIRA_PROJECT_KEY VARCHAR(50),
            JIRA_ISSUE_KEY VARCHAR(50),
            JIRA_SYS_ID VARCHAR(100),
            JIRA_ISSUE_URL VARCHAR(500),
            ERROR_MESSAGE VARCHAR(2000),
            CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            UPDATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        )
    """).collect()


def check_work_order_approved(session, work_order_id: str) -> bool:
    """Verifies that the given work order has STATUS = 'APPROVED' in Snowflake (parameterized)."""
    wo_tbl = table("WORK_ORDERS")
    wo_id_raw = str(work_order_id).replace("WO-", "").strip()
    result = session.sql(
        f"SELECT STATUS FROM {wo_tbl} WHERE LOWER(WORK_ORDER_ID) = LOWER(?) OR LOWER(WORK_ORDER_ID) LIKE LOWER(?)",
        params=[wo_id_raw, f"{wo_id_raw}%"]
    ).collect()
    if not result:
        return False
    return result[0]["STATUS"] == "APPROVED"


def check_existing_success(session, work_order_id: str) -> Optional[Dict[str, Any]]:
    """
    Application-level idempotency: checks if a SUCCESS record already exists
    for this work order in the queue (parameterized).
    """
    q_tbl = table("JIRA_INTEGRATION_QUEUE")
    rows = session.sql(f"""
        SELECT QUEUE_ID, JIRA_ISSUE_KEY, JIRA_ISSUE_URL, STATUS
        FROM {q_tbl}
        WHERE WORK_ORDER_ID = ? AND STATUS = 'SUCCESS'
        ORDER BY CREATED_AT DESC
        LIMIT 1
    """, params=[str(work_order_id)]).collect()
    if rows:
        row = rows[0]
        return {
            "queue_id": row["QUEUE_ID"],
            "jira_issue_key": row["JIRA_ISSUE_KEY"],
            "jira_url": row["JIRA_ISSUE_URL"],
            "status": row["STATUS"]
        }
    return None


def check_existing_pending(session, work_order_id: str) -> bool:
    """Checks if a PENDING or PROCESSING record already exists for this work order (parameterized)."""
    q_tbl = table("JIRA_INTEGRATION_QUEUE")
    rows = session.sql(f"""
        SELECT 1 FROM {q_tbl}
        WHERE WORK_ORDER_ID = ? AND STATUS IN ('PENDING', 'PROCESSING')
        LIMIT 1
    """, params=[str(work_order_id)]).collect()
    return len(rows) > 0


def enqueue_jira_request(
    session,
    work_order_id: str,
    machine_id: str,
    short_description: str,
    description: str,
    impact: str = "HIGH",
    urgency: str = "HIGH",
    jira_project_key: str = "KAN"
) -> Dict[str, Any]:
    """
    Enqueues a Jira issue creation request into the integration queue using parameterized queries.
    """
    _ensure_queue_table(session)

    # Gate 1: Verify work order is APPROVED
    if not check_work_order_approved(session, work_order_id):
        return {
            "status": "BLOCKED",
            "message": f"Work Order {work_order_id} is not APPROVED. Jira request blocked.",
            "jira_key": None,
            "jira_url": None
        }

    # Gate 2: Idempotency — check for existing SUCCESS
    existing = check_existing_success(session, work_order_id)
    if existing:
        return {
            "status": "ALREADY_EXISTS",
            "message": f"Jira issue already created: {existing['jira_issue_key']}",
            "jira_key": existing["jira_issue_key"],
            "jira_url": existing["jira_url"]
        }

    # Gate 3: Check for already-pending request
    if check_existing_pending(session, work_order_id):
        return {
            "status": "PENDING",
            "message": f"Jira request for {work_order_id} is already queued and awaiting processing.",
            "jira_key": None,
            "jira_url": None
        }

    q_tbl = table("JIRA_INTEGRATION_QUEUE")
    safe_short = str(short_description)[:500]
    safe_desc = str(description)[:4000]

    # Parameterized Insert into queue
    session.sql(f"""
        INSERT INTO {q_tbl}
            (WORK_ORDER_ID, MACHINE_ID, SHORT_DESCRIPTION, DESCRIPTION,
             IMPACT, URGENCY, STATUS, JIRA_PROJECT_KEY)
        VALUES
            (?, ?, ?, ?, ?, ?, 'PENDING', ?)
    """, params=[
        str(work_order_id),
        str(machine_id),
        safe_short,
        safe_desc,
        str(impact),
        str(urgency),
        str(jira_project_key)
    ]).collect()

    logger.info(f"Jira request enqueued for {work_order_id} (machine: {machine_id})")

    return {
        "status": "QUEUED",
        "message": f"Jira issue request queued for {work_order_id}. Local Jira Worker will process shortly.",
        "jira_key": None,
        "jira_url": None
    }


def get_queue_status(session, work_order_id: str) -> Optional[Dict[str, Any]]:
    """Returns the latest queue record for a given work order (parameterized)."""
    q_tbl = table("JIRA_INTEGRATION_QUEUE")
    rows = session.sql(f"""
        SELECT QUEUE_ID, WORK_ORDER_ID, MACHINE_ID, STATUS, RETRY_COUNT,
        JIRA_ISSUE_KEY, JIRA_ISSUE_URL, ERROR_MESSAGE, CREATED_AT, UPDATED_AT
        FROM {q_tbl}
        WHERE WORK_ORDER_ID = ?
        ORDER BY CREATED_AT DESC
        LIMIT 1
    """, params=[str(work_order_id)]).collect()
    if not rows:
        return None
    row = rows[0]
    return {
        "queue_id": row["QUEUE_ID"],
        "work_order_id": row["WORK_ORDER_ID"],
        "machine_id": row["MACHINE_ID"],
        "status": row["STATUS"],
        "attempt_count": row.get("RETRY_COUNT", 0),
        "jira_issue_key": row["JIRA_ISSUE_KEY"],
        "jira_url": row.get("JIRA_ISSUE_URL", ""),
        "error_message": row["ERROR_MESSAGE"],
        "created_at": row["CREATED_AT"],
        "updated_at": row["UPDATED_AT"],
    }


def check_worker_health(session, stale_threshold_seconds: int = 300) -> Dict[str, Any]:
    """
    Checks the Local Jira Worker's health status by reading JIRA_WORKER_HEARTBEAT.
    Returns dict with: status (ONLINE/OFFLINE), last_heartbeat, version.
    """
    result = {
        "status": "OFFLINE",
        "last_heartbeat": None,
        "version": None,
        "message": "Worker status unknown",
    }

    if not session:
        return result

    try:
        hb_tbl = table("JIRA_WORKER_HEARTBEAT")
        rows = session.sql(f"""
            SELECT WORKER_ID, STATUS, LAST_HEARTBEAT, VERSION, UPDATED_AT
            FROM {hb_tbl}
            ORDER BY LAST_HEARTBEAT DESC
            LIMIT 1
        """).collect()

        if not rows:
            result["message"] = "No heartbeat record found. Start the Local Jira Worker."
            return result

        row = rows[0]
        try:
            worker_id_val = str(row.get("WORKER_ID", "WORKER_1") if hasattr(row, "get") else row["WORKER_ID"])
        except Exception:
            worker_id_val = "WORKER_1"
        try:
            db_status = str(row["STATUS"]).upper()
        except Exception:
            db_status = "OFFLINE"
        try:
            last_hb = row["LAST_HEARTBEAT"]
        except Exception:
            last_hb = None
        try:
            version = str(row["VERSION"])
        except Exception:
            version = ""

        result["worker_id"] = worker_id_val
        result["last_heartbeat"] = last_hb
        result["version"] = version

        if db_status == "ONLINE" and last_hb:
            stale_rows = session.sql(f"""
                SELECT CASE WHEN DATEDIFF('second', LAST_HEARTBEAT, CURRENT_TIMESTAMP()) <= ?
                       THEN 'FRESH' ELSE 'STALE' END AS FRESHNESS
                FROM {hb_tbl}
                WHERE WORKER_ID = ?
            """, params=[int(stale_threshold_seconds), worker_id_val]).collect()

            if stale_rows and str(stale_rows[0]["FRESHNESS"]) == "FRESH":
                result["status"] = "ONLINE"
                result["message"] = "Worker is running and healthy."
            else:
                result["status"] = "OFFLINE"
                result["message"] = "Worker heartbeat is stale. Restart the Local Jira Worker."
        else:
            result["status"] = "OFFLINE"
            result["message"] = "Worker is offline. Start the Local Jira Worker."

    except Exception as e:
        err = str(e).lower()
        if "does not exist" in err or "not exist" in err:
            result["message"] = "Heartbeat table not found. Run sql/12_jira_worker_heartbeat.sql."
        else:
            result["message"] = "Could not check worker health."
        logger.debug(f"Worker health check error: {e}")

    return result


def update_worker_heartbeat(session, worker_id: str = "default_worker", host: str = "streamlit-app") -> bool:
    """
    Updates the worker heartbeat to keep the worker status ONLINE.
    Called automatically when Jira connectivity is confirmed.
    """
    if not session:
        return False
    try:
        hb_tbl = table("JIRA_WORKER_HEARTBEAT")
        session.sql(f"""
            MERGE INTO {hb_tbl} t
            USING (SELECT ? AS WORKER_ID, 'ONLINE' AS STATUS,
                   CURRENT_TIMESTAMP() AS LAST_HEARTBEAT, '2.0.0' AS VERSION) s
            ON t.WORKER_ID = s.WORKER_ID
            WHEN MATCHED THEN UPDATE SET
                t.STATUS = s.STATUS,
                t.LAST_HEARTBEAT = s.LAST_HEARTBEAT,
                t.VERSION = s.VERSION,
                t.UPDATED_AT = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (WORKER_ID, STATUS, LAST_HEARTBEAT, VERSION)
                VALUES (s.WORKER_ID, s.STATUS, s.LAST_HEARTBEAT, s.VERSION)
        """, params=[worker_id]).collect()
        return True
    except Exception as e:
        logger.debug(f"Heartbeat update error: {e}")
        return False
