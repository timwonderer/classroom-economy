import pyotp
from datetime import datetime, timezone

from app import db
from app.models import Admin
from app.auth import get_current_admin


def test_admin_login_sets_session_identity(client):
    secret = pyotp.random_base32()
    admin = Admin(username="teacher1", totp_secret=secret)
    db.session.add(admin)
    db.session.commit()

    response = client.post(
        "/admin/login",
        data={"username": admin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("is_admin") is True
        assert sess.get("admin_id") == admin.id
        assert "last_activity" in sess

    with client.application.test_request_context('/'):
        from flask import session

        session["is_admin"] = True
        session["admin_id"] = admin.id
        assert get_current_admin().id == admin.id


def test_admin_required_blocks_missing_identity(client):
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()

    response = client.get("/admin/students", follow_redirects=False)

    assert response.status_code == 302
    assert "/admin/login" in response.headers.get("Location", "")
