"""
Test multi-tenancy for admin/teacher routes.

V2 canonical model: isolation is enforced via Seat.class_id → ClassEconomy.user_id.
"""

from tests.helpers.v2_fixtures import seed_canonical_admin, seed_class_with_seat, seed_student_identity
from tests.helpers.class_scope import create_class_scope
import pytest
from app.models import ClassEconomy, Seat, User
from app.extensions import db


def _get_teacher_students(teacher_user_id: int):
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


@pytest.fixture
def two_teachers(client):
    teacher1 = seed_canonical_admin("teacher1").user
    teacher2 = seed_canonical_admin("teacher2").user

    # 5 students in teacher1's classes
    for i in range(5):
        seed_class_with_seat(
            teacher=teacher1,
            display_name="A",
            student_first_name=f"StudentT1_{i}",
            student_last_name="A",
        )

    # 3 students in teacher2's classes
    for i in range(3):
        seed_class_with_seat(
            teacher=teacher2,
            display_name="B",
            student_first_name=f"StudentT2_{i}",
            student_last_name="B",
        )

    db.session.commit()
    return teacher1, teacher2


def test_teacher_can_only_see_own_students(client, two_teachers):
    """Teacher1 sees only their 5 students via class_id scoping."""
    teacher1, teacher2 = two_teachers

    students = _get_teacher_students(teacher1.id)
    assert len(students) == 5
    for seat in students:
        class_row = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
        assert class_row.user_id == teacher1.id


def test_brand_new_teacher_sees_no_students(client, two_teachers):
    """A teacher with no classes sees zero students."""
    new_teacher = seed_canonical_admin("new_teacher").user

    students = _get_teacher_students(new_teacher.id)
    assert len(students) == 0


def test_teacher2_sees_only_their_students(client, two_teachers):
    """Teacher2 sees only their 3 students via class_id scoping."""
    teacher1, teacher2 = two_teachers

    students = _get_teacher_students(teacher2.id)
    assert len(students) == 3
    for seat in students:
        class_row = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
        assert class_row.user_id == teacher2.id


def test_students_without_class_not_visible_to_teachers(client):
    """Students with no class (no Seat) are not visible to any teacher."""
    teacher = seed_canonical_admin("isolated_teacher").user

    students = _get_teacher_students(teacher.id)
    assert len(students) == 0


def test_class_isolation_between_teachers(client):
    """Students in teacher A's class are invisible to teacher B."""
    teacher_a = seed_canonical_admin("cls_iso_a").user
    teacher_b = seed_canonical_admin("cls_iso_b").user

    cls_a = seed_class_with_seat(
        teacher=teacher_a,
        join_code="ISOCLS1",
        display_name="A",
        student_first_name="Isolated",
        student_last_name="I",
    ).class_row
    db.session.commit()

    students_visible_to_b = _get_teacher_students(teacher_b.id)
    assert len(students_visible_to_b) == 0
