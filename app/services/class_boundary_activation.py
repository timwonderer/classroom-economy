"""CLASS next-boundary policy activation (DOM-CLASS-003, slice 8.3c).

A narrow policy-lineage command: at a payroll boundary that has **already been
established as lawful by PROD/FEAT orchestration**, apply the class's authoritative
pending ``next_boundary`` policy transition exactly once.

    find the authoritative pending next_boundary transition for the class
        exactly one?  ── none → lawful no-op
                       └─ >1   → fail closed (never guess by timestamp)
        activate its target version
        deactivate the prior active version (same class + domain)
        mark the transition applied, record applied_at
        NO COMMIT

Held hard:
* **No boundary interpretation inside CLASS.** The caller supplies a boundary that
  is already lawful; this command never asks whether payroll "really completed"
  (that is PROD/orchestration authority, DOM-CLASS-003).
* **Exactly one authoritative pending transition.** Zero → no-op; more than one →
  fail closed. Only ``next_boundary`` (``next_payroll``) transitions can claim
  authority at a payroll boundary; ``manual`` / ``immediate`` / ``next_renewal``
  pending transitions are left untouched.
* **Cross-scope corruption fails closed.** A target (or source) policy version that
  does not belong to the transition's class/domain is rejected, never applied.
* **No commit.** The orchestrator owns atomicity (same pattern as 8.3b).

The ``next_boundary`` activation mode is spelled ``next_payroll`` in the policy
lineage vocabulary (``economy_rebalance``); this command uses that constant.
"""

from __future__ import annotations

from typing import NamedTuple

from app.extensions import db
from app.models import PolicyTransition, PolicyVersion
from app.utils.economy_rebalance import (
    POLICY_TRANSITION_STATUS_APPLIED,
    REBALANCE_ACTIVATION_NEXT_PAYROLL,
    _get_pending_policy_transitions_for_class,
)

# The "next boundary" activation mode in the policy-lineage vocabulary.
NEXT_BOUNDARY_ACTIVATION_MODE = REBALANCE_ACTIVATION_NEXT_PAYROLL


class BoundaryActivationConflict(Exception):
    """Raised when more than one pending transition can claim authority at the
    boundary. The command never guesses which one wins — it fails closed."""


class BoundaryActivationError(Exception):
    """Raised on a cross-scope corruption: a target/source policy version that does
    not belong to the transition's class/domain. Never applied."""


class BoundaryActivationResult(NamedTuple):
    """Outcome of a boundary activation attempt.

    ``applied`` is ``True`` when a transition was activated this call, ``False`` for
    a lawful no-op (no authoritative pending transition — the natural idempotent
    result on replay, once the transition is already applied).
    """

    applied: bool
    transition: PolicyTransition | None
    activated_version: PolicyVersion | None
    deactivated_version: PolicyVersion | None


def _authoritative_pending(class_id: str) -> list[PolicyTransition]:
    """Pending transitions that can claim authority at a payroll boundary."""
    return [
        transition
        for transition in _get_pending_policy_transitions_for_class(class_id)
        if (transition.activation_mode or "").lower() == NEXT_BOUNDARY_ACTIVATION_MODE
    ]


def apply_next_boundary_transition(
    *, class_id: str, boundary_at
) -> BoundaryActivationResult:
    """Apply the class's authoritative pending ``next_boundary`` transition (§8.3c).

    ``boundary_at`` is a lawful boundary already established by the caller; this
    command does not validate it. Runs inside the caller's FEAT transaction —
    ``add``/``flush`` only, never commits.
    """
    if not class_id or boundary_at is None:
        raise ValueError("class_id and a lawful boundary_at are required")

    pending = _authoritative_pending(class_id)
    if not pending:
        # No transition claims authority at this boundary — lawful no-op. (On a
        # replay where the transition is already applied, this is the result.)
        return BoundaryActivationResult(
            applied=False, transition=None, activated_version=None, deactivated_version=None
        )
    if len(pending) > 1:
        raise BoundaryActivationConflict(
            f"{len(pending)} pending next_boundary transitions can claim authority for "
            f"class {class_id}; refusing to guess (DOM-CLASS-003)."
        )

    transition = pending[0]
    target = db.session.get(PolicyVersion, transition.target_policy_version_id)
    if target is None:
        raise BoundaryActivationError(
            f"pending transition {transition.id} has no target policy version."
        )
    if target.class_id != class_id or target.domain != transition.domain:
        raise BoundaryActivationError(
            f"target policy version {target.id} is out of scope for transition "
            f"{transition.id} (class/domain mismatch); refusing to activate."
        )
    if transition.source_policy_version_id is not None:
        source = db.session.get(PolicyVersion, transition.source_policy_version_id)
        if source is not None and (source.class_id != class_id or source.domain != transition.domain):
            raise BoundaryActivationError(
                f"source policy version {source.id} is out of scope for transition "
                f"{transition.id}; refusing to activate."
            )

    # Deactivate the prior active version(s) for this class + domain.
    deactivated: PolicyVersion | None = None
    prior_active = (
        PolicyVersion.query
        .filter_by(class_id=class_id, domain=transition.domain, is_active=True)
        .all()
    )
    for version in prior_active:
        if version.id == target.id:
            continue
        version.is_active = False
        deactivated = version

    # Activate the target version and mark the transition applied.
    target.is_active = True
    target.activated_at = boundary_at
    transition.status = POLICY_TRANSITION_STATUS_APPLIED
    transition.applied_at = boundary_at
    db.session.flush()

    return BoundaryActivationResult(
        applied=True,
        transition=transition,
        activated_version=target,
        deactivated_version=deactivated,
    )
