#!/usr/bin/env python
"""Check current alembic migration version in the database."""

from app.extensions import db
from app import create_app

app = create_app()
with app.app_context():
    try:
        # Use SQLAlchemy 2.0 compatible syntax
        from sqlalchemy import text
        result = db.session.execute(text("SELECT version_num FROM alembic_version;"))
        version = result.scalar()
        print(f"Current alembic migration: {version}")

        # Also show what migrations exist
        print("\nRecent migration files:")
        import os
        migration_dir = "migrations/versions"
        files = sorted(os.listdir(migration_dir), reverse=True)[:10]
        for f in files:
            if f.endswith('.py') and not f.startswith('__'):
                print(f"  {f}")

    except Exception as e:
        print(f"Error: {e}")

