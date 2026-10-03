"""
snowflake_connection.py
Unified connection manager for Snowflake Snowpark session.
Supports dual-mode execution:
1. In-Snowsight Streamlit deployment (get_active_session)
2. Local Streamlit execution (st.secrets, env variables, or interactive UI)
3. Local script execution (snowpark Session builder)
"""

import os
import platform
try:
    import streamlit as st
except ImportError:
    st = None

# Fix for Windows Store Python 3.13 reparse point bug in platform.libc_ver
platform.libc_ver = lambda *args, **kwargs: ("", "")

def get_snowflake_session():
    """
    Attempts to retrieve or establish a Snowflake Snowpark session using multiple fallback mechanisms.
    Returns: (session, status_message, is_local_mode)
    """
    # 1. Check if running inside Snowsight (Streamlit in Snowflake)
    try:
        from snowflake.snowpark.context import get_active_session
        session = get_active_session()
        if session is not None:
            try:
                _init_db_context(session)
            except Exception:
                pass
            return session, "Connected via Snowsight Active Session", False
    except Exception:
        pass

    # 2. Check if a session is already cached in Streamlit session state
    if hasattr(st, "session_state") and "snowflake_session" in st.session_state:
        try:
            session = st.session_state["snowflake_session"]
            if session is not None:
                try:
                    _init_db_context(session)
                except Exception:
                    pass
                return session, "Connected via active session state", True
        except Exception:
            if hasattr(st, "session_state"):
                st.session_state["snowflake_session"] = None

    # 3. Check Streamlit secrets (st.secrets["snowflake"])
    try:
        secrets_config = _get_secrets_safe()
        if secrets_config:
            try:
                from snowflake.snowpark import Session
                session = Session.builder.configs(secrets_config).create()
            except Exception:
                import snowflake.connector
                conn = snowflake.connector.connect(**secrets_config)
                session = conn
            _init_db_context(session)
            if hasattr(st, "session_state"):
                st.session_state["snowflake_session"] = session
            return session, "Connected via Streamlit secrets.toml", True
    except Exception:
        pass

    # 4. Check Environment Variables
    env_account = os.environ.get("SNOWFLAKE_ACCOUNT", "")
    env_user = os.environ.get("SNOWFLAKE_USER", "")
    env_password = os.environ.get("SNOWFLAKE_PASSWORD", "")
    if env_account and env_user and env_password:
        try:
            cfg = {
                "account": env_account,
                "user": env_user,
                "password": env_password,
                "role": os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
                "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "PM_OEE_WH"),
                "database": os.environ.get("SNOWFLAKE_DATABASE", "PM_OEE_DB"),
                "schema": os.environ.get("SNOWFLAKE_SCHEMA", "CORE"),
            }
            try:
                from snowflake.snowpark import Session
                session = Session.builder.configs(cfg).create()
            except Exception:
                import snowflake.connector
                session = snowflake.connector.connect(**cfg)
            _init_db_context(session)
            if hasattr(st, "session_state"):
                st.session_state["snowflake_session"] = session
            return session, "Connected via Environment Variables", True
        except Exception:
            pass

    return None, "No active Snowflake session found. Please configure connection parameters.", True


def connect_with_params(account, user, password, role="ACCOUNTADMIN", warehouse="PM_OEE_WH", database="PM_OEE_DB", schema="CORE"):
    """
    Establishes a new Snowpark session using explicit user-supplied parameters.
    """
    from snowflake.snowpark import Session
    cfg = {
        "account": account.strip(),
        "user": user.strip(),
        "password": password,
        "role": role.strip() or "ACCOUNTADMIN",
        "warehouse": warehouse.strip() or "PM_OEE_WH",
        "database": database.strip() or "PM_OEE_DB",
        "schema": schema.strip() or "CORE",
    }
    session = Session.builder.configs(cfg).create()
    _init_db_context(session)
    if hasattr(st, "session_state"):
        st.session_state["snowflake_session"] = session
    return session


def _get_secrets_safe():
    """
    Safely retrieves secrets without triggering file missing warnings in Snowflake native runtime.
    """
    try:
        if hasattr(st, "secrets") and len(st.secrets) > 0:
            if "snowflake" in st.secrets:
                return dict(st.secrets["snowflake"])
    except Exception:
        pass
    return None


def _init_db_context(session):
    """
    Ensures session is pointing to target database, schema, and warehouse using centralized config.
    """
    if session is None:
        return
    try:
        from config import DATABASE, SCHEMA, WAREHOUSE
        session.sql(f"USE DATABASE {DATABASE}").collect()
        session.sql(f"USE SCHEMA {SCHEMA}").collect()
        session.sql(f"USE WAREHOUSE {WAREHOUSE}").collect()
    except Exception:
        pass
