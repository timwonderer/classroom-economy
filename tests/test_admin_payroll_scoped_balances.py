from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import Admin, Seat, IdentityProfile, Transaction, TransactionStatus, User, UserRole
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context


def _bind_canonical_teacher(admin: Admin) -> User:
    if getattr(admin, "user_id", None):
        user = db.session.get(User, admin.user_id)
        if user is not None:
            return user
    user = User.query.filter_by(username_lookup_hash=admin.username_lookup_hash).first()
    if user is None:
        user = User(
            user_role=UserRole.TEACHER,
            username_hash=admin.username_hash,
            username_lookup_hash=admin.username_lookup_hash,
        )
        db.session.add(user)
        db.session.flush()
    admin.user_id = user.id
    return user


def _login_admin(client, admin_id, *, user_id: int, class_id: str, join_code: str):
    teacher_seat = Seat.query.filter_by(class_id=class_id, role="teacher").first()
    assert teacher_seat is not None
    with client.session_transaction() as sess:
        sess["admin_id"] = admin_id
        sess["is_admin"] = True
        set_canonical_context(
            sess,
            user_id=user_id,
            class_id=class_id,
            seat_id=teacher_seat.id,
            role="teacher",
            join_code=join_code,
        )


def test_admin_payroll_displays_scoped_balances_only(client):
    teacher_a = make_admin("payroll_scope_a", "secret-a")
    teacher_b = make_admin("payroll_scope_b", "secret-b")
    db.session.add_all([teacher_a, teacher_b])
    db.session.flush()
    user_a = _bind_canonical_teacher(teacher_a)
    _bind_canonical_teacher(teacher_b)

    profile = IdentityProfile(profile_type="student", first_name="Pay", last_name="S")
    db.session.add(profile)
    db.session.flush()
    student_user = User(user_role=UserRole.STUDENT, username_hash="payroll_scope_student_hash", username_lookup_hash="payroll_scope_student_lookup")
    db.session.add(student_user)
    db.session.flush()

    class_a = create_class_scope(teacher=teacher_a, join_code="PAYA01", block="A", display_name="A")
    class_b = create_class_scope(teacher=teacher_b, join_code="PAYB01", block="A", display_name="A")
    db.session.flush()
    seat_a = Seat(user_id=student_user.id, class_id=class_a.class_id, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    seat_b = Seat(user_id=student_user.id, class_id=class_b.class_id, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add_all([seat_a, seat_b])
    db.session.flush()
    profile.seat_id = seat_a.id
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
        teacher_a.id,
        user_id=user_a.id,
        class_id=class_a.class_id,
        join_code="PAYA01",
    )
    response = client.get("/admin/payroll")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "$111.11" in body
    assert "$222.22" not in body
