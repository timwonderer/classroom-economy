from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest

pytestmark = [pytest.mark.critical, pytest.mark.regression]
import json
from datetime import datetime, timezone
from app import db
from app.models import Admin, TeacherOnboarding

def login_admin(client, username='admin'):
    from app.utils.auth_username import hash_username_lookup
    admin = Admin.query.filter_by(username_lookup_hash=hash_username_lookup(username)).first()
    if not admin:
        import pyotp
        totp_secret = pyotp.random_base32()
        admin = make_admin(username, totp_secret)
        db.session.add(admin)
        db.session.commit()

    # Ensure a User exists for this admin (required by get_current_admin() → get_current_user())
    from app.models import User, UserRole
    user = User.query.filter_by(username_lookup_hash=admin.username_lookup_hash).first()
    if not user:
        user = User(
            username_hash=admin.username_lookup_hash,
            username_lookup_hash=admin.username_lookup_hash,
            user_role=UserRole.TEACHER,
        )
        db.session.add(user)
        db.session.commit()

    # Simulate login by setting session
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['user_id'] = user.id
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
        sess['_fresh'] = True

    return admin



# ==================== WIDGET FUNCTIONALITY TESTS ====================

def test_widget_task_completed_methods(client):
    """Test mark_widget_task_completed and is_widget_task_completed methods."""
    admin = login_admin(client)
    
    # Create onboarding record
    onboarding = TeacherOnboarding(user_id=admin.id)
    db.session.add(onboarding)
    db.session.commit()
    
    # Initially, no tasks should be completed
    assert onboarding.is_widget_task_completed('roster') is False
    assert onboarding.is_widget_task_completed('payroll') is False
    
    # Mark a task as completed
    onboarding.mark_widget_task_completed('roster')
    db.session.commit()
    
    # Check it's marked as completed
    assert onboarding.is_widget_task_completed('roster') is True
    assert onboarding.is_widget_task_completed('payroll') is False
    
    # Mark another task
    onboarding.mark_widget_task_completed('payroll')
    db.session.commit()
    
    # Both should be completed now
    assert onboarding.is_widget_task_completed('roster') is True
    assert onboarding.is_widget_task_completed('payroll') is True
    
    # Verify last_activity_at was updated
    assert onboarding.last_activity_at is not None


def test_widget_task_completed_with_null_dict(client):
    """Test that is_widget_task_completed handles null widget_tasks_completed."""
    admin = login_admin(client)
    
    # Create onboarding record with null widget_tasks_completed
    onboarding = TeacherOnboarding(user_id=admin.id)
    onboarding.widget_tasks_completed = None
    db.session.add(onboarding)
    db.session.commit()
    
    # Should return False for any task when dict is None
    assert onboarding.is_widget_task_completed('roster') is False
    assert onboarding.is_widget_task_completed('payroll') is False
    
    # Marking a task should initialize the dict
    onboarding.mark_widget_task_completed('roster')
    db.session.commit()
    
    # Now it should be tracked
    assert onboarding.widget_tasks_completed is not None
    assert onboarding.is_widget_task_completed('roster') is True


def test_dismiss_widget_method(client):
    """Test dismiss_widget method."""
    admin = login_admin(client)
    
    # Create onboarding record
    onboarding = TeacherOnboarding(user_id=admin.id)
    db.session.add(onboarding)
    db.session.commit()
    
    # Initially not dismissed
    assert onboarding.widget_dismissed is False
    assert onboarding.widget_dismissed_at is None
    
    # Dismiss the widget
    onboarding.dismiss_widget()
    db.session.commit()
    
    # Should be marked as dismissed
    assert onboarding.widget_dismissed is True
    assert onboarding.widget_dismissed_at is not None
    assert isinstance(onboarding.widget_dismissed_at, datetime)
    assert onboarding.last_activity_at is not None


def test_onboarding_dismiss_widget_endpoint(client):
    """Test the /admin/onboarding/dismiss-widget endpoint."""
    admin = login_admin(client)
    
    # Call the endpoint
    response = client.post('/admin/onboarding/dismiss-widget',
                          json={},
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert 'message' in data
    
    # Verify database was updated
    onboarding = TeacherOnboarding.query.filter_by(user_id=admin.id).first()
    assert onboarding is not None
    assert onboarding.widget_dismissed is True
    assert onboarding.widget_dismissed_at is not None


def test_onboarding_dismiss_widget_endpoint_creates_record(client):
    """Test that dismiss-widget endpoint creates onboarding record if it doesn't exist."""
    admin = login_admin(client)
    
    # Ensure no onboarding record exists
    assert TeacherOnboarding.query.filter_by(user_id=admin.id).first() is None
    
    # Call the endpoint
    response = client.post('/admin/onboarding/dismiss-widget',
                          json={},
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    
    # Verify record was created and dismissed
    onboarding = TeacherOnboarding.query.filter_by(user_id=admin.id).first()
    assert onboarding is not None
    assert onboarding.widget_dismissed is True


def test_onboarding_skip_task_endpoint(client):
    """Test the /admin/onboarding/skip-task endpoint."""
    admin = login_admin(client)
    
    # Skip a task
    response = client.post('/admin/onboarding/skip-task',
                          json={'task': 'store'},
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert 'store' in data['message']
    
    # Verify task was marked as completed (skipped)
    onboarding = TeacherOnboarding.query.filter_by(user_id=admin.id).first()
    assert onboarding is not None
    assert onboarding.is_widget_task_completed('store') is True


def test_onboarding_skip_task_missing_task_name(client):
    """Test that skip-task endpoint requires task name."""
    admin = login_admin(client)
    
    # Call without task name
    response = client.post('/admin/onboarding/skip-task',
                          json={},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['status'] == 'error'


def test_onboarding_status_endpoint_dismissed(client):
    """Test that status endpoint returns dismissed:true when widget is dismissed."""
    admin = login_admin(client)
    
    # Create and dismiss widget
    onboarding = TeacherOnboarding(user_id=admin.id)
    onboarding.dismiss_widget()
    db.session.add(onboarding)
    db.session.commit()
    
    # Check status
    response = client.get('/admin/onboarding/status')
    assert response.status_code == 200
    data = json.loads(response.data)
    
    assert data['status'] == 'success'
    assert data['dismissed'] is True
    assert 'completion' in data


def test_onboarding_status_endpoint_no_class_period(client):
    """Test that status endpoint returns full checklist even when no class period is selected."""
    admin = login_admin(client)

    # Don't set a join_code in session
    with client.session_transaction() as sess:
        if 'join_code' in sess:
            del sess['join_code']

    # Check status
    response = client.get('/admin/onboarding/status')
    assert response.status_code == 200
    data = json.loads(response.data)

    assert data['status'] == 'success'
    assert data['dismissed'] is False
    # The onboarding widget always renders the full checklist regardless of
    # whether a class period is selected, so no_class_period is no longer returned.
    assert 'no_class_period' not in data
    assert 'completion' in data
    assert isinstance(data['completion'], dict)
