"""
app.py — Main entry point for the Solar Design Agent.
Handles login gate and global page configuration.
"""
import streamlit as st
from auth.login import render_login_page, render_sidebar_user, require_login

# ─────────────────────────────────────────────
# Page configuration (must be first Streamlit call)
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Solar Design Agent",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Global CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Global reset */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Dark background */
.stApp {
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%);
    color: #E2E8F0;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #1E3A5F 100%);
    border-right: 1px solid #334155;
}
[data-testid="stSidebar"] * { color: #E2E8F0 !important; }

/* Main content */
.main .block-container { padding-top: 1.5rem; max-width: 1200px; }

/* Headers */
h1, h2, h3 { color: #F59E0B !important; }
h4, h5 { color: #93C5FD !important; }

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #F59E0B, #D97706);
    color: #0F172A;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #FBBF24, #F59E0B);
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(245,158,11,0.4);
}

/* Text inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    background: #1E293B !important;
    color: #E2E8F0 !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #F59E0B !important;
    box-shadow: 0 0 0 2px rgba(245,158,11,0.2) !important;
}

/* Chat messages */
.chat-user {
    background: linear-gradient(135deg, #1E3A5F, #1E293B);
    border: 1px solid #3B82F6;
    border-radius: 12px 12px 0 12px;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    max-width: 80%;
    margin-left: auto;
    color: #E2E8F0;
}
.chat-bot {
    background: linear-gradient(135deg, #1a2744, #1E293B);
    border: 1px solid #F59E0B33;
    border-radius: 12px 12px 12px 0;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    max-width: 85%;
    color: #E2E8F0;
}

/* Cards */
.metric-card {
    background: linear-gradient(135deg, #1E293B, #1a2744);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1.2rem;
    margin: 0.4rem 0;
    transition: all 0.2s ease;
}
.metric-card:hover {
    border-color: #F59E0B66;
    transform: translateY(-2px);
}

/* Dataframes / Tables */
.stDataFrame { background: #1E293B !important; }
.dataframe th {
    background: #1E3A5F !important;
    color: #F59E0B !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #1E293B;
    border-radius: 8px;
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #94A3B8;
    border-radius: 6px;
}
.stTabs [aria-selected="true"] {
    background: #F59E0B !important;
    color: #0F172A !important;
    font-weight: 600;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: #1E293B;
    border: 2px dashed #334155;
    border-radius: 12px;
}

/* Dividers */
hr { border-color: #334155 !important; }

/* Success / error / warning */
.stSuccess { background: #052e16 !important; border-color: #16a34a !important; }
.stError { background: #450a0a !important; border-color: #dc2626 !important; }
.stWarning { background: #422006 !important; border-color: #d97706 !important; }
.stInfo { background: #0c1a3a !important; border-color: #3b82f6 !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0F172A; }
::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #F59E0B; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Login gate
# ─────────────────────────────────────────────
if not require_login():
    st.stop()

# ─────────────────────────────────────────────
# Sidebar navigation (shown after login)
# ─────────────────────────────────────────────
render_sidebar_user()

st.sidebar.markdown("---")
st.sidebar.markdown("### 🧭 Navigation")
st.sidebar.page_link("pages/1_Chat.py",        label="💬 Chat & Design",    icon="💬")
st.sidebar.page_link("pages/2_My_Projects.py", label="📁 My Projects",      icon="📁")
if st.session_state.get("is_admin"):
    st.sidebar.page_link("pages/3_Admin.py",   label="👑 Admin Panel",      icon="👑")

st.sidebar.markdown("---")
st.sidebar.caption("☀️ Solar Design Agent v1.0")

# ─────────────────────────────────────────────
# Home / Welcome screen
# ─────────────────────────────────────────────
profile = st.session_state.get("profile", {})
name = profile.get("full_name", "there")

st.markdown(f"""
<div style='text-align:center; padding: 3rem 0 1rem;'>
    <div style='font-size: 4rem; margin-bottom: 0.5rem;'>☀️</div>
    <h1 style='font-size: 2.5rem; margin: 0; color: #F59E0B;'>Solar Design Agent</h1>
    <p style='color: #94A3B8; font-size: 1.1rem; margin-top: 0.5rem;'>
        AI-powered PV system sizing, design &amp; BOQ generation
    </p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    <div class='metric-card' style='text-align:center;'>
        <div style='font-size:2rem;'>🔋</div>
        <h4>Off-Grid Systems</h4>
        <p style='color:#94A3B8; font-size:0.9rem;'>Full energy independence with battery storage</p>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown("""
    <div class='metric-card' style='text-align:center;'>
        <div style='font-size:2rem;'>⚡</div>
        <h4>Hybrid Systems</h4>
        <p style='color:#94A3B8; font-size:0.9rem;'>Solar + battery + grid backup combination</p>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown("""
    <div class='metric-card' style='text-align:center;'>
        <div style='font-size:2rem;'>🌐</div>
        <h4>Grid-Tied Systems</h4>
        <p style='color:#94A3B8; font-size:0.9rem;'>Export excess generation to the grid</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown(f"""
<div style='text-align:center; margin-top:2.5rem; padding: 1.5rem; background: #1E293B;
     border-radius: 12px; border: 1px solid #334155;'>
    <p style='color:#F59E0B; font-size:1.1rem; margin:0;'>
        👋 Welcome back, <b>{name}</b>!
    </p>
    <p style='color:#94A3B8; margin: 0.5rem 0 0;'>
        Navigate to <b>💬 Chat & Design</b> to start a new solar design session,
        or <b>📁 My Projects</b> to view your saved designs.
    </p>
</div>
""", unsafe_allow_html=True)
