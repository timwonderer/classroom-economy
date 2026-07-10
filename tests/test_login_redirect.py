import pyotp
from app import db
from werkzeug.security import generate_password_hash
from app.hash_utils import hash_username, hash_username_lookup, get_random_salt
from app.models import ClassEconomy, IdentityProfile, Seat, User, UserRole
from app.utils.time import utc_now
from tests.helpers.v2_fixtures import make_admin

def test_student_login_next_redirect(client):
    salt = get_random_salt()
    username = "stu1"
    admin = make_admin("login_redirect_teacher", pyotp.random_base32())
    db.session.flush()
    class_row = ClassEconomy(join_code="LOGIN-REDIRECT", user_id=admin.id, display_name="Login")
    profile = IdentityProfile(profile_type="student", first_name="Stu", last_name="S")
    db.session.add_all([class_row, profile])
    db.session.flush()
    user = User(
        user_role=UserRole.STUDENT,
        username_hash=hash_username(username, salt),
        username_lookup_hash=hash_username_lookup(username),
        pin_hash=generate_password_hash("1234"),
        has_completed_setup=True,
        last_active_class_id=class_row.class_id,
    )
    db.session.add(user)
    db.session.flush()
    seat = Seat(
        user_id=user.id,
        class_id=class_row.class_id,
        role="student",
        claimed_at=utc_now(),
    )
    db.session.add(seat)
    db.session.flush()
    profile.seat_id = seat.id
    db.session.commit()

    # Access protected route
    resp = client.get('/student/dashboard')
    assert resp.status_code == 302
    assert '/student/login?next=%2Fstudent%2Fdashboard' in resp.headers['Location']

    # Login and expect redirect back
    login_resp = client.post('/student/login?next=/student/dashboard', data={'username': 'stu1', 'pin': '1234'})
    assert login_resp.status_code == 302
    assert login_resp.headers['Location'].endswith('/student/dashboard')
