-- Snowflake-native deployment script for MFG Predictive Maintenance Command Center
-- Co-authored with CoCo

USE ROLE ACCOUNTADMIN;
USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

-- ============================================================
-- 1. NETWORK RULE: Allow outbound HTTPS to Google Gemini API
-- ============================================================
CREATE OR REPLACE NETWORK RULE GEMINI_API_NETWORK_RULE
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ('generativelanguage.googleapis.com:443', 'aiplatform.googleapis.com:443');

-- ============================================================
-- 2. SECRET: Store Gemini API Key securely
-- ============================================================
CREATE OR REPLACE SECRET GEMINI_API_KEY_SECRET
  TYPE = GENERIC_STRING
  SECRET_STRING = '<YOUR_GEMINI_API_KEY_HERE>';
  -- Replace with your actual Gemini API key

-- ============================================================
-- 3. EXTERNAL ACCESS INTEGRATION: Combine network rule + secret
-- ============================================================
-- NOTE: External Access Integrations are NOT supported on trial accounts.
-- On a production (Enterprise) account, uncomment the following:
--
-- CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION GEMINI_API_ACCESS
--   ALLOWED_NETWORK_RULES = (GEMINI_API_NETWORK_RULE)
--   ALLOWED_AUTHENTICATION_SECRETS = (GEMINI_API_KEY_SECRET)
--   ENABLED = TRUE
--   COMMENT = 'External access for Google Gemini AI API';
--
-- GRANT USAGE ON INTEGRATION GEMINI_API_ACCESS TO ROLE ACCOUNTADMIN;
--
-- WORKAROUND FOR TRIAL ACCOUNTS:
-- The app uses a deterministic heuristic fallback when Gemini API is unreachable.
-- For the hackathon demo, run the app via Snowsight Workspace (Streamlit in Snowflake)
-- which supports external network calls through the workspace runtime.

-- ============================================================
-- 5. VERIFY: Check everything is created
-- ============================================================
SHOW NETWORK RULES IN SCHEMA PM_OEE_DB.CORE;
SHOW SECRETS IN SCHEMA PM_OEE_DB.CORE;
SHOW EXTERNAL ACCESS INTEGRATIONS;

-- ============================================================
-- 6. CREATE STREAMLIT APP (Snowflake Warehouse Runtime)
-- ============================================================
-- Warehouse runtime loads dependencies strictly from Snowflake's
-- internal Anaconda Channel via environment.yml with zero PyPI/EAI calls.

CREATE OR REPLACE STREAMLIT PM_OEE_DB.CORE.MFG_PM_COMMAND_CENTER
  ROOT_LOCATION = '@PM_OEE_DB.CORE.MFG_PM_STREAMLIT_STAGE'
  MAIN_FILE = 'streamlit_app.py'
  QUERY_WAREHOUSE = PM_OEE_WH
  COMMENT = 'MFG Predictive Maintenance & OEE Command Center (Warehouse Runtime)';

-- ============================================================
-- 7. GRANT ACCESS
-- ============================================================
GRANT USAGE ON STREAMLIT PM_OEE_DB.CORE.MFG_PM_COMMAND_CENTER TO ROLE PUBLIC;
GRANT USAGE ON STREAMLIT PM_OEE_DB.CORE.MFG_PM_COMMAND_CENTER TO ROLE ACCOUNTADMIN;
