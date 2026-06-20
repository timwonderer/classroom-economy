from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

import sqlalchemy as sa

from app.extensions import db


@dataclass
class RecoveryRequestView:
    id: int
    teacher_id: int
    status: str
    created_at: datetime | None
    expires_at: datetime
    completed_at: datetime | None
    partial_codes: list[str] | None
    resume_pin_hash: str | None
    resume_new_username: str | None


@dataclass
class RecoveryCodeView:
    id: int
    user_id: int
    recovery_request_id: int
    code_hash: str | None
    verified_at: datetime | None
    notified_at: datetime | None
    dismissed: bool
    recovery_request: SimpleNamespace


def _tables() -> tuple[sa.Table, sa.Table]:
    requests = db.metadata.tables["recovery_requests"]
    codes = db.metadata.tables["student_recovery_codes"]
    return requests, codes


def _request_row_to_view(row: sa.Row) -> RecoveryRequestView:
    return RecoveryRequestView(
        id=row.id,
        teacher_id=row.teacher_id,
        status=row.status,
        created_at=row.created_at,
        expires_at=row.expires_at,
        completed_at=row.completed_at,
        partial_codes=row.partial_codes,
        resume_pin_hash=row.resume_pin_hash,
        resume_new_username=row.resume_new_username,
    )


def _code_row_to_view(row: sa.Row) -> RecoveryCodeView:
    return RecoveryCodeView(
        id=row.code_id,
        user_id=row.user_id,
        recovery_request_id=row.recovery_request_id,
        code_hash=row.code_hash,
        verified_at=row.verified_at,
        notified_at=row.notified_at,
        dismissed=bool(row.dismissed),
        recovery_request=SimpleNamespace(expires_at=row.expires_at),
    )


def get_pending_recovery_code_for_student(student_id: int, now_utc: datetime) -> RecoveryCodeView | None:
    requests, codes = _tables()
    stmt = (
        sa.select(
            codes.c.id.label("code_id"),
            codes.c.user_id,
            codes.c.recovery_request_id,
            codes.c.code_hash,
            codes.c.verified_at,
            codes.c.notified_at,
            codes.c.dismissed,
            requests.c.expires_at,
        )
        .select_from(codes.join(requests, requests.c.id == codes.c.recovery_request_id))
        .where(
            codes.c.user_id == student_id,
            codes.c.dismissed.is_(False),
            codes.c.code_hash.is_(None),
            requests.c.status == "pending",
            requests.c.expires_at > now_utc,
        )
        .order_by(codes.c.id.asc())
        .limit(1)
    )
    row = db.session.execute(stmt).first()
    return _code_row_to_view(row) if row else None


def get_recovery_code_for_student(code_id: int, student_id: int) -> RecoveryCodeView | None:
    requests, codes = _tables()
    stmt = (
        sa.select(
            codes.c.id.label("code_id"),
            codes.c.user_id,
            codes.c.recovery_request_id,
            codes.c.code_hash,
            codes.c.verified_at,
            codes.c.notified_at,
            codes.c.dismissed,
            requests.c.expires_at,
        )
        .select_from(codes.join(requests, requests.c.id == codes.c.recovery_request_id))
        .where(
            codes.c.id == code_id,
            codes.c.user_id == student_id,
        )
        .limit(1)
    )
    row = db.session.execute(stmt).first()
    return _code_row_to_view(row) if row else None


def set_recovery_code_verified(code_id: int, code_hash: str, verified_at: datetime) -> None:
    _requests, codes = _tables()
    stmt = (
        sa.update(codes)
        .where(codes.c.id == code_id)
        .values(
            code_hash=code_hash,
            verified_at=verified_at,
        )
    )
    db.session.execute(stmt)


def dismiss_recovery_code(code_id: int) -> None:
    _requests, codes = _tables()
    stmt = sa.update(codes).where(codes.c.id == code_id).values(dismissed=True)
    db.session.execute(stmt)


def get_active_recovery_request_for_teacher(teacher_id: int, now_utc: datetime) -> RecoveryRequestView | None:
    requests, _codes = _tables()
    stmt = (
        sa.select(requests)
        .where(
            requests.c.teacher_id == teacher_id,
            requests.c.status == "pending",
            requests.c.expires_at > now_utc,
        )
        .order_by(requests.c.id.desc())
        .limit(1)
    )
    row = db.session.execute(stmt).first()
    return _request_row_to_view(row) if row else None


def create_recovery_request_with_students(
    teacher_id: int,
    student_ids: list[int],
    expires_at: datetime,
) -> RecoveryRequestView:
    requests, codes = _tables()
    insert_stmt = (
        sa.insert(requests)
        .values(
            teacher_id=teacher_id,
            status="pending",
            expires_at=expires_at,
        )
        .returning(requests.c.id)
    )
    request_id = db.session.execute(insert_stmt).scalar_one()
    if student_ids:
        db.session.execute(
            sa.insert(codes),
            [
                {
                    "recovery_request_id": request_id,
                    "student_id": student_id,
                }
                for student_id in student_ids
            ],
        )
    created = get_recovery_request_by_id(request_id)
    if created is None:
        raise RuntimeError("Failed to create recovery request row")
    return created


def get_recovery_request_by_id(recovery_request_id: int) -> RecoveryRequestView | None:
    requests, _codes = _tables()
    stmt = sa.select(requests).where(requests.c.id == recovery_request_id).limit(1)
    row = db.session.execute(stmt).first()
    return _request_row_to_view(row) if row else None


def list_recovery_codes_for_request(recovery_request_id: int) -> list[RecoveryCodeView]:
    requests, codes = _tables()
    stmt = (
        sa.select(
            codes.c.id.label("code_id"),
            codes.c.student_id,
            codes.c.recovery_request_id,
            codes.c.code_hash,
            codes.c.verified_at,
            codes.c.notified_at,
            codes.c.dismissed,
            requests.c.expires_at,
        )
        .select_from(codes.join(requests, requests.c.id == codes.c.recovery_request_id))
        .where(codes.c.recovery_request_id == recovery_request_id)
        .order_by(codes.c.id.asc())
    )
    return [_code_row_to_view(row) for row in db.session.execute(stmt).all()]


def invalidate_recovery_codes(recovery_request_id: int) -> int:
    _requests, codes = _tables()
    stmt = (
        sa.update(codes)
        .where(codes.c.recovery_request_id == recovery_request_id)
        .values(
            code_hash=None,
            verified_at=None,
        )
    )
    result = db.session.execute(stmt)
    return result.rowcount or 0


def mark_recovery_request_verified(recovery_request_id: int, completed_at: datetime) -> None:
    requests, _codes = _tables()
    stmt = (
        sa.update(requests)
        .where(requests.c.id == recovery_request_id)
        .values(
            status="verified",
            completed_at=completed_at,
        )
    )
    db.session.execute(stmt)


def save_recovery_progress(
    recovery_request_id: int,
    partial_codes: list[str],
    resume_pin_hash: str,
    resume_new_username: str,
) -> None:
    requests, _codes = _tables()
    stmt = (
        sa.update(requests)
        .where(requests.c.id == recovery_request_id)
        .values(
            partial_codes=partial_codes,
            resume_pin_hash=resume_pin_hash,
            resume_new_username=resume_new_username,
        )
    )
    db.session.execute(stmt)


def find_recovery_request_by_resume_pin(resume_pin_hash: str, now_utc: datetime) -> RecoveryRequestView | None:
    requests, _codes = _tables()
    stmt = (
        sa.select(requests)
        .where(
            requests.c.resume_pin_hash == resume_pin_hash,
            requests.c.status == "pending",
            requests.c.expires_at > now_utc,
        )
        .order_by(requests.c.id.desc())
        .limit(1)
    )
    row = db.session.execute(stmt).first()
    return _request_row_to_view(row) if row else None


def delete_recovery_rows_for_teacher(teacher_id: int) -> None:
    requests, codes = _tables()
    request_ids_subq = sa.select(requests.c.id).where(requests.c.teacher_id == teacher_id)
    db.session.execute(
        sa.delete(codes).where(codes.c.recovery_request_id.in_(request_ids_subq))
    )
    db.session.execute(
        sa.delete(requests).where(requests.c.teacher_id == teacher_id)
    )


def delete_recovery_codes_for_student(student_id: int) -> None:
    _requests, codes = _tables()
    db.session.execute(sa.delete(codes).where(codes.c.user_id == student_id))
