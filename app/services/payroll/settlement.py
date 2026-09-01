"""Class-wide payroll-cycle settlement (DOM-PROD-001 §XV, slice 8.3b).

Owns exactly one thing: given a ``class_id``, a ``payroll_cycle_id``, and a lawful
resolved cycle boundary, settle the entire eligible class under the currently
governing payroll configuration, stamping the same ``payroll_cycle_id`` on every
payroll event produced.

    enumerate eligible seats (attendance-derived, PROD doctrine)
        -> derive each seat's pay window/facts (the per-seat primitive)
        -> invoke record_payroll_event (payroll_event_type="payroll")
        -> stamp the shared payroll_cycle_id on every event
        -> NO COMMIT

It is deliberately ignorant of ITR, CLASS policy activation, and the
completion/replay anchor — those are composed by the FEAT-PROD-004 orchestrator in
a later slice. It emits only ``payroll`` events; it never manufactures
``manual_credit`` or ``reversal`` events, so teacher credits and reversals never
become cycle-boundary events. It ``add``/``flush``es within the caller's FEAT
transaction and never commits, so a single per-seat failure lets the caller roll
the entire transaction back.
"""

from __future__ import annotations

from typing import NamedTuple

from app.extensions import db
from app.feats.base import get_correlation_id
from app.feats.prod import record_payroll_event
from app.models import (
    AttendanceSession,
    ClassEconomy,
    PayrollEvent,
    PolicyVersion,
    Seat,
)
from app.services.context_resolver import CanonicalContext


class ClassSettlementError(Exception):
    """Raised when class-wide settlement cannot proceed lawfully (e.g. no active
    payroll policy, or no resolvable teacher actor for the class)."""


class ClassSettlementResult(NamedTuple):
    payroll_cycle_id: str
    settled_seat_ids: list[int]      # seats that received a fresh payroll event this call
    skipped_seat_ids: list[int]      # seats already settled for this cycle (idempotent)
    events: list[PayrollEvent]


def _active_payroll_policy_version_id(class_id: str) -> int:
    policy = (
        PolicyVersion.query
        .filter_by(class_id=class_id, domain="payroll", is_active=True)
        .order_by(PolicyVersion.version_number.desc(), PolicyVersion.id.desc())
        .first()
    )
    if policy is None:
        raise ClassSettlementError(
            f"No active payroll policy version exists for class {class_id}; "
            "cannot settle a payroll cycle."
        )
    return policy.id


def _build_teacher_context(class_id: str) -> CanonicalContext:
    class_row = db.session.get(ClassEconomy, class_id)
    if class_row is None or not class_row.teacher_user_id:
        raise ClassSettlementError(f"Class {class_id} has no resolvable teacher actor.")
    teacher_seat = (
        Seat.query.filter_by(class_id=class_id, role="teacher").order_by(Seat.id.asc()).first()
    )
    if teacher_seat is None:
        raise ClassSettlementError(f"Class {class_id} has no teacher seat.")
    return CanonicalContext(
        user_id=class_row.teacher_user_id,
        class_id=class_id,
        seat_id=teacher_seat.id,
        actor_role="teacher",
    )


def _eligible_seat_ids(class_id: str) -> list[int]:
    """Enrolled student seats with attendance activity (current PROD doctrine).

    Payroll pays for attended time over each seat's ``[last payroll, boundary]``
    window, so a seat is eligible only if it has attendance rows — empty/unclaimed
    desks have none and are excluded by construction (mirrors the per-seat run
    population in ``admin.run_payroll``). Returned ascending for determinism.
    """
    attended = {
        seat_id
        for (seat_id,) in (
            db.session.query(AttendanceSession.target_seat_id)
            .filter(AttendanceSession.class_id == class_id)
            .distinct()
            .all()
        )
        if seat_id is not None
    }
    if not attended:
        return []
    rows = (
        Seat.query.with_entities(Seat.id)
        .filter(Seat.id.in_(attended), Seat.role == "student", Seat.class_id == class_id)
        .order_by(Seat.id.asc())
        .all()
    )
    return [row.id for row in rows]


def _already_settled(class_id: str, seat_id: int, payroll_cycle_id: str) -> bool:
    return (
        PayrollEvent.query
        .filter_by(
            class_id=class_id,
            target_seat_id=seat_id,
            payroll_cycle_id=payroll_cycle_id,
            payroll_event_type="payroll",
        )
        .first()
        is not None
    )


def settle_class_payroll_cycle(
    *,
    class_id: str,
    payroll_cycle_id: str,
    boundary_utc,
    actor_ctx: CanonicalContext | None = None,
) -> ClassSettlementResult:
    """Settle the eligible class for one payroll cycle. NO COMMIT (§8.3b).

    Must run inside the caller's FEAT transaction: it reads the active correlation
    id and reuses it for every seat, so all events settle under one transaction and
    one correlation (the per-seat primitive re-enters FEAT-PROD-003 as a no-op
    rather than committing per seat). Re-invoking with the same ``payroll_cycle_id``
    inside the same transaction is idempotent — already-settled seats are skipped,
    so no duplicate payroll rows are manufactured.
    """
    if not class_id or not payroll_cycle_id:
        raise ValueError("class_id and payroll_cycle_id are required for settlement")

    policy_version_id = _active_payroll_policy_version_id(class_id)
    ctx = actor_ctx or _build_teacher_context(class_id)
    correlation_id = get_correlation_id()

    settled: list[int] = []
    skipped: list[int] = []
    events: list[PayrollEvent] = []

    for seat_id in _eligible_seat_ids(class_id):
        if _already_settled(class_id, seat_id, payroll_cycle_id):
            skipped.append(seat_id)
            continue
        result = record_payroll_event(
            ctx=ctx,
            target_seat_id=seat_id,
            payroll_event_type="payroll",
            correlation_id=correlation_id,
            idempotency_key=f"payroll-cycle:{payroll_cycle_id}:seat:{seat_id}",
            policy_version_id=policy_version_id,
            mechanism="TEACHER",
            summary_json={
                "source": "class_payroll_settlement",
                "description": "Payroll based on attendance",
            },
            reference_time_utc=boundary_utc,
            payroll_cycle_id=payroll_cycle_id,
        )
        settled.append(seat_id)
        events.append(result.payroll_event)

    return ClassSettlementResult(
        payroll_cycle_id=payroll_cycle_id,
        settled_seat_ids=settled,
        skipped_seat_ids=skipped,
        events=events,
    )
