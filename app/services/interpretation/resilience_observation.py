"""Q9 — Resilience Observation compute (SPEC-ITR-001 §13).

Q9-C1 is a **composition of already-certified observations**, not a new metric.
It is the sole ``signal_set`` candidate: the five independent §13.3 observation
groups are reported as distinct member signals and are never collapsed into a
single scalar (§13.2). Each member reuses the **same canonical primitive** that
its owning candidate already certified — there is exactly one definition of
"unsatisfied obligation" (Q3's ``interpret_obligations``), one definition of
"resource distribution" (Q6's balance surface), one of "attendance count"
(Q1a's) — so Q9 never re-reads or re-interprets the same facts under slightly
different rules.

Member signals (sorted by ``signal_id`` per §15.9):

* ``labor_participation`` — per-seat attendance-session count distribution
  (§13.3.d), from the Q1a attendance primitive.
* ``obligation_outcomes`` — class counts over the four §8.4 outcomes (§13.3.b),
  from the Q3 ``interpret_obligations`` primitive.
* ``persistence`` — presence across completed cycles (§13.3.e). Persistence is
  **presence**, never a trend/slope/direction. No prior
  ``interpretation_cycle_record`` source exists yet (DOM-ITR-001 §XIII.a), so this
  signal is ``not_applicable`` — the honest current state, not zero.
* ``resource_checking`` / ``resource_savings`` / ``resource_total`` — end-of-cycle
  balance distributions (§13.3.a), from the Q6 resource surface. Savings and total
  are ``not_applicable`` when savings is disabled (per-signal, §14.1).
* ``teacher_support`` — class counts of WAIVED events and teacher-originated
  inflows (§13.3.c), reusing the Q3 obligation primitive and the Q5 inbound-ledger
  primitive.

Dignity (INV-ITR-009): every member is class-level distributional evidence. Q9
uses per-seat observations *internally* but the serialized output exposes no seat
identifiers, no ranking, and no "these students are struggling" claim (§13.4).

The §13.3.a duration sub-observation (days with checking ≤ 0) has no certified
per-day historical primitive today; consistent with the reuse-not-recompute
discipline it is a documented deferred sub-signal, not an independent recompute.
"""

from __future__ import annotations

from typing import Any

from app.services.attendance_service import get_attendance_session_counts_by_seat
from app.services.interpretation.obligation_outcome import (
    OUTCOME_CATEGORIES,
    interpret_obligations,
)
from app.services.interpretation.observation_builders import (
    balance_distribution_value,
    computed_signal,
    count_distribution_value,
    counts_value,
    not_applicable_signal,
    observation_entry,
    signal_set_value,
)
from app.services.interpretation.resource_reads import (
    balances_cents_for_seats,
    enrolled_seat_ids,
    savings_enabled_as_of,
    total_resource_cents_for_seats,
)
from app.services.ledger_service import get_inbound_ledger_rows

_PERSISTENCE_UNAVAILABLE_REASON = {
    "input": "prior_completed_cycle_records",
    "state": "unavailable",
}
_SAVINGS_DISABLED_REASON = {"feature": "savings", "state": "disabled"}


def _labor_participation_signal(class_id, window_start, window_end, seat_ids):
    counts_by_seat = get_attendance_session_counts_by_seat(class_id, window_start, window_end)
    per_seat = [counts_by_seat.get(seat_id, 0) for seat_id in seat_ids]
    return computed_signal(
        "labor_participation", count_distribution_value(per_seat, include_mean=True)
    )


def _obligation_outcomes_signal(obligations):
    outcome_counts = {label: 0 for label in OUTCOME_CATEGORIES}
    for ob in obligations:
        outcome_counts[ob.outcome] += 1
    return computed_signal("obligation_outcomes", counts_value(outcome_counts))


def _teacher_support_signal(class_id, window_start, window_end, obligations):
    waived_events = sum(ob.n_waived_events for ob in obligations)
    inbound = get_inbound_ledger_rows(class_id, window_start, window_end)
    teacher_inflows = sum(
        1
        for row in inbound
        if row.mechanism == "teacher" and row.original_transaction_id is None
    )
    return computed_signal(
        "teacher_support",
        counts_value({"teacher_inflows": teacher_inflows, "waived_events": waived_events}),
    )


def compute_q9(class_id: str, window_start, window_end) -> list[dict[str, Any]]:
    """Compute the Q9-C1 resilience observation set for a completed cycle window.

    Returns a single-entry list. The entry is a ``signal_set`` composing the five
    §13.3 groups; savings-dependent resource signals and the (currently
    unavailable) persistence signal are ``not_applicable`` per member.
    """
    seat_ids = enrolled_seat_ids(class_id)
    savings_enabled = savings_enabled_as_of(class_id, window_end)
    obligations = interpret_obligations(class_id, window_start, window_end)

    signals = [
        _labor_participation_signal(class_id, window_start, window_end, seat_ids),
        _obligation_outcomes_signal(obligations),
        _teacher_support_signal(class_id, window_start, window_end, obligations),
        # Persistence is presence across completed cycles, never a trend (§13.3.e).
        # No prior cycle-record source exists yet (DOM-ITR-001 §XIII.a).
        not_applicable_signal("persistence", dict(_PERSISTENCE_UNAVAILABLE_REASON)),
        computed_signal(
            "resource_checking",
            balance_distribution_value(
                balances_cents_for_seats(class_id, window_end, "checking", seat_ids)
            ),
        ),
    ]

    if savings_enabled:
        signals.append(
            computed_signal(
                "resource_savings",
                balance_distribution_value(
                    balances_cents_for_seats(class_id, window_end, "savings", seat_ids)
                ),
            )
        )
        signals.append(
            computed_signal(
                "resource_total",
                balance_distribution_value(
                    total_resource_cents_for_seats(class_id, window_end, seat_ids)
                ),
            )
        )
    else:
        signals.append(
            not_applicable_signal("resource_savings", dict(_SAVINGS_DISABLED_REASON))
        )
        signals.append(
            not_applicable_signal("resource_total", dict(_SAVINGS_DISABLED_REASON))
        )

    q9_c1 = observation_entry(
        "Q9-C1",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="seat_id",
        aggregation="class_distribution_from_seat_observations",
        reference_dependency="none",
        value=signal_set_value(signals),
    )
    return [q9_c1]
