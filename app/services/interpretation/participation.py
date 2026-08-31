"""Q1a — Labor Participation compute (SPEC-ITR-001 §5).

Produces the two Q1a candidate observation entries from the authoritative
attendance surface (DOM-PROD-001 ``attendance_sessions``) and the enrolled-seat
population (Identity domain). Ledger is never consulted to establish that labor
participation occurred (INV-ITR-016); the participation fact is
attendance-authoritative.

Architectural rule (INV-ARC-009, INV-ITR-016): this module consumes *source-domain
read surfaces*, never arbitrary ORM. It calls
``attendance_service.get_attendance_session_counts_by_seat`` and
``identity_service.get_enrolled_student_seat_ids`` — not ``AttendanceSession.query``.
"""

from __future__ import annotations

from typing import Any

from app.services.attendance_service import get_attendance_session_counts_by_seat
from app.services.identity_service import get_enrolled_student_seat_ids
from app.services.interpretation.observation_builders import (
    count_distribution_value,
    fraction_value,
    observation_entry,
)


def compute_q1a(class_id: str, window_start, window_end) -> list[dict[str, Any]]:
    """Compute Q1a-C1 and Q1a-C2 for a completed cycle window.

    Returns the two entries in candidate_id order (``Q1a-C1`` then ``Q1a-C2``).
    The enrolled-seat set is the denominator/population for both candidates; a
    seat with no attendance session contributes a zero to the count
    distribution and is absent from the participation numerator.
    """
    enrolled_seat_ids = get_enrolled_student_seat_ids(class_id)
    counts_by_seat = get_attendance_session_counts_by_seat(class_id, window_start, window_end)

    # Denominator population and per-seat counts (0 for seats with no session).
    per_seat_counts = [counts_by_seat.get(seat_id, 0) for seat_id in enrolled_seat_ids]
    participating = sum(1 for count in per_seat_counts if count > 0)

    q1a_c1 = observation_entry(
        "Q1a-C1",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="seat_id",
        aggregation="class_aggregate_from_seat_observations",
        reference_dependency="none",
        value=fraction_value(participating, len(enrolled_seat_ids)),
    )

    q1a_c2 = observation_entry(
        "Q1a-C2",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="seat_id",
        aggregation="class_distribution_from_seat_observations",
        reference_dependency="none",
        # Attendance-session counts have no meaningful zero-crossing tail, so no
        # ``n_at_or_below_zero`` extension (SPEC-ITR-001 §5.4, §15.6.1).
        value=count_distribution_value(per_seat_counts, include_mean=True),
    )

    return [q1a_c1, q1a_c2]
