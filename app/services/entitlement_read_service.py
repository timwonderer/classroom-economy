"""
Entitlement Read Service — Canonical EntitlementEvent Query Layer (DOM-STORE-001 v4.0)

Derives entitlement state from immutable EntitlementEvent rows.

RESPONSIBILITIES:
- Derive available entitlement balance (granted - consumed - expired - revoked)
- Check if entitlement is exercisable (has no terminal event + not expired)
- Get entitlement history for audit
- Derive claim allowance from policy + event history
- Support cross-domain consumption checks (e.g., hall-pass used by Productivity)

INVARIANT:
- This service does NOT persist mutable counters (uses_remaining, balance, etc.)
- All state is derived from event history
- Safe for read-after-write consistency

Used by:
- Routes needing to display entitlement status
- FEATs validating entitlement exercisability
- Cross-domain services checking consumption state
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.extensions import db
from app.models import EntitlementEvent


# ---------------------------------------------------------------------------
# Entitlement Balance Derivation
# ---------------------------------------------------------------------------


def get_entitlement_balance(
    seat_id: int,
    class_id: str,
    entitlement_type: str,
    product_id: Optional[int] = None,
    reference_time_utc: Optional[datetime] = None,
) -> int:
    """
    Derive available entitlements from EntitlementEvent history.

    Counts:
    - GRANTED events (acquisition)
    - Minus CONSUMED events (used)
    - Minus EXPIRED events (time-limited)
    - Minus REVOKED events (withdrawn)

    Args:
        seat_id: Target seat
        class_id: Class scope
        entitlement_type: HALL_PASS, INSURANCE, PRIVILEGE, etc.
        product_id: Optional product filter
        reference_time_utc: Optional timestamp for expiration checks

    Returns:
        Available count (may be negative if overclaimed)
    """
    # Count GRANTED events
    granted = (
        db.session.query(db.func.count(EntitlementEvent.event_id))
        .filter(
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.entitlement_type == entitlement_type,
            EntitlementEvent.event_type == "GRANTED",
        )
    )
    if product_id is not None:
        granted = granted.filter(EntitlementEvent.product_id == product_id)

    granted_count = granted.scalar() or 0

    # Count terminal events (consumed, expired, revoked)
    terminal = (
        db.session.query(db.func.count(EntitlementEvent.event_id))
        .filter(
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.entitlement_type == entitlement_type,
            EntitlementEvent.event_type.in_(["CONSUMED", "EXPIRED", "REVOKED"]),
        )
    )
    if product_id is not None:
        terminal = terminal.filter(EntitlementEvent.product_id == product_id)

    terminal_count = terminal.scalar() or 0

    return granted_count - terminal_count


def is_entitlement_exercisable(
    entitlement_id: str,
    class_id: str,
    reference_time_utc: Optional[datetime] = None,
) -> bool:
    """
    Check if an entitlement is exercisable (no terminal event + not expired).

    Args:
        entitlement_id: The entitlement lineage ID
        class_id: Class scope
        reference_time_utc: Time to check expiration against

    Returns:
        True if entitlement can still be used
    """
    # Check if any terminal event exists for this entitlement
    terminal_event = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.entitlement_id == entitlement_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.event_type.in_(["CONSUMED", "EXPIRED", "REVOKED"]),
        )
        .first()
    )

    if terminal_event:
        return False

    # TODO: Check if expired per policy window
    # (requires reading policy configuration)

    return True


def get_entitlement_history(
    seat_id: int,
    class_id: str,
    product_id: Optional[int] = None,
    limit: int = 100,
) -> list[dict]:
    """
    Return EntitlementEvent rows for audit/display.

    Args:
        seat_id: Target seat
        class_id: Class scope
        product_id: Optional product filter
        limit: Max rows to return

    Returns:
        List of event dicts in chronological order
    """
    query = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.class_id == class_id,
        )
        .order_by(EntitlementEvent.timestamp.desc())
        .limit(limit)
    )

    if product_id is not None:
        query = query.filter(EntitlementEvent.product_id == product_id)

    return [
        {
            "event_id": e.event_id,
            "entitlement_id": e.entitlement_id,
            "event_type": e.event_type,
            "acquisition_type": e.acquisition_type,
            "entitlement_type": e.entitlement_type,
            "product_id": e.product_id,
            "timestamp": e.timestamp.isoformat(),
            "correlation_id": e.correlation_id,
        }
        for e in query.all()
    ]


# ---------------------------------------------------------------------------
# Cross-Domain Consumption Checks
# ---------------------------------------------------------------------------


def get_entitlement_lineage_terminal_event(
    entitlement_id: str,
    class_id: str,
) -> Optional[EntitlementEvent]:
    """
    Get the terminal event for an entitlement lineage (if any).

    Used by cross-domain services to detect consumption.
    For example, Productivity domain checks if hall-pass was consumed.

    Returns:
        Terminal event (CONSUMED, EXPIRED, REVOKED) or None if exercisable
    """
    return (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.entitlement_id == entitlement_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.event_type.in_(["CONSUMED", "EXPIRED", "REVOKED"]),
        )
        .first()
    )


def list_entitlements_for_seat(
    seat_id: int,
    class_id: str,
    entitlement_type: Optional[str] = None,
) -> list[dict]:
    """
    List all entitlements for a seat (all events, not just available).

    Used for display and audit purposes.
    """
    query = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.class_id == class_id,
        )
        .order_by(EntitlementEvent.timestamp.desc())
    )

    if entitlement_type:
        query = query.filter(EntitlementEvent.entitlement_type == entitlement_type)

    return [
        {
            "event_id": e.event_id,
            "entitlement_id": e.entitlement_id,
            "event_type": e.event_type,
            "acquisition_type": e.acquisition_type,
            "entitlement_type": e.entitlement_type,
            "product_id": e.product_id,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in query.all()
    ]


# ---------------------------------------------------------------------------
# Claim Allowance Derivation (Insurance-Specific)
# ---------------------------------------------------------------------------


def derive_claim_allowance(
    entitlement_id: str,
    class_id: str,
    policy_config: dict,
    reference_time_utc: datetime,
) -> int:
    """
    Derive remaining claims from policy rules + EntitlementEvent history.

    INVARIANT: Do not query a persisted claims_remaining counter.
    Always derive from policy rules + event history.

    Args:
        entitlement_id: Insurance entitlement lineage
        class_id: Class scope
        policy_config: Dict with claim limits (e.g., {"max_claims_per_month": 3})
        reference_time_utc: Current time for period calculation

    Returns:
        Remaining claims allowed (e.g., 2 out of 3)
    """
    # Get all CONSUMED events for this entitlement (represent claims used)
    consumed_events = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.entitlement_id == entitlement_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.event_type == "CONSUMED",
        )
        .order_by(EntitlementEvent.timestamp)
        .all()
    )

    # TODO: Apply period filters (e.g., within current month) based on policy_config
    # For MVP, return max_claims - used_count

    max_claims = policy_config.get("max_claims_per_month", 3)
    used_count = len([e for e in consumed_events])  # TODO: filter by period

    return max(0, max_claims - used_count)


# ---------------------------------------------------------------------------
# Store Purchase Query Helpers (Operational Support)
# ---------------------------------------------------------------------------


def get_purchase_count(
    seat_id: int,
    class_id: str,
    product_id: int,
) -> int:
    """
    Count how many times a seat has purchased a specific product.

    Queries GRANTED events with acquisition_type='PURCHASE' for the product.

    Args:
        seat_id: Target seat
        class_id: Class scope
        product_id: Product identifier

    Returns:
        Number of times this product was purchased by this seat
    """
    purchase_count = (
        db.session.query(db.func.count(EntitlementEvent.event_id))
        .filter(
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.product_id == product_id,
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PURCHASE",
        )
        .scalar() or 0
    )
    return purchase_count


def get_active_rent_grant(
    seat_id: int,
    class_id: str,
    product_id: int,
    reference_time_utc: Optional[datetime] = None,
) -> Optional[EntitlementEvent]:
    """
    Get an active per-use entitlement from rent (if any).

    Returns the most recent GRANTED event with acquisition_type='PERK' for the product
    that hasn't been CONSUMED yet.

    Args:
        seat_id: Target seat
        class_id: Class scope
        product_id: Product identifier
        reference_time_utc: Optional timestamp for expiration checks

    Returns:
        EntitlementEvent if an active rent grant exists, else None
    """
    # Get GRANTED events with acquisition_type='PERK'
    grant_event = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.product_id == product_id,
            EntitlementEvent.event_type == "GRANTED",
            EntitlementEvent.acquisition_type == "PERK",
        )
        .order_by(EntitlementEvent.timestamp.desc())
        .first()
    )

    if not grant_event:
        return None

    # Check if this entitlement has a terminal event (CONSUMED, EXPIRED, REVOKED)
    terminal_event = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.entitlement_id == grant_event.entitlement_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.event_type.in_(["CONSUMED", "EXPIRED", "REVOKED"]),
        )
        .first()
    )

    if terminal_event:
        return None  # Not active; has terminal event

    return grant_event
