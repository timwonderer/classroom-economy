from datetime import datetime, timezone

from app.extensions import db
from app.models import RentSettings, Seat, User
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.v2_fixtures import seed_canonical_admin, seed_class_feature


def _login_canonical_admin(client, admin: User, *, class_id: str) -> None:
    teacher_seat = Seat.query.filter_by(class_id=class_id, role="teacher").first()
    with client.session_transaction() as sess:
        sess["user_id"] = admin.id
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_id,
            seat_id=teacher_seat.id if teacher_seat else admin.id,
            role="teacher",
        )


def test_rent_settings_update_persists_class_scoped_row(client):
    admin = seed_canonical_admin("rent_scope_admin").user

    class_row = create_class_scope(
        teacher_user=admin,
        join_code="RENT-SCOPE-A",
    )
    seed_class_feature(class_id=class_row.class_id, feature_name="rent")

    _login_canonical_admin(
        client,
        admin,
        class_id=class_row.class_id,
    )

    response = client.post(
        "/admin/rent-settings",
        data={
            "settings_block": "B",
            "is_enabled": "on",
            "rent_amount": "75.00",
            "frequency_type": "weekly",
            "due_day_of_month": "1",
            "grace_period_days": "3",
            "late_penalty_amount": "10.00",
            "late_penalty_type": "once",
            "bill_preview_days": "7",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302

    saved = RentSettings.query.filter_by(class_id=class_row.class_id).first()
    assert saved is not None
    assert float(saved.rent_amount) == 75.0
    assert saved.class_id == class_row.class_id
