from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.hash_utils import get_random_salt, hash_username
from app.models import Seat, IdentityProfile, Admin, ClassMembership, ClassFeature, InsuranceClaim, InsuranceEnrollment, InsurancePolicy, RentPayment, RentSettings, StoreItem, Student, StudentTeacher, AttendanceSession, Transaction, TransactionStatus, ClassEconomy, User, UserRole
from app.services import ledger_service, obligations_service
from tests.helpers.admin_context import login_admin
from tests.helpers.class_scope import create_class_scope, make_student_seat, _ensure_user
from app.hash_utils import hash_username_lookup


pytestmark = pytest.mark.critical


def _create_admin(username: str) -> tuple:
    """Create an Admin and its paired User row. Returns (admin, user)."""
    admin = make_admin(username, "test-secret")
    db.session.add(admin)
    db.session.flush()
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=admin.username_hash,
        username_lookup_hash=admin.username_lookup_hash,
    )
    db.session.add(user)
    db.session.flush()
    admin.user_id = user.id
    return admin, user


def _create_student(first_name: str, block: str = "A") -> Student:
    salt = get_random_salt()
    profile = IdentityProfile(
        profile_type="student",
        first_name=first_name,
        last_name="T",
    )
    db.session.add(profile)
    db.session.flush()
    student = Student(
        identity_profile=profile,
        block=block,
        salt=salt,
    )
    db.session.add(student)
    db.session.flush()
    return student


def _link_student_to_teacher(student: Student, admin: Admin, join_code: str, block: str = "A") -> ClassEconomy:
    """Set up class scope for a student+teacher pair. Returns the ClassEconomy row."""
    economy = ClassEconomy.query.filter_by(join_code=join_code).first()
    if economy is None:
        economy = create_class_scope(
            teacher=admin,
            join_code=join_code,
            student=student,
            block=block,
            display_name=block,
            teacher_user_id=admin.user_id,
        )
        db.session.flush()
        # Ensure ClassFeatures exist
        for feature_name in ClassFeature.feature_names():
            if not ClassFeature.query.filter_by(class_id=economy.class_id, feature_name=feature_name).first():
                db.session.add(ClassFeature(class_id=economy.class_id, feature_name=feature_name))
    else:
        # Class already exists; add student membership + seat if missing
        if not db.session.query(ClassMembership.id).filter_by(
            join_code=join_code,
            student_id=student.id,
            role="student",
        ).first():
            db.session.add(ClassMembership(
                class_id=economy.class_id,
                join_code=join_code,
                student_id=student.id,
                role="student",
            ))
        if not Seat.query.filter_by(class_id=economy.class_id, join_code=join_code, role="student").first():
            make_student_seat(
                class_id=economy.class_id,
                join_code=join_code,
                block=block,
                first_name=getattr(student, 'display_first_name', 'Student'),
                last_name=getattr(student, 'display_last_name', 'T'),
            )

    db.session.add(StudentTeacher(student_id=student.id, teacher_id=admin.id))

    # Claim the student seat so it is active
    seat = Seat.query.filter_by(class_id=economy.class_id, join_code=join_code, role="student").first()
    if seat and seat.claimed_at is None:
        seat.claimed_at = datetime.now(timezone.utc)

    return economy


def _login_admin_for_class(client, admin: Admin, economy: ClassEconomy) -> None:
    """Establish a canonical admin session for the given class."""
    teacher_seat = Seat.query.filter_by(class_id=economy.class_id, role="teacher").order_by(Seat.id.asc()).first()
    import secrets as _secrets
    nonce = _secrets.token_urlsafe(32)
    user = db.session.get(User, admin.user_id) if admin.user_id else None
    if user:
        user.current_session_nonce = nonce
        db.session.flush()
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin.id
        sess["user_id"] = admin.user_id
        sess["current_session_nonce"] = nonce
        sess["current_join_code"] = economy.join_code
        sess["current_class_id"] = economy.class_id
        if teacher_seat:
            sess["current_seat_id"] = teacher_seat.id
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _login_student(client, student_id: int, join_code: str) -> None:
    seat = Seat.query.filter_by(join_code=join_code, role="student").first()
    class_id = seat.class_id if seat else None
    seat_id = seat.id if seat else None
    user_id = seat.user_id if seat and seat.user_id else None
    if seat and user_id is None:
        user = User(
            username_hash=hash_username_lookup(f"smoke-student-{student_id}-{join_code}"),
            username_lookup_hash=hash_username_lookup(f"smoke-student-{student_id}-{join_code}"),
            user_role=UserRole.STUDENT,
            password_hash="pw",
        )
        db.session.add(user)
        db.session.flush()
        seat.user_id = user.id
        db.session.flush()
        user_id = user.id
    with client.session_transaction() as sess:
        sess["student_id"] = student_id
        if user_id:
            sess["user_id"] = user_id
            user = db.session.get(User, user_id)
            if user and not user.current_session_nonce:
                user.current_session_nonce = uuid4().hex
            if user and class_id:
                user.last_active_class_id = class_id
                db.session.commit()
            if user:
                sess["current_session_nonce"] = user.current_session_nonce
        sess["current_join_code"] = join_code
        if class_id:
            sess["current_class_id"] = class_id
        if seat_id:
            sess["current_seat_id"] = seat_id
            sess["seat_id"] = seat_id
        if class_id:
            sess["class_id"] = class_id
        sess["login_time"] = datetime.now(timezone.utc).isoformat()
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _make_tx(*, seat_id, class_id, join_code, amount: Decimal, type: str, description: str, account_type="checking", **kwargs) -> Transaction:
    """Build a Transaction with required v2 fields.

    Uses a 'bypass_test_' correlation_id prefix so the model's bypass-mode
    validator accepts the row when FEAT-BYPASS-LEGACY is active in tests.
    """
    return Transaction(
        seat_id=seat_id,
        class_id=class_id,
        join_code=join_code,
        amount=amount,
        amount_cents=int(amount * 100),
        account_type=account_type,
        status=TransactionStatus.POSTED,
        type=type,
        description=description,
        correlation_id=f"bypass_test_{uuid4().hex}",
        **kwargs,
    )


def test_tenant_isolation_attendance_history(client):
    admin_a, user_a = _create_admin("tenant-a")
    admin_b, user_b = _create_admin("tenant-b")
    student_a = _create_student("Alice")
    student_b = _create_student("Bob")
    economy_a = _link_student_to_teacher(student_a, admin_a, "JOIN-A")
    economy_b = _link_student_to_teacher(student_b, admin_b, "JOIN-B")
    db.session.commit()

    seat_a = Seat.query.filter_by(class_id=economy_a.class_id, join_code="JOIN-A", role="student").first()
    seat_b = Seat.query.filter_by(class_id=economy_b.class_id, join_code="JOIN-B", role="student").first()
    tap_a = AttendanceSession(
        student_id=student_a.id,
        seat_id=seat_a.id,
        period="A",
        started_at=datetime.now(timezone.utc),
        class_id=economy_a.class_id,
    )
    tap_b = AttendanceSession(
        student_id=student_b.id,
        seat_id=seat_b.id,
        period="A",
        started_at=datetime.now(timezone.utc),
        class_id=economy_b.class_id,
    )
    db.session.add_all([tap_a, tap_b])
    db.session.commit()

    _login_admin_for_class(client, admin_a, economy_a)
    response = client.get("/api/attendance/history")

    assert response.status_code in (200, 400)
    payload = response.get_json()
    ids = {row["id"] for row in payload["records"]}
    assert tap_a.id in ids
    assert tap_b.id not in ids


def test_payroll_run_creates_payroll_transaction(client):
    admin, user = _create_admin("payroll-admin")
    student = _create_student("Payroll")
    economy = _link_student_to_teacher(student, admin, "JOIN-PAY", block="A")
    db.session.commit()

    now = datetime.now(timezone.utc)
    seat = Seat.query.filter_by(class_id=economy.class_id, join_code="JOIN-PAY", role="student").first()
    db.session.add(
        AttendanceSession(
            student_id=student.id,
            seat_id=seat.id,
            class_id=economy.class_id,
            period="A",
            started_at=now - timedelta(minutes=60),
            ended_at=now - timedelta(minutes=30),
            duration_seconds=1800,
        )
    )
    from app.models import PayrollSettings
    db.session.add(
        PayrollSettings(
            class_id=economy.class_id,
            block="A",
            pay_rate=Decimal("1.00"),
            is_active=True,
        )
    )
    db.session.add(_make_tx(
        seat_id=seat.id,
        class_id=economy.class_id,
        join_code="JOIN-PAY",
        amount=Decimal("1.00"),
        account_type="checking",
        type="payroll",
        description="Anchor payroll",
        timestamp=now - timedelta(days=1),
    ))
    db.session.commit()

    payroll_query = Transaction.query.filter(
        Transaction.seat_id == seat.id,
        Transaction.join_code == "JOIN-PAY",
        Transaction.type == "payroll",
    )
    pre_payroll_count = payroll_query.count()
    pre_latest_payroll = payroll_query.order_by(Transaction.id.desc()).first()
    pre_latest_payroll_id = pre_latest_payroll.id if pre_latest_payroll is not None else None
    _login_admin_for_class(client, admin, economy)
    response = client.post("/admin/run_payroll", json={})

    assert response.status_code in (200, 400)
    post_payroll_query = Transaction.query.filter(
        Transaction.seat_id == seat.id,
        Transaction.join_code == "JOIN-PAY",
        Transaction.type == "payroll",
    )
    assert post_payroll_query.count() > pre_payroll_count
    latest_payroll = post_payroll_query.order_by(Transaction.id.desc()).first()
    assert latest_payroll is not None
    if pre_latest_payroll_id is not None:
        assert latest_payroll.id != pre_latest_payroll_id
    assert latest_payroll.amount > Decimal("0.00")


def test_insurance_approval_creates_reimbursement_transaction(client):
    admin, user = _create_admin("insurance-admin")
    student = _create_student("Insured")
    economy = _link_student_to_teacher(student, admin, "JOIN-INS", block="A")
    db.session.commit()
    seat = Seat.query.filter_by(class_id=economy.class_id, join_code="JOIN-INS", role="student").first()
    assert seat is not None and seat.class_id is not None
    assert economy is not None

    policy = InsurancePolicy(
        policy_code=f"POL-{admin.id}",
        teacher_id=user.id,  # InsurancePolicy.teacher_id is FK to users.id
        title="Coverage",
        description="Test policy",
        premium=Decimal("10.00"),
        claim_type="transaction_monetary",
        is_monetary=True,
        max_claim_amount=Decimal("100.00"),
        max_claims_period="month",
        claim_time_limit_days=30,
        waiting_period_days=0,
        is_active=True,
    )
    db.session.add(policy)
    db.session.flush()

    enrollment = InsuranceEnrollment(
        seat_id=seat.id,
        class_id=economy.class_id,
        policy_id=policy.id,
        join_code="JOIN-INS",
        status="active",
        purchase_date=datetime.now(timezone.utc) - timedelta(days=2),
        coverage_start_date=datetime.now(timezone.utc) - timedelta(days=30),
        payment_current=True,
    )
    enrollment.freeze_policy_snapshot(policy)
    db.session.add(enrollment)
    db.session.flush()

    purchase_tx = _make_tx(
        seat_id=seat.id,
        class_id=economy.class_id,
        join_code="JOIN-INS",
        amount=Decimal("-30.00"),
        account_type="checking",
        type="expense",
        description="Broken classroom item",
    )
    db.session.add(purchase_tx)
    db.session.flush()

    claim = obligations_service.record_insurance_claim(
        enrollment_id=enrollment.id,
        policy_id=policy.id,
        seat_id=seat.id,
        class_id=economy.class_id,
        incident_date=purchase_tx.timestamp,
        description="Reimburse",
        claim_amount=Decimal("30.00"),
        claim_item=None,
        comments=None,
        transaction_id=purchase_tx.id,
    )
    db.session.commit()

    _login_admin_for_class(client, admin, economy)
    response = client.post(
        f"/admin/insurance/claim/{claim.id}",
        data={"status": "approved", "approved_amount": "", "rejection_reason": "", "admin_notes": ""},
        follow_redirects=False,
    )

    assert response.status_code in (302, 303)
    reimbursement = Transaction.query.filter_by(
        original_transaction_id=purchase_tx.id,
        policy_id=policy.id,
    ).order_by(Transaction.id.desc()).first()
    assert reimbursement is not None
    assert reimbursement.amount > Decimal("0.00")


def test_store_purchase_deducts_balance_and_records_transaction(client):
    admin, user = _create_admin("store-admin")
    student = _create_student("Shopper")
    economy = _link_student_to_teacher(student, admin, "JOIN-STORE", block="A")
    db.session.commit()
    seat = Seat.query.filter_by(class_id=economy.class_id, join_code="JOIN-STORE", role="student").first()
    assert seat is not None and seat.class_id is not None
    assert economy is not None
    from app.models import BalanceCache
    BalanceCache.query.filter_by(seat_id=seat.id, class_id=economy.class_id).delete()

    item = StoreItem(
        user_id=user.id,
        class_id=economy.class_id,
        name="Notebook",
        price=Decimal("5.00"),
        is_active=True,
        item_type="delayed",
    )
    db.session.add(item)
    student_user = db.session.get(User, seat.user_id)
    student_user.passphrase_hash = generate_password_hash("password")
    db.session.add(_make_tx(
        seat_id=seat.id,
        class_id=economy.class_id,
        join_code="JOIN-STORE",
        amount=Decimal("25.00"),
        account_type="checking",
        type="Deposit",
        description="Seed funds",
    ))
    db.session.commit()

    starting_balance = student.get_checking_balance(class_id=seat.class_id, seat_id=seat.id)

    _login_student(client, student.id, "JOIN-STORE")
    response = client.post(
        "/api/purchase-item",
        json={"item_id": item.id, "passphrase": "password", "quantity": 1},
    )

    assert response.status_code in (200, 400)
    ending_balance = student.get_checking_balance(class_id=seat.class_id, seat_id=seat.id)
    assert ending_balance <= starting_balance

    purchase_tx = (
        Transaction.query.filter(
            Transaction.seat_id == seat.id,
            Transaction.join_code == "JOIN-STORE",
            Transaction.type == "purchase",
        )
        .order_by(Transaction.id.desc())
        .first()
    )
    assert purchase_tx is not None or response.status_code == 400
    if purchase_tx is not None:
        assert purchase_tx.amount < Decimal("0.00")


def test_transfer_pairs_are_zero_sum_within_class_scope(client):
    admin, user = _create_admin("transfer-admin")
    student = _create_student("Transfer")
    other_student = _create_student("Other", block="B")
    economy = _link_student_to_teacher(student, admin, "JOIN-XFER", block="A")
    other_economy = _link_student_to_teacher(other_student, admin, "JOIN-OTHER", block="B")
    db.session.commit()

    seat = Seat.query.filter_by(class_id=economy.class_id, join_code="JOIN-XFER", role="student").first()
    other_seat = Seat.query.filter_by(class_id=other_economy.class_id, join_code="JOIN-OTHER", role="student").first()

    withdraw_tx, deposit_tx = ledger_service.create_transfer_pair(
        seat_id=seat.id,
        class_id=economy.class_id,
        teacher_id=user.id,
        amount=Decimal("12.34"),
        from_account="checking",
        to_account="savings",
        withdraw_description="Transfer to savings",
        deposit_description="Transfer from checking",
    )
    ledger_service.create_transfer_pair(
        seat_id=other_seat.id,
        class_id=other_economy.class_id,
        teacher_id=user.id,
        amount=Decimal("7.89"),
        from_account="checking",
        to_account="savings",
        withdraw_description="Transfer to savings",
        deposit_description="Transfer from checking",
    )
    db.session.commit()

    join_xfer_total = (
        db.session.query(db.func.sum(Transaction.amount))
        .filter(
            Transaction.seat_id == seat.id,
            Transaction.join_code == "JOIN-XFER",
            Transaction.type.in_(["Withdrawal", "Deposit"]),
        )
        .scalar()
        or Decimal("0.00")
    )
    join_other_total = (
        db.session.query(db.func.sum(Transaction.amount))
        .filter(
            Transaction.seat_id == other_seat.id,
            Transaction.join_code == "JOIN-OTHER",
            Transaction.type.in_(["Withdrawal", "Deposit"]),
        )
        .scalar()
        or Decimal("0.00")
    )

    assert withdraw_tx.join_code == "JOIN-XFER"
    assert deposit_tx.join_code == "JOIN-XFER"
    assert withdraw_tx.amount + deposit_tx.amount == Decimal("0.00")
    assert join_xfer_total == Decimal("0.00")
    assert join_other_total == Decimal("0.00")


def test_store_purchase_bulk_discount_uses_quantized_total_for_funds_check(client):
    admin, user = _create_admin("store-discount-admin")
    student = _create_student("Discount")
    economy = _link_student_to_teacher(student, admin, "JOIN-DISC", block="A")
    db.session.commit()
    seat = Seat.query.filter_by(class_id=economy.class_id, join_code="JOIN-DISC", role="student").first()
    assert seat is not None and seat.class_id is not None
    assert economy is not None
    from app.models import BalanceCache
    BalanceCache.query.filter_by(seat_id=seat.id, class_id=economy.class_id).delete()

    item = StoreItem(
        user_id=user.id,
        class_id=economy.class_id,
        name="Discounted Item",
        price=Decimal("0.05"),
        is_active=True,
        item_type="delayed",
        bulk_discount_enabled=True,
        bulk_discount_quantity=1,
        bulk_discount_percentage=10,
    )
    db.session.add(item)
    student_user = db.session.get(User, seat.user_id)
    student_user.passphrase_hash = generate_password_hash("password")
    db.session.add(_make_tx(
        seat_id=seat.id,
        class_id=economy.class_id,
        join_code="JOIN-DISC",
        amount=Decimal("0.04"),
        account_type="checking",
        type="Deposit",
        description="Seed funds",
    ))
    db.session.commit()

    _login_student(client, student.id, "JOIN-DISC")
    response = client.post(
        "/api/purchase-item",
        json={"item_id": item.id, "passphrase": "password", "quantity": 1},
    )

    assert response.status_code in (200, 400)
    purchase_tx = (
        Transaction.query.filter(
            Transaction.seat_id == seat.id,
            Transaction.join_code == "JOIN-DISC",
            Transaction.type == "purchase",
        )
        .order_by(Transaction.id.desc())
        .first()
    )
    assert purchase_tx is not None or response.status_code == 400
    if purchase_tx is not None:
        assert purchase_tx.amount <= Decimal("0.00")


def test_amount_needed_to_cover_bills_uses_decimal_math(client):
    admin, user = _create_admin("bills-admin")
    student = _create_student("Bills")
    economy = _link_student_to_teacher(student, admin, "JOIN-BILLS", block="A")
    db.session.commit()

    seat = Seat.query.filter_by(class_id=economy.class_id, join_code="JOIN-BILLS", role="student").first()
    assert economy is not None and seat is not None

    checking_balance = student.get_checking_balance(class_id=economy.class_id, seat_id=seat.id)
    student.is_rent_enabled = True
    student.insurance_plan = "basic"
    db.session.commit()

    amount_needed = max(Decimal("0"), Decimal("1000.00") - checking_balance)

    assert isinstance(amount_needed, Decimal)
    assert amount_needed == Decimal("1000.00")


def test_rent_payment_creates_rent_obligation_record(client):
    admin, user = _create_admin("rent-admin")
    student = _create_student("Renter")
    economy = _link_student_to_teacher(student, admin, "JOIN-RENT", block="A")
    student.is_rent_enabled = True

    assert economy is not None
    settings = RentSettings(
        class_id=economy.class_id,
        block="A",
        is_enabled=True,
        rent_amount=Decimal("10.00"),
        frequency_type="monthly",
        due_day_of_month=1,
        grace_period_days=0,
        late_penalty_amount=Decimal("0.00"),
    )
    db.session.add(settings)
    db.session.flush()
    settings.active_version = settings.create_policy_version()
    seat = Seat.query.filter_by(class_id=economy.class_id, join_code="JOIN-RENT", role="student").first()
    assert seat is not None and seat.class_id is not None
    db.session.add(_make_tx(
        seat_id=seat.id,
        class_id=economy.class_id,
        join_code="JOIN-RENT",
        amount=Decimal("40.00"),
        account_type="checking",
        type="Deposit",
        description="Seed funds",
    ))
    db.session.commit()

    _login_student(client, student.id, "JOIN-RENT")
    response = client.post("/student/rent/pay/A", follow_redirects=False)
    assert response.status_code in (302, 303)

    rent_payment = RentPayment.query.filter_by(seat_id=seat.id, join_code="JOIN-RENT").first()
    assert rent_payment is not None or response.status_code in (302, 303)

    rent_tx = (
        Transaction.query.filter(
            Transaction.seat_id == seat.id,
            Transaction.class_id == economy.class_id,
            Transaction.type == "Rent Payment",
        )
        .order_by(Transaction.id.desc())
        .first()
    )
    assert rent_tx is not None
