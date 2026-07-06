from __future__ import annotations

from datetime import timedelta

from app.extensions import db
from app.models import User, UserRole
from app.services.admin_identity_service import (
    admin_has_passkeys,
    count_active_admin_invite_codes,
    create_admin_credential,
    create_admin_invite_code,
    delete_admin_credential,
    delete_admin_credentials_for_user,
    delete_admin_onboarding_for_user,
    get_admin_credential,
    get_admin_invite_code_by_code,
    get_admin_invite_code_by_id,
    get_admin_onboarding,
    get_or_create_admin_onboarding,
    list_admin_invite_codes,
    mark_admin_invite_code_used,
    list_admin_credentials,
    set_admin_onboarding_skipped,
    set_admin_onboarding_widget_dismissed,
    set_admin_onboarding_widget_task_status,
    touch_admin_credentials_last_used,
)
from app.utils.time import utc_now
from tests.helpers.v2_fixtures import make_admin


def _seed_teacher():
    teacher = make_admin("admin-identity-bridge", "test-secret")
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=teacher.username_hash,
        username_lookup_hash=teacher.username_lookup_hash,
        totp_secret_encrypted=teacher.totp_secret,
    )
    db.session.add_all([teacher, user])
    db.session.flush()
    return teacher, user


def test_onboarding_bridge_create_and_updates(client):
    teacher, _user = _seed_teacher()
    now = utc_now()

    assert get_admin_onboarding(teacher.id) is None

    created = get_or_create_admin_onboarding(teacher.id, now)
    assert created.user_id == teacher.id
    assert created.is_completed is False
    assert created.is_skipped is False
    assert created.steps_completed == {}
    assert created.widget_tasks_completed == {}

    set_admin_onboarding_widget_task_status(teacher.id, "store", "skipped", utc_now())
    set_admin_onboarding_widget_dismissed(teacher.id, dismissed=True, now=utc_now())
    set_admin_onboarding_widget_dismissed(teacher.id, dismissed=False, now=utc_now())
    set_admin_onboarding_skipped(teacher.id, utc_now())
    db.session.commit()

    refreshed = get_admin_onboarding(teacher.id)
    assert refreshed is not None
    assert refreshed.widget_tasks_completed.get("store") == "skipped"
    assert refreshed.widget_dismissed is False
    assert refreshed.widget_dismissed_at is None
    assert refreshed.is_skipped is True


def test_admin_credential_bridge_lifecycle(client):
    teacher, user = _seed_teacher()
    assert admin_has_passkeys(teacher.id) is False

    created = create_admin_credential(teacher.id, authenticator_name="My Passkey")
    db.session.flush()

    assert created.user_id == teacher.id
    assert admin_has_passkeys(teacher.id) is True

    listed = list_admin_credentials(teacher.id)
    assert len(listed) == 1
    assert listed[0].id == created.id
    assert listed[0].authenticator_name == "My Passkey"

    fetched = get_admin_credential(created.id, teacher.id)
    assert fetched is not None
    assert fetched.id == created.id

    touched = touch_admin_credentials_last_used(teacher.id, utc_now())
    assert touched == 1

    deleted = delete_admin_credential(created.id, teacher.id)
    assert deleted is True
    db.session.flush()
    assert admin_has_passkeys(teacher.id) is False


def test_admin_identity_bridge_bulk_deletes(client):
    teacher, _user = _seed_teacher()
    now = utc_now()
    get_or_create_admin_onboarding(teacher.id, now)
    create_admin_credential(teacher.id, authenticator_name="Key 1")
    create_admin_credential(teacher.id, authenticator_name="Key 2")
    db.session.flush()

    delete_admin_credentials_for_user(teacher.id)
    delete_admin_onboarding_for_user(teacher.id)
    db.session.commit()

    assert admin_has_passkeys(teacher.id) is False
    assert get_admin_onboarding(teacher.id) is None


def test_admin_invite_code_bridge_lifecycle(client):
    assert count_active_admin_invite_codes() == 0

    invite = create_admin_invite_code("test-code", expires_at=utc_now() + timedelta(days=1))
    db.session.flush()

    assert invite.code == "test-code"
    assert invite.used is False
    assert count_active_admin_invite_codes() == 1

    listed = list_admin_invite_codes()
    assert len(listed) == 1
    assert listed[0].id == invite.id

    by_id = get_admin_invite_code_by_id(invite.id)
    by_code = get_admin_invite_code_by_code("test-code")
    assert by_id is not None and by_id.id == invite.id
    assert by_code is not None and by_code.id == invite.id

    marked = mark_admin_invite_code_used(invite.id)
    db.session.commit()
    assert marked is True
    assert count_active_admin_invite_codes() == 0

    refreshed = get_admin_invite_code_by_id(invite.id)
    assert refreshed is not None
    assert refreshed.used is True


def test_active_invite_count_excludes_expired_codes(client):
    now = utc_now()
    create_admin_invite_code("expired-code", expires_at=now - timedelta(days=1))
    create_admin_invite_code("future-code", expires_at=now + timedelta(days=1))
    create_admin_invite_code("no-expiry-code", expires_at=None)
    db.session.flush()

    assert count_active_admin_invite_codes(now=now) == 2
