import sys
errors = []

tests = [
    # Third-party packages
    ('streamlit',             'import streamlit as st; v=st.__version__'),
    ('google-genai (NEW)',    'from google import genai; from google.genai import types; v=genai.__version__'),
    ('supabase',              'from supabase import create_client; v="ok"'),
    ('openpyxl',              'import openpyxl; v=openpyxl.__version__'),
    ('pdfplumber',            'import pdfplumber; v="ok"'),
    ('python-docx',           'from docx import Document; v="ok"'),
    ('pandas',                'import pandas as pd; v=pd.__version__'),
    ('python-dotenv',         'from dotenv import load_dotenv; v="ok"'),
    ('pillow',                'from PIL import Image; v="ok"'),
    # Internal modules
    ('agent.system_sizer',   'from agent.system_sizer import size_system, LoadItem, SizingResult; v="ok"'),
    ('agent.boq_generator',  'from agent.boq_generator import generate_boq_excel, boq_to_markdown_table; v="ok"'),
    ('agent.report_analyzer','from agent.report_analyzer import extract_from_text, format_extracted_data; v="ok"'),
    ('utils.file_parser',    'from utils.file_parser import parse_uploaded_file, get_mime_type; v="ok"'),
    ('utils.helpers',        'from utils.helpers import format_datetime, system_type_badge; v="ok"'),
    ('auth.supabase_client', 'from auth.supabase_client import get_client, get_admin_client; v="ok"'),
    ('auth.login',           'from auth.login import require_login, require_admin; v="ok"'),
    ('auth.admin',           'from auth.admin import list_all_users, create_user, generate_temp_password; v="ok"'),
    ('db.queries',           'from db.queries import get_profile, get_user_projects, save_design; v="ok"'),
    # Orchestrator (new SDK)
    ('agent.orchestrator',   'from agent.orchestrator import SolarAgent; v="ok"'),
]

for name, code in tests:
    try:
        ns = {}
        exec(code, ns)
        val = ns.get('v', 'ok')
        print(f"  OK  {name:<30} {val}")
    except Exception as e:
        msg = f"  FAIL  {name}: {e}"
        errors.append(msg)
        print(msg)

print()
if errors:
    print(f"FAILED: {len(errors)} error(s)")
    sys.exit(1)
else:
    print("=" * 55)
    print("  ALL IMPORTS SUCCESSFUL — Solar Design Agent ready!")
    print("=" * 55)
    print()
    print("  Run with:  streamlit run app.py")
