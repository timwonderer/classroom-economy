"""Regression: /admin/run_payroll must survive an empty desk in the roster.

Reproduces the live-browser defect where a class contained one claimed,
attended student seat (done-for-day, so payroll has earnings to pay) PLUS one
empty desk -- an unclaimed roster seat with ``user_id IS NULL`` and
``role='student'``.

The old ``_run_payroll`` iterated *every* ``role='student'`` seat, including the
empty desk. ``record_payroll_event`` then tried to persist a ``PayrollEvent``
with ``target_user_id = seat.user_id`` (NULL), violating the NOT NULL column and
rolling back the *entire* batch -- so the attended student was never paid and the
teacher saw "Database error during payroll".

The fix keys payroll population off the ATTENDANCE RECORD
(``AttendanceSession.target_seat_id``) rather than the seat roster. Empty desks
have no attendance rows and are excluded by construction; any seat that *does*
have attendance is necessarily a claimed participant (attendance is seat+user
anchored). This mirrors DOM-IDEN-001: activity keys off seat_id.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.feats.prod import record_attendance_session
from app.models import AttendanceReasonCode, PayrollEvent, PolicyVersion, Seat
from app.services.context_resolver import CanonicalContext
from tests.helpers.canonical_classroom import _provision_roster_seat
from tests.helpers.class_domain import enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_teacher


def _student_ctx(classroom, student) -> CanonicalContext:
    return CanonicalContext(
        user_id=student.user.id,
        class_id=classroom.class_id,
        seat_id=student.seat.id,
        actor_role="student",
    )


def _seed_active_payroll_policy(class_id: str) -> PolicyVersion:
    with FEATContext(
        "FEAT-BYPASS-LEGACY",
        correlation_id=f"test_payroll_policy:{class_id}",
    ):
        policy = PolicyVersion(
            class_id=class_id,
            domain="payroll",
            version_number=1,
            policy_payload_json='{"source":"test"}',
            activated_at=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
            is_active=True,
        )
        db.session.add(policy)
        db.session.flush()
    return policy


def _record_done_for_day_interval(ctx: CanonicalContext, *, start, end) -> None:
    record_attendance_session(
        ctx=ctx,
        status="active",
        idempotency_key=f"test:attn:active:{ctx.seat_id}:{start.isoformat()}",
        reference_time_utc=start,
    )
    record_attendance_session(
        ctx=ctx,
        status="inactive",
        reason_code=AttendanceReasonCode.DONE_FOR_DAY,
        idempotency_key=f"test:attn:inactive:{ctx.seat_id}:{end.isoformat()}",
        reference_time_utc=end,
    )


def _seed_empty_desk(class_id: str) -> Seat:
    """Create one unclaimed roster seat (role='student', user_id IS NULL)."""
    with FEATContext(
        "FEAT-BYPASS-LEGACY",
        correlation_id=f"test_empty_desk:{class_id}",
    ):
        seat = _provision_roster_seat(
            class_id,
            {"first_name": "Empty", "last_name": "Desk", "dedupe_code": None},
        )
    return seat


def test_DOM_PROD_003__run_payroll_pays_attended_seat_and_skips_empty_desk(client):
    app = client.application
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    attended = classroom.students[0]

    enable_class_feature(class_id=classroom.class_id, feature="payroll")
    _seed_active_payroll_policy(classroom.class_id)

    # Claimed student works, then is done for the day -> payroll has earnings.
    now = datetime.now(timezone.utc)
    _record_done_for_day_interval(
        _student_ctx(classroom, attended),
        start=now - timedelta(minutes=20),
        end=now - timedelta(minutes=5),
    )

    # The poison: an empty desk (unclaimed roster seat, user_id IS NULL).
    empty_desk = _seed_empty_desk(classroom.class_id)
    assert empty_desk.user_id is None
    assert empty_desk.role == "student"

    response = client.post("/admin/run_payroll")

    # The whole batch must succeed -- no rollback, no "Database error".
    assert response.status_code in (200, 302), response.data
    assert b"Database error" not in response.data

    # Exactly one payroll event was recorded: for the attended seat only.
    events = PayrollEvent.query.filter_by(
        class_id=classroom.class_id,
        payroll_event_type="payroll",
    ).all()
    assert len(events) == 1
    event = events[0]
    assert event.target_seat_id == attended.seat.id
    assert event.target_user_id == attended.user.id

    # The empty desk earned no payroll event.
    empty_events = PayrollEvent.query.filter_by(
        class_id=classroom.class_id,
        target_seat_id=empty_desk.id,
    ).all()
    assert empty_events == []

    # The attended seat was actually paid a non-zero amount (15 min worked).
    from app.models import Transaction

    paid = Transaction.query.filter_by(
        class_id=classroom.class_id,
        target_seat_id=attended.seat.id,
        type="payroll",
    ).first()
    assert paid is not None
    assert Decimal(paid.amount) > Decimal("0.00")
