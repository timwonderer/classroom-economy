#!/usr/bin/env python3
"""
Database reset script - drops tables individually (for limited permissions).
WARNING: This will delete ALL data in the database!
"""
import os
import sys
from sqlalchemy import create_engine, text, inspect, MetaData
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
    """Drop all tables in the database individually."""
    print("\n🗑️  Dropping all tables...")

    with engine.begin() as conn:
        # Get all table names
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if not tables:
            print("  ℹ️  No tables found")
            return

        print(f"  Found {len(tables)} tables")

        # Drop alembic_version first
        if 'alembic_version' in tables:
            print("  Dropping alembic_version...")
            conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))

        # Get all tables again and build dependency order
        metadata = MetaData()
        metadata.reflect(bind=engine)

        # Drop in reverse dependency order
        print("  Dropping all tables in reverse dependency order...")
        for table in reversed(metadata.sorted_tables):
            try:
                print(f"    Dropping {table.name}...")
                conn.execute(text(f"DROP TABLE IF EXISTS {table.name} CASCADE"))
            except Exception as e:
                print(f"    ⚠️  Warning: {e}")

        # Verify all tables are gone
        final_tables = inspect(engine).get_table_names()
        if final_tables:
            print(f"  ⚠️  Warning: {len(final_tables)} tables remain")
            for table in final_tables:
                print(f"    - {table}")
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                except Exception as e:
                    print(f"      Failed: {e}")
        else:
            print("  ✓ All tables dropped successfully")

def run_migrations():
    """Run flask db upgrade to apply all migrations."""
    print("\n📦 Running migrations from scratch...")

    import subprocess
    result = subprocess.run(['flask', 'db', 'upgrade'], capture_output=True, text=True)

    if result.returncode == 0:
        print("  ✓ Migrations applied successfully")
        if result.stdout:
            print(result.stdout)
        return True
    else:
        print("  ❌ Migration failed!")
        if result.stderr:
            print(result.stderr)
        if result.stdout:
            print(result.stdout)
        return False

def main():
    """Main function."""
    # Check for DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        sys.exit(1)

    # Mask the password in the display
    display_url = database_url
    if '@' in database_url:
        display_url = database_url.split('@')[1]

    print(f"Database: {display_url}")

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
