from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from app import db
from app.models import Admin, SystemAdmin, User
import pyotp

def test_sysadmin_reset_totp(client):
    # Create system admin
    sysadmin = make_sysadmin("sysadmin_test", pyotp.random_base32())
    db.session.add(sysadmin)

    # Create teacher
    old_secret = pyotp.random_base32()
    teacher = make_admin("teacher_to_reset", old_secret)
    db.session.add(teacher)
    db.session.flush()
    db.session.add(User(
        username_hash=teacher.username_hash,
        username_lookup_hash=teacher.username_lookup_hash,
        totp_secret_encrypted=teacher.totp_secret,
    ))
    db.session.commit()

    # Login as sysadmin
    with client.session_transaction() as sess:
        sess['is_system_admin'] = True
        sess['sysadmin_id'] = sysadmin.id

    # Call reset endpoint
    response = client.post(f'/sysadmin/admins/{teacher.id}/reset-totp')
    assert response.status_code == 200
    data = response.json
    assert data['status'] == 'success'
    assert data['totp_secret'] != old_secret
    assert 'qr_code' in data

    # Verify in DB
    db.session.expire(teacher)
    user = User.query.filter_by(username_lookup_hash=teacher.username_lookup_hash).first()
    assert user is not None
    assert user.totp_secret_encrypted == data['totp_secret']
    assert user.totp_secret_encrypted != old_secret

def test_sysadmin_reset_totp_unauthorized(client):
    # Create teacher
    teacher = make_admin("teacher_fail", pyotp.random_base32())
    db.session.add(teacher)
    db.session.commit()

    # Call reset endpoint without login
    response = client.post(f'/sysadmin/admins/{teacher.id}/reset-totp')
    assert response.status_code == 302 # Redirect to login
