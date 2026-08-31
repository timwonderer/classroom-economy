"""Read-only PayrollEvent corroboration surface (PROD domain).

The Interpretation domain classifies income origin (SPEC-ITR-001 §10.2) and must
distinguish *labor-derived* Ledger inflows from teacher/admin ``manual_credit``
injections. Per INV-ITR-016, that distinction is resolved against the
authoritative ``PayrollEvent`` surface — the source-domain fact — rather than by
trusting a Ledger row's ``feat_code`` to look "payroll-ish". A labor inflow is
corroborated when a ``PayrollEvent`` with ``payroll_event_type='payroll'`` shares
the Ledger row's ``correlation_id``.

This module is a pure read (INV-ARC-007) owned by PROD, which owns the
``PayrollEvent`` record (INV-ARC-009). It performs no classification itself; it
only projects the correlation-id sets Interpretation needs.
"""

from __future__ import annotations

from typing import NamedTuple

from app.models import PayrollEvent
from app.utils.canonical_temporal_resolver import ensure_utc


class PayrollCorrelationSets(NamedTuple):
    """Correlation-id sets for a class window, partitioned by payroll event type.

    * ``labor`` — ``correlation_id``s of ``payroll_event_type='payroll'`` events
      (SPEC-ITR-001 §10.2 category 1). These corroborate labor-derived inflows.
    * ``manual_credit`` — ``correlation_id``s of ``payroll_event_type='manual_credit'``
      events (§10.2 category 3, teacher/admin-injected).

    ``payroll_event_type='reversal'`` is deliberately excluded from both sets: a
    reversal is neither labor nor a manual credit, and reversal Ledger rows are
    identified structurally by ``original_transaction_id`` (§10.2 category 5).
    """

    labor: frozenset[str]
    manual_credit: frozenset[str]


def get_payroll_correlation_sets(
    class_id: str, window_start, window_end
) -> PayrollCorrelationSets:
    """Return the labor / manual-credit correlation-id sets for ``[start, end)``.

    Scoped by ``class_id`` (multi-tenancy) and the half-open completed-cycle
    window on ``PayrollEvent.recorded_at`` so it aligns with the Ledger rows
    Interpretation is classifying over the same window.
    """
    if not class_id or window_start is None or window_end is None:
        return PayrollCorrelationSets(labor=frozenset(), manual_credit=frozenset())

    rows = (
        PayrollEvent.query
        .with_entities(PayrollEvent.correlation_id, PayrollEvent.payroll_event_type)
        .filter(
            PayrollEvent.class_id == class_id,
            PayrollEvent.recorded_at >= ensure_utc(window_start),
            PayrollEvent.recorded_at < ensure_utc(window_end),
        )
        .all()
    )

    labor = {
        row.correlation_id
        for row in rows
        if row.payroll_event_type == "payroll" and row.correlation_id
    }
    manual_credit = {
        row.correlation_id
        for row in rows
        if row.payroll_event_type == "manual_credit" and row.correlation_id
    }
    return PayrollCorrelationSets(
        labor=frozenset(labor), manual_credit=frozenset(manual_credit)
    )
