import pytest
import os
from cryptography.fernet import Fernet

# Set env before importing app or running tests
os.environ["FLASK_ENV"] = "testing"

import json
from app import create_app, db
from app.models import Admin, TeacherOnboarding

@pytest.fixture
def client():
    # Ensure env vars are set for testing
    os.environ["FLASK_ENV"] = "testing"
    os.environ["SECRET_KEY"] = "test_secret"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    os.environ["PEPPER_KEY"] = "test_pepper"

    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for tests usually, but here we might want to test it or bypass it

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()

def login_admin(client, username='admin'):
    # Create admin if not exists
    admin = Admin.query.filter_by(username=username).first()
    if not admin:
        import pyotp
        totp_secret = pyotp.random_base32()
        admin = Admin(username=username, totp_secret=totp_secret)
        db.session.add(admin)
        db.session.commit()

    # Simulate login by setting session
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['_fresh'] = True

    return admin

def test_onboarding_step_welcome(client):
    admin = login_admin(client)

    # Ensure onboarding record exists or is created
    # Accessing the page creates the record in _get_or_create_onboarding
    response = client.get('/admin/onboarding')
    assert response.status_code == 200

    # Check if onboarding record is created
    onboarding = TeacherOnboarding.query.filter_by(teacher_id=admin.id).first()
    assert onboarding is not None
    assert onboarding.current_step == 1

    # POST to next step
    # Route: /admin/onboarding/step/<step_name>
    response = client.post('/admin/onboarding/step/welcome',
                          json={},
                          content_type='application/json')

    assert response.status_code == 200, f"Response: {response.data}"
    data = json.loads(response.data)
    assert data['status'] == 'success'

    # Reload onboarding record
    db.session.expire(onboarding)
    onboarding = TeacherOnboarding.query.filter_by(teacher_id=admin.id).first()

    # Verify the current_step has incremented
    # 'welcome' is step 1. After completion, it should be step 2.
    assert onboarding.current_step == 2, f"Expected step 2, got {onboarding.current_step}"
