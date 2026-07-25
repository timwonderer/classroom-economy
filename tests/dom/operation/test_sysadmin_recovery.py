from app import app
from tests.helpers.classroom_initializer import initialize
from tests.helpers.operation_routes import post_sysadmin_reset_totp

def test_DOM_OPS_001__sysadmin_reset_totp_unauthorized(client):
    classroom = initialize("chemistry_p1", app)
    teacher = classroom.teacher_user
    response = post_sysadmin_reset_totp(client, teacher.id)
    assert response.status_code == 302
