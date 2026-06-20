from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa

from app.extensions import db
from app.utils.time import utc_now


@dataclass
class TeacherOnboardingView:
    id: int
    teacher_id: int
    is_completed: bool
    is_skipped: bool
    current_step: int
    total_steps: int
    steps_completed: dict
    widget_tasks_completed: dict
    widget_dismissed: bool
    widget_dismissed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    skipped_at: datetime | None
    last_activity_at: datetime | None


@dataclass
class AdminCredentialView:
    id: int
    teacher_id: int
    user_id: int | None
    credential_id: str | None
    authenticator_name: str | None
    created_at: datetime | None
    last_used: datetime | None


@dataclass
class AdminInviteCodeView:
    id: int
    code: str
    used: bool
    created_at: datetime | None
    expires_at: datetime | None


def _tables() -> tuple[sa.Table, sa.Table, sa.Table]:
    onboarding = db.metadata.tables["teacher_onboarding"]
    credentials = db.metadata.tables["teacher_credentials"]
    invites = db.metadata.tables["teacher_invite_codes"]
    return onboarding, credentials, invites


def _onboarding_user_col(onboarding: sa.Table) -> sa.ColumnElement:
    """Resolve the canonical teacher/onboarding foreign key column."""
    return onboarding.c.user_id if "user_id" in onboarding.c else onboarding.c.teacher_id


def _onboarding_row_to_view(row: sa.Row) -> TeacherOnboardingView:
    teacher_id = row._mapping["user_id"] if "user_id" in row._mapping else row._mapping["teacher_id"]
    return TeacherOnboardingView(
        id=row.id,
        teacher_id=teacher_id,
        is_completed=bool(row.is_completed),
        is_skipped=bool(row.is_skipped),
        current_step=row.current_step,
        total_steps=row.total_steps,
        steps_completed=row.steps_completed or {},
        widget_tasks_completed=row.widget_tasks_completed or {},
        widget_dismissed=bool(row.widget_dismissed),
        widget_dismissed_at=row.widget_dismissed_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        skipped_at=row.skipped_at,
        last_activity_at=row.last_activity_at,
    )


def _credential_row_to_view(row: sa.Row) -> AdminCredentialView:
    return AdminCredentialView(
        id=row.id,
        teacher_id=row.teacher_id,
        user_id=getattr(row, "user_id", None),
        credential_id=row.credential_id,
        authenticator_name=row.authenticator_name,
        created_at=row.created_at,
        last_used=row.last_used,
    )


def _invite_row_to_view(row: sa.Row) -> AdminInviteCodeView:
    return AdminInviteCodeView(
        id=row.id,
        code=row.code,
        used=bool(row.used),
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


def get_teacher_onboarding(teacher_id: int) -> TeacherOnboardingView | None:
    onboarding, _credentials, _invites = _tables()
    stmt = sa.select(onboarding).where(_onboarding_user_col(onboarding) == teacher_id).limit(1)
    row = db.session.execute(stmt).first()
    return _onboarding_row_to_view(row) if row else None


def create_teacher_onboarding(teacher_id: int, now: datetime) -> TeacherOnboardingView:
    onboarding, _credentials, _invites = _tables()
    insert_stmt = (
        sa.insert(onboarding)
        .values(
            **{_onboarding_user_col(onboarding).name: teacher_id},
            is_completed=False,
            is_skipped=False,
            current_step=1,
            total_steps=5,
            steps_completed={},
            widget_tasks_completed={},
            widget_dismissed=False,
            widget_dismissed_at=None,
            started_at=now,
            completed_at=None,
            skipped_at=None,
            last_activity_at=now,
        )
        .returning(onboarding.c.id)
    )
    onboarding_id = db.session.execute(insert_stmt).scalar_one()
    created = get_teacher_onboarding_by_id(onboarding_id)
    if created is None:
        raise RuntimeError("Failed to create teacher onboarding row")
    return created


def get_teacher_onboarding_by_id(onboarding_id: int) -> TeacherOnboardingView | None:
    onboarding, _credentials, _invites = _tables()
    stmt = sa.select(onboarding).where(onboarding.c.id == onboarding_id).limit(1)
    row = db.session.execute(stmt).first()
    return _onboarding_row_to_view(row) if row else None


def get_or_create_teacher_onboarding(teacher_id: int, now: datetime) -> TeacherOnboardingView:
    existing = get_teacher_onboarding(teacher_id)
    if existing is not None:
        return existing
    return create_teacher_onboarding(teacher_id, now)


def create_legacy_completed_teacher_onboarding(teacher_id: int, completed_at: datetime) -> TeacherOnboardingView:
    onboarding, _credentials, _invites = _tables()
    insert_stmt = (
        sa.insert(onboarding)
        .values(
            **{_onboarding_user_col(onboarding).name: teacher_id},
            is_completed=True,
            is_skipped=True,
            current_step=1,
            total_steps=5,
            steps_completed={},
            widget_tasks_completed={},
            widget_dismissed=False,
            widget_dismissed_at=None,
            started_at=completed_at,
            completed_at=completed_at,
            skipped_at=completed_at,
            last_activity_at=completed_at,
        )
        .returning(onboarding.c.id)
    )
    onboarding_id = db.session.execute(insert_stmt).scalar_one()
    created = get_teacher_onboarding_by_id(onboarding_id)
    if created is None:
        raise RuntimeError("Failed to create legacy completed onboarding row")
    return created


def set_teacher_onboarding_skipped(teacher_id: int, now: datetime) -> None:
    onboarding, _credentials, _invites = _tables()
    stmt = (
        sa.update(onboarding)
        .where(_onboarding_user_col(onboarding) == teacher_id)
        .values(
            is_skipped=True,
            skipped_at=now,
            last_activity_at=now,
        )
    )
    db.session.execute(stmt)


def set_teacher_onboarding_widget_task_status(teacher_id: int, task_name: str, status: str | bool, now: datetime) -> None:
    record = get_or_create_teacher_onboarding(teacher_id, now)
    tasks = dict(record.widget_tasks_completed or {})
    tasks[task_name] = status
    onboarding, _credentials, _invites = _tables()
    stmt = (
        sa.update(onboarding)
        .where(_onboarding_user_col(onboarding) == teacher_id)
        .values(
            widget_tasks_completed=tasks,
            last_activity_at=now,
        )
    )
    db.session.execute(stmt)


def set_teacher_onboarding_widget_dismissed(teacher_id: int, dismissed: bool, now: datetime) -> None:
    get_or_create_teacher_onboarding(teacher_id, now)
    onboarding, _credentials, _invites = _tables()
    stmt = (
        sa.update(onboarding)
        .where(_onboarding_user_col(onboarding) == teacher_id)
        .values(
            widget_dismissed=dismissed,
            widget_dismissed_at=(now if dismissed else None),
            last_activity_at=now,
        )
    )
    db.session.execute(stmt)


def delete_teacher_onboarding_for_teacher(teacher_id: int) -> None:
    onboarding, _credentials, _invites = _tables()
    db.session.execute(sa.delete(onboarding).where(_onboarding_user_col(onboarding) == teacher_id))


def admin_has_passkeys(teacher_id: int) -> bool:
    _onboarding, credentials, _invites = _tables()
    user_id = _teacher_user_id(teacher_id)
    if user_id is None:
        return False
    stmt = (
        sa.select(credentials.c.id)
        .where(credentials.c.user_id == user_id)
        .limit(1)
    )
    return db.session.execute(stmt).first() is not None


def _teacher_user_id(teacher_id: int) -> int | None:
    teachers = db.metadata.tables["teachers"]
    users = db.metadata.tables["users"]
    stmt = (
        sa.select(users.c.id)
        .select_from(teachers.join(users, users.c.username_lookup_hash == teachers.c.username_lookup_hash))
        .where(
            teachers.c.id == teacher_id,
            users.c.user_role == "teacher",
        )
        .limit(1)
    )
    return db.session.execute(stmt).scalar_one_or_none()


def create_admin_credential(teacher_id: int, authenticator_name: str, credential_id: str | None = None) -> AdminCredentialView:
    _onboarding, credentials, _invites = _tables()
    user_id = _teacher_user_id(teacher_id)
    if user_id is None:
        raise RuntimeError("Cannot create passkey credential without canonical teacher user")
    insert_stmt = (
        sa.insert(credentials)
        .values(
            teacher_id=teacher_id,
            user_id=user_id,
            credential_id=credential_id,
            authenticator_name=authenticator_name,
        )
        .returning(credentials.c.id)
    )
    cred_id = db.session.execute(insert_stmt).scalar_one()
    created = get_admin_credential(cred_id, teacher_id)
    if created is None:
        raise RuntimeError("Failed to create admin credential row")
    return created


def touch_admin_credentials_last_used(teacher_id: int, now: datetime) -> int:
    _onboarding, credentials, _invites = _tables()
    user_id = _teacher_user_id(teacher_id)
    if user_id is None:
        return 0
    stmt = (
        sa.update(credentials)
        .where(credentials.c.user_id == user_id)
        .values(last_used=now)
    )
    result = db.session.execute(stmt)
    return result.rowcount or 0


def list_admin_credentials(teacher_id: int) -> list[AdminCredentialView]:
    _onboarding, credentials, _invites = _tables()
    user_id = _teacher_user_id(teacher_id)
    if user_id is None:
        return []
    stmt = (
        sa.select(credentials)
        .where(credentials.c.user_id == user_id)
        .order_by(credentials.c.created_at.desc())
    )
    return [_credential_row_to_view(row) for row in db.session.execute(stmt).all()]


def get_admin_credential(credential_id: int, teacher_id: int) -> AdminCredentialView | None:
    _onboarding, credentials, _invites = _tables()
    user_id = _teacher_user_id(teacher_id)
    if user_id is None:
        return None
    stmt = (
        sa.select(credentials)
        .where(
            credentials.c.id == credential_id,
            credentials.c.user_id == user_id,
        )
        .limit(1)
    )
    row = db.session.execute(stmt).first()
    return _credential_row_to_view(row) if row else None


def delete_admin_credential(credential_id: int, teacher_id: int) -> bool:
    _onboarding, credentials, _invites = _tables()
    user_id = _teacher_user_id(teacher_id)
    if user_id is None:
        return False
    stmt = sa.delete(credentials).where(
        credentials.c.id == credential_id,
        credentials.c.user_id == user_id,
    )
    result = db.session.execute(stmt)
    return (result.rowcount or 0) > 0


def delete_admin_credentials_for_teacher(teacher_id: int) -> None:
    _onboarding, credentials, _invites = _tables()
    user_id = _teacher_user_id(teacher_id)
    if user_id is None:
        return
    db.session.execute(sa.delete(credentials).where(credentials.c.user_id == user_id))


def count_active_admin_invite_codes(*, now: datetime | None = None) -> int:
    _onboarding, _credentials, invites = _tables()
    effective_now = now or utc_now()
    stmt = (
        sa.select(sa.func.count())
        .select_from(invites)
        .where(
            invites.c.used.is_(False),
            sa.or_(
                invites.c.expires_at.is_(None),
                invites.c.expires_at >= effective_now,
            ),
        )
    )
    return int(db.session.execute(stmt).scalar_one())


def create_admin_invite_code(code: str, expires_at: datetime | None) -> AdminInviteCodeView:
    _onboarding, _credentials, invites = _tables()
    insert_stmt = (
        sa.insert(invites)
        .values(code=code, used=False, expires_at=expires_at)
        .returning(invites.c.id)
    )
    invite_id = db.session.execute(insert_stmt).scalar_one()
    created = get_admin_invite_code_by_id(invite_id)
    if created is None:
        raise RuntimeError("Failed to create admin invite code")
    return created


def list_admin_invite_codes() -> list[AdminInviteCodeView]:
    _onboarding, _credentials, invites = _tables()
    stmt = sa.select(invites).order_by(invites.c.created_at.desc())
    return [_invite_row_to_view(row) for row in db.session.execute(stmt).all()]


def get_admin_invite_code_by_id(invite_id: int) -> AdminInviteCodeView | None:
    _onboarding, _credentials, invites = _tables()
    stmt = sa.select(invites).where(invites.c.id == invite_id).limit(1)
    row = db.session.execute(stmt).first()
    return _invite_row_to_view(row) if row else None


def get_admin_invite_code_by_code(code: str) -> AdminInviteCodeView | None:
    _onboarding, _credentials, invites = _tables()
    stmt = sa.select(invites).where(invites.c.code == code).limit(1)
    row = db.session.execute(stmt).first()
    return _invite_row_to_view(row) if row else None


def mark_admin_invite_code_used(invite_id: int) -> bool:
    _onboarding, _credentials, invites = _tables()
    stmt = (
        sa.update(invites)
        .where(
            invites.c.id == invite_id,
            invites.c.used.is_(False),
        )
        .values(
            used=True,
        )
    )
    result = db.session.execute(stmt)
    return (result.rowcount or 0) > 0
