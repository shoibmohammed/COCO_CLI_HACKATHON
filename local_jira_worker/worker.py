# Local Jira Worker — polls Snowflake queue and creates Jira issues via REST API
# Co-authored with CoCo
"""
worker.py
Main polling loop for the Local Jira Worker.
Responsibilities:
- Poll JIRA_INTEGRATION_QUEUE for PENDING records
- Claim records atomically
- Independently verify work order approval
- Check idempotency before calling Jira
- Create Jira issue via REST API
- Update queue with result (SUCCESS/FAILED)
- Handle retries with backoff
- Record audit entries
"""

import time
import logging
import sys

from config import get_config, validate_config
from snowflake_client import SnowflakeClient
from jira_client import JiraClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("jira_worker")


def process_record(record: dict, sf_client: SnowflakeClient, jira_client: JiraClient, max_retries: int):
    """Processes a single queue record."""
    queue_id = record["QUEUE_ID"]
    work_order_id = record["WORK_ORDER_ID"]
    machine_id = record["MACHINE_ID"] or "UNKNOWN"
    attempt_count = record["ATTEMPT_COUNT"] + 1
    t_start = time.time()

    logger.info(f"Processing {queue_id} for work order {work_order_id} (attempt {attempt_count})")

    # Step 1: Claim the record
    sf_client.claim_record(queue_id)
    t_claimed = time.time()
    logger.info(f"  Claimed in {(t_claimed - t_start)*1000:.0f}ms")

    # Step 2: Independent approval verification
    if not sf_client.verify_work_order_approved(work_order_id):
        error_msg = f"Work order {work_order_id} is NOT APPROVED. Refusing to create Jira issue."
        logger.warning(error_msg)
        sf_client.mark_failed(queue_id, error_msg, attempt_count)
        sf_client.record_audit(work_order_id, machine_id, queue_id, None, "REJECTED_NOT_APPROVED", None, attempt_count, error_msg)
        return

    # Step 3: Idempotency check — has this work order already succeeded?
    existing = sf_client.check_already_succeeded(work_order_id)
    if existing:
        logger.info(f"Idempotency: {work_order_id} already has Jira issue {existing['JIRA_ISSUE_KEY']}")
        sf_client.mark_success(queue_id, existing["JIRA_ISSUE_KEY"], existing["JIRA_URL"])
        sf_client.record_audit(work_order_id, machine_id, queue_id, existing["JIRA_ISSUE_KEY"], "DUPLICATE_PREVENTED", None, attempt_count, None)
        return

    # Step 4: Create Jira issue
    project_key = record.get("JIRA_PROJECT_KEY") or "KAN"
    summary = record.get("SHORT_DESCRIPTION") or f"Maintenance Work Order {work_order_id}"
    description = record.get("DESCRIPTION") or summary

    t_jira_start = time.time()
    success, result = jira_client.create_issue(
        project_key=project_key,
        summary=summary,
        description=description,
        issue_type="Task"
    )
    t_jira_end = time.time()
    logger.info(f"  Jira API: {(t_jira_end - t_jira_start)*1000:.0f}ms | HTTP {'201' if success else result.get('status_code', '?')}")

    if success:
        jira_key = result["key"]
        jira_url = result["url"]
        jira_id = result["id"]
        sf_client.mark_success(queue_id, jira_key, jira_url, jira_id)
        sf_client.update_work_order_ticket(work_order_id, jira_key)
        sf_client.record_audit(work_order_id, machine_id, queue_id, jira_key, "SUCCESS", result.get("status_code"), attempt_count, None)
        t_end = time.time()
        logger.info(f"  SUCCESS: {work_order_id} → {jira_key} (total: {(t_end - t_start)*1000:.0f}ms)")
    else:
        error_msg = result.get("error", "Unknown error")[:2000]
        http_status = result.get("status_code")

        if attempt_count < max_retries:
            sf_client.reset_for_retry(queue_id, attempt_count)
            sf_client.record_audit(work_order_id, machine_id, queue_id, None, "RETRY", http_status, attempt_count, error_msg)
            logger.warning(f"FAILED (will retry): {work_order_id} — {error_msg}")
        else:
            sf_client.mark_failed(queue_id, error_msg, attempt_count)
            sf_client.record_audit(work_order_id, machine_id, queue_id, None, "FAILED", http_status, attempt_count, error_msg)
            logger.error(f"FAILED (max retries): {work_order_id} — {error_msg}")


def run_worker():
    """Main worker loop."""
    cfg = get_config()
    missing = validate_config(cfg)
    if missing:
        logger.error(f"Missing required configuration: {missing}")
        sys.exit(1)

    sf_client = SnowflakeClient(cfg)
    jira_client_inst = JiraClient(
        base_url=cfg["jira_base_url"],
        user_email=cfg["jira_user_email"],
        api_token=cfg["jira_api_token"]
    )

    poll_interval = cfg["poll_interval_seconds"]
    max_retries = cfg["max_retries"]
    batch_size = cfg["batch_size"]
    heartbeat_interval = poll_interval * 3  # Update heartbeat every ~30s

    logger.info("Local Jira Worker starting...")
    logger.info(f"Polling interval: {poll_interval}s | Max retries: {max_retries} | Batch size: {batch_size}")

    sf_client.connect()

    # Set ONLINE heartbeat on startup
    try:
        sf_client.update_heartbeat()
        logger.info("Heartbeat: ONLINE")
    except Exception as e:
        logger.warning(f"Could not set initial heartbeat: {e}")

    last_heartbeat = time.time()

    try:
        while True:
            try:
                records = sf_client.get_pending_records(batch_size)
                if records:
                    logger.info(f"Found {len(records)} pending record(s)")
                    for record in records:
                        process_record(record, sf_client, jira_client_inst, max_retries)
                else:
                    logger.debug("No pending records")
            except Exception as e:
                logger.error(f"Error in polling loop: {str(e)[:500]}")
                # Reconnect on connection errors
                try:
                    sf_client.close()
                    sf_client.connect()
                except Exception:
                    pass

            # Periodic heartbeat update
            now = time.time()
            if now - last_heartbeat >= heartbeat_interval:
                try:
                    sf_client.update_heartbeat()
                    last_heartbeat = now
                except Exception as e:
                    logger.warning(f"Heartbeat update failed: {e}")

            time.sleep(poll_interval)
    except KeyboardInterrupt:
        logger.info("Worker shutting down (KeyboardInterrupt)")
    finally:
        # Set OFFLINE on graceful shutdown
        try:
            sf_client.set_offline()
            logger.info("Heartbeat: OFFLINE")
        except Exception:
            pass
        sf_client.close()


if __name__ == "__main__":
    run_worker()
