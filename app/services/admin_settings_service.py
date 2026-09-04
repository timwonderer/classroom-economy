"""Policies-domain commands for the rent policy definition (DOM-POL-001).

``rent_settings`` is an append-only, immutable repository: ``policy_uuid`` *is* the
version (DOM-POL-001 §VI.0). A teacher "editing" rent does not update a row — it
inserts a new one and retires the prior one. Callers must go through
``supersede_rent_settings`` rather than assigning to a fetched row; the model's
``before_update`` guard rejects in-place payload edits outright.
"""

from __future__ import annotations

from app.extensions import db
from app.models import RentSettings
from app.services.class_configuration_query_service import get_rent_settings
from app.utils.canonical_temporal_resolver import utc_now


def create_rent_settings(*, class_id: str) -> RentSettings:
    """Create and flush a canonical rent settings row with default terms."""
    settings = RentSettings(class_id=class_id)
    db.session.add(settings)
    db.session.flush()
    return settings


def supersede_rent_settings(*, class_id: str, updates: dict) -> RentSettings:
    """Record a new immutable rent policy version for ``class_id``.

    This is the ONLY lawful way to change a class's rent terms. Per DOM-POL-001
    §VI.1 every submission — first-time or resubmission — produces a new row with a
    new ``policy_uuid``, and the backend must not infer whether a change is
    "meaningful": a submission is a new contract.

    The new row inherits every payload field from the current policy and then
    applies ``updates``, so a partial submission (the rebalancer changes only
    ``rent_amount``) carries the rest of the contract forward instead of silently
    reverting it to column defaults. The prior row is marked ``RETIRED`` so exactly
    one ``IN_USE`` row remains selectable for new work; it stays readable forever so
    the assessments that froze its ``policy_uuid`` can still resolve their amounts.

    Returns the newly inserted row.
    """
    current = get_rent_settings(class_id)

    carried = {}
    if current is not None:
        for field in RentSettings._FROZEN_POLICY_FIELDS:
            carried[field] = getattr(current, field)

    unknown = set(updates) - set(RentSettings._FROZEN_POLICY_FIELDS)
    if unknown:
        raise ValueError(
            "supersede_rent_settings only accepts immutable definition payload "
            f"fields; got unexpected {sorted(unknown)}"
        )
    carried.update(updates)

    successor = RentSettings(class_id=class_id, **carried)
    successor.rent_configured_at = utc_now()
    successor.availability_state = 'IN_USE'
    db.session.add(successor)

    if current is not None:
        # Availability is the mutable projection over the immutable row
        # (DOM-POL-001 §VI.0) — retiring the predecessor does not touch its payload.
        current.availability_state = 'RETIRED'

    db.session.flush()
    return successor
