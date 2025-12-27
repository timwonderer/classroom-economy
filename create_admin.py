#!/usr/bin/env python3
"""
Create admin accounts (SystemAdmin or Admin) with TOTP authentication.
"""
import os
import sys
import pyotp
import qrcode
from io import BytesIO

# Set up Flask app context
from app import app
from app.extensions import db
from app.models import SystemAdmin, Admin
from app.utils.encryption import encrypt_totp

def create_system_admin(username):
    """Create a system admin account."""
    with app.app_context():
        # Check if username already exists
        existing = SystemAdmin.query.filter_by(username=username).first()
        if existing:
            print(f"❌ SystemAdmin '{username}' already exists!")
            return False

        # Generate TOTP secret
        totp_secret = pyotp.random_base32()

        # Create the admin
        admin = SystemAdmin(
            username=username,
            totp_secret=encrypt_totp(totp_secret)  # Encrypt before storing
        )
        db.session.add(admin)
        db.session.commit()

        print("=" * 70)
        print(f"✅ SystemAdmin '{username}' created successfully!")
        print("=" * 70)
        print()
        print("TOTP Setup Instructions:")
        print("1. Open your authenticator app (Google Authenticator, Authy, etc.)")
        print("2. Scan the QR code or manually enter the secret key")
        print()
        print("   IMPORTANT: The TOTP secret is sensitive information.")
        print("   For security reasons, retrieve it from secure storage or the database.")
        print("   The secret is encrypted in the database and should only be")
        print("   accessed through secure administrative channels.")
        print()
        print(f"   Account: {username}")
        print("   Issuer: Classroom Economy - System")
        print()
        print("3. Store the TOTP secret securely (e.g., password manager).")
        print()
        print("=" * 70)

        return True

def create_regular_admin(username):
    """Create a regular admin account."""
    with app.app_context():
        # Check if username already exists
        existing = Admin.query.filter_by(username=username).first()
        if existing:
            print(f"❌ Admin '{username}' already exists!")
            return False

        # Generate TOTP secret
        totp_secret = pyotp.random_base32()

        # Create the admin
        admin = Admin(
            username=username,
            totp_secret=encrypt_totp(totp_secret)  # Encrypt before storing
        )
        db.session.add(admin)
        db.session.commit()

        print("=" * 70)
        print(f"✅ Admin '{username}' created successfully!")
        print("=" * 70)
        print()
        print("TOTP Setup Instructions:")
        print("1. Open your authenticator app (Google Authenticator, Authy, etc.)")
        print("2. Scan the QR code or manually enter the secret key")
        print()
        print("   IMPORTANT: The TOTP secret is sensitive information.")
        print("   For security reasons, retrieve it from secure storage or the database.")
        print("   The secret is encrypted in the database and should only be")
        print("   accessed through secure administrative channels.")
        print()
        print(f"   Account: {username}")
        print("   Issuer: Classroom Economy")
        print()
        print("3. Store the TOTP secret securely (e.g., password manager).")
        print()
        print("=" * 70)

        return True

def list_admins():
    """List all admin accounts."""
    with app.app_context():
        print("=" * 70)
        print("SYSTEM ADMINS")
        print("=" * 70)
        sys_admins = SystemAdmin.query.all()
        if sys_admins:
            for admin in sys_admins:
                print(f"  - {admin.username} (ID: {admin.id})")
        else:
            print("  (none)")

        print()
        print("=" * 70)
        print("REGULAR ADMINS")
        print("=" * 70)
        admins = Admin.query.all()
        if admins:
            for admin in admins:
                print(f"  - {admin.username} (ID: {admin.id})")
        else:
            print("  (none)")
        print()

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python create_admin.py sysadmin <username>   - Create a system admin")
        print("  python create_admin.py admin <username>      - Create a regular admin")
        print("  python create_admin.py list                  - List all admins")
        print()
        print("Examples:")
        print("  python create_admin.py sysadmin superadmin")
        print("  python create_admin.py admin teacher1")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'list':
        list_admins()
    elif command in ['sysadmin', 'systemadmin', 'sys']:
        if len(sys.argv) < 3:
            print("❌ Please provide a username")
            print("Usage: python create_admin.py sysadmin <username>")
            sys.exit(1)
        username = sys.argv[2]
        create_system_admin(username)
    elif command == 'admin':
        if len(sys.argv) < 3:
            print("❌ Please provide a username")
            print("Usage: python create_admin.py admin <username>")
            sys.exit(1)
        username = sys.argv[2]
        create_regular_admin(username)
    else:
        print(f"❌ Unknown command: {command}")
        print("Valid commands: sysadmin, admin, list")
        sys.exit(1)

if __name__ == '__main__':
    # Check DATABASE_URL is set
    if not os.getenv('DATABASE_URL'):
        print("❌ DATABASE_URL environment variable not set!")
        print("Please set it before running this script.")
        sys.exit(1)

    main()
