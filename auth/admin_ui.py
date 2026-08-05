"""
Admin Dashboard UI Component for Solar Design Agent.
Provides Active Account Monitoring, User Credentials Provisioning, and Account Management.
"""
import streamlit as st
from auth.admin import (
    list_all_users,
    create_user,
    set_user_active,
    reset_user_password,
    generate_temp_password
)


def make_arrow_compatible(df):
    """Converts all columns to string to prevent PyArrow serialization errors."""
    if df is None or df.empty:
        return df
    df_clean = df.copy()
    for col in df_clean.columns:
        df_clean[col] = df_clean[col].astype(str)
    return df_clean


def render_admin_dashboard():
    """Renders the complete Admin Dashboard & User Account Monitor."""
    st.markdown("## 👑 Admin Dashboard — User Account Management & System Monitoring")
    st.markdown("Monitor registered user accounts, manage permissions, deactivate accounts, and issue new credentials.")

    try:
        users = list_all_users()
    except Exception as e:
        st.error(f"⚠️ Error loading accounts list: {e}")
        users = []

    # ── Real-Time Account Monitoring Metrics ──
    total_users = len(users)
    active_users = sum(1 for u in users if u.get("is_active", True))
    deactivated_users = total_users - active_users
    admin_users = sum(1 for u in users if u.get("role") == "admin")

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("👥 Total Accounts", total_users)
    with col_m2:
        st.metric("✅ Active Accounts", active_users)
    with col_m3:
        st.metric("🔴 Deactivated Accounts", deactivated_users)
    with col_m4:
        st.metric("👑 Admin Accounts", admin_users)

    st.markdown("---")

    tab_monitor, tab_create = st.tabs([
        "📊 Active Accounts Monitor & Actions",
        "➕ Create New User Credentials"
    ])

    # ── Tab 1: Active Accounts Monitor & Actions ──
    with tab_monitor:
        st.markdown("### 🔍 Active User Accounts Directory")
        if not users:
            st.info("No registered user accounts found.")
        else:
            # Display Summary Table
            table_data = []
            for u in users:
                status_str = "✅ Active" if u.get("is_active", True) else "🔴 Deactivated"
                role_str = "👑 Admin" if u.get("role") == "admin" else "👤 User"
                table_data.append({
                    "User ID": str(u.get("id", ""))[:8] + "...",
                    "Full Name": u.get("full_name", "N/A"),
                    "Email": u.get("email", "N/A"),
                    "Role": role_str,
                    "Status": status_str,
                    "Created At": str(u.get("created_at", ""))[:10]
                })

            import pandas as pd
            df_users = pd.DataFrame(table_data)
            st.dataframe(make_arrow_compatible(df_users), use_container_width=True)

            st.markdown("#### 🛠️ Account Actions & Management")
            for u in users:
                u_id = u.get("id")
                u_name = u.get("full_name", u.get("email", "User"))
                is_active = u.get("is_active", True)
                status_badge = "🟢 Active" if is_active else "🔴 Deactivated"

                with st.expander(f"👤 {u_name} ({u.get('email', 'no-email')}) — {status_badge}"):
                    c1, c2 = st.columns([1, 1])

                    with c1:
                        st.markdown(f"**Role:** `{u.get('role', 'user')}`")
                        st.markdown(f"**Account Status:** `{status_badge}`")
                        st.markdown(f"**User ID:** `{u_id}`")

                        new_status = not is_active
                        btn_label = "🔴 Deactivate Account" if is_active else "🟢 Activate Account"
                        if st.button(btn_label, key=f"status_btn_{u_id}", use_container_width=True):
                            try:
                                set_user_active(u_id, new_status)
                                action_text = "deactivated" if not new_status else "activated"
                                st.success(f"Account for '{u_name}' has been {action_text}!")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Failed to update status: {ex}")

                    with c2:
                        st.markdown("**🔑 Reset Account Password**")
                        temp_pass = generate_temp_password(12)
                        new_pwd_input = st.text_input("New Password", value=temp_pass, key=f"pwd_in_{u_id}")
                        if st.button("🔄 Update Password", key=f"pwd_btn_{u_id}", use_container_width=True):
                            try:
                                reset_user_password(u_id, new_pwd_input)
                                st.success(f"Password for '{u_name}' reset to: `{new_pwd_input}`")
                            except Exception as ex:
                                st.error(f"Password reset failed: {ex}")

    # ── Tab 2: Create New User Credentials ──
    with tab_create:
        st.markdown("### ➕ Provision New User Credentials")
        st.markdown("Create a new user account with email and password credentials.")

        with st.form("create_user_form", clear_on_submit=False):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                new_name = st.text_input("Full Name", placeholder="e.g. Jane Doe")
                new_email = st.text_input("Email Address", placeholder="jane@company.com")
            with col_f2:
                default_temp = generate_temp_password(12)
                new_password = st.text_input("Initial Password", value=default_temp, help="You can edit or auto-generate")
                new_role = st.selectbox("Assign Role", ["user", "admin"], index=0)

            submitted_create = st.form_submit_button("🚀 Create User Credentials", use_container_width=True)

            if submitted_create:
                if not new_name or not new_email or not new_password:
                    st.error("Please fill in all fields (Full Name, Email, Password).")
                else:
                    try:
                        created = create_user(new_name, new_email, new_password, new_role)
                        st.success(f"✅ User credentials created successfully for **{new_name}**!")
                        st.info(f"**Email:** `{new_email}`\n\n**Password:** `{new_password}`\n\n**Role:** `{new_role.upper()}`")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"⚠️ Failed to create user: {ex}")
