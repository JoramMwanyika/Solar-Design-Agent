"""
create_admin.py -- One-time script to create the first admin user.
Run this once after setting up your .env and Supabase schema.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL             = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

from supabase import create_client

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

EMAIL     = "jorammwanyika@gmail.com"
PASSWORD  = "Mwanyika5081"
FULL_NAME = "Joram Mwanyika"
ROLE      = "admin"

print(f"\n  Creating admin user: {EMAIL}")
print("  " + "-" * 45)

try:
    # -- 1. Create auth user ------------------
    res = client.auth.admin.create_user({
        "email":         EMAIL,
        "password":      PASSWORD,
        "email_confirm": True,
        "user_metadata": {"full_name": FULL_NAME, "role": ROLE},
    })

    if not res.user:
        print("  ERROR: User creation returned no user object.")
        sys.exit(1)

    user_id = res.user.id
    print("  [OK]  Auth user created  (id: {})".format(user_id))

    # -- 2. Ensure profile exists & set admin role -
    # The trigger should auto-create the profile, but we upsert to be safe
    client.table("profiles").upsert({
        "id":        user_id,
        "full_name": FULL_NAME,
        "role":      ROLE,
        "is_active": True,
    }).execute()
    print("  [OK]  Profile set to role='{}'".format(ROLE))

    print()
    print("  [OK]  Admin account ready!")
    print("     Email    : {}".format(EMAIL))
    print("     Password : {}".format(PASSWORD))
    print("     Role     : {}".format(ROLE))
    print()
    print("  Run the app:  streamlit run app.py")
    print()

except Exception as e:
    err = str(e)
    if "already been registered" in err or "already registered" in err:
        # User already exists — just make sure they're admin
        print("  [i]  User already exists. Ensuring admin role...")
        try:
            # Find user by email
            users = client.auth.admin.list_users()
            user_id = next((u.id for u in users if u.email == EMAIL), None)
            if user_id:
                client.table("profiles").upsert({
                    "id":        user_id,
                    "full_name": FULL_NAME,
                    "role":      ROLE,
                    "is_active": True,
                }).execute()
                print("  [OK]  Existing user promoted to admin.")
                print("     Email: {}".format(EMAIL))
            else:
                print("  ERROR: Could not find existing user in auth.users")
                sys.exit(1)
        except Exception as e2:
            print(f"  ERROR promoting existing user: {e2}")
            sys.exit(1)
    else:
        print(f"  ERROR: {err}")
        sys.exit(1)
