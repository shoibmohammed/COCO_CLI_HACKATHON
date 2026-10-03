"""
components/header.py
Application Header — Real Interactive Enterprise SaaS Controls.
Provides interactive native Streamlit controls for:
1. Plant Selector (st.selectbox -> st.session_state["selected_plant"])
2. Date Range Picker (st.date_input -> st.session_state["selected_date_range"])
3. Notification Button (st.button -> navigates to Alert Triage)
4. Avatar Profile Button (st.button -> toggles secure session profile card)

Python 3.8 safe (clean string concatenation, no nested quote f-strings).
"""

import datetime
import streamlit as st


def safe_rerun():
    """Trigger a Streamlit page rerun safely across all Streamlit runtime versions."""
    if hasattr(st, "rerun"):
        try:
            st.rerun()
            return
        except Exception:
            pass
    if hasattr(st, "experimental_rerun"):
        try:
            st.experimental_rerun()
            return
        except Exception:
            pass


def render_header(plant_name: str = "All Plants", alert_count: int = 3, session=None):
    """
    Renders the unified enterprise command center header with fully interactive native Streamlit controls.
    """
    # 1. Initialize stable session state defaults
    if "selected_plant" not in st.session_state:
        st.session_state["selected_plant"] = plant_name if plant_name else "All Plants"

    if "selected_date_range" not in st.session_state:
        st.session_state["selected_date_range"] = (datetime.date(2025, 5, 15), datetime.date(2025, 5, 21))

    if "show_user_profile" not in st.session_state:
        st.session_state["show_user_profile"] = False

    # 2. Header Layout: Left (Title/Subtitle) | Right (Interactive Controls)
    head_left, head_right = st.columns([1.45, 1.55])

    with head_left:
        st.markdown(
            '<div style="padding: 2px 0 6px 0;">'
            '<h1 style="'
            'margin:0;'
            'font-size:1.45rem;'
            'font-weight:800;'
            'color:#0F172A;'
            'letter-spacing:-0.02em;'
            'line-height:1.2;'
            'white-space:nowrap;'
            'overflow:hidden;'
            'text-overflow:ellipsis;'
            '">'
            'MFG Predictive Maintenance &amp; OEE Command Center'
            '</h1>'
            '<p style="margin:2px 0 0 0; font-size:0.80rem; color:#64748B; font-weight:500; line-height:1.3;">'
            'Real-time intelligence to predict, prevent and perform'
            '</p>'
            '</div>',
            unsafe_allow_html=True
        )

    with head_right:
        # Four aligned sub-columns for native interactive controls
        c_plant, c_date, c_bell, c_avatar = st.columns([1.4, 1.7, 0.75, 0.55])

        # Control 1: Plant Selector (st.selectbox)
        with c_plant:
            plant_options = ["All Plants", "Plant A", "Plant B"]
            current_plant = st.session_state.get("selected_plant", "All Plants")
            try:
                plant_idx = plant_options.index(current_plant)
            except ValueError:
                plant_idx = 0

            selected_plant = st.selectbox(
                "Select Plant",
                options=plant_options,
                index=plant_idx,
                key="header_plant_select",
                label_visibility="collapsed",
                help="Filter dashboard metrics by manufacturing plant"
            )
            if selected_plant != st.session_state.get("selected_plant"):
                st.session_state["selected_plant"] = selected_plant
                safe_rerun()

        # Control 2: Date Range Selector (st.date_input)
        with c_date:
            cur_date_val = st.session_state.get(
                "selected_date_range",
                (datetime.date(2025, 5, 15), datetime.date(2025, 5, 21))
            )
            selected_date = st.date_input(
                "Date Range",
                value=cur_date_val,
                key="header_date_picker",
                label_visibility="collapsed",
                help="Historical metric & telemetry analysis window"
            )
            if selected_date != st.session_state.get("selected_date_range"):
                st.session_state["selected_date_range"] = selected_date

        # Control 3: Notification Bell (st.button -> Navigate to Alert Triage)
        with c_bell:
            disp_count = str(alert_count) if alert_count is not None else "3"
            if st.button(
                "🔔 " + disp_count,
                key="header_btn_alerts",
                type="secondary",
                use_container_width=True,
                help="Active Alerts: Click to open Alert Triage"
            ):
                st.session_state["nav_index"] = 1  # 🚨 Alert Triage
                safe_rerun()

        # Control 4: Avatar Profile (st.button -> Toggle Profile Popover)
        with c_avatar:
            if st.button(
                "AD",
                key="header_btn_avatar",
                type="primary",
                use_container_width=True,
                help="Administrator Profile (AD): Click to toggle user info"
            ):
                st.session_state["show_user_profile"] = not st.session_state.get("show_user_profile", False)
                safe_rerun()

    # 3. Secure User Profile Status Card (when toggled via Avatar button)
    if st.session_state.get("show_user_profile", False):
        active_plant = str(st.session_state.get("selected_plant", "All Plants"))
        profile_html = (
            '<div style="'
            'background:#FFFFFF;'
            'border:1px solid #CBD5E1;'
            'border-left:4px solid #2563EB;'
            'border-radius:10px;'
            'padding:12px 18px;'
            'margin:8px 0 14px 0;'
            'box-shadow:0 2px 6px rgba(0,0,0,0.05);'
            'display:flex;'
            'justify-content:space-between;'
            'align-items:center;'
            '">'
            '<div>'
            '<div style="font-size:0.88rem; font-weight:800; color:#0F172A; display:flex; align-items:center; gap:6px;">'
            '<span>👤 Authenticated User:</span> <span style="color:#2563EB;">Administrator (AD)</span>'
            '</div>'
            '<div style="font-size:0.78rem; color:#475569; margin-top:3px;">'
            'Role: <strong style="color:#0F172A;">ACCOUNTADMIN / Operations Lead</strong> &nbsp;|&nbsp; '
            'Database: <strong style="color:#0F172A;">PM_OEE_DB.CORE</strong> &nbsp;|&nbsp; '
            'Active Plant Filter: <strong style="color:#2563EB;">' + active_plant + '</strong>'
            '</div>'
            '</div>'
            '</div>'
        )
        st.markdown(profile_html, unsafe_allow_html=True)
        col_close, _ = st.columns([1.2, 5])
        with col_close:
            if st.button("✕ Dismiss Profile", key="btn_close_header_profile", use_container_width=True):
                st.session_state["show_user_profile"] = False
                safe_rerun()

    # Subtle separator below header
    st.markdown('<div style="border-bottom:1px solid #E2E8F0; margin-bottom:14px; margin-top:2px;"></div>', unsafe_allow_html=True)
