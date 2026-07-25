"""
FEAT-OBLI-001: Assess Obligation

Creates immutable ASSESSMENT event for lawful obligation.
Per DOM-OBL-001 §IX.1 and FEAT-OBLI-001 orchestration.
"""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass

from app.extensions import db
from app.models import ObligationAssessment
from app.services import obligations_service
from app.feats.base import feat_shell, FEATContext


@dataclass
class AssessmentRequest:
    """Input contract for obligation assessment (FEAT-OBLI-001 §II)."""
    seat_id: int
    class_id: str
    internal_ref: str  # Stable lineage key for continuing relationship
    correlation_id: str  # Unique ID for this individual liability
    obligation_type: str  # RENT | INSURANCE_PREMIUM
    due_at: datetime
    viewable_at: datetime | None = None
    source_ref: str | None = None  # Opaque upstream authority reference
    source_version_ref: str | None = None  # Immutable version snapshot
    policy_version_id: int | None = None


def assess_obligation(
    request: AssessmentRequest,
    *,
    context: FEATContext,
) -> ObligationAssessment:
    """
    Create immutable ASSESSMENT event for a liability.

    This is the sole legal way to create an obligation under DOM-OBL-001.

    Preconditions:
    - request has valid seat_id, class_id scoped to canonical context
    - internal_ref and correlation_id are lawful per upstream authority
    - correlation_id is globally unique
    - due_at and viewable_at satisfy temporal boundary contract

    Postconditions:
    - exactly one ASSESSMENT row created with event_type='ASSESSMENT'
    - no satisfaction events yet created
    - assessment is immutable

    Raises:
    - ValueError if idempotency check fails (replay safety)
    - ValueError if preconditions violated
    """
    # Phase 1: Verification (read-only)

    # Scope validation: caller MUST resolve seat_id and class_id via CanonicalContext
    # and pass both. Obligations domain only validates within assessment_events/bill_cycles
    # tables per DOM-OBL-001 §VI. Cross-domain Seat validation belongs to caller.

    # Lineage validation: check idempotency
    if obligations_service.check_idempotency_assessment(
        request.internal_ref,
        request.correlation_id,
    ):
        # Already exists; this is safe replay per FEAT-OBLI-001
        existing = obligations_service.get_assessment_for_correlation(request.correlation_id)
        return existing

    # Temporal validation: upstream authority should have validated due_at
    if request.due_at and request.viewable_at:
        if request.viewable_at > request.due_at:
            raise ValueError("viewable_at cannot be after due_at")

    # Phase 2: Mutation (atomic transaction)

    assessment = ObligationAssessment(
        seat_id=request.seat_id,
        class_id=request.class_id,
        internal_ref=request.internal_ref,
        correlation_id=request.correlation_id,
        event_type='ASSESSMENT',
        obligation_type=request.obligation_type,
        policy_version_id=request.policy_version_id,
        due_at=request.due_at,
        viewable_at=request.viewable_at,
        # ledger_transaction_id is NULL for ASSESSMENT (only filled for PAYMENT)
        # bill_cycle_id is NULL initially (linked later if recurring)
    )

    db.session.add(assessment)
    db.session.flush()  # Get the ID before commit

    # Phase 3: Audit trace
    # Per FEAT-OBLI-001 §V, emit ACT-OBLI-001 via DOM-OPS
    # (OPS audit integration deferred to next phase)

    return assessment


@feat_shell("FEAT-OBLI-001")
def execute_assess_obligation(
    seat_id: int,
    class_id: str,
    internal_ref: str,
    correlation_id: str,
    obligation_type: str,
    due_at: datetime,
    *,
    viewable_at: datetime | None = None,
    source_ref: str | None = None,
    source_version_ref: str | None = None,
    policy_version_id: int | None = None,
) -> ObligationAssessment:
    """
    Public FEAT interface for obligation assessment.

    Callable from routes and other FEATs. Wraps assess_obligation() with
    context and transaction management per feat_shell.

    Returns the immutable ASSESSMENT row.
    """
    request = AssessmentRequest(
        seat_id=seat_id,
        class_id=class_id,
        internal_ref=internal_ref,
        correlation_id=correlation_id,
        obligation_type=obligation_type,
        due_at=due_at,
        viewable_at=viewable_at,
        source_ref=source_ref,
        source_version_ref=source_version_ref,
        policy_version_id=policy_version_id,
    )
    return assess_obligation(request, context=FEATContext("FEAT-OBLI-001"))
