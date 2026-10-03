"""
config.py
Centralized Project Configuration & Safe Object Identifier Resolution
MFG Predictive Maintenance & OEE Command Center

Centralizes database, schema, warehouse names, and enforces strict identifier
whitelisting to prevent SQL injection and configuration drift.
NEVER stores plaintext secrets or credentials.
"""

import os
from typing import Optional, Set

# ==============================================================================
# 1. CORE DATABASE & INFRASTRUCTURE IDENTIFIERS
# ==============================================================================
DATABASE: str = "PM_OEE_DB"
SCHEMA: str = "CORE"
WAREHOUSE: str = os.getenv("SNOWFLAKE_WAREHOUSE", "PM_OEE_WH")
STREAMLIT_APP_NAME: str = os.getenv("SNOWFLAKE_STREAMLIT_APP", "MFG_PM_COMMAND_CENTER")
STREAMLIT_STAGE: str = os.getenv("SNOWFLAKE_STREAMLIT_STAGE", "MFG_PM_STREAMLIT_STAGE")
JIRA_PROJECT_KEY: str = os.getenv("JIRA_PROJECT_KEY", "KAN")

# ==============================================================================
# 2. IDENTIFIER WHITELIST (Defense-in-depth against SQL identifier injection)
# ==============================================================================
ALLOWED_SCHEMAS: Set[str] = {"CORE", "PUBLIC"}

ALLOWED_TABLES: Set[str] = {
    # Core Data & Master Tables
    "MACHINE_MASTER",
    "ERP_ASSETS",
    "SPARE_PARTS",
    "SENSOR_READINGS",
    "PRODUCTION_EVENTS",
    "MAINTENANCE_HISTORY",
    "MAINTENANCE_DOCS",
    "WORK_ORDERS",
    "ALERT_LOG",
    "MODEL_DRIFT_LOG",
    # Governed Queue & Audit Tables
    "JIRA_INTEGRATION_QUEUE",
    "JIRA_TICKET_AUDIT",
    "JIRA_WORKER_HEARTBEAT",
    "NOTIFICATION_AUDIT",
    "NOTIFICATION_QUEUE",
    # Marketplace & Enrichment
    "MARKETPLACE_PART_SUPPLIER_ENRICHMENT",
    "EXTERNAL_SUPPLY_CHAIN_RISK",
    "MARKETPLACE_INGESTION_AUDIT",
    "RAW_MARKETPLACE_DATA",
    "MARKETPLACE_CONFORMED_DATA",
    "AI_AUDIT_LOG",
    # Dynamic Tables (Real-Time Declarative Pipelines)
    "MACHINE_HEALTH_RT",
    "RISK_SCORES_RT",
    "OEE_METRICS_RT",
    # Registered Models & Procedures
    "PM_FAILURE_MODEL",
    "EXECUTE_JIRA_TICKET",
    "JIRA_MCP_WRITEBACK",
}

# ==============================================================================
# 3. SAFE OBJECT IDENTIFIER RESOLVER
# ==============================================================================
def get_object_name(
    table_name: str,
    schema: Optional[str] = None,
    database: Optional[str] = None
) -> str:
    """
    Returns a validated, fully-qualified Snowflake object identifier:
    `DATABASE.SCHEMA.TABLE_NAME`
    
    Raises ValueError if `table_name` is not in ALLOWED_TABLES.
    """
    tbl_clean = str(table_name).strip().upper()
    if tbl_clean not in ALLOWED_TABLES:
        raise ValueError(f"Security Alert: Untrusted or unknown table identifier '{table_name}'. Must be in ALLOWED_TABLES.")
    
    db_clean = (database or DATABASE).strip().upper()
    sch_clean = (schema or SCHEMA).strip().upper()
    
    if sch_clean not in ALLOWED_SCHEMAS:
        raise ValueError(f"Security Alert: Untrusted schema '{sch_clean}'. Must be in ALLOWED_SCHEMAS.")
        
    return f"{db_clean}.{sch_clean}.{tbl_clean}"


def table(table_name: str) -> str:
    """Convenience alias for get_object_name(table_name)."""
    return get_object_name(table_name)
