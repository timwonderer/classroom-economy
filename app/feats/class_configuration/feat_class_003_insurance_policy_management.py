"""
FEAT-CLASS-003: Insurance Policy Management (orchestration boundary).

This FEAT is the *orchestrator* of the teacher-directed insurance-policy action.
It is deliberately thin on economics: it does NOT reimplement the Economic Engine
and it does NOT persist definition rows itself. Its whole job is to decide
**lawfulness** and then coordinate the write:

    Teacher submission
        → FEAT-CLASS-003 resolves canonical class/teacher context
        → asks the Economic Engine for recommendation metadata (advisory only)
        → validates ONLY actual contract legality (hard bounds + per-type
          structural subset), allowing values outside recommended ranges
        → delegates the immutable definition write to FEAT-POL-001
        → returns the fresh ``policy_uuid`` row.

Three-layer separation (authority):
- Economic Engine (SPEC-ECON-003): computes recommendations / derived
  consequences / exposes hard bounds. Advisory; enforces nothing at write time.
- FEAT-CLASS-003 (this module, DOM-CLASS spec §VII): decides lawfulness. Allows
  out-of-recommendation-range teacher values; rejects hard-bound and
  type-structure violations; coordinates the write. SHALL NOT mutate policy
  definitions directly — it delegates to FEAT-POL-001.
- FEAT-POL-001 (``policy_reference_feat`` → ``insurance_definition_service``):
  persists the already-lawful immutable definition; does not reinterpret it.

Immutability (DOM-POL-001): ``policy_uuid`` IS the version. "New" and "edit" both
produce a *fresh* ``policy_uuid`` row; a prior definition is never mutated in place.
Only the availability projection (IN_USE / HIDDEN / RETIRED) may change on an
existing row, via ``set_insurance_definition_availability``.

This module writes NOTHING to ``PolicyVersion`` / ``PolicyTransition`` — that
DOM-CLASS-003 *economic* version-control residue is not the insurance definition
store. There is no fallback to it.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from app.extensions import db
from app.feats.base import requires_feat_context
from app.feats import policy_reference_feat as pol
from app.models import InsurancePolicy, Seat
from app.services import insurance_definition_service as defs
from app.services import economic_engine as ee


# Canonical insurance taxonomy (SPEC-ECON-003 §4.5).
TRANSACTION = "TRANSACTION"
PRODUCTIVITY = "PRODUCTIVITY"
NON_MONETARY = "NON_MONETARY"
INSURANCE_TYPES = frozenset({TRANSACTION, PRODUCTIVITY, NON_MONETARY})

# Lawful coverage periods (SPEC §4.5.2/§4.5.8). Monthly is normalized downstream
# by covered class-local days / 7; BIWEEKLY / SEMESTER are NOT lawful.
CHARGE_FREQUENCIES = frozenset({"WEEKLY", "MONTHLY"})

# Per-type structural contract (SPEC §4.5.3–§4.5.5; mirrors the
# ck_insurance_policies_type_subset DB backstop). "required" fields MUST be
# present & non-null; "forbidden" fields MUST be absent/null.
_TYPE_REQUIRED = {
    TRANSACTION: (
        "reimbursement_percentage",
        "payout_multiple",
        "claims_per_week_equivalent",
        "claim_window_days",
    ),
    PRODUCTIVITY: (
        "reimbursement_percentage",
        "payout_multiple",
        "claimable_dates_per_week_equivalent",
    ),
    NON_MONETARY: (
        "claims_per_week_equivalent",
        "waiting_period_days",
    ),
}
_TYPE_FORBIDDEN = {
    TRANSACTION: (
        "claimable_dates_per_week_equivalent",
        "waiting_period_days",
    ),
    PRODUCTIVITY: (
        "claims_per_week_equivalent",
        "claim_window_days",
        "waiting_period_days",
    ),
    NON_MONETARY: (
        "reimbursement_percentage",
        "payout_multiple",
        "claim_window_days",
        "claimable_dates_per_week_equivalent",
    ),
}

# Typed economic fields and their coercion kind.
_DECIMAL_FIELDS = frozenset(
    {
        "premium",
        "reimbursement_percentage",
        "payout_multiple",
        "claims_per_week_equivalent",
        "claimable_dates_per_week_equivalent",
    }
)
_INT_FIELDS = frozenset({"tier_level", "claim_window_days", "waiting_period_days"})
_TEXT_FIELDS = frozenset({"title", "description", "tier_name", "tier_group"})

# All economic (typed) fields that participate in per-type structure.
_ECONOMIC_FIELDS = (
    "reimbursement_percentage",
    "payout_multiple",
    "claims_per_week_equivalent",
    "claim_window_days",
    "claimable_dates_per_week_equivalent",
    "waiting_period_days",
)


class InsuranceContractViolation(Exception):
    """A submission is not a lawful insurance contract (hard/structural failure).

    Raised BEFORE any delegation to FEAT-POL-001, so an unlawful submission never
    reaches the definition store. Recommendation-range overrides are NOT
    violations — only hard bounds and per-type structure are enforced here.
    """


def _coerce_decimal(field: str, value) -> Decimal:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        raise InsuranceContractViolation(f"{field} must be a number, got {value!r}")


def _coerce_int(field: str, value) -> int:
    try:
        # Reject implicit float truncation surprises by round-tripping through str.
        s = str(value).strip()
        if s != "" and Decimal(s) == Decimal(s).to_integral_value():
            return int(Decimal(s))
        raise ValueError
    except (InvalidOperation, ValueError, AttributeError):
        raise InsuranceContractViolation(f"{field} must be a whole number, got {value!r}")


def _validate_and_build_definition(submission: dict) -> dict:
    """Validate hard legality + per-type structure; return the typed definition dict.

    This is the sole legality gate. It enforces exactly the invariants that are
    real contract law (mirroring the DB CHECK backstops), never the advisory
    recommendation ranges. On any hard/structural failure it raises
    :class:`InsuranceContractViolation`; on success it returns a dict whose keys
    are a subset of the POL writable columns.
    """
    if not isinstance(submission, dict):
        raise InsuranceContractViolation("submission must be a dict of typed fields")

    # --- insurance_type (discriminator) -------------------------------------
    raw_type = submission.get("insurance_type")
    insurance_type = (str(raw_type).strip().upper() if raw_type is not None else "")
    if insurance_type not in INSURANCE_TYPES:
        raise InsuranceContractViolation(
            f"insurance_type must be one of {sorted(INSURANCE_TYPES)}, got {raw_type!r}"
        )

    definition: dict = {"insurance_type": insurance_type}

    # --- common: charge_frequency -------------------------------------------
    raw_freq = submission.get("charge_frequency")
    charge_frequency = (str(raw_freq).strip().upper() if raw_freq is not None else "")
    if charge_frequency not in CHARGE_FREQUENCIES:
        raise InsuranceContractViolation(
            f"charge_frequency must be one of {sorted(CHARGE_FREQUENCIES)} "
            f"(BIWEEKLY/SEMESTER are not lawful), got {raw_freq!r}"
        )
    definition["charge_frequency"] = charge_frequency

    # --- common: premium (>= 0) ---------------------------------------------
    if submission.get("premium") in (None, ""):
        raise InsuranceContractViolation("premium is required")
    premium = _coerce_decimal("premium", submission["premium"])
    if premium < 0:
        raise InsuranceContractViolation("premium must be >= 0")
    definition["premium"] = premium

    # --- per-type structural subset -----------------------------------------
    required = _TYPE_REQUIRED[insurance_type]
    forbidden = _TYPE_FORBIDDEN[insurance_type]

    for field in forbidden:
        if submission.get(field) not in (None, ""):
            raise InsuranceContractViolation(
                f"{insurance_type} must not carry {field}"
            )

    for field in required:
        if submission.get(field) in (None, ""):
            raise InsuranceContractViolation(
                f"{insurance_type} requires {field}"
            )

    # --- coerce + hard-bound the economic fields that apply -----------------
    for field in _ECONOMIC_FIELDS:
        if field not in required:
            continue
        raw = submission[field]
        if field in _DECIMAL_FIELDS:
            val = _coerce_decimal(field, raw)
        else:
            val = _coerce_int(field, raw)

        # Hard non-negativity (mirrors DB CHECKs).
        if val < 0:
            raise InsuranceContractViolation(f"{field} must be >= 0")
        # Hard reimbursement ceiling (SPEC §4.5: reimbursement ≤ 100%).
        if field == "reimbursement_percentage" and val > 100:
            raise InsuranceContractViolation("reimbursement_percentage must be <= 100")
        definition[field] = val

    # --- optional presentation / provenance metadata ------------------------
    if submission.get("tier_level") not in (None, ""):
        tier_level = _coerce_int("tier_level", submission["tier_level"])
        if tier_level < 0:
            raise InsuranceContractViolation("tier_level must be >= 0")
        definition["tier_level"] = tier_level

    for field in _TEXT_FIELDS:
        val = submission.get(field)
        if val not in (None, ""):
            definition[field] = str(val)

    return definition


def _require_teacher_scope(canonical_context, class_id: str) -> None:
    """Fail closed unless ``canonical_context`` is a lawful teacher actor for ``class_id``.

    Canonical context is MANDATORY on every insurance-policy-management action.
    FEAT-CLASS-003 establishes lawfulness *independently* — it does not trust that
    an upstream admin route already performed these checks. Any missing anchor,
    class mismatch, non-teacher role, or a seat that is not the lawful teacher
    actor for the requested class raises :class:`InsuranceContractViolation`
    BEFORE any delegation to FEAT-POL-001.

    Required canonical anchors: ``user_id``, ``class_id``, ``seat_id``,
    ``actor_role``. The seat must exist, belong to the requested class, carry the
    ``teacher`` role, and be owned by the context user.
    """
    if canonical_context is None:
        raise InsuranceContractViolation("Canonical context is required")

    # Required anchors must all be present.
    user_id = getattr(canonical_context, "user_id", None)
    ctx_class_id = getattr(canonical_context, "class_id", None)
    seat_id = getattr(canonical_context, "seat_id", None)
    actor_role = getattr(canonical_context, "actor_role", None)
    if not user_id:
        raise InsuranceContractViolation("Missing canonical user_id")
    if not ctx_class_id:
        raise InsuranceContractViolation("Missing canonical class_id")
    if not seat_id:
        raise InsuranceContractViolation("Missing canonical seat_id")
    if not actor_role:
        raise InsuranceContractViolation("Missing canonical actor_role")

    # Context class must match the requested class (fail-closed cross-class guard).
    if ctx_class_id != class_id:
        raise InsuranceContractViolation(
            f"Class scope mismatch: context {ctx_class_id} != target {class_id}"
        )

    # Only teachers may manage insurance policies.
    if actor_role != "teacher":
        raise InsuranceContractViolation(
            "Only teachers may manage insurance policies"
        )

    # The seat must be the lawful teacher actor for this class.
    teacher_seat = db.session.get(Seat, seat_id)
    if teacher_seat is None:
        raise InsuranceContractViolation("Canonical seat not found")
    if teacher_seat.class_id != class_id:
        raise InsuranceContractViolation("Teacher seat is not in the requested class")
    if getattr(teacher_seat, "role", None) != "teacher":
        raise InsuranceContractViolation("Canonical seat is not a teacher seat")
    if teacher_seat.user_id != user_id:
        raise InsuranceContractViolation(
            "Canonical seat is not owned by the context user"
        )


def recommend_insurance_terms(
    *,
    class_id: str,
    insurance_type: str,
    tier: str = ee.SINGLE,
    coverage_period: str = "weekly",
    covered_calendar_days: Optional[int] = None,
):
    """Advisory recommendation metadata from the Economic Engine (read-only).

    Wraps ``economic_engine.resolve_insurance``. The result is ADVISORY: teachers
    may lawfully configure values outside the returned ``recommended_ranges``.
    FEAT-CLASS-003 never enforces these ranges — only the hard bounds surfaced in
    ``hard_bounds`` (and the DB CHECK backstops) are law. No FEAT context needed:
    this performs no mutation.
    """
    product = str(insurance_type).strip().upper()
    if product not in INSURANCE_TYPES:
        raise InsuranceContractViolation(
            f"insurance_type must be one of {sorted(INSURANCE_TYPES)}, got {insurance_type!r}"
        )
    return ee.resolve_insurance(
        class_id=class_id,
        product=product,
        tier=tier,
        coverage_period=coverage_period,
        covered_calendar_days=covered_calendar_days,
    )


@requires_feat_context("FEAT-CLASS-003")
def configure_insurance_definition(
    *,
    class_id: str,
    submission: dict,
    canonical_context,
    actor_seat_id: Optional[int] = None,
    availability_state: str = defs.IN_USE,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> InsurancePolicy:
    """Validate a teacher insurance submission and store it as a fresh definition.

    Both "new" and "edit" flow through here: each lawful call produces a *new*
    immutable ``policy_uuid`` row (DOM-POL-001). A prior definition is never
    mutated. Validation is hard-legality only — recommendation-range overrides
    are permitted; hard-bound / per-type-structure violations raise
    :class:`InsuranceContractViolation` BEFORE the POL write.

    ``canonical_context`` is MANDATORY: FEAT-CLASS-003 independently establishes
    that the context carries the required anchors, matches the requested class,
    and represents the lawful teacher actor for that class — it never trusts an
    upstream route to have done so. Missing/invalid context fails closed.

    Delegates the actual immutable write to FEAT-POL-001
    (``execute_store_insurance_definition``), propagating the same
    ``correlation_id`` so the nested FEAT context is a lawful re-entry.
    """
    _require_teacher_scope(canonical_context, class_id)
    if actor_seat_id is None:
        actor_seat_id = canonical_context.seat_id

    definition = _validate_and_build_definition(submission)

    return pol.execute_store_insurance_definition(
        class_id=class_id,
        definition=definition,
        actor_seat_id=actor_seat_id,
        availability_state=availability_state,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@requires_feat_context("FEAT-CLASS-003")
def set_insurance_definition_availability(
    *,
    class_id: str,
    policy_uuid: str,
    availability_state: str,
    canonical_context,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> InsurancePolicy:
    """Change ONLY the availability projection of an existing definition.

    Economic/identity fields are never touched (no new ``policy_uuid``). Used for
    deactivate (HIDDEN) and retire (RETIRED). Class-scoped + fail-closed via the
    underlying mechanism; delegates to FEAT-POL-001.

    ``canonical_context`` is MANDATORY: teacher/class scope is established
    independently here (missing/invalid context fails closed) before delegation.
    """
    _require_teacher_scope(canonical_context, class_id)

    return pol.execute_set_insurance_definition_availability(
        class_id=class_id,
        policy_uuid=policy_uuid,
        availability_state=availability_state,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )
