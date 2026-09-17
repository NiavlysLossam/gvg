#!/usr/bin/env python3
"""
CLI script to create or update the initial Super-Admin user in GVG.
Also attaches any pre-existing unassigned events to this Super-Admin for backwards compatibility.

Usage:
    python scripts/create_superadmin.py --email admin@example.com --password "Secret123"
Or run interactively:
    python scripts/create_superadmin.py
Or using environment variables:
    SUPERADMIN_EMAIL=admin@example.com SUPERADMIN_PASSWORD="Secret123" python scripts/create_superadmin.py
"""

import sys
import os
import argparse
import getpass
from pathlib import Path

# Add backend to PYTHONPATH so app modules can be imported
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.event import Event


def create_or_update_superadmin(email: str, password: str) -> None:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError(f"Invalid email address: '{email}'")

    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters long")

    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password cannot exceed 72 bytes")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        hashed = hash_password(password)

        if user:
            print(f"[INFO] User with email '{email}' already exists. Promoting to super_admin and updating password...")
            user.role = UserRole.SUPER_ADMIN
            user.hashed_password = hashed
            user.is_active = True
        else:
            print(f"[INFO] Creating new super_admin account for '{email}'...")
            user = User(
                email=email,
                hashed_password=hashed,
                role=UserRole.SUPER_ADMIN,
                is_active=True,
            )
            db.add(user)

        db.flush()

        # Retroactive claim: assign pre-existing unassigned events to this super-admin
        unassigned_events = db.query(Event).filter(Event.owner_id.is_(None)).all()
        if unassigned_events:
            print(f"[INFO] Found {len(unassigned_events)} unassigned event(s). Assigning to super_admin '{email}'...")
            for ev in unassigned_events:
                ev.owner_id = user.id
            print(f"[SUCCESS] {len(unassigned_events)} event(s) successfully claimed.")
        else:
            print("[INFO] No unassigned events found.")

        db.commit()
        print(f"[SUCCESS] Super-Admin '{email}' is active and ready.")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to configure superadmin: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create or update the GVG Super-Admin user.")
    parser.add_argument("--email", "-e", help="Super-Admin email address")
    parser.add_argument("--password", "-p", help="Super-Admin password")

    args = parser.parse_args()

    email = args.email or os.environ.get("SUPERADMIN_EMAIL")
    password = args.password or os.environ.get("SUPERADMIN_PASSWORD")

    if not email:
        email = input("Enter Super-Admin email: ").strip()

    if not password:
        password = getpass.getpass("Enter Super-Admin password (min 6 chars): ")
        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("[ERROR] Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    try:
        create_or_update_superadmin(email, password)
    except ValueError as err:
        print(f"[ERROR] {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

