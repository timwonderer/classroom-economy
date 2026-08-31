"""Q1b — Student-Initiated Economic Interaction compute (SPEC-ITR-001 §6).

Produces the single Q1b candidate from three authoritative source domains,
combined per the §6.4 minimum-raw-observation rule (a seat counts if it acted in
*any* one of them):

* DOM-LED-001 — student-originated ledger rows (the §6.3 provenance classifier).
* DOM-STORE-001 — ``EntitlementEvent`` purchase grants.
* DOM-OBL-001 — obligation ``PAYMENT`` events backed by a self-mechanism ledger row.

Per INV-ITR-016, when the same act is recorded by a source domain (STORE/OBL)
and by Ledger, the source-domain fact takes precedence; because Q1b-C1 only asks
whether a seat acted *at all*, the union is idempotent under that precedence.

Architectural rule (INV-ARC-009, INV-ITR-016): this module consumes source-domain
read surfaces, never arbitrary ORM. The §6.3 classifier itself lives in the
Ledger domain (``ledger_service.SYSTEM_ORIGINATED_FEAT_CODES``) because the
Ledger owns the provenance of its own rows; ``Transaction.type`` is never
consulted here (INV-ITR-015).
"""

from __future__ import annotations

from typing import Any

from app.services.entitlement_read_service import get_seat_ids_with_purchase_grants
from app.services.identity_service import get_enrolled_student_seat_ids
from app.services.ledger_service import get_seat_ids_with_student_originated_activity
from app.services.obligations_service import get_seat_ids_with_self_payments
from app.services.interpretation.observation_builders import (
    fraction_value,
    observation_entry,
)


def compute_q1b(class_id: str, window_start, window_end) -> list[dict[str, Any]]:
    """Compute Q1b-C1 for a completed cycle window.

    Returns a single-element list holding the ``Q1b-C1`` entry. A seat is in the
    numerator if it appears in the union of the three source-domain acting-seat
    sets, intersected with the enrolled population (the denominator).
    """
    enrolled_seat_ids = get_enrolled_student_seat_ids(class_id)
    enrolled = set(enrolled_seat_ids)

    acted_seat_ids = (
        get_seat_ids_with_student_originated_activity(class_id, window_start, window_end)
        | get_seat_ids_with_purchase_grants(class_id, window_start, window_end)
        | get_seat_ids_with_self_payments(class_id, window_start, window_end)
    )
    # Only enrolled seats form the numerator; a stray act by a non-enrolled seat
    # is not part of this class-aggregate observation.
    participating = len(acted_seat_ids & enrolled)

    q1b_c1 = observation_entry(
        "Q1b-C1",
        semantic_kind="descriptive_observation",
        subject="class_id",
        observation_basis="seat_id",
        aggregation="class_aggregate_from_seat_observations",
        reference_dependency="none",
        value=fraction_value(participating, len(enrolled_seat_ids)),
    )

    return [q1b_c1]
