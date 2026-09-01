"""FEAT-PROD-004 — Complete Payroll Cycle orchestration (DOM-PROD-001 §XV, slice 8.3d).

The canonical class-level payroll-run orchestrator and the sole coordination point
for the economic-cycle boundary. It owns nothing but sequencing and atomicity: every
substantive operation underneath it is a separately-certified substrate command.

    complete_payroll_cycle(...)
        1. resolve_completed_run   ── found → RETURN existing payroll_cycle_id (STOP)
        2. allocate_payroll_cycle_id
        3. settle_class_payroll_cycle           (PROD)
        4. compute_partial_payload              (ITR compute — complete 17/17)
        5. materialize_interpretation_cycle     (ITR — one immutable record)
        6. apply_next_boundary_transition       (CLASS — activate next-cycle policy)
        7. record_run_completion                (replay anchor)
        —— caller's FEATContext commits once ——

Two orderings are held as hard invariants:

* **The replay guard is literally first.** A completed replay resolves the
  completion anchor and returns; it does NOT allocate a cycle id, settle, compute a
  timestamp, capture reference_configuration, or invoke ITR/CLASS. This protects the
  seam 8.2c exposed: a replay never recaptures an advanced configuration.
* **record_run_completion is literally last before commit.** The completion row
  means "this entire economic-cycle transition completed", so if anything before it
  fails, no completion identity survives — the whole run rolls back with the
  caller's transaction.

This function does NOT commit; it runs inside the caller's ``FEATContext``
("FEAT-PROD-004"), which owns the single commit and the fail-closed rollback. It
performs no scheduling and no boundary derivation — the lawful cycle window is
supplied by the caller (PROD/orchestration establishes boundary legality,
DOM-CLASS-003). It never calls a domain directly for anything a substrate command
already owns.
"""

from __future__ import annotations

from typing import NamedTuple

from app.services.class_boundary_activation import apply_next_boundary_transition
from app.services.context_resolver import CanonicalContext
from app.services.interpretation.compute import compute_partial_payload
from app.services.interpretation.materialization import materialize_interpretation_cycle
from app.services.payroll.cycle_completion import (
    allocate_payroll_cycle_id,
    record_run_completion,
    resolve_completed_run,
)
from app.services.payroll.settlement import settle_class_payroll_cycle


class CompletePayrollCycleResult(NamedTuple):
    """Outcome of a payroll-cycle completion.

    ``created`` is ``True`` for a genuinely new run, ``False`` for a replay that
    resolved an already-completed run. On a replay only ``payroll_cycle_id`` and
    ``created`` are meaningful; the downstream fields are ``None`` because no
    downstream work was performed.
    """

    payroll_cycle_id: str
    created: bool
    settled_seat_ids: list[int] | None = None
    interpretation_record_id: str | None = None
    activation_applied: bool | None = None
    completion_created: bool | None = None


def complete_payroll_cycle(
    *,
    ctx: CanonicalContext,
    idempotency_key: str,
    cycle_started_at,
    cycle_completed_at,
) -> CompletePayrollCycleResult:
    """Orchestrate one class-level payroll-cycle completion. NO COMMIT.

    Must run inside the caller's ``FEATContext("FEAT-PROD-004", idempotency_key=...)``.
    ``cycle_started_at`` / ``cycle_completed_at`` are the lawful closed-cycle window
    supplied by the caller; ``cycle_completed_at`` is the boundary used for
    settlement and next-boundary activation.
    """
    if ctx is None or not getattr(ctx, "class_id", None):
        raise ValueError("complete_payroll_cycle requires a lawful class-bound context")
    if not idempotency_key:
        raise ValueError("complete_payroll_cycle requires an idempotency_key")
    class_id = ctx.class_id

    # 1. REPLAY GUARD — literally first. No domain work, no config read, no id
    #    allocation, no timestamp before this resolves.
    existing = resolve_completed_run(class_id, idempotency_key)
    if existing is not None:
        return CompletePayrollCycleResult(payroll_cycle_id=existing, created=False)

    # 2. Only a genuinely new run allocates a cycle identity.
    payroll_cycle_id = allocate_payroll_cycle_id()

    # 3. PROD — settle the closing cycle, stamping payroll_cycle_id on every event.
    settlement = settle_class_payroll_cycle(
        class_id=class_id,
        payroll_cycle_id=payroll_cycle_id,
        boundary_utc=cycle_completed_at,
        actor_ctx=ctx,
    )

    # 4-5. ITR — compute the complete payload and materialize one immutable record
    #      bound to this cycle. The writer re-validates completeness and freezes the
    #      reference configuration governing the closing cycle.
    observations_json = compute_partial_payload(class_id, cycle_started_at, cycle_completed_at)
    materialization = materialize_interpretation_cycle(
        class_id=class_id,
        payroll_cycle_id=payroll_cycle_id,
        cycle_started_at=cycle_started_at,
        cycle_completed_at=cycle_completed_at,
        observations_json=observations_json,
    )

    # 6. CLASS — activate the pending next-cycle policy at this boundary (no-op if
    #    nothing is pending). The next cycle, not the closing one, gets the new law.
    activation = apply_next_boundary_transition(
        class_id=class_id, boundary_at=cycle_completed_at
    )

    # 7. Replay anchor — literally last. It exists iff everything above committed.
    completion = record_run_completion(class_id, idempotency_key, payroll_cycle_id)

    return CompletePayrollCycleResult(
        payroll_cycle_id=payroll_cycle_id,
        created=True,
        settled_seat_ids=list(settlement.settled_seat_ids),
        interpretation_record_id=materialization.record.id,
        activation_applied=activation.applied,
        completion_created=completion.created,
    )
