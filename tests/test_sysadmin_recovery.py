from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin
import pytest
from app import db
from app.models import SystemAdmin, User
import pyotp

def test_sysadmin_reset_totp_unauthorized(client):
    teacher = seed_canonical_admin("teacher_fail").user
    response = client.post(f"/sysadmin/admins/{teacher.id}/reset-totp")
    assert response.status_code == 302
