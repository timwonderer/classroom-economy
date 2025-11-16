#!/usr/bin/env python3
"""
Database reset script - drops all tables and runs migrations fresh.
WARNING: This will delete ALL data in the database!
"""
import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.pool import NullPool

def confirm_reset():
    """Ask for confirmation before proceeding."""
    print("=" * 70)
    print("⚠️  WARNING: DATABASE RESET")
    print("=" * 70)
    print("This will:")
    print("  1. Drop ALL tables in the database")
    print("  2. Delete ALL data (irreversible)")
    print("  3. Run all migrations from scratch")
    print()

    response = input("Type 'RESET DATABASE' to confirm: ")
    return response == "RESET DATABASE"

def drop_all_tables(engine):
    """Drop all tables in the database."""
    print("\n🗑️  Dropping all tables...")

    # Get all table names
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if not tables:
        print("  ℹ️  No tables found")
        return

    print(f"  Found {len(tables)} tables")

    with engine.begin() as conn:
        # Drop alembic_version first if it exists
        if 'alembic_version' in tables:
            print("  Dropping alembic_version table...")
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            tables.remove('alembic_version')

        # Drop all remaining tables
        for table in tables:
            try:
                print(f"  Dropping {table}...")
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            except Exception as e:
                print(f"    ⚠️  Warning: {e}")

        # Double-check by using DROP SCHEMA CASCADE as fallback
        # This ensures everything is cleaned up
        print("  Ensuring clean slate...")
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))

    print("  ✓ All tables dropped successfully")

def run_migrations():
    """Run flask db upgrade to apply all migrations."""
    print("\n📦 Running migrations from scratch...")

    import subprocess
    result = subprocess.run(['flask', 'db', 'upgrade'], capture_output=True, text=True)

    if result.returncode == 0:
        print("  ✓ Migrations applied successfully")
        print(result.stdout)
        return True
    else:
        print("  ❌ Migration failed!")
        print(result.stderr)
        return False

def main():
    """Main function."""
    # Check for DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        sys.exit(1)

    print(f"Database: {database_url.split('@')[1] if '@' in database_url else 'localhost'}")

    # Confirm before proceeding
    if not confirm_reset():
        print("\n❌ Reset cancelled")
        sys.exit(0)

    try:
        # Create engine
        engine = create_engine(database_url, poolclass=NullPool)

        # Drop all tables
        drop_all_tables(engine)

        # Close engine
        engine.dispose()

        # Run migrations
        if run_migrations():
            print("\n" + "=" * 70)
            print("✅ Database reset complete!")
            print("=" * 70)
            print("The database is now fresh with all migrations applied.")
            sys.exit(0)
        else:
            print("\n" + "=" * 70)
            print("❌ Database reset incomplete")
            print("=" * 70)
            print("Tables were dropped but migrations failed.")
            print("Check the error messages above.")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error during reset: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
