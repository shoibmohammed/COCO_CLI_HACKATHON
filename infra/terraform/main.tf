# ==============================================================================
# INFRASTRUCTURE AS CODE (TERRAFORM)
# MFG Predictive Maintenance & OEE Command Center
# 
# SCOPE SEPARATION:
# - Terraform manages: Snowflake Warehouse, Database, Schemas, Stages, and Network Rules.
# - Versioned SQL (deploy_all.sql) manages: Dynamic Tables, ML Models, Stored Procs, Tasks, and Streamlit.
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    snowflake = {
      source  = "Snowflake-Labs/snowflake"
      version = "~> 0.87.0"
    }
  }
}

provider "snowflake" {
  account  = var.snowflake_account
  user     = var.snowflake_user
  password = var.snowflake_password
  role     = var.snowflake_role
}

# 1. Virtual Warehouse
resource "snowflake_warehouse" "pm_warehouse" {
  name           = var.warehouse_name
  warehouse_size = "X-SMALL"
  auto_suspend   = 60
  auto_resume    = true
  initially_suspended = true
  comment        = "Compute warehouse for MFG Predictive Maintenance & OEE workloads"
}

# 2. Database
resource "snowflake_database" "pm_database" {
  name    = var.database_name
  comment = "Database containing telemetry, ML models, work orders, and marketplace conformed data"
}

# 3. Core Application Schema
resource "snowflake_schema" "pm_core_schema" {
  database = snowflake_database.pm_database.name
  name     = var.schema_name
  comment  = "Core schema for tables, views, stored procedures, and Streamlit application"
}

# 4. Internal Stage for Streamlit Application Artifacts
resource "snowflake_stage" "streamlit_stage" {
  name        = "MFG_PM_STREAMLIT_STAGE"
  database    = snowflake_database.pm_database.name
  schema      = snowflake_schema.pm_core_schema.name
  comment     = "Internal stage storing Streamlit application code, components, and assets"
}
