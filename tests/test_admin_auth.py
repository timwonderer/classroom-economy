from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pyotp
from datetime import datetime, timezone

from app import db
from app.auth import ensure_admin_join_code, get_current_admin
from app.models import Admin, IdentityProfile, User, UserRole, Seat


def test_admin_login_sets_session_identity(client):
    secret = pyotp.random_base32()
    admin = make_admin("teacher1", secret)
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=admin.username_hash,
        username_lookup_hash=admin.username_lookup_hash,
        totp_secret_encrypted=admin.totp_secret,
    )
    db.session.add_all([admin, user])
    db.session.commit()

    response = client.post(
        "/admin/login",
        data={"username": "teacher1", "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("is_admin") is True
        assert sess.get("admin_id") == admin.id
        assert sess.get("user_id") == user.id
        assert "last_activity" in sess

    with client.application.test_request_context('/'):
        from flask import session

        session["is_admin"] = True
        session["admin_id"] = admin.id
        session["user_id"] = user.id
        assert get_current_admin().id == admin.id


def test_admin_required_blocks_missing_identity(client):
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    response = client.get("/admin/students", follow_redirects=False)

    assert response.status_code == 302
    assert "/admin/login" in response.headers.get("Location", "")


def test_ensure_admin_join_code_does_not_use_teacher_block_as_authority(client, monkeypatch):
    admin = make_admin("teacher_fallback", "TESTSECRET123456")
    db.session.add(admin)
    db.session.flush()

    identity = IdentityProfile(profile_type="student", first_name="Policy", last_initial="S")
    db.session.add(identity)
    db.session.flush()

    _tb_seat = Seat(join_code="LEGACY123", block="A", block_identifier="A", role="student")

    db.session.add(_tb_seat)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_unclaimed', first_name="Policy", last_initial="S"))
    db.session.commit()

    monkeypatch.setattr("app.auth._table_exists", lambda table_name: table_name != "class_memberships")

    with client.application.test_request_context("/"):
        from flask import session

        ensure_admin_join_code(admin.id)

        assert "current_join_code" not in session
