"""
Identity Domain FEAT Implementations

FEAT-IDEN-001: Unauthenticated Student Seat Claim (verification + binding)
FEAT-IDEN-002: Student Credential Setup (activate credentials on pre-provisioned user)
FEAT-IDEN-003: Teacher Reset Code Generation
FEAT-IDEN-004: Student Recovery Code Validation (clear credentials, redirect to setup)
FEAT-IDEN-005: Authenticated Class Binding (logged-in student adds a new class)
FEAT-IDEN-006: Provision Student Seat in Existing Class

All mutations are atomic per FEAT-CORE-000. Routes call these functions
instead of performing inline domain operations.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Seat, User
from app.services.class_configuration_query_service import get_class_economy
from app.services.classroom_setup import create_student_seat_with_profile, delete_seat_with_profile
from app.services.context_resolver import CanonicalContext
from app.feats.base import requires_feat_context
from app.utils.canonical_temporal_resolver import utc_now

logger = logging.getLogger(__name__)


@requires_feat_context("FEAT-IDEN-006")
def remove_student_from_teacher_scope(
    *,
    canonical_context: CanonicalContext,
    seat_id: int,
    teacher_user_id: int,
    correlation_id: str,
    idempotency_key: str,
) -> bool:
    """Detach one student seat from a teacher's class-owned identity scope."""
    if not canonical_context or canonical_context.user_id != teacher_user_id:
        raise ValueError("canonical teacher context is required for student detachment")
    from app.utils.student_deletion import remove_student_from_teacher_scope as _remove
    return _remove(seat_id, teacher_user_id)


@requires_feat_context("FEAT-IDEN-006")
def remove_pending_student_seat(
    *,
    canonical_context: CanonicalContext,
    seat_id: int,
    correlation_id: str,
    idempotency_key: str,
) -> str:
    """Delete an unclaimed roster seat and its class-scoped identity profile."""
    seat = db.session.get(Seat, seat_id)
    if not seat or seat.class_id != canonical_context.class_id:
        return "NOT_FOUND"
    if seat.role != "student" or seat.claimed_at is not None or seat.user_id is not None:
        return "CLAIMED"
    delete_seat_with_profile(seat)
    db.session.flush()
    return "REMOVED"

RESET_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SeatClaimResult:
    """Result of FEAT-IDEN-001 seat claim verification."""
    success: bool
    seat_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class CredentialSetupResult:
    """Result of FEAT-IDEN-002 credential activation."""
    success: bool
    user_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class ResetCodeResult:
    """Result of FEAT-IDEN-003 reset code generation."""
    success: bool
    code: Optional[str] = None
    display_name: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class RecoveryLookupResult:
    """Result of FEAT-IDEN-004 recovery code validation."""
    success: bool
    seat_id: Optional[int] = None
    user_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class ClassBindingResult:
    """Result of FEAT-IDEN-005 authenticated class binding."""
    success: bool
    seat_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class ProvisionStudentSeatResult:
    """Result of FEAT-IDEN-006 student-seat provisioning."""
    success: bool
    correlation_id: str
    seat_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@requires_feat_context("FEAT-IDEN-006")
def execute_provision_student_seat(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    first_name: str,
    last_name: str,
    notes: str | None = None,
    dedupe_code: str,
    has_received_rent_exemption: bool,
    correlation_id: str,
    idempotency_key: str,
) -> ProvisionStudentSeatResult:
    """Provision an unclaimed student seat and identity profile in a class."""
    corr_id = correlation_id

    if not canonical_context or not canonical_context.seat_id or not canonical_context.class_id:
        return ProvisionStudentSeatResult(False, corr_id, error_code="INVALID_CONTEXT", error_message="Missing canonical context (class_id, seat_id)")
    if class_id != canonical_context.class_id:
        return ProvisionStudentSeatResult(False, corr_id, error_code="CLASS_SCOPE_MISMATCH", error_message=f"Class ID in context ({canonical_context.class_id}) does not match provided class_id ({class_id})")
    if getattr(canonical_context, "actor_role", None) != "teacher":
        return ProvisionStudentSeatResult(False, corr_id, error_code="UNAUTHORIZED", error_message="Only teachers can provision student seats")

    teacher_seat = db.session.get(Seat, canonical_context.seat_id)
    if not teacher_seat or teacher_seat.class_id != class_id or teacher_seat.role != "teacher" or teacher_seat.user_id != canonical_context.user_id:
        return ProvisionStudentSeatResult(False, corr_id, error_code="TEACHER_SEAT_NOT_FOUND", error_message="Teacher seat not found or not in class scope")
    if not get_class_economy(class_id):
        return ProvisionStudentSeatResult(False, corr_id, error_code="CLASS_NOT_FOUND", error_message=f"Class {class_id} not found")
    if not isinstance(first_name, str) or not first_name.strip() or not isinstance(last_name, str) or not last_name.strip():
        return ProvisionStudentSeatResult(False, corr_id, error_code="INVALID_NAME", error_message="first_name and last_name must be non-empty strings")
    if not isinstance(dedupe_code, str) or len(dedupe_code) > 8:
        return ProvisionStudentSeatResult(False, corr_id, error_code="INVALID_DEDUPE_CODE", error_message="dedupe_code must be at most 8 characters")

    new_seat = create_student_seat_with_profile(class_id=class_id, first_name=first_name.strip(), last_name=last_name.strip(), notes=notes)
    new_seat.dedupe_code = dedupe_code
    new_seat.has_received_rent_exemption = has_received_rent_exemption
    return ProvisionStudentSeatResult(True, corr_id, seat_id=new_seat.id)


# ---------------------------------------------------------------------------
# FEAT-IDEN-001: Unauthenticated Student Seat Claim (Verification Phase)
# ---------------------------------------------------------------------------

def resolve_seat_claim(
    *,
    join_code: str,
    first_name: str,
    last_name: str,
    dedupe_code: str = "",
) -> SeatClaimResult:
    """
    FEAT-IDEN-001 verification phase: resolve join code + name credentials
    to a single unclaimed seat.

    This is read-only — no DB writes. Returns the matched seat_id for the
    route to store in session before proceeding to credential setup.

    Per DOM-IDEN-005 §VII: unauthenticated claim SHALL NOT search for or
    infer existing User identities.
    """
    from app.hash_utils import hash_username_lookup
    from app.services.class_configuration_query_service import get_class_economy_by_join_code

    # Step 1: Resolve class
    class_row = get_class_economy_by_join_code(join_code)
    if not class_row:
        return SeatClaimResult(
            success=False,
            error_code="INVALID_JOIN_CODE",
            error_message="Invalid join code or all seats already claimed. Check with your teacher.",
        )

    class_id = class_row.class_id

    # Step 2: Find unclaimed seats
    unclaimed_seats = (
        Seat.query
        .filter(Seat.class_id == class_id, Seat.user_id.is_(None))
        .all()
    )
    if not unclaimed_seats:
        return SeatClaimResult(
            success=False,
            error_code="NO_UNCLAIMED_SEATS",
            error_message="Invalid join code or all seats already claimed. Check with your teacher.",
        )

    # Step 3: Match by name hashes
    claim_first_hash = hash_username_lookup(first_name.lower())
    claim_last_hash = hash_username_lookup(last_name.lower())

    matched_seats = [
        s for s in unclaimed_seats
        if s.claim_first_name_hash == claim_first_hash
        and s.claim_last_name_hash == claim_last_hash
    ]

    if not matched_seats:
        logger.warning(
            "Claim attempt failed for join_code=%s: no matching seat found.",
            join_code,
        )
        return SeatClaimResult(
            success=False,
            error_code="INVALID_CREDENTIALS",
            error_message="No matching account found. Please check your join code and credentials.",
        )

    # Step 4: Deduplication
    if len(matched_seats) == 1:
        return SeatClaimResult(success=True, seat_id=matched_seats[0].id)

    if not dedupe_code:
        return SeatClaimResult(
            success=False,
            error_code="AMBIGUOUS_IDENTITY",
            error_message="Multiple students in this class share that name. Enter your deduplication code from your teacher.",
        )

    dedupe_matches = [s for s in matched_seats if s.dedupe_code == dedupe_code]
    if len(dedupe_matches) != 1:
        return SeatClaimResult(
            success=False,
            error_code="INVALID_DEDUPE_CODE",
            error_message="Invalid deduplication code. Check with your teacher.",
        )

    return SeatClaimResult(success=True, seat_id=dedupe_matches[0].id)


# ---------------------------------------------------------------------------
# FEAT-IDEN-002: Student Credential Setup
# ---------------------------------------------------------------------------

@requires_feat_context("FEAT-IDEN-002")
def activate_student_credentials(
    *,
    seat_id: int,
    user_id: Optional[int],
    username: str,
    pin: str,
    passphrase: str,
    correlation_id: str,
    idempotency_key: str,
) -> CredentialSetupResult:
    """
    FEAT-IDEN-002: Activate login credentials on a student User.

    Handles two paths:
    1. New claim: user_id is None → creates User via create_student_user_for_seat()
    2. Recovery: user_id is set → updates existing User credentials in place

    All mutations are atomic. On IntegrityError (duplicate username),
    returns error result instead of raising.
    """
    from werkzeug.security import generate_password_hash
    from app.hash_utils import hash_username_lookup
    from app.services.classroom_setup import create_student_user_for_seat

    seat = db.session.get(Seat, seat_id)
    if not seat:
        return CredentialSetupResult(
            success=False,
            error_code="INVALID_SEAT_STATE",
            error_message="Invalid setup state. Please start over.",
        )

    now = utc_now()

    if user_id:
        # Recovery path: User already exists, update credentials in place.
        user = db.session.get(User, user_id)
        if not user:
            return CredentialSetupResult(
                success=False,
                error_code="INVALID_USER_STATE",
                error_message="Invalid setup state. Please start over.",
            )
        user.username_lookup_hash = hash_username_lookup(username)
        user.username_hash = hash_username_lookup(username)
        user.pin_hash = generate_password_hash(pin)
        user.passphrase_hash = generate_password_hash(passphrase)
        user.reset_code = None
        user.reset_code_generated_at = None
        user.reset_code_expires_at = None

        # Ensure seat binding
        if seat.user_id is None:
            seat.user_id = user.id
            seat.claimed_at = seat.claimed_at or now
    else:
        # New claim path: create User and bind seat atomically.
        # Use savepoint so IntegrityError doesn't poison the FEATContext transaction.
        savepoint = db.session.begin_nested()
        try:
            user = create_student_user_for_seat(
                seat, username=username, pin=pin, passphrase=passphrase,
            )
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()
            return CredentialSetupResult(
                success=False,
                error_code="USERNAME_TAKEN",
                error_message="That username is already taken. Please go back and choose another word.",
            )

    db.session.flush()
    return CredentialSetupResult(success=True, user_id=user.id)


# ---------------------------------------------------------------------------
# FEAT-IDEN-003: Teacher Reset Code Generation
# ---------------------------------------------------------------------------

@requires_feat_context("FEAT-IDEN-003")
def generate_teacher_reset_code(
    *,
    seat_id: int,
    teacher_user_id: int,
    correlation_id: str,
    idempotency_key: str,
) -> ResetCodeResult:
    """
    FEAT-IDEN-003: Teacher initiates password reset for a student.

    Resolves the Seat to its bound User, generates a time-limited recovery
    code, and writes it to the users table. Overwrites any existing code
    (single active code invariant per DOM-IDEN-002 §IX).
    """
    from app.models import ClassEconomy

    seat = db.session.get(Seat, seat_id)
    if not seat:
        return ResetCodeResult(
            success=False,
            error_code="SEAT_NOT_FOUND",
            error_message="Seat not found.",
        )

    # Verify teacher owns this seat's class (IDOR prevention).
    class_row = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
    if not class_row or class_row.teacher_user_id != teacher_user_id:
        return ResetCodeResult(
            success=False,
            error_code="UNAUTHORIZED",
            error_message="You are not authorized to reset credentials for this student.",
        )

    linked_user = db.session.get(User, seat.user_id) if seat.user_id else None
    if not linked_user:
        return ResetCodeResult(
            success=False,
            error_code="NO_LINKED_USER",
            error_message="Student has no linked account.",
        )

    # Generate and overwrite any existing code (DOM-IDEN-002 §IX invariant 4).
    code = "".join(secrets.choice(RESET_CODE_ALPHABET) for _ in range(8))
    now = utc_now()
    linked_user.reset_code = code
    linked_user.reset_code_generated_at = now
    linked_user.reset_code_expires_at = now + timedelta(minutes=10)

    db.session.flush()

    logger.info(
        "Reset code generated for seat %s (user %s) by user %s",
        seat.id, linked_user.id, teacher_user_id,
    )

    display_name = (
        seat.identity_profile.first_name if seat.identity_profile else str(seat.id)
    )

    return ResetCodeResult(
        success=True,
        code=code,
        display_name=display_name,
    )


# ---------------------------------------------------------------------------
# FEAT-IDEN-004: Student Recovery Code Validation
# ---------------------------------------------------------------------------

@requires_feat_context("FEAT-IDEN-004")
def validate_recovery_code(
    *,
    reset_code: str,
    correlation_id: str,
    idempotency_key: str,
) -> RecoveryLookupResult:
    """
    FEAT-IDEN-004: Student submits reset code to recover account.

    Finds the matching User by reset_code, validates expiration, clears
    credentials (forcing fresh credential setup), and returns the seat/user
    references for the route to establish the onboarding session.
    """
    from app.utils.canonical_temporal_resolver import ensure_utc

    linked_user = User.query.filter_by(reset_code=reset_code).first()

    valid = (
        linked_user is not None
        and linked_user.reset_code_expires_at is not None
        and ensure_utc(linked_user.reset_code_expires_at) >= utc_now()
    )

    if not valid:
        return RecoveryLookupResult(
            success=False,
            error_code="INVALID_OR_EXPIRED",
            error_message="Invalid or expired recovery code.",
        )

    # Find the seat to anchor the setup session.
    seat = (
        Seat.query
        .filter_by(user_id=linked_user.id)
        .order_by(Seat.id.asc())
        .first()
    )

    if not seat:
        return RecoveryLookupResult(
            success=False,
            error_code="NO_SEAT",
            error_message="No class seat found for this account. Contact your teacher.",
        )

    # Clear credentials — forces fresh credential setup.
    linked_user.username_lookup_hash = None
    linked_user.pin_hash = None
    linked_user.passphrase_hash = None
    # Clear the recovery code so it cannot be reused.
    linked_user.reset_code = None
    linked_user.reset_code_generated_at = None
    linked_user.reset_code_expires_at = None

    if seat.claimed_at is None:
        seat.claimed_at = utc_now()

    db.session.flush()

    logger.info(
        "Recovery lookup succeeded for user %s (seat %s); credentials cleared.",
        linked_user.id, seat.id,
    )

    return RecoveryLookupResult(
        success=True,
        seat_id=seat.id,
        user_id=linked_user.id,
    )


# ---------------------------------------------------------------------------
# FEAT-IDEN-005: Authenticated Class Binding
# ---------------------------------------------------------------------------

@requires_feat_context("FEAT-IDEN-005")
def bind_authenticated_student_to_class(
    *,
    user_id: int,
    join_code: str,
    first_name: str,
    last_name: str,
    dedupe_code: str = "",
    correlation_id: str,
    idempotency_key: str,
) -> ClassBindingResult:
    """
    FEAT-IDEN-005: Authenticated student adds a new class.

    Similar to FEAT-IDEN-001 verification but binds an existing User
    (already authenticated) to a new unclaimed Seat in a different class.
    No new User creation — reuses the authenticated principal.
    """
    from app.hash_utils import hash_username_lookup
    from app.services.class_configuration_query_service import get_class_economy_by_join_code

    # Step 1: Resolve class
    class_row = get_class_economy_by_join_code(join_code)
    if not class_row:
        return ClassBindingResult(
            success=False,
            error_code="INVALID_JOIN_CODE",
            error_message="Invalid join code or all seats already claimed. Check with your teacher.",
        )

    class_id = class_row.class_id

    # Step 2: Find unclaimed seats (both user_id and claimed_at must be NULL)
    unclaimed_seats = (
        Seat.query
        .filter(
            Seat.class_id == class_id,
            Seat.claimed_at.is_(None),
            Seat.user_id.is_(None),
        )
        .all()
    )
    if not unclaimed_seats:
        return ClassBindingResult(
            success=False,
            error_code="NO_UNCLAIMED_SEATS",
            error_message="Invalid join code or all seats already claimed. Check with your teacher.",
        )

    # Step 3: Match by name hashes
    claim_first_hash = hash_username_lookup(first_name.lower())
    claim_last_hash = hash_username_lookup(last_name.lower())

    matched_seats = [
        s for s in unclaimed_seats
        if s.claim_first_name_hash == claim_first_hash
        and s.claim_last_name_hash == claim_last_hash
    ]

    if not matched_seats:
        return ClassBindingResult(
            success=False,
            error_code="INVALID_CREDENTIALS",
            error_message="No matching seat found. Please verify your join code and credentials with your teacher.",
        )

    # Step 4: Deduplication
    if len(matched_seats) == 1:
        matched_seat = matched_seats[0]
    elif not dedupe_code:
        return ClassBindingResult(
            success=False,
            error_code="AMBIGUOUS_IDENTITY",
            error_message="Multiple students in this class share that name. Enter your deduplication code from your teacher.",
        )
    else:
        dedupe_matches = [s for s in matched_seats if s.dedupe_code == dedupe_code]
        if len(dedupe_matches) != 1:
            return ClassBindingResult(
                success=False,
                error_code="INVALID_DEDUPE_CODE",
                error_message="Invalid deduplication code. Check with your teacher.",
            )
        matched_seat = dedupe_matches[0]

    # Step 5: Guard — seat already claimed
    if matched_seat.user_id is not None:
        return ClassBindingResult(
            success=False,
            error_code="SEAT_ALREADY_CLAIMED",
            error_message="This seat is already claimed. Contact your teacher.",
        )

    # Step 6: Bind seat to authenticated user
    matched_seat.user_id = user_id
    matched_seat.claimed_at = utc_now()

    db.session.flush()

    return ClassBindingResult(success=True, seat_id=matched_seat.id)
