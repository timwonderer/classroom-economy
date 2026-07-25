"""
Obligation View Models — Cross-Domain Composition

Derives presentation-ready obligation status by composing:
- Obligations domain: PAYMENT event references (ledger_transaction_id)
- Ledger domain: authoritative Transaction amounts
- Per DOM-OBL-001 §VIII: paid_amount = sum(Ledger amounts from PAYMENT events)

This is NOT a domain service. It is a composition layer that joins two
authoritative sources for presentation/read-model use.

Routes and templates call this layer to build complete obligation views.
Obligations and Ledger services remain isolated and own their own facts.
"""

from __future__ import annotations

from decimal import Decimal
from dataclasses import dataclass

from app.extensions import db
from app.models import ObligationAssessment, Transaction


@dataclass(frozen=True)
class ObligationPaymentStatus:
    """Complete payment status derived from Obligations + Ledger facts."""
    correlation_id: str
    is_satisfied: bool
    is_outstanding: bool
    is_past_due: bool
    total_paid: Decimal
    amount_waived: bool


def get_obligation_payment_status(
    correlation_id: str,
    class_id: str,
    assessed_amount: Decimal | None = None,
) -> ObligationPaymentStatus | None:
    """
    Derive complete payment status by composing Obligations and Ledger truth.

    Per DOM-OBL-001 §VIII:
    - Retrieves PAYMENT events from assessment_events (Obligations domain)
    - Reads Transaction amounts from Ledger domain via ledger_transaction_id FK
    - Sums authoritative Ledger amounts to compute total_paid
    - Derives satisfaction: (paid_amount >= assessed_amount) OR (has_waiver)

    Args:
        correlation_id: Identifies the individual liability
        class_id: Scope for multi-tenancy
        assessed_amount: If provided, used for satisfaction computation

    Returns:
        Complete payment status, or None if assessment not found
    """
    from app.services import obligations_service

    # Step 1: Retrieve the ASSESSMENT event from Obligations domain
    assessment = obligations_service.get_assessment_for_correlation(correlation_id)
    if not assessment:
        return None

    # Step 2: Retrieve all PAYMENT and WAIVED events from Obligations domain
    satisfaction_events = obligations_service.get_satisfaction_events(correlation_id)

    # Step 3: Compose with Ledger domain - sum authoritative Transaction amounts
    total_paid = Decimal('0.00')
    has_waiver = False

    for event in satisfaction_events:
        if event.event_type == 'PAYMENT' and event.ledger_transaction_id:
            # CROSS-DOMAIN READ: Ledger provides authoritative monetary truth
            # (per DOM-OBL-001 §XI: Obligations consumes Ledger for settlement truth)
            txn = db.session.get(Transaction, event.ledger_transaction_id)
            if txn and txn.status != 'void':
                total_paid += Decimal(str(txn.amount))
        elif event.event_type == 'WAIVED':
            has_waiver = True

    # Step 4: Derive satisfaction per DOM-OBL-001 §VIII
    if assessed_amount is None:
        assessed_amount = Decimal('0.00')

    is_satisfied = has_waiver or (total_paid >= assessed_amount)
    is_outstanding = not is_satisfied
    is_past_due = (
        is_outstanding and assessment.due_at
        and db.session.query(db.func.now()).scalar() > assessment.due_at
    )

    return ObligationPaymentStatus(
        correlation_id=correlation_id,
        is_satisfied=is_satisfied,
        is_outstanding=is_outstanding,
        is_past_due=is_past_due,
        total_paid=total_paid,
        amount_waived=has_waiver,
    )


def get_total_paid_for_obligation(
    correlation_id: str,
    class_id: str,
) -> Decimal:
    """
    Convenience: get just the total paid amount for an obligation.

    Routes that only need payment total (not full status) can call this
    instead of get_obligation_payment_status and extracting the amount.

    Returns 0.00 if obligation not found.
    """
    status = get_obligation_payment_status(correlation_id, class_id)
    if not status:
        return Decimal('0.00')
    return status.total_paid


# ============================================================================
# Rent-Specific View Models (Phase 5: Read Models and Projections)
# ============================================================================

@dataclass(frozen=True)
class RentAssessmentView:
    """Single rent obligation assessment with derived status."""
    correlation_id: str
    assessment_id: int
    seat_id: int
    class_id: str
    due_at: object  # datetime
    assessed_amount: Decimal
    is_satisfied: bool
    is_outstanding: bool
    is_past_due: bool
    total_paid: Decimal
    amount_waived: bool
    payment_events: list
    waiver_event: object  # ObligationAssessment or None


@dataclass(frozen=True)
class RentStatusView:
    """Aggregated rent status for a seat in a class."""
    seat_id: int
    class_id: str
    all_assessments: list[RentAssessmentView]
    current_period_assessment: RentAssessmentView | None
    current_period_satisfied: bool
    active_waivers: list[object]  # List of WAIVED events
    total_paid_all_periods: Decimal
    total_assessed_all_periods: Decimal
    payment_history: list[object]  # Chronological list of events


def get_rent_assessments_for_seat_class(
    seat_id: int,
    class_id: str,
) -> list[RentAssessmentView]:
    """
    Get all rent ASSESSMENT events for a seat in a class with derived status.

    Per DOM-OBL-001: Returns immutable assessment facts with computed satisfaction.
    Returns in chronological order (created_at ascending).

    Args:
        seat_id: The seat receiving rent obligations
        class_id: The class scope

    Returns:
        List of RentAssessmentView objects
    """
    from app.services import obligations_service

    # Retrieve all rent ASSESSMENT events for this seat/class
    assessments = obligations_service.get_assessment_events_for_seat_class(
        seat_id=seat_id,
        class_id=class_id,
        obligation_type='RENT'
    )

    result = []
    for assessment in assessments:
        if assessment.event_type != 'ASSESSMENT':
            continue

        # Get satisfaction events for this assessment
        satisfaction_events = obligations_service.get_satisfaction_events(assessment.correlation_id)

        # Compute paid amount from PAYMENT events via Ledger
        total_paid = Decimal('0.00')
        payment_events = []
        has_waiver = False
        waiver_event = None

        for event in satisfaction_events:
            if event.event_type == 'PAYMENT' and event.ledger_transaction_id:
                # Read Ledger truth via FK
                txn = db.session.get(Transaction, event.ledger_transaction_id)
                if txn and txn.status != 'void':
                    total_paid += Decimal(str(txn.amount))
                payment_events.append(event)
            elif event.event_type == 'WAIVED':
                has_waiver = True
                waiver_event = event

        # Derive satisfaction
        assessed_amount = assessment.assessed_at or Decimal('0.00')
        is_satisfied = has_waiver or (total_paid >= Decimal(str(assessed_amount)))
        is_outstanding = not is_satisfied

        # Temporal check for past-due (caller can also check this via due_at)
        is_past_due = (
            is_outstanding
            and assessment.due_at
            and db.session.query(db.func.now()).scalar() > assessment.due_at
        )

        view = RentAssessmentView(
            correlation_id=assessment.correlation_id,
            assessment_id=assessment.id,
            seat_id=seat_id,
            class_id=class_id,
            due_at=assessment.due_at,
            assessed_amount=Decimal(str(assessed_amount)),
            is_satisfied=is_satisfied,
            is_outstanding=is_outstanding,
            is_past_due=is_past_due,
            total_paid=total_paid,
            amount_waived=has_waiver,
            payment_events=payment_events,
            waiver_event=waiver_event,
        )
        result.append(view)

    return result


def get_rent_status_projection(
    seat_id: int,
    class_id: str,
    current_period_due_at: object = None,
) -> RentStatusView:
    """
    Get aggregated rent status for a seat in a class.

    Composes:
    - All rent ASSESSMENT events
    - Payment/waiver history
    - Current period identification
    - Derived satisfaction state

    Args:
        seat_id: The seat
        class_id: The class scope
        current_period_due_at: Optional datetime to identify "current" period for display

    Returns:
        Complete rent status projection
    """
    assessments = get_rent_assessments_for_seat_class(seat_id, class_id)

    # Find active waivers
    active_waivers = [a.waiver_event for a in assessments if a.waiver_event]

    # Aggregate totals
    total_paid = sum(a.total_paid for a in assessments)
    total_assessed = sum(a.assessed_amount for a in assessments)

    # Identify current period (if provided)
    current_period_assessment = None
    if current_period_due_at:
        for a in assessments:
            if a.due_at == current_period_due_at:
                current_period_assessment = a
                break

    # Build chronological payment history from all events
    payment_history = []
    for assessment in assessments:
        payment_history.extend(assessment.payment_events)
        if assessment.waiver_event:
            payment_history.append(assessment.waiver_event)

    # Sort by created_at
    payment_history.sort(key=lambda e: e.created_at if hasattr(e, 'created_at') else '', reverse=True)

    return RentStatusView(
        seat_id=seat_id,
        class_id=class_id,
        all_assessments=assessments,
        current_period_assessment=current_period_assessment,
        current_period_satisfied=(current_period_assessment.is_satisfied if current_period_assessment else False),
        active_waivers=active_waivers,
        total_paid_all_periods=total_paid,
        total_assessed_all_periods=total_assessed,
        payment_history=payment_history,
    )
