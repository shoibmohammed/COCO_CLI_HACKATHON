-- ============================================================
-- 06_mcp_server.sql
-- Snowflake-managed MCP surface for CoCo and external MCP clients.
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;

CREATE OR REPLACE MCP SERVER PM_MCP_SERVER
  FROM SPECIFICATION $$
tools:
  - title: "Predictive Maintenance Agent"
    name: "pm_agent"
    type: "CORTEX_AGENT_RUN"
    identifier: "PM_OEE_DB.CORE.PM_AGENT"
    description: "Governed maintenance copilot that combines live machine context, Cortex Search knowledge retrieval, and work-order remediation."

  - title: "Maintenance Knowledge Search"
    name: "maintenance_search"
    type: "CORTEX_SEARCH_SERVICE_QUERY"
    identifier: "PM_OEE_DB.CORE.MAINTENANCE_DOCS_SEARCH"
    description: "Semantic search over equipment manuals, SOPs, and historical repair knowledge."

  - title: "Create Maintenance Work Order"
    name: "create_work_order"
    type: "GENERIC"
    identifier: "PM_OEE_DB.CORE.AGENTIC_REMEDIATION"
    description: "Diagnose the specified machine and create a governed PENDING_APPROVAL work order with parts and estimated downtime."
    config:
      type: "procedure"
      warehouse: "PM_OEE_WH"
      query_timeout: 30
      input_schema:
        type: "object"
        properties:
          P_MACHINE_ID:
            type: "string"
            description: "Machine identifier such as Machine_03"

  - title: "Get Machine Context"
    name: "get_machine_context"
    type: "GENERIC"
    identifier: "PM_OEE_DB.CORE.GET_MACHINE_CONTEXT"
    description: "Returns current telemetry, risk, supplier, spare-part and machine context."
    config:
      type: "procedure"
      warehouse: "PM_OEE_WH"
      query_timeout: 30
      input_schema:
        type: "object"
        properties:
          P_MACHINE_ID:
            type: "string"
            description: "Machine identifier such as Machine_03"

$$;

GRANT USAGE ON MCP SERVER PM_OEE_DB.CORE.PM_MCP_SERVER TO ROLE PUBLIC;

SHOW MCP SERVERS IN SCHEMA PM_OEE_DB.CORE;
DESCRIBE MCP SERVER PM_OEE_DB.CORE.PM_MCP_SERVER;
