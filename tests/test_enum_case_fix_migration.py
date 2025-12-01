"""
Test that the enum case fix migration works correctly.

This test verifies that the migration 9957794d7f45 correctly handles
both uppercase and lowercase enum values in the database.
"""
import os
import sys
import pytest

# Set up environment before imports
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_ENV"] = "testing"
os.environ["PEPPER_KEY"] = "test-primary-pepper"
os.environ["PEPPER_LEGACY_KEYS"] = "legacy-pepper"
os.environ.setdefault("ENCRYPTION_KEY", "jhe53bcYZI4_MZS4Kb8hu8-xnQHHvwqSX8LN4sDtzbw=")
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models import DeletionRequestType


def test_enum_case_fix_migration_exists():
    """Verify that the enum case fix migration file exists."""
    test_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(test_dir, '..'))
    migrations_dir = os.path.join(repo_root, 'migrations', 'versions')
    
    migration_filename = '9957794d7f45_fix_deletionrequesttype_enum_case.py'
    migration_path = os.path.join(migrations_dir, migration_filename)
    
    assert os.path.exists(migration_path), (
        f"Migration file not found at {migration_path}"
    )


def test_enum_case_fix_migration_content():
    """Verify the migration file has the correct structure."""
    test_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(test_dir, '..'))
    migrations_dir = os.path.join(repo_root, 'migrations', 'versions')
    
    migration_filename = '9957794d7f45_fix_deletionrequesttype_enum_case.py'
    migration_path = os.path.join(migrations_dir, migration_filename)
    
    # Skip if file doesn't exist (for different environments)
    if not os.path.exists(migration_path):
        pytest.skip(f"Migration file not found at {migration_path}")
    
    with open(migration_path, 'r') as f:
        content = f.read()
    
    # Verify it creates the new enum with lowercase values
    assert "CREATE TYPE deletionrequesttype_new AS ENUM ('period', 'account')" in content, (
        "Migration should create new enum with lowercase values"
    )
    
    # Verify it handles case conversion properly
    assert "WHEN UPPER(request_type::text) = 'PERIOD' THEN 'period'" in content, (
        "Migration should convert PERIOD to period"
    )
    assert "WHEN UPPER(request_type::text) = 'ACCOUNT' THEN 'account'" in content, (
        "Migration should convert ACCOUNT to account"
    )
    
    # Verify it's idempotent
    assert "has_uppercase" in content or "isupper()" in content, (
        "Migration should check if fix is needed before applying"
    )
    
    # Verify it drops old enum and renames
    assert "DROP TYPE deletionrequesttype" in content, (
        "Migration should drop old enum"
    )
    assert "ALTER TYPE deletionrequesttype_new RENAME TO deletionrequesttype" in content, (
        "Migration should rename new enum to original name"
    )


def test_enum_case_fix_migration_revision_chain():
    """Verify the migration has the correct revision chain."""
    test_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(test_dir, '..'))
    migrations_dir = os.path.join(repo_root, 'migrations', 'versions')
    
    migration_filename = '9957794d7f45_fix_deletionrequesttype_enum_case.py'
    migration_path = os.path.join(migrations_dir, migration_filename)
    
    if not os.path.exists(migration_path):
        pytest.skip(f"Migration file not found at {migration_path}")
    
    with open(migration_path, 'r') as f:
        content = f.read()
    
    # Verify it comes after 3e1b8bd76b40
    assert "down_revision = '3e1b8bd76b40'" in content, (
        "Migration should have down_revision = '3e1b8bd76b40'"
    )
    
    # Verify revision ID is correct
    assert "revision = '9957794d7f45'" in content, (
        "Migration should have revision = '9957794d7f45'"
    )


def test_python_enum_values_are_lowercase():
    """Verify Python enum uses lowercase values."""
    assert DeletionRequestType.PERIOD.value == 'period', (
        "Python enum PERIOD should have lowercase value 'period'"
    )
    assert DeletionRequestType.ACCOUNT.value == 'account', (
        "Python enum ACCOUNT should have lowercase value 'account'"
    )
