from app import db
from app.models import ClassEconomy, Seat, User, UserRole
from app.utils.auth_username import build_hashed_username_fields


def test_DOM_CLASS_001__admin_signup_provisions_initial_class(client, monkeypatch):
    monkeypatch.setattr("app.routes.admin.verify_turnstile_token", lambda *_args, **_kwargs: True)
    monkeypatch.setattr("app.routes.admin.pyotp.random_base32", lambda: "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr("app.routes.admin.generate_join_code", lambda: "SIGNUP1")

    class_state = {}

    def fake_create_class_without_user(*, join_code, display_name, section, teacher_first_name, teacher_last_name):
        class_row = type("ClassRow", (), {"class_id": "class-1", "join_code": join_code, "display_name": display_name, "section": section})()
        seat_row = type("SeatRow", (), {"id": 101, "class_id": "class-1"})()
        class_state["class_id"] = class_row.class_id
        class_state["seat_id"] = seat_row.id
        class_state["join_code"] = join_code
        class_state["display_name"] = display_name
        class_state["teacher_first_name"] = teacher_first_name
        class_state["teacher_last_name"] = teacher_last_name
        return class_row, seat_row

    monkeypatch.setattr("app.routes.admin.create_class_without_user", fake_create_class_without_user)
    monkeypatch.setattr("app.routes.admin.create_teacher", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.routes.admin.bind_teacher_to_class", lambda *args, **kwargs: None)

    step1 = client.post(
        "/admin/signup",
        data={
            "signup_step": "class_setup",
            "class_display_name": "Chemistry",
            "section": "Period 1",
            "first_name": "Ms.",
            "last_name": "Ayala",
            "tos_agreed": "true",
            "turnstile_token": "token",
        },
        follow_redirects=False,
    )

    assert step1.status_code == 200
    assert "Set Up Your Authenticator" in step1.get_data(as_text=True)
    assert class_state["join_code"] == "SIGNUP1"
    assert class_state["display_name"] == "Chemistry"

    monkeypatch.setattr("app.routes.admin.pyotp.TOTP.verify", lambda self, code, valid_window=None: code == "123456" and valid_window == 1)
    monkeypatch.setattr("app.routes.admin.create_teacher", lambda username, totp_secret=None: type("Teacher", (), {"id": 7})())
    monkeypatch.setattr("app.routes.admin.bind_teacher_to_class", lambda *args, **kwargs: None)

    step2 = client.post(
        "/admin/signup",
        data={
            "username": "teacher-signup",
            "totp_code": "123456",
            "tos_agreed": "true",
        },
        follow_redirects=False,
    )

    assert step2.status_code in (302, 303)
    assert class_state["class_id"] == "class-1"

    db.session.rollback()


def test_DOM_CLASS_001__admin_signup_totp_verification_uses_windowed_totp_validation(client, monkeypatch):
    monkeypatch.setattr("app.routes.admin.verify_turnstile_token", lambda *_args, **_kwargs: True)
    monkeypatch.setattr("app.routes.admin.pyotp.random_base32", lambda: "JBSWY3DPEHPK3PXP")
    monkeypatch.setattr("app.routes.admin.generate_join_code", lambda: "SIGNUP2")

    captured = {}

    def fake_verify(self, code, valid_window=None):
        captured["code"] = code
        captured["valid_window"] = valid_window
        return True

    monkeypatch.setattr("app.routes.admin.pyotp.TOTP.verify", fake_verify)
    monkeypatch.setattr("app.routes.admin.create_class_without_user", lambda **_kwargs: (type("ClassRow", (), {"class_id": "class-2"})(), type("SeatRow", (), {"id": 202})()))
    monkeypatch.setattr("app.routes.admin.bind_teacher_to_class", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.routes.admin.create_teacher", lambda *args, **kwargs: type("Teacher", (), {"id": 8})())

    initial_post = client.post(
        "/admin/signup",
        data={
            "signup_step": "class_setup",
            "class_display_name": "Physics",
            "section": "Period 2",
            "first_name": "Mr.",
            "last_name": "Nguyen",
            "username": "teacher-windowed",
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
            "username": "teacher-windowed",
            "totp_code": "123456",
            "tos_agreed": "true",
        },
        follow_redirects=False,
    )

    assert final_post.status_code in (302, 303)
    assert captured["code"] == "123456"
    assert captured["valid_window"] == 1
