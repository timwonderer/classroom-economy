"""Q4 — Savings Behavior compute (SPEC-ITR-001 §9).

Reports savings behavior as three candidates that keep **stock** and **flow**
strictly separate (§9.2):

* **Q4-C1** — savings-holding fraction (*stock*): fraction of enrolled seats with
  a savings balance strictly greater than zero **at window end**.
* **Q4-C2** — savings-contribution fraction (*flow*): fraction of enrolled seats
  with ≥1 student-originated savings contribution *during* the window.
* **Q4-C3** — savings-contribution volume (*flow*): total absolute deposit-side
  amount of those contributions in the window.

Stock and flow are independent observations by design: a seat may hold savings at
window end without contributing this cycle (contributed earlier), and may
contribute this cycle yet end at zero after later movement. This module never
collapses them.

When the savings feature is disabled for the class (as of the cycle boundary),
**all three** Q4 candidates are ``not_applicable`` — never zero (§9.6, §14.1).
"""

from __future__ import annotations

from typing import Any

from app.services.interpretation.observation_builders import (
    amount_value,
    fraction_value,
    not_applicable_entry,
    observation_entry,
)
from app.services.interpretation.resource_reads import (
    balances_cents_for_seats,
    enrolled_seat_ids,
    savings_enabled_as_of,
)
from app.services.ledger_service import get_student_savings_contribution_rows

_SAVINGS_DISABLED_REASON = {"feature": "savings", "state": "disabled"}


def compute_q4(class_id: str, window_start, window_end) -> list[dict[str, Any]]:
    """Compute Q4-C1, Q4-C2, Q4-C3 for a completed cycle window.

    Returns the three entries in candidate_id order. When savings is disabled all
    three are ``not_applicable``; otherwise all three are ``computed`` with
    zero-bearing values where the observed quantity is zero.
    """
    if not savings_enabled_as_of(class_id, window_end):
        return [
            not_applicable_entry(
                cid,
                semantic_kind="descriptive_observation",
                subject="class_id",
                observation_basis=basis,
                aggregation=aggregation,
                reference_dependency="none",
                not_applicable_reason=dict(_SAVINGS_DISABLED_REASON),
                normalization_dependency=norm,
            )
            for cid, basis, aggregation, norm in (
                ("Q4-C1", "seat_id", "class_fraction_from_seat_observations", None),
                ("Q4-C2", "seat_id", "class_fraction_from_seat_observations", None),
                ("Q4-C3", "transaction_id", "class_sum", None),
            )
        ]

    seat_ids = enrolled_seat_ids(class_id)
    enrolled = len(seat_ids)

    # Q4-C1 — stock: enrolled seats holding any savings at window end.
    savings_balances = balances_cents_for_seats(class_id, window_end, "savings", seat_ids)
    holders = sum(1 for cents in savings_balances if cents > 0)
    q4_c1 = observation_entry(
        "Q4-C1",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="seat_id",
        aggregation="class_fraction_from_seat_observations",
        reference_dependency="none",
        value=fraction_value(holders, enrolled),
    )

    # Q4-C2/Q4-C3 — flow: student-originated savings contributions in the window.
    contribution_rows = get_student_savings_contribution_rows(
        class_id, window_start, window_end
    )
    contributing_seats = {row.seat_id for row in contribution_rows if row.seat_id is not None}
    q4_c2 = observation_entry(
        "Q4-C2",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="seat_id",
        aggregation="class_fraction_from_seat_observations",
        reference_dependency="none",
        value=fraction_value(len(contributing_seats), enrolled),
    )

    volume_cents = sum(abs(int(row.amount_cents)) for row in contribution_rows)
    q4_c3 = observation_entry(
        "Q4-C3",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="transaction_id",
        aggregation="class_sum",
        reference_dependency="none",
        # Raw-token report; CWI-normalized reporting is a distinct non-default
        # mode, so normalization_dependency stays null (§9.4, §12.3).
        normalization_dependency=None,
        value=amount_value(volume_cents, unit="tokens"),
    )

    return [q4_c1, q4_c2, q4_c3]
