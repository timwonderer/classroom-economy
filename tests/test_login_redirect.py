import pyotp
from app import db
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.v2_fixtures import seed_canonical_admin

def test_student_login_next_redirect(client):
    admin = seed_canonical_admin("login_redirect_teacher", pyotp.random_base32()).user
    db.session.flush()
    class_row = create_class_scope(teacher_user=admin, join_code="LOGIN-REDIRECT", display_name="Login")
    make_student_identity(
        class_id=class_row.class_id,
        first_name="Stu",
        last_name="S",
        claimed=True,
        username="stu1",
        pin="1234",
    )
    db.session.commit()

    # Access protected route
    resp = client.get('/student/dashboard')
    assert resp.status_code == 302
    assert resp.headers['Location'].startswith('/student/login')
    assert '/student/dashboard' in resp.headers['Location']

    # Login and expect redirect back
    login_resp = client.post('/student/login?next=/student/dashboard', data={'username': 'stu1', 'pin': '1234'})
    assert login_resp.status_code == 302
    assert login_resp.headers['Location'].endswith('/student/dashboard')
