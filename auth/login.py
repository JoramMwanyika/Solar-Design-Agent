"""
Login / Logout UI helpers rendered within Streamlit pages.
"""
import streamlit as st
from auth.supabase_client import get_client
from db.queries import get_profile


def render_login_page():
    """Renders the full login page. Sets st.session_state on success."""
    st.markdown("""
    <style>
    .login-header { text-align: center; padding: 2rem 0 1rem; }
    .login-card { max-width:520px; margin: 0 auto; background: linear-gradient(180deg,#071228,#0b1420); padding:22px; border-radius:12px; border:1px solid #13202b }
    .login-header h1 { font-size: 2.0rem; color: #10B981; margin:0 }
    .login-header p  { color: #94A3B8; font-size: 0.95rem; margin:6px 0 12px }
    .login-note { color:#94A3B8; font-size:0.85rem; margin-top:8px }
    </style>
    <div class="login-header">
        <h1>☀️ Solar Design Agent</h1>
        <p>AI-powered PV sizing, design & BOQ generation</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.markdown("""
        <div class="login-card">
        """, unsafe_allow_html=True)
        with st.form("login_form", clear_on_submit=False):
            st.markdown("### 🔐 Sign In")
            email    = st.text_input("Email address", placeholder="you@company.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
                return

            try:
                client = get_client()
                res = client.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                if res.user:
                    profile = get_profile(res.user.id)
                    if not profile:
                        st.error("Profile not found. Contact your administrator.")
                        return
                    if not profile.get("is_active", True):
                        st.error("Your account has been deactivated. Contact your administrator.")
                        client.auth.sign_out()
                        return

                    # Persist session
                    st.session_state["user"]         = res.user
                    st.session_state["profile"]      = profile
                    st.session_state["access_token"] = res.session.access_token
                    st.session_state["is_admin"]     = profile.get("role") == "admin"
                    st.success("Logged in successfully!")
                    st.rerun()
            except Exception as e:
                err = str(e)
                if "Invalid login credentials" in err:
                    st.error("Invalid email or password.")
                elif "11001" in err or "getaddrinfo failed" in err or "ConnectError" in err:
                    st.error("🌐 Network Connection Error: Unable to resolve Supabase server (DNS or Internet connection is offline).")
                    st.info("💡 Tip: Click **⚡ Continue in Offline / Guest Mode** below to use SolarBot fully offline!")
                else:
                    st.error(f"Login error: {err}")

        st.markdown("<div style='margin-top: 15px;'>", unsafe_allow_html=True)
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            if st.button("⚡ Offline User", use_container_width=True, help="Bypass network login as standard user"):
                class GuestUser:
                    id = "offline-guest-id"
                    email = "guest@local"
                st.session_state["user"] = GuestUser()
                st.session_state["profile"] = {"id": "offline-guest-id", "full_name": "Solar Design Guest", "role": "user", "is_active": True}
                st.session_state["access_token"] = "offline-token"
                st.session_state["is_admin"] = False
                st.success("Entered Offline User Mode!")
                st.rerun()
        with col_g2:
            if st.button("👑 Offline Admin", use_container_width=True, help="Bypass network login with full Admin Rights"):
                class AdminGuestUser:
                    id = "00000000-0000-0000-0000-000000000001"
                    email = "admin@solaragent.com"
                st.session_state["user"] = AdminGuestUser()
                st.session_state["profile"] = {"id": "00000000-0000-0000-0000-000000000001", "full_name": "Admin Lead Engineer", "role": "admin", "is_active": True}
                st.session_state["access_token"] = "offline-admin-token"
                st.session_state["is_admin"] = True
                st.success("Entered Admin Mode with Full Admin Rights!")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("""
        <div class="login-note">Tip: Use the Offline buttons to try the app without a network connection.</div>
        """, unsafe_allow_html=True)


def render_sidebar_user():
    """Renders the user info block + logout button in the sidebar."""
    profile = st.session_state.get("profile", {})
    name    = profile.get("full_name", "User")
    role    = profile.get("role", "user")
    badge   = "👑 Admin" if role == "admin" else "👤 User"
    # derive initials for avatar
    initials = "".join([p[0] for p in name.split()][:2]).upper() if name else "U"
    st.sidebar.markdown(f"""
    <div style='display:flex;align-items:center;gap:10px;padding:0.6rem 0;border-bottom:1px solid #334155;margin-bottom:0.8rem;'>
      <div style='width:44px;height:44px;border-radius:10px;background:#0ea5e9;color:#021124;display:flex;align-items:center;justify-content:center;font-weight:700'>{initials}</div>
      <div>
        <div style='color:#F59E0B;font-weight:700'>{name}</div>
        <div style='font-size:0.8rem;color:#94A3B8'>{badge}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if st.sidebar.button("🚪 Logout", use_container_width=True):
        _logout()


def _logout():
    """Clears session and signs out from Supabase."""
    try:
        get_client().auth.sign_out()
    except Exception:
        pass
    for key in ["user", "profile", "access_token", "is_admin",
                "messages", "current_project_id", "current_session_id"]:
        st.session_state.pop(key, None)
    st.rerun()


def require_login():
    """
    Call at the top of every page to guard access.
    Returns True if logged in, False (and renders login page) otherwise.
    """
    if "user" not in st.session_state:
        render_login_page()
        return False
    return True


def require_admin():
    """
    Guard for admin-only pages.
    Returns True if admin, shows warning otherwise.
    """
    if not require_login():
        return False
    if not st.session_state.get("is_admin"):
        st.error("⛔ Access denied. This page is for administrators only.")
        st.stop()
        return False
    return True
