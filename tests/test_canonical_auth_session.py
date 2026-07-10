from flask import session
import pyotp
from types import SimpleNamespace
from werkzeug.security import generate_password_hash

from app import db
from app.auth import (
    get_current_user,
    set_canonical_user_session,
)
from app.hash_utils import get_random_salt, hash_username, hash_username_lookup
from app.models import (
    AdminCredential,
    ClassEconomy,
    IdentityProfile,
    Seat,
    SystemAdminCredential,
    User,
    UserRole,
)
from app.utils.time import utc_now
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import make_student_identity
from tests.helpers.canonical_session import set_canonical_context


def test_migrated_teacher_login_sets_canonical_user_id(client):
    secret = pyotp.random_base32()
    admin = make_admin("canonical_teacher", secret)
    user = db.session.get(User, admin.id)
    user.current_session_nonce = "nonce"
    db.session.commit()

    response = client.post(
        "/admin/login",
        data={"username": "canonical_teacher", "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as auth_session:

        assert auth_session["user_id"] == user.id


def test_teacher_login_rejects_legacy_only_principal(client):
    secret = pyotp.random_base32()
    salt = get_random_salt()
    username_hash = hash_username("legacy_only_teacher", salt)
    username_lookup_hash = hash_username_lookup("legacy_only_teacher")
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=username_hash,
        username_lookup_hash=username_lookup_hash,
    )
    db.session.add(user)
    db.session.commit()

    response = client.post(
        "/admin/login",
        data={"username": "legacy_only_teacher", "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as auth_session:
        assert "is_admin" not in auth_session

        assert "user_id" not in auth_session


def test_teacher_login_verifies_canonical_totp_not_shadow_totp(client):
    shadow_secret = pyotp.random_base32()
    canonical_secret = pyotp.random_base32()
    admin = make_admin("canonical_totp_teacher", shadow_secret)
    user = db.session.get(User, admin.id)
    user.totp_secret_encrypted = canonical_secret
    db.session.commit()

    rejected = client.post(
        "/admin/login",
        data={"username": "canonical_totp_teacher", "totp_code": pyotp.TOTP(shadow_secret).now()},
        follow_redirects=False,
    )
    assert rejected.status_code == 302
    with client.session_transaction() as auth_session:
        assert "user_id" not in auth_session

    accepted = client.post(
        "/admin/login",
        data={"username": "canonical_totp_teacher", "totp_code": pyotp.TOTP(canonical_secret).now()},
        follow_redirects=False,
    )
    assert accepted.status_code == 302
    with client.session_transaction() as auth_session:
        assert auth_session["user_id"] == user.id



def test_system_admin_login_verifies_canonical_totp(client):
    shadow_secret = pyotp.random_base32()
    canonical_secret = pyotp.random_base32()
    admin = make_sysadmin("canonical_sysadmin", shadow_secret)
    user = db.session.get(User, admin.id)
    user.totp_secret_encrypted = canonical_secret
    db.session.commit()

    response = client.post(
        "/sysadmin/login",
        data={"username": "canonical_sysadmin", "totp_code": pyotp.TOTP(canonical_secret).now()},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as auth_session:
        assert auth_session["user_id"] == user.id



def test_student_login_verifies_user_pin_and_resolves_shadow_through_claimed_seat(client, monkeypatch):
    monkeypatch.setattr("app.routes.student.verify_turnstile_token", lambda *_args, **_kwargs: True)

    admin = make_admin("student_login_teacher", pyotp.random_base32())
    db.session.flush()
    teacher_user = db.session.get(User, admin.id)
    class_row = ClassEconomy(
        user_id=teacher_user.id,
        join_code="CANONICAL-LOGIN",
        display_name="Canonical",
        class_timezone="UTC",
    )
    profile = IdentityProfile(profile_type="student", first_name="Canonical", last_name="S")
    db.session.add_all([class_row, profile])
    db.session.flush()

    username = "canonical_student"
    student = make_student_identity(class_id=class_row.class_id, first_name="Canonical", last_name="S")
    user = User(
        user_role=UserRole.STUDENT,
        username_hash=hash_username_lookup(username),
        username_lookup_hash=hash_username_lookup(username),
        pin_hash=generate_password_hash("2468"),
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

    response = client.post(
        "/student/login",
        data={"username": username, "pin": "2468"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as auth_session:
        assert auth_session["user_id"] == user.id



def test_student_login_missing_last_active_class_shows_selector(client, monkeypatch):
    monkeypatch.setattr("app.routes.student.verify_turnstile_token", lambda *_args, **_kwargs: True)

    admin = make_admin("student_selector_teacher", pyotp.random_base32())
    db.session.flush()
    teacher_user = db.session.get(User, admin.id)
    class_row = ClassEconomy(
        user_id=teacher_user.id,
        join_code="SELECTOR-LOGIN",
        display_name="Selector",
        class_timezone="UTC",
    )
    profile = IdentityProfile(profile_type="student", first_name="Select", last_name="A")
    db.session.add_all([class_row, profile])
    db.session.flush()

    username = "selector_student"
    student = make_student_identity(class_id=class_row.class_id, first_name="Select", last_name="A")
    user = User(
        user_role=UserRole.STUDENT,
        username_hash=hash_username_lookup(username),
        username_lookup_hash=hash_username_lookup(username),
        pin_hash=generate_password_hash("2468"),
        has_completed_setup=True,
        last_active_class_id=None,
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

    monkeypatch.setattr(
        "app.routes.student._get_identity_bound_seat_options",
        lambda _user_id: [{"seat_id": seat.id, "class_id": class_row.class_id, "join_code": class_row.join_code, "class_identifier": "A", "class_name": class_row.display_name}],
    )
    response = client.post("/student/login", data={"username": username, "pin": "2468"}, follow_redirects=False)

    assert response.status_code == 302
    assert "/student/select-class-context" in response.headers["Location"]


def test_student_login_no_valid_class_seats_hard_fails(client, monkeypatch):
    monkeypatch.setattr("app.routes.student.verify_turnstile_token", lambda *_args, **_kwargs: True)

    admin = make_admin("student_hard_fail_teacher", pyotp.random_base32())
    db.session.flush()
    teacher_user = db.session.get(User, admin.id)
    class_row = ClassEconomy(
        user_id=teacher_user.id,
        join_code="HARDFAIL-LOGIN",
        display_name="HardFail",
        class_timezone="UTC",
    )
    profile = IdentityProfile(profile_type="student", first_name="Hard", last_name="F")
    db.session.add_all([class_row, profile])
    db.session.flush()

    username = "hardfail_student"
    student = make_student_identity(class_id=class_row.class_id, first_name="Hard", last_name="F")
    user = User(
        user_role=UserRole.STUDENT,
        username_hash=hash_username_lookup(username),
        username_lookup_hash=hash_username_lookup(username),
        pin_hash=generate_password_hash("2468"),
        has_completed_setup=True,
        last_active_class_id=None,
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

    monkeypatch.setattr("app.routes.student._get_identity_bound_seat_options", lambda _user_id: [])

    response = client.post("/student/login", data={"username": username, "pin": "2468"}, follow_redirects=False)

    assert response.status_code == 302
    assert "/student/login" in response.headers["Location"]
    with client.session_transaction() as auth_session:
        assert "user_id" not in auth_session


def test_admin_passkey_register_uses_canonical_user_external_id(client, monkeypatch):
    captured = {}

    def fake_create_register_token(user_id, username, displayname):
        captured.update(user_id=user_id, username=username, displayname=displayname)
        return "register-token"

    monkeypatch.setattr("app.routes.admin.create_register_token", fake_create_register_token)
    monkeypatch.setattr("app.routes.admin.get_public_api_key", lambda: "public-key")

    admin = make_admin("passkey_teacher", pyotp.random_base32())
    user = db.session.get(User, admin.id)
    class_row = ClassEconomy(user_id=user.id, join_code="PASSKEY1", display_name="Passkey", class_timezone="UTC")
    db.session.add(class_row)
    db.session.flush()
    teacher_seat = Seat(user_id=user.id, class_id=class_row.class_id, role="teacher")
    db.session.add(teacher_seat)
    user.current_session_nonce = "nonce"
    db.session.commit()

    with client.session_transaction() as auth_session:
        auth_session["is_admin"] = True
        auth_session["admin_id"] = admin.id
        auth_session["user_id"] = user.id
        auth_session["last_activity"] = utc_now().isoformat()
        auth_session["admin_auth_username"] = "passkey_teacher"
        auth_session["current_session_nonce"] = "nonce"
        set_canonical_context(
            auth_session,
            user_id=user.id,
            class_id=class_row.class_id,
            seat_id=teacher_seat.id,
            role="teacher",
        )

    response = client.post("/admin/passkey/register/start", json={})

    assert response.status_code == 200, f"Expected 200 but got {response.status_code}. Redirecting to: {response.location if response.status_code == 302 else 'N/A'}"
    assert response.get_json()["token"] == "register-token"
    assert captured["user_id"] == f"user_{user.id}"


def test_admin_passkey_finish_rejects_legacy_external_principal(client, monkeypatch):
    monkeypatch.setattr(
        "app.routes.admin.verify_signin_token",
        lambda _token: SimpleNamespace(user_id="admin_123"),
    )

    response = client.post("/admin/passkey/auth/finish", json={"token": "signed"})

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid user ID"


def test_admin_passkey_finish_sets_canonical_user_session(client, monkeypatch):
    admin = make_admin("passkey_finish_teacher", pyotp.random_base32())
    user = db.session.get(User, admin.id)
    class_row = ClassEconomy(user_id=user.id, join_code="PASSKEY2", display_name="Passkey2", class_timezone="UTC")
    db.session.add(class_row)
    db.session.flush()
    teacher_seat = Seat(user_id=user.id, class_id=class_row.class_id, role="teacher")
    db.session.add(teacher_seat)
    db.session.add(AdminCredential(user_id=user.id, authenticator_name="Key"))
    db.session.commit()

    monkeypatch.setattr(
        "app.routes.admin.verify_signin_token",
        lambda _token: SimpleNamespace(user_id=f"user_{user.id}"),
    )

    response = client.post("/admin/passkey/auth/finish", json={"token": "signed"})

    assert response.status_code == 200


def test_system_admin_passkey_finish_sets_canonical_user_session(client, monkeypatch):
    admin = make_sysadmin("passkey_finish_sysadmin", pyotp.random_base32())
    user = db.session.get(User, admin.id)
    class_row = ClassEconomy(user_id=user.id, join_code="SPASS1", display_name="SysPasskey", class_timezone="UTC")
    db.session.add(class_row)
    db.session.flush()
    teacher_seat = Seat(user_id=user.id, class_id=class_row.class_id, role="teacher")
    db.session.add(teacher_seat)
    user.current_session_nonce = "nonce"
    db.session.add(SystemAdminCredential(user_id=user.id, authenticator_name="Key"))
    db.session.commit()

    monkeypatch.setattr(
        "app.routes.system_admin.verify_signin_token",
        lambda _token: SimpleNamespace(user_id=f"user_{user.id}"),
    )

    response = client.post("/sysadmin/passkey/auth/finish", json={"token": "signed"})

    assert response.status_code == 200


def test_get_current_user_ignores_deprecated_user_session_aliases(client):
    user = User(
        user_role=UserRole.STUDENT,
        username_hash="canonical-user-hash",
        username_lookup_hash="canonical-user-lookup",
    )
    db.session.add(user)
    db.session.commit()

    with client.application.test_request_context("/"):
        session["student_user_id"] = user.id
        session["current_user_id"] = user.id
        assert get_current_user() is None

        session["user_id"] = user.id
        assert get_current_user().id == user.id





def test_canonical_user_session_rejects_role_mismatch(client):
    user = User(
        user_role=UserRole.STUDENT,
        username_hash="role-mismatch-hash",
        username_lookup_hash="role-mismatch-lookup",
    )
    db.session.add(user)
    db.session.commit()

    with client.application.test_request_context("/"):
        resolved = set_canonical_user_session(
            username_lookup_hash=user.username_lookup_hash,
            expected_role="teacher",
        )

        assert resolved is None
        assert "user_id" not in session
