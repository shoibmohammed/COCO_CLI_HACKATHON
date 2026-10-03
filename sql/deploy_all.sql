-- ============================================================
-- MFG Predictive Maintenance & OEE Command Center
-- MASTER DDL DEPLOYMENT MANIFEST: deploy_all.sql
-- ============================================================
-- Recommended Execution Environment: SnowSQL / Snowflake Web UI Worksheets
-- Target Role: ACCOUNTADMIN (or role with CREATE WAREHOUSE, DATABASE, SCHEMA)
--
-- IMPORTANT SAFETY NOTE:
-- This script contains DDL object definitions for core infrastructure.
-- Seed data scripts (03_seed_data.sql) and reset scripts (10_reset_demo_state.sql)
-- are EXPLICIT SEPARATE DEMO STEPS because they perform TRUNCATE/RESET operations.
-- Do NOT execute seed data scripts automatically in production.
-- ============================================================

-- ------------------------------------------------------------
-- STEP 1: Core Database & Schema Infrastructure Setup
-- File: sql/01_setup.sql
-- ------------------------------------------------------------
-- Creates PM_OEE_WH warehouse, PM_OEE_DB database, CORE schema,
-- MACHINE_MASTER, ERP_ASSETS, SPARE_PARTS, SENSOR_READINGS,
-- PRODUCTION_EVENTS, MAINTENANCE_HISTORY, MAINTENANCE_DOCS tables,
-- and Dynamic Tables (MACHINE_HEALTH_RT, RISK_SCORES_RT, OEE_METRICS_RT).

-- ------------------------------------------------------------
-- STEP 2: Document Knowledge & Cortex Search Service
-- Files: sql/02_documents_and_cortex_search.sql
--        sql/02_load_docs_and_procs.sql
-- ------------------------------------------------------------
-- Populates MAINTENANCE_DOCS and initializes MAINTENANCE_DOCS_SEARCH
-- Cortex Search Service for semantic RAG retrieval.

-- ------------------------------------------------------------
-- STEP 3: Snowflake Cortex ML Classification & RUL Pipeline
-- File: sql/03_cortex_ml.sql
-- ------------------------------------------------------------
-- Registers failure prediction classification model and evaluation views.

-- ------------------------------------------------------------
-- STEP 4: Agent Workflow & Context Views
-- Files: sql/04_agent_workflow.sql
--        sql/05_cortex_agent.sql
--        sql/08_environmental_context.sql
-- ------------------------------------------------------------
-- Constructs unified agent context views and Cortex Agent definitions.

-- ------------------------------------------------------------
-- STEP 5: Governed Work Orders, Jira Queue & MCP Server Objects
-- Files: sql/06_mcp_server.sql
--        sql/09_jira_audit.sql
--        sql/09_jira_mcp_integration.sql
--        sql/10_jira_integration_queue.sql
--        sql/12_jira_worker_heartbeat.sql
-- ------------------------------------------------------------
-- Creates WORK_ORDERS table, JIRA_INTEGRATION_QUEUE, JIRA_TICKET_AUDIT,
-- and JIRA_WORKER_HEARTBEAT tables with approval status enforcement.

-- ------------------------------------------------------------
-- STEP 6: Multi-Channel Alert & Notification Audit Setup
-- Files: sql/07_alerts.sql
--        sql/11_notification_integration.sql
--        sql/13_automatic_notifications.sql
-- ------------------------------------------------------------
-- Configures NOTIFICATION_AUDIT schema, alert thresholds, and dual-channel dispatch tables.

-- ------------------------------------------------------------
-- STEP 7: Marketplace Ingestion Pipeline (Optional / Production)
-- Files: sql/marketplace_ingestion.sql
--        sql/external_supply_chain_ingestion.sql
-- ------------------------------------------------------------
-- Integrates external supply chain and parts inventory data.

-- ------------------------------------------------------------
-- STEP 8: Deployment Verification
-- File: sql/validate_deployment.sql
-- ------------------------------------------------------------
-- Runs structural integrity check verifying all required tables exist.
