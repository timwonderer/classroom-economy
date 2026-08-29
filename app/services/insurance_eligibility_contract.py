"""System-owned TRANSACTION insurance eligibility law (Step 6, rule 4).

This module is CTH's canonical, domain-owned authority for *which* ledger
transactions may lawfully back a TRANSACTION insurance claim. It is deliberately
NOT Class Configuration: the disallowed set is fixed system law and a teacher
cannot widen (or narrow) it. Keeping the predicate here — mirroring the narrow
typed ``frozen_insurance_contract`` read contract — means FEAT-STOR-003 asks one
question ("is this transaction a lawful TRANSACTION claim basis?") and never
embeds a magic list of transaction categories.

A TRANSACTION claim's source transaction must satisfy ALL of:

* it is a **loss** — negative from the covered seat's perspective;
* it **belongs** to the covered seat and class;
* its category/type is **not** in CTH's global disallowed-insurance set;
* it is **not** a transfer;
* it is **not** obligation-related (rent / property tax);
* it is **not** collective-goal-related;
* if it is **item-related**, the associated entitlement must have been purchased
  and **USED** (a CONSUMED event exists) and must **not** be REVOKED or EXPIRED.

Two orthogonal gates live in the FEAT, not here, because they need temporal /
claim-history context rather than transaction structure: the **filing window**
(transaction date → submission, class-local calendar days) and the
**one-transaction-one-claim** uniqueness guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.extensions import db
from app.models import EntitlementEvent, Transaction


# Ledger ``type`` strings that are structurally not an insurable loss. System
# law — teachers cannot extend this. Compared case-insensitively.
DISALLOWED_TRANSACTION_TYPES = frozenset({
    "insurance_reimbursement",   # cannot insure an insurance payout
    "insurance_premium",         # the premium itself is not an insurable loss
    "overdraft_fee",             # penalty fees are not insurable
    "interest",                  # credited income, not a loss
    "payroll",                   # income, not a loss
    "bug_reward",                # reward income, not a loss
    "void_item_removed",         # bookkeeping reversal, not a loss
})

# Peer-to-peer / self movement of funds — not an insurable loss of value.
TRANSFER_TYPES = frozenset({"withdrawal", "deposit", "transfer"})

# Obligations are separately governed (DOM-OBL-001); never insurable here.
OBLIGATION_TYPES = frozenset({"rent", "property_tax"})

# Entitlement taxonomy (EntitlementEvent.entitlement_type).
_GOAL_ENTITLEMENT_TYPE = "COLLECTIVE_GOAL"
_ITEM_ENTITLEMENT_TYPES = frozenset({
    "IMMEDIATE_USE", "DELAYED_USE", "PRIVILEGE", "HALL_PASS",
})
_USED_EVENT = "CONSUMED"
_REVOKED_EXPIRED_EVENTS = ("REVOKED", "EXPIRED")


# Verdict reason codes (stable, surfaced to callers/tests).
NOT_FOUND = "TRANSACTION_NOT_FOUND"
WRONG_CLASS = "TRANSACTION_WRONG_CLASS"
WRONG_SEAT = "TRANSACTION_WRONG_SEAT"
NOT_A_LOSS = "TRANSACTION_NOT_A_LOSS"
TRANSFER = "TRANSFER_NOT_INSURABLE"
OBLIGATION = "OBLIGATION_NOT_INSURABLE"
DISALLOWED_CATEGORY = "DISALLOWED_CATEGORY"
GOAL = "GOAL_NOT_INSURABLE"
ITEM_NOT_USED = "ITEM_NOT_YET_USED"
ITEM_REVOKED_OR_EXPIRED = "ITEM_REVOKED_OR_EXPIRED"


@dataclass(frozen=True)
class EligibilityVerdict:
    """Typed verdict for a TRANSACTION claim basis. ``eligible`` is the gate."""

    eligible: bool
    reason_code: Optional[str] = None
    detail: Optional[str] = None


def _normalized_type(transaction: Transaction) -> str:
    return (transaction.type or "").strip().lower()


def _correlated_granted_events(class_id: str, correlation_id: Optional[str]):
    """GRANTED entitlement events that share the transaction's correlation lineage."""
    if not correlation_id:
        return []
    return (
        db.session.query(EntitlementEvent)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.correlation_id == correlation_id,
            EntitlementEvent.event_type == "GRANTED",
        )
        .all()
    )


def _entitlement_has_event(class_id: str, entitlement_id: str, event_types) -> bool:
    return (
        db.session.query(EntitlementEvent)
        .filter(
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.entitlement_id == entitlement_id,
            EntitlementEvent.event_type.in_(list(event_types)),
        )
        .first()
        is not None
    )


def evaluate_transaction_claim_basis(
    transaction: Optional[Transaction],
    *,
    class_id: str,
    covered_seat_id: int,
) -> EligibilityVerdict:
    """Return a typed eligibility verdict for a TRANSACTION claim basis.

    Structural/system-law predicates only. The filing window and the
    one-transaction-one-claim uniqueness guard are enforced by FEAT-STOR-003
    (they require temporal and claim-history context, not transaction shape).
    """
    if transaction is None:
        return EligibilityVerdict(False, NOT_FOUND, "Source transaction not found")

    if transaction.class_id != class_id:
        return EligibilityVerdict(
            False, WRONG_CLASS, "Transaction is not in this class"
        )

    # The covered seat is the ledger anchor of its own loss.
    if transaction.seat_id != covered_seat_id:
        return EligibilityVerdict(
            False, WRONG_SEAT, "Transaction does not belong to the covered seat"
        )

    amount = transaction.amount
    if amount is None or amount >= Decimal("0.00"):
        return EligibilityVerdict(
            False, NOT_A_LOSS, "Only a negative (loss) transaction is insurable"
        )

    ttype = _normalized_type(transaction)
    if ttype in TRANSFER_TYPES:
        return EligibilityVerdict(False, TRANSFER, "Transfers are not insurable")
    if ttype in OBLIGATION_TYPES:
        return EligibilityVerdict(
            False, OBLIGATION, "Obligation charges are not insurable"
        )
    if ttype in DISALLOWED_TRANSACTION_TYPES:
        return EligibilityVerdict(
            False, DISALLOWED_CATEGORY, f"Transaction type '{transaction.type}' is not insurable"
        )

    # Entitlement-linked checks (collective goal, item usage) via shared lineage.
    granted = _correlated_granted_events(class_id, transaction.correlation_id)
    for event in granted:
        if event.entitlement_type == _GOAL_ENTITLEMENT_TYPE:
            return EligibilityVerdict(
                False, GOAL, "Collective-goal contributions are not insurable"
            )

    for event in granted:
        if event.entitlement_type in _ITEM_ENTITLEMENT_TYPES:
            entitlement_id = event.entitlement_id
            # An item that was revoked/expired never delivered lasting value.
            if _entitlement_has_event(class_id, entitlement_id, _REVOKED_EXPIRED_EVENTS):
                return EligibilityVerdict(
                    False,
                    ITEM_REVOKED_OR_EXPIRED,
                    "Associated item was revoked or expired",
                )
            # Item purchases are claimable only once their value is realized (USED).
            if not _entitlement_has_event(class_id, entitlement_id, (_USED_EVENT,)):
                return EligibilityVerdict(
                    False,
                    ITEM_NOT_USED,
                    "Associated item has not been used yet",
                )

    return EligibilityVerdict(True)
