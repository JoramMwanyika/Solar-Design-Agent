"""
pages/2_My_Projects.py — View and manage saved solar design projects.
"""
import streamlit as st
import json
from auth.login import require_login, render_sidebar_user
from db.queries import (
    get_user_projects, get_designs_for_project,
    delete_project, update_project_status, get_chat_sessions
)
from agent.boq_generator import generate_boq_excel
from utils.helpers import format_datetime, system_type_badge, truncate

# ── Page config ──────────────────────────────
st.set_page_config(page_title="My Projects | Solar Agent", page_icon="📁", layout="wide")

if not require_login():
    st.stop()

# ── Styles ───────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%); color: #E2E8F0; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0F172A 0%, #1E3A5F 100%); border-right: 1px solid #334155; }
[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
h1, h2, h3, h4 { color: #F59E0B !important; }
.stButton > button { background: linear-gradient(135deg, #F59E0B, #D97706); color: #0F172A; font-weight: 600; border: none; border-radius: 8px; }
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 15px rgba(245,158,11,0.4); }
.project-card { background: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 1.2rem; margin: 0.5rem 0; transition: all 0.2s; }
.project-card:hover { border-color: #F59E0B66; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; margin-right: 6px; }
.badge-offgrid { background: #1e3a5f; color: #60a5fa; }
.badge-hybrid  { background: #1c2a1e; color: #4ade80; }
.badge-grid    { background: #2a1c1e; color: #f87171; }
.badge-active  { background: #052e16; color: #4ade80; }
.badge-archived{ background: #1c1c2a; color: #94a3b8; }
hr { border-color: #334155 !important; }
</style>
""", unsafe_allow_html=True)

render_sidebar_user()
st.sidebar.markdown("---")
st.sidebar.page_link("pages/1_Chat.py",        label="💬 Chat & Design")
st.sidebar.page_link("pages/2_My_Projects.py", label="📁 My Projects")
if st.session_state.get("is_admin"):
    st.sidebar.page_link("pages/3_Admin.py",   label="👑 Admin Panel")

user_id = st.session_state["user"].id

# ─────────────────────────────────────────────
# Page Header
# ─────────────────────────────────────────────
st.markdown("# 📁 My Projects")
st.markdown("View your saved solar design projects and download their BOQs.")
st.markdown("---")

# ─────────────────────────────────────────────
# Load Projects
# ─────────────────────────────────────────────
projects = get_user_projects(user_id)

if not projects:
    st.info("You don't have any projects yet. Go to **💬 Chat & Design** to start one!")
    st.stop()

# ─────────────────────────────────────────────
# Project List
# ─────────────────────────────────────────────
for proj in projects:
    pid        = proj["id"]
    pname      = proj["name"]
    ptype      = proj.get("system_type", "")
    ploc       = proj.get("location", "")
    pstatus    = proj.get("status", "active")
    pcreated   = format_datetime(proj.get("created_at", ""))

    badge_class = {"off-grid": "badge-offgrid", "hybrid": "badge-hybrid", "grid-tied": "badge-grid"}.get(ptype, "badge-offgrid")

    with st.expander(f"📂 {pname}  —  {system_type_badge(ptype)}  |  📍 {ploc or 'No location'}  |  🗓️ {pcreated}", expanded=False):
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown(f"**Project:** {pname}")
            st.markdown(f"**Type:** {system_type_badge(ptype)}")
            if ploc:
                st.markdown(f"**Location:** {ploc}")
        with col2:
            st.markdown(f"**Status:** {pstatus.title()}")
            st.markdown(f"**Created:** {pcreated}")
        with col3:
            if pstatus == "active":
                if st.button("📦 Archive", key=f"arch_{pid}", use_container_width=True):
                    update_project_status(pid, "archived")
                    st.rerun()
            if st.button("🗑️ Delete", key=f"del_{pid}", use_container_width=True):
                st.session_state[f"confirm_del_{pid}"] = True

            if st.session_state.get(f"confirm_del_{pid}"):
                st.warning("Are you sure? This will delete all data.")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✅ Yes, Delete", key=f"yes_del_{pid}"):
                        delete_project(pid)
                        st.success("Deleted.")
                        st.rerun()
                with col_b:
                    if st.button("❌ Cancel", key=f"no_del_{pid}"):
                        st.session_state.pop(f"confirm_del_{pid}", None)
                        st.rerun()

        st.markdown("---")

        # ── Saved Designs ────────────────────
        designs = get_designs_for_project(pid)
        if designs:
            st.markdown(f"### 📋 Saved Designs ({len(designs)})")
            for design in designs:
                sizing = design.get("sizing_results", {})
                boq    = design.get("boq_data", [])
                dcreated = format_datetime(design.get("created_at", ""))
                dtype  = design.get("system_type", ptype)

                dcol1, dcol2, dcol3 = st.columns([2, 1, 1])
                with dcol1:
                    st.markdown(f"**Design** — {system_type_badge(dtype)} — {dcreated}")
                    if sizing:
                        st.caption(
                            f"Array: {sizing.get('panel_qty','?')} × {sizing.get('panel_wp','?')}Wp | "
                            f"Inverter: {sizing.get('inverter_kva','?')} kVA | "
                            f"Battery: {sizing.get('total_batteries','?')} units"
                        )
                with dcol2:
                    if boq:
                        st.caption(f"BOQ: {len(boq)} line items")
                with dcol3:
                    if boq and sizing:
                        excel_bytes = generate_boq_excel(
                            boq_items=boq,
                            project_name=pname,
                            system_type=dtype,
                            location=ploc,
                            sizing_summary=sizing,
                        )
                        st.download_button(
                            label="📥 Download BOQ",
                            data=excel_bytes,
                            file_name=f"{pname.replace(' ','_')}_BOQ.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_{design['id']}",
                            use_container_width=True,
                        )
        else:
            st.info("No designs saved yet for this project.")
