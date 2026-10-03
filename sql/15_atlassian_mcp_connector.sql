-- ============================================================
-- 15_atlassian_mcp_connector.sql
-- Sets up the Atlassian MCP Connector for Jira integration.
-- Uses Dynamic Client Registration (DCR) OAuth — NO EAI required.
-- Works on trial accounts.
-- ============================================================
--
-- PREREQUISITE (manual, one-time):
--   1. Go to admin.atlassian.com
--   2. Navigate to: Apps → AI Settings → Rovo MCP Server
--   3. Under "Your domains", click "Add Domain"
--   4. Add: https://identity.snowflake.com/oauth2/callback
--   5. Click "Add" and save
--
-- After running this script:
--   - Users authenticate via OAuth popup in CoWork or Streamlit
--   - Tools available: createJiraIssue, getJiraIssue, searchJiraIssues, etc.
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;

-- ============================================================
-- 1. API INTEGRATION (DCR OAuth — no client ID/secret needed)
-- ============================================================
-- NOTE: CREATE OR REPLACE is not supported for external_mcp integrations.
-- Use DROP + CREATE if you need to recreate.

CREATE API INTEGRATION IF NOT EXISTS JIRA_MCP_API_INTEGRATION
  API_PROVIDER = external_mcp
  API_ALLOWED_PREFIXES = ('https://mcp.atlassian.com')
  API_USER_AUTHENTICATION = (
    TYPE = OAUTH_DYNAMIC_CLIENT,
    OAUTH_RESOURCE_URL = 'https://mcp.atlassian.com/v1/mcp'
  )
  ENABLED = TRUE;

-- ============================================================
-- 2. EXTERNAL MCP SERVER
-- ============================================================
CREATE EXTERNAL MCP SERVER IF NOT EXISTS PM_OEE_DB.CORE.ATLASSIAN_MCP_SERVER
  WITH DISPLAY_NAME = 'Atlassian (Jira & Confluence)'
  URL = 'https://mcp.atlassian.com/v1/mcp'
  API_INTEGRATION = JIRA_MCP_API_INTEGRATION;

-- ============================================================
-- 3. GRANT ACCESS
-- ============================================================
-- Grant to PUBLIC for demo. In production, grant to specific roles.
GRANT USAGE ON EXTERNAL MCP SERVER PM_OEE_DB.CORE.ATLASSIAN_MCP_SERVER TO ROLE PUBLIC;
GRANT USAGE ON INTEGRATION JIRA_MCP_API_INTEGRATION TO ROLE PUBLIC;

-- ============================================================
-- 4. VERIFICATION
-- ============================================================
SHOW EXTERNAL MCP SERVERS;
DESCRIBE EXTERNAL MCP SERVER PM_OEE_DB.CORE.ATLASSIAN_MCP_SERVER;

-- ============================================================
-- USAGE NOTES
-- ============================================================
-- The Atlassian MCP connector provides these Jira tools automatically:
--   - createJiraIssue: Create a new Jira issue
--   - getJiraIssue: Get details of an existing issue
--   - searchJiraIssues: Search issues using JQL
--   - updateJiraIssue: Update an existing issue
--   - addJiraComment: Add a comment to an issue
--   - getJiraProject: Get project details
--
-- To use in a Cortex Agent, add the external MCP server to the
-- agent specification's tool_resources section.
--
-- To use in CoCo (Cortex Code), select the Atlassian connector
-- from the + menu in the CoCo composer. Each user authenticates
-- once via OAuth popup.
--
-- To recreate (if needed):
--   DROP EXTERNAL MCP SERVER IF EXISTS PM_OEE_DB.CORE.ATLASSIAN_MCP_SERVER;
--   DROP INTEGRATION IF EXISTS JIRA_MCP_API_INTEGRATION;
--   Then re-run this script.
-- ============================================================
