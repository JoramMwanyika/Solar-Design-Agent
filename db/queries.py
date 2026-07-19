"""
Database query helpers for Solar Design Agent.
"""
from auth.supabase_client import get_client
import streamlit as st


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


# ─────────────────────────────────────────────
# Profiles
# ─────────────────────────────────────────────

def get_profile(user_id: str) -> dict | None:
    from auth.supabase_client import get_admin_client
    res = get_admin_client().table("profiles").select("*").eq("id", user_id).single().execute()
    return res.data


def update_profile(user_id: str, data: dict) -> None:
    _client().table("profiles").update(data).eq("id", user_id).execute()


# ─────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────

def get_user_projects(user_id: str) -> list[dict]:
    res = _client().table("projects").select("*").eq("user_id", user_id)\
        .order("created_at", desc=True).execute()
    return res.data or []


def create_project(user_id: str, name: str, system_type: str,
                   location: str = "", description: str = "") -> dict:
    data = {
        "user_id": user_id,
        "name": name,
        "system_type": system_type,
        "location": location,
        "description": description,
    }
    res = _client().table("projects").insert(data).execute()
    return res.data[0] if res.data else {}


def delete_project(project_id: str) -> None:
    _client().table("projects").delete().eq("id", project_id).execute()


def update_project_status(project_id: str, status: str) -> None:
    _client().table("projects").update({"status": status}).eq("id", project_id).execute()


# ─────────────────────────────────────────────
# Chat Sessions
# ─────────────────────────────────────────────

def create_chat_session(user_id: str, project_id: str, title: str = "New Chat") -> dict:
    data = {"user_id": user_id, "project_id": project_id, "title": title, "messages": []}
    res = _client().table("chat_sessions").insert(data).execute()
    return res.data[0] if res.data else {}


def get_chat_sessions(project_id: str) -> list[dict]:
    res = _client().table("chat_sessions").select("*").eq("project_id", project_id)\
        .order("created_at", desc=True).execute()
    return res.data or []


def update_chat_messages(session_id: str, messages: list) -> None:
    _client().table("chat_sessions").update({"messages": messages})\
        .eq("id", session_id).execute()


# ─────────────────────────────────────────────
# System Designs / BOQs
# ─────────────────────────────────────────────

def save_design(user_id: str, project_id: str, session_id: str,
                system_type: str, inputs: dict,
                sizing_results: dict, boq_data: list) -> dict:
    data = {
        "user_id": user_id,
        "project_id": project_id,
        "chat_session_id": session_id,
        "system_type": system_type,
        "inputs": inputs,
        "sizing_results": sizing_results,
        "boq_data": boq_data,
    }
    res = _client().table("system_designs").insert(data).execute()
    return res.data[0] if res.data else {}


def get_designs_for_project(project_id: str) -> list[dict]:
    res = _client().table("system_designs").select("*").eq("project_id", project_id)\
        .order("created_at", desc=True).execute()
    return res.data or []
