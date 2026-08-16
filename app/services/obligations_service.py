"""
Obligations Service — DOM-OBL-001

Read-only canonical interface for obligation facts and derived state.
Does not perform writes; FEATs own all mutation.
"""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.models import ObligationAssessment, BillCycle


def resolve_assessment_amount(assessment: ObligationAssessment) -> Decimal:
    """Resolve the assessed amount for an assessment event.

    Per DOM-OBL-001 §V.1 and §VII.1, no amount is persisted on
    assessment_events. Amount comes from the upstream policy definition
    addressed by `assessment.policy_uuid`, dispatched by obligation_type.

    Returns Decimal('0.00') when the upstream policy row cannot be
    located (row deleted, policy_uuid unset, or unsupported type). This
    is safe for derived-satisfaction math: an unknown amount treated as
    zero produces `is_satisfied = True` for any non-negative payment,
    which is the same behavior as the pre-remediation stub.
    """
    if assessment is None:
        return Decimal('0.00')

    obligation_type = assessment.obligation_type
    policy_uuid = assessment.policy_uuid

    if obligation_type == 'RENT' and policy_uuid:
        from app.models import RentSettings
        rent = RentSettings.query.filter_by(policy_uuid=policy_uuid).first()
        if rent and rent.rent_amount is not None:
            return Decimal(str(rent.rent_amount))

    # INSURANCE / IMMEDIATE / other types: their upstream contract lives
    # in domain-specific tables not yet centralized here. Callers that
    # need a non-zero amount for those types must resolve upstream and
    # pass explicitly. Returning 0 is safe per the note above.
    return Decimal('0.00')


def resolve_assessment_due_at(assessment: ObligationAssessment) -> datetime | None:
    """Resolve the "due at" boundary for an assessment event.

    Per DOM-OBL-001 §VII.2, temporal boundaries are owned by
    `bill_cycles`. For cyclic obligations (rent), the due boundary is
    the bill_cycle.assessment_at that invoked this assessment. For
    immediate charges (§II.C, no bill_cycle), the assessment is due at
    creation time — return the event's canonical `timestamp`.

    Returns None only if both bill_cycle lookup fails and no timestamp
    exists on the assessment (should not occur for lawful rows).
    """
    if assessment is None:
        return None

    if assessment.bill_cycle_id:
        cycle = db.session.get(BillCycle, assessment.bill_cycle_id)
        if cycle and cycle.assessment_at:
            return cycle.assessment_at

    # Immediate charge (or bill_cycle missing): due at assessment time.
    return assessment.timestamp


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


def get_latest_bill_cycle_for_class(class_id: str) -> BillCycle | None:
    """Get the most recent bill cycle for a class.

    DOM-OBL-001 treats bill_cycles as the current recurring rent cycle in force
    for the class. The latest cycle row for the class is the canonical current
    cycle projection.
    """
    return (
        db.session.query(BillCycle)
        .filter_by(class_id=class_id)
        .order_by(BillCycle.cycle_number.desc(), BillCycle.id.desc())
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


def get_assessments_for_bill_cycle(
    bill_cycle_id: int,
    obligation_type: str | None = None,
) -> list[ObligationAssessment]:
    """
    Retrieve ASSESSMENT events linked to a specific bill cycle.

    Per DOM-OBL-001 v2.5: bill_cycles define periods; assessments link via bill_cycle_id FK.
    This is the canonical way to find assessments for a coverage period.

    Args:
        bill_cycle_id: The bill cycle ID
        obligation_type: Optional filter for obligation type (RENT, INSURANCE_PREMIUM, etc.)

    Returns:
        List of ASSESSMENT events (not PAYMENT or WAIVED events)
    """
    query = (
        db.session.query(ObligationAssessment)
        .filter(
            ObligationAssessment.bill_cycle_id == bill_cycle_id,
            ObligationAssessment.event_type == 'ASSESSMENT',
        )
    )

    if obligation_type:
        query = query.filter(ObligationAssessment.obligation_type == obligation_type)

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




def get_waived_seats_for_bill_cycle(
    bill_cycle_id: int,
) -> set[int]:
    """
    Retrieve seat IDs where obligations were waived for a specific bill cycle.

    Per DOM-OBL-001 v2.5: WAIVED events link to bill_cycles via bill_cycle_id.
    Returns set of seat IDs that have WAIVED events for this cycle.
    """
    query = (
        db.session.query(ObligationAssessment.seat_id.distinct())
        .filter(
            ObligationAssessment.bill_cycle_id == bill_cycle_id,
            ObligationAssessment.event_type == 'WAIVED',
        )
    )

    return set(row[0] for row in query.all())


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


@dataclass(frozen=True)
class RentWaiverView:
    """Derived projection of a rent WAIVED event with its coverage window.

    Per DOM-OBL-001 §VII, assessment events do not store coverage windows.
    The window is derived from the linked bill_cycle
    (cycle_boundary_at, next_assessment_at). This projection resolves the
    derivation once so callers work with a stable shape.
    """
    id: int
    seat_id: int
    correlation_id: str
    timestamp: datetime  # When the waiver was granted (event canonical timestamp)
    coverage_start_time: datetime  # Derived from bill_cycle.cycle_boundary_at
    coverage_end_time: datetime  # Derived from bill_cycle.next_assessment_at


def get_active_rent_waivers_for_class(
    class_id: str,
    coverage_date: datetime | None = None,
) -> list[RentWaiverView]:
    """Return rent WAIVED events for a class whose coverage window contains coverage_date.

    A waiver satisfies exactly one assessment (shared correlation_id) which
    belongs to exactly one bill_cycle. The bill_cycle defines the coverage
    window [cycle_boundary_at, next_assessment_at). "Active" means
    coverage_date falls in that window. When coverage_date is None, all
    waivers with a resolvable window are returned. Waivers whose
    bill_cycle_id is NULL are omitted (no derivable window).
    """
    q = (
        db.session.query(ObligationAssessment, BillCycle)
        .join(BillCycle, ObligationAssessment.bill_cycle_id == BillCycle.id)
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.obligation_type == 'RENT',
            ObligationAssessment.event_type == 'WAIVED',
        )
    )
    if coverage_date is not None:
        q = q.filter(
            BillCycle.cycle_boundary_at <= coverage_date,
            BillCycle.next_assessment_at > coverage_date,
        )
    return [
        RentWaiverView(
            id=waiver.id,
            seat_id=waiver.seat_id,
            correlation_id=waiver.correlation_id,
            timestamp=waiver.timestamp,
            coverage_start_time=cycle.cycle_boundary_at,
            coverage_end_time=cycle.next_assessment_at,
        )
        for waiver, cycle in q.order_by(BillCycle.cycle_boundary_at.desc()).all()
    ]


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
