-- ============================================================
-- 05_cortex_agent.sql
-- Creates the governed maintenance copilot used by CoCo/Streamlit/MCP.
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

CREATE OR REPLACE AGENT PM_AGENT
  COMMENT = 'Predictive maintenance copilot for machine health, technical knowledge retrieval, and governed work-order creation.'
  PROFILE = '{"display_name":"MFG Maintenance Copilot","color":"blue"}'
  FROM SPECIFICATION
  $$
models:
  orchestration: auto

orchestration:
  budget:
    seconds: 30
    tokens: 12000

instructions:
  response: >
    You are the MFG Predictive Maintenance Copilot. Be concise, technical,
    and evidence-driven. Never invent sensor readings, parts, or maintenance
    procedures. For a machine-specific diagnosis, first obtain live machine
    context, then search the maintenance knowledge base. Clearly separate
    observed telemetry from inferred root cause. If you recommend a work
    order, explain the reason and keep the work order in PENDING_APPROVAL
    unless a human explicitly approves the action.
  orchestration: >
    Use GetMachineContext for machine telemetry and current risk. Use
    GetFleetContext for fleet-level risk and OEE-related context. Use
    MaintenanceSearch for manuals, SOPs, and historical repair knowledge.
    Use CreateWorkOrder only when the user explicitly asks to create a
    work order or remediation is required by the workflow.
  sample_questions:
    - question: "Why is Machine_03 at risk?"
    - question: "What does the bearing manual recommend for high vibration and temperature?"
    - question: "Which machines are currently at highest risk?"
    - question: "Create a work order for Machine_03."

tools:
  - tool_spec:
      type: cortex_search
      name: MaintenanceSearch
      description: >
        Semantic search over machine manuals, SOPs, and historical
        maintenance knowledge. Use this to ground technical diagnosis,
        recommended procedures, and spare-part guidance.
  - tool_spec:
      type: generic
      name: GetMachineContext
      description: >
        Returns current telemetry, risk scores, supplier, bearing part,
        lead time, and machine metadata for one machine.
      input_schema:
        type: object
        properties:
          machine_id:
            type: string
            description: "Machine identifier such as Machine_01 or Machine_03."
        required:
          - machine_id
  - tool_spec:
      type: generic
      name: GetFleetContext
      description: >
        Returns fleet-level risk statistics and the highest-risk machines.
      input_schema:
        type: object
        properties: {}
  - tool_spec:
      type: generic
      name: CreateWorkOrder
      description: >
        Creates a governed maintenance work order after diagnosing a machine.
        The work order is created as PENDING_APPROVAL and includes diagnosis,
        action, required part, inventory, risk, and RUL.
      input_schema:
        type: object
        properties:
          machine_id:
            type: string
            description: "Machine identifier for the work order."
        required:
          - machine_id

tool_resources:
  MaintenanceSearch:
    name: PM_OEE_DB.CORE.MAINTENANCE_DOCS_SEARCH
    max_results: "5"
    title_column: source_file
    id_column: chunk_key
  GetMachineContext:
    identifier: PM_OEE_DB.CORE.GET_MACHINE_CONTEXT
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: PM_OEE_WH
      query_timeout: 30
  GetFleetContext:
    identifier: PM_OEE_DB.CORE.GET_FLEET_CONTEXT
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: PM_OEE_WH
      query_timeout: 30
  CreateWorkOrder:
    identifier: PM_OEE_DB.CORE.AGENTIC_REMEDIATION
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: PM_OEE_WH
      query_timeout: 30
  $$;

GRANT USAGE ON AGENT PM_OEE_DB.CORE.PM_AGENT TO ROLE PUBLIC;

SHOW AGENTS IN SCHEMA PM_OEE_DB.CORE;
