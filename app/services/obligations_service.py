"""
Obligations Service — DOM-OBL-001

Read-only canonical interface for obligation facts and derived state.
Does not perform writes; FEATs own all mutation.
"""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass

from app.extensions import db
from app.models import ObligationAssessment, BillCycle


@dataclass(frozen=True)
class ObligationStatus:
    """Derived obligation status (read-only projection over immutable facts)."""
    correlation_id: str
    seat_id: int
    class_id: str
    obligation_type: str
    event_type: str  # ASSESSMENT | PAYMENT | WAIVED

    # Derived facts (never persisted per DOM-OBL-001 §VIII)
    is_satisfied: bool
    is_outstanding: bool
    due_at: datetime | None  # Caller can compare against current time if needed
    amount_paid: float  # Sum of Ledger amounts from PAYMENT events
    amount_waived: bool  # True if any WAIVED event exists


def get_assessment_for_correlation(correlation_id: str) -> ObligationAssessment | None:
    """
    Retrieve the original ASSESSMENT event for a correlation.

    Per DOM-OBL-001 §VII: exactly one ASSESSMENT per correlation_id.
    """
    return (
        db.session.query(ObligationAssessment)
        .filter_by(correlation_id=correlation_id, event_type='ASSESSMENT')
        .first()
    )


def get_satisfaction_events(correlation_id: str) -> list[ObligationAssessment]:
    """Retrieve all PAYMENT and WAIVED events for a correlation (in order)."""
    return (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.correlation_id == correlation_id,
            ObligationAssessment.event_type.in_(['PAYMENT', 'WAIVED'])
        )
        .order_by(ObligationAssessment.timestamp.asc())
        .all()
    )


def get_obligation_status(correlation_id: str) -> ObligationStatus | None:
    """
    Derive obligation status from immutable facts.

    Per DOM-OBL-001 §VIII, satisfaction is computed as:
    - paid_amount = sum(Ledger amounts from PAYMENT events)
    - has_waiver = exists(WAIVED event)
    - if paid_amount >= assessed_amount: SATISFIED
    - elif has_waiver: SATISFIED
    - else: OUTSTANDING

    Past due = OUTSTANDING and now > due_at
    """
    assessment = get_assessment_for_correlation(correlation_id)
    if not assessment:
        return None

    satisfaction_events = get_satisfaction_events(correlation_id)

    # Compute paid amount from Ledger references
    amount_paid = 0.0
    has_waiver = False

    for event in satisfaction_events:
        if event.event_type == 'PAYMENT' and event.ledger_transaction_id:
            # Read Ledger amount through the FK relationship
            txn = db.session.get(db.Model.__class__, event.ledger_transaction_id)
            if txn and hasattr(txn, 'amount'):
                amount_paid += float(txn.amount)
        elif event.event_type == 'WAIVED':
            has_waiver = True

    # Derive satisfaction per DOM-OBL-001 §VIII
    # Note: assessed_amount defaults to 0 (no amount stored in assessment_events per DOM-OBL-001 v2.5)
    # Caller should use get_obligation_payment_status() from obligation_view_model.py to provide assessed_amount
    assessed_amount = 0.0  # Default; caller should pass actual amount
    is_satisfied = has_waiver or (amount_paid >= assessed_amount)
    is_outstanding = not is_satisfied

    # Per DOM-OBL-001 v2.5: due_at should come from bill_cycles, not assessment_events
    # This legacy function defaults to None; use get_obligation_payment_status() for complete status
    return ObligationStatus(
        correlation_id=correlation_id,
        seat_id=assessment.seat_id,
        class_id=assessment.class_id,
        obligation_type=assessment.obligation_type,
        event_type=assessment.event_type,
        is_satisfied=is_satisfied,
        is_outstanding=is_outstanding,
        due_at=None,  # Per DOM-OBL-001 v2.5: use bill_cycles for due dates
        amount_paid=amount_paid,
        amount_waived=has_waiver,
    )


def get_assessment_events_for_seat_class(
    seat_id: int,
    class_id: str,
    obligation_type: str | None = None,
) -> list[ObligationAssessment]:
    """
    Retrieve all assessment events for a seat in a class.

    Optionally filter by obligation_type (RENT, INSURANCE_PREMIUM).
    Returns in creation order (immutable append-only facts).
    """
    query = (
        db.session.query(ObligationAssessment)
        .filter_by(seat_id=seat_id, class_id=class_id)
    )
    if obligation_type:
        query = query.filter_by(obligation_type=obligation_type)

    return query.order_by(ObligationAssessment.timestamp.asc()).all()


def get_bill_cycles_for_internal_ref(internal_ref: str) -> list[BillCycle]:
    """
    Retrieve all bill cycles for an internal reference.

    Per DOM-OBL-001 §VII.3: identity-blind temporal reminder state.
    Returns in cycle number order.
    """
    return (
        db.session.query(BillCycle)
        .filter_by(internal_ref=internal_ref)
        .order_by(BillCycle.cycle_number.asc())
        .all()
    )


def get_latest_bill_cycle(internal_ref: str) -> BillCycle | None:
    """Get the most recent cycle for an internal reference."""
    return (
        db.session.query(BillCycle)
        .filter_by(internal_ref=internal_ref)
        .order_by(BillCycle.cycle_number.desc())
        .first()
    )


def check_idempotency_assessment(
    internal_ref: str,
    correlation_id: str,
) -> bool:
    """
    Check if an assessment already exists for this lineage.

    Per FEAT-OBLI-001: assessment must be idempotent by (internal_ref, correlation_id).
    Returns True if already exists.
    """
    existing = (
        db.session.query(ObligationAssessment)
        .filter_by(
            internal_ref=internal_ref,
            correlation_id=correlation_id,
            event_type='ASSESSMENT',
        )
        .first()
    )
    return existing is not None


def check_idempotency_satisfaction(
    correlation_id: str,
    method: str,  # 'PAYMENT' or 'WAIVED'
) -> bool:
    """
    Check if a satisfaction of this type already exists.

    Per FEAT-OBL-003: satisfaction must be idempotent by (correlation_id, method).
    Returns True if already exists.
    """
    existing = (
        db.session.query(ObligationAssessment)
        .filter_by(
            correlation_id=correlation_id,
            event_type=method,
        )
        .first()
    )
    return existing is not None


def check_idempotency_bill_cycle(
    internal_ref: str,
    cycle_number: int,
) -> bool:
    """
    Check if a bill cycle already exists.

    Per FEAT-OBL-002: advancement must be idempotent by (internal_ref, cycle_number).
    Returns True if already exists.
    """
    existing = (
        db.session.query(BillCycle)
        .filter_by(internal_ref=internal_ref, cycle_number=cycle_number)
        .first()
    )
    return existing is not None


# ---- Rent-specific read models (domain-aware projections) ----


def get_rent_assessments_for_cycle(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
    seat_ids: list[int] | None = None,
) -> list[ObligationAssessment]:
    """
    Retrieve ASSESSMENT events for rent during a coverage cycle.

    Filtered by class, month/year (for coverage period identification),
    and optionally by seat list.

    Returns events in creation order.
    """
    query = (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == 'RENT',
            ObligationAssessment.event_type == 'ASSESSMENT',
        )
    )

    if seat_ids:
        query = query.filter(ObligationAssessment.seat_id.in_(seat_ids))

    # Filter by month/year on due_at (when the payment was due)
    if coverage_month and coverage_year:
        from sqlalchemy import extract
        query = query.filter(
            extract('month', ObligationAssessment.due_at) == coverage_month,
            extract('year', ObligationAssessment.due_at) == coverage_year,
        )

    return query.order_by(ObligationAssessment.timestamp.asc()).all()


def get_payment_events_for_assessment(
    assessment_id: int,
    class_id: str,
) -> list[ObligationAssessment]:
    """
    Retrieve all PAYMENT events for an assessment.

    Per DOM-OBL-001 §VII.1: multiple PAYMENT rows may exist per assessment.
    Returns in creation order.
    """
    assessment = db.session.get(ObligationAssessment, assessment_id)
    if not assessment:
        return []

    return (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.correlation_id == assessment.correlation_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.event_type == 'PAYMENT',
        )
        .order_by(ObligationAssessment.timestamp.asc())
        .all()
    )




def get_waived_seat_ids_for_cycle(
    class_id: str,
    coverage_due_date: datetime,
    seat_ids: list[int] | None = None,
) -> set[int]:
    """
    Retrieve seat IDs where rent was waived for a coverage cycle.

    Per DOM-OBL-001 §VI: WAIVED is rent-only and closes outstanding remainder.
    Returns set of seat IDs that have active waivers.
    """
    query = (
        db.session.query(ObligationAssessment.seat_id.distinct())
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == 'RENT',
            ObligationAssessment.event_type == 'WAIVED',
        )
    )

    if seat_ids:
        query = query.filter(ObligationAssessment.seat_id.in_(seat_ids))

    # Match by due_at month/year to filter by coverage period
    if coverage_due_date:
        from sqlalchemy import extract
        query = query.filter(
            extract('month', ObligationAssessment.due_at) == coverage_due_date.month,
            extract('year', ObligationAssessment.due_at) == coverage_due_date.year,
        )

    return set(row[0] for row in query.all())


def get_paid_rent_assessments_for_cycle(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
    seat_ids: list[int] | None = None,
) -> list[ObligationAssessment]:
    """Alias for get_rent_assessments_for_cycle() for backward compatibility."""
    return get_rent_assessments_for_cycle(
        class_id,
        coverage_month,
        coverage_year,
        seat_ids=seat_ids,
    )


def get_rent_payment_history(
    seat_id: int,
    class_id: str,
    limit: int = 24,
) -> list[ObligationAssessment]:
    """
    Retrieve rent-related assessment events (ASSESSMENT, PAYMENT, WAIVED)
    for a seat in reverse chronological order.

    Used for displaying payment history in student rent view.
    Limits to most recent N events.
    """
    return (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == 'RENT',
        )
        .order_by(ObligationAssessment.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_rent_waivers_for_seat(
    seat_id: int,
    class_id: str,
) -> list[ObligationAssessment]:
    """Retrieve all active rent waivers for a seat in a class."""
    return (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.seat_id == seat_id,
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == 'RENT',
            ObligationAssessment.event_type == 'WAIVED',
        )
        .order_by(ObligationAssessment.timestamp.desc())
        .all()
    )


def get_cycle_rent_amount(
    class_id: str,
    coverage_month: int,
    coverage_year: int,
) -> float | None:
    """
    STUB: Get rent amount for a cycle.

    This function DOES NOT BELONG in Obligations domain (violates DOM-OBL-001).
    Rent amount is Class Configuration authority, not Obligations authority.

    Obligations domain stores assessment amounts in policy_version_id references
    to the upstream PolicyVersion, not in obligation tables.

    Caller should fetch amount from Class Configuration, pass to assessment creator.

    TODO: Remove this function. Rent amount should be determined upstream by
    Class Configuration and passed to FEAT-OBLI-001 via correlation/policy_version_id.
    """
    return None
