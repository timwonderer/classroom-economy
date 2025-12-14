import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Create tables based on current models
    db.create_all()

    # Create alembic_version table if not exists (it shouldn't)
    db.session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
    db.session.execute(text("DELETE FROM alembic_version"))

    # Insert HEAD revision
    # I will get the head from flask db heads output passed as arg or hardcoded
    # Hardcoding a7b8c9d0e1f2 based on previous output
    head = "a7b8c9d0e1f2"
    db.session.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": head})

    db.session.commit()
    print(f"Database initialized and stamped with head: {head}")
