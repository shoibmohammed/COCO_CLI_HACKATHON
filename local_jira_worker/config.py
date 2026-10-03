# Configuration for Local Jira Worker — credentials from environment variables only
# Co-authored with CoCo
"""
config.py
Configuration module for the Local Jira Worker.
All sensitive credentials MUST come from environment variables.
"""

import os
import socket


def get_config() -> dict:
    """Returns worker configuration from environment variables."""
    return {
        # Snowflake connection
        "snowflake_account": os.environ.get("SNOWFLAKE_ACCOUNT", ""),
        "snowflake_user": os.environ.get("SNOWFLAKE_USER", ""),
        "snowflake_password": os.environ.get("SNOWFLAKE_PASSWORD", ""),
        "snowflake_role": os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        "snowflake_warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "PM_OEE_WH"),
        "snowflake_database": os.environ.get("SNOWFLAKE_DATABASE", "PM_OEE_DB"),
        "snowflake_schema": os.environ.get("SNOWFLAKE_SCHEMA", "CORE"),

        # Jira connection
        "jira_base_url": os.environ.get("JIRA_BASE_URL", ""),
        "jira_user_email": os.environ.get("JIRA_USER_EMAIL", ""),
        "jira_api_token": os.environ.get("JIRA_API_TOKEN", ""),
        "jira_project_key": os.environ.get("JIRA_PROJECT_KEY", "KAN"),

        # Worker settings
        "worker_id": os.environ.get("WORKER_ID") or f"worker-{socket.gethostname()}-{os.getpid()}",
        "poll_interval_seconds": int(os.environ.get("WORKER_POLL_INTERVAL", "10")),
        "max_retries": int(os.environ.get("WORKER_MAX_RETRIES", "3")),
        "batch_size": int(os.environ.get("WORKER_BATCH_SIZE", "5")),
    }


def validate_config(cfg: dict) -> list:
    """Returns a list of missing required config keys."""
    required = [
        "snowflake_account", "snowflake_user", "snowflake_password",
        "jira_base_url", "jira_user_email", "jira_api_token"
    ]
    missing = [k for k in required if not cfg.get(k)]
    return missing
