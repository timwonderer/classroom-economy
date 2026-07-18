"""
Tests for API fixes:
1. Block tap settings import fix
2. Timezone sync CSRF token
"""
import pytest
from app.feats.base import FEATContext
from app import db
from app.models import SeatAttendanceState
from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher


@pytest.fixture
def teacher_user(client):
    """Create a teacher for testing."""
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    return classroom.teacher_user


def test_DOM_ATT_001__block_tap_settings_get_returns_tap_enabled_aggregate(client, teacher_user):
    """GET returns tap_enabled=True when any student seat has tap enabled (default)."""
    initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.get('/api/admin/block-tap-settings')

    assert response.status_code == 200
    data = response.get_json()
    assert 'tap_enabled' in data
    assert 'seat_count' in data
    # Default state: no SeatAttendanceState rows → tap enabled=True
    assert data['tap_enabled'] is True
    assert data['seat_count'] == 1


def test_DOM_ATT_001__block_tap_settings_get_no_students(client, teacher_user):
    """GET returns tap_enabled=True and seat_count=0 when no claimed seats exist."""
    initialize_as_teacher("ap_csp_p3", client, client.application)

    response = client.get('/api/admin/block-tap-settings')

    assert response.status_code == 200
    data = response.get_json()
    assert data['tap_enabled'] is True
    assert data['seat_count'] == 0


def test_DOM_ATT_001__block_tap_settings_get_reflects_disabled_state(client, teacher_user):
    """GET returns tap_enabled=False when all students have tap explicitly disabled."""
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)

    with FEATContext("FEAT-ATTN-001", idempotency_key=f"test-disable-tap:{student.seat.id}"):
        state = SeatAttendanceState(
            seat_id=student.seat.id,
            class_id=classroom.class_id,
            tap_enabled=False,
        )
        db.session.add(state)

    initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.get('/api/admin/block-tap-settings')

    assert response.status_code == 200
    data = response.get_json()
    assert data['tap_enabled'] is False
    assert data['seat_count'] == 1


def test_DOM_ATT_001__block_tap_settings_post_updates_seat_attendance_state(client, teacher_user):
    """POST sets tap_enabled on SeatAttendanceState for all claimed seats in the class."""
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)
    initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.post(
        '/api/admin/block-tap-settings',
        json={'tap_enabled': False},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert data['tap_enabled'] is False
    assert data['updated_count'] == 1

    # Verify DB was actually updated
    state = SeatAttendanceState.query.filter_by(
        seat_id=student.seat.id,
        class_id=classroom.class_id,
    ).first()
    assert state is not None
    assert state.tap_enabled is False


def test_DOM_ATT_001__block_tap_settings_post_missing_tap_enabled_field(client, teacher_user):
    """POST without tap_enabled field returns 400."""
    initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.post(
        '/api/admin/block-tap-settings',
        json={'block': 'A'},  # legacy field, missing tap_enabled
    )

    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


def test_DOM_ATT_001__block_tap_settings_ignored_block_param(client, teacher_user):
    """?block= query param is accepted but ignored — scoping is by class_id only (DOM-IDEN-007)."""
    initialize_as_teacher("chemistry_p1", client, client.application)

    # ?block=A is accepted for backwards-compat but must not restrict to that section
    response = client.get('/api/admin/block-tap-settings?block=A')

    assert response.status_code == 200
    data = response.get_json()
    # All seats in the class are returned, not just block "A"
    assert data['seat_count'] == 1


def test_DOM_ATT_001__set_timezone_endpoint_exists(client):
    """Test that /api/set-timezone endpoint exists and handles requests properly."""
    response = client.post(
        '/api/set-timezone',
        json={'timezone': 'America/New_York'}
    )

    assert response.status_code == 401


def test_DOM_ATT_001__timezone_sync_with_student_session(client):
    """Test timezone sync with authenticated student session."""
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)

    response = client.post(
        '/api/set-timezone',
        json={'timezone': 'America/Los_Angeles'}
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'

    with client.session_transaction() as sess:
        assert sess.get('timezone') == 'America/Los_Angeles'
