"""
Tests for Timezone API Fix:
1. Allow admins to sync timezone
2. Return 401 instead of redirect for unauthenticated users
"""
from tests.helpers.v2_fixtures import seed_canonical_admin
import pytest
from datetime import datetime, timezone
from app import db
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context

@pytest.fixture
def admin_user(client):
    """Create an admin for testing."""
    admin = seed_canonical_admin("testadmin_tz").user
    db.session.commit()
    return admin

def test_set_timezone_unauthenticated(client):
    """Test that /api/set-timezone returns 401 for unauthenticated users."""
    response = client.post(
        '/api/set-timezone',
        json={'timezone': 'America/New_York'}
    )

    # Should return 401 Unauthorized
    assert response.status_code == 401
    data = response.get_json()
    assert data['status'] == 'error'
    assert data['message'] == 'Unauthorized'

def test_set_timezone_admin(client, admin_user):
    """Test that /api/set-timezone works for admins."""

    # Login as canonical teacher/admin context.
    class_row = create_class_scope(teacher_user=admin_user, join_code="TZADMIN1", section="A")
    with client.session_transaction() as sess:
        from app.models import Seat
        teacher_seat_id = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first().id
        set_canonical_context(
            sess,
            user_id=admin_user.id,
            class_id=class_row.class_id,
            seat_id=teacher_seat_id,
            role="teacher",
        )

    # Test timezone sync
    response = client.post(
        '/api/set-timezone',
        json={'timezone': 'America/Chicago'}
    )

    # Should succeed with admin auth
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'

    # Verify timezone was stored in session
    with client.session_transaction() as sess:
        assert sess.get('timezone') == 'America/Chicago'

def test_set_timezone_student(client, test_student):
    """Test that /api/set-timezone still works for students."""

    # Login as student
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=test_student.user_id,
            class_id=test_student.class_id,
            seat_id=test_student.id,
            role="student",
        )

    # Test timezone sync
    response = client.post(
        '/api/set-timezone',
        json={'timezone': 'America/Los_Angeles'}
    )

    # Should succeed with student auth
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'

    # Verify timezone was stored in session
    with client.session_transaction() as sess:
        assert sess.get('timezone') == 'America/Los_Angeles'

def test_set_timezone_invalid(client, admin_user):
    """Test that /api/set-timezone rejects invalid timezones."""

    class_row = create_class_scope(teacher_user=admin_user, join_code="TZINVALID1", section="A")
    with client.session_transaction() as sess:
        from app.models import Seat
        teacher_seat_id = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first().id
        set_canonical_context(
            sess,
            user_id=admin_user.id,
            class_id=class_row.class_id,
            seat_id=teacher_seat_id,
            role="teacher",
        )

    response = client.post('/api/set-timezone', json={'timezone': 'Mars/Crater'})
    assert response.status_code == 400
    data = response.get_json()
    assert data['message'] == 'Invalid timezone.'
