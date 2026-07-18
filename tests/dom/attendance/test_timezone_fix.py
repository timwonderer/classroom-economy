"""
Tests for Timezone API Fix:
1. Allow admins to sync timezone
2. Return 401 instead of redirect for unauthenticated users
"""
import pytest

from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher

def test_DOM_IDEN_006__set_timezone_unauthenticated(client):
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

def test_DOM_IDEN_006__set_timezone_admin(client):
    """Test that /api/set-timezone works for admins."""
    initialize_as_teacher("chemistry_p1", client, client.application)

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

def test_DOM_IDEN_006__set_timezone_student(client):
    """Test that /api/set-timezone still works for students."""
    initialize_as_student("chemistry_p1", client, client.application)

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

def test_DOM_IDEN_006__set_timezone_invalid(client):
    """Test that /api/set-timezone rejects invalid timezones."""
    initialize_as_teacher("chemistry_p1", client, client.application)

    response = client.post('/api/set-timezone', json={'timezone': 'Mars/Crater'})
    assert response.status_code == 400
    data = response.get_json()
    assert data['message'] == 'Invalid timezone.'
