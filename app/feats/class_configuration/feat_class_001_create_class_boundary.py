"""
FEAT-CLASS-001: Create Class Boundary (v1.0)

Orchestrates canonical class creation per DOM-CLASS-001:
- Creates immutable ClassEconomy (classes table) with unique join_code
- Creates initial EconomicEngine version
- Seeds default ClassFeature rows via ORM event listener
- Enforces teacher authority and IANA timezone validation

Authority: DOM-CLASS-001, DOM-CLASS-002, INV-ARC-015, INV-ARC-016, SPEC-TIME-001
Sole lawful writer for: classes table (ClassEconomy model)

HIGH Blast Radius: Requires idempotency_key (mandatory per FEAT-CORE-000)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import secrets
import uuid

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.base import requires_feat_context
from app.models import ClassEconomy, User, Seat
from app.services.class_configuration_query_service import (
    get_initial_economic_engine,
)
from app.services.context_resolver import CanonicalContext
from app.utils.canonical_temporal_resolver import canonical_temporal_resolver, CLASS_LEVEL_EVALUATION, SYSTEM_LEVEL_EVALUATION


class CreateClassBoundaryError(Exception):
    """Raised when class creation validation or execution fails."""
    pass


@dataclass
class CreateClassBoundaryResult:
    """Result of successful class boundary creation."""
    success: bool
    correlation_id: str
    class_id: Optional[str] = None
    join_code: Optional[str] = None
    teacher_user_id: Optional[int] = None
    initial_engine_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def execute_create_class_boundary(
    *,
    canonical_context: CanonicalContext,
    class_name: str,
    timezone: Optional[str] = None,
    expected_weekly_hours: float | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> CreateClassBoundaryResult:
    """
    Execute lawful teacher-directed class creation.

    Args:
        canonical_context: CanonicalContext with user_id, class_id (ignored), seat_id, actor_role="teacher"
        class_name: Display name for the class (e.g., "Period 3 Economics")
        timezone: IANA timezone for class-local time evaluation. REQUIRED — a
                  class is never born timezone-less. Blank/missing fails closed
                  (no silent UTC default); an explicit "UTC" is canonicalized to
                  "Etc/UTC"; any other value must be a valid IANA name.
        expected_weekly_hours: Optional initial value for EconomicEngine.expected_weekly_hours
                               (used for CWI calculation). Defaults to None (unset).
        correlation_id: Optional; generated if not provided
        idempotency_key: Required (HIGH blast radius). Format: feat:class:create:<teacher_user_id>:<join_code>

    Returns:
        CreateClassBoundaryResult with success status and class details

    Contract: Teacher authority is validated via CanonicalContext.
    Class creation is immutable once committed.
    """
    return _execute_create_class_boundary_impl(
        canonical_context=canonical_context,
        class_name=class_name,
        timezone=timezone,
        expected_weekly_hours=expected_weekly_hours,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@requires_feat_context("FEAT-CLASS-001")
def _execute_create_class_boundary_impl(
    *,
    canonical_context: CanonicalContext,
    class_name: str,
    timezone: Optional[str] = None,
    expected_weekly_hours: float | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> CreateClassBoundaryResult:
    """
    Internal implementation wrapped in @requires_feat_context for context management.
    """

    # =========================================================================
    # PHASE 1: Read-Only Validation
    # =========================================================================

    # Validate canonical context
    if not canonical_context or not canonical_context.seat_id:
        return CreateClassBoundaryResult(
            success=False,
            correlation_id="",
            error_code="INVALID_CONTEXT",
            error_message="Missing canonical context (seat_id)",
        )

    # Validate actor is teacher
    if getattr(canonical_context, "actor_role", None) != "teacher":
        return CreateClassBoundaryResult(
            success=False,
            correlation_id="",
            error_code="UNAUTHORIZED",
            error_message="Only teachers can create classes",
        )

    # Validate teacher seat exists
    teacher_seat = db.session.get(Seat, canonical_context.seat_id)
    if not teacher_seat or teacher_seat.user_id != canonical_context.user_id:
        return CreateClassBoundaryResult(
            success=False,
            correlation_id="",
            error_code="SEAT_NOT_FOUND",
            error_message="Teacher seat not found or does not belong to user",
        )

    # Validate teacher user exists
    teacher_user = db.session.get(User, canonical_context.user_id)
    if not teacher_user:
        return CreateClassBoundaryResult(
            success=False,
            correlation_id="",
            error_code="USER_NOT_FOUND",
            error_message="Teacher user not found",
        )

    # Validate timezone via the single shared canonicalizer. The class-creation
    # invariant is enforced here identically to the create_class() service path:
    # a class is never born timezone-less (blank/missing fails closed, no silent
    # UTC default), an explicit UTC selection is canonicalized to 'Etc/UTC', and
    # any other value must be a valid IANA name. We reuse the validation LOGIC
    # rather than duplicating it; we do NOT delegate the constructor itself,
    # because create_class() also creates a teacher Seat/IdentityProfile and
    # rebinds last_active pointers — this FEAT boundary creates only the class
    # for an already-seated teacher, so calling create_class() here would
    # double-create a seat and corrupt those pointers.
    from app.services.classroom_setup import canonicalize_class_timezone
    try:
        normalized_timezone = canonicalize_class_timezone(timezone)
    except ValueError as e:
        return CreateClassBoundaryResult(
            success=False,
            correlation_id="",
            error_code="INVALID_TIMEZONE",
            error_message=str(e),
        )

    # Validate class_name
    if not class_name or not isinstance(class_name, str) or len(class_name) > 100:
        return CreateClassBoundaryResult(
            success=False,
            correlation_id="",
            error_code="INVALID_CLASS_NAME",
            error_message="Class name must be a non-empty string up to 100 characters",
        )

    # Replay guard: idempotency_key is documented as required for this HIGH blast-radius
    # FEAT, but storage for key matching is not yet available. The DB unique constraint
    # on join_code prevents true duplicates. A future migration will add an
    # idempotency_key column to support proper replay detection.
    if not idempotency_key:
        return CreateClassBoundaryResult(
            success=False,
            correlation_id="",
            error_code="IDEMPOTENCY_KEY_REQUIRED",
            error_message="idempotency_key is required for class creation (HIGH blast radius)",
        )

    # Generate join_code (6-character alphanumeric, uppercase) using secrets module
    _ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    max_attempts = 10
    join_code = None
    for _attempt in range(max_attempts):
        candidate = ''.join(secrets.choice(_ALPHABET) for _ in range(6))
        if not db.session.query(ClassEconomy).filter_by(join_code=candidate).first():
            join_code = candidate
            break

    if not join_code:
        return CreateClassBoundaryResult(
            success=False,
            correlation_id="",
            error_code="JOIN_CODE_GENERATION_FAILED",
            error_message="Could not generate unique join code after 10 attempts",
        )

    # Generate or use provided correlation ID
    corr_id = correlation_id or idempotency_key or f"class_create_{uuid.uuid4().hex}"

    # =========================================================================
    # PHASE 2: Atomic Class Boundary Creation
    # =========================================================================

    # Get current timestamp via canonical temporal resolver (SLE)
    # SLE is required here: the class does not yet exist, so CLE cannot resolve
    # its timezone. Class-creation timestamps are system-level events.
    temporal_eval = canonical_temporal_resolver(
        SYSTEM_LEVEL_EVALUATION,
        primitive="current_time",
    )
    timestamp_utc = temporal_eval.canonical_now_utc

    # Create ClassEconomy (classes table)
    # Use savepoint + retry on IntegrityError (join_code collision between check and flush)
    class_id = str(uuid.uuid4())
    for _retry in range(max_attempts):
        savepoint = db.session.begin_nested()
        try:
            class_economy = ClassEconomy(
                class_id=class_id,
                class_public_id=str(uuid.uuid4()),
                join_code=join_code,
                teacher_user_id=canonical_context.user_id,
                display_name=class_name,
                class_timezone=normalized_timezone,
                created_at=timestamp_utc,
            )
            db.session.add(class_economy)
            db.session.flush()
            break  # Success — savepoint auto-commits on flush
        except IntegrityError:
            savepoint.rollback()
            # Regenerate join_code and class_id for retry
            join_code = ''.join(secrets.choice(_ALPHABET) for _ in range(6))
            class_id = str(uuid.uuid4())
    else:
        return CreateClassBoundaryResult(
            success=False,
            correlation_id=corr_id,
            error_code="JOIN_CODE_COLLISION",
            error_message="Could not create class after repeated join_code collisions",
        )

    # The root EconomicEngine (economy_policy_mode='default', previous_version_id=None)
    # and its default ClassFeature rows are seeded atomically by the ORM event listener
    # on ClassEconomy insert (see @event.listens_for(ClassEconomy, "after_insert") in
    # models.py). That listener is the single canonical creator of the root version;
    # FEAT-CLASS-001 owns orchestration only and MUST NOT create a competing root
    # (ECON-CONST-005: operational domains must not mutate policy lineage directly).
    #
    # We therefore read back the listener-seeded root rather than minting a second one.
    # `expected_weekly_hours` is not applied at root creation; it is set post-creation
    # via FEAT-CLASS-005 (economic engine evolution), the sole lawful writer for engine
    # evolution.
    initial_engine = get_initial_economic_engine(class_id)
    initial_engine_id = initial_engine.economic_version_id if initial_engine else None

    return CreateClassBoundaryResult(
        success=True,
        correlation_id=corr_id,
        class_id=class_id,
        join_code=join_code,
        teacher_user_id=canonical_context.user_id,
        initial_engine_id=initial_engine_id,
        error_code=None,
        error_message=None,
    )


# execute_set_class_timezone / SetClassTimezoneResult: DELETED — post-hoc,
# one-time timezone configuration existed only because class_timezone used to be
# optional. Every class is now born with a confirmed, immutable IANA timezone at
# creation (classes.class_timezone is NOT NULL), so there is no set-later path.
