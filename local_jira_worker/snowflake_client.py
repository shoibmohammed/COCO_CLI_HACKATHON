# Snowflake client for Local Jira Worker — parameterized queries and strict identifier safety
# Co-authored with CoCo
"""
snowflake_client.py
Handles all Snowflake operations for the Local Jira Worker:
- Read PENDING queue records (parameterized LIMIT)
- Claim records (parameterized PENDING → PROCESSING)
- Verify work order approval (parameterized equality)
- Update queue with results (parameterized DML)
- Record audit entries (parameterized INSERT)
All queries use parameterized bindings to prevent SQL injection.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    import snowflake.connector
except ImportError:
    snowflake = None

logger = logging.getLogger(__name__)


class SnowflakeClient:
    def __init__(self, config: dict):
        self._config = config
        self._conn = None

    def connect(self):
        self._conn = snowflake.connector.connect(
            account=self._config["snowflake_account"],
            user=self._config["snowflake_user"],
            password=self._config["snowflake_password"],
            role=self._config.get("snowflake_role", "ACCOUNTADMIN"),
            warehouse=self._config.get("snowflake_warehouse", "PM_OEE_WH"),
            database=self._config.get("snowflake_database", "PM_OEE_DB"),
            schema=self._config.get("snowflake_schema", "CORE"),
        )
        logger.info("Connected to Snowflake")

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _execute(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        cur = self._conn.cursor(snowflake.connector.DictCursor)
        try:
            if params is not None:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            return cur.fetchall()
        finally:
            cur.close()

    def _execute_dml(self, sql: str, params: Optional[tuple] = None):
        cur = self._conn.cursor()
        try:
            if params is not None:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
        finally:
            cur.close()

    def get_pending_records(self, batch_size: int = 5) -> List[Dict[str, Any]]:
        """Fetches PENDING queue records ordered by creation time (parameterized)."""
        sql = """
            SELECT QUEUE_ID, WORK_ORDER_ID, MACHINE_ID, REQUEST_TYPE,
                   SHORT_DESCRIPTION, DESCRIPTION, IMPACT, URGENCY,
                   JIRA_PROJECT_KEY, RETRY_COUNT AS ATTEMPT_COUNT
            FROM PM_OEE_DB.CORE.JIRA_INTEGRATION_QUEUE
            WHERE STATUS = 'PENDING'
            ORDER BY CREATED_AT ASC
            LIMIT %s
        """
        return self._execute(sql, (batch_size,))

    def claim_record(self, queue_id: str) -> bool:
        """Atomically claims a record by setting STATUS = PROCESSING (parameterized)."""
        sql = """
            UPDATE PM_OEE_DB.CORE.JIRA_INTEGRATION_QUEUE
            SET STATUS = 'PROCESSING', UPDATED_AT = CURRENT_TIMESTAMP()
            WHERE QUEUE_ID = %s AND STATUS = 'PENDING'
        """
        self._execute_dml(sql, (queue_id,))
        return True

    def verify_work_order_approved(self, work_order_id: str) -> bool:
        """Independently verifies that the work order is APPROVED (parameterized)."""
        wo_id_num = work_order_id.replace("WO-", "").strip()
        like_pattern = f"{wo_id_num}%"
        sql = """
            SELECT STATUS 
            FROM PM_OEE_DB.CORE.WORK_ORDERS 
            WHERE LOWER(WORK_ORDER_ID) = LOWER(%s) OR LOWER(WORK_ORDER_ID) LIKE LOWER(%s)
        """
        rows = self._execute(sql, (wo_id_num, like_pattern))
        if not rows:
            logger.warning(f"Work order {work_order_id} not found in WORK_ORDERS table")
            return False
        return rows[0]["STATUS"] == "APPROVED"

    def check_already_succeeded(self, work_order_id: str) -> Optional[Dict[str, Any]]:
        """Application-level idempotency check: returns existing SUCCESS record if any (parameterized)."""
        sql = """
            SELECT JIRA_ISSUE_KEY, JIRA_ISSUE_URL AS JIRA_URL
            FROM PM_OEE_DB.CORE.JIRA_INTEGRATION_QUEUE
            WHERE WORK_ORDER_ID = %s AND STATUS = 'SUCCESS'
            LIMIT 1
        """
        rows = self._execute(sql, (work_order_id,))
        if rows:
            return rows[0]
        return None

    def mark_success(self, queue_id: str, jira_issue_key: str, jira_url: str, jira_sys_id: Optional[str] = None):
        """Marks a queue record as SUCCESS with Jira details (parameterized)."""
        sql = """
            UPDATE PM_OEE_DB.CORE.JIRA_INTEGRATION_QUEUE
            SET STATUS = 'SUCCESS',
                JIRA_ISSUE_KEY = %s,
                JIRA_ISSUE_URL = %s,
                JIRA_SYS_ID = %s,
                UPDATED_AT = CURRENT_TIMESTAMP()
            WHERE QUEUE_ID = %s
        """
        self._execute_dml(sql, (jira_issue_key, jira_url, jira_sys_id, queue_id))

    def mark_failed(self, queue_id: str, error_message: str, attempt_count: int):
        """Marks a queue record as FAILED with error details (parameterized)."""
        safe_err = str(error_message)[:2000]
        sql = """
            UPDATE PM_OEE_DB.CORE.JIRA_INTEGRATION_QUEUE
            SET STATUS = 'FAILED',
                ERROR_MESSAGE = %s,
                RETRY_COUNT = %s,
                UPDATED_AT = CURRENT_TIMESTAMP()
            WHERE QUEUE_ID = %s
        """
        self._execute_dml(sql, (safe_err, attempt_count, queue_id))

    def reset_for_retry(self, queue_id: str, attempt_count: int):
        """Resets a FAILED record back to PENDING for controlled retry (parameterized)."""
        sql = """
            UPDATE PM_OEE_DB.CORE.JIRA_INTEGRATION_QUEUE
            SET STATUS = 'PENDING',
                RETRY_COUNT = %s,
                UPDATED_AT = CURRENT_TIMESTAMP()
            WHERE QUEUE_ID = %s
        """
        self._execute_dml(sql, (attempt_count, queue_id))

    def record_audit(self, work_order_id: str, machine_id: str, queue_id: str,
                     jira_issue_key: Optional[str], status: str, http_status: Optional[int],
                     attempt_count: int, error_message: Optional[str]):
        """Records an audit entry for the Jira integration attempt (parameterized)."""
        safe_err = str(error_message)[:2000] if error_message else ""
        sql = """
            INSERT INTO PM_OEE_DB.CORE.JIRA_TICKET_AUDIT
                (WORK_ORDER_ID, MACHINE_ID, JIRA_ISSUE_KEY, JIRA_PROJECT, STATUS, ERROR_MESSAGE)
            VALUES
                (%s, %s, %s, 'KAN', %s, %s)
        """
        self._execute_dml(sql, (work_order_id, machine_id, jira_issue_key, status, safe_err))

    def update_work_order_ticket(self, work_order_id: str, jira_issue_key: str):
        """Updates WORK_ORDERS.EXTERNAL_TICKET_ID with the Jira issue key (parameterized)."""
        wo_id_num = work_order_id.replace("WO-", "").strip()
        like_pattern = f"{wo_id_num}%"
        sql = """
            UPDATE PM_OEE_DB.CORE.WORK_ORDERS
            SET EXTERNAL_TICKET_ID = %s
            WHERE LOWER(WORK_ORDER_ID) = LOWER(%s) OR LOWER(WORK_ORDER_ID) LIKE LOWER(%s)
        """
        self._execute_dml(sql, (jira_issue_key, wo_id_num, like_pattern))

    def _ensure_heartbeat_table(self):
        """Creates the JIRA_WORKER_HEARTBEAT table if it does not exist."""
        sql = """
            CREATE TABLE IF NOT EXISTS PM_OEE_DB.CORE.JIRA_WORKER_HEARTBEAT (
                WORKER_ID VARCHAR(100) DEFAULT 'LOCAL_JIRA_WORKER_01',
                STATUS VARCHAR(20) DEFAULT 'OFFLINE',
                LAST_HEARTBEAT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                VERSION VARCHAR(50) DEFAULT '1.0.0',
                UPDATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """
        self._execute_dml(sql)

    def update_heartbeat(self, worker_id: str = "LOCAL_JIRA_WORKER_01", version: str = "1.0.0"):
        """Sets or updates the worker heartbeat to ONLINE (parameterized)."""
        self._ensure_heartbeat_table()
        sql = """
            MERGE INTO PM_OEE_DB.CORE.JIRA_WORKER_HEARTBEAT t
            USING (SELECT %s AS WID) s ON t.WORKER_ID = s.WID
            WHEN MATCHED THEN UPDATE SET
                STATUS = 'ONLINE',
                LAST_HEARTBEAT = CURRENT_TIMESTAMP(),
                VERSION = %s,
                UPDATED_AT = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (WORKER_ID, STATUS, LAST_HEARTBEAT, VERSION, UPDATED_AT)
                VALUES (%s, 'ONLINE', CURRENT_TIMESTAMP(), %s, CURRENT_TIMESTAMP())
        """
        self._execute_dml(sql, (worker_id, version, worker_id, version))

    def set_offline(self, worker_id: str = "LOCAL_JIRA_WORKER_01"):
        """Marks the worker as OFFLINE during graceful shutdown (parameterized)."""
        try:
            sql = """
                UPDATE PM_OEE_DB.CORE.JIRA_WORKER_HEARTBEAT
                SET STATUS = 'OFFLINE', UPDATED_AT = CURRENT_TIMESTAMP()
                WHERE WORKER_ID = %s
            """
            self._execute_dml(sql, (worker_id,))
        except Exception as e:
            logger.warning(f"Could not set OFFLINE heartbeat: {e}")