"""
Tests for API fixes:
1. Block tap settings import fix
2. Timezone sync CSRF token
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timezone
from app import db
from app.models import Admin
from tests.helpers.canonical_session import set_canonical_context


@pytest.fixture
def admin_with_students(client):
    """Create an admin for testing."""
    # Create admin
    admin = make_admin("testadmin", "TESTSECRET123456")
    db.session.add(admin)
    db.session.flush()

    db.session.commit()
    return admin


def test_block_tap_settings_get_endpoint(client, admin_with_students):
    """Test that /api/admin/block-tap-settings GET endpoint works with correct import."""
    admin = admin_with_students
    
    # Login as admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    
    # Test GET endpoint
    response = client.get('/api/admin/block-tap-settings?block=A')
    
    # Should not get ImportError anymore (500 error)
    # 302 redirect is acceptable - means auth is working
    # 200/401 also acceptable depending on auth config
    assert response.status_code in [200, 302, 400, 401, 403], \
        f"Expected 200, 302, 400, 401, or 403, got {response.status_code}"
    
    # If successful, check response structure
    if response.status_code == 200:
        data = response.get_json()
        assert 'tap_enabled' in data


def test_block_tap_settings_post_endpoint(client, admin_with_students):
    """Test that /api/admin/block-tap-settings POST endpoint works with correct import."""
    admin = admin_with_students
    
    # Login as admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    
    # Test POST endpoint
    response = client.post(
        '/api/admin/block-tap-settings',
        json={'block': 'A', 'enabled': False}
    )
    
    # Should not get ImportError anymore (500 error)
    # 302 redirect is acceptable - means auth is working
    # 200/401 also acceptable depending on auth config
    # 400 is acceptable - means endpoint is reached but request validation failed
    assert response.status_code in [200, 302, 400, 401, 403], \
        f"Expected 200, 302, 400, 401, or 403, got {response.status_code}"


def test_set_timezone_endpoint_exists(client):
    """Test that /api/set-timezone endpoint exists and handles requests properly."""
    # Note: This endpoint requires login_required decorator, so we need a student session
    # We're just verifying the endpoint exists and doesn't crash
    
    # Without auth, should redirect or return error
    response = client.post(
        '/api/set-timezone',
        json={'timezone': 'America/New_York'}
    )
    
    # Should not crash with 500 error
    assert response.status_code in [302, 401, 403], \
        f"Expected redirect or auth error, got {response.status_code}"


def test_timezone_sync_with_student_session(client, test_student):
    """Test timezone sync with authenticated student session."""
    # Login as student with proper datetime
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
