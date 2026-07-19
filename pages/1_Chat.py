"""
pages/1_Chat.py — Main agent chat interface with sidebar controls and file upload.
"""
import streamlit as st
import json
import importlib
import agent.boq_generator
import agent.system_sizer
import agent.report_analyzer
import agent.orchestrator

importlib.reload(agent.boq_generator)
importlib.reload(agent.system_sizer)
importlib.reload(agent.report_analyzer)
importlib.reload(agent.orchestrator)
from auth.login import require_login, render_sidebar_user
from agent.orchestrator import SolarAgent
from utils.file_parser import get_mime_type
from db.queries import (
    create_project, get_user_projects, create_chat_session,
    update_chat_messages, save_design
)
from utils.helpers import system_type_badge

# ── Page config ──────────────────────────────
st.set_page_config(page_title="Chat & Design | Solar Agent", page_icon="💬", layout="wide")

# ── Auth guard ───────────────────────────────
if not require_login():
    st.stop()

# ── Global styles (reuse from app.py) ────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%); color: #E2E8F0; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0F172A 0%, #1E3A5F 100%); border-right: 1px solid #334155; }
[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
h1, h2, h3 { color: #F59E0B !important; }
.stButton > button { background: linear-gradient(135deg, #F59E0B, #D97706); color: #0F172A; font-weight: 600; border: none; border-radius: 8px; transition: all 0.2s ease; }
.stButton > button:hover { background: linear-gradient(135deg, #FBBF24, #F59E0B); transform: translateY(-1px); box-shadow: 0 4px 15px rgba(245,158,11,0.4); }
.stTextInput > div > div > input, .stTextArea > div > div > textarea, .stSelectbox > div > div { background: #1E293B !important; color: #E2E8F0 !important; border: 1px solid #334155 !important; border-radius: 8px !important; }
.stTextInput > div > div > input:focus { border-color: #F59E0B !important; box-shadow: 0 0 0 2px rgba(245,158,11,0.2) !important; }
[data-testid="stFileUploader"] { background: #1E293B; border: 2px dashed #334155; border-radius: 12px; }
.stTabs [data-baseweb="tab-list"] { background: #1E293B; border-radius: 8px; gap: 4px; }
.stTabs [data-baseweb="tab"] { background: transparent; color: #94A3B8; border-radius: 6px; }
.stTabs [aria-selected="true"] { background: #F59E0B !important; color: #0F172A !important; font-weight: 600; }
hr { border-color: #334155 !important; }
::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: #0F172A; } ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

render_sidebar_user()
st.sidebar.markdown("---")

# ── Sidebar Controls ─────────────────────────
st.sidebar.markdown("## ⚙️ System Configuration")

system_type = st.sidebar.selectbox(
    "System Type",
    options=["off-grid", "hybrid", "grid-tied"],
    format_func=lambda x: {"off-grid": "🔋 Off-Grid", "hybrid": "⚡ Hybrid", "grid-tied": "🌐 Grid-Tied"}[x],
    key="system_type_select"
)

# Initialize agent to display brain status badge (re-init if old cached object in session state)
if "agent" not in st.session_state or getattr(st.session_state["agent"], "version", "") != "3.1":
    try:
        st.session_state["agent"] = SolarAgent()
    except EnvironmentError as e:
        st.error(f"⚠️ {e}")
        st.info("Please set your FEATHERLESS_API_KEY, GITHUB_TOKEN, or GEMINI_API_KEY in the .env file and restart.")
        st.stop()
agent: SolarAgent = st.session_state["agent"]

active_engine = getattr(agent, "active_engine", "gemini")
if active_engine == "featherless":
    brain_label = f"🪶 Featherless AI (`{getattr(agent, 'featherless_model', 'DeepSeek-V3.1')}`)"
elif active_engine == "github-gpt-4o":
    brain_label = f"🚀 GitHub Models (`{getattr(agent, 'github_model', 'gpt-4o')}`)"
else:
    brain_label = "⚡ Google Gemini"
st.sidebar.markdown(f"**🧠 Active AI Brain:** {brain_label}")

st.sidebar.markdown("---")
st.sidebar.markdown("## 📁 Project")

user_id = st.session_state["user"].id
projects = get_user_projects(user_id)

project_options = {p["id"]: p["name"] for p in projects}
project_options["__new__"] = "➕ Create New Project"

selected_project_id = st.sidebar.selectbox(
    "Select Project",
    options=list(project_options.keys()),
    format_func=lambda x: project_options[x],
    key="selected_project"
)

if selected_project_id == "__new__":
    with st.sidebar.form("new_project_form"):
        proj_name = st.text_input("Project Name", placeholder="e.g. Mombasa Farm Solar")
        proj_loc  = st.text_input("Location",     placeholder="e.g. Mombasa, Kenya")
        submitted = st.form_submit_button("Create Project")
        if submitted and proj_name:
            new_proj = create_project(user_id, proj_name, system_type, proj_loc)
            if new_proj.get("id"):
                st.session_state["current_project_id"] = new_proj["id"]
                st.success(f"Project '{proj_name}' created!")
                st.rerun()
else:
    st.session_state["current_project_id"] = selected_project_id

st.sidebar.markdown("---")
st.sidebar.markdown("## 📎 Upload File")
uploaded_file = st.sidebar.file_uploader(
    "Site visit report, load schedule...",
    type=["pdf", "docx", "xlsx", "xls", "csv", "png", "jpg", "jpeg", "txt"],
    key="file_uploader"
)

if st.sidebar.button("🗑️ Clear Chat", use_container_width=True):
    st.session_state.pop("messages", None)
    st.session_state.pop("agent",    None)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("☀️ Solar Design Agent v1.0")

agent: SolarAgent = st.session_state["agent"]
agent.set_system_type(system_type)

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": (
                "👋 **Welcome to Solar Design Agent!**\n\n"
                "I'm **SolarBot**, your AI solar PV design engineer. I can help you with:\n\n"
                "- ⚡ **System sizing** — panels, batteries, inverter, charge controller\n"
                "- 📋 **Bill of Quantities (BOQ)** — complete component list with quantities\n"
                "- 📄 **Site visit report analysis** — upload a report and I'll extract the data\n\n"
                f"**Current system type:** {system_type_badge(system_type)}\n\n"
                "To get started, tell me about your project or upload a site visit report from the sidebar!"
            )
        }
    ]

if "boq_excel" not in st.session_state:
    st.session_state["boq_excel"] = None

# ─────────────────────────────────────────────
# Main Chat Area
# ─────────────────────────────────────────────
st.markdown("# 💬 Chat & Design")
st.markdown(f"**Active system:** {system_type_badge(system_type)}")
st.markdown("---")

# ── Process uploaded file ────────────────────
if uploaded_file and st.session_state.get("_last_upload") != uploaded_file.name:
    st.session_state["_last_upload"] = uploaded_file.name
    with st.spinner(f"📄 Analyzing {uploaded_file.name}..."):
        file_bytes = uploaded_file.read()
        mime = get_mime_type(uploaded_file.name)
        response = agent.process_uploaded_file(file_bytes, uploaded_file.name, mime)
    st.session_state["messages"].append({
        "role": "user",
        "content": f"📎 *Uploaded file:* `{uploaded_file.name}`"
    })
    st.session_state["messages"].append({"role": "assistant", "content": response})

# ── Render Messages ──────────────────────────
chat_container = st.container()
with chat_container:
    for msg in st.session_state["messages"]:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="☀️"):
                st.markdown(msg["content"])

# ── Chat Input ───────────────────────────────
user_input = st.chat_input("Ask SolarBot anything about your solar project...", key="chat_input")

if user_input:
    # Show user message immediately
    st.session_state["messages"].append({"role": "user", "content": user_input})

    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="☀️"):
        with st.spinner("🔆 SolarBot is thinking..."):
            response_text, boq_excel, boq_items = agent.chat_message(user_input)

        st.markdown(response_text)

        if boq_excel:
            st.session_state["boq_excel"] = boq_excel

    st.session_state["messages"].append({"role": "assistant", "content": response_text})

    # Save to Supabase if project selected
    proj_id = st.session_state.get("current_project_id")
    if proj_id and proj_id != "__new__":
        history = agent.get_conversation_history()
        try:
            if "current_session_id" not in st.session_state:
                session = create_chat_session(user_id, proj_id, "Design Session")
                st.session_state["current_session_id"] = session.get("id")
            if st.session_state.get("current_session_id"):
                update_chat_messages(st.session_state["current_session_id"], history)
        except Exception:
            pass  # Non-critical

# ── Sizing Form (Quick Input or CSV Upload) ───
st.markdown("---")
with st.expander("⚙️ Quick Sizing Form — Upload CSV / Excel or Enter Loads Manually", expanded=False):
    tab_csv, tab_manual = st.tabs(["📂 Upload Loads CSV / Excel", "✍️ Enter Loads Manually"])

    with tab_csv:
        st.markdown("Upload a `.csv` or `.xlsx` spreadsheet of your load schedule so you don't have to type appliances manually!")
        sample_csv = "name,wattage,quantity,hours_per_day\nLED Lighting & Office,15,20,10.0\nDesktop Computers,150,10,8.0\nAir Conditioning HVAC,2500,2,8.0\nCommercial Refrigerator,350,1,24.0\nWater Pumping Motor,1200,1,2.0\n"
        st.download_button("📥 Download Sample Loads CSV Template", data=sample_csv, file_name="sample_load_schedule.csv", mime="text/csv")

        load_file = st.file_uploader("Choose Load Schedule File (.csv or .xlsx)", type=["csv", "xlsx"], key="load_csv_uploader")
        if load_file:
            import pandas as pd
            try:
                if load_file.name.endswith(".csv"):
                    df_loads = pd.read_csv(load_file)
                else:
                    df_loads = pd.read_excel(load_file)
                st.dataframe(df_loads, use_container_width=True)

                col_u1, col_u2, col_u3 = st.columns(3)
                with col_u1:
                    u_loc = st.text_input("Location", value="Nairobi, Kenya", key="u_loc")
                    u_wp = st.number_input("Panel Watt-peak (Wp)", value=625, step=25, key="u_wp")
                with col_u2:
                    u_days = st.number_input("Days of Autonomy", value=2.0, min_value=0.5, max_value=7.0, step=0.5, key="u_days")
                    u_volt = st.selectbox("System Voltage (DC)", [12, 24, 48], index=2, key="u_volt")
                with col_u3:
                    u_dod = st.slider("Battery DoD (%)", 50, 90, 80, key="u_dod") / 100
                    u_ah  = st.number_input("Battery Ah Rating", value=280, step=20, key="u_ah")

                if st.button("⚡ Run Sizing from Uploaded CSV", key="run_csv_sizing", use_container_width=True):
                    from utils.file_parser import extract_loads_from_dataframe
                    csv_loads, is_time_series = extract_loads_from_dataframe(df_loads)
                    if not csv_loads:
                        st.warning("No valid loads found in CSV/Excel. Ensure columns contain active/apparent power ratings or numeric values.")
                    else:
                        with st.spinner("Calculating system size from CSV..."):
                            md_result, sizing_result = agent.run_sizing(
                                loads=csv_loads,
                                location=u_loc,
                                days_of_autonomy=u_days,
                                dod=u_dod,
                                system_voltage_dc=int(u_volt),
                                battery_ah_rating=int(u_ah),
                                panel_wp=int(u_wp),
                            )
                        st.session_state["messages"].append({"role": "assistant", "content": md_result})
                        st.success("✅ Sizing complete from uploaded CSV! Check the chat above.")
                        st.rerun()
            except Exception as e:
                st.error(f"Error parsing spreadsheet: {e}")

    with tab_manual:
        st.markdown("Fill in your load schedule and click **Run Sizing** to calculate the system.")

        col1, col2, col3 = st.columns(3)
        with col1:
            location = st.text_input("Location", placeholder="e.g. Nairobi, Kenya", key="loc_input")
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
                    md_result, sizing_result = agent.run_sizing(
                        loads=loads,
                        location=location,
                        days_of_autonomy=float(days_autonomy),
                        dod=dod,
                        system_voltage_dc=int(sys_voltage),
                        battery_ah_rating=int(batt_ah),
                        panel_wp=int(panel_wp),
                    )
                st.session_state["messages"].append({"role": "assistant", "content": md_result})
                st.success("✅ Sizing complete! Check the chat above.")
                st.rerun()

# ── BOQ Download Button ──────────────────────
if agent.last_boq_excel or st.session_state.get("boq_excel"):
    excel_data = agent.last_boq_excel or st.session_state["boq_excel"]
    st.markdown("---")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.success("✅ BOQ ready for download!")
    with col2:
        st.download_button(
            label="📥 Download BOQ (Excel)",
            data=excel_data,
            file_name="Solar_BOQ.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # Save to Supabase
    proj_id = st.session_state.get("current_project_id")
    if proj_id and proj_id != "__new__" and agent.last_sizing_result:
        try:
            save_design(
                user_id=user_id,
                project_id=proj_id,
                session_id=st.session_state.get("current_session_id", ""),
                system_type=system_type,
                inputs={},
                sizing_results=agent.last_sizing_result.to_dict(),
                boq_data=agent.last_boq_items,
            )
        except Exception:
            pass
