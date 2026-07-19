"""utils/helpers.py — Utility functions."""
from datetime import datetime


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
