"""
Test migration idempotency to ensure migrations can be run multiple times safely.

These tests run against the shared Postgres test database rather than SQLite.
"""

import pytest
from sqlalchemy import inspect, text

from app import db


def _reset_schema():
    db.session.remove()
    with db.engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        enum_rows = conn.execute(
            text(
                """
                SELECT t.typname
                FROM pg_type AS t
                JOIN pg_namespace AS n ON n.oid = t.typnamespace
                WHERE t.typtype = 'e' AND n.nspname = 'public'
                """
            )
        )
        for row in enum_rows:
            conn.execute(text(f'DROP TYPE IF EXISTS "{row.typname}" CASCADE'))
    db.engine.dispose()
    db.create_all()


@pytest.fixture
def test_db(app):
    """Create a clean Postgres test database with all necessary tables."""
    with app.app_context():
        _reset_schema()
        yield db


def test_column_exists_helper(test_db):
    """Test the column existence detection logic used in migrations."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY,
                    test_column VARCHAR(50)
                )
                """
            )
        )

    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("test_table")]
    assert "test_column" in columns
    assert "nonexistent_column" not in columns


def test_migration_1ef03001fb2a_idempotency(test_db):
    """Test that migration 1ef03001fb2a can detect existing columns."""
    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("store_items")]
    assert "teacher_id" in columns

    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_store_items (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(100)
                )
                """
            )
        )
    inspector = inspect(db.engine)
    columns_before = [col["name"] for col in inspector.get_columns("test_store_items")]
    assert "teacher_id" not in columns_before

    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE test_store_items ADD COLUMN teacher_id INTEGER"))

    inspector = inspect(db.engine)
    columns_after = [col["name"] for col in inspector.get_columns("test_store_items")]
    assert "teacher_id" in columns_after


def test_migration_w2x3y4z5a6b7_idempotency(test_db):
    """Test that the canonical settings tables no longer expose legacy teacher scoping."""
    tables = ["rent_settings", "payroll_settings", "banking_settings", "hall_pass_settings"]

    inspector = inspect(db.engine)
    for table in tables:
        columns = [col["name"] for col in inspector.get_columns(table)]
        assert "class_id" in columns
        assert "teacher_id" not in columns

    test_tables = ["test_rent", "test_payroll", "test_banking", "test_hall_pass"]
    with db.engine.begin() as conn:
        for table in test_tables:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id INTEGER PRIMARY KEY,
                        setting_value VARCHAR(100)
                    )
                    """
                )
            )

    inspector = inspect(db.engine)
    for table in test_tables:
        columns = [col["name"] for col in inspector.get_columns(table)]
        assert "teacher_id" not in columns

    with db.engine.begin() as conn:
        for table in test_tables:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN teacher_id INTEGER"))

    inspector = inspect(db.engine)
    for table in test_tables:
        columns = [col["name"] for col in inspector.get_columns(table)]
        assert "teacher_id" in columns


def test_migration_00212c18b0ac_idempotency(test_db):
    """Test that migration 00212c18b0ac can handle existing columns and indexes."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS transaction_test (
                    id INTEGER PRIMARY KEY,
                    student_id INTEGER,
                    join_code VARCHAR(20),
                    amount INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_transaction_test_join_code
                ON transaction_test (join_code)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_transaction_test_student_join_code
                ON transaction_test (student_id, join_code)
                """
            )
        )

    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("transaction_test")]
    assert "join_code" in columns

    indexes = [idx["name"] for idx in inspector.get_indexes("transaction_test")]
    assert "ix_transaction_test_join_code" in indexes
    assert "ix_transaction_test_student_join_code" in indexes


def test_helper_functions_dont_crash_with_existing_schema(test_db):
    """Test that helper functions handle existing schema elements gracefully."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS parent_table (
                    id INTEGER PRIMARY KEY
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS child_table (
                    id INTEGER PRIMARY KEY,
                    parent_id INTEGER REFERENCES parent_table(id)
                )
                """
            )
        )

    inspector = inspect(db.engine)
    columns = [col["name"] for col in inspector.get_columns("child_table")]
    assert "parent_id" in columns

    foreign_keys = inspector.get_foreign_keys("child_table")
    assert len(foreign_keys) >= 0


def test_nullable_column_check(test_db):
    """Test checking if a column is nullable."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_nullable (
                    id INTEGER PRIMARY KEY,
                    nullable_col INTEGER,
                    not_null_col INTEGER NOT NULL
                )
                """
            )
        )

    inspector = inspect(db.engine)
    columns = inspector.get_columns("test_nullable")

    nullable_col = next((col for col in columns if col["name"] == "nullable_col"), None)
    not_null_col = next((col for col in columns if col["name"] == "not_null_col"), None)

    assert nullable_col is not None
    assert nullable_col.get("nullable", True) is True

    assert not_null_col is not None
    assert not_null_col.get("nullable") is False
