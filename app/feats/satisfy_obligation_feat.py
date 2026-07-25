"""
FEAT-OBL-003: Satisfy Obligation

Records lawful satisfaction of an assessed obligation through payment or waiver.
Per DOM-OBL-001 §IX.2 and FEAT-OBL-003 orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.extensions import db
from app.models import ObligationAssessment
from app.services import obligations_service
from app.feats.base import feat_shell, FEATContext


@dataclass
class SatisfyObligationRequest:
    """Input contract for obligation satisfaction (FEAT-OBL-003 §III)."""
    correlation_id: str  # Identifies the individual liability to satisfy
    class_id: str
    seat_id: int
    method: Literal['PAYMENT', 'WAIVED']  # Satisfaction method
    ledger_transaction_id: int | None = None  # Required for PAYMENT, NULL for WAIVED


def satisfy_obligation(
    request: SatisfyObligationRequest,
    *,
    context: FEATContext,
) -> ObligationAssessment:
    """
    Record lawful satisfaction of an assessed obligation.

    Per DOM-OBL-001 §IX.2:
    - PAYMENT may occur multiple times for partial payment
    - WAIVED is rent-only and closes outstanding remainder
    - WAIVED creates no Ledger movement

    Preconditions:
    - correlation_id identifies an existing ASSESSMENT
    - method is lawful for the assessment type (WAIVED only for RENT)
    - For PAYMENT: ledger_transaction_id references a lawful Ledger row
    - For PAYMENT: Ledger transaction belongs to same class/seat boundary
    - idempotency_key prevents duplicate satisfaction

    Postconditions:
    - exactly one satisfaction row created with event_type=PAYMENT or WAIVED
    - PAYMENT row references the Ledger transaction
    - WAIVED row has no Ledger reference
    - satisfaction rows are immutable

    Raises:
    - ValueError if preconditions violated
    """
    # Phase 1: Verification (read-only)

    # Retrieve the assessment this satisfies
    assessment = obligations_service.get_assessment_for_correlation(request.correlation_id)
    if not assessment:
        raise ValueError(f"Assessment not found for correlation {request.correlation_id}")

    # Scope validation: assessment must match class/seat
    if assessment.class_id != request.class_id or assessment.seat_id != request.seat_id:
        raise ValueError(
            f"Assessment scope mismatch: expected ({request.seat_id}, {request.class_id}), "
            f"got ({assessment.seat_id}, {assessment.class_id})"
        )

    # Method validation per FEAT-OBL-003 §IV.3
    if request.method == 'WAIVED':
        if assessment.obligation_type != 'RENT':
            raise ValueError(f"WAIVED is only lawful for RENT; got {assessment.obligation_type}")

    # For PAYMENT, verify Ledger transaction
    if request.method == 'PAYMENT':
        if not request.ledger_transaction_id:
            raise ValueError("PAYMENT method requires ledger_transaction_id")
        # Ledger transaction scope/validity is verified by caller (Ledger FEAT)

    # Idempotency check: per FEAT-OBL-003, prevent duplicate satisfactions
    if obligations_service.check_idempotency_satisfaction(
        request.correlation_id,
        request.method,
    ):
        # Already satisfied this way; safe replay
        existing = (
            db.session.query(ObligationAssessment)
            .filter_by(
                correlation_id=request.correlation_id,
                event_type=request.method,
            )
            .first()
        )
        return existing

    # Phase 2: Mutation (atomic transaction)

    satisfaction = ObligationAssessment(
        seat_id=request.seat_id,
        class_id=request.class_id,
        internal_ref=assessment.internal_ref,  # Preserve lineage
        correlation_id=request.correlation_id,  # Link to assessment
        event_type=request.method,  # PAYMENT or WAIVED
        obligation_type=assessment.obligation_type,
        policy_version_id=assessment.policy_version_id,
        due_at=assessment.due_at,
        viewable_at=assessment.viewable_at,
        bill_cycle_id=assessment.bill_cycle_id,
        # For PAYMENT, reference the Ledger transaction
        ledger_transaction_id=request.ledger_transaction_id if request.method == 'PAYMENT' else None,
    )

    db.session.add(satisfaction)
    db.session.flush()

    # Phase 3: Note on derived state
    # Satisfaction status (is_satisfied, is_outstanding, etc.) is derived
    # from immutable assessment + satisfaction event history per DOM-OBL-001 §VIII.
    # It is never persisted as a mutable flag on this row.

    return satisfaction


@feat_shell("FEAT-OBL-003")
def execute_satisfy_obligation_payment(
    correlation_id: str,
    class_id: str,
    seat_id: int,
    ledger_transaction_id: int,
) -> ObligationAssessment:
    """
    Public FEAT interface for obligation payment satisfaction.

    Called by Ledger FEAT when a lawful monetary transaction is posted
    toward an obligation.

    The caller (Ledger FEAT) supplies the authoritative ledger_transaction_id
    and must verify scope and lawfulness.

    Returns the immutable PAYMENT satisfaction row.
    """
    request = SatisfyObligationRequest(
        correlation_id=correlation_id,
        class_id=class_id,
        seat_id=seat_id,
        method='PAYMENT',
        ledger_transaction_id=ledger_transaction_id,
    )
    return satisfy_obligation(request, context=FEATContext("FEAT-OBL-003"))


@feat_shell("FEAT-OBL-003")
def execute_satisfy_obligation_waiver(
    correlation_id: str,
    class_id: str,
    seat_id: int,
) -> ObligationAssessment:
    """
    Public FEAT interface for rent obligation waiver.

    Called by authorized administrative route when a teacher lawfully
    waives a rent liability.

    Waiver is rent-only and creates no Ledger movement.

    Returns the immutable WAIVED satisfaction row.
    """
    request = SatisfyObligationRequest(
        correlation_id=correlation_id,
        class_id=class_id,
        seat_id=seat_id,
        method='WAIVED',
        ledger_transaction_id=None,
    )
    return satisfy_obligation(request, context=FEATContext("FEAT-OBL-003"))
