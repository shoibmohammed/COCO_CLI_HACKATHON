"""
components/theme.py
Centralized Enterprise Light SaaS CSS Theme & Styling Tokens
MFG Predictive Maintenance & OEE Command Center V7.3

Guarantees 100% readable text hierarchy across light backgrounds:
- PRIMARY:   #0F172A (Headings, metric values, bold labels)
- SECONDARY: #1E293B (Subheadings, body paragraphs)
- BODY:      #334155 (Standard body text, descriptions)
- MUTED:     #475569 (Captions, metadata, lineage notes)
- SIDEBAR:   #090D16 (Dark navy sidebar with crisp #F8FAFC text)
"""

import streamlit as st

ENTERPRISE_THEME_CSS = """
<style>
  /* ==========================================================================
     1. GLOBAL PAGE CANVAS & BASE TYPOGRAPHY (High-Contrast Slate)
     ========================================================================== */
  html, body, [data-testid="stAppViewContainer"], .stApp {
    background-color: #F8FAFC !important;
    color: #0F172A !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
  }

  .block-container {
    padding-top: 0.75rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 100% !important;
  }

  /* ==========================================================================
     2. UNIVERSAL TEXT & HEADINGS (Strict High-Contrast #0F172A / #1E293B)
     ========================================================================== */
  .main h1, .main h2, .main h3, .main h4, .main h5, .main h6,
  .main [data-testid="stMarkdownContainer"] h1,
  .main [data-testid="stMarkdownContainer"] h2,
  .main [data-testid="stMarkdownContainer"] h3,
  .main [data-testid="stMarkdownContainer"] h4,
  .main [data-testid="stMarkdownContainer"] h5,
  .main [data-testid="stMarkdownContainer"] h6,
  [data-testid="stAppViewContainer"] h1,
  [data-testid="stAppViewContainer"] h2,
  [data-testid="stAppViewContainer"] h3,
  [data-testid="stAppViewContainer"] h4,
  [data-testid="stAppViewContainer"] h5,
  [data-testid="stAppViewContainer"] h6 {
    color: #0F172A !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em !important;
  }

  .main p, .main li, .main label {
    color: #1E293B !important;
  }

  .main [data-testid="stMarkdownContainer"] > p,
  .main [data-testid="stMarkdownContainer"] > li,
  .main [data-testid="stMarkdownContainer"] > strong,
  .main [data-testid="stMarkdownContainer"] > em {
    color: #1E293B !important;
  }

  .main [data-testid="stMarkdownContainer"] > code {
    color: #0F172A !important;
  }

  /* Inline code formatting */
  .main [data-testid="stMarkdownContainer"] code {
    background-color: #F1F5F9 !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 4px !important;
    padding: 2px 6px !important;
    color: #0F172A !important;
    font-weight: 600 !important;
    font-size: 0.84em !important;
  }

  /* Subdued body text & captions */
  .stCaption,
  [data-testid="stCaptionContainer"],
  [data-testid="stCaptionContainer"] p,
  [data-testid="stCaptionContainer"] span {
    color: #475569 !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    line-height: 1.4 !important;
  }

  /* ==========================================================================
     3. NOTIFICATIONS & ALERTS (Clean Soft Contrast)
     ========================================================================== */
  .main [data-testid="stAlert"],
  .main [data-testid="stNotification"],
  .main [data-baseweb="notification"] {
    background-color: #EFF6FF !important;
    border: 1px solid #BFDBFE !important;
    border-radius: 8px !important;
    color: #1E3A8A !important;
  }

  .main [data-testid="stAlert"] *,
  .main [data-testid="stNotification"] *,
  .main [data-baseweb="notification"] * {
    color: #1E3A8A !important;
  }

  /* ==========================================================================
     4. WIDGET LABELS & FORM CONTROLS
     ========================================================================== */
  [data-testid="stWidgetLabel"] label,
  [data-testid="stWidgetLabel"] p,
  [data-testid="stWidgetLabel"] span {
    color: #0F172A !important;
    font-weight: 700 !important;
    font-size: 0.88rem !important;
  }

  .stSelectbox div[data-baseweb="select"] > div,
  .stTextInput input,
  .stTextArea textarea {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    font-size: 0.88rem !important;
  }

  .stSelectbox div[data-baseweb="select"] span {
    color: #0F172A !important;
    font-weight: 600 !important;
  }

  /* ==========================================================================
     6. BUTTONS & ACTIONS (Explicit readable states)
     ========================================================================== */
  .main button,
  [data-testid="stAppViewContainer"] button {
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    transition: all 0.15s ease-in-out !important;
  }

  /* Primary Button: Vibrant Royal Blue with crisp white text */
  .main button[kind="primary"],
  .main button[data-testid="baseButton-primary"],
  [data-testid="stAppViewContainer"] button[kind="primary"],
  [data-testid="stAppViewContainer"] button[data-testid="baseButton-primary"] {
    background-color: #2563EB !important;
    color: #FFFFFF !important;
    border: 1px solid #1D4ED8 !important;
    box-shadow: 0 1px 3px rgba(37,99,235,0.25) !important;
  }

  .main button[kind="primary"] *,
  .main button[data-testid="baseButton-primary"] * {
    color: #FFFFFF !important;
  }

  .main button[kind="primary"]:hover,
  .main button[data-testid="baseButton-primary"]:hover {
    background-color: #1D4ED8 !important;
    box-shadow: 0 2px 5px rgba(37,99,235,0.35) !important;
  }

  /* Secondary Button: Clean white background with high-contrast text (main area only) */
  .main button[kind="secondary"],
  .main button[data-testid="baseButton-secondary"] {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid #CBD5E1 !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
  }

  .main button[kind="secondary"] *,
  .main button[data-testid="baseButton-secondary"] * {
    color: #0F172A !important;
  }

  .main button[kind="secondary"]:hover,
  .main button[data-testid="baseButton-secondary"]:hover {
    background-color: #F1F5F9 !important;
    border-color: #94A3B8 !important;
    color: #0F172A !important;
  }

  /* ==========================================================================
     7. METRIC CARDS
     ========================================================================== */
  .stMetric {
    background-color: #FFFFFF !important;
    border-radius: 12px !important;
    padding: 14px 16px !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
  }

  .stMetric label {
    color: #64748B !important;
    font-size: 0.75rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
  }

  .stMetric [data-testid="stMetricValue"],
  .stMetric [data-testid="stMetricValue"] * {
    color: #0F172A !important;
    font-weight: 800 !important;
    font-size: 1.45rem !important;
  }

  .stMetric [data-testid="stMetricDelta"] {
    font-weight: 700 !important;
    font-size: 0.78rem !important;
  }

  /* ==========================================================================
     8. EXPANDERS & TABS
     ========================================================================== */
  [data-testid="stExpander"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03) !important;
    margin-bottom: 12px !important;
  }

  [data-testid="stExpander"] details summary,
  [data-testid="stExpander"] details summary p,
  [data-testid="stExpander"] details summary span {
    color: #0F172A !important;
    font-weight: 700 !important;
    font-size: 0.92rem !important;
  }

  [data-baseweb="tab-list"] {
    background-color: transparent !important;
    border-bottom: 2px solid #E2E8F0 !important;
    gap: 8px !important;
  }

  [data-baseweb="tab"] {
    color: #475569 !important;
    font-weight: 700 !important;
    font-size: 0.88rem !important;
    padding: 8px 16px !important;
  }

  [data-baseweb="tab"][aria-selected="true"] {
    color: #2563EB !important;
    border-bottom: 2px solid #2563EB !important;
  }

  /* ==========================================================================
     9. TABLES & DATAFRAMES
     ========================================================================== */
  [data-testid="stDataFrame"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    overflow: hidden !important;
  }

  /* ==========================================================================
     10. CODE & MONOSPACE BLOCKS
     ========================================================================== */
  .stCodeBlock, [data-testid="stCode"] {
    background-color: #0F172A !important;
    border: 1px solid #1E293B !important;
    border-radius: 8px !important;
  }

  .stCodeBlock code, [data-testid="stCode"] code, [data-testid="stCode"] pre {
    color: #E2E8F0 !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
  }

  /* ==========================================================================
     11. DARK NAVY SIDEBAR (Protected dark mode)
     ========================================================================== */
  [data-testid="stSidebar"] {
    background-color: #090D16 !important;
    border-right: 1px solid #1E293B !important;
  }

  [data-testid="stSidebar"] h1,
  [data-testid="stSidebar"] h2,
  [data-testid="stSidebar"] h3,
  [data-testid="stSidebar"] h4,
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] span,
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] div,
  [data-testid="stSidebar"] strong {
    color: #F8FAFC !important;
  }

  [data-testid="stSidebar"] .stCaption,
  [data-testid="stSidebar"] [data-testid="stCaptionContainer"] *,
  [data-testid="stSidebar"] .text-muted {
    color: #94A3B8 !important;
  }

  [data-testid="stSidebar"] .stRadio label {
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    color: #F8FAFC !important;
  }

  [data-testid="stSidebar"] button {
    background-color: #1E293B !important;
    color: #F8FAFC !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
  }

  [data-testid="stSidebar"] button p,
  [data-testid="stSidebar"] button span,
  [data-testid="stSidebar"] button div {
    color: #F8FAFC !important;
  }

  [data-testid="stSidebar"] button[kind="primary"],
  [data-testid="stSidebar"] button[data-testid="baseButton-primary"] {
    background-color: #2563EB !important;
    color: #FFFFFF !important;
    border: none !important;
  }

  /* ==========================================================================
     12. ENTERPRISE CARD UTILITY CLASS
     ========================================================================== */
  .enterprise-card {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 18px 20px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    margin-bottom: 14px !important;
  }

   .enterprise-card h1, .enterprise-card h2, .enterprise-card h3, .enterprise-card h4 {
    color: #0F172A !important;
  }

  .enterprise-card p, .enterprise-card span, .enterprise-card div {
    color: #1E293B !important;
  }

  /* ==========================================================================
     13. MICRO-ANIMATIONS & TRANSITIONS
     ========================================================================== */
  .main button:active {
    transform: scale(0.97) !important;
  }

  [data-testid="stExpander"]:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
    border-color: #CBD5E1 !important;
  }

  /* ==========================================================================
     14. CUSTOM SCROLLBAR (Refined)
     ========================================================================== */
  ::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }

  ::-webkit-scrollbar-track {
    background: #F8FAFC;
    border-radius: 3px;
  }

  ::-webkit-scrollbar-thumb {
    background: #CBD5E1;
    border-radius: 3px;
  }

  ::-webkit-scrollbar-thumb:hover {
    background: #94A3B8;
  }

  /* ==========================================================================
     15. SIDEBAR NAVIGATION REFINEMENT
     ========================================================================== */
  [data-testid="stSidebar"] [data-testid="stRadio"] > div > label {
    padding: 6px 10px !important;
    border-radius: 8px !important;
    transition: background 0.15s ease !important;
    margin-bottom: 2px !important;
  }

  [data-testid="stSidebar"] [data-testid="stRadio"] > div > label:hover {
    background: #1E293B !important;
  }

  [data-testid="stSidebar"] [data-testid="stRadio"] > div > label[data-checked="true"],
  [data-testid="stSidebar"] .st-emotion-cache-1gwvy71[aria-checked="true"] ~ label {
    background: #1E293B !important;
    border-left: 3px solid #2563EB !important;
  }

  /* ==========================================================================
     16. PLOTLY CHART CONTAINER
     ========================================================================== */
  [data-testid="stPlotlyChart"] {
    border-radius: 0 0 12px 12px !important;
    overflow: hidden !important;
  }

  /* ==========================================================================
     17. STATUS BADGES & PILLS
     ========================================================================== */
  .status-critical {
    background: #FEE2E2 !important;
    color: #DC2626 !important;
    font-weight: 700 !important;
    padding: 2px 8px !important;
    border-radius: 10px !important;
    font-size: 0.70rem !important;
  }

  .status-warning {
    background: #FEF3C7 !important;
    color: #D97706 !important;
    font-weight: 700 !important;
    padding: 2px 8px !important;
    border-radius: 10px !important;
    font-size: 0.70rem !important;
  }

  .status-healthy {
    background: #DCFCE7 !important;
    color: #16A34A !important;
    font-weight: 700 !important;
    padding: 2px 8px !important;
    border-radius: 10px !important;
    font-size: 0.70rem !important;
  }

  /* ==========================================================================
     18. HIDE STREAMLIT BRANDING & DEPLOY BUTTON
     ========================================================================== */
  #MainMenu {visibility: hidden !important;}
  footer {visibility: hidden !important;}
  [data-testid="stDeployButton"] {display: none !important;}
  header[data-testid="stHeader"] {background: transparent !important; backdrop-filter: none !important;}

  /* ==========================================================================
     HIDE AUTO-GENERATED MULTIPAGE NAVIGATION (pages/ folder nav)
     ========================================================================== */
  [data-testid="stSidebarNav"] {display: none !important;}
  [data-testid="stSidebarNavItems"] {display: none !important;}
  section[data-testid="stSidebar"] > div > div > div > ul {display: none !important;}

  /* ==========================================================================
     19. IMPROVED SIDEBAR SELECTBOX (Dark mode)
     ========================================================================== */
  [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {
    background-color: #1E293B !important;
    color: #F8FAFC !important;
    border: 1px solid #334155 !important;
  }

  [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] span {
    color: #F8FAFC !important;
  }
</style>
"""


def apply_theme():
    """Injects the global high-contrast Enterprise Light SaaS CSS theme."""
    st.markdown(ENTERPRISE_THEME_CSS, unsafe_allow_html=True)
