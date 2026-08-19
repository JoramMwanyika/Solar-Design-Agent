"""utils/helpers.py — Utility functions."""
from datetime import datetime
import base64
import os
import streamlit as st
from PIL import Image


@st.cache_data
def get_logo_base64() -> str:
    """Loads and caches the base64 string of the logo to avoid slow disk reads and static path routing issues in production."""
    paths_to_try = [
        os.path.join(os.path.dirname(__file__), "../static/jmsolar_logo_sm.png"),
        os.path.join(os.path.dirname(__file__), "../static/jmsolar_logo.png"),
        "static/jmsolar_logo_sm.png",
        "static/jmsolar_logo.png"
    ]
    for p in paths_to_try:
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass
    return ""


@st.cache_data
def get_logo_image():
    """Loads and caches the logo as a PIL Image for use in st.set_page_config icon."""
    paths_to_try = [
        os.path.join(os.path.dirname(__file__), "../static/jmsolar_logo_sm.png"),
        os.path.join(os.path.dirname(__file__), "../static/jmsolar_logo.png"),
        "static/jmsolar_logo_sm.png",
        "static/jmsolar_logo.png"
    ]
    for p in paths_to_try:
        if os.path.exists(p):
            try:
                return Image.open(p)
            except Exception:
                pass
    return None




def format_datetime(dt_str: str) -> str:
    """Formats a Supabase timestamp string to human-readable."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return dt_str or "—"


def system_type_badge(system_type: str) -> str:
    """Returns an emoji badge for the system type."""
    badges = {
        "off-grid": "🔋 Off-Grid",
        "hybrid": "⚡ Hybrid",
        "grid-tied": "🌐 Grid-Tied",
    }
    return badges.get(system_type, system_type or "—")


def truncate(text: str, max_len: int = 80) -> str:
    """Truncates a string with ellipsis."""
    return text if len(text) <= max_len else text[:max_len - 3] + "..."
