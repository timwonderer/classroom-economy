"""Canonical Store Entitlement Primitives — DOM-STORE-001 v3.0.

Domain primitives for the three canonical tables: entitlements,
entitlement_consumptions, and insurance_claims.

These operate on the v3 canonical schema — NOT on the hall-pass
EntitlementEvent log (which is a separate Productivity domain mechanism).

All time resolution goes through canonical_temporal_resolver (SPEC-TIME-001).
All identity comes from CanonicalContext via context_resolver.
"""

from __future__ import annotations

import uuid
import json
from typing import Literal

import sqlalchemy as sa

from app.extensions import db
from app.feats.base import generate_correlation_id
from app.models import (
    Disposition,
    Entitlement,
    EntitlementConsumption,
    GrantType,
    InsuranceClaim,
    InsuranceClaimStatus,
    ObligationAssessment,
    PolicyVersion,
    RedemptionEvent,
    RedemptionEventAction,
)
from app.utils.canonical_temporal_resolver import (
    SYSTEM_LEVEL_EVALUATION,
    canonical_temporal_resolver,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_utc():
    """Canonical UTC timestamp via temporal resolver."""
    return canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="current_time",
    ).canonical_now_utc


def _new_id() -> str:
    return str(uuid.uuid4())


def _load_policy_payload(version: PolicyVersion) -> dict:
    try:
        return json.loads(version.policy_payload_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# FEAT-STOR-001 — Grant primitives (§VII.A, §XIII.A)
# ---------------------------------------------------------------------------

def grant_entitlement(
    *,
    entitlement_item_id: int,
    target_seat_id: int,
    actor_seat_id: int,
    class_id: str,
    grant_type: GrantType,
    correlation_id: str | None = None,
) -> Entitlement:
    """Create a single atomic entitlement row.

    One call = one entitlement unit.  For a purchase of quantity N, the
    caller (FEAT-STOR-001) calls this N times within the same FEAT
    transaction and correlation lifecycle.

    Returns the persisted Entitlement (flushed, not committed).
    """
    now = _now_utc()
    ent = Entitlement(
        entitlement_id=_new_id(),
        entitlement_item_id=entitlement_item_id,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        class_id=class_id,
        grant_type=grant_type,
        correlation_id=correlation_id or generate_correlation_id(),
        granted_at=now,
    )
    db.session.add(ent)
    db.session.flush()
    return ent


def grant_entitlements_bulk(
    *,
    entitlement_item_id: int,
    target_seat_id: int,
    actor_seat_id: int,
    class_id: str,
    grant_type: GrantType,
    quantity: int,
    correlation_id: str | None = None,
) -> list[Entitlement]:
    """Grant *quantity* atomic entitlements in one batch.

    All rows share the same correlation_id.
    Returns list of persisted Entitlement rows (flushed).
    """
    if quantity < 1:
        raise ValueError("Entitlement grant quantity must be >= 1")

    corr = correlation_id or generate_correlation_id()
    grants = []
    for _ in range(quantity):
        g = grant_entitlement(
            entitlement_item_id=entitlement_item_id,
            target_seat_id=target_seat_id,
            actor_seat_id=actor_seat_id,
            class_id=class_id,
            grant_type=grant_type,
            correlation_id=corr,
        )
        grants.append(g)
    return grants


# ---------------------------------------------------------------------------
# FEAT-STOR-002 — Terminal lifecycle primitives (§VII.B, §XIII.B)
# ---------------------------------------------------------------------------

def _write_terminal_event(
    *,
    entitlement_id: str,
    disposition: Disposition,
    class_id: str,
    target_seat_id: int,
    actor_seat_id: int | None,
    correlation_id: str | None = None,
) -> EntitlementConsumption:
    """Write a single terminal lifecycle fact.

    The unique constraint (entitlement_id, disposition) prevents duplicate
    terminal events of the same type for the same entitlement.
    """
    now = _now_utc()
    consumption = EntitlementConsumption(
        consumption_id=_new_id(),
        entitlement_id=entitlement_id,
        disposition=disposition,
        class_id=class_id,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        correlation_id=correlation_id or generate_correlation_id(),
        timestamp=now,
    )
    db.session.add(consumption)
    db.session.flush()
    return consumption


def consume_entitlement(
    *,
    entitlement_id: str,
    class_id: str,
    target_seat_id: int,
    actor_seat_id: int | None,
    correlation_id: str | None = None,
) -> EntitlementConsumption:
    """Mark an entitlement as CONSUMED (Store-owned exercise, e.g. late-work pass)."""
    return _write_terminal_event(
        entitlement_id=entitlement_id,
        disposition=Disposition.CONSUMED,
        class_id=class_id,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        correlation_id=correlation_id,
    )


from app.feats.base import feat_shell


def _is_insurance_entitlement(entitlement: Entitlement) -> bool:
    if entitlement is None:
        return False
    versions = PolicyVersion.query.filter_by(class_id=entitlement.class_id, domain="insurance").all()
    return any(
        _load_policy_payload(version).get("entitlement_item_id") == entitlement.entitlement_item_id
        for version in versions
    )


@feat_shell("FEAT-STOR-002")
def revoke_entitlement(
    *,
    entitlement_id: str,
    class_id: str,
    target_seat_id: int,
    actor_seat_id: int | None,
    correlation_id: str | None = None,
) -> EntitlementConsumption:
    """Mark an entitlement as REVOKED (provenance-aware, see §XIII.B)."""
    entitlement = Entitlement.query.filter_by(entitlement_id=entitlement_id).first()
    if entitlement is None:
        raise ValueError(f"Entitlement {entitlement_id} not found")
    if _is_insurance_entitlement(entitlement):
        raise ValueError("Insurance entitlements cannot be revoked through FEAT-STOR-002")
    return _write_terminal_event(
        entitlement_id=entitlement_id,
        disposition=Disposition.REVOKED,
        class_id=class_id,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        correlation_id=correlation_id,
    )


@feat_shell("FEAT-STOR-002")
def expire_entitlement(
    *,
    entitlement_id: str,
    class_id: str,
    target_seat_id: int,
    correlation_id: str | None = None,
) -> EntitlementConsumption:
    """Mark an entitlement as EXPIRED (system/time-based)."""
    return _write_terminal_event(
        entitlement_id=entitlement_id,
        disposition=Disposition.EXPIRED,
        class_id=class_id,
        target_seat_id=target_seat_id,
        actor_seat_id=None,
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# Query primitives (§XIII.D)
# ---------------------------------------------------------------------------

def get_entitlement(*, entitlement_id: str) -> Entitlement | None:
    """Return a single entitlement by its domain identifier."""
    return Entitlement.query.filter_by(entitlement_id=entitlement_id).first()


def list_entitlements_for_seat(
    *,
    target_seat_id: int,
    class_id: str,
    entitlement_item_id: int | None = None,
) -> list[Entitlement]:
    """Return all entitlements (active and terminated) for a seat."""
    q = Entitlement.query.filter(
        Entitlement.target_seat_id == target_seat_id,
        Entitlement.class_id == class_id,
    ).order_by(Entitlement.granted_at.asc(), Entitlement.id.asc())
    if entitlement_item_id is not None:
        q = q.filter(Entitlement.entitlement_item_id == entitlement_item_id)
    return q.all()


def list_available_entitlements(
    *,
    target_seat_id: int,
    class_id: str,
    entitlement_item_id: int | None = None,
) -> list[Entitlement]:
    """Return active (non-terminated) Entitlement rows.

    Availability = grant exists AND no authoritative terminal event in
    entitlement_consumptions.  Cross-domain consumption (e.g. hall_pass_logs)
    is not evaluated here — that requires the consuming domain's read surface.
    """
    terminated_ids = (
        db.session.query(EntitlementConsumption.entitlement_id)
        .filter(EntitlementConsumption.class_id == class_id)
        .subquery()
    )

    q = (
        Entitlement.query
        .filter(
            Entitlement.target_seat_id == target_seat_id,
            Entitlement.class_id == class_id,
            ~Entitlement.entitlement_id.in_(
                sa.select(terminated_ids.c.entitlement_id)
            ),
        )
        .order_by(Entitlement.granted_at.asc(), Entitlement.id.asc())
    )
    if entitlement_item_id is not None:
        q = q.filter(Entitlement.entitlement_item_id == entitlement_item_id)

    return q.all()


def get_entitlement_balance(
    *,
    target_seat_id: int,
    class_id: str,
    entitlement_item_id: int | None = None,
) -> int:
    """Count active (non-terminated) entitlements for a seat in a class.

    This is a derived projection (§V.C) — never persisted state.
    """
    terminated_ids = (
        db.session.query(EntitlementConsumption.entitlement_id)
        .filter(EntitlementConsumption.class_id == class_id)
        .subquery()
    )

    q = (
        db.session.query(sa.func.count(Entitlement.id))
        .filter(
            Entitlement.target_seat_id == target_seat_id,
            Entitlement.class_id == class_id,
            ~Entitlement.entitlement_id.in_(
                sa.select(terminated_ids.c.entitlement_id)
            ),
        )
    )
    if entitlement_item_id is not None:
        q = q.filter(Entitlement.entitlement_item_id == entitlement_item_id)

    return q.scalar() or 0


def is_entitlement_available(*, entitlement_id: str) -> bool:
    """Check whether a specific entitlement has no terminal event."""
    return not db.session.query(
        db.session.query(EntitlementConsumption.id)
        .filter(EntitlementConsumption.entitlement_id == entitlement_id)
        .exists()
    ).scalar()


def list_entitlement_history(
    *,
    target_seat_id: int,
    class_id: str,
    entitlement_item_id: int | None = None,
) -> list[dict]:
    """Return entitlement history with terminal event status.

    Each entry contains the grant and its terminal event (if any).
    """
    entitlements = list_entitlements_for_seat(
        target_seat_id=target_seat_id,
        class_id=class_id,
        entitlement_item_id=entitlement_item_id,
    )
    result = []
    for ent in entitlements:
        terminal = EntitlementConsumption.query.filter_by(
            entitlement_id=ent.entitlement_id,
        ).first()
        result.append({
            "entitlement": ent,
            "terminal_event": terminal,
        })
    return result


def get_last_entitlement_end_for_policy_version(
    *,
    class_id: str,
    policy_version_id: int,
):
    """Return the latest end boundary currently enforced for a policy lineage."""
    return (
        db.session.query(sa.func.max(ObligationAssessment.coverage_end_time))
        .filter(
            ObligationAssessment.class_id == class_id,
            ObligationAssessment.policy_version_id == policy_version_id,
            ObligationAssessment.coverage_end_time.isnot(None),
        )
        .scalar()
    )


# ---------------------------------------------------------------------------
# FEAT-STOR-003 — Insurance claim primitives (§VII.C, §XIII.C)
# ---------------------------------------------------------------------------

def submit_insurance_claim(
    *,
    entitlement_id: str,
    target_seat_id: int,
    actor_seat_id: int,
    class_id: str,
    transaction_id: int | None = None,
    claimed_dates: dict | list | None = None,
    correlation_id: str | None = None,
) -> InsuranceClaim:
    """Create a SUBMITTED insurance claim.

    Insurance type is NOT stored on the claim — it is resolvable through
    entitlement_id -> entitlement_item_id -> Class Configuration (§VII.C).
    """
    now = _now_utc()
    claim = InsuranceClaim(
        claim_id=_new_id(),
        class_id=class_id,
        entitlement_id=entitlement_id,
        target_seat_id=target_seat_id,
        actor_seat_id=actor_seat_id,
        transaction_id=transaction_id,
        claimed_dates=claimed_dates,
        status=InsuranceClaimStatus.SUBMITTED,
        correlation_id=correlation_id or generate_correlation_id(),
        submitted_at=now,
    )
    db.session.add(claim)
    db.session.flush()
    return claim


def approve_insurance_claim(
    *,
    claim_id: str,
    decided_by_seat_id: int,
) -> InsuranceClaim:
    """Advance a claim: SUBMITTED -> APPROVED (§XIII.C)."""
    claim = InsuranceClaim.query.filter_by(claim_id=claim_id).first()
    if claim is None:
        raise ValueError(f"Insurance claim {claim_id} not found")
    if claim.status != InsuranceClaimStatus.SUBMITTED:
        raise ValueError(f"Claim {claim_id} already decided ({claim.status.value})")

    now = _now_utc()
    claim.status = InsuranceClaimStatus.APPROVED
    claim.decided_by_seat_id = decided_by_seat_id
    claim.decided_at = now
    db.session.flush()
    return claim


def reject_insurance_claim(
    *,
    claim_id: str,
    decided_by_seat_id: int,
) -> InsuranceClaim:
    """Advance a claim: SUBMITTED -> REJECTED (§XIII.C)."""
    claim = InsuranceClaim.query.filter_by(claim_id=claim_id).first()
    if claim is None:
        raise ValueError(f"Insurance claim {claim_id} not found")
    if claim.status != InsuranceClaimStatus.SUBMITTED:
        raise ValueError(f"Claim {claim_id} already decided ({claim.status.value})")

    now = _now_utc()
    claim.status = InsuranceClaimStatus.REJECTED
    claim.decided_by_seat_id = decided_by_seat_id
    claim.decided_at = now
    db.session.flush()
    return claim


# ---------------------------------------------------------------------------
# Insurance query primitives (§XIII.D)
# ---------------------------------------------------------------------------

def get_insurance_claim(*, claim_id: str) -> InsuranceClaim | None:
    """Return a single insurance claim by its domain identifier."""
    return InsuranceClaim.query.filter_by(claim_id=claim_id).first()


def list_insurance_claims(
    *,
    target_seat_id: int | None = None,
    class_id: str,
    entitlement_id: str | None = None,
    status: InsuranceClaimStatus | None = None,
) -> list[InsuranceClaim]:
    """List insurance claims with optional filters."""
    q = InsuranceClaim.query.filter(InsuranceClaim.class_id == class_id)
    if target_seat_id is not None:
        q = q.filter(InsuranceClaim.target_seat_id == target_seat_id)
    if entitlement_id is not None:
        q = q.filter(InsuranceClaim.entitlement_id == entitlement_id)
    if status is not None:
        q = q.filter(InsuranceClaim.status == status)
    return q.order_by(InsuranceClaim.submitted_at.desc()).all()


# ---------------------------------------------------------------------------
# Display status derivation (shared helper)
# ---------------------------------------------------------------------------

def derive_display_status(entitlement_id: str) -> str:
    """Derive a human-readable display status for an entitlement.

    Resolution order:
      1. Terminal consumption event (CONSUMED/EXPIRED/REVOKED)
      2. Unresolved redemption REQUEST (no APPROVED/REJECTED follow-up)
      3. Default: "purchased" (granted, available)
    """
    consumption = EntitlementConsumption.query.filter_by(
        entitlement_id=entitlement_id,
    ).first()
    if consumption is not None:
        disposition_map = {
            Disposition.CONSUMED: "redeemed",
            Disposition.EXPIRED: "expired",
            Disposition.REVOKED: "revoked",
        }
        return disposition_map.get(consumption.disposition, "purchased")

    # Check for an unresolved REQUEST (no APPROVED or REJECTED event exists).
    has_request = db.session.query(
        RedemptionEvent.query.filter(
            RedemptionEvent.entitlement_id == entitlement_id,
            RedemptionEvent.action == RedemptionEventAction.REQUEST,
        ).exists()
    ).scalar()

    if has_request:
        has_resolution = db.session.query(
            RedemptionEvent.query.filter(
                RedemptionEvent.entitlement_id == entitlement_id,
                RedemptionEvent.action.in_([
                    RedemptionEventAction.APPROVED,
                    RedemptionEventAction.REJECTED,
                ]),
            ).exists()
        ).scalar()
        if not has_resolution:
            return "processing"

    return "purchased"
