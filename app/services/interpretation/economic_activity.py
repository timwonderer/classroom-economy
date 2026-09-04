"""Q2 — Student-Initiated Economic Activity Level compute (SPEC-ITR-001 §7).

Produces the two Q2 candidates from the authoritative Ledger surface, restricted
to *student-originated* rows by the §6.3 provenance classifier (the same
classifier Q1b consumes). Per §7.2 the two quantities are reported as separate
values and are never collapsed into a single "activity" scalar:

* **Q2-C1** — student-initiated transaction *frequency* as a per-active-seat,
  per-day rate (§7.3). The denominator uses *active* seats (seats with ≥1
  student-initiated act), not enrolled seats, so participation (Q1b) and
  intensity (Q2-C1) remain independent quantities.
* **Q2-C2** — student-initiated transaction *monetary volume*: the sum of the
  absolute amounts of those rows, reported in raw tokens (§7.3).

Architectural rule (INV-ARC-009, INV-ITR-016): this module consumes a
source-domain read surface (``ledger_provenance_query_service.get_student_originated_rows``),
never arbitrary ORM, and never consults ``Transaction.type`` (INV-ITR-015).
"""

from __future__ import annotations

from typing import Any

from app.services.ledger_provenance_query_service import get_student_originated_rows
from app.services.interpretation.observation_builders import (
    amount_value,
    observation_entry,
    rate_value,
)
from app.utils.canonical_temporal_resolver import ensure_utc


def _window_days(window_start, window_end) -> int:
    """Whole completed-cycle days spanned by ``[window_start, window_end)``.

    Uses the integer day component of the window's span (a payroll-cycle window
    is day-aligned). A degenerate or inverted window yields ``0`` days, which the
    rate builder handles as a zero-denominator (value ``0``).
    """
    delta = ensure_utc(window_end) - ensure_utc(window_start)
    return max(delta.days, 0)


def compute_q2(class_id: str, window_start, window_end) -> list[dict[str, Any]]:
    """Compute Q2-C1 and Q2-C2 for a completed cycle window.

    Returns the two entries in candidate_id order (``Q2-C1`` then ``Q2-C2``).
    Both are derived from a single scoped read of student-originated rows so the
    frequency numerator, active-seat denominator, and monetary volume are
    mutually consistent.
    """
    rows = get_student_originated_rows(class_id, window_start, window_end)

    transaction_count = len(rows)
    active_seats = len({row.seat_id for row in rows if row.seat_id is not None})
    days = _window_days(window_start, window_end)
    active_seat_days = active_seats * days

    q2_c1 = observation_entry(
        "Q2-C1",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="transaction_id",
        aggregation="class_rate_from_seat_observations",
        reference_dependency="none",
        value=rate_value(
            transaction_count,
            active_seat_days,
            unit="transactions_per_active_seat_per_day",
        ),
    )

    # Sum of absolute amounts (student-initiated rows may be inbound or outbound).
    volume_cents = sum(abs(int(row.amount_cents)) for row in rows)
    q2_c2 = observation_entry(
        "Q2-C2",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="transaction_id",
        aggregation="class_sum",
        reference_dependency="none",
        # Raw-token report: no CWI rescale, so normalization_dependency stays null
        # (§7.3; CWI-normalized reporting is a distinct, non-default mode).
        normalization_dependency=None,
        value=amount_value(volume_cents, unit="tokens"),
    )

    return [q2_c1, q2_c2]
