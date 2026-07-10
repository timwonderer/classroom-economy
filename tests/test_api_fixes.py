"""
Tests for API fixes:
1. Block tap settings import fix
2. Timezone sync CSRF token
"""
from tests.helpers.v2_fixtures import make_teacher
import pytest
from datetime import datetime, timezone
from app import db
from app.models import ClassEconomy, Seat, User, UserRole
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_scope import create_class_scope
from tests.helpers.admin_context import login_teacher


@pytest.fixture
def teacher_user(client):
    """Create a teacher for testing."""
    teacher = make_teacher("testadmin")
    db.session.flush()
    db.session.commit()
    return teacher


def test_block_tap_settings_get_endpoint(client, teacher_user):
    """Test that /api/admin/block-tap-settings GET endpoint works with correct import."""
    login_teacher(client, teacher_user)

    response = client.get('/api/admin/block-tap-settings?block=A')

    assert response.status_code in [200, 302, 400, 401, 403], \
        f"Expected 200, 302, 400, 401, or 403, got {response.status_code}"

    if response.status_code == 200:
        data = response.get_json()
        assert 'tap_enabled' in data


def test_block_tap_settings_post_endpoint(client, teacher_user):
    """Test that /api/admin/block-tap-settings POST endpoint works with correct import."""
    login_teacher(client, teacher_user)

    response = client.post(
        '/api/admin/block-tap-settings',
        json={'block': 'A', 'enabled': False}
    )

    assert response.status_code in [200, 302, 400, 401, 403], \
        f"Expected 200, 302, 400, 401, or 403, got {response.status_code}"


def test_set_timezone_endpoint_exists(client):
    """Test that /api/set-timezone endpoint exists and handles requests properly."""
    response = client.post(
        '/api/set-timezone',
        json={'timezone': 'America/New_York'}
    )

    assert response.status_code in [302, 401, 403], \
        f"Expected redirect or auth error, got {response.status_code}"


def test_timezone_sync_with_student_session(client):
    """Test timezone sync with authenticated student session."""
    teacher = make_teacher("timezone_admin")
    db.session.flush()
    class_row = create_class_scope(teacher_user=teacher, join_code="TZ01")
    db.session.flush()

    student_user = User(
        user_role=UserRole.STUDENT,
        username_hash="tz_student_hash",
        username_lookup_hash="tz_student_lookup",
    )
    db.session.add(student_user)
    db.session.flush()
    student_seat = Seat(
        user_id=student_user.id,
        class_id=class_row.class_id,
        role="student",
        block="A",
        block_identifier="A",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(student_seat)
    db.session.flush()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student_seat.user_id,
            class_id=class_row.class_id,
            seat_id=student_seat.id,
            role="student",
        )

    response = client.post(
        '/api/set-timezone',
        json={'timezone': 'America/Los_Angeles'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'

    with client.session_transaction() as sess:
        assert sess.get('timezone') == 'America/Los_Angeles'
