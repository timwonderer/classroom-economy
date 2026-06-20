from datetime import datetime, timezone
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import csv
from io import StringIO

from app import db
from app.hash_utils import get_random_salt, hash_username
from app.models import Admin, ClassMembership, IdentityProfile, Seat, Student, StudentTeacher, Transaction
from tests.helpers.class_scope import create_class_scope


def _create_admin(username: str) -> Admin:
    admin = make_admin(username, "TESTSECRET123456")
    db.session.add(admin)
    db.session.commit()
    return admin


def _create_student(first_name: str, teacher: Admin) -> Student:
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="T",
        block="A",
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="fake-hash",
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.commit()
    return student


def _add_claimed_seat(admin: Admin, student: Student, block: str, join_code: str):
    if db.session.query(ClassMembership.id).filter_by(
        join_code=join_code,
        admin_id=admin.id,
        role="admin",
    ).first() is None:
        create_class_scope(
            teacher=admin,
            join_code=join_code,
            block=block,
            display_name=block,
        )
        db.session.flush()

    if db.session.query(ClassMembership.id).filter_by(
        join_code=join_code,
        student_id=student.id,
        role="student",
    ).first() is None:
        db.session.add(ClassMembership(
            join_code=join_code,
            student_id=student.id,
            role="student",
        ))

    from app.models import ClassEconomy
    class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
    seat = Seat(
        student_id=student.id,
        class_id=class_row.class_id if class_row else None,
        join_code=join_code,
        block=block,
        block_identifier=block,
        role="student",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat.id, profile_type="student_claimed", first_name=student.display_first_name, last_name=student.display_last_initial))
    db.session.commit()
    return seat


def _as_admin_session(client, admin: Admin):
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin.id


def test_export_students_scopes_students_and_balances_by_join_code(client):
    admin = _create_admin("export-admin")
    student_a = _create_student("Alice", admin)
    student_b = _create_student("Bob", admin)

    _add_claimed_seat(admin, student_a, "A", "JOIN_A")
    _add_claimed_seat(admin, student_a, "B", "JOIN_B")
    _add_claimed_seat(admin, student_b, "B", "JOIN_B")

    db.session.add_all(
        [
            Transaction(
                student_id=student_a.id,
                amount=10,
                type="bonus",
                account_type="checking",
                description="A-scoped",
                join_code="JOIN_A",
            ),
            Transaction(
                student_id=student_a.id,
                amount=25,
                type="bonus",
                account_type="checking",
                description="B-scoped",
                join_code="JOIN_B",
            ),
            Transaction(
                student_id=student_b.id,
                amount=15,
                type="bonus",
                account_type="checking",
                description="B-only",
                join_code="JOIN_B",
            ),
        ]
    )
    db.session.commit()

    _as_admin_session(client, admin)
    response = client.get("/admin/export-students?join_code=JOIN_A")

    assert response.status_code == 200
    rows = list(csv.reader(StringIO(response.get_data(as_text=True))))
    assert len(rows) == 2  # header + one scoped student row

    header, data_row = rows
    assert header[0] == "First Name"
    assert data_row[0] == "Alice"
    assert data_row[2] == "A"
    assert data_row[3] == "10.00"
    assert data_row[5] == "10.00"


def test_export_students_rejects_invalid_join_code_scope(client):
    admin = _create_admin("export-admin-invalid")
    _as_admin_session(client, admin)

    response = client.get("/admin/export-students?join_code=NOT_MINE")

    assert response.status_code == 403
