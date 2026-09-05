"""
Stores your PostgreSQL password in your OS's secure credential store —
macOS Keychain, Windows Credential Manager, or Linux Secret Service —
instead of leaving it in plaintext in .env.

Run this once, locally:

    python store_db_password.py

It prompts for the password with hidden input (nothing echoed to the
terminal, nothing saved to shell history). After running it:

    1. Set USE_KEYCHAIN_FOR_DB_PASSWORD=true in your .env
    2. Make sure DB_USER, DB_HOST, DB_PORT, DB_NAME in .env match your setup
       (they default to the values from the original setup instructions)
    3. You can delete the password out of DATABASE_URL in .env, or remove
       that line entirely — it's ignored once the keychain flag is on

--------------------------------------------------------------------------
LOCAL DEVELOPMENT ONLY. Don't set USE_KEYCHAIN_FOR_DB_PASSWORD=true on
Render (or most cloud hosts) — those run headless Linux containers without
a real OS keychain, and Render already encrypts your environment variables
at rest on their end, so there's nothing extra to gain there. Keep using a
plain DATABASE_URL env var in Render's dashboard for production; this
script is specifically for keeping your password off your own laptop's disk.
--------------------------------------------------------------------------
"""
import getpass

import keyring

from config import settings


def main():
    print(f"Storing a password for user '{settings.DB_USER}' "
          f"under service '{settings.KEYCHAIN_SERVICE_NAME}' in your OS keychain.\n")
    password = getpass.getpass("Enter the PostgreSQL password: ")
    confirm = getpass.getpass("Enter it again to confirm: ")

    if not password:
        print("No password entered — nothing was saved.")
        return
    if password != confirm:
        print("Those didn't match — nothing was saved. Run this again.")
        return

    keyring.set_password(settings.KEYCHAIN_SERVICE_NAME, settings.DB_USER, password)
    print(f"\nSaved. Now set USE_KEYCHAIN_FOR_DB_PASSWORD=true in your .env and restart uvicorn.")


if __name__ == "__main__":
    main()
