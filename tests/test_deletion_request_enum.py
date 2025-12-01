"""
Test that DeletionRequestType enum values match those used in the migration.

This test ensures the migration enum values stay in sync with the model definition.
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

from app.extensions import db
from app import app
from app.models import DeletionRequestType


@pytest.fixture
def test_db():
    """Create a test database with all necessary tables."""
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        ENV="testing",
        SESSION_COOKIE_SECURE=False,
    )
    ctx = app.app_context()
    ctx.push()
    
    # Create all tables
    db.create_all()
    
    yield db
    
    db.drop_all()
    ctx.pop()


def test_deletion_request_type_enum_values():
    """Verify DeletionRequestType enum has the correct values."""
    # The enum should have exactly these two values
    expected_values = {'period', 'account'}
    actual_values = {member.value for member in DeletionRequestType}
    
    assert actual_values == expected_values, (
        f"DeletionRequestType enum values mismatch. "
        f"Expected: {expected_values}, Got: {actual_values}"
    )


def test_deletion_request_type_members():
    """Verify DeletionRequestType enum has the correct member names."""
    # The enum should have exactly these two members
    assert hasattr(DeletionRequestType, 'PERIOD'), "PERIOD member missing"
    assert hasattr(DeletionRequestType, 'ACCOUNT'), "ACCOUNT member missing"
    
    # Verify the values are correct
    assert DeletionRequestType.PERIOD.value == 'period'
    assert DeletionRequestType.ACCOUNT.value == 'account'


def test_deletion_request_type_from_string():
    """Test the from_string method handles correct values."""
    # Should successfully convert valid strings
    assert DeletionRequestType.from_string('period') == DeletionRequestType.PERIOD
    assert DeletionRequestType.from_string('account') == DeletionRequestType.ACCOUNT
    
    # Should raise ValueError for invalid strings
    with pytest.raises(ValueError) as exc_info:
        DeletionRequestType.from_string('invalid_value')
    assert "Invalid DeletionRequestType" in str(exc_info.value)
    
    # Should handle enum values passed in
    assert DeletionRequestType.from_string(DeletionRequestType.PERIOD) == DeletionRequestType.PERIOD


def test_migration_enum_values_match_model():
    """
    Verify that the migration file uses the same enum values as the model.
    
    This is a documentation test - it checks that the migration file
    contains the correct enum values that match the model.
    """
    migration_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        'migrations',
        'versions',
        '1ef03001fb2a_add_teacher_id_to_store_items_for_multi_.py'
    )
    
    # Read the migration file
    with open(migration_path, 'r') as f:
        migration_content = f.read()
    
    # Check that the migration uses the correct enum values
    assert "postgresql.ENUM('period', 'account'" in migration_content, (
        "Migration should use ENUM('period', 'account', ...) to match the model"
    )
    
    # Check that the migration does NOT use the old incorrect values
    assert "full_account" not in migration_content, (
        "Migration should not use the old 'full_account' value"
    )
    assert "student_data_only" not in migration_content, (
        "Migration should not use the old 'student_data_only' value"
    )
    
    # Check that case-insensitive conversion is present
    assert "LOWER(request_type::text)" in migration_content, (
        "Migration should handle case-insensitive conversion for existing data"
    )
