from datetime import datetime, timezone
from decimal import Decimal
import io

from app.extensions import db
from app.models import IdentityProfile, Seat, Transaction, User, UserRole
from app.services.ledger_service import get_available_balances
from app.routes.admin import _sanitize_roster_text
from app.feats.base import FEATContext
from tests.helpers.classroom_initializer import initialize_as_teacher


def test_DOM_CLASS_001__roster_upload_ignores_balance_columns_and_keeps_ledger_truth(client, app):
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    teacher = classroom.teacher_user
    class_row = classroom.economy
    seat = classroom.students[0].seat
    teacher_seat = classroom.teacher_seat
    with FEATContext("FEAT-IDEN-001", idempotency_key="admin_export_students_scoping:public_id"):
        seat.public_id = "stu_roster_sync_1"
        db.session.flush()

    with FEATContext("FEAT-LED-001", idempotency_key="admin_export_students_scoping:seed_balance"):
        from tests.helpers.v2_fixtures import seed_purchase
        seed_purchase(
            seat_id=seat.id,
            class_id=class_row.class_id,
            user_id=seat.user_id,
            amount="42.50",
            description="Seed checking balance",
            transaction_type="deposit",
        )

    before_checking, before_savings = get_available_balances(seat.id, class_row.class_id)
    assert before_checking == Decimal("42.50")
    assert before_savings == Decimal("0.00")

    csv_body = (
        "join_code,actor_public_id,first_name,last_name,notes,checking_balance,savings_balance\n"
        f"{class_row.join_code},{seat.public_id},<b>Updated</b>,Name,<script>alert(1)</script>Updated note,9999.99,8888.88\n"
    )
    response = client.post(
        "/admin/upload-students",
        data={
            "csv_file": (io.BytesIO(csv_body.encode("utf-8")), "roster.csv"),
            "roster_sync": "1",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    after_checking, after_savings = get_available_balances(seat.id, class_row.class_id)

    assert after_checking == before_checking
    assert after_savings == before_savings


def test_DOM_CLASS_001__roster_text_sanitizer_strips_markup():
    assert _sanitize_roster_text("  <b>Safe</b> <script>alert(1)</script>  ") == "Safe alert(1)"


def test_DOM_CLASS_001__roster_text_sanitizer_preserves_special_name_characters():
    assert _sanitize_roster_text("O'Connor-Ana María & Co.") == "O'Connor-Ana María & Co."
