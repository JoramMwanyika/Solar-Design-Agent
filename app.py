"""
app.py — Main entry point for the Solar Design Agent.
"""
import streamlit as st
import json
import importlib
import agent.boq_generator
import agent.system_sizer
import agent.report_analyzer
import agent.orchestrator
import agent.multiagent.tools.math_tools
import agent.multiagent.state
import agent.multiagent.agents
import agent.multiagent.supervisor

from auth.login import require_login, render_sidebar_user
from agent.orchestrator import SolarAgent
from utils.file_parser import get_mime_type
from db.queries import (
    create_project, delete_project, get_user_projects, create_chat_session,
    get_chat_sessions, update_chat_messages, save_design,
    get_designs_for_project, delete_chat_session
)
from utils.helpers import system_type_badge, get_logo_base64, get_logo_image

# ── Load Logo Resources ──────────────────────
logo_img = get_logo_image()
logo_b64 = get_logo_base64()

# ── Page config ──────────────────────────────
st.set_page_config(page_title="JMSolar.AI", page_icon=logo_img or "static/jmsolar_logo.png", layout="wide", initial_sidebar_state="expanded")

# ── Auth guard ───────────────────────────────
if not require_login():
    st.stop()


def make_arrow_compatible(df):
    """Converts all columns to string to prevent PyArrow serialization ArrowTypeError in Streamlit."""
    if df is None or df.empty:
        return df
    df_clean = df.copy()
    for col in df_clean.columns:
        df_clean[col] = df_clean[col].astype(str)
    return df_clean

# ── Global styles (Pixel-accurate Dark Dashboard) ────────
st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">', unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/*
  JMSolar.AI Brand Palette (extracted from logo)
  --jm-bg-deep:    #060d08  deep solar-night background
  --jm-bg-panel:   #0a1410  main panel surface
  --jm-bg-card:    #0f1e15  card surface
  --jm-green:      #22c55e  solar green (circle, M, swipe)
  --jm-green-dark: #15803d  dark green
  --jm-blue:       #3b82f6  panel blue (solar panels, .AI)
  --jm-blue-lt:    #60a5fa  light blue
  --jm-gold:       #f59e0b  sun-gold (rays)
  --jm-gold-lt:    #fbbf24  light gold
  --jm-white:      #f1f5f9  near-white text
  --jm-muted:      #6b9e7e  muted green-grey
  --jm-border:     #1a3025  subtle green-tinted border
*/

/* === BASE === */
.stApp {
    background-color: #060d08 !important;
    color: #6b9e7e;
    padding-bottom: 70px !important;
}
.stApp > div { background-color: #060d08 !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a1410 0%, #071008 60%, #050c07 100%) !important;
    border-right: 1px solid #1a3025 !important;
}
[data-testid="stSidebar"] > div { background: transparent !important; }
[data-testid="stSidebar"] * { color: #a7c4b0 !important; }

/* Header bar */
[data-testid="stHeader"] { background-color: #060d08 !important; border-bottom: 1px solid #1a3025; }
[data-testid="stToolbar"] { background-color: #060d08 !important; }

/* Main container */
.main .block-container { padding-top: 1rem !important; max-width: 100% !important; }

/* Hide Streamlit chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

/* === TYPOGRAPHY === */
h1, h2, h3, h4, h5, h6 { color: #f1f5f9 !important; font-weight: 600; letter-spacing: -0.01em; }
p, li { color: #6b9e7e; line-height: 1.6; }
strong, b { color: #e2e8f0 !important; }
label { color: #6b9e7e !important; }

/* === WINDOWS-STYLE TASKBAR AT SCREEN BOTTOM === */
.windows-taskbar {
    position: fixed !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    background: #060d08 !important;
    border-top: 1px solid #1a3025 !important;
    padding: 8px 0 !important;
    z-index: 99999 !important;
    gap: 20px !important;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.6) !important;
}
.taskbar-icon-item {
    font-size: 1.25rem !important;
    color: #6b9e7e !important;
    cursor: pointer !important;
    position: relative !important;
    padding: 8px !important;
    border-radius: 6px !important;
    transition: all 0.2s ease !important;
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    width: 36px !important;
    height: 36px !important;
}
.taskbar-icon-item:hover {
    background: rgba(34, 197, 94, 0.1) !important;
    color: #22c55e !important;
    transform: translateY(-2px) !important;
}
.taskbar-icon-item::after {
    content: '' !important;
    position: absolute !important;
    bottom: 2px !important;
    left: 30% !important;
    width: 40% !important;
    height: 3px !important;
    background: transparent !important;
    border-radius: 2px !important;
    transition: all 0.2s ease !important;
}
.taskbar-icon-item:hover::after {
    background: #22c55e !important;
}
.taskbar-icon-active {
    color: #22c55e !important;
    background: rgba(34, 197, 94, 0.06) !important;
}
.taskbar-icon-active::after {
    background: #f59e0b !important;
}

/* Pro Plan card */
.pro-card {
    background: linear-gradient(135deg, #0f1e15, #0a1410);
    border: 1px solid #1a3025;
    border-radius: 10px;
    padding: 13px 15px;
    margin: 10px 0;
}
.pro-label { color: #f59e0b !important; font-weight: 600; font-size: 0.85rem; }
.pro-sub { color: #4a7a5a !important; font-size: 0.78rem; line-height: 1.5; }

/* === BUTTONS === */
.stButton > button {
    background: linear-gradient(135deg, #15803d, #22c55e) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 8px !important;
    transition: all 0.18s ease !important;
    font-size: 0.88rem !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #22c55e, #4ade80) !important;
    box-shadow: 0 4px 15px rgba(34, 197, 94, 0.35) !important;
    transform: translateY(-1px) !important;
}

/* Quick action card-buttons */
div[data-testid="column"] .stButton > button {
    background: #0f1e15 !important;
    color: #6b9e7e !important;
    border: 1px solid #1a3025 !important;
    font-weight: 450 !important;
    min-height: 95px;
    white-space: normal;
    text-align: left;
    padding: 14px !important;
    border-radius: 10px !important;
    box-shadow: none !important;
}
div[data-testid="column"] .stButton > button:hover {
    background: #142119 !important;
    border-color: #22c55e !important;
    color: #f1f5f9 !important;
    box-shadow: 0 0 0 1px rgba(34,197,94,0.2) !important;
    transform: none !important;
}

/* Bottom action pill-buttons */
.action-pill .stButton > button {
    background: #0f1e15 !important;
    color: #6b9e7e !important;
    border: 1px solid #1a3025 !important;
    border-radius: 20px !important;
    font-size: 0.82rem !important;
    font-weight: 450 !important;
    min-height: 36px !important;
    max-height: 36px !important;
    padding: 0 16px !important;
    box-shadow: none !important;
}
.action-pill .stButton > button:hover {
    background: #142119 !important;
    color: #e2e8f0 !important;
    border-color: #22c55e !important;
    box-shadow: none !important;
    transform: none !important;
}

/* === DASHBOARD CARDS === */
.dashboard-card {
    background-color: #0f1e15;
    border: 1px solid #1a3025;
    border-radius: 10px;
    padding: 18px;
    margin-bottom: 12px;
    transition: transform 0.15s ease, border-color 0.15s ease;
}
.dashboard-card:hover { border-color: #22c55e; transform: translateY(-1px); }

/* === LIVE METRIC ROWS === */
.live-metric-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 11px 0;
    border-bottom: 1px solid #1a3025;
    font-size: 0.875rem;
}
.live-metric-label { color: #6b9e7e; }
.live-metric-val { color: #e2e8f0; font-weight: 500; }

/* === FORM INPUTS === */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    background: #0f1e15 !important;
    color: #f1f5f9 !important;
    border: 1px solid #1a3025 !important;
    border-radius: 8px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #22c55e !important;
    box-shadow: 0 0 0 2px rgba(34,197,94,0.15) !important;
}
[data-baseweb="select"] { background: #0f1e15 !important; border-color: #1a3025 !important; }

/* === CHAT MESSAGES === */
[data-testid="stChatMessageContent"] {
    background: transparent !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) .stMarkdown {
    background: #0d2018;
    border-radius: 10px 10px 2px 10px;
    padding: 10px 14px;
    border: 1px solid #1a4030;
}

/* Modern chat bubbles */
[data-testid="stChatMessage"] .stMarkdown {
    background: transparent !important;
    padding: 0 !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) .stMarkdown > div {
    background: linear-gradient(180deg,#0a1a10,#0d2018); color:#c6ecd4; border-radius:12px; padding:12px 14px; border:1px solid rgba(34,197,94,0.12);
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) .stMarkdown > div {
    background: linear-gradient(180deg,#071008,#0a150d); color:#a7c4b0; border-radius:12px; padding:12px 14px; border:1px solid rgba(255,255,255,0.03);
    margin-left: 20px !important;
}

/* Chat input area */
[data-testid="stChatInput"] {
    background: #0a1410 !important;
    border: 1px solid #1a3025 !important;
    border-radius: 14px !important;
    padding: 6px !important;
}
[data-testid="stChatInput"] textarea {
    background: transparent !important;
    color: #f1f5f9 !important;
}

/* === FILE UPLOADER === */
[data-testid="stFileUploader"] {
    background: #0a1410;
    border: 2px dashed #1a3025;
    border-radius: 10px;
}

hr { border-color: #1a3025 !important; }

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #060d08; }
::-webkit-scrollbar-thumb { background: #1a4030; border-radius: 6px; }
::-webkit-scrollbar-thumb:hover { background: #22c55e; }

.stExpander { background: #0a1410; border-color: #1a3025 !important; border-radius: 12px; }
.stSuccess { background: #052e16 !important; border-color: #22c55e !important; color: #bbf7d0 !important; }
.stError { background: #2d0a0a !important; border-color: #ef4444 !important; }
.stWarning { background: #2d1a04 !important; border-color: #f59e0b !important; }
.stInfo { background: #061428 !important; border-color: #3b82f6 !important; }

/* Right panel metric cards */
.metric-grid { display:grid; grid-template-columns: repeat(1, minmax(0,1fr)); gap:8px; }
.metric-card { background: linear-gradient(180deg,#0a1a10,#0d2018); border:1px solid #1a3025; padding:12px; border-radius:10px; display:flex; align-items:center; gap:12px }
.metric-icon { width:44px; height:44px; border-radius:8px; display:flex; align-items:center; justify-content:center; background:#071008; color:#22c55e; font-size:1.1rem }
.metric-body { flex:1 }
.metric-label { color:#6b9e7e; font-size:0.85rem }
.metric-value { color:#f1f5f9; font-weight:700; font-size:1rem }

/* Highlight accent colours for data values */
.jm-green  { color: #22c55e !important; }
.jm-blue   { color: #3b82f6 !important; }
.jm-gold   { color: #f59e0b !important; }
.jm-white  { color: #f1f5f9 !important; }

</style>
""", unsafe_allow_html=True)

# Top navigation bar (visual only) — appears above the page content
st.markdown("""
<style>
 .top-nav {
         display:flex; align-items:center; justify-content:space-between;
         gap:12px;padding:10px 18px;border-bottom:1px solid #1a3025;background:linear-gradient(90deg,#060d08,#0a1410);
         position:sticky;top:0;z-index:99998;
 }
 .top-nav .brand { display:flex; align-items:center; gap:12px }
 .brand .logo-img { height:42px; width:auto; border-radius:8px; }
 .top-nav .actions { display:flex; gap:8px; align-items:center }
 .nav-pill { background:transparent; border:1px solid #1a3025; color:#6b9e7e; padding:8px 12px; border-radius:8px; font-weight:600; font-size:0.85rem; }
 .nav-pill:hover { background:rgba(34,197,94,0.08); color:#22c55e; border-color:#22c55e; }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="top-nav">
    <div class="brand">
        <img class="logo-img" src="data:image/png;base64,{logo_b64}" alt="JMSolar.AI Logo" />
        <div style="line-height:1">
            <div style="font-weight:700;color:#f1f5f9;font-size:1.05rem;"><span style="color:#ffffff;">JM</span><span style="color:#22c55e;">Solar</span><span style="color:#3b82f6;">.</span><span style="color:#3b82f6;">AI</span></div>
            <div style="font-size:0.72rem;color:#f59e0b;letter-spacing:0.1em;font-weight:500;">AI-POWERED SOLAR DESIGN ENGINEER</div>
        </div>
    </div>
    <div class="actions">
        <div class="nav-pill">New Project</div>
        <div class="nav-pill">Upload</div>
        <div class="nav-pill">Reports</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Initialize Agent ─────────────────────────
if "agent" not in st.session_state or getattr(st.session_state["agent"], "version", "") != "5.3":
    try:
        st.session_state["agent"] = SolarAgent()
    except EnvironmentError as e:
        st.error(f"⚠️ {e}")
        st.info("Please set your API keys in the .env file and restart.")
        st.stop()
agent: SolarAgent = st.session_state["agent"]

user_id = st.session_state["user"].id
projects = get_user_projects(user_id)

def save_current_project_state():
    proj_id = st.session_state.get("current_project_id")
    user_id = st.session_state.get("user").id if st.session_state.get("user") else None
    if proj_id and proj_id != "__new__" and user_id:
        try:
            curr_sess_id = st.session_state.get("current_session_id")
            if not curr_sess_id or curr_sess_id == "__new_chat__":
                title_text = "Design Conversation"
                for m in st.session_state["messages"]:
                    if m["role"] == "user" and m.get("content"):
                        raw = m["content"].replace("📎 *Attached file:*", "").replace("📎 *Uploaded file:*", "").strip()
                        if raw:
                            title_text = raw[:28] + ("..." if len(raw) > 28 else "")
                            break
                new_session = create_chat_session(user_id, proj_id, title=title_text)
                if new_session.get("id"):
                    curr_sess_id = new_session["id"]
                    st.session_state["current_session_id"] = curr_sess_id
                    st.session_state["loaded_session_id"] = curr_sess_id
            
            if curr_sess_id:
                update_chat_messages(curr_sess_id, st.session_state["messages"])
                sizing_dict = agent.last_sizing_result.to_dict() if agent.last_sizing_result else {}
                systype = st.session_state.get("sidebar_system_type", "hybrid")
                save_design(user_id, proj_id, curr_sess_id, systype, {}, sizing_dict, agent.last_boq_items)
        except Exception as e:
            print(f"DB auto-save error: {e}")

# ── Sidebar Navigation (Left Panel) ──────────
with st.sidebar:
    st.markdown("### ☀️ Solar Design\n#### Agent")
    system_type = st.selectbox("System Type", ["off-grid", "hybrid", "grid-tied"], index=1, key="sidebar_system_type")
    agent.set_system_type(system_type)

    if "show_new_project_input" not in st.session_state:
        st.session_state["show_new_project_input"] = False

    if st.button("➕ New Project", use_container_width=True):
        st.session_state["show_new_project_input"] = True
        st.rerun()

    if st.session_state["show_new_project_input"]:
        with st.form("new_project_sidebar_form", clear_on_submit=True):
            new_proj_name = st.text_input("Project Name", placeholder="e.g. Off-grid Home Design")
            col_sb1, col_sb2 = st.columns(2)
            with col_sb1:
                create_clicked = st.form_submit_button("Start")
            with col_sb2:
                cancel_clicked = st.form_submit_button("Cancel")
            
            if cancel_clicked:
                st.session_state["show_new_project_input"] = False
                st.rerun()
                
            if create_clicked and new_proj_name.strip():
                new_proj = create_project(user_id, new_proj_name.strip(), system_type, "Nairobi, Kenya")
                if new_proj.get("id"):
                    proj_id = new_proj["id"]
                    new_session = create_chat_session(user_id, proj_id, title=new_proj_name.strip())
                    if new_session.get("id"):
                        st.session_state["current_project_id"] = proj_id
                        st.session_state["current_session_id"] = new_session["id"]
                        st.session_state["loaded_session_id"] = new_session["id"]
                        st.session_state["messages"] = [
                            {"role": "assistant", "content": f"Hi there! 👋 Welcome to your new project **{new_proj_name.strip()}**. What would you like to design today?"}
                        ]
                        # Reset previous sizing state so the panel starts clean
                        agent.last_sizing_result = None
                        agent.last_boq_items = []
                        agent.last_boq_excel = None
                        st.session_state["boq_excel"] = None
                        
                        update_chat_messages(new_session["id"], st.session_state["messages"])
                        st.session_state["show_new_project_input"] = False
                        st.success(f"Project '{new_proj_name.strip()}' created!")
                        st.rerun()
    
    st.markdown("---")
    st.markdown("#### 📁 My Projects")
    
    if projects:
        for p in projects:
            proj_name = p.get("name", "Project")
            short_name = proj_name[:16] + "..." if len(proj_name) > 16 else proj_name
            date_str = str(p.get("created_at", ""))[:10]
            label = f"📁 {short_name}"
            
            is_active = (p["id"] == st.session_state.get("current_project_id"))
            
            col_p1, col_p2 = st.columns([4, 1])
            with col_p1:
                if st.button(label, key=f"proj_btn_{p['id']}", use_container_width=True, type="primary" if is_active else "secondary", help=f"Created on {date_str}"):
                    st.session_state["current_project_id"] = p["id"]
                    chat_sess = get_chat_sessions(p["id"])
                    if chat_sess:
                        target_s = chat_sess[0]
                        st.session_state["current_session_id"] = target_s["id"]
                        st.session_state["loaded_session_id"] = target_s["id"]
                        saved_messages = target_s.get("messages", [])
                        if saved_messages:
                            st.session_state["messages"] = saved_messages
                            agent.load_conversation_history(saved_messages)
                    else:
                        st.session_state["current_session_id"] = None
                        st.session_state["loaded_session_id"] = None
                        st.session_state["messages"] = [
                            {"role": "assistant", "content": "Hi there! 👋 What would you like to design today?"}
                        ]
                    
                    try:
                        designs = get_designs_for_project(p["id"])
                        if designs:
                            sess_design = designs[0]
                            if sess_design.get("sizing_results"):
                                d_res = sess_design["sizing_results"]
                                from agent.system_sizer import SizingResult
                                agent.last_sizing_result = SizingResult(
                                    system_type=d_res.get("system_type", system_type),
                                    location=d_res.get("location", "Nairobi, Kenya"),
                                    peak_sun_hours=float(d_res.get("peak_sun_hours", 3.458)),
                                    total_peak_power_w=float(d_res.get("total_peak_power_w", 0.0)),
                                    daily_energy_wh=float(d_res.get("daily_energy_wh", 0.0)),
                                    design_energy_wh=float(d_res.get("design_energy_wh", 0.0)),
                                    panel_wp=int(d_res.get("panel_wp", 625)),
                                    panel_qty=int(d_res.get("panel_qty", 0)),
                                    total_pv_kwp=float(d_res.get("total_pv_kwp", 0.0)),
                                    inverter_kw=float(d_res.get("inverter", {}).get("kw", d_res.get("inverter_kw", 0.0))),
                                    inverter_kva=float(d_res.get("inverter", {}).get("kva", d_res.get("inverter_kva", 0.0))),
                                    inverter_qty=int(d_res.get("inverter", {}).get("qty", d_res.get("inverter_qty", 1))),
                                    inverter_brand=d_res.get("inverter", {}).get("brand", d_res.get("inverter_brand", "Huawei SUN2000 Series")),
                                    voltage_architecture=d_res.get("inverter", {}).get("voltage_architecture", d_res.get("voltage_architecture", "High Voltage (HV: 1000V DC)")),
                                    battery_qty=int(d_res.get("battery", {}).get("qty", d_res.get("battery_qty", 0))),
                                    battery_module_kwh=float(d_res.get("battery", {}).get("module_kwh", 14.33)),
                                    total_storage_kwh=float(d_res.get("battery", {}).get("total_kwh", 0.0)),
                                )
                                if sess_design.get("boq_data"):
                                    agent.last_boq_items = sess_design["boq_data"]
                                    agent.last_boq_excel = generate_boq_excel(agent.last_boq_items)
                                    st.session_state["boq_excel"] = agent.last_boq_excel
                    except Exception:
                        pass
                    st.rerun()
            with col_p2:
                if st.button("🗑️", key=f"del_proj_{p['id']}", use_container_width=True, help="Delete Project"):
                    delete_project(p["id"])
                    if st.session_state.get("current_project_id") == p["id"]:
                        st.session_state["current_project_id"] = None
                        st.session_state["current_session_id"] = None
                        st.session_state["loaded_session_id"] = None
                        st.session_state["messages"] = [
                            {"role": "assistant", "content": "Hi there! 👋 What would you like to design today?"}
                        ]
                    st.rerun()
    else:
        st.info("No projects yet. Start a chat to save a project!")
    


    render_sidebar_user()

# ── Main Layout: Center Chat & Right Panel ───
col_center, col_right = st.columns([2.5, 1], gap="large")

with col_center:
    # ── Admin Dashboard & Account Monitor ──────
    is_admin = st.session_state.get("is_admin") or st.session_state.get("profile", {}).get("role") == "admin"
    if is_admin:
        with st.expander("👑 Admin Dashboard — Active Accounts Monitor & User Credentials", expanded=False):
            from auth.admin_ui import render_admin_dashboard
            render_admin_dashboard()

    # Top Bar: Greeting
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:20px; margin-bottom: 20px;">
        <div style="width:72px; height:72px; border-radius:50%; border:2px solid #10B981; display:flex; align-items:center; justify-content:center; background:#0F172A; overflow:hidden;">
            <img src="data:image/png;base64,{logo_b64}" alt="JMSolar.AI" style="width:60px; height:60px; object-fit:contain;" />
        </div>
        <div>
            <h2 style="margin:0; margin-bottom:4px;">Hello! I'm <span style="color:#10B981;">JMSolar</span><span style="color:#38BDF8;">.AI</span> &mdash; your Solar Design Engineer.</h2>
            <p style="margin:0;">Upload your site plan, electricity bill, or describe your project to begin.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    


    st.markdown("---")
    
    # Chat Messages Container
    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {"role": "assistant", "content": f"Hi there! 👋 What would you like to design today? I'm set to **{system_type}** mode."}
        ]

    for msg in st.session_state["messages"]:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="☀️"):
                st.markdown(msg["content"])



    # Chat Input with Automatic File Processing
    user_submission = st.chat_input("Ask anything about your solar design or attach loads...", accept_file="multiple")
    
    if user_submission:
        text = ""
        files = []
        if isinstance(user_submission, dict):
            text = user_submission.get("text", "") or ""
            files = user_submission.get("files", []) or []
        elif hasattr(user_submission, "files"):
            text = getattr(user_submission, "text", "") or ""
            files = getattr(user_submission, "files", []) or []
        else:
            text = str(user_submission or "")

        if text.strip():
            st.session_state["messages"].append({"role": "user", "content": text})

        # AUTOMATIC UNPROMPTED FILE PARSING & SIZING
        for chat_file in files:
            fname = chat_file.name
            st.session_state["messages"].append({"role": "user", "content": f"📎 *Attached file:* `{fname}`"})
            if fname.endswith((".csv", ".xlsx", ".xls")):
                import pandas as pd
                from utils.file_parser import extract_loads_from_dataframe
                try:
                    df_loads = pd.read_csv(chat_file) if fname.endswith(".csv") else pd.read_excel(chat_file)
                    df_loads.columns = df_loads.columns.astype(str)
                    csv_loads, _ = extract_loads_from_dataframe(df_loads)
                    if csv_loads:
                        with st.spinner(f"⚡ Automatically calculating system size from `{fname}`..."):
                            md_result, _ = agent.run_sizing(loads=csv_loads, location=agent.project_state.location)
                        st.session_state["messages"].append({"role": "assistant", "content": md_result})
                    else:
                        st.session_state["messages"].append({"role": "assistant", "content": f"⚠️ Could not extract loads from `{fname}`. Ensure columns contain wattage or power values."})
                except Exception as e:
                    st.session_state["messages"].append({"role": "assistant", "content": f"Error parsing `{fname}`: {e}"})
            else:
                with st.spinner(f"📄 Analyzing attached file `{fname}`..."):
                    resp = agent.process_uploaded_file(chat_file.read(), fname, get_mime_type(fname))
                st.session_state["messages"].append({"role": "assistant", "content": resp})

        st.rerun()

    # Process latest user text message with SolarBot
    if st.session_state["messages"] and st.session_state["messages"][-1]["role"] == "user":
        user_text = st.session_state["messages"][-1]["content"]
        if not user_text.startswith("📎 *Attached file:*"):
            with st.chat_message("assistant", avatar="☀️"):
                with st.spinner("🔆 SolarBot is thinking..."):
                    response_text, boq_excel, boq_items = agent.chat_message(user_text)
                st.markdown(response_text)
                if boq_excel:
                    st.session_state["boq_excel"] = boq_excel
            st.session_state["messages"].append({"role": "assistant", "content": response_text})
        
        save_current_project_state()
        st.rerun()

    # ── Interactive Quick Sizing & Manual Load Entry Form ──
    st.markdown("---")
    with st.expander("⚙️ Quick Sizing Form — Select Sizing Input Source", expanded=True):
        # Default initialization
        if "active_sizing_mode" not in st.session_state:
            st.session_state["active_sizing_mode"] = "logged_data"
            
        active_mode = st.session_state["active_sizing_mode"]
        
        st.markdown("##### 🔍 Sizing Method Selection:")
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("📂 Logged Data Sizing", key="btn_logged_data", use_container_width=True, type="primary" if active_mode == "logged_data" else "secondary"):
                st.session_state["active_sizing_mode"] = "logged_data"
                st.rerun()
        with col_btn2:
            if st.button("✍️ Load Profile Sizing", key="btn_load_profile", use_container_width=True, type="primary" if active_mode == "load_profile" else "secondary"):
                st.session_state["active_sizing_mode"] = "load_profile"
                st.rerun()
        with col_btn3:
            if st.button("📄 Bill Analysis Sizing", key="btn_bill_analysis", use_container_width=True, type="primary" if active_mode == "bill_analysis" else "secondary"):
                st.session_state["active_sizing_mode"] = "bill_analysis"
                st.rerun()
                
        st.markdown("---")

        # Sizing common settings helper
        def render_sizing_settings(prefix: str):
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                loc = st.text_input("Location", value=agent.project_state.location or "Nairobi, Kenya", key=f"{prefix}_loc")
                p_wp = st.number_input("Panel Watt-peak (Wp)", value=625, step=25, key=f"{prefix}_p_wp")
            with col_s2:
                days = st.number_input("Days of Autonomy", value=2.0, min_value=0.5, max_value=7.0, step=0.5, key=f"{prefix}_days")
                volt = st.selectbox("System Voltage (DC)", [12, 24, 48], index=2, key=f"{prefix}_volt")
            with col_s3:
                dod_val = st.slider("Battery DoD (%)", 50, 90, 80, key=f"{prefix}_dod") / 100
                ah_val = st.number_input("Battery Ah Rating", value=280, step=20, key=f"{prefix}_ah")
            return loc, p_wp, days, volt, dod_val, ah_val

        if active_mode == "logged_data":
            st.markdown("##### 📂 Sizing based on time-series interval logger data (SCADA/Fluke/Meter logs)")
            logged_file = st.file_uploader("Upload Logger Spreadsheet (.csv or .xlsx)", type=["csv", "xlsx"], key="logged_csv_uploader")
            if logged_file:
                import pandas as pd
                try:
                    df_logged = pd.read_csv(logged_file) if logged_file.name.endswith(".csv") else pd.read_excel(logged_file)
                    df_logged.columns = df_logged.columns.astype(str)
                    st.dataframe(make_arrow_compatible(df_logged))
                    
                    st.markdown("---")
                    st.markdown("##### Sizing Parameters")
                    l_loc, l_wp, l_days, l_volt, l_dod, l_ah = render_sizing_settings("logged")
                    
                    if st.button("⚡ Run Sizing (Logged Data)", key="run_logged_sizing", use_container_width=True):
                        from utils.file_parser import extract_loads_from_dataframe
                        csv_loads, _ = extract_loads_from_dataframe(df_logged)
                        if not csv_loads:
                            st.warning("No valid data found in logger file. Ensure columns contain power values.")
                        else:
                            with st.spinner("Logged Data Agent is sizing system..."):
                                md_result, _ = agent.run_sizing_by_logged_data(
                                    loads=csv_loads,
                                    location=l_loc,
                                    days_of_autonomy=l_days,
                                    dod=l_dod,
                                    system_voltage_dc=int(l_volt),
                                    battery_ah_rating=int(l_ah),
                                    panel_wp=int(l_wp),
                                )
                            st.session_state["messages"].append({"role": "user", "content": f"📎 *Ran Logged Data Sizing from:* `{logged_file.name}`"})
                            st.session_state["messages"].append({"role": "assistant", "content": md_result})
                            st.success("✅ Sizing complete! Check the chat above.")
                            save_current_project_state()
                            st.rerun()
                except Exception as e:
                    st.error(f"Error parsing logger spreadsheet: {e}")

        elif active_mode == "load_profile":
            st.markdown("##### ✍️ Sizing based on load schedule/appliance list")
            st.markdown("You can upload a `.csv` / `.xlsx` template or enter appliance details manually.")
            
            p_tab_csv, p_tab_manual = st.tabs(["📂 Upload Appliance Spreadsheet", "✍️ Enter Appliances Manually"])
            
            with p_tab_csv:
                sample_csv = "name,wattage,quantity,hours_per_day\nLED Lighting & Office,15,20,10.0\nDesktop Computers,150,10,8.0\nAir Conditioning HVAC,2500,2,8.0\nCommercial Refrigerator,350,1,24.0\nWater Pumping Motor,1200,1,2.0\n"
                st.download_button("📥 Download Appliance List CSV Template", data=sample_csv, file_name="sample_load_schedule.csv", mime="text/csv")
                
                profile_file = st.file_uploader("Upload Appliance Spreadsheet (.csv or .xlsx)", type=["csv", "xlsx"], key="profile_csv_uploader")
                if profile_file:
                    import pandas as pd
                    try:
                        df_prof = pd.read_csv(profile_file) if profile_file.name.endswith(".csv") else pd.read_excel(profile_file)
                        df_prof.columns = df_prof.columns.astype(str)
                        st.dataframe(make_arrow_compatible(df_prof))
                        
                        st.markdown("---")
                        st.markdown("##### Sizing Parameters")
                        p_loc, p_wp, p_days, p_volt, p_dod, p_ah = render_sizing_settings("profile_csv")
                        
                        if st.button("🔆 Run Sizing (Load Profile from Spreadsheet)", key="run_profile_csv_sizing", use_container_width=True):
                            from utils.file_parser import extract_loads_from_dataframe
                            csv_loads, _ = extract_loads_from_dataframe(df_prof)
                            if not csv_loads:
                                st.warning("No valid appliances found. Ensure columns contain wattage or power values.")
                            else:
                                with st.spinner("Load Profile Agent is sizing system..."):
                                    md_result, _ = agent.run_sizing_by_load_profile(
                                        loads=csv_loads,
                                        location=p_loc,
                                        days_of_autonomy=p_days,
                                        dod=p_dod,
                                        system_voltage_dc=int(p_volt),
                                        battery_ah_rating=int(p_ah),
                                        panel_wp=int(p_wp),
                                    )
                                st.session_state["messages"].append({"role": "user", "content": f"📎 *Ran Load Profile Sizing from:* `{profile_file.name}`"})
                                st.session_state["messages"].append({"role": "assistant", "content": md_result})
                                st.success("✅ Sizing complete! Check the chat above.")
                                save_current_project_state()
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error parsing appliance spreadsheet: {e}")

            with p_tab_manual:
                st.markdown("Fill in appliance load schedule manually below:")
                pm_loc, pm_wp, pm_days, pm_volt, pm_dod, pm_ah = render_sizing_settings("profile_manual")
                
                st.markdown("---")
                st.markdown("##### ⚡ Load Schedule")
                load_count = st.number_input("Number of loads", min_value=1, max_value=20, value=3, key="profile_manual_count")
                
                loads = []
                for i in range(int(load_count)):
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    with c1:
                        lname = st.text_input(f"Load {i+1} Name", key=f"p_lname_{i}", placeholder="e.g. LED Light")
                    with c2:
                        lwatt = st.number_input("Watts", key=f"p_lwatt_{i}", min_value=0, value=10)
                    with c3:
                        lqty  = st.number_input("Qty",   key=f"p_lqty_{i}",  min_value=1, value=1)
                    with c4:
                        lhrs  = st.number_input("Hrs/day", key=f"p_lhrs_{i}", min_value=0.0, value=8.0, step=0.5)
                    if lname and lwatt > 0:
                        loads.append({"name": lname, "wattage": lwatt, "quantity": lqty, "hours_per_day": lhrs})
                        
                if st.button("🔆 Run Sizing (Load Profile Manual)", key="run_profile_manual_sizing", use_container_width=True):
                    if not loads:
                        st.warning("Please add at least one load.")
                    else:
                        with st.spinner("Load Profile Agent is sizing system..."):
                            md_result, _ = agent.run_sizing_by_load_profile(
                                loads=loads,
                                location=pm_loc,
                                days_of_autonomy=pm_days,
                                dod=pm_dod,
                                system_voltage_dc=int(pm_volt),
                                battery_ah_rating=int(pm_ah),
                                panel_wp=int(pm_wp),
                            )
                        st.session_state["messages"].append({"role": "user", "content": "⚡ *Submitted manual load schedule*" })
                        st.session_state["messages"].append({"role": "assistant", "content": md_result})
                        st.success("✅ Sizing complete! Check the chat above.")
                        save_current_project_state()
                        st.rerun()

        elif active_mode == "bill_analysis":
            st.markdown("##### 📄 Sizing based on monthly utility bill analysis")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                monthly_kwh = st.number_input("Monthly Energy Consumption (kWh)", min_value=1.0, value=1200.0, step=100.0, key="bill_monthly_kwh")
                billing_days = st.number_input("Billing Period Days", min_value=1, value=30, key="bill_days")
            with col_b2:
                customer_type = st.selectbox("Customer / Tariff Type", ["Residential", "Commercial", "Industrial"], key="bill_cust_type")
                max_demand_kw = st.number_input("Measured Peak Demand (kW) — Optional", min_value=0.0, value=0.0, step=1.0, key="bill_max_demand")
            
            st.markdown("---")
            st.markdown("##### Sizing Parameters")
            b_loc, b_wp, b_days, b_volt, b_dod, b_ah = render_sizing_settings("bill")
            
            if st.button("📊 Run Sizing (Bill Analysis)", key="run_bill_sizing", use_container_width=True):
                with st.spinner("Bill Analysis Agent is sizing system..."):
                    md_result, _ = agent.run_sizing_by_bill_analysis(
                        monthly_energy_kwh=monthly_kwh,
                        billing_days=int(billing_days),
                        customer_type=customer_type,
                        max_demand_kw=max_demand_kw,
                        location=b_loc,
                        days_of_autonomy=b_days,
                        dod=b_dod,
                        system_voltage_dc=int(b_volt),
                        battery_voltage=51.2, # default
                        panel_wp=int(b_wp),
                    )
                st.session_state["messages"].append({"role": "user", "content": f"📄 *Submitted utility bill info ({monthly_kwh} kWh, {billing_days} days)*"})
                st.session_state["messages"].append({"role": "assistant", "content": md_result})
                st.success("✅ Sizing complete! Check the chat above.")
                save_current_project_state()
                st.rerun()

    # ── Equipment Datasheets & Component Reference Library ──
    with st.expander("📚 Equipment Datasheets & Component Reference Library", expanded=False):
        st.markdown("Upload equipment datasheets (**PV Modules, Inverters, Battery Energy Storage Systems, Protection Switchgear**) in PDF, Word, Excel, CSV, or Image format. SolarBot will index the technical specifications and use them for stringing, voltage limits, and component selection!")
        
        ds_file = st.file_uploader("Upload Equipment Datasheet / Spec Sheet (.pdf, .docx, .png, .jpg, .xlsx, .csv, .json)", type=["pdf", "docx", "png", "jpg", "xlsx", "csv", "json"], key="datasheet_library_uploader")
        if ds_file and st.session_state.get("_last_ds_file") != ds_file.name:
            st.session_state["_last_ds_file"] = ds_file.name
            with st.spinner(f"🔍 Analyzing datasheet `{ds_file.name}`..."):
                analysis_resp = agent.process_uploaded_file(ds_file.read(), ds_file.name, get_mime_type(ds_file.name))
            st.session_state["messages"].append({"role": "user", "content": f"📚 *Uploaded Datasheet for Agent Reference:* `{ds_file.name}`"})
            st.session_state["messages"].append({"role": "assistant", "content": analysis_resp})
            st.success(f"✅ Indexed `{ds_file.name}` into SolarBot's reference memory! See chat above.")
            st.rerun()

    # ── Export Project Reports & Workbooks ────
    if agent.last_sizing_result or agent.last_boq_excel or st.session_state.get("boq_excel"):
        st.markdown("---")
        st.markdown("### 📥 Export Project Reports & Workbooks")
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            if agent.last_sizing_result:
                wb_data = agent.last_design_workbook or agent.get_or_create_design_workbook()
                if wb_data:
                    st.download_button(
                        label="📊 Download Complete Sizing & Design Workbook (6 Sheets Excel)",
                        data=wb_data,
                        file_name=f"Solar_Design_Workbook_{system_type}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="dl_bottom_design_workbook"
                    )
            else:
                st.info("⚡ Complete system sizing above to unlock full 6-sheet design workbook.")
        with col_exp2:
            excel_data = agent.last_boq_excel or st.session_state.get("boq_excel")
            if excel_data:
                st.download_button(
                    label="📥 Download BOQ Only (Excel)",
                    data=excel_data,
                    file_name="Solar_BOQ.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_bottom_boq_excel"
                )
            else:
                st.info("📋 Type 'generate BOQ' in chat to unlock BOQ download.")

# ── Right Panel: Live Project ───────────────
with col_right:
    st.markdown("""
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <h4 style="margin:0;"><span style="color:#10B981;">●</span> Live Project</h4>
        <span style="font-size:0.8rem;">Auto-saved</span>
    </div>
    <hr style="margin: 10px 0;">
    """, unsafe_allow_html=True)
    
    res = agent.last_sizing_result
    
    loc = res.location if res else agent.project_state.location
    roof = "--- m²"
    panels = f"{res.panel_qty} panels ({res.panel_wp}W)" if res else "---"
    inv = f"{res.inverter_qty}x {res.inverter_brand}" if res else "---"
    batt = f"{res.battery_qty}x {res.battery_module_kwh}kWh" if res and res.system_type != 'grid-tied' else "---"
    load = f"{res.daily_energy_wh/1000:.1f} kWh/day" if res else "---"
    psh = f"{res.peak_sun_hours} h/day" if res else "---"
    savings = "KES --- / year"
    st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card"><div class="metric-icon">📍</div><div class="metric-body"><div class="metric-label">Location</div><div class="metric-value">{loc}</div></div></div>
            <div class="metric-card"><div class="metric-icon">📐</div><div class="metric-body"><div class="metric-label">Roof Area</div><div class="metric-value">{roof}</div></div></div>
            <div class="metric-card"><div class="metric-icon">🔲</div><div class="metric-body"><div class="metric-label">Panel Count</div><div class="metric-value">{panels}</div></div></div>
            <div class="metric-card"><div class="metric-icon">⚡</div><div class="metric-body"><div class="metric-label">Inverter</div><div class="metric-value">{inv}</div></div></div>
            <div class="metric-card"><div class="metric-icon">🔋</div><div class="metric-body"><div class="metric-label">Battery</div><div class="metric-value">{batt}</div></div></div>
            <div class="metric-card"><div class="metric-icon">🔌</div><div class="metric-body"><div class="metric-label">Daily Load</div><div class="metric-value">{load}</div></div></div>
            <div class="metric-card"><div class="metric-icon">☀️</div><div class="metric-body"><div class="metric-label">Peak Sun Hours</div><div class="metric-value">{psh}</div></div></div>
            <div class="metric-card"><div class="metric-icon" style="background:#072012;color:#10B981">💲</div><div class="metric-body"><div class="metric-label">Estimated Savings</div><div class="metric-value" style="color:#10B981">{savings}</div></div></div>
        </div>
        """, unsafe_allow_html=True)
    

    
    # File Uploader in right panel
    st.markdown("---")
    st.caption("Upload File or Load Schedule")
    uploaded_file = st.file_uploader("Drop here", label_visibility="collapsed", type=["csv", "xlsx", "pdf", "docx", "json"], key="right_panel_uploader")
    if uploaded_file and st.session_state.get("_last_upload_rp") != uploaded_file.name:
        st.session_state["_last_upload_rp"] = uploaded_file.name
        if uploaded_file.name.endswith((".csv", ".xlsx", ".xls")):
            import pandas as pd
            from utils.file_parser import extract_loads_from_dataframe
            try:
                df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
                df.columns = df.columns.astype(str)
                csv_loads, _ = extract_loads_from_dataframe(df)
                if csv_loads:
                    with st.spinner(f"Sizing from {uploaded_file.name}..."):
                        md, _ = agent.run_sizing(loads=csv_loads, location=loc, system_type=system_type)
                    st.session_state["messages"].append({"role": "user", "content": f"📎 *Uploaded {uploaded_file.name}*"})
                    st.session_state["messages"].append({"role": "assistant", "content": md})
                    save_current_project_state()
                    st.rerun()
            except Exception as e:
                st.error(f"Error parsing file: {e}")
        else:
            with st.spinner("Analyzing document..."):
                resp = agent.process_uploaded_file(uploaded_file.read(), uploaded_file.name, get_mime_type(uploaded_file.name))
                st.session_state["messages"].append({"role": "user", "content": f"📎 *Uploaded {uploaded_file.name}*"})
                st.session_state["messages"].append({"role": "assistant", "content": resp})
                save_current_project_state()
                st.rerun()

# ── Global Screen-Bottom Windows Taskbar ──────────
st.markdown("""
<div class="windows-taskbar">
    <span class="taskbar-icon-item taskbar-icon-active" title="Dashboard"><i class="fa-solid fa-house"></i></span>
    <span class="taskbar-icon-item" title="Solar Layouts"><i class="fa-solid fa-solar-panel"></i></span>
    <span class="taskbar-icon-item" title="Site Analysis"><i class="fa-solid fa-ruler-combined"></i></span>
    <span class="taskbar-icon-item" title="Energy Yield"><i class="fa-solid fa-chart-column"></i></span>
    <span class="taskbar-icon-item" title="Battery Sizing"><i class="fa-solid fa-battery-three-quarters"></i></span>
    <span class="taskbar-icon-item" title="Reports"><i class="fa-solid fa-file-lines"></i></span>
    <span class="taskbar-icon-item" title="Settings"><i class="fa-solid fa-gear"></i></span>
</div>
""", unsafe_allow_html=True)
