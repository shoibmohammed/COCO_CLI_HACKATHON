# Safe Single-Pass Jira Worker Test Script — dynamic work-order selection
# Co-authored with CoCo
"""
local_jira_worker/approved_work_order_to_jira.py

PURPOSE:
- Executable dynamic single-pass test runner for Local Jira Worker.
- Supports both Command-line mode (--work-order WO-501 or -w 501) and Interactive mode.
- Fetches and displays APPROVED work orders from PM_OEE_DB.CORE.WORK_ORDERS.
- Enforces independent approval verification (WORK_ORDERS.STATUS == 'APPROVED').
- Enforces application-level idempotency (prevents duplicate Jira tickets).
- Enqueues new queue requests via Snowflake JIRA_INTEGRATION_QUEUE if no queue record exists.
- Processes EXACTLY ONE selected work order, calls Jira REST API, performs Snowflake write-back, and exits.

REUSES:
- config.py (get_config, validate_config)
- snowflake_client.py (SnowflakeClient)
- jira_client.py (JiraClient)
- worker.py (process_record)
"""

import os
import sys
import logging
import platform
import argparse

# Python 3.14 Windows compatibility workaround for platform.libc_ver
if not hasattr(platform, "libc_ver") or callable(platform.libc_ver):
    try:
        platform.libc_ver = lambda *args, **kwargs: ("", "")
    except Exception:
        pass

# Ensure parent directory (local_jira_worker) is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def load_env_from_secrets():
    """
    Helper to load environment variables from .streamlit/secrets.toml if missing.
    Ensures credentials come only from local secure configuration.
    """
    secrets_path = os.path.join(PROJECT_ROOT, ".streamlit", "secrets.toml")
    if not os.path.exists(secrets_path):
        return

    try:
        import tomllib
        with open(secrets_path, "rb") as f:
            data = tomllib.load(f)

        sf = data.get("snowflake", {})
        if sf:
            os.environ.setdefault("SNOWFLAKE_ACCOUNT", sf.get("account", ""))
            os.environ.setdefault("SNOWFLAKE_USER", sf.get("user", ""))
            os.environ.setdefault("SNOWFLAKE_PASSWORD", sf.get("password", ""))
            os.environ.setdefault("SNOWFLAKE_ROLE", sf.get("role", "ACCOUNTADMIN"))
            os.environ.setdefault("SNOWFLAKE_WAREHOUSE", sf.get("warehouse", "PM_OEE_WH"))
            os.environ.setdefault("SNOWFLAKE_DATABASE", sf.get("database", "PM_OEE_DB"))
            os.environ.setdefault("SNOWFLAKE_SCHEMA", sf.get("schema", "CORE"))

        jira = data.get("jira", {})
        if jira:
            os.environ.setdefault("JIRA_BASE_URL", jira.get("base_url") or jira.get("url", ""))
            os.environ.setdefault("JIRA_USER_EMAIL", jira.get("email") or jira.get("user_email", ""))
            os.environ.setdefault("JIRA_API_TOKEN", jira.get("api_token", ""))
            os.environ.setdefault("JIRA_PROJECT_KEY", jira.get("project_key", "KAN"))
    except Exception:
        pass


def normalize_wo_id(wo_input: str) -> str:
    """Standardizes work order ID format (e.g. '501' or 'wo-501' -> 'WO-501')."""
    cleaned = wo_input.strip().upper()
    if cleaned.isdigit():
        return f"WO-{cleaned}"
    return cleaned


def fetch_approved_work_orders(sf_client) -> list:
    """Fetches all APPROVED work orders from WORK_ORDERS table."""
    try:
        return sf_client._execute("""
            SELECT WORK_ORDER_ID, MACHINE_ID, PRIORITY, DIAGNOSIS, RISK_SCORE, RUL_HOURS, STATUS
            FROM PM_OEE_DB.CORE.WORK_ORDERS
            WHERE STATUS = 'APPROVED'
            ORDER BY WORK_ORDER_ID ASC
        """)
    except Exception:
        return sf_client._execute("""
            SELECT WORK_ORDER_ID, MACHINE_ID, PRIORITY, STATUS
            FROM PM_OEE_DB.CORE.WORK_ORDERS
            WHERE STATUS = 'APPROVED'
            ORDER BY WORK_ORDER_ID ASC
        """)


def get_work_order_details(sf_client, wo_id: str) -> dict:
    """Fetches details for a specific work order ID."""
    wo_num = wo_id.replace("WO-", "").strip()
    if not wo_num.isdigit():
        return None

    sql = """
        SELECT WORK_ORDER_ID, MACHINE_ID, PRIORITY, DIAGNOSIS, RISK_SCORE, RUL_HOURS, STATUS, SHORT_DESCRIPTION, DESCRIPTION
        FROM PM_OEE_DB.CORE.WORK_ORDERS
        WHERE WORK_ORDER_ID = %s
    """
    try:
        rows = sf_client._execute(sql, (int(wo_num),))
        if rows:
            return rows[0]
    except Exception:
        sql_fallback = """
            SELECT WORK_ORDER_ID, MACHINE_ID, PRIORITY, STATUS
            FROM PM_OEE_DB.CORE.WORK_ORDERS
            WHERE WORK_ORDER_ID = %s
        """
        rows = sf_client._execute(sql_fallback, (int(wo_num),))
        if rows:
            return rows[0]
    return None


def get_latest_queue_record(sf_client, wo_id: str) -> dict:
    """Fetches the latest queue record for a work order."""
    formatted_wo_id = f"WO-{str(wo_id).replace('WO-', '')}"
    rows = sf_client._execute("""
        SELECT QUEUE_ID, WORK_ORDER_ID, MACHINE_ID, REQUEST_TYPE,
               SHORT_DESCRIPTION, DESCRIPTION, IMPACT, URGENCY,
               STATUS, ATTEMPT_COUNT, JIRA_PROJECT_KEY, JIRA_ISSUE_KEY, JIRA_URL, ERROR_MESSAGE
        FROM PM_OEE_DB.CORE.JIRA_INTEGRATION_QUEUE
        WHERE WORK_ORDER_ID = %s
        ORDER BY CREATED_AT DESC
        LIMIT 1
    """, (formatted_wo_id,))
    return rows[0] if rows else None


def enqueue_new_request(sf_client, wo_data: dict, jira_project_key: str = "KAN") -> dict:
    """Enqueues a new PENDING request in JIRA_INTEGRATION_QUEUE."""
    wo_id = f"WO-{str(wo_data['WORK_ORDER_ID']).replace('WO-', '')}"
    machine_id = wo_data.get("MACHINE_ID") or "UNKNOWN"
    short_desc = wo_data.get("SHORT_DESCRIPTION") or f"Maintenance Work Order {wo_id}"
    desc = wo_data.get("DESCRIPTION") or f"Work Order {wo_id} for machine {machine_id}"

    sf_client._execute_dml("""
        INSERT INTO PM_OEE_DB.CORE.JIRA_INTEGRATION_QUEUE
            (WORK_ORDER_ID, MACHINE_ID, REQUEST_TYPE, SHORT_DESCRIPTION, DESCRIPTION,
             IMPACT, URGENCY, STATUS, ATTEMPT_COUNT, JIRA_PROJECT_KEY)
        VALUES
            (%s, %s, 'CREATE_ISSUE', %s, %s,
             'HIGH', 'HIGH', 'PENDING', 0, %s)
    """, (wo_id, machine_id, short_desc[:500], desc[:4000], jira_project_key))
    return get_latest_queue_record(sf_client, wo_id)


def run_single_pass_test(target_wo: str = None, dry_run: bool = False, auto_confirm: bool = False):
    """
    Executes dynamic single-pass test for a selected work order.
    """
    load_env_from_secrets()

    from config import get_config, validate_config
    cfg = get_config()
    missing = validate_config(cfg)

    if missing:
        print("=" * 50)
        print("ERROR: Missing required configuration variables:")
        for m in missing:
            print(f"  - {m}")
        print("Please configure environment variables or .streamlit/secrets.toml")
        print("=" * 50)
        sys.exit(1)

    from snowflake_client import SnowflakeClient
    from jira_client import JiraClient

    print("=" * 50)
    print("LOCAL JIRA SINGLE-PASS TEST RUNNER")
    print("=" * 50)

    sf_client = SnowflakeClient(cfg)
    try:
        sf_client.connect()
    except Exception as e:
        print(f"ERROR: Snowflake connection failed: {str(e)[:200]}")
        sys.exit(1)

    try:
        # Step 1: Select Work Order (CLI or Interactive)
        selected_wo_id = None

        if target_wo:
            selected_wo_id = normalize_wo_id(target_wo)
        else:
            approved_wos = fetch_approved_work_orders(sf_client)
            if not approved_wos:
                print("No APPROVED work orders found in PM_OEE_DB.CORE.WORK_ORDERS.")
                sys.exit(0)

            print("\nAvailable approved work orders:\n")
            for idx, wo in enumerate(approved_wos, start=1):
                wo_id = f"WO-{str(wo['WORK_ORDER_ID']).replace('WO-', '')}"
                machine = wo.get("MACHINE_ID", "N/A")
                priority = wo.get("PRIORITY", "P1")
                risk = f"{wo.get('RISK_SCORE', 0):.1f}%" if wo.get("RISK_SCORE") is not None else "N/A"
                rul = f"{wo.get('RUL_HOURS', 0):.1f}h" if wo.get("RUL_HOURS") is not None else "N/A"
                print(f"  {idx}. {wo_id} | {machine} | {priority} | Risk: {risk} | RUL: {rul}")

            print("\nEnter Work Order ID (or number from list above): ", end="")
            user_choice = input().strip()

            if user_choice.isdigit():
                idx_val = int(user_choice)
                if 1 <= idx_val <= len(approved_wos):
                    selected_wo_id = f"WO-{str(approved_wos[idx_val-1]['WORK_ORDER_ID']).replace('WO-', '')}"
                else:
                    selected_wo_id = normalize_wo_id(user_choice)
            else:
                selected_wo_id = normalize_wo_id(user_choice)

        print(f"\nTarget Work Order: {selected_wo_id}")

        # Step 2: Validate Work Order Existence and Approval Guard
        wo_data = get_work_order_details(sf_client, selected_wo_id)

        if not wo_data:
            print(f"\nERROR: Work Order {selected_wo_id} not found.")
            sys.exit(1)

        formatted_wo_id = f"WO-{str(wo_data['WORK_ORDER_ID']).replace('WO-', '')}"
        wo_status = wo_data.get("STATUS", "").upper()

        if wo_status != "APPROVED":
            print(f"\nBLOCK: Work Order {formatted_wo_id} is not APPROVED (Current status: {wo_status}). Jira creation is not allowed.")
            sys.exit(1)

        print(f"Work Order Status: APPROVED ({wo_data.get('MACHINE_ID', 'N/A')})")

        # Step 3: Find Queue Record
        queue_rec = get_latest_queue_record(sf_client, formatted_wo_id)

        # Step 4: Handle Existing State
        if queue_rec:
            q_status = queue_rec["STATUS"]
            if q_status == "SUCCESS":
                jira_key = queue_rec.get("JIRA_ISSUE_KEY", "UNKNOWN")
                jira_url = queue_rec.get("JIRA_URL", "N/A")
                print(f"\nJira ticket already exists: {jira_key}")
                print(f"Jira URL: {jira_url}")
                print("Idempotency: PASS — no duplicate created.")
                print("=" * 50)
                sys.exit(0)

            elif q_status == "PROCESSING":
                print(f"\nWork Order {formatted_wo_id} is already being processed.")
                print("Do NOT create another request.")
                print("=" * 50)
                sys.exit(0)

            elif q_status == "FAILED":
                print(f"\nQueue record for {formatted_wo_id} is FAILED (attempts: {queue_rec.get('ATTEMPT_COUNT', 0)}).")
                print(f"Error message: {queue_rec.get('ERROR_MESSAGE', '')[:200]}")

                retry_resp = "Y" if auto_confirm else ""
                if not auto_confirm:
                    print("Requeue and retry this failed request? [Y/N]: ", end="")
                    retry_resp = input().strip().upper()

                if retry_resp.startswith("Y"):
                    sf_client.reset_for_retry(queue_rec["QUEUE_ID"], 0)
                    queue_rec = get_latest_queue_record(sf_client, formatted_wo_id)
                    print("Queue status reset to PENDING.")
                else:
                    print("Retry cancelled by user.")
                    sys.exit(0)

        # Step 5: Handle Case Where No Queue Record Exists
        if not queue_rec:
            print(f"\nNo Jira request exists for {formatted_wo_id}.")
            create_resp = "Y" if auto_confirm else ""
            if not auto_confirm:
                print(f"Create a Jira queue request for this approved work order? [Y/N]: ", end="")
                create_resp = input().strip().upper()

            if create_resp.startswith("Y"):
                queue_rec = enqueue_new_request(sf_client, wo_data, cfg.get("jira_project_key", "KAN"))
                print(f"Jira queue request enqueued: {queue_rec['QUEUE_ID']} (STATUS = PENDING)")
            else:
                print("Creation cancelled by user.")
                sys.exit(0)

        # Step 6: Process Exactly One Queue Record
        queue_id = queue_rec["QUEUE_ID"]
        wo_id = queue_rec["WORK_ORDER_ID"]
        machine_id = queue_rec.get("MACHINE_ID") or wo_data.get("MACHINE_ID") or "UNKNOWN"
        project_key = queue_rec.get("JIRA_PROJECT_KEY") or cfg.get("jira_project_key", "KAN")
        summary = queue_rec.get("SHORT_DESCRIPTION") or f"Maintenance Work Order {wo_id}"
        description = queue_rec.get("DESCRIPTION") or summary
        attempt_count = queue_rec.get("ATTEMPT_COUNT", 0) + 1

        # Double check idempotency before calling Jira
        existing_jira = sf_client.check_already_succeeded(wo_id)
        if existing_jira:
            print(f"\nJira ticket already exists: {existing_jira.get('JIRA_ISSUE_KEY')}")
            print("Idempotency: PASS — no duplicate created.")
            sys.exit(0)

        # Claim record (PENDING -> PROCESSING)
        sf_client.claim_record(queue_id)
        print("\nQueue Status: PROCESSING")

        if dry_run:
            print("\n[DRY RUN MODE] Record claimed. Jira API call skipped.")
            print("=" * 50)
            sys.exit(0)

        # Print Safe Payload Summary (NO secrets)
        print("\nJira Payload Summary:")
        print(f"  - Project Key: {project_key}")
        print("  - Issue Type: Task")
        print(f"  - Summary: {summary[:100]}")
        print(f"  - Work Order ID: {wo_id}")
        print(f"  - Machine ID: {machine_id}")

        # Step 7: Call Jira REST API
        jira_client_inst = JiraClient(
            base_url=cfg["jira_base_url"],
            user_email=cfg["jira_user_email"],
            api_token=cfg["jira_api_token"]
        )

        success, result = jira_client_inst.create_issue(
            project_key=project_key,
            summary=summary,
            description=description,
            issue_type="Task"
        )

        http_status = result.get("status_code")

        # Step 8: Write-Back and Output Final Result
        if success:
            jira_key = result.get("key", "")
            jira_id = result.get("id", "")
            jira_url = result.get("url", "")

            sf_client.mark_success(queue_id, jira_key, jira_url, jira_id)
            sf_client.update_work_order_ticket(wo_id, jira_key)
            sf_client.record_audit(wo_id, machine_id, queue_id, jira_key, "SUCCESS", http_status, attempt_count, None)

            print("\n" + "=" * 50)
            print("LOCAL JIRA SINGLE-PASS TEST RESULT")
            print("=" * 50)
            print(f"Work Order: {wo_id}")
            print(f"Machine: {machine_id}")
            print("Work Order Status: APPROVED")
            print("Queue Status: SUCCESS")
            print(f"Jira Status: SUCCESS ({http_status})")
            print(f"Jira Issue: {jira_key}")
            print(f"Jira URL: {jira_url}")
            print("=" * 50)
        else:
            error_msg = result.get("error", "Unknown error")[:2000]
            max_retries = cfg.get("max_retries", 3)

            if attempt_count < max_retries:
                sf_client.reset_for_retry(queue_id, attempt_count)
                sf_client.record_audit(wo_id, machine_id, queue_id, None, "RETRY", http_status, attempt_count, error_msg)
            else:
                sf_client.mark_failed(queue_id, error_msg, attempt_count)
                sf_client.record_audit(wo_id, machine_id, queue_id, None, "FAILED", http_status, attempt_count, error_msg)

            print("\n" + "=" * 50)
            print("LOCAL JIRA SINGLE-PASS TEST RESULT")
            print("=" * 50)
            print(f"Work Order: {wo_id}")
            print(f"Machine: {machine_id}")
            print("Work Order Status: APPROVED")
            print("Queue Status: FAILED")
            print(f"Jira Status: FAILED ({http_status})")
            print(f"Error Details: {error_msg[:200]}")
            print("=" * 50)

    except Exception as e:
        print(f"\nERROR: {str(e)[:300]}")
        print("=" * 50)
        sys.exit(1)
    finally:
        sf_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safe Dynamic Single-Pass Jira Worker Test Runner")
    parser.add_argument("--work-order", "-w", type=str, help="Specific Work Order ID (e.g. 501 or WO-501)")
    parser.add_argument("--dry-run", action="store_true", help="Validate queue and approval without calling Jira API")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm enqueue/retry prompts")
    args = parser.parse_args()

    run_single_pass_test(target_wo=args.work_order, dry_run=args.dry_run, auto_confirm=args.yes)
