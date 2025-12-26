import pyotp
from datetime import datetime, timedelta, timezone

from app import db
from app.models import SystemAdmin


def _create_sysadmin(username: str = "sysadmin") -> tuple[SystemAdmin, str]:
    secret = pyotp.random_base32()
    sysadmin = SystemAdmin(username=username, totp_secret=secret)
    db.session.add(sysadmin)
    db.session.commit()
    return sysadmin, secret


def test_auth_check_returns_identity_header(client):
    sysadmin, _ = _create_sysadmin()
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["sysadmin_id"] = sysadmin.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    resp = client.get("/sysadmin/auth-check")

    assert resp.status_code == 204
    assert resp.headers.get("X-Auth-User") == sysadmin.username


def test_auth_check_expires_stale_session(client):
    sysadmin, _ = _create_sysadmin()
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["sysadmin_id"] = sysadmin.id
        sess["last_activity"] = stale_time.isoformat()

    resp = client.get("/sysadmin/auth-check")

    assert resp.status_code == 401
    with client.session_transaction() as sess:
        assert "is_system_admin" not in sess
        assert "sysadmin_id" not in sess
        assert "last_activity" not in sess


def test_grafana_auth_check_returns_identity(client):
    sysadmin, _ = _create_sysadmin("grafana-admin")
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["sysadmin_id"] = sysadmin.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    resp = client.get("/sysadmin/grafana/auth-check")

    assert resp.status_code == 200
    assert resp.headers.get("X-Auth-User") == sysadmin.username
