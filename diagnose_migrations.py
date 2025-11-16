#!/usr/bin/env python3
"""
Diagnostic script to check Alembic migration state.
Run this on your Digital Ocean server to diagnose migration issues.
"""
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

def check_migration_files():
    """Check all migration files and their dependencies."""
    migrations_dir = Path('migrations/versions')

    if not migrations_dir.exists():
        print("❌ migrations/versions directory not found!")
        return None, None

    revisions = {}
    dependencies = {}

    print("📁 Scanning migration files...")
    for migration_file in migrations_dir.glob('*.py'):
        if migration_file.name.startswith('__'):
            continue

        with open(migration_file, 'r') as f:
            content = f.read()
            revision = None
            down_revision = None

            for line in content.split('\n'):
                if line.startswith("revision = "):
                    revision = line.split("=")[1].strip().strip("'\"")
                elif line.startswith("down_revision = "):
                    down_rev_str = line.split("=")[1].strip()
                    if down_rev_str == 'None':
                        down_revision = None
                    elif down_rev_str.startswith('('):
                        down_revision = eval(down_rev_str)
                    else:
                        down_revision = down_rev_str.strip("'\"")

            if revision:
                revisions[revision] = migration_file.name
                dependencies[revision] = down_revision

    print(f"✓ Found {len(revisions)} migration files\n")
    return revisions, dependencies

def find_broken_dependencies(revisions, dependencies):
    """Find any broken migration dependencies."""
    print("🔍 Checking for broken dependencies...")
    broken = []

    for rev, down_rev in dependencies.items():
        if down_rev is not None:
            if isinstance(down_rev, tuple):
                for dr in down_rev:
                    if dr not in revisions:
                        broken.append((rev, dr, revisions[rev]))
                        print(f"  ❌ {revisions[rev]} references missing: {dr}")
            else:
                if down_rev not in revisions:
                    broken.append((rev, down_rev, revisions[rev]))
                    print(f"  ❌ {revisions[rev]} references missing: {down_rev}")

    if not broken:
        print("  ✓ No broken dependencies found")

    return broken

def check_database_state():
    """Check the alembic_version table in the database."""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("\n⚠️  DATABASE_URL not set - skipping database check")
        return None

    try:
        print(f"\n🗄️  Connecting to database...")
        engine = create_engine(database_url)

        with engine.connect() as conn:
            # Check if alembic_version table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'alembic_version'
                )
            """))
            exists = result.scalar()

            if not exists:
                print("  ⚠️  alembic_version table doesn't exist - fresh database")
                return None

            # Get current version
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            current = result.scalar()

            print(f"  ✓ Current database version: {current}")
            return current

    except Exception as e:
        print(f"  ❌ Database check failed: {e}")
        return None

def main():
    print("=" * 70)
    print("🔧 Alembic Migration Diagnostics")
    print("=" * 70)
    print()

    # Check migration files
    revisions, dependencies = check_migration_files()
    if not revisions:
        print("\n❌ Cannot proceed - no migrations found")
        sys.exit(1)

    # Check for broken dependencies
    broken = find_broken_dependencies(revisions, dependencies)

    # Check database state
    current_version = check_database_state()

    # Summary
    print("\n" + "=" * 70)
    print("📊 Summary")
    print("=" * 70)
    print(f"Migration files: {len(revisions)}")
    print(f"Broken dependencies: {len(broken)}")

    if current_version:
        print(f"Database version: {current_version}")
        if current_version in revisions:
            print(f"  ✓ Current version exists in migrations")
        else:
            print(f"  ❌ Current version NOT in migration files!")
            print(f"     This is likely causing your deployment error!")

    # Find heads
    all_down_revs = set()
    for down_rev in dependencies.values():
        if down_rev is not None:
            if isinstance(down_rev, tuple):
                all_down_revs.update(down_rev)
            else:
                all_down_revs.add(down_rev)

    heads = [rev for rev in revisions.keys() if rev not in all_down_revs]
    print(f"Migration heads: {len(heads)}")

    if len(heads) > 1:
        print("  ⚠️  Multiple heads detected:")
        for head in heads:
            print(f"     - {head}: {revisions[head]}")
    elif len(heads) == 1:
        print(f"  ✓ Single head: {heads[0]}")

    # Exit code
    if broken or len(heads) > 1:
        print("\n❌ Issues detected - fix required before deployment")
        sys.exit(1)
    else:
        print("\n✓ Migration chain looks healthy")
        sys.exit(0)

if __name__ == '__main__':
    main()
