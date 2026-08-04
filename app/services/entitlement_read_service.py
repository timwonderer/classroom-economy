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

    Formula: (GRANTED count) - (CONSUMED + EXPIRED + REVOKED count)

    Preconditions:
    - seat_id must be valid in class
    - class_id must exist
    - entitlement_type must be one of: HALL_PASS, INSURANCE, PRIVILEGE, IMMEDIATE_USE, DELAYED_USE, COLLECTIVE_GOAL
    - If reference_time_utc provided, used for expiration window checks (TODO)

    Args:
        seat_id: Target seat
        class_id: Class scope
        entitlement_type: Entitlement type (see preconditions)
        product_id: Optional product filter
        reference_time_utc: Optional timestamp for expiration checks (not yet used)

    Returns:
        Available count as integer (may be negative if overclaimed)

    Purity: Pure (read-only query, deterministic result based on immutable events)
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

    Preconditions:
    - entitlement_id must exist with event_type='GRANTED'
    - class_id must be valid
    - If reference_time_utc provided, used for expiration checks (TODO: not yet implemented)

    Args:
        entitlement_id: The entitlement lineage ID
        class_id: Class scope
        reference_time_utc: Time to check expiration against (not yet used)

    Returns:
        True if entitlement has no terminal event (can still be used)

    Purity: Pure (read-only query)

    Note: Expiration window checks not yet implemented. Currently only checks
          for terminal events (CONSUMED, EXPIRED, REVOKED).
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
    Return all EntitlementEvent rows for a seat (audit trail).

    Returns events in reverse chronological order (newest first).

    Preconditions:
    - seat_id must be valid in class
    - class_id must exist
    - limit must be positive integer

    Args:
        seat_id: Target seat
        class_id: Class scope
        product_id: Optional product filter (if provided, only returns events for this product)
        limit: Max rows to return (default 100)

    Returns:
        List of event dicts (newest first), each containing:
        - event_id, entitlement_id, event_type, acquisition_type, entitlement_type,
          product_id, timestamp (ISO format), correlation_id

    Purity: Pure (read-only query)

    Freshness: Point-in-time snapshot at query time
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

def get_hall_pass_balance(
    seat_id: int,
    class_id: str,
) -> int:
    """
    Derive the available hall-pass balance for a seat.

    Hall-pass availability is computed from immutable entitlement events only.
    This remains a pure read and does not rely on any mutable counter column.

    Preconditions:
    - seat_id must be valid in class
    - class_id must exist

    Returns:
        Net hall-pass balance for the seat in the class.

    Purity: Pure (read-only query, deterministic result)
    """
    return get_entitlement_balance(
        seat_id=seat_id,
        class_id=class_id,
        entitlement_type="HALL_PASS",
    )
# ---------------------------------------------------------------------------
# Cross-Domain Consumption Checks
# ---------------------------------------------------------------------------


def get_entitlement_lineage_terminal_event(
    entitlement_id: str,
    class_id: str,
) -> Optional[EntitlementEvent]:
    """
    Get the terminal event for an entitlement lineage (if any).

    Used by cross-domain services to detect if entitlement has been consumed/expired/revoked.
    Example: Productivity domain checks if hall-pass was consumed before logging usage.

    Preconditions:
    - entitlement_id must exist with event_type='GRANTED'
    - class_id must be valid

    Returns:
        Terminal event object (CONSUMED, EXPIRED, or REVOKED) if one exists, else None

    Purity: Pure (read-only query)

    Cross-Domain Use: Safe for external domains to call (returns immutable event object)
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
    List all entitlements for a seat (all event types: GRANTED, CONSUMED, EXPIRED, REVOKED).

    Used for display, audit, and dashboard purposes.

    Preconditions:
    - seat_id must be valid in class
    - class_id must exist
    - entitlement_type is optional filter

    Args:
        seat_id: Target seat
        class_id: Class scope
        entitlement_type: Optional filter (HALL_PASS, INSURANCE, PRIVILEGE, etc.)

    Returns:
        List of event dicts (newest first), each containing:
        - event_id, entitlement_id, event_type, acquisition_type, entitlement_type,
          product_id, timestamp (ISO format)

    Purity: Pure (read-only query)

    Note: Returns all events for seat regardless of status. Caller should use
          get_entitlement_status() to determine if entitlement is active.
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
    Derive remaining claims allowed from policy config + EntitlementEvent history.

    INVARIANT: Do NOT query a persisted claims_remaining counter.
    Always derive from policy rules + immutable event history.

    Preconditions:
    - entitlement_id must exist with entitlement_type='INSURANCE'
    - class_id must be valid
    - policy_config must have 'max_claims_per_month' key
    - reference_time_utc must be valid datetime

    Args:
        entitlement_id: Insurance entitlement lineage
        class_id: Class scope
        policy_config: Dict with claim limits (e.g., {"max_claims_per_month": 3})
        reference_time_utc: Current time for period calculation (TODO: not yet used for filtering)

    Returns:
        Remaining claims allowed (e.g., 2 if max is 3 and 1 already used)

    Purity: Pure (read-only query, deterministic derivation)

    Note: Period filtering (e.g., "within current month") not yet implemented.
          Currently counts all CONSUMED events without time window.
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
# Entitlement Status Derivation
# ---------------------------------------------------------------------------


def get_entitlement_status(
    entitlement_id: str,
    class_id: str,
) -> str:
    """
    Derive the current status of an entitlement from its event history.

    Examines terminal events in order of precedence:
    1. REVOKED (administratively withdrawn)
    2. EXPIRED (time window passed)
    3. CONSUMED (used)
    4. GRANTED (default if no terminal event)

    Preconditions:
    - entitlement_id must exist in EntitlementEvent with event_type='GRANTED'
    - class_id must be valid and scope must match

    Returns:
        'GRANTED', 'CONSUMED', 'EXPIRED', 'REVOKED', or 'UNKNOWN'

    Purity: Pure (read-only query, deterministic result)
    """
    # Check for terminal events in precedence order
    for event_type in ["REVOKED", "EXPIRED", "CONSUMED"]:
        event = (
            EntitlementEvent.query
            .filter(
                EntitlementEvent.entitlement_id == entitlement_id,
                EntitlementEvent.class_id == class_id,
                EntitlementEvent.event_type == event_type,
            )
            .first()
        )
        if event:
            return event_type

    # No terminal event found; check if GRANTED exists
    granted = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.entitlement_id == entitlement_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.event_type == "GRANTED",
        )
        .first()
    )

    if granted:
        return "GRANTED"

    return "UNKNOWN"


def get_active_entitlements(
    seat_id: int,
    class_id: str,
    product_id: Optional[int] = None,
    entitlement_type: Optional[str] = None,
) -> list[EntitlementEvent]:
    """
    Get all GRANTED (active, non-terminal) entitlements for a seat.

    Returns GRANTED events; caller should check for terminal events
    if precise availability is needed.

    Preconditions:
    - seat_id must be valid in class
    - class_id must exist
    - product_id and entitlement_type are optional filters

    Args:
        seat_id: Target seat
        class_id: Class scope
        product_id: Optional product filter
        entitlement_type: Optional entitlement type filter

    Returns:
        List of GRANTED EntitlementEvent objects

    Purity: Pure (read-only query)
    """
    query = (
        EntitlementEvent.query
        .filter(
            EntitlementEvent.target_seat_id == seat_id,
            EntitlementEvent.class_id == class_id,
            EntitlementEvent.event_type == "GRANTED",
        )
    )

    if product_id is not None:
        query = query.filter(EntitlementEvent.product_id == product_id)

    if entitlement_type is not None:
        query = query.filter(EntitlementEvent.entitlement_type == entitlement_type)

    return query.all()


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

    Preconditions:
    - seat_id must be valid in class
    - class_id must exist
    - product_id must be valid

    Args:
        seat_id: Target seat
        class_id: Class scope
        product_id: Product identifier

    Returns:
        Number of times this product was purchased by this seat

    Purity: Pure (read-only, deterministic count)
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
