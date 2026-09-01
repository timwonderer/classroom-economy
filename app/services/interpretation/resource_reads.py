"""Shared economic-resource reads for Q4 and Q6 (SPEC-ITR-001 §9, §11).

Q4 (savings behavior) and Q6 (resource distribution) ask different questions but
draw on the same lawful source-domain facts: enrolled-seat population (Identity),
per-seat account balances **as of the cycle boundary** (Ledger), and savings
feature enablement (Class Configuration). This module centralizes those reads so
both candidates observe an identical, historically-correct resource surface —
without blurring the distinct semantics each candidate reports.

The balance reads are strictly point-in-time (``timestamp < as_of``): a later
transaction can never leak into an earlier cycle's materialized interpretation
(INV-ITR-003). ``Transaction.type`` is never consulted (INV-ITR-015).
"""

from __future__ import annotations

from decimal import Decimal

from app.services.class_configuration_query_service import get_class_feature
from app.services.identity_service import get_enrolled_student_seat_ids
from app.services.ledger_service import get_posted_balances_as_of

# Savings accounts are provisioned by the CLASS "banking" feature; savings is
# available for a class iff banking is enabled (there is no finer savings-only
# toggle in the current Class Configuration model). SPEC-ITR-001 §9.6/§11.5 treat
# "savings feature" enablement as this CLASS-owned fact.
SAVINGS_FEATURE = "banking"

_CENTS = Decimal("1")


def enrolled_seat_ids(class_id: str) -> list[int]:
    """Return the enrolled student seat ids — the Q4/Q6 population (Identity)."""
    return get_enrolled_student_seat_ids(class_id)


def savings_enabled_as_of(class_id: str, as_of) -> bool:
    """Return whether the savings (banking) feature is enabled as of ``as_of``.

    Evaluated at the cycle boundary so the applicability of Q4/Q6-C2 reflects the
    feature state during the completed cycle, not the current instant.
    """
    return get_class_feature(class_id, SAVINGS_FEATURE, as_of) is not None


def _to_cents(amount: Decimal) -> int:
    return int((amount * 100).quantize(_CENTS))


def balances_cents_for_seats(
    class_id: str, as_of, account_type: str, seat_ids: list[int]
) -> list[int]:
    """Per-seat balances (cents) for ``seat_ids`` as of ``as_of``, one per seat.

    Seats with no ledger rows for the account contribute an explicit ``0`` — the
    distribution population is the enrolled roster, not only the seats that
    transacted (SPEC-ITR-001 §11.5).
    """
    balances = get_posted_balances_as_of(class_id, as_of, account_type)
    return [_to_cents(balances.get(seat_id, Decimal("0.00"))) for seat_id in seat_ids]


def total_resource_cents_for_seats(
    class_id: str, as_of, seat_ids: list[int]
) -> list[int]:
    """Per-seat total resources (checking + savings, cents) as of ``as_of``."""
    checking = get_posted_balances_as_of(class_id, as_of, "checking")
    savings = get_posted_balances_as_of(class_id, as_of, "savings")
    return [
        _to_cents(
            checking.get(seat_id, Decimal("0.00")) + savings.get(seat_id, Decimal("0.00"))
        )
        for seat_id in seat_ids
    ]
