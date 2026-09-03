"""
FEAT-OBL-005: Insurance Cancellation (stop renewal).

Cancellation of a lawfully purchased insurance policy is **stop-renewal**, not a
revoke or refund. Authority (EXPIRED-only model, confirmed against the docs):

- DOM-STORE-001 §1 — insurance ends at cycle boundaries; REVOKED is authorized
  only for non-insurance entitlement types.
- FEAT-STOR-002 §VIII / §IX.C / §XIV — a lawfully purchased insurance entitlement
  SHALL NOT be revoked or refunded; teacher cancellation is prospective; coverage
  is never expired early. (`INSURANCE_NON_REVOCABLE`.)
- DOM-OBL-001 §160/§241/§293 — termination is a terminal bill-cycle row
  (`next_assessment_at = NULL`) that stops future recurrence without rewriting
  prior obligation events.

What this FEAT does (and only this):
- resolve the seat's ACTIVE recurring `INSURANCE_PREMIUM` lineage for the policy,
- terminate that lineage's bill cycle (no further premiums will be assessed).

What this FEAT explicitly does NOT do:
- it writes NO `REVOKED` and NO early `EXPIRED` entitlement event, and moves NO
  money (no refund). Coverage remains active and claimable until its cycle
  boundary; the terminal `EXPIRED` disposition lands at that boundary through the
  Store-owned boundary-expiry mechanism (FEAT-STOR-002), never here.

The seat↔lineage binding lives on the `assessment_events` the bill cycle drives
(FEAT-OBL-004 §VIII.5 / §IX; bill cycles are seat-blind). FEAT-OBL-004's §114 hard
invariant guarantees at most one concurrently-active entitlement per
(seat, policy_uuid), so the active lineage resolves unambiguously.

Execution model: one FEAT context composing the OBL domain command
``terminate_bill_cycle`` — never another FEAT executor (FEAT-CORE-000 §V.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.services import obligations_service
from app.services.context_resolver import CanonicalContext
from app.feats.base import requires_feat_context
from app.feats.terminate_bill_cycle_feat import (
    terminate_bill_cycle,
    TerminateBillCycleRequest,
)


@dataclass
class InsuranceCancellationResult:
    """Outcome of an insurance cancellation (stop-renewal, replay-safe)."""
    success: bool = False
    correlation_id: str | None = None
    internal_ref: str | None = None
    terminal_cycle_id: int | None = None
    coverage_boundary_at: datetime | None = None
    already_cancelled: bool = False  # lineage was already terminal (idempotent)
    error_code: str | None = None
    error_message: str | None = None


def _resolve_premium_lineages(seat_id: int, class_id: str, policy_uuid: str) -> list[str]:
    """Distinct recurring-premium lineage keys for this seat's coverage of a policy.

    The seat/class/policy binding lives on the INSURANCE_PREMIUM assessment events
    (FEAT-OBL-004 §VIII.5); the bill cycle itself is seat-blind. Returned in
    first-seen (creation) order.
    """
    refs: list[str] = []
    for a in obligations_service.get_assessment_events_for_seat_class(
        seat_id, class_id, obligation_type="INSURANCE_PREMIUM"
    ):
        if a.policy_uuid == policy_uuid and a.internal_ref not in refs:
            refs.append(a.internal_ref)
    return refs


@requires_feat_context("FEAT-OBL-005")
def execute_cancel_insurance(
    *,
    canonical_context: CanonicalContext,
    policy_uuid: str,
    idempotency_key: str,
    target_seat_id: int | None = None,
    correlation_id: str | None = None,
) -> InsuranceCancellationResult:
    """Cancel (stop future premiums on) a seat's active insurance coverage.

    ``target_seat_id`` defaults to the acting seat (student self-cancel); a teacher
    supplies the covered seat. Class scope comes from ``canonical_context``.

    Idempotent: cancelling already-terminated coverage returns success with
    ``already_cancelled = True`` and creates no second terminal cycle.
    """
    class_id = canonical_context.class_id
    seat_id = target_seat_id if target_seat_id is not None else canonical_context.seat_id
    correlation_id = correlation_id or f"insurance-cancel:{idempotency_key}"

    if seat_id is None or class_id is None:
        return InsuranceCancellationResult(
            success=False, correlation_id=correlation_id,
            error_code="NO_CONTEXT",
            error_message="cancellation requires a resolved seat and class",
        )

    refs = _resolve_premium_lineages(seat_id, class_id, policy_uuid)
    if not refs:
        return InsuranceCancellationResult(
            success=False, correlation_id=correlation_id,
            error_code="COVERAGE_NOT_FOUND",
            error_message=(
                f"no INSURANCE_PREMIUM lineage for seat {seat_id} / policy "
                f"{policy_uuid} in class {class_id}"
            ),
        )

    # The active lineage is the one whose latest cycle is non-terminal. Under the
    # §114 single-active-coverage invariant there is at most one.
    active_ref = None
    latest_seen = None
    for ref in refs:
        latest = obligations_service.get_latest_bill_cycle(ref)
        if latest is None:
            continue
        latest_seen = latest
        if latest.next_assessment_at is not None:
            active_ref = ref
            break

    if active_ref is None:
        # Every lineage is already terminal — coverage renewal is already stopped.
        return InsuranceCancellationResult(
            success=True, already_cancelled=True, correlation_id=correlation_id,
            internal_ref=(latest_seen.internal_ref if latest_seen else None),
            terminal_cycle_id=(latest_seen.id if latest_seen else None),
            coverage_boundary_at=(latest_seen.cycle_boundary_at if latest_seen else None),
        )

    terminal = terminate_bill_cycle(
        TerminateBillCycleRequest(class_id=class_id, internal_ref=active_ref),
        context=None,
    )
    return InsuranceCancellationResult(
        success=True, correlation_id=correlation_id,
        internal_ref=active_ref,
        terminal_cycle_id=terminal.id,
        coverage_boundary_at=terminal.cycle_boundary_at,
    )
