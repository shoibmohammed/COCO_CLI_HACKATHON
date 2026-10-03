"""
components/kpi_card.py
Enterprise 7-Metric KPI Card Strip with sparklines & circular badges.
Matches the MFG CMD CENTER dashboard design.
"""

try:
    import streamlit as st
except ImportError:
    st = None


def render_kpi_cards(
    oee_pct: float = 82.6,
    fleet_risk: float = 0.78,
    critical_count: int = 3,
    warning_count: int = 7,
    open_wo_count: int = 3,
    downtime_risk_usd: float = 0.0,
    running_count: int = 12
):
    """Renders 7 prominent executive KPI cards with circular colored icons and SVG sparklines."""
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)

    # Values — show actual data (including zeros after reset)
    disp_oee = f"{oee_pct:.1f}%"
    disp_risk = f"{fleet_risk:.2f}"
    disp_crit = str(critical_count)
    disp_warn = str(warning_count)
    disp_running = str(running_count)
    disp_wo = str(open_wo_count)
    # Convert dollar risk to hours estimate (approx $2000/hr downtime)
    if downtime_risk_usd > 0:
        dt_hrs = downtime_risk_usd / 2000.0
        disp_dt = f"{dt_hrs:.1f} hrs"
    else:
        disp_dt = "0.0 hrs"

    kpi_configs = [
        (
            c1,
            "OVERALL OEE",
            disp_oee,
            "↑ 4.2% vs 7d",
            "#16A34A",
            "#EFF6FF",
            "#2563EB",
            "📊",
            '<svg width="100%" height="18" viewBox="0 0 100 18" preserveAspectRatio="none" fill="none"><path d="M2 14L18 12L35 15L52 8L70 10L85 5L98 7" stroke="#2563EB" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        ),
        (
            c2,
            "FLEET RISK SCORE",
            disp_risk,
            "↑ 0.12 vs 24h",
            "#DC2626",
            "#FEF2F2",
            "#DC2626",
            "🛡️",
            '<svg width="100%" height="18" viewBox="0 0 100 18" preserveAspectRatio="none" fill="none"><path d="M2 10L18 12L35 7L52 13L70 5L85 11L98 3" stroke="#DC2626" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        ),
        (
            c3,
            "CRIT. MACH/FACS",
            disp_crit,
            "↑ 1 vs 24h",
            "#DC2626",
            "#FFF7ED",
            "#EA580C",
            "⚠️",
            '<svg width="100%" height="18" viewBox="0 0 100 18" preserveAspectRatio="none" fill="none"><path d="M2 13L18 15L35 11L52 12L70 6L85 9L98 3" stroke="#EA580C" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        ),
        (
            c4,
            "WARNING MACHINES",
            disp_warn,
            "↓ 2 vs 24h",
            "#16A34A",
            "#FEFCE8",
            "#CA8A04",
            "⏱️",
            '<svg width="100%" height="18" viewBox="0 0 100 18" preserveAspectRatio="none" fill="none"><path d="M2 5L18 9L35 7L52 13L70 11L85 15L98 12" stroke="#CA8A04" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        ),
        (
            c5,
            "RUNNING MACHINES",
            disp_running,
            "Stable",
            "#16A34A",
            "#F0FDF4",
            "#16A34A",
            "🏭",
            '<svg width="100%" height="18" viewBox="0 0 100 18" preserveAspectRatio="none" fill="none"><path d="M2 9L18 8L35 9L52 8L70 9L85 8L98 9" stroke="#16A34A" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        ),
        (
            c6,
            "OPEN WORK ORDERS",
            disp_wo,
            "↓ 1 vs 24h",
            "#16A34A",
            "#EFF6FF",
            "#2563EB",
            "📋",
            '<svg width="100%" height="18" viewBox="0 0 100 18" preserveAspectRatio="none" fill="none"><path d="M2 7L18 11L35 9L52 14L70 12L85 16L98 13" stroke="#2563EB" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        ),
        (
            c7,
            "DOWNTIME RISK",
            disp_dt,
            "↑ 1.8 hrs vs 24h",
            "#DC2626",
            "#FAF5FF",
            "#7C3AED",
            "⏳",
            '<svg width="100%" height="18" viewBox="0 0 100 18" preserveAspectRatio="none" fill="none"><path d="M2 14L18 11L35 13L52 8L70 11L85 4L98 6" stroke="#7C3AED" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        )
    ]

    for col, label, val, trend, trend_col, badge_bg, badge_border, icon, sparkline_svg in kpi_configs:
        with col:
            st.markdown(
                '<div style="'
                'background:#FFFFFF;'
                'padding:10px 12px;'
                'border-radius:12px;'
                'border:1px solid #E2E8F0;'
                'box-shadow:0 1px 3px rgba(0,0,0,0.03);'
                'margin-bottom:12px;'
                'box-sizing:border-box;'
                'min-width:0;'
                '">'
                '<div style="display:flex; justify-content:space-between; align-items:flex-start;">'
                '<div style="font-size:0.58rem; color:#64748B; font-weight:700; letter-spacing:0.03em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">'
                + str(label) +
                '</div>'
                '<div style="background:' + str(badge_bg) + '; width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:0.65rem; flex-shrink:0; border:1px solid ' + str(badge_border) + '44;">'
                + str(icon) +
                '</div>'
                '</div>'
                '<div style="font-size:1.35rem; font-weight:800; color:#0F172A; margin-top:3px; letter-spacing:-0.02em; line-height:1.1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">'
                + str(val) +
                '</div>'
                '<div style="font-size:0.62rem; color:' + str(trend_col) + '; font-weight:600; margin-top:3px; margin-bottom:5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">'
                + str(trend) +
                '</div>'
                '<div style="margin-top:2px;">'
                + str(sparkline_svg) +
                '</div>'
                '</div>',
                unsafe_allow_html=True
            )
