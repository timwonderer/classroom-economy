#!/usr/bin/env python3
"""
Direct SQL migration to add join_code column to student_blocks table.
This script is intended for SQLite databases only.

import sqlite3
import os
import sys

# Get database URL from environment or use default
database_url = os.getenv('DATABASE_URL', 'sqlite:///dev.db')

# Extract database path from SQLite URL
if database_url.startswith('sqlite:///'):
    db_path = database_url.replace('sqlite:///', '')
else:
    print(f"Error: Only SQLite databases are supported by this script")
    print(f"Database URL: {database_url}")
    sys.exit(1)

try:
    # Connect to SQLite database
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print(f"Connected to database: {db_path}")
    print("Adding join_code column to student_blocks table...")

    # Check if column already exists
    cur.execute("PRAGMA table_info(student_blocks)")
    columns = [row[1] for row in cur.fetchall()]

    if 'join_code' in columns:
        print("⚠️  join_code column already exists!")
    else:
        # Add column
        cur.execute("""
            ALTER TABLE student_blocks
            ADD COLUMN join_code VARCHAR(20);
        """)
        print("✅ join_code column added")

    print("Creating index on join_code...")

    # Create index (SQLite will ignore if exists)
    try:
        cur.execute("""
            CREATE INDEX ix_student_blocks_join_code
            ON student_blocks(join_code);
        """)
        print("✅ Index created")
    except sqlite3.OperationalError as e:
        if 'already exists' in str(e):
            print("⚠️  Index already exists")
        else:
            raise

    # Update alembic_version table to mark migration as applied
    print("Updating alembic_version...")
    try:
        cur.execute("""
            UPDATE alembic_version
            SET version_num = 'a1b2c3d4e5f6';
        """)
        print("✅ Alembic version updated")
    except sqlite3.OperationalError:
        print("⚠️  Could not update alembic_version (table may not exist)")

    # Commit changes
    conn.commit()

    print("\n✅ Migration complete! join_code column added to student_blocks")
    print("   You can now run the legacy migration script.")

    # Close connection
    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    if 'conn' in locals():
        conn.rollback()
    sys.exit(1)
