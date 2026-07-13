from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import seed_canonical_admin, seed_purchase
from app.extensions import db
from app.feats.base import FEATContext
from app.models import Seat, IdentityProfile, Transaction, TransactionStatus, User, UserRole
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context


def _login_admin(client, *, user_id: int, class_id: str):
    teacher_seat = Seat.query.filter_by(class_id=class_id, role="teacher").first()
    assert teacher_seat is not None
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=user_id,
            class_id=class_id,
            seat_id=teacher_seat.id,
            role="teacher",
        )


def test_admin_payroll_displays_scoped_balances_only(client):
    teacher_a = seed_canonical_admin("payroll_scope_a").user
    teacher_b = seed_canonical_admin("payroll_scope_b").user
    db.session.flush()

    class_a = create_class_scope(teacher_user=teacher_a, join_code="PAYA01", display_name="A")
    class_b = create_class_scope(teacher_user=teacher_b, join_code="PAYB01", display_name="A")
    db.session.flush()
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin_payroll_scoped_balances:student_seed"):
        student_user = User(user_role=UserRole.STUDENT, username_hash="payroll_scope_student_hash", username_lookup_hash="payroll_scope_student_lookup")
        db.session.add(student_user)
        db.session.flush()
        seat_a = Seat(user_id=student_user.id, class_id=class_a.class_id, role="student", claimed_at=datetime.now(timezone.utc))
        seat_b = Seat(user_id=student_user.id, class_id=class_b.class_id, role="student", claimed_at=datetime.now(timezone.utc))
        db.session.add_all([seat_a, seat_b])
        db.session.flush()
        db.session.add(IdentityProfile(seat_id=seat_a.id, profile_type="student", first_name="Pay", last_name="S"))
        db.session.add(IdentityProfile(seat_id=seat_b.id, profile_type="student_claimed", first_name="Pay", last_name="S"))
        db.session.flush()
    assert seat_a is not None and seat_b is not None

    with FEATContext("FEAT-ADMN-001"):
        seed_purchase(
            seat_id=seat_a.id,
            class_id=class_a.class_id,
            user_id=student_user.id,
            amount="111.11",
            description="Teacher A balance",
            transaction_type="deposit",
        )
        seed_purchase(
            seat_id=seat_b.id,
            class_id=class_b.class_id,
            user_id=student_user.id,
            amount="222.22",
            description="Teacher B balance",
            transaction_type="deposit",
        )

    _login_admin(
        client,
        user_id=teacher_a.id,
        class_id=class_a.class_id,
    )
    response = client.get("/admin/payroll")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "$111.11" in body
    assert "$222.22" not in body
