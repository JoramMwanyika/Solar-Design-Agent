"""
Login / Logout UI helpers rendered within Streamlit pages.
"""
import streamlit as st
from auth.supabase_client import get_client
from db.queries import get_profile


def render_login_page():
    """Renders the full login page. Sets st.session_state on success."""
    from utils.helpers import get_logo_base64
    logo_b64 = get_logo_base64()

    st.markdown("""
    <style>
    body, .stApp { background-color: #060d08 !important; }
    .login-header { text-align: center; padding: 2rem 0 1rem; }
    .login-card { max-width:520px; margin: 0 auto; background: linear-gradient(180deg,#0a1410,#060d08); padding:22px; border-radius:12px; border:1px solid #1a3025 }
    .login-header h1 { font-size: 2.0rem; margin:0 }
    .login-header p  { color: #6b9e7e; font-size: 0.95rem; margin:6px 0 12px }
    .login-note { color:#6b9e7e; font-size:0.85rem; margin-top:8px }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="login-header">
        <img src="data:image/png;base64,{logo_b64}" alt="JMSolar.AI" style="height:100px; margin-bottom:10px;" />
        <h1><span style="color:#ffffff;">JM</span><span style="color:#22c55e;">Solar</span><span style="color:#3b82f6;">.AI</span></h1>
        <p style="letter-spacing:0.1em; font-size:0.78rem; color:#f59e0b; font-weight:600;">AI-POWERED SOLAR DESIGN ENGINEER</p>
        <p>AI-powered PV sizing, design &amp; BOQ generation</p>
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

        # ── Forgot Password link ──────────────────────────────────────────
        st.markdown(
            "<div style='text-align:right; margin-top:-6px; margin-bottom:10px;'>"
            "<a href='?page=forgot_password' style='color:#22c55e; font-size:0.85rem; text-decoration:none;'>"
            "🔑 Forgot your password?</a></div>",
            unsafe_allow_html=True,
        )
        # Streamlit workaround: show the forgot-password flow inline if selected
        if st.session_state.get("_show_forgot_pw"):
            _render_forgot_password_inline()
        else:
            if st.button("🔑 Forgot / Change Password", use_container_width=False, key="btn_forgot_pw"):
                st.session_state["_show_forgot_pw"] = True
                st.rerun()

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


def _render_forgot_password_inline():
    """
    Inline 'Forgot Password' panel shown beneath the login form.
    Sends a Supabase password-reset email to the client's address.
    """
    st.markdown("---")
    st.markdown("#### 📧 Send Password Reset Email")
    st.caption(
        "Enter your registered email address. You'll receive a secure link "
        "to set a new password — valid for 1 hour."
    )
    fp_email = st.text_input("Your email address", placeholder="you@company.com", key="fp_email_input")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📬 Send Reset Link", key="send_reset_btn", use_container_width=True, type="primary"):
            if not fp_email:
                st.error("Please enter your email address.")
            else:
                from auth.admin import send_password_reset_email
                result = send_password_reset_email(fp_email)
                if result.get("ok"):
                    st.success(
                        f"✅ A password-reset link has been sent to **{fp_email}**.\n\n"
                        "Check your inbox (and spam folder) and click the link to set a new password."
                    )
                    st.session_state.pop("_show_forgot_pw", None)
                else:
                    st.error(f"Could not send email: {result.get('error')}")
    with c2:
        if st.button("✖ Cancel", key="cancel_forgot_btn", use_container_width=True):
            st.session_state.pop("_show_forgot_pw", None)
            st.rerun()


def render_set_password_page(access_token: str):
    """
    Shown when the user arrives via a Supabase password-reset link.
    The URL contains `access_token` and `type=recovery` as fragments
    (Streamlit exposes them via st.query_params after the JS redirect).
    """
    from utils.helpers import get_logo_base64
    logo_b64 = get_logo_base64()

    st.markdown("""
    <style>
    body, .stApp { background-color: #060d08 !important; }
    .login-header { text-align: center; padding: 2rem 0 1rem; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="login-header">
        <img src="data:image/png;base64,{logo_b64}" alt="JMSolar.AI" style="height:80px; margin-bottom:10px;" />
        <h2 style="color:#22c55e;">Set Your New Password</h2>
        <p style="color:#6b9e7e;">Choose a strong password for your JMSolar.AI account.</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        with st.form("set_password_form", clear_on_submit=False):
            st.markdown("### 🔒 Create New Password")
            new_pw  = st.text_input("New Password",     type="password", placeholder="Min. 8 characters")
            conf_pw = st.text_input("Confirm Password", type="password", placeholder="Repeat your password")
            submitted = st.form_submit_button("✅ Save New Password", use_container_width=True)

        if submitted:
            if not new_pw or not conf_pw:
                st.error("Please fill in both password fields.")
            elif new_pw != conf_pw:
                st.error("Passwords do not match. Please try again.")
            elif len(new_pw) < 8:
                st.error("Password must be at least 8 characters long.")
            else:
                from auth.admin import update_user_password
                result = update_user_password(new_pw, access_token)
                if result.get("ok"):
                    st.success(
                        "✅ **Password updated successfully!** "
                        "You can now log in with your new password."
                    )
                    # Clear the recovery state
                    for k in ["_recovery_token", "_recovery_type"]:
                        st.session_state.pop(k, None)
                    st.balloons()
                    if st.button("Go to Login →", use_container_width=True):
                        st.rerun()
                else:
                    st.error(
                        f"Failed to update password: {result.get('error')}\n\n"
                        "The reset link may have expired. Please request a new one."
                    )


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

    # Change password shortcut for logged-in users
    if st.sidebar.button("🔑 Change Password", use_container_width=True, key="sb_change_pw"):
        st.session_state["_show_change_pw_sidebar"] = True
        st.rerun()

    if st.session_state.get("_show_change_pw_sidebar"):
        _render_sidebar_change_password()

    if st.sidebar.button("🚪 Logout", use_container_width=True):
        _logout()


def _render_sidebar_change_password():
    """
    Renders an inline password change form in the sidebar.
    Logged in users can update their password directly.
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🔑 Change Password**")
    
    with st.sidebar.form("sb_change_pw_form", clear_on_submit=True):
        new_pw = st.text_input("New Password", type="password", placeholder="Min. 8 characters")
        conf_pw = st.text_input("Confirm Password", type="password")
        
        c1, c2 = st.columns(2)
        with c1:
            submitted = st.form_submit_button("✅ Save", use_container_width=True)
        with c2:
            cancel = st.form_submit_button("✖ Cancel", use_container_width=True)
            
        if cancel:
            st.session_state.pop("_show_change_pw_sidebar", None)
            st.rerun()
            
        if submitted:
            if not new_pw or not conf_pw:
                st.error("Please fill in both fields.")
            elif new_pw != conf_pw:
                st.error("Passwords do not match.")
            elif len(new_pw) < 8:
                st.error("Minimum 8 characters.")
            else:
                try:
                    from auth.supabase_client import get_client
                    client = get_client()
                    # Ensure the client is authenticated with the current session
                    access_token = st.session_state.get("access_token")
                    if access_token:
                        client.auth.set_session(access_token, "")
                        client.auth.update_user({"password": new_pw})
                        st.success("✅ Password updated!")
                        st.session_state.pop("_show_change_pw_sidebar", None)
                    else:
                        st.error("Session expired. Please log in again.")
                except Exception as e:
                    st.error(f"Failed to update: {e}")
    st.sidebar.markdown("---")


def _logout():
    """Clears session and signs out from Supabase."""
    try:
        get_client().auth.sign_out()
    except Exception:
        pass
    for key in ["user", "profile", "access_token", "is_admin",
                "messages", "current_project_id", "current_session_id",
                "_show_forgot_pw", "_show_change_pw_sidebar",
                "_recovery_token", "_recovery_type"]:
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
