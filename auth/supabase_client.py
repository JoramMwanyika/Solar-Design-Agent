"""
Supabase client singleton — shared across the entire app.
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None
_admin_client: Client | None = None


def get_client() -> Client:
    """Returns the standard Supabase client (uses anon key + RLS)."""
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env"
            )
        _client = create_client(url, key)
    return _client


def get_admin_client() -> Client:
    """
    Returns a Supabase client with the service role key.
    Bypasses RLS — use only for admin operations.
    """
    global _admin_client
    if _admin_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
            )
        _admin_client = create_client(url, key)
    return _admin_client
