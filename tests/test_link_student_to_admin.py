import pytest

from app import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock
from app.routes.admin import _link_student_to_admin
from app.utils.join_code import generate_join_code
from hash_utils import get_random_salt, hash_username


def _create_admin(username: str = "teacher") -> Admin:
    admin = Admin(username=username, totp_secret="secret")
    db.session.add(admin)
    db.session.commit()
    return admin


def _create_student(block: str = "A", first_name: str = "Test", last_initial: str = "S", dob_sum: int = 1234) -> Student:
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial=last_initial,
        block=block,
        salt=salt,
        dob_sum=dob_sum,
        first_half_hash=f"{first_name[0].upper()}{dob_sum}",
        username_hash=hash_username(f"{first_name.lower()}-{block.lower()}", salt),
        pin_hash="pin",
    )
    db.session.add(student)
    db.session.commit()
    return student


def _create_teacher_block(admin_id: int, block: str, join_code: str, class_label: str | None, student: Student | None = None,
                          claimed: bool = False) -> TeacherBlock:
    last_name_parts = student.last_name_hash_by_part if student and student.last_name_hash_by_part is not None else {}
    seat = TeacherBlock(
        teacher_id=admin_id,
        block=block,
        class_label=class_label,
        join_code=join_code,
        is_claimed=claimed,
        student_id=student.id if student else None,
        first_name=(student.first_name if student else "Placeholder"),
        last_initial=(student.last_initial if student else "P"),
        last_name_hash_by_part=last_name_parts,
        dob_sum=(student.dob_sum if student else 0),
        salt=(student.salt if student else get_random_salt()),
        first_half_hash=(student.first_half_hash if student else "P0"),
    )
    db.session.add(seat)
    db.session.commit()
    return seat


def test_link_student_creates_relationships_and_teacher_block(client):
    admin = _create_admin()
    student = _create_student()

    _link_student_to_admin(student, admin.id)
    db.session.commit()

    assert StudentTeacher.query.filter_by(student_id=student.id, admin_id=admin.id).count() == 1
    teacher_block = TeacherBlock.query.filter_by(student_id=student.id, teacher_id=admin.id, block=student.block).one()
    assert teacher_block.join_code is not None
    assert teacher_block.is_claimed is True


def test_link_student_reuses_existing_join_code_and_label(client):
    admin = _create_admin("teacher-two")
    existing_join_code = generate_join_code()
    _create_teacher_block(admin.id, "B", existing_join_code, class_label="Biology")
    student = _create_student(block="B", first_name="Alex", last_initial="B")

    _link_student_to_admin(student, admin.id)
    db.session.commit()

    teacher_block = TeacherBlock.query.filter_by(student_id=student.id, teacher_id=admin.id, block="B").one()
    assert teacher_block.join_code == existing_join_code
    assert teacher_block.get_class_label() == "Biology"


def test_link_student_claims_existing_seat(client):
    admin = _create_admin("teacher-three")
    student = _create_student(block="C", first_name="Jamie", last_initial="C")
    existing = _create_teacher_block(admin.id, "C", generate_join_code(), class_label=None, student=student, claimed=False)

    _link_student_to_admin(student, admin.id)
    db.session.commit()

    refreshed = TeacherBlock.query.get(existing.id)
    assert refreshed.is_claimed is True
    # Should not create a duplicate record for the same student/block
    assert TeacherBlock.query.filter_by(teacher_id=admin.id, block="C").count() == 1


def test_link_student_skips_when_block_missing(client, caplog):
    admin = _create_admin("teacher-four")
    student = _create_student(block="", dob_sum=4321)

    with caplog.at_level("WARNING"):
        _link_student_to_admin(student, admin.id)

    assert StudentTeacher.query.filter_by(student_id=student.id, admin_id=admin.id).count() == 0
    assert TeacherBlock.query.filter_by(teacher_id=admin.id).count() == 0
