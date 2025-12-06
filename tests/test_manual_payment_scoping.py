import pytest

from app import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock, Transaction
from hash_utils import get_random_salt


@pytest.fixture
def teacher_with_multi_class_student(client):
    """Create a teacher with a student assigned to two blocks."""

    teacher = Admin(username="teacher", totp_secret="SECRET")
    db.session.add(teacher)
    db.session.flush()

    salt = get_random_salt()
    student = Student(
        first_name="Timothy",
        last_initial="C",
        block="A,B",
        salt=salt,
        dob_sum=2025,
        first_half_hash="hash-primary",
        teacher_id=teacher.id,
    )
    db.session.add(student)
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))

    block_a = TeacherBlock(
        teacher_id=teacher.id,
        block="A",
        first_name=student.first_name,
        last_initial=student.last_initial,
        last_name_hash_by_part={},
        dob_sum=student.dob_sum,
        salt=salt,
        first_half_hash="hash-a",
        join_code="JOINA",
        is_claimed=True,
        student_id=student.id,
    )

    block_b = TeacherBlock(
        teacher_id=teacher.id,
        block="B",
        first_name=student.first_name,
        last_initial=student.last_initial,
        last_name_hash_by_part={},
        dob_sum=student.dob_sum,
        salt=salt,
        first_half_hash="hash-b",
        join_code="JOINB",
        is_claimed=True,
        student_id=student.id,
    )

    db.session.add_all([block_a, block_b])
    db.session.commit()

    return teacher, student


def test_manual_payment_scopes_to_selected_block(client, teacher_with_multi_class_student):
    teacher, student = teacher_with_multi_class_student

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = teacher.id

    response = client.post(
        "/admin/payroll/manual-payment",
        data={
            "description": "Bonus",
            "amount": "15.00",
            "account_type": "checking",
            "student_ids": [str(student.id)],
            "block": "B",
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True

    tx = Transaction.query.one()
    assert tx.join_code == "JOINB"
    assert tx.teacher_id == teacher.id
    assert tx.amount == 15.0


def test_manual_payment_requires_block_for_multi_class_student(client, teacher_with_multi_class_student):
    teacher, student = teacher_with_multi_class_student

    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = teacher.id

    response = client.post(
        "/admin/payroll/manual-payment",
        data={
            "description": "Bonus",
            "amount": "5.00",
            "account_type": "checking",
            "student_ids": [str(student.id)],
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert Transaction.query.count() == 0
