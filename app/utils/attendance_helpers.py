"""
Attendance Helper Utilities

Shared utilities for attendance and payroll calculations.
Created to break circular dependency between attendance.py and payroll.py.
"""

from sqlalchemy import func


def get_join_code_for_student_period(student_id, period, teacher_id=None):
    """
    Resolve the join_code for a student's specific period.

    Args:
        student_id (int): ID of the student.
        period (str): Period/block identifier (case-insensitive).
        teacher_id (int, optional): Restrict lookup to a specific teacher.

    Returns:
        str | None: join_code matching the student's seat for the requested period.
    """
    from app.models import ClassEconomy, IdentityProfile, Seat, Student

    query = (
        Seat.query
        .join(IdentityProfile, IdentityProfile.seat_id == Seat.id)
        .join(Student, Student.identity_id == IdentityProfile.id)
        .filter(
            Student.id == student_id,
            func.upper(Seat.block) == func.upper(period),
            Seat.claimed_at.isnot(None),
        )
    )

    if teacher_id:
        teacher_class_ids = (
            ClassEconomy.query
            .with_entities(ClassEconomy.class_id)
            .filter(ClassEconomy.teacher_id == teacher_id)
            .subquery()
        )
        query = query.filter(Seat.class_id.in_(teacher_class_ids))

    seat = query.order_by(Seat.id.desc()).first()
    return seat.join_code if seat else None
