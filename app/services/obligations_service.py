from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.feats.base import generate_correlation_id
from app.models import (
    EntitlementEvent,
    ObligationAssessment,
    ObligationLifecycle,
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
            event_type='ASSESSMENT',
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
        event_type='ASSESSMENT',
        due_at=incident_date,
        assessed_at=assessed_at,
        cycle_idempotency_key=_claim_assessment_key(claim_id),
        internal_ref=_claim_assessment_key(claim_id),
        correlation_id=generate_correlation_id(),
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
    """Record a rent payment as a canonical PAYMENT event in assessment_events (DOM-OBL-001).

    Creates a PAYMENT event linked to the assessment correlation, with Ledger transaction reference.
    """
    now = utc_now()
    period_key = f"{coverage_year}-{coverage_month:02d}" if coverage_year is not None and coverage_month is not None else None
    rent_settings = RentSettings.query.filter_by(class_id=class_id).first()
    if rent_settings is None:
        raise ValueError(f"RentSettings for class {class_id} not found")

    # Create PAYMENT event
    payment_event = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        period=period,
        event_type='PAYMENT',
        obligation_type="RENT",
        assessed_at=now,
        ledger_transaction_id=transaction_id,
        period_key=period_key,
        coverage_start_time=coverage_start_time,
        coverage_end_time=coverage_end_time,
        cycle_idempotency_key=cycle_idempotency_key,
        period_month=period_month,
        period_year=period_year,
        coverage_month=coverage_month,
        coverage_year=coverage_year,
        internal_ref=f"rent:{class_id}:{period_key}" if period_key else f"rent:{class_id}",
        correlation_id=generate_correlation_id(),
    )
    db.session.add(payment_event)
    db.session.flush()

    db.session.add(
        ObligationLifecycle(
            assessment_id=payment_event.id,
            status="PAID",
            updated_at=now,
        )
    )
    return payment_event


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
    """Record a rent waiver as a canonical WAIVED event in assessment_events (DOM-OBL-001)."""
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

    # Create WAIVED event
    waiver_event = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="RENT",
        event_type='WAIVED',
        due_at=waiver_start_date,
        assessed_at=now,
        coverage_start_time=waiver_start_date,
        coverage_end_time=waiver_end_date,
        cycle_idempotency_key=f"rent-waiver:{seat_id}:{class_id}:{waiver_start_date.isoformat()}",
        reason=reason,
        reversed_by_seat_id=created_by_seat_id,
        internal_ref=f"rent:{class_id}:waiver",
        correlation_id=generate_correlation_id(),
    )
    db.session.add(waiver_event)
    db.session.flush()

    db.session.add(
        ObligationLifecycle(
            assessment_id=waiver_event.id,
            status="WAIVED",
            updated_at=now,
        )
    )
    return waiver_event


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
    """Record the canonical insurance enrollment as an ASSESSMENT event."""
    now = utc_now()
    assessment = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="INSURANCE_PREMIUM",
        event_type='ASSESSMENT',
        due_at=next_payment_due,
        assessed_at=now,
        policy_version_id=getattr(policy, "id", None),
        coverage_start_time=coverage_start_date,
        cycle_idempotency_key=f"insurance-enrollment:{seat_id}:{class_id}:{getattr(policy, 'id', 'unknown')}",
        internal_ref=f"insurance:{class_id}:{getattr(policy, 'id', 'unknown')}",
        correlation_id=generate_correlation_id(),
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
    """Record a seat-scoped recurring insurance premium as a PAYMENT event (DOM-OBL-001)."""
    now = utc_now()
    payment_event = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="INSURANCE_PREMIUM",
        event_type='PAYMENT',
        due_at=due_at,
        assessed_at=now,
        coverage_start_time=coverage_start_time,
        coverage_end_time=coverage_end_time,
        cycle_idempotency_key=cycle_idempotency_key,
        policy_version_id=policy_version_id,
        ledger_transaction_id=transaction_id,
        internal_ref=f"insurance:{class_id}:{policy_version_id}",
        correlation_id=generate_correlation_id(),
    )
    db.session.add(payment_event)
    db.session.flush()

    db.session.add(
        ObligationLifecycle(
            assessment_id=payment_event.id,
            status="PAID",
            updated_at=now,
        )
    )
    return payment_event


def record_insurance_claim_assessment(
    *,
    seat_id: int,
    class_id: str,
    claim_id: int,
    claim_amount,
    incident_date,
) -> ObligationAssessment:
    """Record insurance claim as ASSESSMENT event."""
    assessment = _create_claim_assessment(
        seat_id=seat_id,
        class_id=class_id,
        claim_id=claim_id,
        claim_amount=claim_amount,
        incident_date=incident_date,
        assessed_at=utc_now(),
    )
    return assessment


def record_insurance_claim_payment(
    *,
    seat_id: int,
    class_id: str,
    claim_id: int,
    payment_amount,
    transaction_id: int | None = None,
) -> ObligationAssessment:
    """Record insurance claim payment as PAYMENT event."""
    now = utc_now()
    assessment = _require_claim_assessment(claim_id, seat_id, class_id)

    payment_event = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="INSURANCE_CLAIM",
        event_type='PAYMENT',
        assessed_at=now,
        ledger_transaction_id=transaction_id,
        cycle_idempotency_key=f"insurance-claim-payment:{claim_id}",
        internal_ref=_claim_assessment_key(claim_id),
        correlation_id=generate_correlation_id(),
    )
    db.session.add(payment_event)
    db.session.flush()

    _set_assessment_lifecycle(payment_event, status="PAID", updated_at=now)
    return payment_event


def record_insurance_reversal(
    *,
    seat_id: int,
    class_id: str,
    claim_id: int,
    reason: str | None = None,
    reversed_by_seat_id: int | None = None,
) -> ObligationAssessment:
    """Record insurance claim reversal as REVERSED event."""
    now = utc_now()
    assessment = _require_claim_assessment(claim_id, seat_id, class_id)

    reversal_event = ObligationAssessment(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type="INSURANCE_CLAIM",
        event_type='REVERSED',
        assessed_at=now,
        reason=reason,
        reversed_by_seat_id=reversed_by_seat_id,
        cycle_idempotency_key=f"insurance-claim-reversal:{claim_id}",
        internal_ref=_claim_assessment_key(claim_id),
        correlation_id=generate_correlation_id(),
    )
    db.session.add(reversal_event)
    db.session.flush()

    _set_assessment_lifecycle(reversal_event, status="REVERSED", updated_at=now)
    return reversal_event


# ---------------------------------------------------------------------------
# Rent Assessment Queries (v2 schema - event_type discriminator)
# ---------------------------------------------------------------------------

def get_rent_assessments_for_cycle(
    class_id: str,
    month: int,
    year: int,
    seat_ids: list[int] | None = None,
) -> list[ObligationAssessment]:
    """Get all ASSESSMENT events for a rent cycle (month/year).

    Returns only ASSESSMENT events (event_type='ASSESSMENT') for the given month/year.
    Optionally filter by seat_ids.
    """
    query = ObligationAssessment.query.filter_by(
        class_id=class_id,
        obligation_type='RENT',
        event_type='ASSESSMENT',
        period_month=month,
        period_year=year,
    )

    if seat_ids:
        query = query.filter(ObligationAssessment.seat_id.in_(seat_ids))

    return query.all()


def get_payment_events_for_assessment(
    assessment_id: int,
    class_id: str,
) -> list[ObligationAssessment]:
    """Get all PAYMENT events linked to an assessment (via internal_ref).

    ASSESSMENT events have an internal_ref (e.g., 'rent:class-id:2026-01').
    PAYMENT events for the same ref represent payments against that assessment.
    """
    assessment = ObligationAssessment.query.get(assessment_id)
    if not assessment or not assessment.internal_ref:
        return []

    return ObligationAssessment.query.filter_by(
        class_id=class_id,
        obligation_type='RENT',
        event_type='PAYMENT',
        internal_ref=assessment.internal_ref,
    ).all()


def get_total_paid_for_assessment(
    assessment_id: int,
    class_id: str,
) -> Decimal:
    """Sum amounts from all PAYMENT events for an assessment (via Ledger).

    Per DOM-OBL-001, amounts are stored in Ledger, not in obligations.
    Each PAYMENT event has a ledger_transaction_id pointing to the transaction.
    """
    from app.models import Transaction

    payment_events = get_payment_events_for_assessment(assessment_id, class_id)
    total = Decimal('0.00')

    for payment in payment_events:
        if payment.ledger_transaction_id:
            txn = db.session.get(Transaction, payment.ledger_transaction_id)
            if txn and txn.type == 'credit':
                total += txn.amount

    return total


def get_waived_event_for_assessment(
    assessment_id: int,
    class_id: str,
) -> ObligationAssessment | None:
    """Get the WAIVED event for an assessment (if any).

    Returns the WAIVED event (event_type='WAIVED') for this assessment's internal_ref.
    """
    assessment = ObligationAssessment.query.get(assessment_id)
    if not assessment or not assessment.internal_ref:
        return None

    return ObligationAssessment.query.filter_by(
        class_id=class_id,
        obligation_type='RENT',
        event_type='WAIVED',
        internal_ref=assessment.internal_ref,
    ).first()


def get_rent_payment_history(
    seat_id: int,
    class_id: str,
    limit: int = 24,
) -> list[tuple[ObligationAssessment, list[ObligationAssessment]]]:
    """Get payment history for a seat: list of (ASSESSMENT event, [PAYMENT/WAIVED/REVERSED events]).

    Returns pairs of (assessment_event, state_change_events) in reverse chronological order.
    Limit defaults to 24 most recent assessment cycles.
    """
    # Get all ASSESSMENT events for this seat/class, ordered by coverage period
    assessments = (
        ObligationAssessment.query.filter_by(
            seat_id=seat_id,
            class_id=class_id,
            obligation_type='RENT',
            event_type='ASSESSMENT',
        )
        .order_by(
            ObligationAssessment.period_year.desc(),
            ObligationAssessment.period_month.desc(),
        )
        .limit(limit)
        .all()
    )

    history = []
    for assessment in assessments:
        # Get all state-change events for this assessment's internal_ref
        state_events = ObligationAssessment.query.filter_by(
            class_id=class_id,
            obligation_type='RENT',
            internal_ref=assessment.internal_ref,
        ).filter(ObligationAssessment.event_type.in_(['PAYMENT', 'WAIVED', 'REVERSED'])).all()

        history.append((assessment, state_events))

    return history


def get_rent_waivers_for_seat(
    seat_id: int,
    class_id: str,
) -> list[ObligationAssessment]:
    """Get all WAIVED events for a seat."""
    return ObligationAssessment.query.filter_by(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type='RENT',
        event_type='WAIVED',
    ).order_by(ObligationAssessment.assessed_at.desc()).all()
