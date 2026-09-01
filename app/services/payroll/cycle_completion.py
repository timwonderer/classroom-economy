"""Payroll-cycle completion replay-identity API (DOM-PROD-001 §XV, slice 8.3 substrate).

The persistent answer to the one question that makes the payroll cycle boundary
replay-safe:

    "Have I already completed this class-level payroll run, and if so, which
     payroll_cycle_id did it produce?"

``resolve_completed_run`` answers it as a pure read, to be consulted at the very
top of the completion lifecycle — before any domain command, configuration read,
materialization, or policy activation. ``record_run_completion`` writes the
completion anchor as the final step of a successful lifecycle, within the caller's
atomic FEAT transaction, so the anchor exists iff the whole lifecycle committed.

This module is the substrate only. It does NOT orchestrate PROD settlement, ITR
materialization, or CLASS activation — that is the FEAT-PROD-004 orchestrator,
built in a later slice. It performs no cross-domain calls.
"""

from __future__ import annotations

import uuid
from typing import NamedTuple

from app.extensions import db
from app.models import PayrollCycleCompletion


class PayrollCycleCompletionConflict(Exception):
    """Raised when a completion already exists for ``(class_id, idempotency_key)``
    bound to a *different* ``payroll_cycle_id``. The completion anchor is immutable:
    a mismatch is an integrity violation, never an update."""


class RunCompletionResult(NamedTuple):
    """Outcome of recording a run completion.

    ``created`` is ``True`` when a new anchor was inserted, ``False`` when an
    identical anchor already existed (idempotent replay of the final step).
    """

    completion: PayrollCycleCompletion
    payroll_cycle_id: str
    created: bool


def allocate_payroll_cycle_id() -> str:
    """Allocate a fresh economic-cycle identity. Called exactly once per new run.

    A replay MUST NOT call this: it resolves the completed run first and reuses the
    original ``payroll_cycle_id`` (see module docstring)."""
    return str(uuid.uuid4())


def resolve_completed_run(class_id: str, idempotency_key: str) -> str | None:
    """Return the ``payroll_cycle_id`` of an already-completed run, else ``None``.

    Pure read (INV-ARC-007), scoped by ``(class_id, idempotency_key)``. This is the
    top-level replay guard: a non-``None`` result means the lifecycle already
    committed and the caller must short-circuit to that cycle id without touching
    any domain.
    """
    if not class_id or not idempotency_key:
        return None
    row = (
        PayrollCycleCompletion.query
        .filter_by(class_id=class_id, idempotency_key=idempotency_key)
        .first()
    )
    return row.payroll_cycle_id if row else None


def record_run_completion(
    class_id: str, idempotency_key: str, payroll_cycle_id: str
) -> RunCompletionResult:
    """Persist the completion anchor for a finished run (final lifecycle step).

    Idempotent: re-recording the same ``(class_id, idempotency_key)`` with the same
    ``payroll_cycle_id`` returns the existing anchor without a second write. A
    different ``payroll_cycle_id`` for the same key raises
    :class:`PayrollCycleCompletionConflict` (fail closed). ``add``/``flush`` within
    the caller's FEAT transaction; never commits on its own.
    """
    if not class_id or not idempotency_key or not payroll_cycle_id:
        raise ValueError(
            "class_id, idempotency_key, and payroll_cycle_id are required to record a completion"
        )
    existing = (
        PayrollCycleCompletion.query
        .filter_by(class_id=class_id, idempotency_key=idempotency_key)
        .first()
    )
    if existing is not None:
        if existing.payroll_cycle_id == payroll_cycle_id:
            return RunCompletionResult(existing, existing.payroll_cycle_id, created=False)
        raise PayrollCycleCompletionConflict(
            f"payroll_cycle_completion already exists for class_id={class_id}, "
            f"idempotency_key={idempotency_key} bound to a different payroll_cycle_id "
            f"({existing.payroll_cycle_id} != {payroll_cycle_id}); the completion anchor "
            "is immutable (DOM-PROD-001 §XV)."
        )

    completion = PayrollCycleCompletion(
        class_id=class_id,
        idempotency_key=idempotency_key,
        payroll_cycle_id=payroll_cycle_id,
    )
    db.session.add(completion)
    db.session.flush()
    return RunCompletionResult(completion, payroll_cycle_id, created=True)
