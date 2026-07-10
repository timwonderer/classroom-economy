from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import make_student_identity, create_class_scope
import pyotp
from app import db
from app.models import User, ClassEconomy, Seat


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
    db.session.flush()
    # Create a class for teacher_b, then create student in it
    class_b = create_class_scope(teacher_user=teacher_b, join_code="LEAKCLS1")
    student_b = make_student_identity(class_id=class_b.class_id, first_name="UnassignedStudent", last_name="B", claimed=False)
    db.session.commit()

    teacher_a = make_admin("teacher_a_leak", pyotp.random_base32())
    db.session.flush()
    db.session.commit()

    # teacher_a has no classes, should see no students
    results = _get_teacher_student_seats(teacher_a.id)
    assert len(results) == 0, "Teacher A should not see students not in Teacher A's classes"


def test_owner_can_see_students_in_own_class(client):
    """
    Verify that a teacher CAN see students enrolled in their own class.
    """
    teacher_b = make_admin("teacher_b_owner", pyotp.random_base32())
    db.session.flush()

    class_b = create_class_scope(teacher_user=teacher_b, join_code="OWNERCLS1")
    student_b = make_student_identity(class_id=class_b.class_id, first_name="OwnerTestStudent", last_name="B")
    db.session.commit()

    results = _get_teacher_student_seats(teacher_b.id)
    assert len(results) == 1
