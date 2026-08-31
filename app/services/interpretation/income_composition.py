"""Q5 — Income Composition compute (SPEC-ITR-001 §10).

Produces the two Q5 candidates over *inbound* Ledger rows for the window,
classified into the six §10.2 origin categories by the shared income-origin
provenance classifier (:mod:`app.services.interpretation.income_origin`):

* **Q5-C1** — income composition as the share of total inbound monetary volume
  belonging to each of the six categories (§10.3), a ``category_fractions`` value.
* **Q5-C2** — the labor share as a ``ratio`` of labor-derived inbound volume to
  total inbound volume (§10.3).

Source-domain precedence (INV-ITR-016): labor is corroborated against the
authoritative ``PayrollEvent`` surface via shared ``correlation_id`` rather than
by trusting a Ledger row's ``feat_code``. The classifier's deterministic
precedence guarantees each inflow lands in exactly one category and that
"other / unclassified" is only reached after every canonical provenance check
fails (§10.2 category 6). ``Transaction.type`` is never consulted (INV-ITR-015).
"""

from __future__ import annotations

from typing import Any

from app.services.interpretation.income_origin import (
    CATEGORY_LABOR,
    aggregate_income_by_category,
)
from app.services.interpretation.observation_builders import (
    category_fractions_value,
    observation_entry,
    ratio_value,
)
from app.services.ledger_service import get_inbound_ledger_rows
from app.services.payroll.read_service import get_payroll_correlation_sets


def compute_q5(class_id: str, window_start, window_end) -> list[dict[str, Any]]:
    """Compute Q5-C1 and Q5-C2 for a completed cycle window.

    Returns the two entries in candidate_id order (``Q5-C1`` then ``Q5-C2``).
    Both are derived from the same inbound-row classification so the composition
    shares and the labor ratio are mutually consistent (Q5-C2 is exactly the
    category-1 share of Q5-C1).
    """
    inbound_rows = get_inbound_ledger_rows(class_id, window_start, window_end)
    payroll_sets = get_payroll_correlation_sets(class_id, window_start, window_end)

    category_cents = aggregate_income_by_category(
        inbound_rows,
        labor_correlation_ids=payroll_sets.labor,
        manual_credit_correlation_ids=payroll_sets.manual_credit,
    )
    total_inbound_cents = sum(category_cents.values())

    q5_c1 = observation_entry(
        "Q5-C1",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="transaction_id",
        aggregation="class_share_by_category",
        reference_dependency="none",
        value=category_fractions_value(category_cents, total_inbound_cents),
    )

    labor_cents = category_cents[CATEGORY_LABOR]
    q5_c2 = observation_entry(
        "Q5-C2",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="transaction_id",
        aggregation="class_ratio",
        reference_dependency="none",
        value=ratio_value(labor_cents, total_inbound_cents),
    )

    return [q5_c1, q5_c2]
