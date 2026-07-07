from datetime import datetime, timezone
from decimal import Decimal
import io

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import User, UserRole, Admin, IdentityProfile, Seat, Transaction
from app.services.ledger_service import get_available_balances
from app.routes.admin import _sanitize_roster_text
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin_id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _make_student(first_name: str, last_initial: str = "A", block: str = "A"):
    user = User(
        user_role=UserRole.STUDENT,
        username_hash=f"{first_name.lower()}-{block.lower()}-hash",
        username_lookup_hash=f"{first_name.lower()}-{block.lower()}-lookup",
    )
    db.session.add(user)
    db.session.flush()

    seat = Seat(
        user_id=user.id,
        role="student",
        block=block,
        block_identifier=block,
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(seat)
    db.session.flush()

    profile = IdentityProfile(
        seat_id=seat.id,
        profile_type="student",
        first_name=first_name,
        last_name=last_initial,
    )
    db.session.add(profile)
    db.session.flush()
    return user, seat, profile


def test_roster_upload_ignores_balance_columns_and_keeps_ledger_truth(client):
    teacher = make_admin("teacher_roster_sync", "secret-sync")
    db.session.add(teacher)
    db.session.commit()

    student_user, seat, profile = _make_student("Original", "N")
    class_row = create_class_scope(
        teacher=teacher,
        student=seat,
        block="A",
        display_name="Roster Sync",
        create_claimed_teacher_block=True,
        teacher_block_claimed=True,
        create_seat=True,
    )
    db.session.commit()

    seat = Seat.query.filter_by(class_id=class_row.class_id, role="student").first()
    teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").first()
    assert seat is not None
    assert teacher_seat is not None
    seat.public_id = "stu_roster_sync_1"
    db.session.commit()

    db.session.add(
        Transaction(
            user_id=student_user.id,
            seat_id=seat.id,
            class_id=class_row.class_id,
            amount=Decimal("42.50"),
            account_type="checking",
            type="deposit",
            description="Seed checking balance",
        )
    )
    db.session.commit()

    before_checking, before_savings = get_available_balances(seat.id, class_row.class_id)
    assert before_checking == Decimal("42.50")
    assert before_savings == Decimal("0.00")

    _login_admin(client, teacher.id)
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=teacher_seat.user_id,
            class_id=class_row.class_id,
            seat_id=teacher_seat.id,
            role="teacher",
        )

    csv_body = (
        "join_code,actor_public_id,first_name,last_name,notes,checking_balance,savings_balance\n"
        f"{class_row.join_code},{seat.public_id},<b>Updated</b>,Name,<script>alert(1)</script>Updated note,9999.99,8888.88\n"
    )
    response = client.post(
        "/admin/upload-students",
        data={
            "csv_file": (io.BytesIO(csv_body.encode("utf-8")), "roster.csv"),
            "roster_sync": "1",
            "confirm_roster_delete": "1",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    after_checking, after_savings = get_available_balances(seat.id, class_row.class_id)

    assert after_checking == before_checking
    assert after_savings == before_savings


def test_roster_text_sanitizer_strips_markup():
    assert _sanitize_roster_text("  <b>Safe</b> <script>alert(1)</script>  ") == "Safe alert(1)"


def test_roster_text_sanitizer_preserves_special_name_characters():
    assert _sanitize_roster_text("O'Connor-Ana María & Co.") == "O'Connor-Ana María & Co."
