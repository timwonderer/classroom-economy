"""Q3 — Obligation Observation compute (SPEC-ITR-001 §8).

Produces the three Q3 candidates from a single canonical read of the interpreted
per-obligation state (:func:`obligation_outcome.interpret_obligations`). All
three consume the same records, so the count-based outcome (Q3-C1), the
amount-based coverage (Q3-C2), and the raw event counts (Q3-C3) are mutually
consistent:

* **Q3-C1** — count-based satisfaction across the four disjoint outcome
  categories (§8.4), a ``category_fractions_by_type`` value: each obligation type
  carries its own four-outcome fraction vector over that type's obligation count.
* **Q3-C2** — amount-based coverage: student-paid vs waived vs unmet cents as
  separate numerators partitioning the assessed denominator (§8.4, §8.5), a
  ``coverage_by_type`` value, per obligation type.
* **Q3-C3** — raw event counts by ``(obligation_type, event kind)`` plus per-type
  unsatisfied counts (§8.4), a ``counts`` value.

All three candidates carry the per-obligation-type subject, so NSF-fee
obligations are identified distinctly in every Q3 output and a reader can inspect
outcomes *with and without* the NSF-fee contribution (§8.6). NSF fees enter Q3
only because ``NSF_FEE`` ``AssessmentEvent`` rows exist — their obligation type is
an ordinary map key, never special compute, never synthesized.

Count-based and amount-based observations are reported as separate candidates and
waived is a distinct outcome, never merged with paid (§8.3). ``Transaction.type``
is never consulted (INV-ITR-015); obligation facts come only from
``assessment_events`` (INV-ITR-016).
"""

from __future__ import annotations

from typing import Any

from app.services.interpretation.obligation_outcome import (
    EVENT_KINDS,
    OUTCOME_CATEGORIES,
    OUTCOME_UNSATISFIED,
    interpret_obligations,
)
from app.services.interpretation.observation_builders import (
    category_fractions_by_type_value,
    counts_value,
    coverage_by_type_value,
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

    # Q3-C1 — count-based satisfaction over the four disjoint outcomes, keyed by
    # obligation type (§8.4 per-type subject; §8.6 NSF distinctness). Each present
    # type gets the full four-outcome vector (explicit zeros); its denominator is
    # that type's obligation count.
    outcome_numerators: dict[str, dict[str, int]] = {}
    outcome_denominators: dict[str, int] = {}
    for ob in obligations:
        by_outcome = outcome_numerators.setdefault(
            ob.obligation_type, {label: 0 for label in OUTCOME_CATEGORIES}
        )
        by_outcome[ob.outcome] += 1
        outcome_denominators[ob.obligation_type] = (
            outcome_denominators.get(ob.obligation_type, 0) + 1
        )
    q3_c1 = observation_entry(
        "Q3-C1",
        semantic_kind="descriptive_observation",
        subject="class_id, per obligation type",
        observation_basis="assessment_correlation_id",
        aggregation="class_fraction_over_obligations_by_type",
        reference_dependency="none",
        value=category_fractions_by_type_value(outcome_numerators, outcome_denominators),
    )

    # Q3-C2 — amount-based coverage in integer cents, keyed by obligation type;
    # student-paid / waived / unmet partition assessed per type (§8.4, §8.5).
    coverage_by_type: dict[str, dict[str, int]] = {}
    for ob in obligations:
        comp = coverage_by_type.setdefault(
            ob.obligation_type,
            {"assessed_cents": 0, "student_paid_cents": 0, "waived_cents": 0, "unmet_cents": 0},
        )
        comp["assessed_cents"] += ob.assessed_cents
        comp["student_paid_cents"] += ob.paid_student_cents
        comp["waived_cents"] += ob.waived_cents
        comp["unmet_cents"] += ob.unmet_cents
    q3_c2 = observation_entry(
        "Q3-C2",
        semantic_kind="descriptive_observation",
        subject="class_id, per obligation type",
        observation_basis="assessment_correlation_id",
        aggregation="class_coverage_over_assessed_amount_by_type",
        reference_dependency="none",
        value=coverage_by_type_value(coverage_by_type),
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
