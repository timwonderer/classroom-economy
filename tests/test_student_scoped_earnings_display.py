from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import Admin, Student, StudentTeacher, Transaction, TransactionStatus
from tests.helpers.class_scope import create_class_scope


def _login_student(client, student_id, join_code):
    with client.session_transaction() as sess:
        sess["student_id"] = student_id
        sess["current_join_code"] = join_code
        sess["login_time"] = datetime.now(timezone.utc).isoformat()


def _build_multi_class_student():
    unique_suffix = datetime.now(timezone.utc).strftime("%H%M%S%f")
    teacher = make_admin(f"student_scope_teacher_{unique_suffix}", "secret")
    db.session.add(teacher)
    db.session.flush()

    student = Student(first_name="Scope", last_initial="T", block="A, B", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    class_a = create_class_scope(teacher=teacher, join_code="STUDSC1", student=student, block="A", display_name="A")
    class_b = create_class_scope(teacher=teacher, join_code="STUDSC2", student=student, block="B", display_name="B")
    db.session.add_all([
        Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code="STUDSC1",
            amount=Decimal("10.00"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            type="deposit",
            description="Class A earnings",
        ),
        Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code="STUDSC2",
            amount=Decimal("200.00"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            type="deposit",
            description="Class B earnings",
        ),
    ])
    db.session.commit()
    return student


def test_student_payroll_displays_join_code_scoped_lifetime_earnings(client):
    student = _build_multi_class_student()
    _login_student(client, student.id, "STUDSC1")

    response = client.get("/student/payroll")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Total Lifetime Earnings" in body
    assert "$10.00" in body
    assert "$210.00" not in body


def test_student_transfer_displays_join_code_scoped_total_earnings(client):
    student = _build_multi_class_student()
    _login_student(client, student.id, "STUDSC1")

    response = client.get("/student/transfer")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Total Earnings" in body
    assert "$10.00" in body
    assert "$210.00" not in body
