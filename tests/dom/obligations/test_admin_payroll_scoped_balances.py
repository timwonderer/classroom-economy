from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.feats.base import FEATContext
from app.models import IdentityProfile, Seat, User, UserRole
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher
from tests.helpers.v2_fixtures import seed_purchase


def test_DOM_CLASS_001__admin_payroll_displays_scoped_balances_only(client):
    class_a = initialize("chemistry_p1", client.application)
    class_b = initialize("biology_block_a", client.application)
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin_payroll_scoped_balances:student_seed"):
        student_user = class_a.students[0].user
        seat_a = class_a.students[0].seat
        seat_b = Seat(user_id=student_user.id, class_id=class_b.class_id, role="student", claimed_at=datetime.now(timezone.utc))
        db.session.add(seat_b)
        db.session.flush()
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

    initialize_as_teacher("chemistry_p1", client, client.application)
    response = client.get("/admin/payroll")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "$111.11" in body
    assert "$222.22" not in body
