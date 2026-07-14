from datetime import datetime, timezone

from app.extensions import db
from app.feats.base import FEATContext
from app.models import PayrollSettings, Seat, User
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.v2_fixtures import seed_canonical_admin


def _login_canonical_admin(client, admin: User, *, class_id: str) -> None:
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
        )


def test_payroll_settings_update_persists_class_scoped_row(client):
    admin = seed_canonical_admin("pay_scope_admin").user

    with FEATContext("FEAT-IDEN-001", idempotency_key="payroll_settings_scope:create_class"):
        class_row = create_class_scope(
            teacher_user=admin,
            join_code="PAY-SCOPE-A",
            section="B",
        )
        db.session.flush()

    _login_canonical_admin(
        client,
        admin,
        class_id=class_row.class_id,
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
    admin = seed_canonical_admin("pay_hours_admin").user

    with FEATContext("FEAT-IDEN-001", idempotency_key="payroll_settings_scope:create_class_hours"):
        class_row = create_class_scope(
            teacher_user=admin,
            join_code="PAY-SCOPE-H",
            section="C",
        )
        db.session.flush()

    _login_canonical_admin(
        client,
        admin,
        class_id=class_row.class_id,
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
