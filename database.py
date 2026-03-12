import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def _get_secret(key):
    """Try st.secrets first (Streamlit Cloud), fallback to os.environ (local)."""
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.getenv(key, '')

SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_KEY = _get_secret("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY. Set in .env (local) or Streamlit Cloud secrets.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ─── AUCTIONS ───────────────────────────────────────────
def get_auctions(unread_only=True):
    query = supabase.table("auctions").select("*")
    if unread_only:
        query = query.eq("is_read", False)
    return query.order("found_at", desc=True).execute().data

def mark_auction_as_read(auction_id: str):
    return supabase.table("auctions").update({"is_read": True}).eq("id", auction_id).execute().data

def insert_auction(auction_data: dict):
    try:
        existing = supabase.table("auctions").select("id").eq("id", auction_data["id"]).execute()
        if not existing.data:
            supabase.table("auctions").insert(auction_data).execute()
            print(f"  + Inserted: {auction_data.get('title', '')[:60]}")
            return True
        return False
    except Exception as e:
        print(f"  ! Error inserting: {e}")
        return False

# ─── SEARCH SETTINGS ────────────────────────────────────
def get_search_settings():
    return supabase.table("search_settings").select("*").execute().data

def insert_search_setting(template: str, time_filters: list, exclude_groups: list = None):
    data = {"template": template, "time_filters": time_filters, "exclude_groups": exclude_groups or []}
    return supabase.table("search_settings").insert(data).execute().data

def update_search_setting(setting_id: str, template: str, time_filters: list, exclude_groups: list = None):
    data = {"template": template, "time_filters": time_filters, "exclude_groups": exclude_groups or []}
    return supabase.table("search_settings").update(data).eq("id", setting_id).execute().data

def delete_search_setting(setting_id: str):
    return supabase.table("search_settings").delete().eq("id", setting_id).execute().data

# ─── GLOBAL EXCLUDES ────────────────────────────────────
def get_global_excludes():
    return supabase.table("global_excludes").select("*").execute().data

def insert_global_exclude(exclude_text: str, group_name: str = "ค่าเริ่มต้น"):
    return supabase.table("global_excludes").insert({"exclude_text": exclude_text, "group_name": group_name}).execute().data

def update_global_exclude(exclude_id: str, exclude_text: str, group_name: str):
    return supabase.table("global_excludes").update({"exclude_text": exclude_text, "group_name": group_name}).eq("id", exclude_id).execute().data

def delete_global_exclude(exclude_id: str):
    return supabase.table("global_excludes").delete().eq("id", exclude_id).execute().data

# ─── PROVINCE GROUPS ────────────────────────────────────
def get_province_groups():
    return supabase.table("province_groups").select("*").execute().data

def insert_province_group(group_name: str, provinces: str):
    return supabase.table("province_groups").insert({"group_name": group_name, "provinces": provinces}).execute().data

def update_province_group(group_id: str, group_name: str, provinces: str):
    return supabase.table("province_groups").update({"group_name": group_name, "provinces": provinces}).eq("id", group_id).execute().data

def delete_province_group(group_id: str):
    return supabase.table("province_groups").delete().eq("id", group_id).execute().data
