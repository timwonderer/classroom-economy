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
