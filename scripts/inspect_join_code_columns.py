#!/usr/bin/env python3
"""
Database schema inspection tool to identify tables missing join_code column.

This script connects to the database and inspects all tables, showing:
1. Tables that have join_code column
2. Tables that should have join_code but don't
3. Tables that don't need join_code (system tables)
4. All columns for each table
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import inspect


# Tables that SHOULD have join_code for multi-tenancy isolation
STUDENT_DATA_TABLES = {
    'transaction',
    'tap_events',
    'student_blocks',
    'teacher_blocks',
    'student_items',
    'student_insurance',
    'hall_pass_logs',
    'rent_payments',
    'student_fines',
    'payroll_settings',
    'rent_settings',
    'banking_settings',
    'insurance_policies',
    'store_items',
    'insurance_policy_blocks',
    'store_item_blocks',
}

# Tables that DON'T need join_code (system/account management)
SYSTEM_TABLES = {
    'admin',
    'student',
    'system_admin',
    'student_teacher',
    'alembic_version',
    'recovery_request',
    'student_recovery_codes',
}


def inspect_database_schema():
    """Inspect database schema and report on join_code column status."""
    app = create_app()

    with app.app_context():
        inspector = inspect(db.engine)
        all_tables = inspector.get_table_names()

        print("=" * 80)
        print("DATABASE SCHEMA INSPECTION: join_code COLUMN AUDIT")
        print("=" * 80)
        print()

        tables_with_join_code = []
        tables_missing_join_code = []
        system_tables_found = []
        unknown_tables = []

        for table_name in sorted(all_tables):
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            has_join_code = 'join_code' in columns

            if table_name in STUDENT_DATA_TABLES:
                if has_join_code:
                    tables_with_join_code.append((table_name, columns))
                else:
                    tables_missing_join_code.append((table_name, columns))
            elif table_name in SYSTEM_TABLES:
                system_tables_found.append((table_name, columns))
            else:
                # Unknown table - might need review
                unknown_tables.append((table_name, columns, has_join_code))

        # Print summary
        print("SUMMARY")
        print("-" * 80)
        print(f"✅ Student data tables WITH join_code: {len(tables_with_join_code)}")
        print(f"❌ Student data tables MISSING join_code: {len(tables_missing_join_code)}")
        print(f"⚪ System tables (no join_code needed): {len(system_tables_found)}")
        print(f"❓ Unknown tables (needs review): {len(unknown_tables)}")
        print()

        # Print tables WITH join_code
        if tables_with_join_code:
            print("=" * 80)
            print("✅ STUDENT DATA TABLES WITH join_code")
            print("=" * 80)
            print()
            for table_name, columns in tables_with_join_code:
                print(f"📊 {table_name}")
                print(f"   Columns: {', '.join(columns)}")
                print()

        # Print tables MISSING join_code (CRITICAL)
        if tables_missing_join_code:
            print("=" * 80)
            print("❌ STUDENT DATA TABLES MISSING join_code (NEEDS FIX)")
            print("=" * 80)
            print()
            for table_name, columns in tables_missing_join_code:
                print(f"⚠️  {table_name}")
                print(f"   Columns: {', '.join(columns)}")
                print()

        # Print system tables
        if system_tables_found:
            print("=" * 80)
            print("⚪ SYSTEM TABLES (join_code not required)")
            print("=" * 80)
            print()
            for table_name, columns in system_tables_found:
                print(f"🔧 {table_name}")
                print(f"   Columns: {', '.join(columns)}")
                print()

        # Print unknown tables (needs review)
        if unknown_tables:
            print("=" * 80)
            print("❓ UNKNOWN TABLES (Manual Review Needed)")
            print("=" * 80)
            print()
            for table_name, columns, has_join_code in unknown_tables:
                status = "✅ HAS" if has_join_code else "❌ MISSING"
                print(f"❓ {table_name} [{status} join_code]")
                print(f"   Columns: {', '.join(columns)}")
                print(f"   👉 Review: Does this table store student/class-specific data?")
                print()

        # Print detailed breakdown
        print("=" * 80)
        print("COMPLETE TABLE LIST WITH ALL COLUMNS")
        print("=" * 80)
        print()

        for table_name in sorted(all_tables):
            columns = inspector.get_columns(table_name)
            has_join_code = any(col['name'] == 'join_code' for col in columns)

            # Determine table category
            if table_name in STUDENT_DATA_TABLES:
                category = "STUDENT DATA"
                status = "✅" if has_join_code else "❌ MISSING join_code"
            elif table_name in SYSTEM_TABLES:
                category = "SYSTEM"
                status = "⚪ (not needed)"
            else:
                category = "UNKNOWN"
                status = "✅ HAS join_code" if has_join_code else "❌ NO join_code"

            print(f"📋 {table_name} [{category}] {status}")
            for col in columns:
                col_type = str(col['type'])
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                default = f"DEFAULT {col['default']}" if col['default'] else ""
                print(f"   - {col['name']}: {col_type} {nullable} {default}".strip())
            print()

        # Final recommendations
        print("=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        print()

        if tables_missing_join_code:
            print("🚨 CRITICAL: The following tables MUST have join_code added:")
            for table_name, _ in tables_missing_join_code:
                print(f"   - {table_name}")
            print()
            print("Run the following to create migrations:")
            print("   flask db migrate -m 'Add join_code to <table_name>'")
            print()

        if unknown_tables:
            print("⚠️  REVIEW NEEDED: The following tables need classification:")
            for table_name, _, has_join_code in unknown_tables:
                print(f"   - {table_name} (has join_code: {has_join_code})")
            print()
            print("Action: Update STUDENT_DATA_TABLES or SYSTEM_TABLES in this script.")
            print()

        if not tables_missing_join_code and not unknown_tables:
            print("✅ All student data tables have join_code column!")
            print("✅ No unknown tables found!")
            print()
            print("Your database schema is properly configured for multi-tenancy.")


if __name__ == '__main__':
    inspect_database_schema()
