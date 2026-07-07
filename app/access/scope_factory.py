from __future__ import annotations

from dataclasses import dataclass

from flask import g, session

from app.access.scope import Scope
from app.auth import _column_exists
from app.extensions import db
from app.models import ClassEconomy, Seat


class AccessScopeDenied(Exception):
    def __init__(self, *, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


@dataclass(frozen=True)
class ResolvedStudentClassSwitch:
    scope: Scope
    seat_id: int


def _store_session_class_context(*, class_id: str | None, join_code: str | None) -> None:
    return None


def _scope_from_runtime_seat(*, actor, selected_class_id: str | None) -> Scope | None:
    context = getattr(g, "canonical_context", None)
    if not context:
        return None
    current_seat = db.session.get(Seat, context.seat_id)
    if not current_seat:
        return None
    if selected_class_id and current_seat.class_id != selected_class_id:
        return None

    class_row = None
    if current_seat.class_id:
        class_row = ClassEconomy.query.filter_by(class_id=current_seat.class_id).first()
    if not class_row:
        return None

    _store_session_class_context(class_id=class_row.class_id, join_code=None)
    return Scope(
        class_id=class_row.class_id,
        join_code=class_row.join_code,
        actor_id=actor.id,
        role="student",
        user_id=class_row.user_id,
        block=current_seat.block_identifier or current_seat.block,
        seat_id=current_seat.id,
    )


def resolve_student_class_switch_scope(*, actor, class_id: str) -> ResolvedStudentClassSwitch:
    """Resolve a strict claimed-class target for student class switching."""
    normalized_class_id = (class_id or "").strip()
    if not normalized_class_id:
        raise AccessScopeDenied(
            reason_code="no_class_scope",
            message="No class selected. Please select a class to continue.",
        )

    seat = (
        Seat.query.filter_by(
            user_id=actor.id,
            class_id=normalized_class_id,
        )
        .filter(Seat.claimed_at.isnot(None))
        .order_by(Seat.id.asc())
        .first()
    )

    if seat is None:
        raise AccessScopeDenied(
            reason_code="foreign_class_scope",
            message="You don't have access to that class.",
        )

    class_row = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
    if not class_row:
         raise AccessScopeDenied(
            reason_code="foreign_class_scope",
            message="Class configuration not found.",
        )

    scope = Scope(
        class_id=class_row.class_id,
        join_code=class_row.join_code,
        actor_id=actor.id,
        role="student",
        user_id=class_row.user_id,
        block=seat.block_identifier or seat.block,
        seat_id=seat.id,
    )
    return ResolvedStudentClassSwitch(scope=scope, seat_id=seat.id)


def _resolve_teacher_scope(*, actor, selected_class_id: str | None) -> Scope:
    normalized_class_id = (selected_class_id or "").strip() or None
    if not normalized_class_id:
        context = getattr(g, "canonical_context", None)
        normalized_class_id = getattr(context, "class_id", None)
    if normalized_class_id:
        class_row = ClassEconomy.query.filter_by(
            user_id=actor.id,
            class_id=normalized_class_id,
        ).first()
        if class_row:
            _store_session_class_context(class_id=class_row.class_id, join_code=None)
            return Scope(
                class_id=class_row.class_id,
                join_code=class_row.join_code,
                actor_id=actor.id,
                role="teacher",
                user_id=actor.id,
                block=class_row.display_name,
                seat_id=None,
            )

    class_query = (
        ClassEconomy.query
        .filter_by(user_id=actor.id)
        .order_by(ClassEconomy.display_name.asc(), ClassEconomy.join_code.asc())
    )
    class_row = None
    if normalized_class_id:
        class_row = class_query.filter(ClassEconomy.class_id == normalized_class_id).first()
    if class_row is None:
        class_row = class_query.first()
    
    if class_row:
        _store_session_class_context(class_id=class_row.class_id, join_code=None)
        return Scope(
            class_id=class_row.class_id,
            join_code=class_row.join_code,
            actor_id=actor.id,
            role="teacher",
            user_id=actor.id,
            block=class_row.display_name,
            seat_id=None,
        )

    raise AccessScopeDenied(
        reason_code="no_admin_scope",
        message="No class selected. Please select a class to continue.",
    )


def resolve_scope(*, actor, selected_join_code: str | None = None, actor_role: str = "student") -> Scope:
    """Resolve a request-time scope for the current actor inside the selected class."""
    if actor is None:
        raise AccessScopeDenied(
            reason_code="missing_actor",
            message="No active actor is bound to this request.",
        )

    if actor_role == "teacher":
        selected_class_id = None
        if selected_join_code:
            class_row = ClassEconomy.query.filter_by(join_code=selected_join_code).first()
            selected_class_id = class_row.class_id if class_row else None
        return _resolve_teacher_scope(actor=actor, selected_class_id=selected_class_id)

    context = getattr(g, "canonical_context", None)
    selected_class_id = getattr(context, "class_id", None)
    if selected_join_code:
        class_row = ClassEconomy.query.filter_by(join_code=selected_join_code).first()
        if class_row is None:
            raise AccessScopeDenied(
                reason_code="foreign_class_scope",
                message="You don't have access to that class.",
            )
        selected_class_id = class_row.class_id
    scope = _scope_from_runtime_seat(actor=actor, selected_class_id=selected_class_id)
    if scope is not None:
        return scope
    claimed_seats = (
        Seat.query.filter_by(user_id=actor.id)
        .filter(Seat.claimed_at.isnot(None))
        .order_by(Seat.id.asc())
        .all()
    )
    if not claimed_seats:
        raise AccessScopeDenied(
            reason_code="no_class_scope",
            message="No class selected. Please select a class to continue.",
        )

    active_seat = next((seat for seat in claimed_seats if seat.class_id == selected_class_id), None)
    if active_seat is None:
        active_seat = claimed_seats[0]

    _store_session_class_context(class_id=active_seat.class_id, join_code=None)
    g._auth_current_seat_cache = active_seat

    class_row = ClassEconomy.query.filter_by(class_id=active_seat.class_id).first()
    if not class_row:
         raise AccessScopeDenied(
            reason_code="no_class_scope",
            message="Class configuration not found.",
        )

    return Scope(
        class_id=class_row.class_id,
        join_code=class_row.join_code,
        actor_id=actor.id,
        role="student",
        user_id=class_row.user_id,
        block=active_seat.block_identifier or active_seat.block,
        seat_id=active_seat.id,
    )
