from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import User, Seat, Transaction, TransactionStatus
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_scope import make_student_identity


def _login_student(client, student_id, join_code):
    from app.models import ClassEconomy
    with client.session_transaction() as sess:
        class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
        student_seat = Seat.query.filter_by(user_id=student_id, class_id=class_row.class_id if class_row else None).first()
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

    class_a = create_class_scope(teacher_user=teacher, join_code="STUDSC1", display_name="A")
    class_b = create_class_scope(teacher_user=teacher, join_code="STUDSC2", display_name="B")
    db.session.flush()

    student = make_student_identity(class_id=class_a.class_id, first_name="Scope", last_name="T", claimed=True)
    db.session.flush()
    # Add student to class_b as well
    from app.models import IdentityProfile
    seat_b_extra = Seat(user_id=student.user_id, class_id=class_b.class_id, role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat_b_extra)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat_b_extra.id, profile_type="student_claimed", first_name="Scope", last_name="T", class_id=class_b.class_id))
    seat_a = Seat.query.filter_by(class_id=class_a.class_id, user_id=student.user_id).first()
    seat_b = Seat.query.filter_by(class_id=class_b.class_id, user_id=student.user_id).first()
    db.session.add_all([
        Transaction(
            seat_id=seat_a.id,
            user_id=student.user_id,
            join_code="STUDSC1",
            class_id=class_a.class_id,
            amount=Decimal("10.00"),
            account_type="checking",
            status=TransactionStatus.PENDING,
            type="deposit",
            description="Class A earnings",
        ),
        Transaction(
            seat_id=seat_b.id,
            user_id=student.user_id,
            join_code="STUDSC2",
            class_id=class_b.class_id,
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
