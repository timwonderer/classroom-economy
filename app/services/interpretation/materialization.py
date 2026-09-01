"""Interpretation cycle-record materialization writer (DOM-ITR-001 §IX, slice 8.2c).

The single command that turns a complete, lawful ``observations_json`` payload into
exactly **one immutable** ``interpretation_cycle_record`` for a completed economic
cycle. This is the first slice in which DOM-ITR lawfully creates history.

Responsibilities (and only these):

1. **Re-validate, never trust.** Re-run ``validate_for_materialization`` inside the
   writer — the caller's claim that the payload is complete is irrelevant; the
   serializer-derived completeness gate (SPEC-ITR-001 §15.8) is re-evaluated here
   and fails closed if the payload is not exactly-complete and lawful.
2. **Freeze the reference configuration** from authoritative CLASS/economic reads
   at the cycle boundary (§VII), so the record is self-describing.
3. **Write exactly one record per ``(class_id, payroll_cycle_id)``** (§IX).
4. **Idempotent replay, fail-closed conflict.** Re-presenting the same cycle with
   the same canonical payload and reference configuration is idempotent success.
   Re-presenting the same cycle with *different* content is an integrity violation:
   the record is immutable, so the writer rejects it — it never updates, overwrites,
   or recomputes.

The writer is deliberately **dumb about candidate meaning**: it knows nothing of
how Q3 or Q9 is computed, only that the payload passes the serialization contract
and that a lawful reference configuration was captured. It performs **no**
Analytics call. It ``add``s and ``flush``es within the caller's FEAT transaction
and never commits on its own, so any failure rolls back with that transaction;
FEAT-PROD-004 orchestration is wired in a later slice, not here.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from app.extensions import db
from app.models import InterpretationCycleRecord
from app.services.interpretation.observation_contract import validate_for_materialization
from app.services.interpretation.reference_configuration import (
    capture_reference_configuration,
)


class CycleMaterializationConflict(Exception):
    """Raised when a cycle record already exists for ``(class_id, payroll_cycle_id)``
    with different content. A materialized record is immutable (§IX): a mismatch is
    an integrity violation, never an update."""


class MaterializationResult(NamedTuple):
    """Outcome of a materialization attempt.

    ``created`` is ``True`` when a new record was inserted, ``False`` when an
    identical record already existed (idempotent replay).
    """

    record: InterpretationCycleRecord
    created: bool
    reference_configuration: dict[str, Any]


def materialize_interpretation_cycle(
    *,
    class_id: str,
    payroll_cycle_id: str,
    cycle_started_at,
    cycle_completed_at,
    observations_json: dict[str, Any],
) -> MaterializationResult:
    """Materialize exactly one immutable cycle record, idempotently (§IX).

    Raises :class:`app.services.interpretation.observation_contract.ObservationContractError`
    if the payload is not a complete, lawful materialization payload (fail closed,
    before any write). Raises :class:`CycleMaterializationConflict` if a record for
    this cycle already exists with different content. Otherwise inserts one record
    (or returns the existing identical one) and flushes within the caller's
    transaction.
    """
    if not class_id or not payroll_cycle_id:
        raise ValueError("class_id and payroll_cycle_id are required for materialization")

    # 1. Re-validate the payload independently of the caller's claim (fail closed).
    validate_for_materialization(observations_json)

    # 2. Freeze the governing reference configuration at the cycle boundary.
    reference_configuration = capture_reference_configuration(class_id)

    # 3. Idempotency / conflict — scoped by (class_id, payroll_cycle_id).
    existing = (
        InterpretationCycleRecord.query
        .filter_by(class_id=class_id, payroll_cycle_id=payroll_cycle_id)
        .first()
    )
    if existing is not None:
        identical = (
            existing.observations_json == observations_json
            and existing.reference_configuration == reference_configuration
        )
        if identical:
            # Idempotent success — no second write, no update.
            return MaterializationResult(
                record=existing, created=False,
                reference_configuration=reference_configuration,
            )
        raise CycleMaterializationConflict(
            f"interpretation_cycle_record already exists for class_id={class_id}, "
            f"payroll_cycle_id={payroll_cycle_id} with different content; a materialized "
            "cycle record is immutable and is never overwritten (DOM-ITR-001 §IX)."
        )

    # 4. Insert exactly one record within the caller's FEAT transaction.
    record = InterpretationCycleRecord(
        class_id=class_id,
        payroll_cycle_id=payroll_cycle_id,
        cycle_started_at=cycle_started_at,
        cycle_completed_at=cycle_completed_at,
        reference_configuration=reference_configuration,
        observations_json=observations_json,
    )
    db.session.add(record)
    db.session.flush()
    return MaterializationResult(
        record=record, created=True, reference_configuration=reference_configuration,
    )
