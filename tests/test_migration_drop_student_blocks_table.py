"""
Test the legacy student_blocks-table drop migration.

These tests run against the shared Postgres test database rather than SQLite.
"""

from importlib import util
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text

from app import db


MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "8b1bc35a7d58_drop_legacy_studentblock_table.py"


def _load_migration_module():
    spec = util.spec_from_file_location("migration_8b1bc35a7d58_drop_legacy_studentblock_table", MIGRATION_PATH)
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


def _prepare_legacy_student_blocks_table():
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE student_blocks (
                    id SERIAL PRIMARY KEY,
                    seat_id INTEGER NOT NULL,
                    period VARCHAR(10) NOT NULL,
                    class_id VARCHAR(36),
                    join_code VARCHAR(20),
                    tap_enabled BOOLEAN NOT NULL DEFAULT true,
                    done_for_day_date DATE,
                    rent_hall_passes INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE,
                    updated_at TIMESTAMP WITH TIME ZONE
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX ix_student_blocks_class_id ON student_blocks (class_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE legacy_student_block_notes (
                    id SERIAL PRIMARY KEY,
                    student_block_id INTEGER NOT NULL REFERENCES student_blocks(id) ON DELETE CASCADE
                )
                """
            )
        )


def test_student_blocks_table_drop_migration_is_idempotent(app, monkeypatch):
    with app.app_context():
        _reset_schema()
        _prepare_legacy_student_blocks_table()
        migration = _load_migration_module()

        with db.engine.begin() as conn:
            ops = Operations(MigrationContext.configure(conn))
            monkeypatch.setattr(migration, "op", ops)

            migration.upgrade()
            migration.upgrade()

            inspector = inspect(conn)
            assert "student_blocks" not in inspector.get_table_names()
            assert inspector.get_foreign_keys("legacy_student_block_notes") == []

            migration.downgrade()
            migration.downgrade()

            inspector = inspect(conn)
            assert "student_blocks" in inspector.get_table_names()

            columns = {col["name"] for col in inspector.get_columns("student_blocks")}
            assert {"id", "seat_id", "period", "class_id", "join_code", "tap_enabled", "rent_hall_passes"}.issubset(columns)
            assert inspector.get_foreign_keys("legacy_student_block_notes") == []

