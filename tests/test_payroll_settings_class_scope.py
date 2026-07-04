from datetime import datetime, timezone

from app.extensions import db
from app.models import Admin, PayrollSettings, Seat, User, UserRole
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
    assert teacher_seat is not None
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin.id
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=class_id,
            seat_id=teacher_seat.id,
            role="teacher",
            join_code=join_code,
        )


def test_payroll_settings_update_persists_class_scoped_row(client):
    admin = make_admin("pay_scope_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    user = _bind_canonical_teacher(admin, "pay_scope_admin")
    class_row = create_class_scope(
        teacher=admin,
        join_code="PAY001",
        block="B",
        create_claimed_teacher_block=True,
    )
    db.session.commit()

    _login_canonical_admin(
        client,
        admin,
        user,
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

    saved = PayrollSettings.query.filter_by(class_id=class_row.class_id, block="B").first()
    assert saved is not None
    assert float(saved.expected_weekly_hours) == 5.0


def test_expected_weekly_hours_update_creates_class_scoped_row(client):
    admin = make_admin("pay_hours_admin", "secret")
    db.session.add(admin)
    db.session.flush()

    user = _bind_canonical_teacher(admin, "pay_hours_admin")
    class_row = create_class_scope(
        teacher=admin,
        join_code="PAY002",
        block="C",
        create_claimed_teacher_block=True,
    )
    db.session.commit()

    _login_canonical_admin(
        client,
        admin,
        user,
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

    saved = PayrollSettings.query.filter_by(class_id=class_row.class_id, block="C").first()
    assert saved is not None
    assert float(saved.expected_weekly_hours) == 7.5
