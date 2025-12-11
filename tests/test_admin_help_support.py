import pyotp

from app import db
from app.models import Admin


def _login_admin(client):
    secret = pyotp.random_base32()
    admin = Admin(username="teacher_help", totp_secret=secret)
    db.session.add(admin)
    db.session.commit()

    response = client.post(
        "/admin/login",
        data={"username": admin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_help_support_page_renders(client):
    _login_admin(client)

    response = client.get("/admin/help-support")

    assert response.status_code == 200
    assert b"Help & Support" in response.data
    assert b"Knowledge Base" in response.data
