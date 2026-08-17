"""
Tests for FEAT-CLASS-002: Modify Class Boundary

Covers:
- Authorization: non-teacher role rejected across all three operations
- Scope mismatch: class_id in context != provided class_id
- Idempotency: remove on already-missing seat returns success
- Claimed-seat force guard: remove blocked without force=True
- Happy paths: modify, provision, remove
"""

import pytest

from app.extensions import db
from app.models import Seat
from app.services.context_resolver import CanonicalContext
from app.feats.identity_feat import (
    execute_modify_student,
    execute_provision_student_seat,
    execute_remove_student_seat,
)
from tests.helpers.canonical_classroom import provision_classroom


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _teacher_context(classroom) -> CanonicalContext:
    """Build a teacher CanonicalContext from a ProvisionedClassroom."""
    return CanonicalContext(
        user_id=classroom.teacher_user_id,
        class_id=classroom.class_id,
        seat_id=classroom.teacher_seat_id,
        actor_role="teacher",
    )


def _student_context(classroom, student) -> CanonicalContext:
    """Build a student CanonicalContext for authorization tests."""
    return CanonicalContext(
        user_id=student.user_id,
        class_id=classroom.class_id,
        seat_id=student.seat_id,
        actor_role="student",
    )


# ---------------------------------------------------------------------------
# FEAT-CLASS-002: execute_modify_student
# ---------------------------------------------------------------------------


class TestModifyStudent:
    """Tests for execute_modify_student."""

    def test_happy_path_updates_student_name(self, app):
        """Happy path: teacher can update a student's name."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            student = classroom.students[0]
            ctx = _teacher_context(classroom)

            result = execute_modify_student(idempotency_key="modify-test", 
                canonical_context=ctx,
                class_id=classroom.class_id,
                seat_id=student.seat_id,
                first_name="Updated",
                last_name="Name",
            )

            assert result.success is True
            assert result.seat_id == student.seat_id

    def test_unauthorized_non_teacher_rejected(self, app):
        """Authorization: student actor_role is rejected."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            student = classroom.students[0]
            student_ctx = _student_context(classroom, student)

            result = execute_modify_student(idempotency_key="modify-test", 
                canonical_context=student_ctx,
                class_id=classroom.class_id,
                seat_id=student.seat_id,
                first_name="Hacker",
                last_name="Attempt",
            )

            assert result.success is False
            assert result.error_code == "UNAUTHORIZED"

    def test_scope_mismatch_rejected(self, app):
        """Scope: class_id in context differs from provided class_id."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            student = classroom.students[0]
            ctx = _teacher_context(classroom)

            result = execute_modify_student(idempotency_key="modify-test", 
                canonical_context=ctx,
                class_id="different-class-id",
                seat_id=student.seat_id,
                first_name="Name",
                last_name="Change",
            )

            assert result.success is False
            assert result.error_code == "CLASS_SCOPE_MISMATCH"

    def test_rejects_empty_first_name(self, app):
        """Validation: empty first_name is rejected."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            student = classroom.students[0]
            ctx = _teacher_context(classroom)

            result = execute_modify_student(idempotency_key="modify-test", 
                canonical_context=ctx,
                class_id=classroom.class_id,
                seat_id=student.seat_id,
                first_name="   ",
                last_name="Valid",
            )

            assert result.success is False
            assert result.error_code == "INVALID_NAME"


# ---------------------------------------------------------------------------
# FEAT-CLASS-002: execute_provision_student_seat
# ---------------------------------------------------------------------------


class TestProvisionStudentSeat:
    """Tests for execute_provision_student_seat."""

    def test_happy_path_creates_new_seat(self, app):
        """Happy path: teacher can provision a new student seat."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            ctx = _teacher_context(classroom)

            result = execute_provision_student_seat(idempotency_key="provision-test", 
                canonical_context=ctx,
                class_id=classroom.class_id,
                first_name="New",
                last_name="Student",
            )

            assert result.success is True
            assert result.seat_id is not None
            seat = db.session.get(Seat, result.seat_id)
            assert seat is not None
            assert seat.class_id == classroom.class_id
            assert seat.role == "student"

    def test_unauthorized_non_teacher_rejected(self, app):
        """Authorization: student actor_role is rejected."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            student = classroom.students[0]
            student_ctx = _student_context(classroom, student)

            result = execute_provision_student_seat(idempotency_key="provision-test", 
                canonical_context=student_ctx,
                class_id=classroom.class_id,
                first_name="Bad",
                last_name="Actor",
            )

            assert result.success is False
            assert result.error_code == "UNAUTHORIZED"

    def test_scope_mismatch_rejected(self, app):
        """Scope: class_id mismatch is rejected."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            ctx = _teacher_context(classroom)

            result = execute_provision_student_seat(idempotency_key="provision-test", 
                canonical_context=ctx,
                class_id="wrong-class-id",
                first_name="Name",
                last_name="Here",
            )

            assert result.success is False
            assert result.error_code == "CLASS_SCOPE_MISMATCH"


# ---------------------------------------------------------------------------
# FEAT-CLASS-002: execute_remove_student_seat
# ---------------------------------------------------------------------------


class TestRemoveStudentSeat:
    """Tests for execute_remove_student_seat."""

    def test_happy_path_removes_unclaimed_seat(self, app):
        """Happy path: teacher removes an unclaimed student seat."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            ctx = _teacher_context(classroom)

            # First provision a new unclaimed seat (no user_id set)
            provision_result = execute_provision_student_seat(idempotency_key="provision-test", 
                canonical_context=ctx,
                class_id=classroom.class_id,
                first_name="Temp",
                last_name="Student",
            )
            assert provision_result.success is True
            new_seat_id = provision_result.seat_id

            result = execute_remove_student_seat(idempotency_key="remove-test", 
                canonical_context=ctx,
                class_id=classroom.class_id,
                seat_id=new_seat_id,
            )

            assert result.success is True
            assert result.seat_id == new_seat_id

    def test_idempotency_missing_seat_returns_success(self, app):
        """Idempotency: removing an already-gone seat returns success."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            ctx = _teacher_context(classroom)

            result = execute_remove_student_seat(idempotency_key="remove-test", 
                canonical_context=ctx,
                class_id=classroom.class_id,
                seat_id=999999,
            )

            assert result.success is True

    def test_claimed_seat_blocked_without_force(self, app):
        """Force guard: claimed seat (user_id set) blocked without force=True."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            ctx = _teacher_context(classroom)
            # Roster students are claimed (have user_id bound)
            claimed_student = classroom.students[0]

            result = execute_remove_student_seat(idempotency_key="remove-test", 
                canonical_context=ctx,
                class_id=classroom.class_id,
                seat_id=claimed_student.seat_id,
                force=False,
            )

            assert result.success is False
            assert result.error_code == "SEAT_CLAIMED"

    def test_claimed_seat_removed_with_force(self, app):
        """Force: claimed seat is removed when force=True."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            ctx = _teacher_context(classroom)
            claimed_student = classroom.students[0]

            result = execute_remove_student_seat(idempotency_key="remove-test", 
                canonical_context=ctx,
                class_id=classroom.class_id,
                seat_id=claimed_student.seat_id,
                force=True,
            )

            assert result.success is True
            assert result.seat_id == claimed_student.seat_id

    def test_unauthorized_non_teacher_rejected(self, app):
        """Authorization: student actor_role is rejected."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            student = classroom.students[0]
            student_ctx = _student_context(classroom, student)

            result = execute_remove_student_seat(idempotency_key="remove-test", 
                canonical_context=student_ctx,
                class_id=classroom.class_id,
                seat_id=student.seat_id,
                force=True,
            )

            assert result.success is False
            assert result.error_code == "UNAUTHORIZED"

    def test_scope_mismatch_rejected(self, app):
        """Scope: class_id mismatch is rejected."""
        with app.app_context():
            classroom = provision_classroom("chemistry_p1")
            student = classroom.students[0]
            ctx = _teacher_context(classroom)

            result = execute_remove_student_seat(idempotency_key="remove-test", 
                canonical_context=ctx,
                class_id="wrong-class-id",
                seat_id=student.seat_id,
            )

            assert result.success is False
            assert result.error_code == "CLASS_SCOPE_MISMATCH"
