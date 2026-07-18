from app.auth import SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES
from app import app, db
from app.feats.base import FEATContext
from app.hash_utils import hash_username_lookup
from app.models import User
from app.utils.time import utc_now
from tests.helpers.classroom_initializer import initialize
from tests.helpers.operation_routes import (
    get_sysadmin_auth_check,
    get_sysadmin_dashboard,
    get_sysadmin_grafana_auth_check,
    seed_sysadmin_session,
)
from wsgi import app as cli_app


def _create_sysadmin_via_cli(username: str):
    result = cli_app.test_cli_runner().invoke(args=["create-sysadmin"], input=f"{username}\n")
    assert result.exit_code == 0, result.output
    user = User.query.filter_by(username_lookup_hash=hash_username_lookup(username)).first()
    assert user is not None, "create-sysadmin did not create a sysadmin user"
    secret = ""
    lines = result.output.splitlines()
    for idx, line in enumerate(lines):
        if "TOTP SECRET" in line:
            for candidate in lines[idx + 1 :]:
                stripped = candidate.strip()
                if stripped and not stripped.startswith("=") and "IMPORTANT:" not in stripped and "Manual entry URI" not in stripped:
                    secret = stripped
                    break
            break
    assert secret, result.output
    return user, secret


def test_DOM_OPS_001__sysadmin_login_get_requests_do_not_trip_rate_limit(client):
    for _ in range(12):
        response = client.get("/sysadmin/login")
        assert response.status_code == 200


def test_DOM_OPS_001__grafana_auth_check_uses_longer_sysadmin_timeout(client):
    sysadmin, _ = _create_sysadmin_via_cli("grafana_timeout")
    seed_sysadmin_session(
        client,
        user_id=sysadmin.id,
        username="grafana_timeout",
        minutes_ago=SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES - 5,
    )

    response = get_sysadmin_grafana_auth_check(client)

    assert response.status_code == 200
    assert response.headers["X-Auth-User"] == "grafana_timeout"


def test_DOM_OPS_001__expired_grafana_subrequest_returns_401_instead_of_login_redirect(client):
    sysadmin, _ = _create_sysadmin_via_cli("grafana_expired")
    seed_sysadmin_session(
        client,
        user_id=sysadmin.id,
        username="grafana_expired",
        minutes_ago=SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES + 1,
    )

    response = client.get("/sysadmin/grafana/public/build/app.js")

    assert response.status_code == 401
    assert "/sysadmin/login" not in (response.headers.get("Location") or "")


def test_DOM_OPS_001__expired_sysadmin_dashboard_still_redirects_to_login(client):
    sysadmin, _ = _create_sysadmin_via_cli("dashboard_expired")
    seed_sysadmin_session(
        client,
        user_id=sysadmin.id,
        username="dashboard_expired",
        minutes_ago=SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES + 1,
    )

    response = get_sysadmin_dashboard(client)

    assert response.status_code == 302
    assert "/sysadmin/login" in response.headers["Location"]




def test_DOM_OPS_001__sysadmin_auth_check_rejects_non_sysadmin_user(client):
    _create_sysadmin_via_cli("auth_check_match")
    classroom = initialize("chemistry_p1", app)
    teacher = classroom.teacher_user
    with FEATContext("FEAT-IDEN-001", idempotency_key="sysadmin:auth_check_teacher_nonce"):
        teacher.current_session_nonce = "nonce-auth_check_teacher"
        db.session.flush()

    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["user_id"] = teacher.id
        sess["sysadmin_auth_username"] = "auth_check_teacher"
        sess["current_session_nonce"] = teacher.current_session_nonce
        sess["last_activity"] = utc_now().isoformat()

    response = get_sysadmin_auth_check(client)

    assert response.status_code == 401


def test_DOM_OPS_001__grafana_auth_check_rejects_missing_canonical_user(client):
    _create_sysadmin_via_cli("grafana_missing_user")
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["current_session_nonce"] = "nonce-grafana_missing_user"
        sess["last_activity"] = utc_now().isoformat()

    response = get_sysadmin_grafana_auth_check(client)

    assert response.status_code == 401
