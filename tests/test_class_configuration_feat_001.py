"""
Tests for FEAT-CLASS-001: Create Class Boundary — extended operations

Covers: execute_set_class_timezone (post-creation timezone configuration)

Authority: DOM-CLASS-001, FEAT-CLASS-001
Test Spec: SPEC-TEST-001 (canonical test initializer patterns)
"""

import pytest

from app.models import ClassEconomy
from app.feats.class_configuration import (
    execute_set_class_timezone,
    SetClassTimezoneResult,
)
from app.services.context_resolver import CanonicalContext
from tests.helpers.classroom_initializer import initialize


class TestFEATCLASS001SetTimezone:
    """Test FEAT-CLASS-001: execute_set_class_timezone

    Uses initialize() — no session needed, testing FEAT directly.
    Per SPEC-TEST-001 the classroom is provisioned with a default UTC timezone.
    """

    def test_set_timezone_success(self, app):
        """Setting an initial timezone on a new class succeeds."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            result = execute_set_class_timezone(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                timezone="America/Los_Angeles",
                correlation_id="test-set-timezone",
                idempotency_key="test-set-timezone",
            )

            assert result.success is True
            assert result.class_id == classroom.class_id
            assert result.class_timezone == "America/Los_Angeles"

            # Verify persisted to ClassEconomy
            row = ClassEconomy.query.filter_by(class_id=classroom.class_id).first()
            assert row.class_timezone == "America/Los_Angeles"

    def test_set_timezone_invalid_timezone(self, app):
        """Invalid IANA timezone is rejected before any DB write."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            result = execute_set_class_timezone(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                timezone="Not/A/Real/Timezone",
                idempotency_key="test-invalid-timezone",
            )

            assert result.success is False
            assert result.error_code == "INVALID_TIMEZONE"

    def test_set_timezone_idempotent_same_value(self, app):
        """Setting the same timezone twice is idempotent — returns success both times."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            result1 = execute_set_class_timezone(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                timezone="America/New_York",
                idempotency_key="test-set-timezone-idempotent-1",
            )
            assert result1.success is True

            # Second call with same value — idempotent
            result2 = execute_set_class_timezone(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                timezone="America/New_York",
                idempotency_key="test-set-timezone-idempotent-2",
            )
            assert result2.success is True
            assert result2.class_timezone == "America/New_York"

    def test_set_timezone_locked_after_set(self, app):
        """Once set to a non-UTC timezone, the timezone cannot be changed."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            # Set initial timezone
            result1 = execute_set_class_timezone(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                timezone="America/Chicago",
                idempotency_key="test-timezone-lock-1",
            )
            assert result1.success is True

            # Attempt to change to a different timezone
            result2 = execute_set_class_timezone(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                timezone="America/Denver",
                idempotency_key="test-timezone-lock-2",
            )

            assert result2.success is False
            assert result2.error_code == "TIMEZONE_ALREADY_SET"

    def test_set_timezone_locked_after_setting_utc(self, app):
        """Setting UTC explicitly locks the timezone against later changes."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            result1 = execute_set_class_timezone(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                timezone="UTC",
                idempotency_key="test-timezone-utc-lock-1",
            )
            assert result1.success is True
            assert result1.class_timezone == "Etc/UTC"

            result2 = execute_set_class_timezone(
                canonical_context=canonical_context,
                class_id=classroom.class_id,
                timezone="America/Denver",
                idempotency_key="test-timezone-utc-lock-2",
            )

            assert result2.success is False
            assert result2.error_code == "TIMEZONE_ALREADY_SET"

    def test_set_timezone_not_teacher(self, app):
        """Non-teacher actor is rejected."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            student = classroom.students[0]
            student_context = CanonicalContext(
                user_id=student.user.id,
                class_id=classroom.class_id,
                seat_id=student.seat.id,
                actor_role="student",
            )

            result = execute_set_class_timezone(
                canonical_context=student_context,
                class_id=classroom.class_id,
                timezone="America/Los_Angeles",
                idempotency_key="test-timezone-not-teacher",
            )

            assert result.success is False
            assert result.error_code == "NOT_TEACHER"

    def test_set_timezone_rejects_other_teachers_class(self, app):
        """Teacher cannot configure timezone for another teacher's class."""
        classroom = initialize("chemistry_p1", app)
        other_classroom = initialize("biology_block_a", app)
        with app.app_context():
            assert other_classroom.teacher_user.id != classroom.teacher_user.id

            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            result = execute_set_class_timezone(
                canonical_context=canonical_context,
                class_id=other_classroom.class_id,
                timezone="America/Los_Angeles",
                idempotency_key="test-timezone-other-class",
            )

            assert result.success is False
            assert result.error_code == "CLASS_NOT_FOUND"

    def test_set_timezone_wrong_class(self, app):
        """Teacher cannot set timezone on a class they don't own."""
        classroom = initialize("chemistry_p1", app)
        with app.app_context():
            canonical_context = CanonicalContext(
                user_id=classroom.teacher_user.id,
                class_id=classroom.class_id,
                seat_id=classroom.teacher_seat.id,
                actor_role="teacher",
            )

            result = execute_set_class_timezone(
                canonical_context=canonical_context,
                class_id="00000000-0000-0000-0000-000000000000",  # Non-existent class
                timezone="America/Los_Angeles",
                idempotency_key="test-timezone-missing-class",
            )

            assert result.success is False
            assert result.error_code == "CLASS_NOT_FOUND"
