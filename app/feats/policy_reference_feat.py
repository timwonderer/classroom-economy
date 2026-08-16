"""
FEAT-POL-001: Policy Reference Management (insurance policy family).

Implements the "New Policy" and future policy-lifecycle actions from
FEAT-POL-001 §V–§VIII for the insurance policy family. Route handlers
call these functions directly instead of wrapping themselves in
`@feat_shell` — that keeps the FEAT boundary tight around the mutation
and stops the DIRTY warning from firing on GET loads.

Authority:
- FEAT-POL-001 §V ("New Policy") — creating a new immutable definition
  row with a new identifier and family-specific payload.
- FEAT-CLASS-003 §VII — delegates insurance policy creation to
  FEAT-POL-001; this module is the callee.
- DOM-POL-001 §VI (Insert and Availability Contract) — Insert is the
  only lawful way to add a new definition row; each submission is a
  new immutable row.
"""

from __future__ import annotations

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import PolicyVersion
from app.services.insurance_policy_service import create_policy_version


INSURANCE_DRAFT_PAYLOAD_DEFAULTS = {
    "description": "",
    "premium": "0.00",
    "charge_frequency": "monthly",
    "autopay": True,
    "waiting_period_days": 0,
    "claim_time_limit_days": 0,
    "max_claims_count": 0,
    "max_claim_amount": None,
    "max_payout_per_period": None,
    "claim_type": "transaction_monetary",
    "tier_group": None,
    "tier_name": None,
    "tier_color": None,
    "tier_level": None,
    "bundle_with_policy_ids": [],
    "bundle_discount_percent": None,
    "bundle_discount_amount": None,
    "entitlement_item_id": None,
}


@requires_feat_context("FEAT-POL-001")
def execute_create_insurance_policy_draft(
    *,
    class_id: str,
    actor_user_id: int | None,
    title: str,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> PolicyVersion:
    """Create a HIDDEN draft insurance policy per FEAT-POL-001 §V.

    Availability is deliberately requested as HIDDEN (is_active=False)
    because the bootstrap payload is functionally incomplete (premium
    $0, no coverage terms). Students never see the policy until the
    teacher fills it in and explicitly activates it via the edit page.
    This is the explicit "unless the caller requests HIDDEN" exception
    FEAT-POL-001 §V.4 accommodates.

    Args:
        class_id: canonical class scope
        actor_user_id: teacher's user_id for audit lineage
        title: human-readable policy title (validated by caller)
        correlation_id: propagated to FEATContext / audit lineage
        idempotency_key: propagated to FEATContext; caller SHOULD
            provide a stable hash keyed by class_id + title so a
            double-submit from the UI is a no-op

    Returns:
        The newly-inserted PolicyVersion row.
    """
    payload = {
        **INSURANCE_DRAFT_PAYLOAD_DEFAULTS,
        "title": title,
        "is_active": False,  # HIDDEN per §V.4 exception (see docstring above)
    }
    return create_policy_version(
        class_id=class_id,
        actor_user_id=actor_user_id,
        payload=payload,
        source_version=None,
        is_active=False,
        activation_mode="manual",
        status="applied",
    )
