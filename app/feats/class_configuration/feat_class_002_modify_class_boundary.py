"""
FEAT-CLASS-002: Modify Class Boundary (v1.0)

Orchestrates roster modifications within an existing class boundary per DOM-CLASS-001:
- Individual student modification (update IdentityProfile) — Spec § IV.1
- Manual student provisioning (create new Seat + IdentityProfile, no User) — Spec § IV.2
- Individual student removal (delete Seat + IdentityProfile) — Spec § IV.3
- Bulk roster modification — DEFERRED (Spec § IV.4 + § V require template
  parsing, structural boundary markers, and duplicate claim collision handling;
  will be implemented when route rewiring reaches upload_students)

Authority: DOM-CLASS-001, DOM-IDEN-007 (seat/profile delegation), INV-ARC-019
Delegates persistence to: app/services/classroom_setup.py (Identity domain service layer)
Deletion confirmation: enforced via force parameter; route layer owns confirmation UI (§ IV.3)

MED Blast Radius: Idempotency_key recommended but not required
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import uuid

from app.extensions import db
from app.feats.base import feat_shell
from app.models import ClassEconomy, Seat, IdentityProfile
from app.services.context_resolver import CanonicalContext
from app.services.classroom_setup import (
    create_student_seat_with_profile,
    update_or_create_roster_seat,
    delete_seat_with_profile,
)


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


@feat_shell("FEAT-CLASS-002")
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
    """Internal implementation wrapped in @feat_shell."""

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
    if not teacher_seat or teacher_seat.class_id != class_id:
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


@feat_shell("FEAT-CLASS-002")
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
    """Internal implementation wrapped in @feat_shell."""

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
    if not teacher_seat or teacher_seat.class_id != class_id:
        return ProvisionStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="TEACHER_SEAT_NOT_FOUND",
            error_message="Teacher seat not found or not in class scope",
        )

    # Validate class exists
    class_economy = ClassEconomy.query.filter_by(class_id=class_id).first()
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


@feat_shell("FEAT-CLASS-002")
def _execute_remove_student_seat_impl(
    *,
    canonical_context: CanonicalContext,
    class_id: str,
    seat_id: int,
    force: bool = False,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> RemoveStudentSeatResult:
    """Internal implementation wrapped in @feat_shell."""

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
    if not teacher_seat or teacher_seat.class_id != class_id:
        return RemoveStudentSeatResult(
            success=False,
            correlation_id=corr_id,
            error_code="TEACHER_SEAT_NOT_FOUND",
            error_message="Teacher seat not found or not in class scope",
        )

    # Validate target student seat exists in this class
    student_seat = db.session.get(Seat, seat_id)
    if not student_seat or student_seat.class_id != class_id:
        # Idempotency: seat already gone is success
        return RemoveStudentSeatResult(
            success=True,
            correlation_id=corr_id,
            seat_id=seat_id,
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
