from datetime import datetime, timezone

from app.extensions import db
from app.models import Admin, BankingSettings, Seat, User, UserRole
from app.utils.auth_username import build_hashed_username_fields
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.v2_fixtures import make_admin


def _bind_canonical_teacher(admin: Admin, username: str) -> User:
    salt, username_hash, username_lookup_hash = build_hashed_username_fields(username)
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=username_hash,
        username_lookup_hash=username_lookup_hash,
    )
    db.session.add(user)
    db.session.flush()
    admin.user_id = user.id
    return user


def _login_canonical_admin(client, admin: Admin, user: User, *, class_id: str, join_code: str) -> None:
    teacher_seat = Seat.query.filter_by(class_id=class_id, role="teacher").first()
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin.id
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=class_id,
            seat_id=teacher_seat.id if teacher_seat else user.id,
            role="teacher",
            join_code=join_code,
        )


def test_banking_settings_update_persists_class_scoped_row(client):
    admin = make_admin("bank_scope_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    user = _bind_canonical_teacher(admin, "bank_scope_admin")
    class_row = create_class_scope(
        teacher=admin,
        join_code="BANK001",
        block="B",
        create_claimed_teacher_block=True,
    )
    db.session.add(ClassFeature(class_id=class_row.class_id, feature_name="banking"))
    db.session.commit()

    _login_canonical_admin(
        client,
        admin,
        user,
        class_id=class_row.class_id,
        join_code=class_row.join_code,
    )

    response = client.post(
        "/admin/banking/settings",
        data={
            "settings_block": "B",
            "rate_input_mode": "apy",
            "savings_apy": "4.5",
            "savings_monthly_rate": "0.0",
            "interest_calculation_type": "simple",
            "compound_frequency": "monthly",
            "interest_schedule_type": "monthly",
            "interest_schedule_cycle_days": "30",
            "overdraft_fee_type": "flat",
            "overdraft_fee_flat_amount": "15.00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/banking?settings_block=B")

    saved = BankingSettings.query.filter_by(class_id=class_row.class_id, block="B").first()
    assert saved is not None
    assert float(saved.savings_apy) == 4.5
    assert saved.class_id == class_row.class_id
    assert saved.block == "B"
