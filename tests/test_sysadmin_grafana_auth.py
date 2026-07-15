from datetime import timedelta

from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin
import pyotp

from app import db
from app.feats.base import FEATContext
from app.auth import SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES
from app.models import SystemAdmin, User, UserRole
from app.utils.encryption import encrypt_totp
from app.utils.time import utc_now


def _create_sysadmin(username: str = "grafana_sysadmin"):
    secret = pyotp.random_base32()
    sysadmin = make_sysadmin(username, encrypt_totp(secret))
    return sysadmin, secret


def _login_sysadmin_session(client, *, user_id: int, username: str = "grafana_sysadmin", minutes_ago: int = 0):
    nonce = f"nonce-{username}"
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"sysadmin:grafana_login:{user_id}:{username}:{minutes_ago}"):
        user = db.session.get(User, user_id)
        if user is not None:
            user.current_session_nonce = nonce
            db.session.flush()
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["user_id"] = user_id
        sess["sysadmin_auth_username"] = username
        sess["current_session_nonce"] = nonce
        sess["last_activity"] = (utc_now() - timedelta(minutes=minutes_ago)).isoformat()


def test_sysadmin_login_get_requests_do_not_trip_rate_limit(client):
    for _ in range(12):
        response = client.get("/sysadmin/login")
        assert response.status_code == 200


def test_grafana_auth_check_uses_longer_sysadmin_timeout(client):
    sysadmin, _ = _create_sysadmin("grafana_timeout")
    _login_sysadmin_session(
        client,
        user_id=sysadmin.id,
        username="grafana_timeout",
        minutes_ago=SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES - 5,
    )

    response = client.get("/sysadmin/grafana/auth-check")

    assert response.status_code == 200
    assert response.headers["X-Auth-User"] == "grafana_timeout"


def test_expired_grafana_subrequest_returns_401_instead_of_login_redirect(client):
    sysadmin, _ = _create_sysadmin("grafana_expired")
    _login_sysadmin_session(
        client,
        user_id=sysadmin.id,
        username="grafana_expired",
        minutes_ago=SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES + 1,
    )

    response = client.get("/sysadmin/grafana/public/build/app.js")

    assert response.status_code == 401
    assert "/sysadmin/login" not in (response.headers.get("Location") or "")


def test_expired_sysadmin_dashboard_still_redirects_to_login(client):
    sysadmin, _ = _create_sysadmin("dashboard_expired")
    _login_sysadmin_session(
        client,
        user_id=sysadmin.id,
        username="dashboard_expired",
        minutes_ago=SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES + 1,
    )

    response = client.get("/sysadmin/dashboard")

    assert response.status_code == 302
    assert "/sysadmin/login" in response.headers["Location"]




def test_sysadmin_auth_check_rejects_non_sysadmin_user(client):
    _create_sysadmin("auth_check_match")
    teacher = seed_canonical_admin("auth_check_teacher", pyotp.random_base32()).user
    with FEATContext("FEAT-IDEN-001", idempotency_key="sysadmin:auth_check_teacher_nonce"):
        teacher.current_session_nonce = "nonce-auth_check_teacher"
        db.session.flush()

    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["user_id"] = teacher.id
        sess["sysadmin_auth_username"] = "auth_check_teacher"
        sess["current_session_nonce"] = teacher.current_session_nonce
        sess["last_activity"] = utc_now().isoformat()

    response = client.get("/sysadmin/auth-check")

    assert response.status_code == 401


def test_grafana_auth_check_rejects_missing_canonical_user(client):
    sysadmin, _ = _create_sysadmin("grafana_missing_user")
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["current_session_nonce"] = "nonce-grafana_missing_user"
        sess["last_activity"] = utc_now().isoformat()

    response = client.get("/sysadmin/grafana/auth-check")

    assert response.status_code == 401
