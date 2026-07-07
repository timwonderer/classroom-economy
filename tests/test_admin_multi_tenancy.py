"""
Test multi-tenancy for admin/teacher routes.

Ensures that teachers can only see students in their own classes,
not students belonging to other teachers' classes.

V2 canonical model: isolation is enforced via Seat.class_id → ClassEconomy.user_id.
A teacher owns classes where ClassEconomy.user_id == teacher's User.id.
"""

from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import create_class_scope, make_student_identity
import pytest
from app.models import User, UserRole, Admin, ClassEconomy, Seat
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
    teacher1 = make_admin("teacher1", "SECRET1")
    teacher2 = make_admin("teacher2", "SECRET2")
    db.session.add_all([teacher1, teacher2])
    db.session.flush()

    # 5 students in teacher1's class
    for i in range(5):
        s = make_student_identity(block="A", first_name=f"StudentT1_{i}", last_name="A")
        create_class_scope(teacher=teacher1, join_code=f"T1CLS{i}", student=s, block="A", display_name="A")

    # 3 students in teacher2's class
    for i in range(3):
        s = make_student_identity(block="B", first_name=f"StudentT2_{i}", last_name="B")
        create_class_scope(teacher=teacher2, join_code=f"T2CLS{i}", student=s, block="B", display_name="B")

    db.session.commit()
    return teacher1, teacher2


def test_teacher_can_only_see_own_students(client, two_teachers):
    """Teacher1 sees only their 5 students via class_id scoping."""
    teacher1, teacher2 = two_teachers
    user1 = User.query.filter_by(username_hash=teacher1.username_hash).first()
    assert user1 is not None

    students = _get_teacher_students(user1.id)
    assert len(students) == 5
    for seat in students:
        class_row = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
        assert class_row.user_id == user1.id


def test_brand_new_teacher_sees_no_students(client, two_teachers):
    """A teacher with no classes sees zero students."""
    new_teacher = make_admin("new_teacher", "SECRET3")
    db.session.add(new_teacher)
    db.session.commit()

    user = User.query.filter_by(username_hash=new_teacher.username_hash).first()
    assert user is not None

    students = _get_teacher_students(user.id)
    assert len(students) == 0


def test_teacher2_sees_only_their_students(client, two_teachers):
    """Teacher2 sees only their 3 students via class_id scoping."""
    teacher1, teacher2 = two_teachers
    user2 = User.query.filter_by(username_hash=teacher2.username_hash).first()
    assert user2 is not None

    students = _get_teacher_students(user2.id)
    assert len(students) == 3
    for seat in students:
        class_row = ClassEconomy.query.filter_by(class_id=seat.class_id).first()
        assert class_row.user_id == user2.id


def test_students_without_class_not_visible_to_teachers(client):
    """Students with no class (no Seat) are not visible to any teacher."""
    teacher = make_admin("isolated_teacher", "SECRET4")
    db.session.add(teacher)
    db.session.flush()

    orphaned = make_student_identity(block="Z", first_name="Orphaned", last_name="Z", claimed=False)
    db.session.commit()

    user = User.query.filter_by(username_hash=teacher.username_hash).first()
    assert user is not None

    students = _get_teacher_students(user.id)
    seat_ids = {s.id for s in students}

    orphaned_seat = Seat.query.filter_by(user_id=orphaned.user_id).first()
    if orphaned_seat:
        assert orphaned_seat.id not in seat_ids
    else:
        assert len(students) == 0


def test_class_isolation_between_teachers(client):
    """Students in teacher A's class are invisible to teacher B."""
    teacher_a = make_admin("cls_iso_a", "SECA")
    teacher_b = make_admin("cls_iso_b", "SECB")
    db.session.add_all([teacher_a, teacher_b])
    db.session.flush()

    student = make_student_identity(block="A", first_name="Isolated", last_name="I")
    create_class_scope(teacher=teacher_a, join_code="ISOCLS1", student=student, block="A", display_name="A")
    db.session.commit()

    user_b = User.query.filter_by(username_hash=teacher_b.username_hash).first()
    assert user_b is not None

    students_visible_to_b = _get_teacher_students(user_b.id)
    assert len(students_visible_to_b) == 0
