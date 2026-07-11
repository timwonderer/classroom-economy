from datetime import datetime, timezone

from app.extensions import db
from app.models import PayrollSettings, Seat, User, UserRole
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.v2_fixtures import make_admin


def _login_canonical_admin(client, admin: User, *, class_id: str, join_code: str) -> None:
    teacher_seat = Seat.query.filter_by(class_id=class_id, role="teacher").first()
    assert teacher_seat is not None
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        set_canonical_context(
            sess,
            user_id=admin.id,
            class_id=class_id,
            seat_id=teacher_seat.id,
            role="teacher",
            join_code=join_code,
        )


def test_payroll_settings_update_persists_class_scoped_row(client):
    admin = make_admin("pay_scope_admin")
    db.session.flush()

    class_row = create_class_scope(
        teacher_user=admin,
        join_code="PAY001",
    )
    db.session.commit()

    _login_canonical_admin(
        client,
        admin,
        class_id=class_row.class_id,
        join_code=class_row.join_code,
    )

    response = client.post(
        "/admin/payroll/settings",
        data={
            "cwi_block": "B",
            "settings_mode": "simple",
            "simple_pay_rate": "15.0",
            "simple_frequency": "biweekly",
            "expected_weekly_hours": "5.0",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll")

    saved = PayrollSettings.query.filter_by(class_id=class_row.class_id).first()
    assert saved is not None
    assert float(saved.expected_weekly_hours) == 5.0


def test_expected_weekly_hours_update_creates_class_scoped_row(client):
    admin = make_admin("pay_hours_admin")
    db.session.flush()

    class_row = create_class_scope(
        teacher_user=admin,
        join_code="PAY002",
    )
    db.session.commit()

    _login_canonical_admin(
        client,
        admin,
        class_id=class_row.class_id,
        join_code=class_row.join_code,
    )

    response = client.post(
        "/admin/payroll/update-expected-hours",
        data={
            "cwi_block": "C",
            "expected_weekly_hours": "7.5",
            "apply_to_all": "false",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/payroll?cwi_block=C")

    saved = PayrollSettings.query.filter_by(class_id=class_row.class_id).first()
    assert saved is not None
    assert float(saved.expected_weekly_hours) == 7.5
