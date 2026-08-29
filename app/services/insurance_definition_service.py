"""POL storage/retrieval mechanism for immutable insurance policy definitions.

This is the generic Policies (POL) mechanism for the ``insurance_policies``
definition family (the STOR-owned, POL-managed definition-of-record introduced
in Step 1). It is the successor to the ``PolicyVersion(domain="insurance")``
residue in ``insurance_policy_service`` — the old path drove the DOM-CLASS-003
*economic* version-control tables (``policy_versions`` / ``policy_transitions``:
integer id, ``version_number``, JSON payload, ``is_active``, lineage
transitions), whose shape is architecturally incompatible with the typed,
UUID-keyed, availability-projected ``insurance_policies`` table. This module
does NOT reuse that abstraction and provides no fallback to it.

Scope discipline (DOM-POL-001):

* POL is a *mechanism* domain: it stores and retrieves immutable definition
  rows. It performs **no semantic insurance validation** — it does not decide
  whether 60% reimbursement is appropriate, whether PRODUCTIVITY should carry a
  payout multiple, etc. FEAT-CLASS-003 validates contract conformance to
  SPEC-ECON-003 *before* delegating here. POL relies only on the DB integrity
  CHECKs as structural backstops.
* ``policy_uuid`` IS the version (DOM-POL-001 §VI.0). "Create" and "update" both
  produce a *new* immutable row with a *fresh* ``policy_uuid``; economic and
  identity fields are NEVER mutated in place.
* Only ``availability_state`` (and its retirement metadata) may change on an
  existing definition row (availability projection, DOM-POL-001 §IX).
* Retrieval/listing are class-scoped and fail closed on class mismatch.
* Deletion is intentionally NOT implemented here: DOM-POL-001 §VI.4 permits
  removing a RETIRED row only after live dependencies drain, and that
  dependency-draining path is not yet wired for this family. No new deletion
  policy is invented for insurance.

These functions perform ORM mutations and MUST be invoked inside an active FEAT
context (enforced by ``app.feats.base``). They are the domain-layer callee of
FEAT-POL-001, not a public route surface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional
import uuid

from app.extensions import db
from app.models import InsurancePolicy
from app.utils.canonical_temporal_resolver import utc_now


# Canonical availability projection states (DOM-POL-001 §IX).
IN_USE = "IN_USE"
HIDDEN = "HIDDEN"
RETIRED = "RETIRED"
AVAILABILITY_STATES = frozenset({IN_USE, HIDDEN, RETIRED})

# Writable definition columns. This is a *structural* allow-list (a mechanism
# concern — reject stray keys), NOT semantic validation of the values.
_DEFINITION_FIELDS = frozenset(
    {
        "insurance_type",
        "tier_level",
        "premium",
        "charge_frequency",
        "reimbursement_percentage",
        "payout_multiple",
        "claims_per_week_equivalent",
        "claim_window_days",
        "claimable_dates_per_week_equivalent",
        "waiting_period_days",
        "title",
        "description",
        "tier_name",
        "tier_group",
    }
)


class InsuranceDefinitionServiceError(Exception):
    """Base error for the insurance-definition POL mechanism."""


class InsuranceDefinitionNotFound(InsuranceDefinitionServiceError):
    """No definition exists for the given (class_id, policy_uuid)."""


class InvalidAvailabilityState(InsuranceDefinitionServiceError):
    """Requested availability_state is not a canonical projection state."""


class UnknownDefinitionField(InsuranceDefinitionServiceError):
    """The definition payload carried a key outside the writable column set."""


def create_insurance_definition(
    *,
    class_id: str,
    definition: dict,
    actor_seat_id: Optional[int] = None,
    availability_state: str = IN_USE,
    created_at: Optional[datetime] = None,
) -> InsurancePolicy:
    """Insert a new immutable insurance definition with a fresh ``policy_uuid``.

    This is the sole write path for both "new" and "update" (a change is a new
    version — a new row — never an in-place mutation of the prior contract).

    ``definition`` carries the typed economic/identity fields (see
    ``_DEFINITION_FIELDS``); unknown keys fail closed. No semantic validation is
    performed here — the DB CHECK constraints are the only structural backstop.
    """
    if not isinstance(definition, dict):
        raise InsuranceDefinitionServiceError("definition must be a dict of typed fields")
    if availability_state not in AVAILABILITY_STATES:
        raise InvalidAvailabilityState(
            f"availability_state {availability_state!r} is not one of {sorted(AVAILABILITY_STATES)}"
        )

    unknown = set(definition) - _DEFINITION_FIELDS
    if unknown:
        raise UnknownDefinitionField(
            f"definition carried non-writable keys: {sorted(unknown)}"
        )

    row = InsurancePolicy(
        policy_uuid=str(uuid.uuid4()),
        class_id=class_id,
        availability_state=availability_state,
        created_at=created_at or utc_now(),
        created_by_seat_id=actor_seat_id,
        **definition,
    )
    db.session.add(row)
    db.session.flush()
    return row


def get_insurance_definition(
    policy_uuid: str, *, class_id: str
) -> Optional[InsurancePolicy]:
    """Return one class-scoped definition, or ``None``.

    Fails closed on class mismatch: a ``policy_uuid`` that exists under a
    different class returns ``None`` rather than leaking the row.
    """
    return (
        db.session.query(InsurancePolicy)
        .filter(
            InsurancePolicy.policy_uuid == policy_uuid,
            InsurancePolicy.class_id == class_id,
        )
        .first()
    )


def list_insurance_definitions(
    *,
    class_id: str,
    availability_states: Optional[Iterable[str]] = None,
) -> list[InsurancePolicy]:
    """List class-scoped definitions, newest first, with explicit availability filtering.

    When ``availability_states`` is None, all states are returned. Callers that
    want only selectable definitions pass ``[IN_USE]`` explicitly — this
    mechanism does not silently hide RETIRED/HIDDEN rows.
    """
    query = db.session.query(InsurancePolicy).filter(
        InsurancePolicy.class_id == class_id
    )
    if availability_states is not None:
        states = list(availability_states)
        unknown = set(states) - AVAILABILITY_STATES
        if unknown:
            raise InvalidAvailabilityState(
                f"unknown availability_states filter: {sorted(unknown)}"
            )
        query = query.filter(InsurancePolicy.availability_state.in_(states))
    return query.order_by(
        InsurancePolicy.created_at.desc(), InsurancePolicy.policy_uuid.desc()
    ).all()


def set_availability(
    *,
    policy_uuid: str,
    class_id: str,
    availability_state: str,
    retired_at: Optional[datetime] = None,
) -> InsurancePolicy:
    """Change ONLY the availability projection (and retirement metadata).

    Economic/identity fields are never touched. Transitioning to ``RETIRED``
    stamps ``retired_at`` (defaulting to now); other transitions leave the
    economic contract and prior retirement metadata untouched. Class-scoped and
    fail-closed: a mismatched class raises :class:`InsuranceDefinitionNotFound`.
    """
    if availability_state not in AVAILABILITY_STATES:
        raise InvalidAvailabilityState(
            f"availability_state {availability_state!r} is not one of {sorted(AVAILABILITY_STATES)}"
        )

    row = get_insurance_definition(policy_uuid, class_id=class_id)
    if row is None:
        raise InsuranceDefinitionNotFound(
            f"Insurance definition {policy_uuid} not found in class {class_id}"
        )

    row.availability_state = availability_state
    if availability_state == RETIRED:
        row.retired_at = retired_at or utc_now()

    db.session.add(row)
    db.session.flush()
    return row


def retire_insurance_definition(
    *, policy_uuid: str, class_id: str, retired_at: Optional[datetime] = None
) -> InsurancePolicy:
    """Mark a definition RETIRED (permanently unavailable for new selection)."""
    return set_availability(
        policy_uuid=policy_uuid,
        class_id=class_id,
        availability_state=RETIRED,
        retired_at=retired_at,
    )


def hide_insurance_definition(
    *, policy_uuid: str, class_id: str
) -> InsurancePolicy:
    """Mark a definition HIDDEN (temporarily unavailable; may return to IN_USE)."""
    return set_availability(
        policy_uuid=policy_uuid,
        class_id=class_id,
        availability_state=HIDDEN,
    )
