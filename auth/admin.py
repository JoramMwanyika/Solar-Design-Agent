"""
Admin-only functions: create users, list users, deactivate, reset password.
All operations use the service role key (bypasses RLS).
"""
import secrets
import string
from auth.supabase_client import get_admin_client


def list_all_users() -> list[dict]:
    """Returns all profiles with auth user emails merged."""
    client = get_admin_client()
    profiles = client.table("profiles").select("*").order("created_at", desc=False).execute()
    data = profiles.data or []

    # Fetch emails from auth.users via admin API
    try:
        auth_users = client.auth.admin.list_users()
        email_map = {u.id: u.email for u in auth_users}
        for p in data:
            p["email"] = email_map.get(p["id"], "—")
    except Exception:
        for p in data:
            p["email"] = "—"
    return data


def create_user(full_name: str, email: str, password: str, role: str = "user") -> dict:
    """
    Creates a new Supabase auth user and their profile.
    Returns the created profile dict or raises on error.
    """
    client = get_admin_client()
    res = client.auth.admin.create_user({
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"full_name": full_name, "role": role}
    })
    if not res.user:
        raise ValueError("Failed to create user — no user returned.")
    return {"id": res.user.id, "email": email, "full_name": full_name, "role": role}


def set_user_active(user_id: str, is_active: bool) -> None:
    """Activates or deactivates a user (sets is_active on profile)."""
    client = get_admin_client()
    client.table("profiles").update({"is_active": is_active}).eq("id", user_id).execute()


def reset_user_password(user_id: str, new_password: str) -> None:
    """Resets a user's password via the admin API."""
    client = get_admin_client()
    client.auth.admin.update_user_by_id(user_id, {"password": new_password})


def generate_temp_password(length: int = 12) -> str:
    """Generates a secure random temporary password."""
    chars = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(chars) for _ in range(length))
