from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import User, UserRole, Admin, IdentityProfile, StudentTeacher, Transaction, TransactionStatus
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_scope import make_student_identity


def _login_student(client, student_id, join_code):
    with client.session_transaction() as sess:
        seat = StudentTeacher.query.filter_by(user_id=student_id).first()
        if seat:
            student_seat = Seat.query.filter_by(user_id=student_id, join_code=join_code).first()
            if student_seat:
                set_canonical_context(
                    sess,
                    user_id=student_id,
                    class_id=student_seat.class_id,
                    seat_id=student_seat.id,
                    role="student",
                    join_code=join_code,
                )


def _build_multi_class_student():
    unique_suffix = datetime.now(timezone.utc).strftime("%H%M%S%f")
    teacher = make_admin(f"student_scope_teacher_{unique_suffix}", "secret")
    db.session.add(teacher)
    db.session.flush()

    profile = IdentityProfile(profile_type="student", first_name="Scope", last_name="T")
    db.session.add(profile)
    db.session.flush()
    student = make_student_identity(first_name="Scope", last_name="T", block="A, B", claimed=True, profile_type="student_claimed")

    db.session.add(StudentTeacher(user_id=student.user_id, teacher_id=teacher.id))
    class_a = create_class_scope(teacher=teacher, join_code="STUDSC1", student=student, block="A", display_name="A")
    class_b = create_class_scope(teacher=teacher, join_code="STUDSC2", student=student, block="B", display_name="B")
    db.session.add_all([
        Transaction(
            user_id=student.user_id,join_code="STUDSC1",
            amount=Decimal("10.00"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            type="deposit",
            description="Class A earnings",
        ),
        Transaction(
            user_id=student.user_id,join_code="STUDSC2",
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
