-- ============================================================
-- 02_documents_and_cortex_search.sql
-- Upload PDFs to @MAINTENANCE_DOC_STAGE before running the parse section.
-- The script uses AI_PARSE_DOCUMENT + Cortex Search.
-- ============================================================

USE DATABASE PM_OEE_DB;
USE SCHEMA CORE;
USE WAREHOUSE PM_OEE_WH;

-- If you have uploaded PDFs through Snowsight/SnowSQL:
-- PUT file:///absolute/path/Precision_Mill_Bearing_Manual.pdf @MAINTENANCE_DOC_STAGE
--     AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
-- PUT file:///absolute/path/Coolant_System_SOP.pdf @MAINTENANCE_DOC_STAGE
--     AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
-- PUT file:///absolute/path/Spindle_Drive_Belt_SOP.pdf @MAINTENANCE_DOC_STAGE
--     AUTO_COMPRESS=FALSE OVERWRITE=TRUE;
-- ALTER STAGE MAINTENANCE_DOC_STAGE REFRESH;

-- Inspect staged files:
SELECT RELATIVE_PATH, SIZE, LAST_MODIFIED
FROM DIRECTORY(@MAINTENANCE_DOC_STAGE)
ORDER BY RELATIVE_PATH;

-- ------------------------------------------------------------
-- Parse PDFs into page-level text using Snowflake Cortex.
-- AI_PARSE_DOCUMENT supports PDF and returns structured content.
-- ------------------------------------------------------------
CREATE OR REPLACE TABLE MAINTENANCE_DOC_PAGES AS
SELECT
    RELATIVE_PATH AS source_file,
    p.value:index::NUMBER AS page_number,
    p.value:content::VARCHAR AS page_text,
    BUILD_SCOPED_FILE_URL(@MAINTENANCE_DOC_STAGE, RELATIVE_PATH) AS file_url
FROM DIRECTORY(@MAINTENANCE_DOC_STAGE),
     LATERAL FLATTEN(
       INPUT => AI_PARSE_DOCUMENT(
         TO_FILE('@PM_OEE_DB.CORE.MAINTENANCE_DOC_STAGE', RELATIVE_PATH),
         {'mode':'LAYOUT', 'page_split':true}
       ):pages
     ) p
WHERE LOWER(RELATIVE_PATH) LIKE '%.pdf';

-- ------------------------------------------------------------
-- Chunk the parsed pages for retrieval.
-- ------------------------------------------------------------
TRUNCATE TABLE MAINTENANCE_DOCS;

INSERT INTO MAINTENANCE_DOCS
    (source_file, page_number, chunk_text, file_url)
SELECT
    source_file,
    page_number,
    c.value:chunk::VARCHAR AS chunk_text,
    file_url
FROM MAINTENANCE_DOC_PAGES,
LATERAL FLATTEN(
    INPUT => SNOWFLAKE.CORTEX.SPLIT_TEXT_MARKDOWN_HEADER(
        page_text,
        OBJECT_CONSTRUCT('#','header_1','##','header_2'),
        1800,
        250
    )
) c
WHERE NULLIF(TRIM(c.value:chunk::VARCHAR), '') IS NOT NULL;

ALTER TABLE MAINTENANCE_DOCS SET CHANGE_TRACKING = TRUE;

-- ------------------------------------------------------------
-- Managed semantic retrieval: hybrid keyword + vector search.
-- ON chunk_text creates a managed vector embedding index.
-- ------------------------------------------------------------
CREATE OR REPLACE CORTEX SEARCH SERVICE MAINTENANCE_DOCS_SEARCH
  ON chunk_text
  ATTRIBUTES source_file, page_number
  WAREHOUSE = PM_OEE_WH
  TARGET_LAG = '5 minutes'
  REFRESH_MODE = INCREMENTAL
  AS (
    SELECT
      (source_file || ':' || COALESCE(page_number::VARCHAR,'0') || ':' || chunk_id::VARCHAR) AS chunk_key,
      source_file,
      page_number,
      chunk_text,
      file_url
    FROM MAINTENANCE_DOCS
  );

SHOW CORTEX SEARCH SERVICES LIKE 'MAINTENANCE_DOCS_SEARCH';

-- Test the service after it has populated:
SELECT PARSE_JSON(
  SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
    'PM_OEE_DB.CORE.MAINTENANCE_DOCS_SEARCH',
    '{
      "query": "bearing vibration temperature failure",
      "columns": ["source_file","page_number","chunk_text","file_url"],
      "limit": 3
    }'
  )
)['results'] AS search_results;
