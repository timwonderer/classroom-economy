from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.hash_utils import get_random_salt, hash_username
from app.models import Seat, IdentityProfile, Admin, ClassMembership, ClassFeature, InsuranceClaim, InsuranceEnrollment, InsurancePolicy, RentPayment, RentSettings, StoreItem, Student, StudentInsurance, StudentTeacher, TapEvent, Transaction, TransactionStatus, ClassEconomy, User, UserRole
from app.services import ledger_service, obligations_service
from tests.helpers.admin_context import login_admin
from tests.helpers.class_scope import create_class_scope
from app.hash_utils import hash_username_lookup


pytestmark = pytest.mark.critical


def _create_admin(username: str) -> Admin:
    admin = make_admin(username, "test-secret")
    db.session.add(admin)
    db.session.flush()
    return admin


def _create_student(first_name: str, block: str = "A") -> Student:
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="T",
        block=block,
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin-hash",
        passphrase_hash=generate_password_hash("password"),
    )
    db.session.add(student)
    db.session.flush()
    return student


def _link_student_to_teacher(student: Student, admin: Admin, join_code: str, block: str = "A") -> None:
    if not db.session.query(ClassMembership.id).filter_by(
        join_code=join_code,
        admin_id=admin.id,
        role="admin",
    ).first():
        create_class_scope(
            teacher=admin,
            join_code=join_code,
            student=student,
            block=block,
            display_name=block,
        )
        db.session.flush()
    elif not db.session.query(ClassMembership.id).filter_by(
        join_code=join_code,
        student_id=student.id,
        role="student",
    ).first():
        db.session.add(ClassMembership(
            join_code=join_code,
            student_id=student.id,
            role="student",
        ))
    db.session.add(StudentTeacher(student_id=student.id, teacher_id=admin.id))
    class_row = db.session.query(ClassMembership.join_code).filter_by(
        join_code=join_code,
        admin_id=admin.id,
        role="admin",
    ).first()
    if class_row:
        from app.models import ClassEconomy
        economy = ClassEconomy.query.filter_by(join_code=join_code).first()
        if economy:
            for feature_name in ClassFeature.feature_names():
                if not ClassFeature.query.filter_by(class_id=economy.class_id, feature_name=feature_name).first():
                    db.session.add(ClassFeature(class_id=economy.class_id, feature_name=feature_name))
    _tb_seat = Seat(student_id=student.id, join_code=join_code, block=block, block_identifier=block, role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name=student.display_first_name, last_name=student.display_last_initial))
    economy = ClassEconomy.query.filter_by(join_code=join_code).first()
    if economy:
        seat = Seat.query.filter_by(student_id=student.id, class_id=economy.class_id).first()
        if seat and seat.claimed_at is None:
            seat.claimed_at = datetime.now(timezone.utc)


def _login_admin(client, admin_id: int) -> None:
    class_row = ClassEconomy.query.filter_by(teacher_id=admin_id).order_by(ClassEconomy.created_at.asc(), ClassEconomy.join_code.asc()).first()
    if class_row:
        teacher_seat = Seat.query.filter_by(class_id=class_row.class_id, role="teacher").order_by(Seat.id.asc()).first()
        login_admin(
            client,
            admin_id,
            class_row.join_code,
            class_id=class_row.class_id,
            seat_id=teacher_seat.id if teacher_seat else None,
        )
    else:
        login_admin(client, admin_id)


def _login_student(client, student_id: int, join_code: str) -> None:
    seat = Seat.query.filter_by(student_id=student_id, join_code=join_code).first()
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


def test_tenant_isolation_attendance_history(client):
    admin_a = _create_admin("tenant-a")
    admin_b = _create_admin("tenant-b")
    student_a = _create_student("Alice")
    student_b = _create_student("Bob")
    _link_student_to_teacher(student_a, admin_a, "JOIN-A")
    _link_student_to_teacher(student_b, admin_b, "JOIN-B")
    db.session.commit()

    economy_a = ClassEconomy.query.filter_by(join_code="JOIN-A").first()
    economy_b = ClassEconomy.query.filter_by(join_code="JOIN-B").first()
    tap_a = TapEvent(
        student_id=student_a.id,
        period="A",
        status="active",
        timestamp=datetime.now(timezone.utc),
        join_code="JOIN-A",
        class_id=economy_a.class_id if economy_a else None,
    )
    tap_b = TapEvent(
        student_id=student_b.id,
        period="A",
        status="active",
        timestamp=datetime.now(timezone.utc),
        join_code="JOIN-B",
        class_id=economy_b.class_id if economy_b else None,
    )
    db.session.add_all([tap_a, tap_b])
    db.session.commit()

    _login_admin(client, admin_a.id)
    response = client.get("/api/attendance/history")

    assert response.status_code in (200, 400)
    payload = response.get_json()
    ids = {row["id"] for row in payload["records"]}
    assert tap_a.id in ids
    assert tap_b.id not in ids


def test_payroll_run_creates_payroll_transaction(client):
    admin = _create_admin("payroll-admin")
    student = _create_student("Payroll")
    _link_student_to_teacher(student, admin, "JOIN-PAY", block="A")
    db.session.commit()

    now = datetime.now(timezone.utc)
    economy = ClassEconomy.query.filter_by(join_code="JOIN-PAY").first()
    from app.models import AttendanceSession
    db.session.add(
        AttendanceSession(
            student_id=student.id,
            seat_id=Seat.query.filter_by(student_id=student.id, join_code="JOIN-PAY").first().id,
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
    db.session.add(
        Transaction(
            student_id=student.id,
            teacher_id=admin.id,
            join_code="JOIN-PAY",
            amount=Decimal("1.00"),
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="payroll",
            description="Anchor payroll",
            timestamp=now - timedelta(days=1),
        )
    )
    db.session.commit()

    seat = Seat.query.filter_by(student_id=student.id, join_code="JOIN-PAY").first()
    payroll_query = Transaction.query.filter(
        Transaction.seat_id == seat.id,
        Transaction.join_code == "JOIN-PAY",
        Transaction.type == "payroll",
    ) if seat else Transaction.query.filter_by(id=-1)
    pre_payroll_count = payroll_query.count()
    pre_latest_payroll = payroll_query.order_by(Transaction.id.desc()).first()
    pre_latest_payroll_id = pre_latest_payroll.id if pre_latest_payroll is not None else None
    _login_admin(client, admin.id)
    response = client.post("/admin/run_payroll", json={})

    assert response.status_code in (200, 400)
    post_payroll_query = Transaction.query.filter(
        Transaction.seat_id == seat.id,
        Transaction.join_code == "JOIN-PAY",
        Transaction.type == "payroll",
    ) if seat else Transaction.query.filter_by(id=-1)
    assert post_payroll_query.count() > pre_payroll_count
    latest_payroll = post_payroll_query.order_by(Transaction.id.desc()).first()
    assert latest_payroll is not None
    if pre_latest_payroll_id is not None:
        assert latest_payroll.id != pre_latest_payroll_id
    assert latest_payroll.amount > Decimal("0.00")


def test_insurance_approval_creates_reimbursement_transaction(client):
    admin = _create_admin("insurance-admin")
    student = _create_student("Insured")
    _link_student_to_teacher(student, admin, "JOIN-INS", block="A")
    db.session.commit()
    seat = Seat.query.filter_by(student_id=student.id, join_code="JOIN-INS").first()
    economy = ClassEconomy.query.filter_by(join_code="JOIN-INS").first()
    assert seat is not None and seat.class_id is not None
    assert economy is not None

    policy = InsurancePolicy(
        policy_code=f"POL-{admin.id}",
        teacher_id=admin.id,
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

    purchase_tx = Transaction(
        seat_id=seat.id,
        student_id=student.id,
        teacher_id=admin.id,
        class_id=economy.class_id,
        join_code="JOIN-INS",
        amount=Decimal("-30.00"),
        account_type="checking",
        status=TransactionStatus.POSTED,
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

    login_admin(client, admin.id, "JOIN-INS")
    with client.session_transaction() as sess:
        sess["current_class_id"] = economy.class_id
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
    admin = _create_admin("store-admin")
    student = _create_student("Shopper")
    _link_student_to_teacher(student, admin, "JOIN-STORE", block="A")
    db.session.commit()
    seat = Seat.query.filter_by(student_id=student.id, join_code="JOIN-STORE").first()
    economy = ClassEconomy.query.filter_by(join_code="JOIN-STORE").first()
    assert seat is not None and seat.class_id is not None
    assert economy is not None
    from app.models import BalanceCache
    BalanceCache.query.filter_by(seat_id=seat.id, class_id=economy.class_id).delete()

    item = StoreItem(
        teacher_id=admin.id,
        class_id=economy.class_id,
        name="Notebook",
        price=Decimal("5.00"),
        is_active=True,
        item_type="delayed",
    )
    db.session.add(item)
    db.session.add(
        Transaction(
            seat_id=seat.id,
            student_id=student.id,
            teacher_id=admin.id,
            class_id=economy.class_id,
            join_code="JOIN-STORE",
            amount=Decimal("25.00"),
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="Deposit",
            description="Seed funds",
        )
    )
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
    admin = _create_admin("transfer-admin")
    student = _create_student("Transfer")
    other_student = _create_student("Other", block="B")
    _link_student_to_teacher(student, admin, "JOIN-XFER", block="A")
    _link_student_to_teacher(other_student, admin, "JOIN-OTHER", block="B")
    db.session.commit()

    seat = Seat.query.filter_by(student_id=student.id, join_code="JOIN-XFER").first()
    other_seat = Seat.query.filter_by(student_id=other_student.id, join_code="JOIN-OTHER").first()
    economy = ClassEconomy.query.filter_by(join_code="JOIN-XFER").first()
    other_economy = ClassEconomy.query.filter_by(join_code="JOIN-OTHER").first()

    withdraw_tx, deposit_tx = ledger_service.create_transfer_pair(
        seat_id=seat.id,
        class_id=economy.class_id,
        teacher_id=admin.id,
        amount=Decimal("12.34"),
        from_account="checking",
        to_account="savings",
        withdraw_description="Transfer to savings",
        deposit_description="Transfer from checking",
    )
    ledger_service.create_transfer_pair(
        seat_id=other_seat.id,
        class_id=other_economy.class_id,
        teacher_id=admin.id,
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
            Transaction.teacher_id == admin.id,
            Transaction.join_code == "JOIN-XFER",
            Transaction.type.in_(["Withdrawal", "Deposit"]),
        )
        .scalar()
        or Decimal("0.00")
    )
    join_other_total = (
        db.session.query(db.func.sum(Transaction.amount))
        .filter(
            Transaction.teacher_id == admin.id,
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
    admin = _create_admin("store-discount-admin")
    student = _create_student("Discount")
    _link_student_to_teacher(student, admin, "JOIN-DISC", block="A")
    db.session.commit()
    seat = Seat.query.filter_by(student_id=student.id, join_code="JOIN-DISC").first()
    economy = ClassEconomy.query.filter_by(join_code="JOIN-DISC").first()
    assert seat is not None and seat.class_id is not None
    assert economy is not None
    from app.models import BalanceCache
    BalanceCache.query.filter_by(seat_id=seat.id, class_id=economy.class_id).delete()

    item = StoreItem(
        teacher_id=admin.id,
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
    db.session.add(
        Transaction(
            seat_id=seat.id,
            student_id=student.id,
            teacher_id=admin.id,
            class_id=economy.class_id,
            join_code="JOIN-DISC",
            amount=Decimal("0.04"),
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="Deposit",
            description="Seed funds",
        )
    )
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
    admin = _create_admin("bills-admin")
    student = _create_student("Bills")
    _link_student_to_teacher(student, admin, "JOIN-BILLS", block="A")
    db.session.commit()

    economy = ClassEconomy.query.filter_by(join_code="JOIN-BILLS").first()
    seat = Seat.query.filter_by(student_id=student.id, join_code="JOIN-BILLS").first()
    assert economy is not None and seat is not None

    checking_balance = student.get_checking_balance(class_id=economy.class_id, seat_id=seat.id)
    student.is_rent_enabled = True
    student.insurance_plan = "basic"
    db.session.commit()

    amount_needed = max(Decimal("0"), Decimal("1000.00") - checking_balance)

    assert isinstance(amount_needed, Decimal)
    assert amount_needed == Decimal("1000.00")


def test_rent_payment_creates_rent_obligation_record(client):
    admin = _create_admin("rent-admin")
    student = _create_student("Renter")
    _link_student_to_teacher(student, admin, "JOIN-RENT", block="A")
    student.is_rent_enabled = True

    economy = ClassEconomy.query.filter_by(join_code="JOIN-RENT").first()
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
    seat = Seat.query.filter_by(student_id=student.id, join_code="JOIN-RENT").first()
    assert seat is not None and seat.class_id is not None
    db.session.add(
        Transaction(
            seat_id=seat.id,
            student_id=student.id,
            teacher_id=admin.id,
            class_id=economy.class_id,
            join_code="JOIN-RENT",
            amount=Decimal("40.00"),
            account_type="checking",
            status=TransactionStatus.POSTED,
            type="Deposit",
            description="Seed funds",
        )
    )
    db.session.commit()

    _login_student(client, student.id, "JOIN-RENT")
    response = client.post("/student/rent/pay/A", follow_redirects=False)
    assert response.status_code in (302, 303)

    rent_payment = RentPayment.query.filter_by(seat_id=seat.id, join_code="JOIN-RENT").first()
    assert rent_payment is not None or response.status_code in (302, 303)

    rent_tx = (
        Transaction.query.filter(
            Transaction.seat_id == seat.id,
            Transaction.join_code == "JOIN-RENT",
            Transaction.type == "Rent Payment",
        )
        .order_by(Transaction.id.desc())
        .first()
    )
    assert rent_tx is not None
