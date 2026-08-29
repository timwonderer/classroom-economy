"""
FEAT-POL-001: Policy Reference Management (insurance policy family).

Implements the "New Policy" and future policy-lifecycle actions from
FEAT-POL-001 §V–§VIII for the insurance policy family. Route handlers
call these functions directly instead of wrapping themselves in a FEAT
boundary. Placing the canonical FEAT boundary here keeps the mutation tight
around the domain operation and stops the DIRTY warning from firing on GET loads.

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

from typing import Optional

from app.feats.base import requires_feat_context
from app.models import InsurancePolicy
from app.services import insurance_definition_service as defs


# ---------------------------------------------------------------------------
# FEAT-POL-001 — insurance_policies definition family (typed, UUID-keyed).
#
# These entry points target the Step-1 ``insurance_policies`` definition-of-record
# through the generic POL mechanism (``insurance_definition_service``). They do
# NOT fall back to ``create_policy_version`` / ``PolicyVersion(domain="insurance")``:
# that abstraction models the DOM-CLASS-003 *economic* version-control tables
# (integer id, version_number, JSON payload, is_active, lineage transitions) and
# is structurally incompatible with the typed, availability-projected definition
# rows. The obsolete ``execute_create_insurance_policy_draft`` PolicyVersion
# wrapper has been retired (Step 3): the teacher route now flows
# FEAT-CLASS-003 → FEAT-POL-001 → ``insurance_policies`` with no insurance write
# to PolicyVersion / PolicyTransition.
#
# POL performs no semantic insurance validation here — FEAT-CLASS-003 validates
# SPEC-ECON-003 conformance before delegating. These functions are the immutable
# definition write / availability-projection mechanism only.
# ---------------------------------------------------------------------------


@requires_feat_context("FEAT-POL-001")
def execute_store_insurance_definition(
    *,
    class_id: str,
    definition: dict,
    actor_seat_id: Optional[int] = None,
    availability_state: str = defs.IN_USE,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> InsurancePolicy:
    """Store a new immutable insurance definition (DOM-POL-001 §VI Insert).

    Both "new" and "update" flow through here: each call inserts a fresh
    ``policy_uuid`` row. ``definition`` carries the caller-validated typed fields;
    POL only relies on the DB CHECK backstops for structural integrity.
    """
    return defs.create_insurance_definition(
        class_id=class_id,
        definition=definition,
        actor_seat_id=actor_seat_id,
        availability_state=availability_state,
    )


@requires_feat_context("FEAT-POL-001")
def execute_set_insurance_definition_availability(
    *,
    class_id: str,
    policy_uuid: str,
    availability_state: str,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> InsurancePolicy:
    """Change ONLY the availability projection of an existing definition.

    Availability-only mutation (IN_USE / HIDDEN / RETIRED); economic and identity
    fields are never touched. Retiring stamps ``retired_at``. Class-scoped and
    fail-closed via the underlying mechanism.
    """
    return defs.set_availability(
        policy_uuid=policy_uuid,
        class_id=class_id,
        availability_state=availability_state,
    )
