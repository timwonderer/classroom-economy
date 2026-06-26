"""
Canonical Class Context Resolver for the v2 architecture.

This service establishes a strict context object anchored only on
user_id, class_id, and seat_id. It raises exceptions on failure
and never infers or reconstructs context.
"""

from dataclasses import dataclass
from typing import Optional

from flask import has_request_context, request, session
from app.extensions import db
from app.models import Seat, ClassEconomy, User, UserRole


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


def resolve_canonical_context() -> CanonicalContext:
    """
    Establish the canonical class context for the current actor.
    
    Raises:
        ContextForbidden: If the actor is a system administrator.
        ContextNotEstablished: If no valid class_id or seat_id is found.
        ContextMismatch: If the seat does not belong to the class, or the user does not own the seat.
    """
    if session.get("is_system_admin"):
        raise ContextForbidden("System administrators cannot possess Class Context.")

    user_id = session.get("user_id")
    session_nonce = session.get("current_session_nonce")

    if not user_id:
        raise ContextNotEstablished("Missing user_id in session.")

    if not session_nonce:
        raise ContextNotEstablished("Missing session nonce.")

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise ContextNotEstablished("Invalid format for user_id.")

    user = db.session.get(User, user_id)
    if not user:
        raise ContextNotEstablished("User not found.")
    if user.current_session_nonce != session_nonce:
        raise ContextMismatch("Session nonce does not match canonical user session.")

    class_id = getattr(user, "last_active_class_id", None)
    if not class_id:
        if _allow_teacher_context_exception(user_id):
            return None
        raise ContextInvariantViolation("Missing canonical class_id in user context.")

    seat = (
        db.session.query(Seat)
        .filter(Seat.user_id == user_id, Seat.class_id == class_id)
        .order_by(Seat.id.asc())
        .first()
    )
    if not seat:
        raise ContextNotEstablished("Seat not found.")
    if getattr(seat, "role", None) == "student" and getattr(seat, "claimed_at", None) is None:
        raise ContextNotEstablished("Seat is not claimed.")

    return CanonicalContext(
        user_id=user_id,
        class_id=class_id,
        seat_id=seat.id,
        actor_role=seat.role,
    )


def _allow_teacher_context_exception(user_id: object) -> bool:
    """Allow the teacher-only pre-class or create-class pages to resolve with user_id only."""
    if not has_request_context():
        return False

    try:
        normalized_user_id = int(user_id)
    except (TypeError, ValueError):
        return False

    user = db.session.get(User, normalized_user_id)
    if not user or getattr(user.user_role, "value", user.user_role) != UserRole.TEACHER.value:
        return False

    endpoint = request.endpoint or ""
    path = request.path or ""
    if endpoint == "admin.onboarding":
        return True
    if path == "/admin/onboarding":
        return True

    return False
