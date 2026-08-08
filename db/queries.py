"""
Database query helpers for Solar Design Agent.
"""
from auth.supabase_client import get_client
import streamlit as st


import uuid


def is_valid_uuid(val) -> bool:
    """Checks if a string is a valid UUID before sending to PostgreSQL."""
    if not val or not isinstance(val, str):
        return False
    try:
        uuid.UUID(val)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _client():
    """Returns an authenticated client with user's access token."""
    c = get_client()
    token = st.session_state.get("access_token")
    if token:
        try:
            c.auth.set_session(token, "")
        except Exception:
            pass
    return c


def _exec(query):
    """Executes a Supabase query with graceful JWT expiration, invalid UUID, & network error handling."""
    try:
        return query.execute()
    except Exception as e:
        err_str = str(e)
        if "JWT expired" in err_str or "PGRST303" in err_str:
            st.session_state["user"] = None
            st.session_state["access_token"] = None
            st.warning("🔒 Your session has expired. Please log in again.")
            st.rerun()
        elif "22P02" in err_str or "invalid input syntax for type uuid" in err_str or "11001" in err_str or "getaddrinfo failed" in err_str or "ConnectError" in err_str:
            class DummyRes:
                data = []
            return DummyRes()
        raise e


# ─────────────────────────────────────────────
# Profiles
# ─────────────────────────────────────────────

def get_profile(user_id: str) -> dict | None:
    if not is_valid_uuid(user_id):
        return {"id": "offline-guest-id", "full_name": "Solar Design Guest", "role": "user", "is_active": True}
    try:
        from auth.supabase_client import get_admin_client
        res = get_admin_client().table("profiles").select("*").eq("id", user_id).single().execute()
        return res.data
    except Exception:
        return {"id": user_id, "full_name": "Solar User", "role": "user", "is_active": True}


def update_profile(user_id: str, data: dict) -> None:
    if is_valid_uuid(user_id):
        _exec(_client().table("profiles").update(data).eq("id", user_id))


# ─────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────

def get_user_projects(user_id: str) -> list[dict]:
    if not is_valid_uuid(user_id):
        return [{"id": "offline-proj-1", "name": "Offline Local Project", "system_type": "hybrid", "location": "Nairobi, Kenya"}]
    res = _exec(_client().table("projects").select("*").eq("user_id", user_id)\
        .order("created_at", desc=True))
    return res.data if (res and res.data) else [{"id": "offline-proj-1", "name": "Offline Local Project", "system_type": "hybrid", "location": "Nairobi, Kenya"}]


def create_project(user_id: str, name: str, system_type: str,
                   location: str = "", description: str = "") -> dict:
    if not is_valid_uuid(user_id):
        return {"id": "offline-proj-1", "name": name, "system_type": system_type, "location": location}
    data = {
        "user_id": user_id,
        "name": name,
        "system_type": system_type,
        "location": location,
        "description": description,
    }
    res = _exec(_client().table("projects").insert(data))
    return res.data[0] if (res and res.data) else {}


def delete_project(project_id: str) -> None:
    if is_valid_uuid(project_id):
        _exec(_client().table("projects").delete().eq("id", project_id))


def update_project_status(project_id: str, status: str) -> None:
    if is_valid_uuid(project_id):
        _exec(_client().table("projects").update({"status": status}).eq("id", project_id))


# ─────────────────────────────────────────────
# Chat Sessions
# ─────────────────────────────────────────────

def create_chat_session(user_id: str, project_id: str, title: str = "New Chat") -> dict:
    if not is_valid_uuid(user_id) or not is_valid_uuid(project_id):
        return {"id": "offline-session-1", "title": title, "messages": []}
    data = {"user_id": user_id, "project_id": project_id, "title": title, "messages": []}
    res = _exec(_client().table("chat_sessions").insert(data))
    return res.data[0] if (res and res.data) else {}


def get_chat_sessions(project_id: str) -> list[dict]:
    if not is_valid_uuid(project_id):
        return []
    res = _exec(_client().table("chat_sessions").select("*").eq("project_id", project_id)\
        .order("created_at", desc=True))
    return res.data if (res and res.data) else []


def update_chat_messages(session_id: str, messages: list) -> None:
    if not is_valid_uuid(session_id):
        return
    _exec(_client().table("chat_sessions").update({"messages": messages})\
        .eq("id", session_id))


def delete_chat_session(session_id: str) -> None:
    if is_valid_uuid(session_id):
        _exec(_client().table("chat_sessions").delete().eq("id", session_id))


def update_chat_session_title(session_id: str, title: str) -> None:
    if is_valid_uuid(session_id):
        _exec(_client().table("chat_sessions").update({"title": title})\
            .eq("id", session_id))



# ─────────────────────────────────────────────
# System Designs / BOQs
# ─────────────────────────────────────────────

def save_design(user_id: str, project_id: str, session_id: str,
                system_type: str, inputs: dict,
                sizing_results: dict, boq_data: list) -> dict:
    if not is_valid_uuid(user_id) or not is_valid_uuid(project_id):
        return {}
    data = {
        "user_id": user_id,
        "project_id": project_id,
        "chat_session_id": session_id if is_valid_uuid(session_id) else None,
        "system_type": system_type,
        "inputs": inputs,
        "sizing_results": sizing_results,
        "boq_data": boq_data,
    }
    res = _exec(_client().table("system_designs").insert(data))
    return res.data[0] if res.data else {}


def get_designs_for_project(project_id: str) -> list[dict]:
    res = _exec(_client().table("system_designs").select("*").eq("project_id", project_id)\
        .order("created_at", desc=True))
    return res.data or []
