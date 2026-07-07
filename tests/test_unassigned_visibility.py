from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import make_student_identity, create_class_scope
import pytest
from app import db
from app.models import User, Admin, ClassEconomy, Seat
import pyotp


def _get_teacher_student_seats(teacher_user_id: int):
    """Return student Seat rows in classes owned by this teacher."""
    return (
        Seat.query
        .join(ClassEconomy, ClassEconomy.class_id == Seat.class_id)
        .filter(
            ClassEconomy.user_id == teacher_user_id,
            Seat.role == "student",
        )
        .all()
    )


def test_new_admin_cannot_see_unassigned_students(client):
    """
    Regression test for P0 leak: New admins should NOT see students who have
    no class association (no Seat in any of their classes).
    """
    teacher_b = make_admin("teacher_b_leak", pyotp.random_base32())
    db.session.add(teacher_b)
    db.session.commit()

    # Student with no class association
    student_b = make_student_identity(block="A", first_name="UnassignedStudent", last_name="B", claimed=False)
    db.session.commit()

    teacher_a = make_admin("teacher_a_leak", pyotp.random_base32())
    db.session.add(teacher_a)
    db.session.commit()

    user_a = User.query.filter_by(username_hash=teacher_a.username_hash).first()
    assert user_a is not None

    results = _get_teacher_student_seats(user_a.id)
    assert len(results) == 0, "Teacher A should not see students with no class in Teacher A's scope"


def test_owner_can_see_students_in_own_class(client):
    """
    Verify that a teacher CAN see students enrolled in their own class.
    """
    teacher_b = make_admin("teacher_b_owner", pyotp.random_base32())
    db.session.add(teacher_b)
    db.session.flush()

    student_b = make_student_identity(block="A", first_name="OwnerTestStudent", last_name="B")
    create_class_scope(
        teacher=teacher_b,
        join_code="OWNERCLS1",
        student=student_b,
        block="A",
        display_name="A",
    )
    db.session.commit()

    user_b = User.query.filter_by(username_hash=teacher_b.username_hash).first()
    assert user_b is not None

    results = _get_teacher_student_seats(user_b.id)
    assert len(results) == 1
