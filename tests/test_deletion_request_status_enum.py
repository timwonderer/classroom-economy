"""
Test that DeletionRequestStatus enum values are correct and properly stored.

This test ensures the migration correctly handles the enum case conversion.
"""
import os
import sys
import pytest
import pyotp

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
from app.models import DeletionRequestStatus, DeletionRequestType, DeletionRequest, Admin


def test_deletion_request_status_enum_values():
    """Verify DeletionRequestStatus enum has the correct lowercase values."""
    # The enum should have exactly these three values (lowercase)
    expected_values = {'pending', 'approved', 'rejected'}
    actual_values = {member.value for member in DeletionRequestStatus}
    
    assert actual_values == expected_values, (
        f"DeletionRequestStatus enum values mismatch. "
        f"Expected: {expected_values}, Got: {actual_values}"
    )


def test_deletion_request_status_members():
    """Verify DeletionRequestStatus enum has the correct member names."""
    # The enum should have exactly these three members (uppercase names, lowercase values)
    assert hasattr(DeletionRequestStatus, 'PENDING'), "PENDING member missing"
    assert hasattr(DeletionRequestStatus, 'APPROVED'), "APPROVED member missing"
    assert hasattr(DeletionRequestStatus, 'REJECTED'), "REJECTED member missing"
    
    # Verify the values are lowercase
    assert DeletionRequestStatus.PENDING.value == 'pending'
    assert DeletionRequestStatus.APPROVED.value == 'approved'
    assert DeletionRequestStatus.REJECTED.value == 'rejected'


def test_deletion_request_status_can_be_stored_and_retrieved():
    """Test that DeletionRequestStatus can be stored and retrieved from database."""
    with app.app_context():
        # Clean up any existing data
        db.drop_all()
        db.create_all()
        
        # Create a test admin
        admin = Admin(
            username='test_admin',
            totp_secret=pyotp.random_base32()
        )
        db.session.add(admin)
        db.session.commit()
        
        # Create a deletion request with PENDING status
        deletion_request = DeletionRequest(
            admin_id=admin.id,
            request_type=DeletionRequestType.ACCOUNT,
            status=DeletionRequestStatus.PENDING,
            reason="Test deletion request"
        )
        db.session.add(deletion_request)
        db.session.commit()
        
        # Retrieve the deletion request
        retrieved = DeletionRequest.query.filter_by(admin_id=admin.id).first()
        
        # Verify the status is correct
        assert retrieved is not None, "Deletion request not found"
        assert retrieved.status == DeletionRequestStatus.PENDING, (
            f"Status mismatch. Expected PENDING, got {retrieved.status}"
        )
        
        # Update the status
        retrieved.status = DeletionRequestStatus.APPROVED
        db.session.commit()
        
        # Re-retrieve and verify
        updated = DeletionRequest.query.filter_by(admin_id=admin.id).first()
        assert updated.status == DeletionRequestStatus.APPROVED, (
            f"Status update failed. Expected APPROVED, got {updated.status}"
        )


def test_deletion_request_status_enum_comparison():
    """Test that enum comparisons work correctly."""
    # Test equality
    assert DeletionRequestStatus.PENDING == DeletionRequestStatus.PENDING
    assert DeletionRequestStatus.PENDING != DeletionRequestStatus.APPROVED
    
    # Test value comparison
    assert DeletionRequestStatus.PENDING.value == 'pending'
    assert DeletionRequestStatus.APPROVED.value == 'approved'
    assert DeletionRequestStatus.REJECTED.value == 'rejected'
    
    # Test that uppercase values don't match
    assert DeletionRequestStatus.PENDING.value != 'PENDING'
    assert DeletionRequestStatus.APPROVED.value != 'APPROVED'
    assert DeletionRequestStatus.REJECTED.value != 'REJECTED'
