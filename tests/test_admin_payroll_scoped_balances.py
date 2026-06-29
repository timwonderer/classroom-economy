from datetime import datetime, timezone
from decimal import Decimal
from werkzeug.security import generate_password_hash

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import Admin, Seat, IdentityProfile, Student, StudentTeacher, Transaction, TransactionStatus, User, UserRole
from tests.helpers.class_scope import create_class_scope


def _bind_canonical_teacher(admin: Admin) -> User:
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
    user = db.session.get(User, user_id)
    if user is not None:
        user.current_session_nonce = user.current_session_nonce or "payroll-scope-nonce"
        user.last_active_class_id = class_id
        db.session.commit()
    with client.session_transaction() as sess:
        sess["admin_id"] = admin_id
        sess["is_admin"] = True
        sess["user_id"] = user_id
        sess["current_session_nonce"] = user.current_session_nonce if user else "payroll-scope-nonce"
        sess["current_seat_id"] = teacher_seat.id
        sess["current_class_id"] = class_id
        sess["current_join_code"] = join_code
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def test_admin_payroll_displays_scoped_balances_only(client):
    teacher_a = make_admin("payroll_scope_a", "secret-a")
    teacher_b = make_admin("payroll_scope_b", "secret-b")
    db.session.add_all([teacher_a, teacher_b])
    db.session.flush()
    user_a = _bind_canonical_teacher(teacher_a)
    _bind_canonical_teacher(teacher_b)
    user_a.passphrase_hash = generate_password_hash("password")

    profile_a = IdentityProfile(profile_type="student", first_name="Pay", last_name="A")
    profile_b = IdentityProfile(profile_type="student", first_name="Pay", last_name="B")
    db.session.add_all([profile_a, profile_b])
    db.session.flush()
    student_a = Student(identity_profile=profile_a, block="A", salt=b"salt-a")
    student_b = Student(identity_profile=profile_b, block="A", salt=b"salt-b")
    db.session.add_all([student_a, student_b])
    db.session.flush()

    class_a = create_class_scope(teacher=teacher_a, join_code="PAYA01", student=student_a, block="A", display_name="A")
    class_b = create_class_scope(teacher=teacher_b, join_code="PAYB01", student=student_b, block="A", display_name="A")
    db.session.flush()
    seat_a = Seat.query.filter_by(class_id=class_a.class_id, role="student").first()
    seat_b = Seat.query.filter_by(class_id=class_b.class_id, role="student").first()
    assert seat_a is not None and seat_b is not None
    seat_a.claimed_at = datetime.now(timezone.utc)
    seat_b.claimed_at = datetime.now(timezone.utc)

    from app.feats.base import FEATContext
    with FEATContext("FEAT-ADMN-001"):
        db.session.add_all([
            StudentTeacher(student_id=student_a.id, teacher_id=teacher_a.id),
            StudentTeacher(student_id=student_b.id, teacher_id=teacher_b.id),
                    Transaction(
                        seat_id=seat_a.id,
                        class_id=class_a.class_id,
                        user_id=user_a.id,
                        join_code="PAYA01",
                        amount=Decimal("111.11"),
                        account_type="checking",
                        status=TransactionStatus.PENDING,
                        type="deposit",
                        description="Teacher A balance",
                    ),
                    Transaction(
                        seat_id=seat_b.id,
                        class_id=class_b.class_id,
                        user_id=user_a.id,
                        join_code="PAYB01",
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
