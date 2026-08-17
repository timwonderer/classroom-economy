"""
Identity Domain FEAT Implementations

FEAT-IDEN-001: Unauthenticated Student Seat Claim (verification + binding)
FEAT-IDEN-002: Student Credential Setup (activate credentials on pre-provisioned user)
FEAT-IDEN-003: Teacher Reset Code Generation
FEAT-IDEN-004: Student Recovery Code Validation (clear credentials, redirect to setup)
FEAT-IDEN-005: Authenticated Class Binding (logged-in student adds a new class)

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
from app.feats.base import requires_feat_context
from app.models import Seat, User, ClassEconomy, IdentityProfile
from app.utils.canonical_temporal_resolver import utc_now
from app.utils.student_deletion import remove_student_from_teacher_scope
from app.services.classroom_setup import delete_seat_with_profile, create_student_seat_with_profile, update_or_create_roster_seat
from app.services.context_resolver import CanonicalContext
from app.services.class_configuration_query_service import get_class_economy
import uuid
from app.utils.canonical_temporal_resolver import utc_now
from app.utils.student_deletion import remove_student_from_teacher_scope
from app.services.classroom_setup import delete_seat_with_profile

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# FEAT-IDEN-001: Unauthenticated Student Seat Claim (Verification Phase)
# ---------------------------------------------------------------------------

@requires_feat_context("FEAT-IDEN-001")
def resolve_seat_claim(
    *,
    join_code: str,
    first_name: str,
    last_name: str,
    dedupe_code: str = "",
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
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
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
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
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
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
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
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
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
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


@dataclass
class DeleteStudentResult:
    """Result of a student deletion operation."""
    seat_id: int
    was_hard_deleted: bool

@dataclass
class DeletePendingStudentResult:
    """Result of a pending student deletion operation."""
    seat_id: int
    student_name: str

@requires_feat_context("FEAT-ADMN-001")
def execute_delete_student(seat_id: int, user_id: int, correlation_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> DeleteStudentResult:
    """
    Remove a student from a teacher's roster.
    
    If the student is shared with other teachers, only the current teacher
    association is removed. The student record is hard-deleted only when it no
    longer has any canonical class-seat links.
    """
    was_hard_deleted = remove_student_from_teacher_scope(seat_id, user_id)
    return DeleteStudentResult(
        seat_id=seat_id,
        was_hard_deleted=was_hard_deleted
    )

@requires_feat_context("FEAT-ADMN-001")
def execute_bulk_delete_students(seat_ids: List[int], user_id: int, correlation_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> Dict[int, bool]:
    """
    Remove multiple students from a teacher's roster.
    Returns a dictionary mapping seat_id to was_hard_deleted boolean.
    """
    from app.models import Seat
    results = {}
    for seat_id in seat_ids:
        student = db.session.get(Seat, seat_id)
        if student and student.role != "teacher":
            was_hard_deleted = remove_student_from_teacher_scope(seat_id, user_id)
            results[seat_id] = was_hard_deleted
    return results

@requires_feat_context("FEAT-ADMN-001")
def execute_delete_pending_student(seat_id: int, user_id: int, correlation_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> DeletePendingStudentResult:
    """
    Delete a single pending student (unclaimed Seat entry).
    """
    seat_entry = (
        Seat.query
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            Seat.id == seat_id,
            ClassEconomy.teacher_user_id == user_id,
        )
        .first()
    )
    if not seat_entry:
        raise ValueError("Pending student not found or access denied.")

    if seat_entry.claimed_at is not None or seat_entry.student_id is not None:
        raise ValueError("This seat has already been claimed. Use the regular student deletion route instead.")

    student_name = seat_entry.identity_profile.full_name if seat_entry.identity_profile else 'Unknown'
    delete_seat_with_profile(seat_entry)
    
    return DeletePendingStudentResult(seat_id=seat_id, student_name=student_name)

@requires_feat_context("FEAT-ADMN-001")
def execute_bulk_delete_pending_students(seat_ids: List[int], user_id: int, correlation_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> List[DeletePendingStudentResult]:
    """
    Delete multiple pending students.
    """
    results = []
    for seat_id in seat_ids:
        try:
            res = execute_delete_pending_student(seat_id, user_id, correlation_id=correlation_id, idempotency_key=f"bulk_del_pend_{seat_id}")
            results.append(res)
        except ValueError:
            pass # Skip invalid/unauthorized
    return results

@requires_feat_context("FEAT-ADMN-001")
def execute_bulk_delete_pending_students_by_class(class_ids: List[int], correlation_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> int:
    """
    Delete all pending students (unclaimed Seat entries) in the specified classes.
    """
    deleted_count = Seat.query.filter(
        Seat.class_id.in_(class_ids),
        Seat.claimed_at.is_(None),
        Seat.student_id.is_(None)
    ).delete(synchronize_session=False)
    
    return deleted_count

@dataclass
class AddManualStudentResult:
    success: bool
    is_duplicate_linked: bool = False
    is_already_in_class: bool = False
    class_id: Optional[int] = None
    seat_id: Optional[int] = None
    error_message: Optional[str] = None

@requires_feat_context("FEAT-IDEN-002")
def execute_add_manual_student(
    first_name: str,
    last_name: str,
    dob_sum: int,
    section: str,
    rent_enabled: bool,
    canonical_context,
    correlation_id: Optional[str] = None,
    idempotency_key: Optional[str] = None
) -> AddManualStudentResult:
    """
    Manually provision a student seat (advanced mode).
    This handles deduplication, credential matching, and linking existing students.
    """
    from app.models import Seat, IdentityProfile, get_class_economy
    from app.services.classroom_setup import create_pending_student_seat
    from app.utils.claim_credentials import compute_primary_claim_hash, match_claim_hash
    from app.routes.admin import _resolve_student_add_class_context, _build_teacher_block_dedupe_key
    from app.feats.class_configuration import execute_provision_student_seat
    from app.utils.auth_username import get_random_salt

    class_context = _resolve_student_add_class_context(
        canonical_context,
        block_select=section,
        section=section,
    )
    if not class_context:
        return AddManualStudentResult(success=False, error_message="Select a class before making changes.")

    class_id = class_context['class_id']
    dedupe_key = _build_teacher_block_dedupe_key(class_id, first_name, last_name)
    first_initial = first_name[0].upper()
    last_initial = last_name[0].upper()

    existing_seat_in_class = Seat.query.filter_by(
        class_id=class_id,
        dedupe_code=dedupe_key,
    ).first()
    if existing_seat_in_class:
        return AddManualStudentResult(success=True, is_already_in_class=True, class_id=class_id, seat_id=existing_seat_in_class.id)

    # Check for duplicates globally
    potential_duplicates = (
        Seat.query
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .filter(IdentityProfile.first_name == first_name)
        .all()
    )

    for existing_student in potential_duplicates:
        credential_matches, is_primary, canonical_hash = match_claim_hash(
            existing_student.first_half_hash if existing_student.identity_profile else None,
            first_initial,
            last_initial,
            dob_sum,
            existing_student.salt,
        )

        if credential_matches:
            if canonical_hash and not is_primary:
                existing_student.first_half_hash = canonical_hash
            existing_class_seat = Seat.query.filter_by(
                user_id=existing_student.user_id,
                class_id=class_id,
            ).first()
            if existing_class_seat and existing_class_seat.claimed_at:
                return AddManualStudentResult(success=True, is_already_in_class=True, class_id=class_id, seat_id=existing_class_seat.id)
            else:
                provision_result = execute_provision_student_seat(
                    canonical_context=canonical_context,
                    class_id=class_id,
                    first_name=first_name,
                    last_name=last_name,
                    idempotency_key=f"feat:admin:provision_dup:{class_id}:{first_name}:{last_name}"
                )
                if not provision_result.success:
                    return AddManualStudentResult(success=False, error_message=f"Provision failed linking duplicate: {provision_result.error_message}")
                
                return AddManualStudentResult(success=True, is_duplicate_linked=True, class_id=class_id, seat_id=provision_result.seat_id)

    # Seat only — no User until student completes claim (DOM-IDEN-002 §VIII).
    profile = IdentityProfile(
        profile_type='student',
        first_name=first_name,
        last_name=last_name,
    )

    if not get_class_economy(class_id):
        return AddManualStudentResult(success=False, error_message=f"Class {class_id} does not exist")

    new_seat = create_pending_student_seat(
        class_id=class_id,
        dedupe_code=dedupe_key,
        has_received_rent_exemption=not rent_enabled,
    )

    profile.seat_id = new_seat.id

    if class_context.get('class_created'):
        from app.routes.admin import _queue_pending_class_timezone_confirmation
        _queue_pending_class_timezone_confirmation(class_context.get('class_row'))

    return AddManualStudentResult(success=True, class_id=class_id, seat_id=new_seat.id)



# =============================================================================
# Result Types
# =============================================================================


@dataclass
class ModifyStudentResult:
    """Result of individual student profile modification."""
    success: bool
    correlation_id: str
    seat_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ProvisionStudentSeatResult:
    """Result of manual student seat provisioning."""
    success: bool
    correlation_id: str
    seat_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class RemoveStudentSeatResult:
    """Result of individual student seat removal."""
    success: bool
    correlation_id: str
    seat_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


# =============================================================================
# FEAT-CLASS-002: Modify Student Profile
# =============================================================================


def execute_modify_student(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    seat_id: int,
    first_name: str,
    last_name: str,
    notes: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> ModifyStudentResult:
    """
    Update IdentityProfile for an existing student seat.

    Args:
        canonical_context: CanonicalContext with actor_role="teacher"
        class_id: Class scope for the modification
        seat_id: Seat ID of the student to modify
        first_name: New first name
        last_name: New last name
        notes: Optional notes (replaces existing)
        correlation_id: Optional audit trail identifier
        idempotency_key: Optional replay guard

    Returns:
        ModifyStudentResult with success status
    """
    return _execute_modify_student_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        seat_id=seat_id,
        first_name=first_name,
        last_name=last_name,
        notes=notes,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@requires_feat_context("FEAT-IDEN-002")
def _execute_modify_student_impl(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    seat_id: int,
    first_name: str,
    last_name: str,
    notes: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> ModifyStudentResult:
    """Internal implementation wrapped in @requires_feat_context."""

    corr_id = correlation_id or idempotency_key or f"modify_student_{uuid.uuid4().hex}"

    # =========================================================================
    # PHASE 1: Read-Only Validation
    # =========================================================================

    if not canonical_context or not canonical_context.seat_id or not canonical_context.class_id:
        return ModifyStudentResult(
            success=False,
            correlation_id=corr_id,
            error_code="INVALID_CONTEXT",
            error_message="Missing canonical context (class_id, seat_id)",
        )

    if class_id != canonical_context.class_id:
        return ModifyStudentResult(
            success=False,
            correlation_id=corr_id,
            error_code="CLASS_SCOPE_MISMATCH",
            error_message=f"Class ID in context ({canonical_context.class_id}) does not match provided class_id ({class_id})",
        )

    if getattr(canonical_context, "actor_role", None) != "teacher":
        return ModifyStudentResult(
            success=False,
            correlation_id=corr_id,
            error_code="UNAUTHORIZED",
            error_message="Only teachers can modify student profiles",
        )

    # Validate teacher seat exists and belongs to class
    teacher_seat = db.session.get(Seat, canonical_context.seat_id)
    if not teacher_seat or teacher_seat.class_id != class_id or teacher_seat.role != "teacher" or teacher_seat.user_id != canonical_context.user_id:
        return ModifyStudentResult(
            success=False,
            correlation_id=corr_id,
            error_code="TEACHER_SEAT_NOT_FOUND",
            error_message="Teacher seat not found or not in class scope",
        )

    # Validate target student seat exists in this class
    student_seat = db.session.get(Seat, seat_id)
    if not student_seat or student_seat.class_id != class_id:
        return ModifyStudentResult(
            success=False,
            correlation_id=corr_id,
            error_code="SEAT_NOT_FOUND",
            error_message=f"Student seat {seat_id} not found in class {class_id}",
        )

    if student_seat.role != "student":
        return ModifyStudentResult(
            success=False,
            correlation_id=corr_id,
            error_code="NOT_STUDENT_SEAT",
            error_message=f"Seat {seat_id} is not a student seat",
        )

    # Validate name fields
    if not first_name or not isinstance(first_name, str) or len(first_name.strip()) == 0:
        return ModifyStudentResult(
            success=False,
            correlation_id=corr_id,
            error_code="INVALID_NAME",
            error_message="first_name must be a non-empty string",
        )

    if not last_name or not isinstance(last_name, str) or len(last_name.strip()) == 0:
        return ModifyStudentResult(
            success=False,
            correlation_id=corr_id,
            error_code="INVALID_NAME",
            error_message="last_name must be a non-empty string",
        )

    # =========================================================================
    # PHASE 2: Atomic Mutation
    # =========================================================================

    update_or_create_roster_seat(
        class_id=class_id,
        first_name=first_name,
        last_name=last_name,
        notes=notes,
        existing_seat=student_seat,
    )

    return ModifyStudentResult(
        success=True,
        correlation_id=corr_id,
        seat_id=seat_id,
    )


# =============================================================================
# FEAT-CLASS-002: Provision Student Seat
# =============================================================================


def execute_provision_student_seat(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    first_name: str,
    last_name: str,
    notes: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> ProvisionStudentSeatResult:
    """
    Create a new student Seat + IdentityProfile (no User created).

    Args:
        canonical_context: CanonicalContext with actor_role="teacher"
        class_id: Class to provision the seat in
        first_name: Student first name
        last_name: Student last name
        notes: Optional notes
        correlation_id: Optional audit trail identifier
        idempotency_key: Optional replay guard

    Returns:
        ProvisionStudentSeatResult with new seat_id
    """
    return _execute_provision_student_seat_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        first_name=first_name,
        last_name=last_name,
        notes=notes,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@requires_feat_context("FEAT-IDEN-002")
def _execute_provision_student_seat_impl(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    first_name: str,
    last_name: str,
    notes: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> ProvisionStudentSeatResult:
    """Internal implementation wrapped in @requires_feat_context."""

    corr_id = correlation_id or idempotency_key or f"provision_seat_{uuid.uuid4().hex}"

    # =========================================================================
    # PHASE 1: Read-Only Validation
    # =========================================================================

    if not canonical_context or not canonical_context.seat_id or not canonical_context.class_id:
        return ProvisionStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="INVALID_CONTEXT",
            error_message="Missing canonical context (class_id, seat_id)",
        )

    if class_id != canonical_context.class_id:
        return ProvisionStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="CLASS_SCOPE_MISMATCH",
            error_message=f"Class ID in context ({canonical_context.class_id}) does not match provided class_id ({class_id})",
        )

    if getattr(canonical_context, "actor_role", None) != "teacher":
        return ProvisionStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="UNAUTHORIZED",
            error_message="Only teachers can provision student seats",
        )

    # Validate teacher seat exists and belongs to class
    teacher_seat = db.session.get(Seat, canonical_context.seat_id)
    if not teacher_seat or teacher_seat.class_id != class_id or teacher_seat.role != "teacher" or teacher_seat.user_id != canonical_context.user_id:
        return ProvisionStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="TEACHER_SEAT_NOT_FOUND",
            error_message="Teacher seat not found or not in class scope",
        )

    # Validate class exists
    class_economy = get_class_economy(class_id)
    if not class_economy:
        return ProvisionStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="CLASS_NOT_FOUND",
            error_message=f"Class {class_id} not found",
        )

    # Validate name fields
    if not first_name or not isinstance(first_name, str) or len(first_name.strip()) == 0:
        return ProvisionStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="INVALID_NAME",
            error_message="first_name must be a non-empty string",
        )

    if not last_name or not isinstance(last_name, str) or len(last_name.strip()) == 0:
        return ProvisionStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="INVALID_NAME",
            error_message="last_name must be a non-empty string",
        )

    # =========================================================================
    # PHASE 2: Atomic Mutation
    # =========================================================================

    new_seat = create_student_seat_with_profile(
        class_id=class_id,
        first_name=first_name,
        last_name=last_name,
        notes=notes,
    )

    return ProvisionStudentSeatResult(
        success=True,
        correlation_id=corr_id,
        seat_id=new_seat.id,
    )


# =============================================================================
# FEAT-CLASS-002: Remove Student Seat
# =============================================================================


def execute_remove_student_seat(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    seat_id: int,
    force: bool = False,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> RemoveStudentSeatResult:
    """
    Remove a student seat and its identity profile.

    Args:
        canonical_context: CanonicalContext with actor_role="teacher"
        class_id: Class scope for the removal
        seat_id: Seat ID of the student to remove
        force: Must be True to remove a claimed seat (one with user_id set)
        correlation_id: Optional audit trail identifier
        idempotency_key: Optional replay guard

    Returns:
        RemoveStudentSeatResult with success status
    """
    return _execute_remove_student_seat_impl(
        canonical_context=canonical_context,
        class_id=class_id,
        seat_id=seat_id,
        force=force,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
    )


@requires_feat_context("FEAT-IDEN-002")
def _execute_remove_student_seat_impl(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    seat_id: int,
    force: bool = False,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> RemoveStudentSeatResult:
    """Internal implementation wrapped in @requires_feat_context."""

    corr_id = correlation_id or idempotency_key or f"remove_seat_{uuid.uuid4().hex}"

    # =========================================================================
    # PHASE 1: Read-Only Validation
    # =========================================================================

    if not canonical_context or not canonical_context.seat_id or not canonical_context.class_id:
        return RemoveStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="INVALID_CONTEXT",
            error_message="Missing canonical context (class_id, seat_id)",
        )

    if class_id != canonical_context.class_id:
        return RemoveStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="CLASS_SCOPE_MISMATCH",
            error_message=f"Class ID in context ({canonical_context.class_id}) does not match provided class_id ({class_id})",
        )

    if getattr(canonical_context, "actor_role", None) != "teacher":
        return RemoveStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="UNAUTHORIZED",
            error_message="Only teachers can remove student seats",
        )

    # Validate teacher seat exists and belongs to class
    teacher_seat = db.session.get(Seat, canonical_context.seat_id)
    if not teacher_seat or teacher_seat.class_id != class_id or teacher_seat.role != "teacher" or teacher_seat.user_id != canonical_context.user_id:
        return RemoveStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="TEACHER_SEAT_NOT_FOUND",
            error_message="Teacher seat not found or not in class scope",
        )

    # Validate target student seat exists in this class
    student_seat = db.session.get(Seat, seat_id)
    if not student_seat:
        # Idempotency: seat already gone is success
        return RemoveStudentSeatResult(
            success=True,
            correlation_id=corr_id,
            seat_id=seat_id,
        )

    if student_seat.class_id != class_id:
        return RemoveStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="SEAT_NOT_FOUND",
            error_message=f"Student seat {seat_id} not found in class {class_id}",
        )

    if student_seat.role != "student":
        return RemoveStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="NOT_STUDENT_SEAT",
            error_message=f"Seat {seat_id} is not a student seat",
        )

    # Claimed seat guard: require force=True for seats with a bound user
    if student_seat.user_id is not None and not force:
        return RemoveStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="SEAT_CLAIMED",
            error_message=f"Seat {seat_id} is claimed by a user. Set force=True to remove a claimed seat.",
        )

    # =========================================================================
    # PHASE 2: Atomic Mutation
    # =========================================================================

    delete_seat_with_profile(student_seat)
    db.session.flush()

    return RemoveStudentSeatResult(
        success=True,
        correlation_id=corr_id,
        seat_id=seat_id,
    )
