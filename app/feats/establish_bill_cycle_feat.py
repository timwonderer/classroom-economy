"""
Bill-cycle genesis — the Obligations command that establishes the FIRST cycle.

Genesis and advancement are distinct Obligations mutations (DOM-OBL-001):

    genesis:      nothing  -> cycle 1     (establish_bill_cycle, this module)
    advancement:  cycle N  -> cycle N+1   (advance_bill_cycle, FEAT-OBL-002)

`cycle_number` is NOT caller-selected here — genesis inherently produces cycle 1.
The precondition is that no prior cycle exists for the lineage; a second genesis
attempt fails (BillCycleLifecycleError) regardless of idempotency key, because
idempotency protects retries of a command, it does not license a second cycle 1.

This is a domain command, not a user-facing FEAT: it carries no FEAT-registry
number of its own. It executes under the shared bill-cycle mutation-authority tag
`FEAT-OBL-002` (the same coarse authority under which rent reconciliation and
advancement already run) — the genesis-vs-advancement distinction lives in the
command contracts, not the authority tag.
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
class EstablishBillCycleRequest:
    """Input contract for bill-cycle genesis (cycle 1)."""
    class_id: str  # Multi-tenancy scope (INV-CORE-000)
    internal_ref: str  # Stable lineage key for the continuing relationship
    cycle_boundary_at: datetime  # When cycle 1 ends
    next_assessment_at: datetime  # When the lineage is next reconsidered
    source_version_id: str | None = None
    grace_boundary_at: datetime | None = None
    policy_uuid: str | None = None  # Canonical upstream policy identity for this cycle


def establish_bill_cycle(
    request: EstablishBillCycleRequest,
    *,
    context: FEATContext | None = None,
) -> BillCycle:
    """Establish cycle 1 for a recurring obligation lineage where none exists.

    Preconditions:
    - no prior bill cycle exists for ``internal_ref`` (the genesis invariant);
    - ``next_assessment_at`` is after ``cycle_boundary_at``.

    Postconditions:
    - exactly one BillCycle row with ``cycle_number = 1`` for the lineage.

    Raises:
    - BillCycleLifecycleError if any cycle already exists for the lineage. This
      holds even under a different idempotency key: idempotency guards retries,
      not manufacturing a second cycle 1.
    - ValueError if the temporal ordering is invalid.
    """
    # Genesis invariant: the lineage must be empty. Checked against authoritative
    # Obligations state, not an idempotency key.
    if obligations_service.get_latest_bill_cycle(request.internal_ref) is not None:
        raise BillCycleLifecycleError(
            f"establish_bill_cycle requires no prior cycle for lineage "
            f"'{request.internal_ref}'; a cycle already exists. Use "
            f"advance_bill_cycle (FEAT-OBL-002) to progress an existing lineage."
        )

    if request.next_assessment_at <= request.cycle_boundary_at:
        raise ValueError(
            f"next_assessment_at must be after cycle_boundary_at "
            f"({request.next_assessment_at} <= {request.cycle_boundary_at})"
        )

    bill_cycle = BillCycle(
        class_id=request.class_id,
        internal_ref=request.internal_ref,
        cycle_number=1,  # genesis inherently produces cycle 1; never caller-selected
        source_version_id=request.source_version_id,
        policy_uuid=request.policy_uuid,
        cycle_boundary_at=request.cycle_boundary_at,
        next_assessment_at=request.next_assessment_at,
        grace_boundary_at=request.grace_boundary_at,
    )
    db.session.add(bill_cycle)
    db.session.flush()
    return bill_cycle


@requires_feat_context("FEAT-OBL-002")
def execute_establish_bill_cycle(
    class_id: str,
    internal_ref: str,
    cycle_boundary_at: datetime,
    next_assessment_at: datetime,
    *,
    source_version_id: str | None = None,
    grace_boundary_at: datetime | None = None,
    policy_uuid: str | None = None,
) -> BillCycle:
    """Public entry for bill-cycle genesis under the shared FEAT-OBL-002 authority.

    Genesis carries no FEAT-registry number of its own; it runs under the bill-cycle
    mutation-authority tag (nested lawfully when a caller already holds it).
    """
    request = EstablishBillCycleRequest(
        class_id=class_id,
        internal_ref=internal_ref,
        cycle_boundary_at=cycle_boundary_at,
        next_assessment_at=next_assessment_at,
        source_version_id=source_version_id,
        grace_boundary_at=grace_boundary_at,
        policy_uuid=policy_uuid,
    )
    return establish_bill_cycle(request)
