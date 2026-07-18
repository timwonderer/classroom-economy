"""Canonical Operation-domain test helpers.

These helpers stay close to the production routes they exercise.
Each helper does one thing only and keeps the setup surface narrow.
"""

from __future__ import annotations

from datetime import timedelta

import pyotp

from app import db
from app.feats.base import FEATContext
from app.models import User
from app.utils.time import utc_now


def login_sysadmin(client, *, username: str, totp_secret: str):
    """Authenticate a sysadmin through the production login route."""
    return client.post(
        "/sysadmin/login",
        data={"username": username, "totp_code": pyotp.TOTP(totp_secret).now()},
        follow_redirects=True,
    )


def seed_sysadmin_session(
    client,
    *,
    user_id: int,
    username: str,
    minutes_ago: int = 0,
) -> None:
    """Establish a sysadmin session for route-level auth tests."""
    nonce = f"nonce-{username}"
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"operation:seed_sysadmin_session:{user_id}:{username}:{minutes_ago}"):
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


def get_sysadmin_auth_check(client):
    """Fetch the sysadmin auth-check route."""
    return client.get("/sysadmin/auth-check")


def get_sysadmin_grafana_auth_check(client):
    """Fetch the Grafana auth-check route."""
    return client.get("/sysadmin/grafana/auth-check")


def get_sysadmin_dashboard(client):
    """Fetch the sysadmin dashboard route."""
    return client.get("/sysadmin/dashboard")


def get_sysadmin_admins(client):
    """Fetch the sysadmin admins page."""
    return client.get("/sysadmin/admins")


def post_sysadmin_reset_totp(client, user_id: int):
    """Invoke the sysadmin reset-TOTP route."""
    return client.post(f"/sysadmin/admins/{user_id}/reset-totp")


def set_maintenance_global_bypass(client) -> None:
    """Mark the session as having maintenance bypass."""
    with client.session_transaction() as sess:
        sess["is_system_admin"] = True
        sess["maintenance_global_bypass"] = True
