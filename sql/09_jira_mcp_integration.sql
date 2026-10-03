-- Jira MCP Integration: stored procedures, MCP server, and Cortex Agent for automated ticket management
-- Co-authored with CoCo

-- ============================================================================
-- JIRA MCP INTEGRATION FOR MFG PREDICTIVE MAINTENANCE
-- ============================================================================
-- This script creates:
--   1. Network Rule + External Access Integration for Jira API
--   2. Secret for Jira API credentials
--   3. Stored procedures as MCP-callable tools
--   4. MCP Server exposing the Jira tools
--   5. Cortex Agent configured with the Jira MCP tools
--
-- OPTION A: Native Atlassian MCP Connector (recommended for production)
-- OPTION B: Custom Stored Procedure MCP Server (works with existing API token)
-- ============================================================================

USE ROLE ACCOUNTADMIN;
USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE COMPUTE_WH;

-- ============================================================================
-- OPTION A: NATIVE ATLASSIAN MCP CONNECTOR (Dynamic Client Registration)
-- ============================================================================
-- Prerequisites:
--   1. Navigate to admin.atlassian.com > Apps > AI Settings > Rovo MCP Server
--   2. Under "Your domains", add: https://identity.snowflake.com/oauth2/callback
--
-- Uncomment below when Atlassian admin setup is complete:
-- 
-- CREATE OR REPLACE API INTEGRATION JIRA_ATLASSIAN_MCP_INTEGRATION
--   API_PROVIDER = external_mcp
--   API_ALLOWED_PREFIXES = ('https://mcp.atlassian.com')
--   API_USER_AUTHENTICATION = (
--     TYPE=OAUTH_DYNAMIC_CLIENT,
--     OAUTH_RESOURCE_URL='https://mcp.atlassian.com/v1/mcp'
--   )
--   ENABLED = TRUE;
--
-- CREATE OR REPLACE EXTERNAL MCP SERVER PM_OEE_DB.CORE.JIRA_ATLASSIAN_MCP
--   WITH DISPLAY_NAME = 'Atlassian Jira (MFG Maintenance)'
--   URL = 'https://mcp.atlassian.com/v1/mcp'
--   API_INTEGRATION = JIRA_ATLASSIAN_MCP_INTEGRATION;
--
-- GRANT USAGE ON EXTERNAL MCP SERVER PM_OEE_DB.CORE.JIRA_ATLASSIAN_MCP TO ROLE ACCOUNTADMIN;
-- GRANT USAGE ON INTEGRATION JIRA_ATLASSIAN_MCP_INTEGRATION TO ROLE ACCOUNTADMIN;


-- ============================================================================
-- OPTION B: CUSTOM STORED PROCEDURE MCP SERVER
-- ============================================================================
-- Uses your existing Jira API token (from secrets.toml) wrapped in stored
-- procedures that the MCP server exposes as tools.

-- 1. Network Rule for Jira Cloud API
CREATE OR REPLACE NETWORK RULE JIRA_API_NETWORK_RULE
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ('sidsn7-1786720131938.atlassian.net:443');

-- 2. Secret for Jira API credentials
-- UPDATE the api_token value with your actual Jira API token:
-- Generate at: https://id.atlassian.com/manage-profile/security/api-tokens
CREATE OR REPLACE SECRET JIRA_API_CREDENTIALS
  TYPE = GENERIC_STRING
  SECRET_STRING = '{"url":"https://sidsn7-1786720131938.atlassian.net","email":"siddharthasankar.nath@merkle.com","api_token":"YOUR_TOKEN_HERE","project_key":"KAN"}';

-- To update the token later:
-- ALTER SECRET PM_OEE_DB.CORE.JIRA_API_CREDENTIALS SET SECRET_STRING = '{"url":"...","email":"...","api_token":"REAL_TOKEN","project_key":"KAN"}';

-- 3. External Access Integration
-- NOTE: Not available on Trial accounts. Upgrade to Standard/Enterprise to enable.
CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION JIRA_API_ACCESS
  ALLOWED_NETWORK_RULES = (PM_OEE_DB.CORE.JIRA_API_NETWORK_RULE)
  ALLOWED_AUTHENTICATION_SECRETS = (PM_OEE_DB.CORE.JIRA_API_CREDENTIALS)
  ENABLED = TRUE;

-- 4. Stored Procedure: CREATE JIRA TICKET
CREATE OR REPLACE PROCEDURE PM_OEE_DB.CORE.MCP_JIRA_CREATE_TICKET(
    MACHINE_ID VARCHAR,
    SEVERITY VARCHAR,
    SUMMARY VARCHAR,
    DESCRIPTION VARCHAR,
    WORK_ORDER_ID VARCHAR
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'requests')
HANDLER = 'create_ticket'
EXTERNAL_ACCESS_INTEGRATIONS = (JIRA_API_ACCESS)
SECRETS = ('jira_creds' = JIRA_API_CREDENTIALS)
AS
$$
import json
import requests
import base64
import _snowflake

def create_ticket(session, machine_id, severity, summary, description, work_order_id):
    # Load credentials from secret
    creds_json = _snowflake.get_generic_secret_string('jira_creds')
    creds = json.loads(creds_json)

    url = creds["url"].rstrip("/")
    email = creds["email"]
    api_token = creds["api_token"]
    project_key = creds.get("project_key", "KAN")

    # Check for duplicate via JQL
    jql = f'project = {project_key} AND summary ~ "{machine_id}" AND summary ~ "{work_order_id}" AND status != Done'
    search_url = f"{url}/rest/api/3/search"
    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        search_resp = requests.get(search_url, headers=headers, params={"jql": jql, "maxResults": 1}, timeout=15)
        if search_resp.status_code == 200 and search_resp.json().get("total", 0) > 0:
            existing = search_resp.json()["issues"][0]
            return {
                "status": "ALREADY_EXISTS",
                "jira_key": existing["key"],
                "jira_url": f"{url}/browse/{existing['key']}",
                "message": f"Duplicate ticket found: {existing['key']}"
            }
    except Exception:
        pass  # Proceed to create if search fails

    # Map severity to priority
    priority_map = {"CRITICAL": "Highest", "HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}
    priority_name = priority_map.get(severity.upper(), "Medium")

    # Create ticket
    create_url = f"{url}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
            },
            "issuetype": {"name": "Task"},
            "priority": {"name": priority_name},
            "labels": ["predictive-maintenance", "auto-generated", f"machine-{machine_id.lower().replace(' ', '-')}"]
        }
    }

    resp = requests.post(create_url, headers=headers, json=payload, timeout=30)

    if resp.status_code == 201:
        issue = resp.json()
        issue_key = issue["key"]
        issue_url = f"{url}/browse/{issue_key}"

        # Audit log
        try:
            session.sql(f"""
                INSERT INTO PM_OEE_DB.CORE.JIRA_TICKET_AUDIT
                (WORK_ORDER_ID, MACHINE_ID, JIRA_ISSUE_KEY, JIRA_ISSUE_URL, JIRA_PROJECT, ISSUE_TYPE, STATUS)
                VALUES ('{work_order_id}', '{machine_id}', '{issue_key}', '{issue_url}', '{project_key}', 'Task', 'CREATED')
            """).collect()
        except Exception:
            pass

        return {
            "status": "SUCCESS",
            "jira_key": issue_key,
            "jira_url": issue_url,
            "message": f"Jira ticket {issue_key} created successfully"
        }
    else:
        return {
            "status": "FAILED",
            "message": f"HTTP {resp.status_code}: {resp.text[:300]}",
            "jira_key": None,
            "jira_url": None
        }
$$;

-- 5. Stored Procedure: SEARCH JIRA TICKETS
CREATE OR REPLACE PROCEDURE PM_OEE_DB.CORE.MCP_JIRA_SEARCH_TICKETS(
    QUERY VARCHAR
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'requests')
HANDLER = 'search_tickets'
EXTERNAL_ACCESS_INTEGRATIONS = (JIRA_API_ACCESS)
SECRETS = ('jira_creds' = JIRA_API_CREDENTIALS)
AS
$$
import json
import requests
import base64
import _snowflake

def search_tickets(session, query):
    creds_json = _snowflake.get_generic_secret_string('jira_creds')
    creds = json.loads(creds_json)

    url = creds["url"].rstrip("/")
    email = creds["email"]
    api_token = creds["api_token"]
    project_key = creds.get("project_key", "KAN")

    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Build JQL from natural language query or pass through if already JQL
    if "=" in query or "ORDER BY" in query.upper():
        jql = query
    else:
        jql = f'project = {project_key} AND text ~ "{query}" ORDER BY created DESC'

    search_url = f"{url}/rest/api/3/search"
    params = {"jql": jql, "maxResults": 10, "fields": "summary,status,priority,assignee,created,updated"}

    try:
        resp = requests.get(search_url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            issues = []
            for issue in data.get("issues", []):
                fields = issue["fields"]
                issues.append({
                    "key": issue["key"],
                    "summary": fields.get("summary", ""),
                    "status": fields.get("status", {}).get("name", "Unknown"),
                    "priority": fields.get("priority", {}).get("name", "None"),
                    "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
                    "created": fields.get("created", ""),
                    "url": f"{url}/browse/{issue['key']}"
                })
            return {"status": "SUCCESS", "total": data.get("total", 0), "issues": issues}
        else:
            return {"status": "FAILED", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)[:300]}
$$;

-- 6. Stored Procedure: GET TICKET STATUS
CREATE OR REPLACE PROCEDURE PM_OEE_DB.CORE.MCP_JIRA_GET_TICKET_STATUS(
    ISSUE_KEY VARCHAR
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'requests')
HANDLER = 'get_status'
EXTERNAL_ACCESS_INTEGRATIONS = (JIRA_API_ACCESS)
SECRETS = ('jira_creds' = JIRA_API_CREDENTIALS)
AS
$$
import json
import requests
import base64
import _snowflake

def get_status(session, issue_key):
    creds_json = _snowflake.get_generic_secret_string('jira_creds')
    creds = json.loads(creds_json)

    url = creds["url"].rstrip("/")
    email = creds["email"]
    api_token = creds["api_token"]

    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json"
    }

    issue_url = f"{url}/rest/api/3/issue/{issue_key}"
    params = {"fields": "summary,status,priority,assignee,reporter,created,updated,comment"}

    try:
        resp = requests.get(issue_url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            fields = data["fields"]
            comments = fields.get("comment", {}).get("comments", [])
            latest_comments = [{"author": c["author"]["displayName"], "body": c["body"]["content"][0]["content"][0]["text"] if c.get("body", {}).get("content") else "", "created": c["created"]} for c in comments[-3:]]

            return {
                "status": "SUCCESS",
                "key": issue_key,
                "summary": fields.get("summary", ""),
                "ticket_status": fields.get("status", {}).get("name", "Unknown"),
                "priority": fields.get("priority", {}).get("name", "None"),
                "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
                "reporter": (fields.get("reporter") or {}).get("displayName", "Unknown"),
                "created": fields.get("created", ""),
                "updated": fields.get("updated", ""),
                "recent_comments": latest_comments,
                "url": f"{url}/browse/{issue_key}"
            }
        elif resp.status_code == 404:
            return {"status": "NOT_FOUND", "message": f"Issue {issue_key} not found"}
        else:
            return {"status": "FAILED", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)[:300]}
$$;

-- 7. Stored Procedure: ADD COMMENT TO TICKET
CREATE OR REPLACE PROCEDURE PM_OEE_DB.CORE.MCP_JIRA_ADD_COMMENT(
    ISSUE_KEY VARCHAR,
    COMMENT_TEXT VARCHAR
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python', 'requests')
HANDLER = 'add_comment'
EXTERNAL_ACCESS_INTEGRATIONS = (JIRA_API_ACCESS)
SECRETS = ('jira_creds' = JIRA_API_CREDENTIALS)
AS
$$
import json
import requests
import base64
import _snowflake

def add_comment(session, issue_key, comment_text):
    creds_json = _snowflake.get_generic_secret_string('jira_creds')
    creds = json.loads(creds_json)

    url = creds["url"].rstrip("/")
    email = creds["email"]
    api_token = creds["api_token"]

    auth = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    comment_url = f"{url}/rest/api/3/issue/{issue_key}/comment"
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment_text}]}]
        }
    }

    try:
        resp = requests.post(comment_url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 201:
            return {"status": "SUCCESS", "message": f"Comment added to {issue_key}", "issue_key": issue_key}
        else:
            return {"status": "FAILED", "message": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)[:300]}
$$;


-- ============================================================================
-- 8. MCP SERVER: Expose Jira stored procedures as MCP tools
-- ============================================================================
CREATE OR REPLACE MCP SERVER PM_OEE_DB.CORE.MFG_JIRA_MCP_SERVER
  FROM SPECIFICATION $$
  tools:
    - title: "Create Jira Maintenance Ticket"
      name: "create_maintenance_ticket"
      identifier: "PM_OEE_DB.CORE.MCP_JIRA_CREATE_TICKET"
      type: "GENERIC"
      description: "Creates a Jira ticket for a machine maintenance work order. Use when a machine has a critical failure, elevated risk, or needs scheduled maintenance. Includes duplicate protection."
      config:
        type: "procedure"
        warehouse: "COMPUTE_WH"
        input_schema:
          type: "object"
          properties:
            MACHINE_ID:
              type: "string"
              description: "Machine identifier (e.g. Machine_03)"
            SEVERITY:
              type: "string"
              description: "Alert severity: CRITICAL, HIGH, MEDIUM, or LOW"
            SUMMARY:
              type: "string"
              description: "Ticket title/summary describing the maintenance need"
            DESCRIPTION:
              type: "string"
              description: "Detailed description including telemetry readings, risk scores, and recommended actions"
            WORK_ORDER_ID:
              type: "string"
              description: "Associated work order ID (e.g. WO-10023)"
          required: ["MACHINE_ID", "SEVERITY", "SUMMARY", "DESCRIPTION", "WORK_ORDER_ID"]

    - title: "Search Jira Tickets"
      name: "search_jira_tickets"
      identifier: "PM_OEE_DB.CORE.MCP_JIRA_SEARCH_TICKETS"
      type: "GENERIC"
      description: "Search for existing Jira maintenance tickets. Accepts natural language queries or JQL. Returns matching tickets with status, priority, and assignee."
      config:
        type: "procedure"
        warehouse: "COMPUTE_WH"
        input_schema:
          type: "object"
          properties:
            QUERY:
              type: "string"
              description: "Search query - either natural language (e.g. 'Machine_03 bearing') or JQL syntax"
          required: ["QUERY"]

    - title: "Get Jira Ticket Status"
      name: "get_ticket_status"
      identifier: "PM_OEE_DB.CORE.MCP_JIRA_GET_TICKET_STATUS"
      type: "GENERIC"
      description: "Get detailed status of a specific Jira ticket including current state, assignee, priority, and recent comments."
      config:
        type: "procedure"
        warehouse: "COMPUTE_WH"
        input_schema:
          type: "object"
          properties:
            ISSUE_KEY:
              type: "string"
              description: "Jira issue key (e.g. KAN-42)"
          required: ["ISSUE_KEY"]

    - title: "Add Comment to Jira Ticket"
      name: "add_ticket_comment"
      identifier: "PM_OEE_DB.CORE.MCP_JIRA_ADD_COMMENT"
      type: "GENERIC"
      description: "Add a comment to an existing Jira maintenance ticket. Use for status updates, diagnostic results, or maintenance notes."
      config:
        type: "procedure"
        warehouse: "COMPUTE_WH"
        input_schema:
          type: "object"
          properties:
            ISSUE_KEY:
              type: "string"
              description: "Jira issue key (e.g. KAN-42)"
            COMMENT_TEXT:
              type: "string"
              description: "Comment text to add to the ticket"
          required: ["ISSUE_KEY", "COMMENT_TEXT"]
  $$;

-- Grant access
GRANT USAGE ON MCP SERVER PM_OEE_DB.CORE.MFG_JIRA_MCP_SERVER TO ROLE ACCOUNTADMIN;
GRANT USAGE ON PROCEDURE PM_OEE_DB.CORE.MCP_JIRA_CREATE_TICKET(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR) TO ROLE ACCOUNTADMIN;
GRANT USAGE ON PROCEDURE PM_OEE_DB.CORE.MCP_JIRA_SEARCH_TICKETS(VARCHAR) TO ROLE ACCOUNTADMIN;
GRANT USAGE ON PROCEDURE PM_OEE_DB.CORE.MCP_JIRA_GET_TICKET_STATUS(VARCHAR) TO ROLE ACCOUNTADMIN;
GRANT USAGE ON PROCEDURE PM_OEE_DB.CORE.MCP_JIRA_ADD_COMMENT(VARCHAR, VARCHAR) TO ROLE ACCOUNTADMIN;


-- ============================================================================
-- 9. CORTEX AGENT: MFG Maintenance Agent with Jira MCP Tools
-- ============================================================================
CREATE OR REPLACE AGENT PM_OEE_DB.CORE.MFG_MAINTENANCE_AGENT
  FROM SPECIFICATION $$
models:
  orchestration: auto
instructions:
  response: |
    You are the MFG Predictive Maintenance AI Agent. You help plant engineers
    manage machine maintenance by creating Jira tickets, checking ticket status,
    and providing maintenance recommendations based on machine telemetry data.
    Always include the machine ID, severity level, and relevant sensor readings
    when creating tickets. Use search before creating to avoid duplicates.
  orchestration: |
    When asked to create a maintenance ticket:
    1. First search for existing tickets for that machine to avoid duplicates
    2. If no duplicate exists, create the ticket with full context
    3. Report back the ticket key and URL

    When asked about ticket status:
    1. Look up the ticket by key
    2. Summarize current status, assignee, and any recent comments

    When asked to update a ticket:
    1. Add a comment with the diagnostic or status update
tools:
  - tool_spec:
      type: generic
      name: create_maintenance_ticket
      description: "Creates a Jira ticket for machine maintenance. Includes duplicate protection."
      input_schema:
        type: object
        properties:
          MACHINE_ID:
            type: string
            description: "Machine identifier (e.g. Machine_03)"
          SEVERITY:
            type: string
            description: "CRITICAL, HIGH, MEDIUM, or LOW"
          SUMMARY:
            type: string
            description: "Ticket summary/title"
          DESCRIPTION:
            type: string
            description: "Full description with telemetry and recommendations"
          WORK_ORDER_ID:
            type: string
            description: "Work order ID (e.g. WO-10023)"
        required: ["MACHINE_ID", "SEVERITY", "SUMMARY", "DESCRIPTION", "WORK_ORDER_ID"]
  - tool_spec:
      type: generic
      name: search_jira_tickets
      description: "Search Jira for maintenance tickets by keyword or JQL"
      input_schema:
        type: object
        properties:
          QUERY:
            type: string
            description: "Search text or JQL query"
        required: ["QUERY"]
  - tool_spec:
      type: generic
      name: get_ticket_status
      description: "Get detailed status of a Jira ticket by key"
      input_schema:
        type: object
        properties:
          ISSUE_KEY:
            type: string
            description: "Jira issue key (e.g. KAN-42)"
        required: ["ISSUE_KEY"]
  - tool_spec:
      type: generic
      name: add_ticket_comment
      description: "Add a comment to a Jira ticket"
      input_schema:
        type: object
        properties:
          ISSUE_KEY:
            type: string
            description: "Jira issue key"
          COMMENT_TEXT:
            type: string
            description: "Comment to add"
        required: ["ISSUE_KEY", "COMMENT_TEXT"]
tool_resources:
  create_maintenance_ticket:
    identifier: PM_OEE_DB.CORE.MCP_JIRA_CREATE_TICKET
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: "COMPUTE_WH"
  search_jira_tickets:
    identifier: PM_OEE_DB.CORE.MCP_JIRA_SEARCH_TICKETS
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: "COMPUTE_WH"
  get_ticket_status:
    identifier: PM_OEE_DB.CORE.MCP_JIRA_GET_TICKET_STATUS
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: "COMPUTE_WH"
  add_ticket_comment:
    identifier: PM_OEE_DB.CORE.MCP_JIRA_ADD_COMMENT
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: "COMPUTE_WH"
$$;

GRANT USAGE ON AGENT PM_OEE_DB.CORE.MFG_MAINTENANCE_AGENT TO ROLE ACCOUNTADMIN;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SHOW MCP SERVERS IN SCHEMA PM_OEE_DB.CORE;
SHOW AGENTS IN SCHEMA PM_OEE_DB.CORE;
DESCRIBE MCP SERVER PM_OEE_DB.CORE.MFG_JIRA_MCP_SERVER;
DESCRIBE AGENT PM_OEE_DB.CORE.MFG_MAINTENANCE_AGENT;
