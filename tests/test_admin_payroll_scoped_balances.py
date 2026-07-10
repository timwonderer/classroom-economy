from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin
from app.extensions import db
from app.models import Seat, IdentityProfile, Transaction, TransactionStatus, User, UserRole
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context


def _login_admin(client, *, user_id: int, class_id: str, join_code: str):
    teacher_seat = Seat.query.filter_by(class_id=class_id, role="teacher").first()
    assert teacher_seat is not None
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user_id,
            class_id=class_id,
            seat_id=teacher_seat.id,
            role="teacher",
            join_code=join_code,
        )


def test_admin_payroll_displays_scoped_balances_only(client):
    teacher_a = make_admin("payroll_scope_a")
    teacher_b = make_admin("payroll_scope_b")
    db.session.flush()

    student_user = User(user_role=UserRole.STUDENT, username_hash="payroll_scope_student_hash", username_lookup_hash="payroll_scope_student_lookup")
    db.session.add(student_user)
    db.session.flush()

    class_a = create_class_scope(teacher_user=teacher_a, join_code="PAYA01", display_name="A")
    class_b = create_class_scope(teacher_user=teacher_b, join_code="PAYB01", display_name="A")
    db.session.flush()
    seat_a = Seat(user_id=student_user.id, class_id=class_a.class_id, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    seat_b = Seat(user_id=student_user.id, class_id=class_b.class_id, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add_all([seat_a, seat_b])
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat_a.id, profile_type="student", first_name="Pay", last_name="S"))
    db.session.add(IdentityProfile(seat_id=seat_b.id, profile_type="student_claimed", first_name="Pay", last_name="S"))
    assert seat_a is not None and seat_b is not None

    from app.feats.base import FEATContext
    with FEATContext("FEAT-ADMN-001"):
        db.session.add_all([
            Transaction(
                user_id=student_user.id, join_code="PAYA01",
                class_id=class_a.class_id,
                seat_id=seat_a.id,
                amount=Decimal("111.11"),
                account_type="checking",
                status=TransactionStatus.PENDING,
                type="deposit",
                description="Teacher A balance",
            ),
            Transaction(
                user_id=student_user.id, join_code="PAYB01",
                class_id=class_b.class_id,
                seat_id=seat_b.id,
                amount=Decimal("222.22"),
                account_type="checking",
                status=TransactionStatus.PENDING,
                type="deposit",
                description="Teacher B balance",
            ),
        ])
        db.session.flush()

    _login_admin(
        client,
        user_id=teacher_a.id,
        class_id=class_a.class_id,
        join_code="PAYA01",
    )
    response = client.get("/admin/payroll")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "$111.11" in body
    assert "$222.22" not in body
