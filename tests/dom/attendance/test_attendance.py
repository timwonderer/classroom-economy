from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.attendance import (
    calculate_period_attendance,
    calculate_unpaid_attendance_seconds,
    get_last_payroll_time,
    get_session_status,
)
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session, record_payroll_event
from app.models import AttendanceReasonCode, PolicyVersion
from app.services.context_resolver import CanonicalContext
from tests.helpers.classroom_initializer import initialize


def _create_class_and_student(test_suffix, app, section="A"):
    """Create a teacher + class + student. Returns (classroom, student fixture)."""
    classroom_key = "ap_csp_p3" if test_suffix.endswith("B") else {
        "unpaid-A": "ap_csp_p3",
        "period-A": "biology_block_a",
        "session-A": "duplicate_names",
    }.get(test_suffix, "chemistry_p1")
    classroom = initialize(classroom_key, app)
    return classroom, classroom.students[0]


def _student_ctx(classroom, student) -> CanonicalContext:
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _teacher_ctx(classroom) -> CanonicalContext:
    return CanonicalContext(
        user_id=classroom.teacher_user.id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat.id,
        actor_role="teacher",
    )


def _active_payroll_policy_version(classroom) -> PolicyVersion:
    with FEATContext("FEAT-BYPASS-LEGACY", correlation_id=f"test_payroll_policy:{classroom.class_id}"):
        policy = PolicyVersion(
            class_id=classroom.class_id,
            domain="payroll",
            version_number=1,
            policy_payload_json='{"source":"test"}',
            activated_at=datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc),
            is_active=True,
        )
        db.session.add(policy)
        db.session.flush()
    return policy


def _record_active_interval(ctx: CanonicalContext, *, start, end) -> None:
    record_attendance_session(
        ctx=ctx,
        status="active",
        idempotency_key=f"test:attendance:active:{ctx.class_id}:{ctx.seat_id}:{start.isoformat()}",
        reference_time_utc=start,
    )
    record_attendance_session(
        ctx=ctx,
        status="inactive",
        reason_code=AttendanceReasonCode.DONE_FOR_DAY,
        idempotency_key=f"test:attendance:inactive:{ctx.class_id}:{ctx.seat_id}:{end.isoformat()}",
        reference_time_utc=end,
    )


def test_DOM_PROD_001__get_last_payroll_time_reads_payroll_events(client):
    with pytest.raises(ValueError):
        get_last_payroll_time(seat_id=None, class_id=None)

    classroom, student = _create_class_and_student("payroll-A", client.application)
    policy = _active_payroll_policy_version(classroom)
    payroll_time = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)
    manual_credit_time = payroll_time + timedelta(hours=1)

    record_payroll_event(
        ctx=_teacher_ctx(classroom),
        target_seat_id=student.seat.id,
        payroll_event_type="payroll",
        correlation_id="corr:test:payroll-anchor",
        idempotency_key="test:payroll-anchor",
        policy_version_id=policy.id,
        mechanism="TEACHER",
        amount=Decimal("0.00"),
        reference_time_utc=payroll_time,
    )
    record_payroll_event(
        ctx=_teacher_ctx(classroom),
        target_seat_id=student.seat.id,
        payroll_event_type="manual_credit",
        correlation_id="corr:test:manual-credit-anchor",
        idempotency_key="test:manual-credit-anchor",
        policy_version_id=policy.id,
        mechanism="TEACHER",
        amount=Decimal("1.00"),
        reference_time_utc=manual_credit_time,
    )

    assert get_last_payroll_time(seat_id=student.seat.id, class_id=classroom.class_id) == payroll_time
    assert get_last_payroll_time(seat_id=student.seat.id, class_id=classroom.class_id) == payroll_time


def test_DOM_PROD_001__calculate_unpaid_attendance_seconds(client):
    classroom, student = _create_class_and_student("unpaid-A", client.application)
    ctx = _student_ctx(classroom, student)

    start = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=15)
    _record_active_interval(ctx, start=start, end=end)

    last_payroll_time = start - timedelta(days=1)
    unpaid_seconds = calculate_unpaid_attendance_seconds(student.seat.id, classroom.class_id, last_payroll_time)

    assert unpaid_seconds == 900


def test_DOM_PROD_001__calculate_period_attendance(client):
    classroom, student = _create_class_and_student("period-A", client.application)
    ctx = _student_ctx(classroom, student)

    start = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=10)
    _record_active_interval(ctx, start=start, end=end)

    period_attendance = calculate_period_attendance(student.seat.id, classroom.class_id, start.date())

    assert period_attendance == 600


def test_DOM_PROD_001__get_session_status(client):
    classroom, student = _create_class_and_student("session-A", client.application)
    ctx = _student_ctx(classroom, student)

    active_start = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)
    record_attendance_session(
        ctx=ctx,
        status="active",
        idempotency_key="test:get-session-status:active",
        reference_time_utc=active_start,
    )

    is_active, done, duration = get_session_status(student.seat.id, classroom.class_id)
    assert is_active is True
    assert done is False
    assert duration > 0
