"""Purchase-time insurance contract freezing (Step 5).

At purchase/grant time an INSURANCE entitlement must capture a *self-sufficient*
snapshot of the immutable ``InsurancePolicy`` it was bought under, so that claim
decisions can trust the entitlement without consulting current class
configuration. Once GRANTED, later HIDDEN / RETIRED / deleted source definitions
must not change the purchased contract.

This module builds that snapshot via an **explicit, type-specific projection** of
the immutable definition — never ``row.__dict__``, generic serialization, or a
copy of the StoreProduct payload. Only claim-time contract truth is frozen;
derived, display, provenance, and recommendation fields are deliberately excluded
(they either remain derived or are not claim-time truth).

Frozen subset per SPEC-ECON-003 insurance taxonomy:

- TRANSACTION: insurance_type, premium, charge_frequency, reimbursement_percentage,
  payout_multiple, claims_per_week_equivalent, claim_window_days
- PRODUCTIVITY: insurance_type, premium, charge_frequency, reimbursement_percentage,
  payout_multiple, claimable_dates_per_week_equivalent
- NON_MONETARY: insurance_type, premium, charge_frequency, claims_per_week_equivalent,
  waiting_period_days

Never frozen (contract truth boundary): maximum_policy_payout, period premium,
coverage week-equivalent, recommendation metadata, availability state, provenance
timestamps, creator identity.

``purchase_metadata`` preserves presentation-only fields (tier_level, tier_name,
title) for historical display; claims MUST NEVER consume those.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from app.models import InsurancePolicy


TRANSACTION = "TRANSACTION"
PRODUCTIVITY = "PRODUCTIVITY"
NON_MONETARY = "NON_MONETARY"


class InsuranceFreezeError(Exception):
    """Raised when an insurance definition cannot be lawfully frozen."""


def _num(value: Optional[Decimal]) -> Optional[str]:
    """JSON-safe exact numeric: Decimal → string, preserving scale."""
    if value is None:
        return None
    return str(value)


def _int(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def build_frozen_contract(policy: InsurancePolicy) -> Dict[str, Any]:
    """Project the immutable definition into a claim-time contract snapshot.

    Type-specific: only the lawful subset for ``policy.insurance_type`` is
    emitted. Numeric terms are stringified for exactness in JSON.

    Raises:
        InsuranceFreezeError: unknown insurance_type (should be impossible given
            the DB CHECK, but we fail closed rather than silently under-freeze).
    """
    itype = policy.insurance_type

    if itype == TRANSACTION:
        return {
            "insurance_type": TRANSACTION,
            "premium": _num(policy.premium),
            "charge_frequency": policy.charge_frequency,
            "reimbursement_percentage": _num(policy.reimbursement_percentage),
            "payout_multiple": _num(policy.payout_multiple),
            "claims_per_week_equivalent": _num(policy.claims_per_week_equivalent),
            "claim_window_days": _int(policy.claim_window_days),
        }

    if itype == PRODUCTIVITY:
        return {
            "insurance_type": PRODUCTIVITY,
            "premium": _num(policy.premium),
            "charge_frequency": policy.charge_frequency,
            "reimbursement_percentage": _num(policy.reimbursement_percentage),
            "payout_multiple": _num(policy.payout_multiple),
            "claimable_dates_per_week_equivalent": _num(
                policy.claimable_dates_per_week_equivalent
            ),
        }

    if itype == NON_MONETARY:
        return {
            "insurance_type": NON_MONETARY,
            "premium": _num(policy.premium),
            "charge_frequency": policy.charge_frequency,
            "claims_per_week_equivalent": _num(policy.claims_per_week_equivalent),
            "waiting_period_days": _int(policy.waiting_period_days),
        }

    raise InsuranceFreezeError(f"Cannot freeze unknown insurance_type: {itype!r}")


def build_purchase_metadata(policy: InsurancePolicy) -> Dict[str, Any]:
    """Presentation-only historical metadata (NEVER claim-time truth).

    Preserves tier_level, tier_name, and title for display. Claims must not
    consume these fields.
    """
    return {
        "tier_level": _int(policy.tier_level),
        "tier_name": policy.tier_name,
        "title": policy.title,
    }
