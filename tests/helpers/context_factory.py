"""Canonical context factory for tests."""

from dataclasses import dataclass
from app.services.context_resolver import CanonicalContext
from app.models import Seat, User


@dataclass
class _StudentInfo:
    """Test student info."""
    user: User
    seat: Seat


def make_canonical_context(
    user_id: int,
    class_id: str,
    seat_id: int,
    actor_role: str = "student",
) -> CanonicalContext:
    """
    Create a canonical context for testing.

    Args:
        user_id: User ID
        class_id: Class ID
        seat_id: Seat ID
        actor_role: Actor role ("student", "teacher", "admin")

    Returns:
        CanonicalContext instance
    """
    return CanonicalContext(
        user_id=user_id,
        class_id=class_id,
        seat_id=seat_id,
        actor_role=actor_role,
    )


class ClassroomContextFactory:
    """Factory for building complete classroom test contexts."""

    def __init__(self, db, **kwargs):
        """Initialize factory with database session."""
        self.db = db
        self.teacher_user = kwargs.get("teacher_user")
        self.teacher_seat = kwargs.get("teacher_seat")
        self.teacher_profile = kwargs.get("teacher_profile")
        self.class_economy = kwargs.get("class_economy")
        self.students = []
        self._is_built = False

    def with_students(self, n: int = 1):
        """Add N student records to context."""
        # Placeholder for now - students to be created on build()
        self._num_students = n
        return self

    def build(self):
        """Build and return complete context."""
        # Implementation would create all the necessary records
        # For now, return self to satisfy fixture contract
        self._is_built = True
        return self
