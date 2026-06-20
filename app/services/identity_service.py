from __future__ import annotations

from app.extensions import db
from app.models import IdentityProfile, Student, StudentBlock, User, Seat


def _resolve_student_and_seat(identity, *, seat=None) -> tuple[Student | None, Seat | None]:
    """
    Resolve a legacy/new identity input to a concrete (student, seat) pair.

    Supported identity inputs:
    - legacy Student
    - new Seat
    - new User (first linked student seat)
    """
    resolved_seat = seat
    resolved_student = None

    if isinstance(identity, Student):
        resolved_student = identity
    elif isinstance(identity, Seat):
        resolved_seat = identity
    elif isinstance(identity, User):
        if not resolved_seat:
            resolved_seat = (
                Seat.query
                .filter(
                    Seat.user_id == identity.id,
                )
                .order_by(Seat.id.asc())
                .first()
            )
    elif identity is None:
        pass
    else:
        # Backward-compatible duck typing for legacy callers that pass student-like objects.
        if hasattr(identity, "hall_passes") and hasattr(identity, "id"):
            resolved_student = identity

    if resolved_seat and not resolved_student:
        resolved_student = resolved_seat.student
        if not resolved_student and resolved_seat.user_id:
            resolved_student = db.session.get(Student, resolved_seat.user_id)

    if resolved_student and not resolved_seat:
        resolved_seat = (
            Seat.query
            .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
            .join(Student, Student.identity_id == IdentityProfile.id)
            .filter(Student.id == resolved_student.id)
            .order_by(Seat.id.asc())
            .first()
        )

    return resolved_student, resolved_seat


def add_hall_passes(identity, quantity: int, *, seat=None) -> int:
    """Identity-owned mutation for hall-pass counters."""
    student, _ = _resolve_student_and_seat(identity, seat=seat)
    if not student:
        return 0
    current_total = max(0, int(student.hall_passes or 0))
    student.hall_passes = current_total + int(quantity)
    db.session.add(student)
    return student.hall_passes


def reconcile_rent_hall_pass_top_off(
    *,
    seat=None,
    identity=None,
    target_rent_passes: int,
):
    """
    Identity-owned mutation for rent-provided hall passes.

    Returns (passes_awarded, passes_revoked, state_changed).
    """
    student, seat = _resolve_student_and_seat(identity, seat=seat)
    if not student:
        return 0, 0, False

    student_block = None
    if seat:
        student_block = StudentBlock.query.filter(
            StudentBlock.seat_id == seat.id,
        ).first()

    if not student_block:
        student_block = StudentBlock.query.filter(
            StudentBlock.student_id == student.id,
            StudentBlock.period == (seat.block if seat else None),
            StudentBlock.join_code == (seat.join_code if seat else None),
        ).order_by(StudentBlock.id.asc()).first()

    state_changed = False
    target_rent_passes = max(0, int(target_rent_passes or 0))

    if not student_block and target_rent_passes > 0 and seat:
        student_block = StudentBlock(
            student_id=student.id,
            seat_id=seat.id,
            period=seat.block,
            class_id=seat.class_id,
            rent_hall_passes=0,
        )
        db.session.add(student_block)
        state_changed = True

    current_total_passes = max(0, int(student.hall_passes or 0))
    current_rent_passes = max(0, int(student_block.rent_hall_passes or 0)) if student_block else 0
    effective_rent_passes = min(current_rent_passes, current_total_passes)
    delta = target_rent_passes - effective_rent_passes
    passes_awarded = max(0, delta)
    passes_revoked = max(0, -delta)

    if delta != 0:
        student.hall_passes = current_total_passes + delta
        db.session.add(student)
        state_changed = True

    if student_block and student_block.rent_hall_passes != target_rent_passes:
        student_block.rent_hall_passes = target_rent_passes
        state_changed = True

    return passes_awarded, passes_revoked, state_changed
