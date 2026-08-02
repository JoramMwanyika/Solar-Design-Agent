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

importlib.reload(agent.multiagent.tools.math_tools)
importlib.reload(agent.multiagent.state)
importlib.reload(agent.multiagent.agents)
importlib.reload(agent.multiagent.supervisor)
importlib.reload(agent.boq_generator)
importlib.reload(agent.system_sizer)
importlib.reload(agent.report_analyzer)
importlib.reload(agent.orchestrator)

from auth.login import require_login, render_sidebar_user
from agent.orchestrator import SolarAgent
from utils.file_parser import get_mime_type
from db.queries import (
    create_project, get_user_projects, create_chat_session,
    get_chat_sessions, update_chat_messages, save_design,
    get_designs_for_project, delete_chat_session
)
from utils.helpers import system_type_badge

# ── Page config ──────────────────────────────
st.set_page_config(page_title="Solar Design Agent", page_icon="☀️", layout="wide", initial_sidebar_state="expanded")

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
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* === BASE === */
.stApp {
    background-color: #0d1117 !important;
    color: #94a3b8;
}
.stApp > div { background-color: #0d1117 !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111827 0%, #0d1b2a 60%, #0a1628 100%) !important;
    border-right: 1px solid #1e2a3a !important;
}
[data-testid="stSidebar"] > div { background: transparent !important; }
[data-testid="stSidebar"] * { color: #cbd5e1 !important; }

/* Header bar */
[data-testid="stHeader"] { background-color: #0d1117 !important; border-bottom: 1px solid #1e2a3a; }
[data-testid="stToolbar"] { background-color: #0d1117 !important; }

/* Main container */
.main .block-container { padding-top: 1rem !important; max-width: 100% !important; }

/* Hide Streamlit chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }

/* === TYPOGRAPHY === */
h1, h2, h3, h4, h5, h6 { color: #f1f5f9 !important; font-weight: 600; letter-spacing: -0.01em; }
p, li { color: #94a3b8; line-height: 1.6; }
strong, b { color: #e2e8f0 !important; }
label { color: #94a3b8 !important; }

/* === SIDEBAR NAV ITEMS === */
.nav-item {
    padding: 9px 14px;
    margin: 2px 0;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
    color: #94a3b8;
    font-size: 0.88rem;
    font-weight: 450;
    display: flex;
    align-items: center;
    gap: 11px;
}
.nav-item:hover { background-color: #1e2a3a; color: #f1f5f9; }
.nav-active {
    background-color: rgba(74, 222, 128, 0.08);
    color: #4ade80 !important;
    font-weight: 500;
    border-left: 2px solid #4ade80;
}

/* Pro Plan card */
.pro-card {
    background: linear-gradient(135deg, #1a2234, #131920);
    border: 1px solid #2d3f55;
    border-radius: 10px;
    padding: 13px 15px;
    margin: 10px 0;
}
.pro-label { color: #f59e0b !important; font-weight: 600; font-size: 0.85rem; }
.pro-sub { color: #64748b !important; font-size: 0.78rem; line-height: 1.5; }

/* === BUTTONS === */
.stButton > button {
    background: #2563eb !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 8px !important;
    transition: all 0.18s ease !important;
    font-size: 0.88rem !important;
}
.stButton > button:hover {
    background: #3b82f6 !important;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.35) !important;
    transform: translateY(-1px) !important;
}

/* Quick action card-buttons */
div[data-testid="column"] .stButton > button {
    background: #1a2234 !important;
    color: #94a3b8 !important;
    border: 1px solid #252f40 !important;
    font-weight: 450 !important;
    min-height: 95px;
    white-space: normal;
    text-align: left;
    padding: 14px !important;
    border-radius: 10px !important;
    box-shadow: none !important;
}
div[data-testid="column"] .stButton > button:hover {
    background: #1e2a3a !important;
    border-color: #2d3f55 !important;
    color: #f1f5f9 !important;
    box-shadow: none !important;
    transform: none !important;
}

/* Bottom action pill-buttons */
.action-pill .stButton > button {
    background: #1a2234 !important;
    color: #94a3b8 !important;
    border: 1px solid #252f40 !important;
    border-radius: 20px !important;
    font-size: 0.82rem !important;
    font-weight: 450 !important;
    min-height: 36px !important;
    max-height: 36px !important;
    padding: 0 16px !important;
    box-shadow: none !important;
}
.action-pill .stButton > button:hover {
    background: #1e2a3a !important;
    color: #e2e8f0 !important;
    border-color: #3b82f6 !important;
    box-shadow: none !important;
    transform: none !important;
}

/* === DASHBOARD CARDS === */
.dashboard-card {
    background-color: #1a2234;
    border: 1px solid #252f40;
    border-radius: 10px;
    padding: 18px;
    margin-bottom: 12px;
    transition: transform 0.15s ease, border-color 0.15s ease;
}
.dashboard-card:hover { border-color: #2d3f55; transform: translateY(-1px); }

/* === LIVE METRIC ROWS === */
.live-metric-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 11px 0;
    border-bottom: 1px solid #1e2a3a;
    font-size: 0.875rem;
}
.live-metric-label { color: #94a3b8; }
.live-metric-val { color: #e2e8f0; font-weight: 500; }

/* === FORM INPUTS === */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    background: #1a2234 !important;
    color: #f1f5f9 !important;
    border: 1px solid #252f40 !important;
    border-radius: 8px !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #4ade80 !important;
    box-shadow: 0 0 0 2px rgba(74,222,128,0.15) !important;
}
[data-baseweb="select"] { background: #1a2234 !important; border-color: #252f40 !important; }

/* === CHAT MESSAGES === */
[data-testid="stChatMessageContent"] {
    background: transparent !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) .stMarkdown {
    background: #1d3461;
    border-radius: 10px 10px 2px 10px;
    padding: 10px 14px;
    border: 1px solid #2d4a8a;
}

/* Chat input area */
[data-testid="stChatInput"] {
    background: #1a2234 !important;
    border: 1px solid #252f40 !important;
    border-radius: 10px !important;
}
[data-testid="stChatInput"] textarea {
    background: transparent !important;
    color: #f1f5f9 !important;
}

/* === FILE UPLOADER === */
[data-testid="stFileUploader"] {
    background: #1a2234;
    border: 2px dashed #252f40;
    border-radius: 10px;
}

hr { border-color: #1e2a3a !important; }

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #2d3f55; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4ade80; }

.stExpander { background: #1a2234; border-color: #252f40 !important; border-radius: 10px; }
.stSuccess { background: #052e16 !important; border-color: #4ade80 !important; color: #bbf7d0 !important; }
.stError { background: #450a0a !important; border-color: #ef4444 !important; }
.stWarning { background: #422006 !important; border-color: #f59e0b !important; }
.stInfo { background: #0c1a3a !important; border-color: #3b82f6 !important; }
</style>
""", unsafe_allow_html=True)


# ── Initialize Agent ─────────────────────────
if "agent" not in st.session_state or getattr(st.session_state["agent"], "version", "") != "4.8":
    try:
        st.session_state["agent"] = SolarAgent()
    except EnvironmentError as e:
        st.error(f"⚠️ {e}")
        st.info("Please set your API keys in the .env file and restart.")
        st.stop()
agent: SolarAgent = st.session_state["agent"]

user_id = st.session_state["user"].id
projects = get_user_projects(user_id)

# ── Sidebar Navigation (Left Panel) ──────────
with st.sidebar:
    st.markdown("### ☀️ Solar Design\n#### Agent")
    st.button("➕ New Project", use_container_width=True)
    
    st.markdown("""
    <div class="nav-item nav-active">🏠 Dashboard</div>
    <div class="nav-item">🔲 Solar Layouts</div>
    <div class="nav-item">📐 Site Analysis</div>
    <div class="nav-item">📊 Energy Yield</div>
    <div class="nav-item">🔋 Battery Sizing</div>
    <div class="nav-item">📄 Reports</div>
    <div class="nav-item">⚙️ Settings</div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="pro-card">
        <span class="pro-label">👑 Pro Plan</span><br>
        <span class="pro-sub">Unlimited designs<br>Renews Aug 12, 2025</span>
    </div>
    """, unsafe_allow_html=True)
    
    # Project & System Config (Functional)
    st.markdown("---")
    project_options = {p["id"]: p["name"] for p in projects}
    project_options["__new__"] = "➕ Create New Project"
    selected_project_id = st.selectbox(
        "Active Project",
        options=list(project_options.keys()),
        format_func=lambda x: project_options[x],
        key="selected_project"
    )
    
    if selected_project_id == "__new__":
        with st.form("new_project_form"):
            proj_name = st.text_input("Project Name", placeholder="e.g. Green Leaf Residence")
            proj_loc  = st.text_input("Location",     placeholder="e.g. Kitengela, Kenya")
            sys_type = st.selectbox("System Type", ["off-grid", "hybrid", "grid-tied"], index=1)
            submitted = st.form_submit_button("Create")
            if submitted and proj_name:
                new_proj = create_project(user_id, proj_name, sys_type, proj_loc)
                if new_proj.get("id"):
                    st.session_state["current_project_id"] = new_proj["id"]
                    st.session_state["current_session_id"] = None
                    st.session_state["loaded_session_id"] = None
                    st.success(f"Project '{proj_name}' created!")
                    st.rerun()
    else:
        st.session_state["current_project_id"] = selected_project_id
        
    system_type = st.selectbox("System Type", ["off-grid", "hybrid", "grid-tied"], index=1)
    agent.set_system_type(system_type)

    # ── Saved Chat Conversations ──────────────
    st.markdown("---")
    st.markdown("#### 💬 Saved Conversations")
    
    current_proj_id = st.session_state.get("current_project_id")
    chat_sessions_list = get_chat_sessions(current_proj_id) if (current_proj_id and current_proj_id != "__new__") else []
    
    sess_opts = {"__new_chat__": "➕ New Conversation"}
    for s in chat_sessions_list:
        title_str = s.get("title", "Conversation")
        date_str = str(s.get("updated_at", ""))[:10]
        sess_opts[s["id"]] = f"💬 {title_str} ({date_str})"
        
    col_s1, col_s2 = st.columns([4, 1])
    with col_s1:
        sel_session_id = st.selectbox(
            "Saved Chats",
            options=list(sess_opts.keys()),
            format_func=lambda x: sess_opts[x],
            key="chat_session_selector",
            label_visibility="collapsed"
        )
    with col_s2:
        if st.button("➕", help="Start New Conversation", use_container_width=True):
            st.session_state["current_session_id"] = None
            st.session_state["loaded_session_id"] = None
            st.session_state["messages"] = [
                {"role": "assistant", "content": f"Hi there! 👋 What would you like to design today? I'm set to **{system_type}** mode."}
            ]
            st.rerun()

    # Load session when selected
    if sel_session_id != "__new_chat__" and sel_session_id != st.session_state.get("loaded_session_id"):
        target_s = next((s for s in chat_sessions_list if s["id"] == sel_session_id), None)
        if target_s:
            st.session_state["current_session_id"] = target_s["id"]
            st.session_state["loaded_session_id"] = target_s["id"]
            saved_messages = target_s.get("messages", [])
            if saved_messages:
                st.session_state["messages"] = saved_messages
                agent.load_conversation_history(saved_messages)
            
            # Load stored system design for this conversation to restore Live Project panel & BOQ!
            try:
                designs = get_designs_for_project(current_proj_id)
                sess_design = next((d for d in designs if d.get("chat_session_id") == target_s["id"]), None) or (designs[0] if designs else None)
                if sess_design and sess_design.get("sizing_results"):
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
    
    st.markdown("---")
    st.caption("📎 Upload Site Report or Load Schedule:")
    sidebar_file = st.file_uploader("Upload PDF, CSV, Excel", type=["pdf", "docx", "xlsx", "xls", "csv", "png", "jpg"], key="sidebar_file_uploader", label_visibility="collapsed")
    if sidebar_file and st.session_state.get("_last_upload_sb") != sidebar_file.name:
        st.session_state["_last_upload_sb"] = sidebar_file.name
        if sidebar_file.name.endswith((".csv", ".xlsx", ".xls")):
            import pandas as pd
            from utils.file_parser import extract_loads_from_dataframe
            try:
                df_loads = pd.read_csv(sidebar_file) if sidebar_file.name.endswith(".csv") else pd.read_excel(sidebar_file)
                df_loads.columns = df_loads.columns.astype(str)
                csv_loads, _ = extract_loads_from_dataframe(df_loads)
                if csv_loads:
                    with st.spinner(f"⚡ Calculating system size from `{sidebar_file.name}`..."):
                        md_res, _ = agent.run_sizing(loads=csv_loads, location=agent.project_state.location)
                    st.session_state["messages"].append({"role": "user", "content": f"📎 *Uploaded file:* `{sidebar_file.name}`"})
                    st.session_state["messages"].append({"role": "assistant", "content": md_res})
                    st.rerun()
            except Exception as e:
                st.error(f"Error parsing `{sidebar_file.name}`: {e}")
        else:
            with st.spinner(f"📄 Analyzing `{sidebar_file.name}`..."):
                resp = agent.process_uploaded_file(sidebar_file.read(), sidebar_file.name, get_mime_type(sidebar_file.name))
            st.session_state["messages"].append({"role": "user", "content": f"📎 *Uploaded file:* `{sidebar_file.name}`"})
            st.session_state["messages"].append({"role": "assistant", "content": resp})
            st.rerun()

    st.markdown("---")
    render_sidebar_user()

# ── Main Layout: Center Chat & Right Panel ───
col_center, col_right = st.columns([2.5, 1], gap="large")

with col_center:
    # Top Bar: Greeting
    st.markdown("""
    <div style="display:flex; align-items:center; gap:20px; margin-bottom: 20px;">
        <div style="width:70px; height:70px; border-radius:50%; border:2px solid #38BDF8; display:flex; align-items:center; justify-content:center; background:#0F172A;">
            <h1 style="margin:0; padding:0; font-size:1.8rem;">☀️</h1>
        </div>
        <div>
            <h2 style="margin:0; margin-bottom:4px;">Hello! I'm your <span style="color:#10B981;">Solar Design Agent.</span></h2>
            <p style="margin:0;">Upload your site plan, electricity bill, or describe your project to begin.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick Actions
    st.caption("Try asking me to...")
    qa1, qa2, qa3, qa4 = st.columns(4)
    with qa1:
        if st.button("🏠 Design a 10kW residential system", use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": "Design a 10kW residential system"})
            st.rerun()
    with qa2:
        if st.button("🔋 Optimize battery capacity", use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": "Optimize battery capacity"})
            st.rerun()
    with qa3:
        if st.button("🛰️ Analyze shading from satellite", use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": "Analyze shading from satellite image"})
            st.rerun()
    with qa4:
        if st.button("📈 Estimate annual energy", use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": "Estimate annual energy production"})
            st.rerun()

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

    # Bottom floating action buttons
    b1, b2, b3, b4, _ = st.columns([1, 1, 1, 1, 3])
    with b1:
        st.markdown('<div class="action-pill">', unsafe_allow_html=True)
        if st.button("🛰️ Satellite View", use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": "Show Satellite View"})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with b2:
        st.markdown('<div class="action-pill">', unsafe_allow_html=True)
        if st.button("🔲 PV Layout", use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": "Generate PV Layout"})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with b3:
        st.markdown('<div class="action-pill">', unsafe_allow_html=True)
        if st.button("📋 BOM", use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": "Generate BOQ"})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with b4:
        if st.button("📊 Simulation", use_container_width=True):
            st.session_state["messages"].append({"role": "user", "content": "Run Simulation"})
            st.rerun()

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
        
        # Auto-save chat messages & sizing design to Supabase DB
        proj_id = st.session_state.get("current_project_id")
        if proj_id and proj_id != "__new__":
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
                    if agent.last_sizing_result:
                        save_design(user_id, proj_id, curr_sess_id, system_type, {}, agent.last_sizing_result.to_dict(), agent.last_boq_items)
            except Exception as e:
                print(f"DB auto-save error: {e}")
        st.rerun()

    # ── Interactive Quick Sizing & Manual Load Entry Form ──
    st.markdown("---")
    with st.expander("⚙️ Quick Sizing Form — Upload Spreadsheet or Enter Loads Manually", expanded=False):
        tab_csv, tab_manual = st.tabs(["📂 Upload Loads CSV / Excel", "✍️ Enter Loads Manually"])

        with tab_csv:
            st.markdown("Upload a `.csv` or `.xlsx` spreadsheet of your load schedule or interval logger data!")
            sample_csv = "name,wattage,quantity,hours_per_day\nLED Lighting & Office,15,20,10.0\nDesktop Computers,150,10,8.0\nAir Conditioning HVAC,2500,2,8.0\nCommercial Refrigerator,350,1,24.0\nWater Pumping Motor,1200,1,2.0\n"
            st.download_button("📥 Download Sample Loads CSV Template", data=sample_csv, file_name="sample_load_schedule.csv", mime="text/csv")

            load_file = st.file_uploader("Choose Load Schedule / Logger File (.csv or .xlsx)", type=["csv", "xlsx"], key="load_csv_uploader")
            if load_file:
                import pandas as pd
                try:
                    df_loads = pd.read_csv(load_file) if load_file.name.endswith(".csv") else pd.read_excel(load_file)
                    df_loads.columns = df_loads.columns.astype(str)
                    st.dataframe(make_arrow_compatible(df_loads))

                    col_u1, col_u2, col_u3 = st.columns(3)
                    with col_u1:
                        u_loc = st.text_input("Location", value=agent.project_state.location or "Nairobi, Kenya", key="u_loc")
                        u_wp = st.number_input("Panel Watt-peak (Wp)", value=625, step=25, key="u_wp")
                    with col_u2:
                        u_days = st.number_input("Days of Autonomy", value=2.0, min_value=0.5, max_value=7.0, step=0.5, key="u_days")
                        u_volt = st.selectbox("System Voltage (DC)", [12, 24, 48], index=2, key="u_volt")
                    with col_u3:
                        u_dod = st.slider("Battery DoD (%)", 50, 90, 80, key="u_dod") / 100
                        u_ah  = st.number_input("Battery Ah Rating", value=280, step=20, key="u_ah")

                    if st.button("⚡ Run Sizing from Uploaded File", key="run_csv_sizing", use_container_width=True):
                        from utils.file_parser import extract_loads_from_dataframe
                        csv_loads, _ = extract_loads_from_dataframe(df_loads)
                        if not csv_loads:
                            st.warning("No valid loads found in CSV/Excel. Ensure columns contain wattage or power values.")
                        else:
                            with st.spinner("Calculating system size..."):
                                md_result, _ = agent.run_sizing(
                                    loads=csv_loads,
                                    location=u_loc,
                                    days_of_autonomy=u_days,
                                    dod=u_dod,
                                    system_voltage_dc=int(u_volt),
                                    battery_ah_rating=int(u_ah),
                                    panel_wp=int(u_wp),
                                )
                            st.session_state["messages"].append({"role": "user", "content": f"📎 *Ran sizing from CSV:* `{load_file.name}`"})
                            st.session_state["messages"].append({"role": "assistant", "content": md_result})
                            st.success("✅ Sizing complete! Check the chat above.")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error parsing spreadsheet: {e}")

        with tab_manual:
            st.markdown("Fill in your load schedule manually and click **Run Sizing**.")

            col1, col2, col3 = st.columns(3)
            with col1:
                location = st.text_input("Location", value=agent.project_state.location or "Nairobi, Kenya", key="loc_input")
                panel_wp = st.number_input("Panel Watt-peak (Wp)", value=625, step=25, key="panel_wp")
            with col2:
                days_autonomy = st.number_input("Days of Autonomy", value=2.0, min_value=0.5, max_value=7.0, step=0.5, key="days_auto")
                sys_voltage   = st.selectbox("System Voltage (DC)", [12, 24, 48], index=2, key="sys_volt")
            with col3:
                dod         = st.slider("Battery DoD (%)", 50, 90, 80, key="dod_slider") / 100
                batt_ah     = st.number_input("Battery Ah Rating", value=280, step=20, key="batt_ah")

            st.markdown("#### ⚡ Load Schedule")
            load_count = st.number_input("Number of loads", min_value=1, max_value=20, value=3, key="load_count")

            loads = []
            for i in range(int(load_count)):
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                with c1:
                    lname = st.text_input(f"Load {i+1} Name", key=f"lname_{i}", placeholder="e.g. LED Light")
                with c2:
                    lwatt = st.number_input("Watts", key=f"lwatt_{i}", min_value=0, value=10)
                with c3:
                    lqty  = st.number_input("Qty",   key=f"lqty_{i}",  min_value=1, value=1)
                with c4:
                    lhrs  = st.number_input("Hrs/day", key=f"lhrs_{i}", min_value=0.0, value=8.0, step=0.5)
                if lname and lwatt > 0:
                    loads.append({"name": lname, "wattage": lwatt, "quantity": lqty, "hours_per_day": lhrs})

            if st.button("🔆 Run Sizing (Manual)", key="run_sizing", use_container_width=True):
                if not loads:
                    st.warning("Please add at least one load.")
                else:
                    with st.spinner("Calculating system size..."):
                        md_result, _ = agent.run_sizing(
                            loads=loads,
                            location=location,
                            days_of_autonomy=float(days_autonomy),
                            dod=dod,
                            system_voltage_dc=int(sys_voltage),
                            battery_ah_rating=int(batt_ah),
                            panel_wp=int(panel_wp),
                        )
                    st.session_state["messages"].append({"role": "user", "content": "⚡ *Submitted manual load schedule*" })
                    st.session_state["messages"].append({"role": "assistant", "content": md_result})
                    st.success("✅ Sizing complete! Check the chat above.")
                    st.rerun()

    # ── Equipment Datasheets & Component Reference Library ──
    with st.expander("📚 Equipment Datasheets & Component Reference Library", expanded=False):
        st.markdown("Upload equipment datasheets (**PV Modules, Inverters, Battery Energy Storage Systems, Protection Switchgear**) in PDF, Word, Excel, CSV, or Image format. SolarBot will index the technical specifications and use them for stringing, voltage limits, and component selection!")
        
        ds_file = st.file_uploader("Upload Equipment Datasheet / Spec Sheet (.pdf, .docx, .png, .jpg, .xlsx, .csv)", type=["pdf", "docx", "png", "jpg", "xlsx", "csv"], key="datasheet_library_uploader")
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
    inv = f"{res.inverter_qty}x {res.inverter_kw:.1f}kW {res.system_type.capitalize()}" if res else "---"
    batt = f"{res.battery_qty}x {res.battery_module_kwh}kWh" if res and res.system_type != 'grid-tied' else "---"
    load = f"{res.daily_energy_wh/1000:.1f} kWh/day" if res else "---"
    psh = f"{res.peak_sun_hours} h/day" if res else "---"
    savings = "KES --- / year"
    
    st.markdown(f"""
    <div class="live-metric-row"><span class="live-metric-label">📍 Location</span><span class="live-metric-val">{loc}</span></div>
    <div class="live-metric-row"><span class="live-metric-label">📐 Roof Area</span><span class="live-metric-val">{roof}</span></div>
    <div class="live-metric-row"><span class="live-metric-label">🔲 Panel Count</span><span class="live-metric-val">{panels}</span></div>
    <div class="live-metric-row"><span class="live-metric-label">⚡ Inverter</span><span class="live-metric-val">{inv}</span></div>
    <div class="live-metric-row"><span class="live-metric-label">🔋 Battery</span><span class="live-metric-val">{batt}</span></div>
    <div class="live-metric-row"><span class="live-metric-label">🔌 Daily Load</span><span class="live-metric-val">{load}</span></div>
    <div class="live-metric-row"><span class="live-metric-label">☀️ Peak Sun Hours</span><span class="live-metric-val">{psh}</span></div>
    <div class="live-metric-row"><span class="live-metric-label" style="color:#10B981;">💲 Estimated Savings</span><span class="live-metric-val" style="color:#10B981;">{savings}</span></div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Summary Card
    sys_size = f"{res.total_pv_kwp:.2f} kW" if res else "0.00 kW"
    prod = f"{((res.daily_energy_wh/1000) * 365):,.0f} kWh" if res else "0 kWh"
    
    st.markdown(f"""
    <div class="dashboard-card" style="border-color:#3B82F6; background: linear-gradient(180deg, #111827 0%, #1E3A8A20 100%);">
        <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
            <div style="text-align:center;">
                <span style="font-size:0.8rem;">System Size</span><br>
                <strong style="font-size:1.4rem; color:#F8FAFC;">{sys_size}</strong><br>
                <span style="font-size:0.8rem;">DC</span>
            </div>
            <div style="text-align:center;">
                <span style="font-size:0.8rem;">Annual Production</span><br>
                <strong style="font-size:1.4rem; color:#F8FAFC;">{prod}</strong><br>
                <span style="font-size:0.8rem;">Est.</span>
            </div>
        </div>
        <button style="width:100%; padding:10px; background:#1E293B; border:1px solid #334155; border-radius:6px; color:#94A3B8; cursor:pointer;">
            📄 View Detailed Report
        </button>
    </div>
    """, unsafe_allow_html=True)
    
    # File Uploader in right panel
    st.markdown("---")
    st.caption("Upload File or Load Schedule")
    uploaded_file = st.file_uploader("Drop here", label_visibility="collapsed", type=["csv", "xlsx", "pdf", "docx"], key="right_panel_uploader")
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
                    st.rerun()
            except Exception as e:
                st.error(f"Error parsing file: {e}")
        else:
            with st.spinner("Analyzing document..."):
                resp = agent.process_uploaded_file(uploaded_file.read(), uploaded_file.name, get_mime_type(uploaded_file.name))
                st.session_state["messages"].append({"role": "user", "content": f"📎 *Uploaded {uploaded_file.name}*"})
                st.session_state["messages"].append({"role": "assistant", "content": resp})
                st.rerun()
