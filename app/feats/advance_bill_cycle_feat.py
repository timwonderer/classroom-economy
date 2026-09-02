"""
FEAT-OBL-002: Advance Bill Cycle

Creates the strictly sequential SUCCESSOR recurring reminder state for an
obligation source that already has a current cycle. Advancement is not genesis:

    genesis:      nothing  -> cycle 1     (establish_bill_cycle — separate command)
    advancement:  cycle N  -> cycle N+1   (this FEAT)

The successor number is derived from authoritative Obligations state; advancement
requires a prior cycle and refuses to create cycle 1. Per DOM-OBL-001 §VII.3 and
FEAT-OBL-002 orchestration.
"""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass

from app.extensions import db
from app.models import BillCycle
from app.services import obligations_service
from app.services.obligations_service import BillCycleLifecycleError
from app.feats.base import requires_feat_context, FEATContext


@dataclass
class AdvanceBillCycleRequest:
    """Input contract for bill cycle advancement (FEAT-OBL-002 §III)."""
    class_id: str  # Multi-tenancy scope (required per INV-CORE-000)
    internal_ref: str  # Stable reference for continuing relationship
    cycle_number: int  # Next cycle number to create
    cycle_boundary_at: datetime  # When this cycle ends
    next_assessment_at: datetime  # When to reassess this reference
    source_version_id: str | None = None  # Lawful version snapshot reference
    grace_boundary_at: datetime | None = None  # Resolved late-penalty boundary for this cycle
    policy_uuid: str | None = None  # Canonical upstream policy identity for this cycle


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
    - a current lawful cycle already exists for internal_ref (genesis is a
      separate command — establish_bill_cycle); advancement never creates cycle 1
    - cycle_number equals the derived successor (latest.cycle_number + 1)
    - cycle_boundary_at is the terminal boundary of this cycle
    - next_assessment_at is a lawful successor assessment time

    Postconditions:
    - exactly one BillCycle row created with (internal_ref, cycle_number)
    - Unique constraint enforces at most one cycle per (internal_ref, cycle_number)

    Raises:
    - BillCycleLifecycleError if no prior cycle exists (advancement is not genesis)
      or the requested cycle_number is not the strict successor
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

    # Advancement is not genesis: it requires an existing current cycle and only
    # ever creates the strictly sequential successor. The lawful successor number
    # is derived from authoritative Obligations state, not trusted from the caller
    # (the caller-supplied cycle_number serves only as the replay key above, and
    # is verified against the derived successor here). Genesis (cycle 1) is a
    # separate command — establish_bill_cycle (DOM-OBL-001).
    latest = obligations_service.get_latest_bill_cycle(request.internal_ref)
    if latest is None:
        raise BillCycleLifecycleError(
            f"advance_bill_cycle requires an existing cycle for lineage "
            f"'{request.internal_ref}'; use establish_bill_cycle for genesis (cycle 1)."
        )
    expected = latest.cycle_number + 1
    if request.cycle_number != expected:
        raise BillCycleLifecycleError(
            f"non-sequential advancement for lineage '{request.internal_ref}': "
            f"expected successor cycle {expected}, got {request.cycle_number}."
        )

    # Temporal validation: successor cycle times must be ordered
    if request.next_assessment_at <= request.cycle_boundary_at:
        raise ValueError(
            f"next_assessment_at must be after cycle_boundary_at "
            f"({request.next_assessment_at} <= {request.cycle_boundary_at})"
        )

    # Phase 2: Mutation (atomic transaction)

    bill_cycle = BillCycle(
        class_id=request.class_id,
        internal_ref=request.internal_ref,
        cycle_number=request.cycle_number,
        source_version_id=request.source_version_id,
        policy_uuid=request.policy_uuid,
        cycle_boundary_at=request.cycle_boundary_at,
        next_assessment_at=request.next_assessment_at,
        grace_boundary_at=request.grace_boundary_at,
    )

    db.session.add(bill_cycle)
    db.session.flush()

    # Phase 3: Note on terminal case
    # If upstream authority indicates the relationship has terminated,
    # the caller must NOT invoke this FEAT. The terminated relationship
    # produces no successor cycle per FEAT-OBL-002 §IV.3.

    return bill_cycle


@requires_feat_context("FEAT-OBL-002")
def execute_advance_bill_cycle(
    class_id: str,
    internal_ref: str,
    cycle_number: int,
    cycle_boundary_at: datetime,
    next_assessment_at: datetime,
    *,
    source_version_id: str | None = None,
    grace_boundary_at: datetime | None = None,
    policy_uuid: str | None = None,
) -> BillCycle:
    """
    Public FEAT interface for bill cycle advancement.

    Called by upstream authorities (Class Configuration, entitlement services)
    when lawful recurring progression permits another assessment boundary.

    Returns the successor BillCycle row.
    """
    request = AdvanceBillCycleRequest(
        class_id=class_id,
        internal_ref=internal_ref,
        cycle_number=cycle_number,
        cycle_boundary_at=cycle_boundary_at,
        next_assessment_at=next_assessment_at,
        source_version_id=source_version_id,
        grace_boundary_at=grace_boundary_at,
        policy_uuid=policy_uuid,
    )
    return advance_bill_cycle(request, context=FEATContext("FEAT-OBL-002"))
