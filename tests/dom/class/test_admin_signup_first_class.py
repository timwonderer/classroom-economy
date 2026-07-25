from app import db
from app.models import ClassEconomy, Seat, User, UserRole
from app.utils.auth_username import build_hashed_username_fields


def test_DOM_CLASS_001__admin_signup_provisions_initial_class(client, monkeypatch):
    monkeypatch.setattr("app.routes.admin.verify_turnstile_token", lambda *_args, **_kwargs: True)
    monkeypatch.setattr("app.routes.admin.pyotp.random_base32", lambda: "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr("app.routes.admin.pyotp.TOTP.verify", lambda self, code: code == "123456")
    monkeypatch.setattr("app.routes.admin.generate_join_code", lambda: "SIGNUP1")

    initial_post = client.post(
        "/admin/signup",
        data={
            "username": "teacher-signup",
            "tos_agreed": "true",
            "turnstile_token": "token",
        },
        follow_redirects=False,
    )

    assert initial_post.status_code == 200
    assert "Set Up Your Authenticator" in initial_post.get_data(as_text=True)

    final_post = client.post(
        "/admin/signup",
        data={
            "username": "teacher-signup",
            "totp_code": "123456",
            "tos_agreed": "true",
        },
        follow_redirects=False,
    )

    assert final_post.status_code in (302, 303)

    _salt, _username_hash, username_lookup_hash = build_hashed_username_fields("teacher-signup")
    teacher = User.query.filter_by(username_lookup_hash=username_lookup_hash).first()
    assert teacher is not None
    assert teacher.user_role == UserRole.TEACHER
    assert teacher.last_active_class_id is not None
    assert teacher.last_active_seat_id is not None

    class_row = ClassEconomy.query.filter_by(user_id=teacher.id).first()
    assert class_row is not None
    assert class_row.join_code == "SIGNUP1"
    assert class_row.display_name == "teacher-signup"

    teacher_seat = Seat.query.filter_by(user_id=teacher.id, class_id=class_row.class_id, role="teacher").first()
    assert teacher_seat is not None
    assert teacher.last_active_seat_id == teacher_seat.id
    assert teacher.last_active_class_id == class_row.class_id

    db.session.rollback()
