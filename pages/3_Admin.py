"""
pages/3_Admin.py — Admin panel for user management.
Only accessible to users with role='admin'.
"""
import streamlit as st
from auth.login import require_admin, render_sidebar_user
from auth.admin import (
    list_all_users, create_user, set_user_active,
    reset_user_password, generate_temp_password
)
from utils.helpers import format_datetime

# ── Page config ──────────────────────────────
st.set_page_config(page_title="Admin Panel | Solar Agent", page_icon="👑", layout="wide")

if not require_admin():
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
.stTextInput > div > div > input, .stSelectbox > div > div { background: #1E293B !important; color: #E2E8F0 !important; border: 1px solid #334155 !important; border-radius: 8px !important; }
.stDataFrame { background: #1E293B !important; }
.admin-stat { background: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 1rem; text-align: center; }
hr { border-color: #334155 !important; }
</style>
""", unsafe_allow_html=True)

render_sidebar_user()
st.sidebar.markdown("---")
st.sidebar.page_link("pages/1_Chat.py",        label="💬 Chat & Design")
st.sidebar.page_link("pages/2_My_Projects.py", label="📁 My Projects")
st.sidebar.page_link("pages/3_Admin.py",        label="👑 Admin Panel")

# ─────────────────────────────────────────────
# Page Header
# ─────────────────────────────────────────────
st.markdown("# 👑 Admin Panel")
st.markdown("Manage users, roles, and access.")
st.markdown("---")

# ─────────────────────────────────────────────
# Load Users
# ─────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_users():
    return list_all_users()

users = load_users()

# ── Stats Row ────────────────────────────────
total     = len(users)
admins    = sum(1 for u in users if u.get("role") == "admin")
actives   = sum(1 for u in users if u.get("is_active", True))
inactive  = total - actives

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""<div class='admin-stat'><h2 style='color:#F59E0B;margin:0'>{total}</h2><p style='color:#94A3B8;margin:0'>Total Users</p></div>""", unsafe_allow_html=True)
with col2:
    st.markdown(f"""<div class='admin-stat'><h2 style='color:#4ade80;margin:0'>{actives}</h2><p style='color:#94A3B8;margin:0'>Active</p></div>""", unsafe_allow_html=True)
with col3:
    st.markdown(f"""<div class='admin-stat'><h2 style='color:#f87171;margin:0'>{inactive}</h2><p style='color:#94A3B8;margin:0'>Inactive</p></div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""<div class='admin-stat'><h2 style='color:#c084fc;margin:0'>{admins}</h2><p style='color:#94A3B8;margin:0'>Admins</p></div>""", unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────
tab_users, tab_create, tab_reset = st.tabs(["👥 User List", "➕ Create User", "🔑 Reset Password"])

# ── Tab 1: User List ─────────────────────────
with tab_users:
    st.markdown("### 👥 All Users")

    if not users:
        st.info("No users found.")
    else:
        search = st.text_input("🔍 Search by name or email", key="user_search")

        filtered = [u for u in users if
                    search.lower() in (u.get("full_name","")).lower() or
                    search.lower() in (u.get("email","")).lower()
                   ] if search else users

        for u in filtered:
            uid       = u["id"]
            uname     = u.get("full_name", "—")
            uemail    = u.get("email", "—")
            urole     = u.get("role", "user")
            uactive   = u.get("is_active", True)
            ucreated  = format_datetime(u.get("created_at", ""))

            active_icon = "🟢" if uactive else "🔴"
            role_icon   = "👑" if urole == "admin" else "👤"

            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 2, 1, 1, 2])
                with col1:
                    st.markdown(f"**{role_icon} {uname}**")
                    st.caption(uemail)
                with col2:
                    st.markdown(f"*Created: {ucreated}*")
                with col3:
                    st.markdown(f"**{active_icon} {'Active' if uactive else 'Inactive'}**")
                with col4:
                    st.markdown(f"**{urole.title()}**")
                with col5:
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if uactive:
                            if st.button("⛔ Deactivate", key=f"deact_{uid}", use_container_width=True):
                                set_user_active(uid, False)
                                st.cache_data.clear()
                                st.success(f"Deactivated {uname}")
                                st.rerun()
                        else:
                            if st.button("✅ Activate", key=f"act_{uid}", use_container_width=True):
                                set_user_active(uid, True)
                                st.cache_data.clear()
                                st.success(f"Activated {uname}")
                                st.rerun()
                st.markdown("<hr style='margin: 0.3rem 0; border-color: #1E293B;'>", unsafe_allow_html=True)

# ── Tab 2: Create User ───────────────────────
with tab_create:
    st.markdown("### ➕ Create New User")

    with st.form("create_user_form"):
        c1, c2 = st.columns(2)
        with c1:
            new_name  = st.text_input("Full Name *", placeholder="e.g. John Kamau")
            new_email = st.text_input("Email Address *", placeholder="john@company.com")
        with c2:
            new_role  = st.selectbox("Role", ["user", "admin"])
            auto_pwd  = st.checkbox("Auto-generate password", value=True)

        if auto_pwd:
            st.info("A secure temporary password will be generated automatically.")
            new_pwd   = ""
            new_pwd2  = ""
        else:
            new_pwd   = st.text_input("Password *", type="password", min_chars=8)
            new_pwd2  = st.text_input("Confirm Password *", type="password")

        submitted = st.form_submit_button("🚀 Create User", use_container_width=True)

        if submitted:
            # Validation
            if not new_name or not new_email:
                st.error("Name and email are required.")
            elif not auto_pwd and new_pwd != new_pwd2:
                st.error("Passwords do not match.")
            elif not auto_pwd and len(new_pwd) < 8:
                st.error("Password must be at least 8 characters.")
            else:
                password = generate_temp_password() if auto_pwd else new_pwd
                try:
                    result = create_user(new_name, new_email, password, new_role)
                    st.success(f"✅ User **{new_name}** created successfully!")
                    if auto_pwd:
                        st.code(f"Temporary password: {password}", language=None)
                        st.warning("⚠️ Share this password securely. The user should change it on first login.")
                    st.cache_data.clear()
                except Exception as e:
                    err = str(e)
                    if "already registered" in err.lower() or "already been registered" in err.lower():
                        st.error(f"A user with email **{new_email}** already exists.")
                    else:
                        st.error(f"Failed to create user: {err}")

# ── Tab 3: Reset Password ────────────────────
with tab_reset:
    st.markdown("### 🔑 Reset User Password")

    user_map = {u["id"]: f"{u.get('full_name','?')} ({u.get('email','?')})" for u in users}

    if not user_map:
        st.info("No users available.")
    else:
        selected_uid = st.selectbox(
            "Select User", options=list(user_map.keys()),
            format_func=lambda x: user_map[x], key="reset_user_select"
        )

        with st.form("reset_pwd_form"):
            auto_reset = st.checkbox("Auto-generate new password", value=True)
            manual_pwd = st.text_input("New Password", type="password", disabled=auto_reset)
            reset_sub  = st.form_submit_button("🔄 Reset Password", use_container_width=True)

            if reset_sub:
                new_pass = generate_temp_password() if auto_reset else manual_pwd
                if not auto_reset and len(new_pass) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    try:
                        reset_user_password(selected_uid, new_pass)
                        st.success("✅ Password reset successfully!")
                        st.code(f"New password: {new_pass}", language=None)
                        st.warning("⚠️ Share this password securely with the user.")
                    except Exception as e:
                        st.error(f"Failed to reset password: {e}")
