"""ITR-owned read models over ``interpretation_cycle_record`` (DOM-ITR-001, INV-ARC-022).

The lawful domain read surface for the teacher-facing Interpretation page. It
returns ITR presentation objects — never ORM rows, never JSONB — and **never
recomputes**: reviewing cycle N returns the interpretation that was materialized
when cycle N closed (a durable historical record, DOM-ITR-001 §VII/§IX), not a
re-run of today's compute code. There is deliberately no import of the compute
layer in this module.

Every read is scoped by ``class_id`` (multi-tenancy).
"""

from __future__ import annotations

from app.models import InterpretationCycleRecord
from app.services.interpretation.presentation import (
    InterpretationCycleSummary,
    InterpretationCycleView,
    build_cycle_view,
)


def _summary(record: InterpretationCycleRecord) -> InterpretationCycleSummary:
    return InterpretationCycleSummary(
        payroll_cycle_id=record.payroll_cycle_id,
        cycle_started_at=record.cycle_started_at,
        cycle_completed_at=record.cycle_completed_at,
        computed_at=record.computed_at,
    )


def list_cycle_summaries(class_id: str) -> list[InterpretationCycleSummary]:
    """Cycle history for a class, most recently completed first.

    A lightweight projection for "what cycles exist?" — no observations payload is
    parsed. Scoped by ``class_id``.
    """
    if not class_id:
        return []
    records = (
        InterpretationCycleRecord.query
        .filter_by(class_id=class_id)
        .order_by(
            InterpretationCycleRecord.cycle_completed_at.desc(),
            InterpretationCycleRecord.computed_at.desc(),
        )
        .all()
    )
    return [_summary(record) for record in records]


def get_cycle_view(class_id: str, payroll_cycle_id: str) -> InterpretationCycleView | None:
    """Full presentation of one completed cycle, or ``None`` if it does not exist.

    Reads the stored, immutable ``observations_json`` and presents it — never
    recomputes. Scoped by ``(class_id, payroll_cycle_id)``.
    """
    if not class_id or not payroll_cycle_id:
        return None
    record = (
        InterpretationCycleRecord.query
        .filter_by(class_id=class_id, payroll_cycle_id=payroll_cycle_id)
        .first()
    )
    if record is None:
        return None
    return build_cycle_view(_summary(record), record.observations_json)


def get_latest_cycle_view(class_id: str) -> InterpretationCycleView | None:
    """Presentation of the most recently completed cycle for a class, or ``None``."""
    if not class_id:
        return None
    record = (
        InterpretationCycleRecord.query
        .filter_by(class_id=class_id)
        .order_by(
            InterpretationCycleRecord.cycle_completed_at.desc(),
            InterpretationCycleRecord.computed_at.desc(),
        )
        .first()
    )
    if record is None:
        return None
    return build_cycle_view(_summary(record), record.observations_json)
