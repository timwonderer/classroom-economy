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
from tests.helpers.class_scope import create_class_scope
from tests.helpers.v2_fixtures import make_sysadmin, seed_canonical_admin
from tests.helpers.canonical_session import set_canonical_context


def _seed_claimed_student_for_class(*, class_id: str, username: str, first_name: str, last_name: str, pin: str = "2468"):
    """Create a student through claim semantics: unclaimed seat first, then bind user."""
    with FEATContext("FEAT-IDEN-001"):
        seat = Seat(
            class_id=class_id,
            role="student",
            claim_first_name_hash=hash_username_lookup(first_name.lower()),
            claim_last_name_hash=hash_username_lookup(last_name.lower()),
        )
        db.session.add(seat)
        db.session.flush()

        profile = IdentityProfile(
            seat_id=seat.id,
            class_id=class_id,
            profile_type="student_unclaimed",
            first_name=first_name,
            last_name=last_name,
        )
        db.session.add(profile)
        db.session.flush()

        salt = get_random_salt()
        user = User(
            user_role=UserRole.STUDENT,
            username_hash=hash_username(username, salt),
            username_lookup_hash=hash_username_lookup(username),
            pin_hash=generate_password_hash(pin),
        )
        db.session.add(user)
        db.session.flush()

        seat.user_id = user.id
        seat.claimed_at = utc_now()
        profile.profile_type = "student_claimed"
        user.last_active_class_id = class_id
        user.last_active_seat_id = seat.id
        db.session.flush()

    return user, seat

 
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
        teacher = seed_canonical_admin("student_login_teacher", pyotp.random_base32()).user
        class_row = create_class_scope(
            teacher_user=teacher,
            join_code="CANONICAL-LOGIN",
            display_name="Canonical",
        )

        username = "canonical_student"
        student_user, _seat = _seed_claimed_student_for_class(
            class_id=class_row.class_id,
            username=username,
            first_name="Canonical",
            last_name="S",
        )

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
        teacher = seed_canonical_admin("student_selector_teacher", pyotp.random_base32()).user
        class_row = create_class_scope(
            teacher_user=teacher,
            join_code="SELECTOR-LOGIN",
            display_name="Selector",
        )

        username = "selector_student"
        user, seat = _seed_claimed_student_for_class(
            class_id=class_row.class_id,
            username=username,
            first_name="Select",
            last_name="A",
        )
        user.last_active_class_id = None
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
        teacher = seed_canonical_admin("student_hard_fail_teacher", pyotp.random_base32()).user
        class_row = create_class_scope(
            teacher_user=teacher,
            join_code="HARDFAIL-LOGIN",
            display_name="HardFail",
        )

        username = "hardfail_student"
        user, seat = _seed_claimed_student_for_class(
            class_id=class_row.class_id,
            username=username,
            first_name="Hard",
            last_name="F",
        )
        user.last_active_class_id = None
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
        class_row = create_class_scope(
            teacher_user=admin,
            join_code="PASSKEY1",
            display_name="Passkey",
        )
        user = db.session.get(User, admin.id)
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
        class_row = create_class_scope(
            teacher_user=admin,
            join_code="PASSKEY2",
            display_name="Passkey2",
        )
        user = db.session.get(User, admin.id)
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
