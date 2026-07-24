from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.feats.base import generate_correlation_id
from app.models import (
    EntitlementEvent,
    ObligationAssessment,
    ObligationLifecycle,
    ObligationReversal,
    ObligationSatisfaction,
    RentSettings,
    Seat,
)
from app.utils.time import utc_now


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _claim_assessment_key(claim_id: int) -> str:
    return f"insurance-claim:{claim_id}"


def _get_claim_assessment(assessment_key: str, seat_id: int, class_id: str) -> ObligationAssessment | None:
    return (
        ObligationAssessment.query.filter_by(
            seat_id=seat_id,
            class_id=class_id,
            cycle_idempotency_key=assessment_key,
        )
        .order_by(ObligationAssessment.id.desc())
        .first()
    )


def _create_claim_assessment(
    *,
    seat_id: int,
    class_id: str,
    claim_id: int,
    claim_amount,
    incident_date,
    assessed_at,
) -> ObligationAssessment:
    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="INSURANCE_CLAIM",
        amount_snap=claim_amount,
        due_at=incident_date,
        assessed_at=assessed_at,
        cycle_idempotency_key=_claim_assessment_key(claim_id),
    )
    db.session.add(assessment)
    db.session.flush()
    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="DUE",
            updated_at=assessed_at,
        )
    )
    return assessment


def _require_claim_assessment(claim_id: int, seat_id: int, class_id: str) -> ObligationAssessment:
    key = _claim_assessment_key(claim_id)
    assessment = _get_claim_assessment(key, seat_id, class_id)
    if assessment is None:
        raise ValueError(f"Missing canonical claim assessment for insurance claim {claim_id}")
    return assessment


def _set_assessment_lifecycle(assessment: ObligationAssessment, *, status: str, updated_at):
    lifecycle = assessment.lifecycle
    if lifecycle is None:
        lifecycle = ObligationLifecycle(
            assessment_id=assessment.id,
            status=status,
            updated_at=updated_at,
        )
        db.session.add(lifecycle)
        return lifecycle
    lifecycle.status = status
    lifecycle.updated_at = updated_at
    return lifecycle


# ---------------------------------------------------------------------------
# Rent mutations
# ---------------------------------------------------------------------------

def record_rent_payment(
    *,
    seat_id: int,
    class_id: str,
    period: str,
    amount_paid,
    period_month: int,
    period_year: int,
    coverage_month: int,
    coverage_year: int,
    was_late: bool,
    late_fee_charged,
    coverage_start_time=None,
    coverage_end_time=None,
    cycle_idempotency_key: str | None = None,
    transaction_id: int | None = None,
) -> ObligationAssessment:
    """Record a rent payment as a canonical assessment + satisfaction.
    """
    now = utc_now()
    period_key = f"{coverage_year}-{coverage_month:02d}" if coverage_year is not None and coverage_month is not None else None
    rent_settings = RentSettings.query.filter_by(class_id=class_id).first()
    if rent_settings is None:
        raise ValueError(f"RentSettings for class {class_id} not found")

    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        period=period,
        obligation_type="RENT",
        amount_snap=rent_settings.rent_amount,
        assessed_at=now,
        period_key=period_key,
        coverage_start_time=coverage_start_time,
        coverage_end_time=coverage_end_time,
        cycle_idempotency_key=cycle_idempotency_key,
        period_month=period_month,
        period_year=period_year,
        coverage_month=coverage_month,
        coverage_year=coverage_year,
    )
    db.session.add(assessment)
    db.session.flush()

    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="PAID",
            updated_at=now,
        )
    )
    db.session.add(
        ObligationSatisfaction(
            assessment_id=assessment.id,
            method="PAYMENT",
            amount_paid=amount_paid,
            was_late=was_late,
            late_fee_charged=late_fee_charged,
            transaction_id=transaction_id,
            satisfied_at=now,
        )
    )
    return assessment


def record_rent_waiver(
    *,
    seat_id: int,
    class_id: str,
    waiver_start_date,
    waiver_end_date,
    periods_count: int,
    reason: str | None = None,
    created_by_seat_id: int | None = None,
    created_by_user_id: int | None = None,
) -> ObligationAssessment:
    """Record a rent waiver as a canonical assessment + reversal."""
    now = utc_now()
    if created_by_seat_id is None and created_by_user_id is not None:
        created_by_seat_id = (
            Seat.query.filter_by(class_id=class_id, role="teacher", user_id=created_by_user_id)
            .order_by(Seat.id.asc())
            .with_entities(Seat.id)
            .scalar()
        )
    if created_by_seat_id is None:
        created_by_seat_id = (
            Seat.query.filter_by(class_id=class_id, role="teacher")
            .order_by(Seat.id.asc())
            .with_entities(Seat.id)
            .scalar()
        )
    if created_by_seat_id is None:
        raise ValueError(
            f"No teacher seat found for class {class_id}. A valid teacher seat is required to record a rent waiver."
        )

    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="RENT_WAIVER",
        amount_snap=Decimal("0.00"),
        due_at=waiver_start_date,
        assessed_at=now,
        coverage_start_time=waiver_start_date,
        coverage_end_time=waiver_end_date,
        cycle_idempotency_key=f"rent-waiver:{seat_id}:{class_id}:{waiver_start_date.isoformat()}",
    )
    db.session.add(assessment)
    db.session.flush()

    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="REVERSED",
            updated_at=now,
        )
    )
    db.session.add(
        ObligationReversal(
            assessment_id=assessment.id,
            reason=reason,
            reversed_at=now,
            reversed_by_seat_id=created_by_seat_id,
        )
    )
    return assessment


# ---------------------------------------------------------------------------
# Insurance mutations
# ---------------------------------------------------------------------------

def record_insurance_enrollment(
    *,
    seat_id: int,
    class_id: str,
    policy,
    purchase_date,
    next_payment_due,
    coverage_start_date,
) -> ObligationAssessment:
    """Record the canonical insurance enrollment as an assessment event."""
    now = utc_now()
    amount_snap = getattr(policy, "premium", None)
    if amount_snap is None:
        amount_snap = 0
    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="INSURANCE_PREMIUM",
        amount_snap=amount_snap,
        due_at=next_payment_due,
        assessed_at=now,
        policy_version_id=getattr(policy, "id", None),
        coverage_start_time=coverage_start_date,
        cycle_idempotency_key=f"insurance-enrollment:{seat_id}:{class_id}:{getattr(policy, 'id', 'unknown')}",
    )
    db.session.add(assessment)
    db.session.flush()
    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="DUE",
            updated_at=now,
        )
    )
    return assessment


def record_insurance_premium_payment(
    *,
    seat_id: int,
    class_id: str,
    policy_version_id: int | None,
    amount_paid,
    due_at,
    coverage_start_time=None,
    coverage_end_time=None,
    cycle_idempotency_key: str | None = None,
    transaction_id: int | None = None,
) -> ObligationAssessment:
    """Record a seat-scoped recurring insurance premium as a canonical assessment + satisfaction."""
    now = utc_now()
    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="INSURANCE_PREMIUM",
        amount_snap=amount_paid,
        due_at=due_at,
        assessed_at=now,
        coverage_start_time=coverage_start_time,
        coverage_end_time=coverage_end_time,
        cycle_idempotency_key=cycle_idempotency_key,
        policy_version_id=policy_version_id,
    )
    db.session.add(assessment)
    db.session.flush()

    db.session.add(
        ObligationLifecycle(
            assessment_id=assessment.id,
            status="PAID",
            updated_at=now,
        )
    )
    db.session.add(
        ObligationSatisfaction(
            assessment_id=assessment.id,
            method="PAYMENT",
            amount_paid=amount_paid,
            was_late=False,
            late_fee_charged=Decimal("0.00"),
            transaction_id=transaction_id,
            satisfied_at=now,
        )
    )
    return assessment


def record_insurance_claim(
    *,
    enrollment_id: int,
    policy_id: int,
    seat_id: int,
    class_id: str,
    incident_date,
    description: str,
    claim_amount,
    claim_item: str | None,
    comments: str | None,
    transaction_id: int | None,
) -> ObligationAssessment:
    """Legacy insurance claim mutation is no longer supported."""
    raise NotImplementedError("Insurance claim rows have been removed")


def apply_claim_resolution(
    claim: ObligationAssessment,
    *,
    status: str,
    teacher_notes: str | None,
    rejection_reason: str | None,
    processed_by_user_id: int | None,
    processed_at,
    approved_amount=None,
    processed_by_seat_id: int | None = None,
):
    """Legacy insurance claim resolution is no longer supported."""
    raise NotImplementedError("Insurance claim resolution rows have been removed")


# ---------------------------------------------------------------------------
# Canonical read helpers
# ---------------------------------------------------------------------------

def has_rent_coverage(
    seat_id: int,
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> bool:
    """Check whether a seat has a PAID rent assessment for the given cycle."""
    return (
        db.session.query(ObligationAssessment.id)
        .join(ObligationLifecycle, ObligationLifecycle.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
            ObligationAssessment.coverage_month == coverage_month,
            ObligationAssessment.coverage_year == coverage_year,
            ObligationLifecycle.status == "PAID",
        )
        .first()
    ) is not None


def get_rent_payments_for_cycle(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> list[ObligationAssessment]:
    """Return all PAID rent assessments for a class + cycle."""
    return (
        ObligationAssessment.query
        .join(ObligationLifecycle, ObligationLifecycle.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
            ObligationAssessment.coverage_month == coverage_month,
            ObligationAssessment.coverage_year == coverage_year,
            ObligationLifecycle.status == "PAID",
        )
        .order_by(ObligationAssessment.assessed_at.asc())
        .all()
    )


def get_rent_payment_history(
    seat_id: int,
    class_id: str,
    *,
    limit: int | None = None,
) -> list[ObligationAssessment]:
    """Return rent assessments for a seat, newest first."""
    q = (
        ObligationAssessment.query
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
        )
        .order_by(ObligationAssessment.assessed_at.desc())
    )
    if limit is not None:
        q = q.limit(limit)
    return q.all()


def has_active_rent_waiver(
    seat_id: int,
    class_id: str,
    coverage_date,
) -> bool:
    """Check whether a seat has a canonical rent waiver covering the given date."""
    return (
        db.session.query(ObligationAssessment.id)
        .join(ObligationReversal, ObligationReversal.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT_WAIVER",
            ObligationAssessment.coverage_start_time <= coverage_date,
            ObligationAssessment.coverage_end_time >= coverage_date,
        )
        .first()
    ) is not None


def get_claim_status(claim_id: int) -> str | None:
    """Return the canonical lifecycle status for an insurance claim."""
    assessment = (
        ObligationAssessment.query
        .filter_by(
            obligation_type="INSURANCE_CLAIM",
            cycle_idempotency_key=_claim_assessment_key(claim_id),
        )
        .first()
    )
    if assessment is None:
        return None
    return assessment.lifecycle.status if assessment.lifecycle else None


# ---------------------------------------------------------------------------
# Rent read helpers for canonical obligation assessments
# ---------------------------------------------------------------------------

def get_paid_rent_assessments_for_cycle(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
    *,
    seat_ids: list[int] | None = None,
) -> list[ObligationAssessment]:
    """Return PAID rent assessments for a class + cycle, optionally filtered by seats.

    Each returned assessment has a loaded `satisfaction` relationship with
    `amount_paid`, `was_late`, `late_fee_charged`, `transaction_id`, and
    `satisfied_at` (the canonical equivalent of ``payment_date``).
    """
    from app.models import Transaction

    q = (
        ObligationAssessment.query
        .join(ObligationLifecycle, ObligationLifecycle.assessment_id == ObligationAssessment.id)
        .outerjoin(ObligationSatisfaction, ObligationSatisfaction.assessment_id == ObligationAssessment.id)
        .outerjoin(Transaction, Transaction.id == ObligationSatisfaction.transaction_id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT",
            ObligationAssessment.coverage_month == coverage_month,
            ObligationAssessment.coverage_year == coverage_year,
            ObligationLifecycle.status == "PAID",
        )
    )
    if seat_ids is not None:
        q = q.filter(ObligationAssessment.seat_id.in_(seat_ids))
    # Exclude assessments whose backing ledger transaction was voided
    q = q.filter(
        db.or_(
            ObligationSatisfaction.transaction_id.is_(None),
            Transaction.is_void.is_(False),
        )
    )
    return q.order_by(ObligationAssessment.assessed_at.asc()).all()


def get_waived_seat_ids_for_cycle(
    class_id: str,
    coverage_date,
    seat_ids: list[int],
) -> set[int]:
    """Return the set of seat_ids that have a canonical rent waiver covering ``coverage_date``."""
    rows = (
        db.session.query(ObligationAssessment.seat_id)
        .join(ObligationReversal, ObligationReversal.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT_WAIVER",
            ObligationAssessment.seat_id.in_(seat_ids),
            ObligationAssessment.coverage_start_time <= coverage_date,
            ObligationAssessment.coverage_end_time >= coverage_date,
        )
        .all()
    )
    return {r[0] for r in rows}


def get_rent_waiver_for_seat(
    seat_id: int,
    class_id: str,
    coverage_date,
) -> ObligationAssessment | None:
    """Return the canonical rent waiver assessment covering ``coverage_date``, if any."""
    return (
        ObligationAssessment.query
        .join(ObligationReversal, ObligationReversal.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT_WAIVER",
            ObligationAssessment.coverage_start_time <= coverage_date,
            ObligationAssessment.coverage_end_time >= coverage_date,
        )
        .order_by(ObligationAssessment.assessed_at.desc())
        .first()
    )


def get_rent_waivers_for_seat(
    seat_id: int,
    class_id: str,
) -> list[ObligationAssessment]:
    """Return all rent waiver assessments for a seat, newest first."""
    return (
        ObligationAssessment.query
        .join(ObligationReversal, ObligationReversal.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT_WAIVER",
        )
        .order_by(ObligationAssessment.assessed_at.desc())
        .all()
    )


def get_active_rent_waivers_for_class(
    class_id: str,
    *,
    coverage_date=None,
    seat_ids: list[int] | None = None,
) -> list[ObligationAssessment]:
    """Return active rent-waiver assessments for a class at a point in time."""
    if coverage_date is None:
        coverage_date = utc_now()
    q = (
        ObligationAssessment.query
        .join(ObligationReversal, ObligationReversal.assessment_id == ObligationAssessment.id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == "RENT_WAIVER",
            ObligationAssessment.coverage_start_time <= coverage_date,
            ObligationAssessment.coverage_end_time >= coverage_date,
        )
    )
    if seat_ids is not None:
        q = q.filter(ObligationAssessment.seat_id.in_(seat_ids))
    return q.order_by(ObligationAssessment.assessed_at.desc()).all()


def remove_rent_waiver_assessment(assessment_id: int) -> ObligationAssessment | None:
    """Delete a canonical rent-waiver assessment and its derived rows."""
    assessment = db.session.get(ObligationAssessment, assessment_id)
    if assessment is None or assessment.obligation_type != "RENT_WAIVER":
        return None

    if assessment.reversal is not None:
        db.session.delete(assessment.reversal)
    if assessment.satisfaction is not None:
        db.session.delete(assessment.satisfaction)
    if assessment.lifecycle is not None:
        db.session.delete(assessment.lifecycle)
    db.session.delete(assessment)
    return assessment


def remove_rent_payment_assessment(assessment_id: int) -> ObligationAssessment | None:
    """Delete a canonical rent-payment assessment and its derived rows."""
    assessment = db.session.get(ObligationAssessment, assessment_id)
    if assessment is None or assessment.obligation_type != "RENT":
        return None

    if assessment.satisfaction is not None:
        db.session.delete(assessment.satisfaction)
    if assessment.reversal is not None:
        db.session.delete(assessment.reversal)
    if assessment.lifecycle is not None:
        db.session.delete(assessment.lifecycle)
    db.session.delete(assessment)
    return assessment


def get_cycle_rent_amount(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> "Decimal | None":
    """Return the policy-defined rent amount for a cycle."""
    return get_cycle_rent_amount_from_version(class_id, coverage_month, coverage_year)


# ---------------------------------------------------------------------------
# Rent helpers
# ---------------------------------------------------------------------------

def get_cycle_rent_amount_from_version(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> "Decimal | None":
    """Return the canonical rent amount for a cycle from RentSettings."""
    settings = RentSettings.query.filter_by(class_id=class_id).first()
    if settings is None:
        return None
    return settings.rent_amount


# ---------------------------------------------------------------------------
# Entitlement mutations
# ---------------------------------------------------------------------------

def record_entitlement_grant(
    *,
    seat_id: int,
    class_id: str,
    quantity: int,
    trigger_id: str | None = None,
    correlation_id: str | None = None,
    assessment_id: int | None = None,
) -> EntitlementEvent:
    """Record a GRANT entitlement event for obligation-linked perks (e.g., hall passes from rent)."""
    event = EntitlementEvent(
        seat_id=seat_id,
        class_id=class_id,
        assessment_id=assessment_id,
        trigger_id=trigger_id,
        correlation_id=correlation_id or generate_correlation_id(),
        quantity_delta=quantity,
        event_type="GRANT",
        occurred_at=utc_now(),
    )
    db.session.add(event)
    return event
