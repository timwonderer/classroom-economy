"""Q6 — Resource Distribution compute (SPEC-ITR-001 §11).

Reports the per-seat balance distribution separately for checking, savings, and
total resources (§11.2 — never collapsed into one number), each as the pinned
``distribution`` value-kind (core percentiles + ``iqr`` + the balance extension
``n_at_or_below_zero``; §15.6.1). Distribution-first: the percentile decomposition
is the primary output and ``mean`` is only a secondary statistic (§11.3).

Balances are read **as of the cycle boundary** (window end) over the full
enrolled roster, so a zero-balance seat still counts toward the population and the
low tail (§11.5). The population and the historical balance surface are shared
with Q4 via ``resource_reads`` but the semantics stay distinct.

Feature enablement (as of the cycle boundary):
* Q6-C1 (checking) is always computed.
* Q6-C2 (savings) is ``not_applicable`` when savings is disabled — never zero.
* Q6-C3 (total resources) falls back to a **checking-only** distribution with a
  declared basis-note qualifier when savings is disabled (§11.5).
"""

from __future__ import annotations

from typing import Any

from app.services.interpretation.observation_builders import (
    balance_distribution_value,
    not_applicable_entry,
    observation_entry,
)
from app.services.interpretation.resource_reads import (
    balances_cents_for_seats,
    enrolled_seat_ids,
    savings_enabled_as_of,
    total_resource_cents_for_seats,
)

_SAVINGS_DISABLED_REASON = {"feature": "savings", "state": "disabled"}
_CHECKING_ONLY_QUALIFIER = {
    "basis_note": {"code": "checking_only_savings_disabled", "excluded_component": "savings"}
}
_DISTRIBUTION_AGGREGATION = "class_distribution_from_seat_observations"


def _distribution_entry(candidate_id, balances_cents, *, qualifiers=None):
    return observation_entry(
        candidate_id,
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="seat_id",
        aggregation=_DISTRIBUTION_AGGREGATION,
        reference_dependency="none",
        value=balance_distribution_value(balances_cents),
        qualifiers=qualifiers,
    )


def compute_q6(class_id: str, window_start, window_end) -> list[dict[str, Any]]:
    """Compute Q6-C1, Q6-C2, Q6-C3 for a completed cycle window.

    Returns the three entries in candidate_id order. ``window_start`` is unused —
    Q6 observes end-of-cycle *stock*, not flow — but is accepted for a uniform
    compute signature.
    """
    seat_ids = enrolled_seat_ids(class_id)
    savings_enabled = savings_enabled_as_of(class_id, window_end)

    checking_cents = balances_cents_for_seats(class_id, window_end, "checking", seat_ids)
    q6_c1 = _distribution_entry("Q6-C1", checking_cents)

    if savings_enabled:
        savings_cents = balances_cents_for_seats(class_id, window_end, "savings", seat_ids)
        q6_c2 = _distribution_entry("Q6-C2", savings_cents)
        total_cents = total_resource_cents_for_seats(class_id, window_end, seat_ids)
        q6_c3 = _distribution_entry("Q6-C3", total_cents)
    else:
        q6_c2 = not_applicable_entry(
            "Q6-C2",
            semantic_kind="descriptive_observation",
            subject="class_id",
            observation_basis="seat_id",
            aggregation=_DISTRIBUTION_AGGREGATION,
            reference_dependency="none",
            not_applicable_reason=dict(_SAVINGS_DISABLED_REASON),
        )
        # Q6-C3 total resources falls back to checking-only with the required
        # basis note (§11.5) — a computed observation on a narrowed basis, not
        # not_applicable.
        q6_c3 = _distribution_entry(
            "Q6-C3", checking_cents, qualifiers=dict(_CHECKING_ONLY_QUALIFIER)
        )

    return [q6_c1, q6_c2, q6_c3]
