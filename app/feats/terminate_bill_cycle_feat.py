"""
Bill-cycle termination — the Obligations command that STOPS a recurring lineage.

Genesis, advancement, and termination are the three distinct bill-cycle
mutations (DOM-OBL-001):

    genesis:      nothing  -> cycle 1        (establish_bill_cycle)
    advancement:  cycle N  -> cycle N+1      (advance_bill_cycle, FEAT-OBL-002)
    termination:  cycle N  -> cycle N+1*     (this module)  *terminal, no recurrence

A terminal cycle row carries ``next_assessment_at = NULL``: the lineage produces
no further recurring assessment (DOM-OBL-001 §160, §241). It does NOT rewrite
prior obligation events (DOM-OBL-001 §IX.7 / §293) — the historical cycles and
their assessments remain immutable. Coverage still runs to the current cycle's
``cycle_boundary_at``; ending the entitlement at that boundary is a separate,
Store-owned disposition (FEAT-STOR-002 EXPIRED), never performed here.

Insurance cancellation (FEAT-OBL-005) terminates the recurring
``INSURANCE_PREMIUM`` lineage through this command — stopping future premiums
without revoking, refunding, or early-expiring the paid coverage
(FEAT-STOR-002 §IX.C: insurance is non-revocable).

This is a domain command, not a user-facing FEAT: it carries no FEAT-registry
number of its own and executes under the shared bill-cycle mutation-authority tag
``FEAT-OBL-002`` (the same coarse authority as genesis/advancement). The
termination distinction lives in the command contract, not the authority tag.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.extensions import db
from app.models import BillCycle
from app.services import obligations_service
from app.services.obligations_service import BillCycleLifecycleError
from app.feats.base import requires_feat_context, FEATContext


@dataclass
class TerminateBillCycleRequest:
    """Input contract for bill-cycle termination.

    Only the lineage scope is caller-supplied. The terminal cycle's boundary and
    upstream identity are carried forward from the authoritative current cycle —
    termination stops recurrence, it does not move the coverage boundary or
    reinterpret the lineage's policy identity (INV-ARC-009).
    """
    class_id: str  # Multi-tenancy scope (INV-CORE-000)
    internal_ref: str  # Stable lineage key for the continuing relationship


def terminate_bill_cycle(
    request: TerminateBillCycleRequest,
    *,
    context: FEATContext | None = None,
) -> BillCycle:
    """Terminate a recurring obligation lineage by appending a terminal cycle.

    Preconditions:
    - a current cycle exists for ``internal_ref`` (you cannot terminate a lineage
      that was never established — genesis is a separate command);
    - the current cycle belongs to ``class_id`` (scope integrity).

    Postconditions:
    - the latest cycle for the lineage is terminal (``next_assessment_at IS NULL``),
      so no further recurring assessment will be scheduled;
    - the terminal cycle's ``cycle_boundary_at`` is the prior cycle's
      ``next_assessment_at`` — the end of the period the last paid premium covers,
      i.e. the point at which (absent cancellation) the next premium would have
      fallen due. Coverage runs through that boundary and then expires
      (FEAT-STOR-002), and the policy identity is carried forward;
    - prior cycles and their assessment/satisfaction events are unchanged.

    Idempotency:
    - if the lineage is already terminal (latest cycle has ``next_assessment_at IS
      NULL``), the existing terminal cycle is returned unchanged — cancelling an
      already-cancelled lineage is a safe no-op.

    Raises:
    - BillCycleLifecycleError if no cycle exists for the lineage, or the current
      cycle is out of the requested class scope.
    """
    latest = obligations_service.get_latest_bill_cycle(request.internal_ref)
    if latest is None:
        raise BillCycleLifecycleError(
            f"terminate_bill_cycle requires an existing cycle for lineage "
            f"'{request.internal_ref}'; nothing to terminate."
        )
    if latest.class_id != request.class_id:
        raise BillCycleLifecycleError(
            f"class scope mismatch for lineage '{request.internal_ref}': "
            f"cycle belongs to class {latest.class_id}, not {request.class_id}."
        )

    # Idempotent: an already-terminal lineage stays terminal. Do not append a
    # second terminal row.
    if latest.next_assessment_at is None:
        return latest

    terminal = BillCycle(
        class_id=latest.class_id,
        internal_ref=latest.internal_ref,
        cycle_number=latest.cycle_number + 1,
        source_version_id=latest.source_version_id,
        policy_uuid=latest.policy_uuid,
        # Coverage runs through the end of the last paid period: the current
        # cycle's next_assessment_at (when the next premium would have been due).
        cycle_boundary_at=latest.next_assessment_at,
        next_assessment_at=None,  # TERMINAL — stops future recurrence
        grace_boundary_at=None,
    )
    db.session.add(terminal)
    db.session.flush()
    return terminal


@requires_feat_context("FEAT-OBL-002")
def execute_terminate_bill_cycle(
    class_id: str,
    internal_ref: str,
) -> BillCycle:
    """Public entry for bill-cycle termination under the shared FEAT-OBL-002 authority.

    Termination carries no FEAT-registry number of its own; it runs under the
    bill-cycle mutation-authority tag. Composing callers (e.g. FEAT-OBL-005) invoke
    the plain ``terminate_bill_cycle`` command inside their own context instead.
    """
    return terminate_bill_cycle(
        TerminateBillCycleRequest(class_id=class_id, internal_ref=internal_ref),
        context=None,
    )
