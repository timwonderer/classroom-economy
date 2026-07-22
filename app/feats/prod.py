from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

from sqlalchemy import func

from app.extensions import db
from app.feats.base import feat_shell, get_correlation_id
from app.models import (
    AttendanceReasonCode,
    AttendanceSession,
    ClassEconomy,
    HallPassLog,
    HallPassSettings,
    PayrollEvent,
    PayrollSettings,
    Seat,
    Transaction,
)
from app.services.context_resolver import CanonicalContext
from app.services.entitlement_service import consume_hall_pass, get_hall_pass_balance
from app.services.ledger_service import create_pending_transaction
from app.utils.canonical_temporal_resolver import (
    CLASS_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


@dataclass(frozen=True)
class AttendanceSessionResult:
    session: AttendanceSession


@dataclass(frozen=True)
class HallPassLogResult:
    hall_pass_log: HallPassLog


@dataclass(frozen=True)
class PayrollEventResult:
    payroll_event: PayrollEvent
    ledger_transaction: Transaction | None


def _require_context(ctx: CanonicalContext | None) -> CanonicalContext:
    if ctx is None:
        raise ValueError("CanonicalContext is required.")
    if not getattr(ctx, "class_id", None) or not getattr(ctx, "seat_id", None):
        raise ValueError("CanonicalContext must include class_id and seat_id.")
    return ctx


def _resolve_class_economy(class_id: str) -> ClassEconomy:
    economy = ClassEconomy.query.filter_by(class_id=class_id).first()
    if not economy:
        raise LookupError(f"No class economy found for class_id={class_id!r}.")
    return economy


def _resolve_pay_rate_per_second(class_id: str, *, block: str | None = None) -> Decimal:
    query = PayrollSettings.query.filter(
        PayrollSettings.class_id == class_id,
        PayrollSettings.is_active.is_(True),
    )
    if block:
        query = query.filter(func.upper(PayrollSettings.block) == block.upper())
    else:
        query = query.filter(PayrollSettings.block.is_(None))

    setting = query.order_by(PayrollSettings.updated_at.desc(), PayrollSettings.id.desc()).first()
    if setting and setting.pay_rate:
        return Decimal(setting.pay_rate) / Decimal("60")
    return Decimal("0.25") / Decimal("60")


def _latest_hall_pass_attendance_state(log: HallPassLog) -> str:
    rows = (
        AttendanceSession.query.filter_by(
            class_id=log.class_id,
            target_seat_id=log.requested_by_seat_id,
            hall_pass_id=log.hall_pass_id,
        )
        .order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc())
        .all()
    )
    left_seen = False
    for row in rows:
        if row.status == "inactive" and row.reason_code == AttendanceReasonCode.HALL_PASS.value:
            left_seen = True
        elif left_seen and row.status == "active":
            return "returned"
    return "left" if left_seen else "approved"


def _enforce_hall_pass_settings(
    *,
    ctx: CanonicalContext,
    destination: str,
    reference_time_utc,
) -> None:
    settings = HallPassSettings.query.filter_by(class_id=ctx.class_id).first()
    pass_types = settings.get_pass_types() if settings else HallPassSettings.get_default_pass_types()
    normalized_destination = (destination or "").strip().lower()
    pass_type = next(
        (
            item for item in pass_types
            if (item.get("name") or "").strip().lower() == normalized_destination
        ),
        None,
    )
    if pass_type is not None and not pass_type.get("enabled", True):
        raise ValueError("Hall-pass destination is disabled.")

    day_bounds = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="evaluation_day_boundaries",
        reference_time_utc=reference_time_utc,
    )
    todays_logs = (
        HallPassLog.query.filter(
            HallPassLog.class_id == ctx.class_id,
            HallPassLog.timestamp >= day_bounds.boundary_start_utc,
            HallPassLog.timestamp < day_bounds.boundary_end_utc,
        )
        .order_by(HallPassLog.timestamp.asc(), HallPassLog.id.asc())
        .all()
    )
    currently_out = [
        log for log in todays_logs
        if _latest_hall_pass_attendance_state(log) == "left"
    ]

    queue_limit = getattr(settings, "queue_limit", None) if settings else None
    queue_enabled = getattr(settings, "queue_enabled", True) if settings else True
    if queue_enabled and queue_limit is not None and len(currently_out) >= int(queue_limit):
        raise ValueError("Hall-pass queue limit reached.")

    simultaneous_limit = pass_type.get("simultaneous_limit") if pass_type else None
    if simultaneous_limit is not None:
        destination_out = [
            log for log in currently_out
            if (log.destination or "").strip().lower() == normalized_destination
        ]
        if len(destination_out) >= int(simultaneous_limit):
            raise ValueError("Hall-pass destination limit reached.")


def _last_payroll_event_time(*, seat_id: int, class_id: str) -> datetime | None:
    event = (
        PayrollEvent.query.filter(
            PayrollEvent.class_id == class_id,
            PayrollEvent.target_seat_id == seat_id,
            PayrollEvent.payroll_event_type == "payroll",
        )
        .order_by(PayrollEvent.recorded_at.desc(), PayrollEvent.id.desc())
        .first()
    )
    return event.recorded_at if event else None


def _calculate_attendance_seconds_since(
    *,
    ctx: CanonicalContext,
    seat_id: int,
    class_id: str,
    since_utc,
    current_time_utc,
) -> int:
    """Calculate attendance seconds from the append-only timeline.

    Each ``status='active'`` row marks a start; the next ``status='inactive'``
    row for the same target_seat_id+class_id marks the end. If no inactive row
    follows, the current payroll evaluation timestamp is used.
    """
    query = AttendanceSession.query.filter(
        AttendanceSession.target_seat_id == seat_id,
        AttendanceSession.class_id == class_id,
    )
    if since_utc:
        query = query.filter(AttendanceSession.timestamp >= since_utc)
    rows = query.order_by(AttendanceSession.timestamp.asc(), AttendanceSession.id.asc()).all()

    intervals = []
    active_start = None
    for row in rows:
        ts = row.timestamp
        if since_utc and ts < since_utc:
            continue
        if row.status == "active":
            active_start = ts
        elif row.status == "inactive" and active_start is not None:
            intervals.append((active_start, ts))
            active_start = None
    if active_start is not None:
        intervals.append((active_start, current_time_utc))
    if not intervals:
        return 0

    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="elapsed_duration",
        reference_time_utc=current_time_utc,
        intervals=intervals,
    )
    return evaluation.elapsed_seconds


@feat_shell("FEAT-PROD-001")
def record_attendance_session(
    *,
    ctx: CanonicalContext,
    status: str,
    target_seat_id: int | None = None,
    actor_seat_id: int | None = None,
    mechanism: str = "self",
    reason: str | None = None,
    reason_code: AttendanceReasonCode | None = None,
    hall_pass_id: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
    reference_time_utc=None,
) -> AttendanceSessionResult:
    ctx = _require_context(ctx)
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    )
    event_time = evaluation.canonical_now_utc

    if status not in {"active", "inactive"}:
        raise ValueError("Attendance status must be 'active' or 'inactive'.")

    # Resolve reason_code for inactive status
    if status == "inactive" and reason_code is None and reason:
        normalized_reason = reason.strip().lower().replace(" ", "_")
        if normalized_reason == "hall_pass":
            reason_code = AttendanceReasonCode.HALL_PASS
        elif normalized_reason == "done_for_day":
            reason_code = AttendanceReasonCode.DONE_FOR_DAY
    if status == "inactive" and reason_code is None:
        raise ValueError("Inactive attendance sessions require a reason_code.")
    if status == "inactive" and reason_code == AttendanceReasonCode.HALL_PASS and not hall_pass_id:
        raise ValueError("Hall-pass attendance sessions require hall_pass_id.")

    resolved_actor_seat_id = actor_seat_id or ctx.seat_id
    resolved_target_seat_id = target_seat_id or ctx.seat_id
    if mechanism not in {"self", "teacher", "system"}:
        raise ValueError("Attendance mechanism must be 'self', 'teacher', or 'system'.")

    target_seat = db.session.get(Seat, resolved_target_seat_id)
    if target_seat is None or target_seat.class_id != ctx.class_id:
        raise ValueError("Attendance target seat must belong to the canonical class.")
    if resolved_actor_seat_id:
        actor_seat = db.session.get(Seat, resolved_actor_seat_id)
        if actor_seat is None or actor_seat.class_id != ctx.class_id:
            raise ValueError("Attendance actor seat must belong to the canonical class.")
    target_user_id = target_seat.user_id

    resolved_reason_code = (
        reason_code.value if reason_code else AttendanceReasonCode.START_WORK.value
    ) if status == "active" else (
        reason_code.value if reason_code else None
    )

    session = AttendanceSession(
        target_seat_id=resolved_target_seat_id,
        actor_seat_id=resolved_actor_seat_id,
        class_id=ctx.class_id,
        target_user_id=target_user_id,
        status=status,
        reason_code=resolved_reason_code,
        timestamp=event_time,
        mechanism=mechanism,
        hall_pass_id=hall_pass_id,
    )
    db.session.add(session)
    db.session.flush()
    return AttendanceSessionResult(session=session)


@feat_shell("FEAT-PROD-002")
def record_hall_pass_log(
    *,
    ctx: CanonicalContext,
    requested_by_seat_id: int,
    approved_by_seat_id: int,
    hall_pass_id: str,
    destination: str,
    correlation_id: str,
    reason: str,
    idempotency_key: str | None = None,
    reference_time_utc=None,
) -> HallPassLogResult:
    ctx = _require_context(ctx)
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    )
    now = evaluation.canonical_now_utc
    _enforce_hall_pass_settings(
        ctx=ctx,
        destination=destination,
        reference_time_utc=now,
    )

    log = HallPassLog(
        requested_by_seat_id=requested_by_seat_id,
        approved_by_seat_id=approved_by_seat_id,
        class_id=ctx.class_id,
        timestamp=now,
        hall_pass_id=hall_pass_id,
        correlation_id=correlation_id,
        destination=destination,
    )
    db.session.add(log)
    db.session.flush()

    if requested_by_seat_id and ctx.class_id:
        consume_hall_pass(
            requested_by_seat_id,
            ctx.class_id,
            trigger_id=f"hall_pass_log:{hall_pass_id}",
        )

    return HallPassLogResult(hall_pass_log=log)


def _record_payroll_event_impl(
    *,
    ctx: CanonicalContext,
    target_seat_id: int,
    payroll_event_type: str,
    correlation_id: str,
    idempotency_key: str,
    policy_version_id: int,
    mechanism: str,
    summary_json: dict | None = None,
    reference_time_utc=None,
    amount: Decimal | None = None,
) -> PayrollEventResult:
    ctx = _require_context(ctx)
    if policy_version_id is None:
        raise ValueError("FEAT-PROD-003 requires a payroll policy_version_id.")
    evaluation = canonical_temporal_resolver(
        CLASS_LEVEL_EVALUATION,
        canonical_execution_context=ctx,
        primitive="current_time",
        reference_time_utc=reference_time_utc,
    )
    recorded_at = evaluation.canonical_now_utc
    class_row = _resolve_class_economy(ctx.class_id)
    section = getattr(class_row, "section", None)

    if payroll_event_type == "payroll" and amount is None:
        last_payroll_time = _last_payroll_event_time(seat_id=target_seat_id, class_id=ctx.class_id)
        attendance_seconds = _calculate_attendance_seconds_since(
            ctx=ctx,
            seat_id=target_seat_id,
            class_id=ctx.class_id,
            since_utc=last_payroll_time,
            current_time_utc=recorded_at,
        )
        rate_per_second = _resolve_pay_rate_per_second(ctx.class_id, block=section)
        amount = (Decimal(attendance_seconds) * rate_per_second).quantize(Decimal("0.01"))
    elif payroll_event_type == "manual_credit" and amount is None:
        raise ValueError("manual_credit payroll events require an amount.")
    elif payroll_event_type == "reversal":
        original = (
            PayrollEvent.query.filter(
                PayrollEvent.class_id == ctx.class_id,
                PayrollEvent.target_seat_id == target_seat_id,
                PayrollEvent.correlation_id == correlation_id,
            )
            .order_by(PayrollEvent.recorded_at.desc(), PayrollEvent.id.desc())
            .first()
        )
        if original is None:
            raise LookupError("Unable to establish original payroll event for reversal.")
        if amount is None:
            active_correlation_id = get_correlation_id()
            linked = (
                Transaction.query.filter(
                    Transaction.class_id == ctx.class_id,
                    Transaction.target_seat_id == target_seat_id,
                    Transaction.correlation_id.in_([correlation_id, active_correlation_id]),
                )
                .order_by(Transaction.timestamp.desc(), Transaction.id.desc())
                .first()
            )
            if linked is None:
                raise LookupError("Unable to establish original ledger transaction for reversal.")
            amount = -(Decimal(linked.amount or Decimal("0.00")))

    event = PayrollEvent(
        class_id=ctx.class_id,
        actor_seat_id=ctx.seat_id,
        target_seat_id=target_seat_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        policy_version_id=policy_version_id,
        mechanism=mechanism,
        payroll_event_type=payroll_event_type,
        recorded_at=recorded_at,
        summary_json=summary_json or {},
    )
    db.session.add(event)
    db.session.flush()

    if amount is not None and amount != Decimal("0.00"):
        tx = create_pending_transaction(
            seat_id=target_seat_id,
            class_id=ctx.class_id,
            target_seat_id=target_seat_id,
            actor_seat_id=ctx.seat_id,
            mechanism=mechanism.lower(),
            user_id=ctx.user_id,
            amount=amount,
            account_type="checking",
            type="payroll" if payroll_event_type != "manual_credit" else "manual_payment",
            description=(summary_json or {}).get("description", "Payroll event"),
        )
    else:
        tx = None

    return PayrollEventResult(payroll_event=event, ledger_transaction=tx)


@feat_shell("FEAT-PROD-003")
def record_payroll_event(
    *,
    ctx: CanonicalContext,
    target_seat_id: int,
    payroll_event_type: str,
    correlation_id: str,
    idempotency_key: str,
    policy_version_id: int,
    mechanism: str,
    summary_json: dict | None = None,
    reference_time_utc=None,
    amount: Decimal | None = None,
) -> PayrollEventResult:
    return _record_payroll_event_impl(
        ctx=ctx,
        target_seat_id=target_seat_id,
        payroll_event_type=payroll_event_type,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        policy_version_id=policy_version_id,
        mechanism=mechanism,
        summary_json=summary_json,
        reference_time_utc=reference_time_utc,
        amount=amount,
    )


@feat_shell("FEAT-PROD-003")
def record_payroll_reversal(
    *,
    ctx: CanonicalContext,
    target_seat_id: int,
    correlation_id: str,
    idempotency_key: str,
    policy_version_id: int,
    mechanism: str,
    summary_json: dict | None = None,
    reference_time_utc=None,
) -> PayrollEventResult:
    return _record_payroll_event_impl(
        ctx=ctx,
        target_seat_id=target_seat_id,
        payroll_event_type="reversal",
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        policy_version_id=policy_version_id,
        mechanism=mechanism,
        summary_json=summary_json,
        reference_time_utc=reference_time_utc,
    )
