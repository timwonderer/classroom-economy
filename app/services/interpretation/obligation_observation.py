"""Q3 — Obligation Observation compute (SPEC-ITR-001 §8).

Produces the three Q3 candidates from a single canonical read of the interpreted
per-obligation state (:func:`obligation_outcome.interpret_obligations`). All
three consume the same records, so the count-based outcome (Q3-C1), the
amount-based coverage (Q3-C2), and the raw event counts (Q3-C3) are mutually
consistent:

* **Q3-C1** — count-based satisfaction across the four disjoint outcome
  categories (§8.4), a ``category_fractions`` value over the obligation count.
* **Q3-C2** — amount-based coverage: student-paid vs waived vs unmet dollars as
  separate numerators against the assessed denominator (§8.4, §8.5), a
  ``category_fractions`` value in integer cents.
* **Q3-C3** — raw event counts by ``(obligation_type, event kind)`` plus per-type
  unsatisfied counts (§8.4), a ``counts`` value. This is the Q3 output that
  carries the per-obligation-type dimension, so a reader can see obligation
  outcomes *with and without* the NSF-fee contribution (§8.6) — NSF fees appear
  here only because ``NSF_FEE`` ``AssessmentEvent`` rows exist, never synthesized.

Count-based and amount-based observations are reported as separate candidates and
waived is a distinct outcome, never merged with paid (§8.3). ``Transaction.type``
is never consulted (INV-ITR-015); obligation facts come only from
``assessment_events`` (INV-ITR-016).
"""

from __future__ import annotations

from typing import Any

from app.services.interpretation.obligation_outcome import (
    COVERAGE_CATEGORIES,
    COVERAGE_PAID,
    COVERAGE_UNMET,
    COVERAGE_WAIVED,
    EVENT_KINDS,
    OUTCOME_CATEGORIES,
    OUTCOME_UNSATISFIED,
    interpret_obligations,
)
from app.services.interpretation.observation_builders import (
    category_fractions_value,
    counts_value,
    observation_entry,
)


def compute_q3(class_id: str, window_start, window_end) -> list[dict[str, Any]]:
    """Compute Q3-C1, Q3-C2, and Q3-C3 for a completed cycle window.

    Returns the three entries in candidate_id order (``Q3-C1``, ``Q3-C2``,
    ``Q3-C3``). A window with no assessed obligations yields lawful zero-bearing
    values (the feature is enabled but nothing was observed, §15.3) rather than
    ``not_applicable``.
    """
    obligations = interpret_obligations(class_id, window_start, window_end)

    # Q3-C1 — count-based satisfaction over the four disjoint outcomes.
    outcome_counts = {label: 0 for label in OUTCOME_CATEGORIES}
    for ob in obligations:
        outcome_counts[ob.outcome] += 1
    total_obligations = len(obligations)
    q3_c1 = observation_entry(
        "Q3-C1",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="assessment_correlation_id",
        aggregation="class_fraction_over_obligations",
        reference_dependency="none",
        value=category_fractions_value(outcome_counts, total_obligations),
    )

    # Q3-C2 — amount-based coverage in integer cents; paid/waived kept separate.
    coverage_cents = {label: 0 for label in COVERAGE_CATEGORIES}
    assessed_total_cents = 0
    for ob in obligations:
        coverage_cents[COVERAGE_PAID] += ob.paid_student_cents
        coverage_cents[COVERAGE_WAIVED] += ob.waived_cents
        coverage_cents[COVERAGE_UNMET] += ob.unmet_cents
        assessed_total_cents += ob.assessed_cents
    q3_c2 = observation_entry(
        "Q3-C2",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="assessment_correlation_id",
        aggregation="class_coverage_share_over_assessed_amount",
        reference_dependency="none",
        value=category_fractions_value(coverage_cents, assessed_total_cents),
    )

    # Q3-C3 — raw counts, per (obligation_type, event kind) + per-type unsatisfied.
    # This is where the per-obligation-type dimension (and NSF distinctness, §8.6)
    # lives. A window with no obligations reports an explicit zero baseline over
    # the global event kinds so the closed ``counts`` vocabulary stays non-empty.
    type_counts: dict[str, int] = {}
    for ob in obligations:
        t = ob.obligation_type
        type_counts[f"{t}:assessment"] = type_counts.get(f"{t}:assessment", 0) + 1
        type_counts[f"{t}:payment"] = type_counts.get(f"{t}:payment", 0) + ob.n_payment_events
        type_counts[f"{t}:waived"] = type_counts.get(f"{t}:waived", 0) + ob.n_waived_events
        type_counts.setdefault(f"{t}:unsatisfied", 0)
        if ob.outcome == OUTCOME_UNSATISFIED:
            type_counts[f"{t}:unsatisfied"] += 1
    if not type_counts:
        type_counts = {kind: 0 for kind in EVENT_KINDS}
    q3_c3 = observation_entry(
        "Q3-C3",
        semantic_kind="descriptive_observation",
        subject="class_id, per obligation type",
        observation_basis="assessment_event_rows",
        aggregation="class_counts",
        reference_dependency="none",
        value=counts_value(type_counts),
    )

    return [q3_c1, q3_c2, q3_c3]
