"""
pages/what_if_simulator.py
What-if Simulator View
"""
import streamlit as st
import pandas as pd
from config import table
from services.scenario_service import SCENARIOS, inject_scenario_to_snowflake


def render_what_if_simulator(session, risk_df, oee_df, parts_df, qexec, safe_rerun):
    st.subheader("🎛️ Interactive Predictive Failure Simulator & What-If Sandbox")
    st.caption("Test real-time sensor degradation scenarios against Cortex ML z-score risk algorithms & RUL extrapolation.")

    sim_c1, sim_c2 = st.columns([1, 1])

    with sim_c1:
        st.markdown("#### 🎚️ Live Scenario Telemetry Controls")
        sim_m = st.selectbox("Target Equipment", [
            "Machine_03 (Precision Mill C)",
            "Machine_02 (CNC Spindle B)",
            "Machine_01 (CNC Spindle A)",
            "Machine_04 (Precision Mill D)"
        ])
        s_vib = st.slider("Vibration Level (mm/s)", 0.5, 12.0, 6.15, 0.05, key="sim_vib_slider")
        s_temp = st.slider("Spindle Temperature (°C)", 40.0, 120.0, 97.3, 0.5, key="sim_temp_slider")
        s_rpm = st.slider("RPM Speed", 800, 2400, 1552, 10, key="sim_rpm_slider")

        # Real-time Cortex ML Z-score calculation
        zv = max(0.0, (s_vib - 2.0) / 0.5)
        zt = max(0.0, (s_temp - 65.0) / 5.0)
        urisk = min(1.0, (0.4 * zv + 0.6 * zt) / 4.5)
        fprob = int(urisk * 100)
        srul = max(0.0, round(24.0 * (1.0 - urisk), 1))
        dcost = int((4.0 if urisk >= 0.70 else (2.0 if urisk >= 0.40 else 0.0)) * 3125.0)

        st.divider()
        if st.button("⚡ DISPATCH GOVERNED WORK ORDER TO SNOWFLAKE", use_container_width=True, type="primary"):
            mid = sim_m.split()[0]
            wo_tbl = table("WORK_ORDERS")
            session.sql(f"""
                INSERT INTO {wo_tbl} (
                    machine_id, priority, status, diagnosis, recommended_action,
                    parts_required, estimated_downtime_hours, risk_score, rul_hours, created_at
                ) VALUES (
                    ?, 'P1', 'PENDING_APPROVAL',
                    ?,
                    'Stop machine, inspect spindle raceway, replace bearing',
                    'SKF-6205-2RS', 4.0, ?, ?, CURRENT_TIMESTAMP()
                )
            """, params=[
                mid,
                f"Simulated failure: Spindle vibration {s_vib} mm/s, Temp {s_temp} °C",
                round(urisk, 2),
                round(srul, 1)
            ]).collect()
            st.success(f"Work Order drafted & persisted directly into Snowflake WORK_ORDERS table for {mid}!")

    with sim_c2:
        st.markdown("#### 📊 Real-Time Predictive Risk Gauge & Financial Impact")

        # Risk Gauge — HTML/CSS replacement
        gauge_color = "#DC2626" if urisk >= 0.70 else ("#D97706" if urisk >= 0.40 else "#16A34A")
        gauge_label = "CRITICAL" if urisk >= 0.70 else ("WARNING" if urisk >= 0.40 else "HEALTHY")
        st.markdown(
            f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:20px; text-align:center;">'
            f'<div style="font-size:0.85rem; font-weight:600; color:#64748B; margin-bottom:8px;">Predicted Failure Risk (%)</div>'
            f'<div style="font-size:3rem; font-weight:800; color:{gauge_color};">{fprob}%</div>'
            f'<div style="margin:10px auto; width:80%; background:#F1F5F9; border-radius:8px; height:18px; overflow:hidden;">'
            f'<div style="width:{fprob}%; height:100%; border-radius:8px; background:linear-gradient(90deg, #DCFCE7 0%, #FEF3C7 40%, #FEE2E2 70%, #DC2626 100%);"></div></div>'
            f'<span style="background:{gauge_color}20; color:{gauge_color}; font-weight:700; padding:3px 12px; border-radius:8px; font-size:0.75rem;">{gauge_label}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            f'<div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px; padding:14px 18px; margin-top:8px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; font-size:0.92rem; font-weight:700; color:#0F172A;">'
            f'<span>Estimated RUL: <strong style="color:#2563EB;">{srul} Hours</strong></span>'
            f'<span>Financial Risk: <strong style="color:#DC2626;">${dcost:,} USD</strong></span>'
            f'</div>'
            f'<div style="font-size:0.82rem; color:#475569; margin-top:6px; font-weight:500;">'
            f'Cortex ML Z-Scores: Vibration <strong>{zv:.1f}σ</strong> | Temp <strong>{zt:.1f}σ</strong> | Stock Match: <span style="background:#F1F5F9; color:#2563EB; font-weight:700; padding:1px 6px; border-radius:4px;">SKF-6205-2RS</span> (4 units on hand)'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    # ------------------------------------------------------------------
    # TAB 4: GOVERNED WORK ORDERS
    # ------------------------------------------------------------------



