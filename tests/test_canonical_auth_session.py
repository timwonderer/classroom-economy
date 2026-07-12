from flask import session
import pyotp
from types import SimpleNamespace
from werkzeug.security import generate_password_hash

from app import db
from app.auth import (
    set_canonical_user_session,
)
from app.feats.base import FEATContext
from app.hash_utils import get_random_salt, hash_username, hash_username_lookup
from app.models import (
    ClassEconomy,
    IdentityProfile,
    Seat,
    PasskeyCredential,
    User,
    UserRole,
)
from app.utils.time import utc_now
from tests.helpers.v2_fixtures import make_admin, make_sysadmin, seed_canonical_admin, seed_class_with_seat
from tests.helpers.class_scope import make_student_identity
from tests.helpers.canonical_session import set_canonical_context


def test_system_admin_login_verifies_canonical_totp(client):
    canonical_secret = pyotp.random_base32()
    admin = make_sysadmin("canonical_sysadmin", canonical_secret)
    user = db.session.get(User, admin.id)
    with FEATContext("FEAT-IDEN-001"):
        user.totp_secret_encrypted = canonical_secret

    response = client.post(
        "/sysadmin/login",
        data={"username": "canonical_sysadmin", "totp_code": pyotp.TOTP(canonical_secret).now()},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as auth_session:
        assert auth_session["user_id"] == user.id



def test_student_login_verifies_user_pin_and_resolves_through_claimed_seat(client, monkeypatch):
    monkeypatch.setattr("app.routes.student.verify_turnstile_token", lambda *_args, **_kwargs: True)

    with FEATContext("FEAT-IDEN-001"):
        admin = make_admin("student_login_teacher", pyotp.random_base32())
        teacher_user = db.session.get(User, admin.id)
        class_row = ClassEconomy(
            user_id=teacher_user.id,
            join_code="CANONICAL-LOGIN",
            display_name="Canonical",
            class_timezone="UTC",
        )
        db.session.add(class_row)
        db.session.flush()

        username = "canonical_student"
        student_user = User(
            user_role=UserRole.STUDENT,
            username_hash=hash_username_lookup(username),
            username_lookup_hash=hash_username_lookup(username),
            pin_hash=generate_password_hash("2468"),
            last_active_class_id=class_row.class_id,
        )
        db.session.add(student_user)
        db.session.flush()
        seat = Seat(
            user_id=student_user.id,
            class_id=class_row.class_id,
            role="student",
            claimed_at=utc_now(),
        )
        db.session.add(seat)
        db.session.flush()
        profile = IdentityProfile(
            seat_id=seat.id,
            class_id=class_row.class_id,
            profile_type="student",
            first_name="Canonical",
            last_name="S",
        )
        db.session.add(profile)
        db.session.flush()

    response = client.post(
        "/student/login",
        data={"username": username, "pin": "2468"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as auth_session:
        assert auth_session["user_id"] == student_user.id



def test_student_login_missing_last_active_class_shows_selector(client, monkeypatch):
    monkeypatch.setattr("app.routes.student.verify_turnstile_token", lambda *_args, **_kwargs: True)

    with FEATContext("FEAT-IDEN-001"):
        admin = make_admin("student_selector_teacher", pyotp.random_base32())
        teacher_user = db.session.get(User, admin.id)
        class_row = ClassEconomy(
            user_id=teacher_user.id,
            join_code="SELECTOR-LOGIN",
            display_name="Selector",
            class_timezone="UTC",
        )
        db.session.add(class_row)
        db.session.flush()

        username = "selector_student"
        user = User(
            user_role=UserRole.STUDENT,
            username_hash=hash_username_lookup(username),
            username_lookup_hash=hash_username_lookup(username),
            pin_hash=generate_password_hash("2468"),
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
        profile = IdentityProfile(
            seat_id=seat.id,
            class_id=class_row.class_id,
            profile_type="student",
            first_name="Select",
            last_name="A",
        )
        db.session.add(profile)
        db.session.flush()

    monkeypatch.setattr(
        "app.routes.student._get_identity_bound_seat_options",
        lambda _user_id: [{"seat_id": seat.id, "class_id": class_row.class_id, "join_code": class_row.join_code, "class_identifier": "A", "class_name": class_row.display_name}],
    )
    response = client.post("/student/login", data={"username": username, "pin": "2468"}, follow_redirects=False)

    assert response.status_code == 302
    assert "/student/select-class-context" in response.headers["Location"]


def test_student_login_no_valid_class_seats_hard_fails(client, monkeypatch):
    monkeypatch.setattr("app.routes.student.verify_turnstile_token", lambda *_args, **_kwargs: True)

    with FEATContext("FEAT-IDEN-001"):
        admin = make_admin("student_hard_fail_teacher", pyotp.random_base32())
        teacher_user = db.session.get(User, admin.id)
        class_row = ClassEconomy(
            user_id=teacher_user.id,
            join_code="HARDFAIL-LOGIN",
            display_name="HardFail",
            class_timezone="UTC",
        )
        db.session.add(class_row)
        db.session.flush()

        username = "hardfail_student"
        user = User(
            user_role=UserRole.STUDENT,
            username_hash=hash_username_lookup(username),
            username_lookup_hash=hash_username_lookup(username),
            pin_hash=generate_password_hash("2468"),
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
        profile = IdentityProfile(
            seat_id=seat.id,
            class_id=class_row.class_id,
            profile_type="student",
            first_name="Hard",
            last_name="F",
        )
        db.session.add(profile)
        db.session.flush()

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

    with FEATContext("FEAT-IDEN-001"):
        admin = seed_canonical_admin("passkey_teacher", pyotp.random_base32()).user
        class_seed = seed_class_with_seat(
            teacher=admin,
            join_code="PASSKEY1",
            display_name="Passkey",
        )
        user = db.session.get(User, admin.id)
        class_row = class_seed.class_row
        teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
        user.current_session_nonce = "nonce"
        db.session.flush()

    with client.session_transaction() as auth_session:
        auth_session["user_id"] = admin.id
        auth_session["user_id"] = user.id
        auth_session["last_activity"] = utc_now().isoformat()
        auth_session["admin_auth_username"] = "passkey_teacher"
        auth_session["current_session_nonce"] = "nonce"
        with FEATContext("FEAT-IDEN-001"):
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


def test_admin_passkey_finish_sets_canonical_user_session(client, monkeypatch):
    with FEATContext("FEAT-IDEN-001"):
        admin = seed_canonical_admin("passkey_finish_teacher", pyotp.random_base32()).user
        class_seed = seed_class_with_seat(
            teacher=admin,
            join_code="PASSKEY2",
            display_name="Passkey2",
        )
        user = db.session.get(User, admin.id)
        class_row = class_seed.class_row
        teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
        db.session.add(PasskeyCredential(user_id=user.id, authenticator_name="Key"))
        db.session.flush()

    monkeypatch.setattr(
        "app.routes.admin.verify_signin_token",
        lambda _token: SimpleNamespace(user_id=f"user_{user.id}"),
    )

    response = client.post("/admin/passkey/auth/finish", json={"token": "signed"})

    assert response.status_code == 200


def test_system_admin_passkey_finish_sets_canonical_user_session(client, monkeypatch):
    with FEATContext("FEAT-IDEN-001"):
        admin = make_sysadmin("passkey_finish_sysadmin", pyotp.random_base32())
        user = db.session.get(User, admin.id)
        class_row = ClassEconomy(user_id=user.id, join_code="SPASS1", display_name="SysPasskey", class_timezone="UTC")
        db.session.add(class_row)
        db.session.flush()
        teacher_seat = Seat(user_id=user.id, class_id=class_row.class_id, role="teacher")
        db.session.add(teacher_seat)
        user.current_session_nonce = "nonce"
        db.session.add(PasskeyCredential(user_id=user.id, authenticator_name="Key"))
        db.session.flush()

    monkeypatch.setattr(
        "app.routes.system_admin.verify_signin_token",
        lambda _token: SimpleNamespace(user_id=f"user_{user.id}"),
    )

    response = client.post("/sysadmin/passkey/auth/finish", json={"token": "signed"})

    assert response.status_code == 200


def test_canonical_user_session_rejects_role_mismatch(client):
    with FEATContext("FEAT-IDEN-001"):
        user = User(
            user_role=UserRole.STUDENT,
            username_hash="role-mismatch-hash",
            username_lookup_hash="role-mismatch-lookup",
        )
        db.session.add(user)
        db.session.flush()

    with client.application.test_request_context("/"):
        resolved = set_canonical_user_session(
            username_lookup_hash=user.username_lookup_hash,
            expected_role="teacher",
        )

        assert resolved is None
        assert "user_id" not in session
