"""
Canonical Class Context Resolver for the v2 architecture.

This service establishes a strict context object anchored only on
user_id, class_id, and seat_id. It raises exceptions on failure
and never infers or reconstructs context.
"""

from dataclasses import dataclass

from flask import session
from app.extensions import db
from app.models import Seat, User, UserRole


class ContextResolutionError(Exception):
    """Base class for all context resolution errors."""
    pass


class ContextNotEstablished(ContextResolutionError):
    """Raised when the requested context cannot be established (e.g. missing session keys)."""
    pass


class ContextForbidden(ContextResolutionError):
    """Raised when the actor is explicitly forbidden from holding class context (e.g. sysadmins)."""
    pass


class ContextMismatch(ContextResolutionError):
    """Raised when the requested context conflicts with the actor's authorized scope."""
    pass


class ContextInvariantViolation(ContextResolutionError):
    """Raised when canonical context is missing and no explicit exception applies."""
    pass


@dataclass(frozen=True)
class CanonicalContext:
    user_id: int
    class_id: str
    seat_id: int
    actor_role: str

    def __getattr__(self, name):
        forbidden_attrs = {"join_code", "teacher_id", "block", "section", "student_id"}
        if name in forbidden_attrs:
            raise AttributeError(f"Strict context invariant violation: cannot access {name}")
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


@dataclass(frozen=True)
class BoundaryContext:
    user_id: int
    actor_role: str  # "teacher" or "sysadmin"

    def __getattr__(self, name):
        if name in {"class_id", "seat_id"}:
            raise AttributeError(
                "BoundaryContext has no class scope — resolve class selection first"
            )
        forbidden = {"join_code", "teacher_id", "block", "section", "student_id"}
        if name in forbidden:
            raise AttributeError(f"Strict context invariant violation: cannot access {name}")
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


def resolve_canonical_context(require_class: bool = True) -> CanonicalContext | BoundaryContext:
    """
    Establish the canonical class context for the current actor.
    
    Args:
        require_class: If True, demands a full class context. If False, allows returning
            a BoundaryContext for actors (teachers/sysadmins) without an active class.
            
    Raises:
        ContextForbidden: If the actor is a system administrator and require_class=True.
        ContextNotEstablished: If no valid class_id or seat_id is found (when require_class=True).
        ContextMismatch: If the seat does not belong to the class, or the user does not own the seat.
    """
    user_id = session.get("user_id")
    if not user_id:
        raise ContextNotEstablished("Missing user_id in session.")

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise ContextNotEstablished("Invalid format for user_id.")

    user = db.session.get(User, user_id)
    if not user:
        raise ContextNotEstablished("User not found.")

    is_sysadmin = getattr(user.user_role, "value", user.user_role) == UserRole.SYSADMIN.value

    if is_sysadmin:
        if require_class:
            raise ContextForbidden("System administrators cannot possess Class Context.")
        return BoundaryContext(user_id=user_id, actor_role="sysadmin")

    class_id = getattr(user, "last_active_class_id", None)
    if not class_id:
        if not require_class and getattr(user.user_role, "value", user.user_role) == UserRole.TEACHER.value:
            return BoundaryContext(user_id=user_id, actor_role="teacher")
        print(f"DEBUG: Missing class_id! user_id={user_id}, last_active_class_id={getattr(user, 'last_active_class_id', 'NOT SET')}")
        raise ContextInvariantViolation("Missing canonical class_id in user context.")

    seat_id = getattr(user, "last_active_seat_id", None)
    seat = None
    if seat_id:
        try:
            seat_id = int(seat_id)
        except (ValueError, TypeError):
            print("DEBUG: Invalid canonical seat pointer.")
            raise ContextInvariantViolation("Invalid canonical seat pointer.")
        seat = db.session.get(Seat, seat_id)
        if not seat:
            print("DEBUG: Missing or deleted last_active_seat_id.")
            raise ContextInvariantViolation("Missing or deleted last_active_seat_id.")
        if seat.class_id != class_id:
            print(f"DEBUG: last_active_seat_id {seat_id} does not belong to last_active_class_id {class_id}.")
            raise ContextMismatch("last_active_seat_id does not belong to last_active_class_id.")
        if seat.user_id != user_id:
            print("DEBUG: last_active_seat_id does not belong to authenticated user.")
            raise ContextMismatch("last_active_seat_id does not belong to authenticated user.")
    else:
        seat = (
            db.session.query(Seat)
            .filter(Seat.user_id == user_id, Seat.class_id == class_id)
            .order_by(Seat.id.asc())
            .first()
        )
        if not seat:
            print(f"DEBUG: Seat not found for canonical class context. user_id={user_id}, class_id={class_id}")
            raise ContextNotEstablished("Seat not found for canonical class context.")

    if getattr(seat, "role", None) == "student" and getattr(seat, "claimed_at", None) is None:
        print("DEBUG: Student seat is not claimed.")
        raise ContextInvariantViolation("Student seat is not claimed.")

    return CanonicalContext(
        user_id=user_id,
        class_id=class_id,
        seat_id=seat.id,
        actor_role=seat.role,
    )
