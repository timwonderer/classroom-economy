"""
Test the legacy students-table drop migration.

These tests run against the shared Postgres test database rather than SQLite.
"""

from importlib import util
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text

from app import db


MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "9c1d2e3f4a5b_drop_students_table.py"


def _load_migration_module():
    spec = util.spec_from_file_location("migration_9c1d2e3f4a5b_drop_students_table", MIGRATION_PATH)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _reset_schema():
    db.session.remove()
    with db.engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    db.engine.dispose()
    db.create_all()


def _prepare_legacy_students_table():
    with db.engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS legacy_student_notes CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS students CASCADE"))
        conn.execute(
            text(
                """
                CREATE TABLE students (
                    id SERIAL PRIMARY KEY,
                    first_name BYTEA NOT NULL,
                    last_initial VARCHAR(1) NOT NULL,
                    identity_id INTEGER NOT NULL,
                    block VARCHAR(10) NOT NULL,
                    join_code VARCHAR(20),
                    class_id VARCHAR(36),
                    salt BYTEA NOT NULL,
                    internal_reference VARCHAR(64) NOT NULL,
                    opaque_reference VARCHAR(64) NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE legacy_student_notes (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE
                )
                """
            )
        )


def _table_columns(table_name):
    inspector = inspect(db.engine)
    return {col["name"] for col in inspector.get_columns(table_name)}


def _table_fks(table_name):
    inspector = inspect(db.engine)
    return inspector.get_foreign_keys(table_name)


def test_students_table_drop_migration_is_idempotent(app, monkeypatch):
    with app.app_context():
        _reset_schema()
        _prepare_legacy_students_table()
        migration = _load_migration_module()

        with db.engine.begin() as conn:
            ops = Operations(MigrationContext.configure(conn))
            monkeypatch.setattr(migration, "op", ops)

            migration.upgrade()
            migration.upgrade()

            inspector = inspect(conn)
            assert "students" not in inspector.get_table_names()
            assert inspector.get_foreign_keys("legacy_student_notes") == []

            migration.downgrade()
            migration.downgrade()

            inspector = inspect(conn)
            assert "students" in inspector.get_table_names()

            columns = {col["name"] for col in inspector.get_columns("students")}
            assert {"id", "first_name", "last_initial", "identity_id", "block", "salt", "internal_reference", "opaque_reference"}.issubset(columns)
            assert inspector.get_foreign_keys("legacy_student_notes") == []
