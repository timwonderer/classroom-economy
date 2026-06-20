from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import (
    Admin,
    IdentityProfile,
    Student,
    StudentTeacher,
    Transaction,
    TransactionStatus,
)
from tests.helpers.class_scope import create_class_scope


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin_id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _attach_student_to_class(student, teacher, join_code):
    create_class_scope(teacher=teacher, join_code=join_code, student=student)


def test_export_students_uses_only_teacher_owned_join_codes(client):
    teacher_a = make_admin("teacher_export_a", "secret-a")
    teacher_b = make_admin("teacher_export_b", "secret-b")
    db.session.add_all([teacher_a, teacher_b])
    db.session.flush()

    profile = IdentityProfile(profile_type="student", first_name="Alex", last_name="S")
    db.session.add(profile)
    db.session.flush()
    student = Student(identity_profile=profile, block="A", salt=b"salt")
    db.session.add(student)
    db.session.flush()

    db.session.add_all([
        StudentTeacher(student_id=student.id, teacher_id=teacher_a.id),
        StudentTeacher(student_id=student.id, teacher_id=teacher_b.id),
    ])

    _attach_student_to_class(student, teacher_a, "JOINEXPA")
    _attach_student_to_class(student, teacher_b, "JOINEXPB")

    db.session.add_all([
        Transaction(
            student_id=student.id,
            teacher_id=teacher_a.id,
            join_code="JOINEXPA",
            amount=Decimal("100.00"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            type="deposit",
            description="Teacher A funds",
        ),
        Transaction(
            student_id=student.id,
            teacher_id=teacher_b.id,
            join_code="JOINEXPB",
            amount=Decimal("250.00"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            type="deposit",
            description="Teacher B funds",
        ),
    ])
    db.session.commit()

    _login_admin(client, teacher_a.id)
    response_a = client.get("/admin/export-students")
    assert response_a.status_code == 200
    body_a = response_a.data.decode("utf-8")
    assert "Alex,S,A,100.00,0.00,100.00" in body_a
    assert "250.00" not in body_a

    _login_admin(client, teacher_b.id)
    response_b = client.get("/admin/export-students")
    assert response_b.status_code == 200
    body_b = response_b.data.decode("utf-8")
    assert "Alex,S,A,250.00,0.00,250.00" in body_b
    assert "100.00,0.00,100.00" not in body_b
