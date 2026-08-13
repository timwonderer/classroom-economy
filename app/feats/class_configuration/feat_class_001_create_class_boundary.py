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
import pytz

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.feats.base import feat_shell
from app.models import ClassEconomy, EconomicEngine, User, Seat
from app.services.class_configuration_query_service import verify_teacher_owns_class
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
    timezone: str = "UTC",
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> CreateClassBoundaryResult:
    """
    Execute lawful teacher-directed class creation.

    Args:
        canonical_context: CanonicalContext with user_id, class_id (ignored), seat_id, actor_role="teacher"
        class_name: Display name for the class (e.g., "Period 3 Economics")
        timezone: IANA timezone for class-local time evaluation (default: "UTC")
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
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@feat_shell("FEAT-CLASS-001")
def _execute_create_class_boundary_impl(
    *,
    canonical_context: CanonicalContext,
    class_name: str,
    timezone: str = "UTC",
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> CreateClassBoundaryResult:
    """
    Internal implementation wrapped in @feat_shell for context management.
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

    # Validate timezone
    try:
        if timezone not in pytz.all_timezones_set:
            return CreateClassBoundaryResult(
                success=False,
                correlation_id="",
                error_code="INVALID_TIMEZONE",
                error_message=f"Timezone '{timezone}' is not a valid IANA timezone",
            )
    except Exception as e:
        return CreateClassBoundaryResult(
            success=False,
            correlation_id="",
            error_code="TIMEZONE_VALIDATION_ERROR",
            error_message=f"Error validating timezone: {str(e)}",
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
                class_timezone=timezone,
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

    # Create initial EconomicEngine version
    # Default to 'default' policy mode per DOM-CLASS-002
    initial_engine_id = str(uuid.uuid4())
    initial_engine = EconomicEngine(
        economic_version_id=initial_engine_id,
        class_id=class_id,
        economy_policy_mode='default',
        previous_version_id=None,  # Initial version has no predecessor
        created_at=timestamp_utc,
    )
    db.session.add(initial_engine)
    db.session.flush()

    # ClassFeature rows are seeded by ORM event listener on ClassEconomy creation
    # (see @event.listens_for(ClassEconomy, "after_insert") in models.py)
    # This ensures default feature set is created with proper effective_at timestamps

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


# =============================================================================
# FEAT-CLASS-001: Set Class Timezone (post-creation, one-time only)
# =============================================================================


@dataclass
class SetClassTimezoneResult:
    """Result of class timezone configuration."""
    success: bool
    correlation_id: str
    class_id: Optional[str] = None
    class_timezone: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


def execute_set_class_timezone(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    timezone: str,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> SetClassTimezoneResult:
    """
    Set the initial timezone for an existing class boundary.

    This is a one-time operation: once set, class_timezone is immutable.
    Permitted only if the class has never had its timezone confirmed.

    Args:
        canonical_context: CanonicalContext with actor_role="teacher"
        class_id: Class UUID to configure
        timezone: Valid IANA timezone string
        correlation_id: Optional audit trail identifier
        idempotency_key: Optional replay guard

    Authority: FEAT-CLASS-001 (Sole lawful writer for ClassEconomy)
    Error codes: INVALID_CONTEXT, NOT_TEACHER, CLASS_NOT_FOUND,
                 INVALID_TIMEZONE, TIMEZONE_ALREADY_SET
    """
    return _execute_set_class_timezone_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        timezone=timezone,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@feat_shell("FEAT-CLASS-001")
def _execute_set_class_timezone_impl(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    timezone: str,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> SetClassTimezoneResult:
    """Internal implementation: set initial class timezone."""

    corr_id = correlation_id or f"set_timezone_{class_id}"

    # =========================================================================
    # PHASE 1: Read-Only Validation
    # =========================================================================

    if not canonical_context or not canonical_context.seat_id:
        return SetClassTimezoneResult(
            success=False,
            correlation_id=corr_id,
            error_code="INVALID_CONTEXT",
            error_message="Missing canonical context (seat_id required)",
        )

    if getattr(canonical_context, "actor_role", None) != "teacher":
        return SetClassTimezoneResult(
            success=False,
            correlation_id=corr_id,
            error_code="NOT_TEACHER",
            error_message="Only teachers may configure class timezone",
        )

    # Validate IANA timezone
    try:
        if timezone not in pytz.all_timezones_set:
            return SetClassTimezoneResult(
                success=False,
                correlation_id=corr_id,
                error_code="INVALID_TIMEZONE",
                error_message=f"'{timezone}' is not a valid IANA timezone",
            )
    except Exception as e:
        return SetClassTimezoneResult(
            success=False,
            correlation_id=corr_id,
            error_code="INVALID_TIMEZONE",
            error_message=f"Error validating timezone: {str(e)}",
        )

    # Load class, verify teacher ownership
    class_row = verify_teacher_owns_class(class_id, canonical_context.user_id)
    if class_row is None:
        return SetClassTimezoneResult(
            success=False,
            correlation_id=corr_id,
            error_code="CLASS_NOT_FOUND",
            error_message="Class not found or teacher does not own this class",
        )

    # Check idempotency: already set to the same timezone
    if class_row.class_timezone and class_row.class_timezone == (
        'Etc/UTC' if timezone == 'UTC' else timezone
    ):
        return SetClassTimezoneResult(
            success=True,
            correlation_id=corr_id,
            class_id=class_id,
            class_timezone=class_row.class_timezone,
            error_code=None,
            error_message=None,
        )

    # Reject if timezone is already locked (was previously confirmed)
    # A non-placeholder timezone means it's been set and is immutable
    _placeholder_timezones = {'UTC', None, ''}
    current_tz = class_row.class_timezone
    if current_tz not in _placeholder_timezones:
        return SetClassTimezoneResult(
            success=False,
            correlation_id=corr_id,
            error_code="TIMEZONE_ALREADY_SET",
            error_message=f"Class timezone is already set to '{current_tz}' and cannot be changed",
        )

    # =========================================================================
    # PHASE 2: Mutation
    # =========================================================================

    class_row.class_timezone = 'Etc/UTC' if timezone == 'UTC' else timezone

    return SetClassTimezoneResult(
        success=True,
        correlation_id=corr_id,
        class_id=class_id,
        class_timezone=class_row.class_timezone,
    )
