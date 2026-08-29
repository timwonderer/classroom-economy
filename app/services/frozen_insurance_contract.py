"""Claim-time read model for a purchased insurance contract (Step 6).

Once an INSURANCE entitlement is GRANTED, claim eligibility and economics MUST be
computed from the ``frozen_contract`` snapshot captured at purchase time (Step 5),
never by re-reading the current ``InsurancePolicy``. This module is the single,
narrow, typed read contract that turns the GRANTED event's raw ``frozen_contract``
payload into a *validated, product-specific* object.

FEAT-STOR-003 (and any future claim executor) consumes ONLY this contract. Raw
payload/JSON parsing stays here — claim branches never re-implement the frozen
subset semantics, and they never touch ``StorePolicyResolver`` or
``InsurancePolicy`` for a purchased entitlement's terms.

The lawful per-type subset mirrors ``insurance_contract_freeze`` exactly (the two
must stay in lockstep): the freeze module writes the snapshot; this module reads
it back and refuses anything that is not shaped like a lawful freeze.

``insurance_policy_uuid`` is carried as **provenance only** — it must never be
re-resolved to fetch current terms. ``purchase_metadata`` is presentation-only and
is likewise never a source of claim-time economic truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Mapping, Optional

from app.extensions import db
from app.models import EntitlementEvent


TRANSACTION = "TRANSACTION"
PRODUCTIVITY = "PRODUCTIVITY"
NON_MONETARY = "NON_MONETARY"

_INSURANCE_ENTITLEMENT_TYPE = "INSURANCE"

# Exact lawful key set per type — MUST match insurance_contract_freeze.build_frozen_contract.
_FROZEN_SUBSET: Dict[str, frozenset] = {
    TRANSACTION: frozenset({
        "insurance_type", "premium", "charge_frequency",
        "reimbursement_percentage", "payout_multiple",
        "claims_per_week_equivalent", "claim_window_days",
    }),
    PRODUCTIVITY: frozenset({
        "insurance_type", "premium", "charge_frequency",
        "reimbursement_percentage", "payout_multiple",
        "claimable_dates_per_week_equivalent",
    }),
    NON_MONETARY: frozenset({
        "insurance_type", "premium", "charge_frequency",
        "claims_per_week_equivalent", "waiting_period_days",
    }),
}

# Which lawful keys are exact decimals vs integers (the rest are plain strings).
_DECIMAL_KEYS = frozenset({
    "premium", "reimbursement_percentage", "payout_multiple",
    "claims_per_week_equivalent", "claimable_dates_per_week_equivalent",
})
_INT_KEYS = frozenset({"claim_window_days", "waiting_period_days"})


class FrozenContractError(Exception):
    """Raised when a GRANTED entitlement cannot yield a lawful frozen contract."""


@dataclass(frozen=True)
class FrozenInsuranceContract:
    """Validated, product-specific view of a purchased insurance contract.

    Only the fields lawful for ``insurance_type`` are populated; every other
    economic accessor is ``None``. Numeric terms are exact (``Decimal`` / ``int``).
    ``insurance_policy_uuid`` is provenance only.
    """

    insurance_type: str
    premium: Decimal
    charge_frequency: str
    insurance_policy_uuid: Optional[str] = None
    reimbursement_percentage: Optional[Decimal] = None
    payout_multiple: Optional[Decimal] = None
    claims_per_week_equivalent: Optional[Decimal] = None
    claim_window_days: Optional[int] = None
    claimable_dates_per_week_equivalent: Optional[Decimal] = None
    waiting_period_days: Optional[int] = None
    purchase_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_monetary(self) -> bool:
        """Monetary products carry reimbursement %/payout multiple (TRANSACTION, PRODUCTIVITY)."""
        return self.insurance_type in (TRANSACTION, PRODUCTIVITY)


def _to_decimal(key: str, value: Any) -> Decimal:
    if value is None:
        raise FrozenContractError(f"frozen_contract.{key} must not be null")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise FrozenContractError(f"frozen_contract.{key} is not a valid number: {value!r}") from exc


def _to_int(key: str, value: Any) -> int:
    if value is None:
        raise FrozenContractError(f"frozen_contract.{key} must not be null")
    try:
        return int(value)
    except (ValueError, TypeError) as exc:
        raise FrozenContractError(f"frozen_contract.{key} is not a valid integer: {value!r}") from exc


def parse_frozen_contract(
    raw: Mapping[str, Any],
    *,
    insurance_policy_uuid: Optional[str] = None,
    purchase_metadata: Optional[Mapping[str, Any]] = None,
) -> FrozenInsuranceContract:
    """Validate a raw frozen_contract mapping into a typed contract (no DB access).

    Enforces the EXACT lawful key set for ``insurance_type`` — no missing keys, no
    extra keys — so a snapshot written by an older/looser path cannot be silently
    under- or over-read at claim time.

    Raises:
        FrozenContractError: malformed, unknown type, or wrong key set.
    """
    if not isinstance(raw, Mapping):
        raise FrozenContractError("frozen_contract must be a mapping")

    itype = raw.get("insurance_type")
    if itype not in _FROZEN_SUBSET:
        raise FrozenContractError(f"Unknown or missing insurance_type in frozen_contract: {itype!r}")

    expected = _FROZEN_SUBSET[itype]
    present = set(raw.keys())
    if present != expected:
        missing = expected - present
        extra = present - expected
        raise FrozenContractError(
            f"frozen_contract for {itype} has an unlawful shape "
            f"(missing={sorted(missing)}, extra={sorted(extra)})"
        )

    charge_frequency = raw.get("charge_frequency")
    if not charge_frequency or not isinstance(charge_frequency, str):
        raise FrozenContractError("frozen_contract.charge_frequency must be a non-empty string")

    kwargs: Dict[str, Any] = {
        "insurance_type": itype,
        "premium": _to_decimal("premium", raw.get("premium")),
        "charge_frequency": charge_frequency,
        "insurance_policy_uuid": insurance_policy_uuid,
        "purchase_metadata": dict(purchase_metadata) if purchase_metadata else {},
    }

    for key in expected:
        if key in ("insurance_type", "premium", "charge_frequency"):
            continue
        if key in _DECIMAL_KEYS:
            kwargs[key] = _to_decimal(key, raw[key])
        elif key in _INT_KEYS:
            kwargs[key] = _to_int(key, raw[key])
        else:  # pragma: no cover - defensive; all lawful keys are typed above
            raise FrozenContractError(f"frozen_contract carries an untyped lawful key: {key}")

    return FrozenInsuranceContract(**kwargs)


def get_frozen_insurance_contract(
    entitlement_id: str,
    *,
    class_id: str,
    seat_id: int,
) -> FrozenInsuranceContract:
    """Resolve the GRANTED insurance entitlement and return its frozen contract.

    Locates the GRANTED INSURANCE event for ``(entitlement_id, class_id, seat_id)``
    and projects its captured ``frozen_contract`` snapshot into a validated typed
    object. Provenance (``insurance_policy_uuid``) and presentation
    (``purchase_metadata``) travel with the object but are never economic truth.

    This read NEVER consults the current ``InsurancePolicy`` / ``StoreProduct``: a
    later HIDDEN / RETIRED / edited / deleted source definition cannot change what a
    purchased entitlement is worth.

    Raises:
        FrozenContractError: no such GRANTED insurance entitlement, or the captured
            snapshot is absent/malformed.
    """
    granted_event = (
        db.session.query(EntitlementEvent)
        .filter(
            EntitlementEvent.entitlement_id == entitlement_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.event_type == "GRANTED",
        )
        .first()
    )
    if granted_event is None:
        raise FrozenContractError(
            f"No GRANTED entitlement {entitlement_id} for seat {seat_id} in class {class_id}"
        )
    if granted_event.entitlement_type != _INSURANCE_ENTITLEMENT_TYPE:
        raise FrozenContractError(
            f"Entitlement {entitlement_id} is {granted_event.entitlement_type}, not INSURANCE"
        )

    payload = granted_event.payload or {}
    raw_contract = payload.get("frozen_contract")
    if not raw_contract:
        raise FrozenContractError(
            f"GRANTED insurance entitlement {entitlement_id} has no frozen_contract snapshot"
        )

    return parse_frozen_contract(
        raw_contract,
        insurance_policy_uuid=payload.get("insurance_policy_uuid"),
        purchase_metadata=payload.get("purchase_metadata") or {},
    )
