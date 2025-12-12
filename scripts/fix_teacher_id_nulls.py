#!/usr/bin/env python3
"""
Fix NULL teacher_id values before running migration.
This script populates teacher_id for all settings tables.
"""

import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text

def fix_teacher_id_nulls():
    """Populate NULL teacher_id values with the first admin's ID."""

    app = create_app()

    with app.app_context():
        # Get the first admin ID
        result = db.session.execute(text("SELECT id FROM admins ORDER BY id LIMIT 1"))
        first_admin = result.fetchone()

        if not first_admin:
            print("❌ ERROR: No admins found in database!")
            print("   Please create an admin account first.")
            return 1

        admin_id = first_admin[0]
        print(f"📝 Using admin ID: {admin_id}")

        # Tables to update
        tables = [
            'rent_settings',
            'banking_settings',
            'payroll_settings',
            'payroll_rewards',
            'payroll_fines',
            'store_items',
            'hall_pass_settings'
        ]

        total_updated = 0

        for table in tables:
            # Check if table exists and has teacher_id column
            check_query = text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = :table
                    AND column_name = 'teacher_id'
                )
            """)
            exists = db.session.execute(check_query, {"table": table}).scalar()

            if not exists:
                print(f"⏭️  Skipping {table} (teacher_id column doesn't exist yet)")
                continue

            # Count NULL values
            count_query = text(f"SELECT COUNT(*) FROM {table} WHERE teacher_id IS NULL")
            null_count = db.session.execute(count_query).scalar()

            if null_count == 0:
                print(f"✅ {table}: No NULL teacher_id values")
                continue

            # Update NULL values
            update_query = text(f"UPDATE {table} SET teacher_id = :admin_id WHERE teacher_id IS NULL")
            result = db.session.execute(update_query, {"admin_id": admin_id})

            print(f"✅ {table}: Updated {null_count} rows")
            total_updated += null_count

        # Commit all changes
        db.session.commit()

        print(f"\n✅ SUCCESS: Updated {total_updated} total rows")
        print(f"   All NULL teacher_id values set to admin {admin_id}")
        print(f"\n🚀 You can now run: flask db upgrade")

        return 0

if __name__ == '__main__':
    try:
        exit_code = fix_teacher_id_nulls()
        sys.exit(exit_code)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
