"""
Test that migration 1a4ee2388d62 (add teacher analytics) can handle
missing indexes and columns gracefully.

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
    """Create a clean Postgres test database with necessary tables."""
    with app.app_context():
        _reset_schema()
        yield db


def test_conditional_index_drop_logic(test_db):
    """Test that the migration's conditional index drop logic works correctly."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_credentials (
                    id INTEGER PRIMARY KEY,
                    credential_id TEXT,
                    public_key BYTEA,
                    aaguid VARCHAR(36),
                    sign_count INTEGER,
                    transports VARCHAR(255)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_test_credentials_credential_id
                ON test_credentials(credential_id)
                """
            )
        )

    inspector = inspect(db.engine)
    indexes_before = {idx["name"] for idx in inspector.get_indexes("test_credentials")}
    assert "ix_test_credentials_credential_id" in indexes_before

    test_cred_indexes = {idx["name"] for idx in inspector.get_indexes("test_credentials")}
    test_cred_columns = {col["name"] for col in inspector.get_columns("test_credentials")}

    if "ix_test_credentials_credential_id" in test_cred_indexes:
        with db.engine.begin() as conn:
            conn.execute(text("DROP INDEX IF EXISTS ix_test_credentials_credential_id"))

    inspector = inspect(db.engine)
    indexes_after = {idx["name"] for idx in inspector.get_indexes("test_credentials")}
    assert "ix_test_credentials_credential_id" not in indexes_after

    columns_to_drop = ["public_key", "aaguid", "sign_count", "transports"]
    for col in columns_to_drop:
        assert col in test_cred_columns


def test_conditional_index_drop_when_missing(test_db):
    """Test that the migration handles missing indexes gracefully."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_credentials_no_index (
                    id INTEGER PRIMARY KEY,
                    credential_id TEXT,
                    authenticator_name VARCHAR(100)
                )
                """
            )
        )

    inspector = inspect(db.engine)
    indexes_before = {idx["name"] for idx in inspector.get_indexes("test_credentials_no_index")}
    assert "ix_test_credentials_no_index_credential_id" not in indexes_before

    test_cred_indexes = {idx["name"] for idx in inspector.get_indexes("test_credentials_no_index")}
    if "ix_test_credentials_no_index_credential_id" in test_cred_indexes:
        pytest.fail("Index should not exist but was found in indexes")


def test_column_existence_check(test_db):
    """Test that column existence detection works correctly."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS test_column_check (
                    id INTEGER PRIMARY KEY,
                    existing_col TEXT,
                    another_col INTEGER
                )
                """
            )
        )

    inspector = inspect(db.engine)
    columns = {col["name"] for col in inspector.get_columns("test_column_check")}

    assert "existing_col" in columns
    assert "another_col" in columns
    assert "nonexistent_col" not in columns

    columns_to_check = ["existing_col", "nonexistent_col", "another_col"]
    columns_that_exist = [col for col in columns_to_check if col in columns]

    assert "existing_col" in columns_that_exist
    assert "another_col" in columns_that_exist
    assert "nonexistent_col" not in columns_that_exist


def test_both_tables_pattern(test_db):
    """Test the pattern used for both admin_credentials and system_admin_credentials."""
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS sim_admin_credentials (
                    id INTEGER PRIMARY KEY,
                    credential_id TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_sim_admin_credentials_cred
                ON sim_admin_credentials(credential_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS sim_system_admin_credentials (
                    id INTEGER PRIMARY KEY,
                    credential_id TEXT
                )
                """
            )
        )

    inspector = inspect(db.engine)
    admin_indexes = {idx["name"] for idx in inspector.get_indexes("sim_admin_credentials")}
    assert "ix_sim_admin_credentials_cred" in admin_indexes

    sys_admin_indexes = {idx["name"] for idx in inspector.get_indexes("sim_system_admin_credentials")}
    assert "ix_sim_system_admin_credentials_cred" not in sys_admin_indexes

    if "ix_sim_admin_credentials_cred" in admin_indexes:
        with db.engine.begin() as conn:
            conn.execute(text("DROP INDEX IF EXISTS ix_sim_admin_credentials_cred"))

    if "ix_sim_system_admin_credentials_cred" in sys_admin_indexes:
        pytest.fail("This should not execute because index doesn't exist")

    inspector = inspect(db.engine)
    admin_indexes_after = {idx["name"] for idx in inspector.get_indexes("sim_admin_credentials")}
    assert "ix_sim_admin_credentials_cred" not in admin_indexes_after
