"""
FEAT-OBL-002: Advance Bill Cycle

Creates successor recurring reminder state for obligation sources.
Per DOM-OBL-001 §VII.3 and FEAT-OBL-002 orchestration.
"""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass

from app.extensions import db
from app.models import BillCycle
from app.services import obligations_service
from app.feats.base import feat_shell, FEATContext


@dataclass
class AdvanceBillCycleRequest:
    """Input contract for bill cycle advancement (FEAT-OBL-002 §III)."""
    internal_ref: str  # Stable reference for continuing relationship
    cycle_number: int  # Next cycle number to create
    cycle_boundary_at: datetime  # When this cycle ends
    next_assessment_at: datetime  # When to reassess this reference
    source_version_id: str | None = None  # Lawful version snapshot reference


def advance_bill_cycle(
    request: AdvanceBillCycleRequest,
    *,
    context: FEATContext,
) -> BillCycle:
    """
    Create successor bill cycle for recurring obligation source.

    Per DOM-OBL-001 §VII.3 and FEAT-OBL-002:
    - Bill cycle is identity-blind temporal reminder
    - Does not store monetary amount, business meaning, or seat/class identity
    - Only records that an internal_ref must be reconsidered at a boundary

    Preconditions:
    - internal_ref continues to exist lawfully upstream
    - cycle_number is the logical successor to the current cycle
    - cycle_boundary_at is the terminal boundary of this cycle
    - next_assessment_at is a lawful successor assessment time

    Postconditions:
    - exactly one BillCycle row created with (internal_ref, cycle_number)
    - Unique constraint enforces at most one cycle per (internal_ref, cycle_number)

    Raises:
    - ValueError if idempotency check fails
    - ValueError if temporal constraints violated
    """
    # Phase 1: Verification (read-only)

    # Check idempotency per FEAT-OBL-002 §V.5
    if obligations_service.check_idempotency_bill_cycle(
        request.internal_ref,
        request.cycle_number,
    ):
        # Already exists; safe replay
        existing = (
            db.session.query(BillCycle)
            .filter_by(internal_ref=request.internal_ref, cycle_number=request.cycle_number)
            .first()
        )
        return existing

    # Temporal validation: successor cycle times must be ordered
    if request.next_assessment_at <= request.cycle_boundary_at:
        raise ValueError(
            f"next_assessment_at must be after cycle_boundary_at "
            f"({request.next_assessment_at} <= {request.cycle_boundary_at})"
        )

    # Phase 2: Mutation (atomic transaction)

    bill_cycle = BillCycle(
        internal_ref=request.internal_ref,
        cycle_number=request.cycle_number,
        source_version_id=request.source_version_id,
        cycle_boundary_at=request.cycle_boundary_at,
        next_assessment_at=request.next_assessment_at,
    )

    db.session.add(bill_cycle)
    db.session.flush()

    # Phase 3: Note on terminal case
    # If upstream authority indicates the relationship has terminated,
    # the caller must NOT invoke this FEAT. The terminated relationship
    # produces no successor cycle per FEAT-OBL-002 §IV.3.

    return bill_cycle


@feat_shell("FEAT-OBL-002")
def execute_advance_bill_cycle(
    internal_ref: str,
    cycle_number: int,
    cycle_boundary_at: datetime,
    next_assessment_at: datetime,
    *,
    source_version_id: str | None = None,
) -> BillCycle:
    """
    Public FEAT interface for bill cycle advancement.

    Called by upstream authorities (Class Configuration, entitlement services)
    when lawful recurring progression permits another assessment boundary.

    Returns the successor BillCycle row.
    """
    request = AdvanceBillCycleRequest(
        internal_ref=internal_ref,
        cycle_number=cycle_number,
        cycle_boundary_at=cycle_boundary_at,
        next_assessment_at=next_assessment_at,
        source_version_id=source_version_id,
    )
    return advance_bill_cycle(request, context=FEATContext("FEAT-OBL-002"))
