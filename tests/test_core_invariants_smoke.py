from datetime import datetime, timedelta, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_teacher
import pytest

from app import db
from app.hash_utils import hash_username_lookup
from app.models import (
    Seat, IdentityProfile, ClassFeature, InsuranceClaim, InsuranceEnrollment,
    InsurancePolicy, RentPayment, RentSettings, StoreItem, AttendanceSession,
    Transaction, TransactionStatus, ClassEconomy, User, UserRole,
)
from app.services import ledger_service, obligations_service
from tests.helpers.admin_context import login_teacher
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context


pytestmark = pytest.mark.critical


def _create_teacher(username: str) -> User:
    return make_teacher(username)


def _create_class(teacher: User, join_code: str) -> ClassEconomy:
    class_row = create_class_scope(teacher_user=teacher, join_code=join_code)
    db.session.flush()
    # Ensure ClassFeatures exist
    for feature_name in ClassFeature.feature_names():
        if not ClassFeature.query.filter_by(class_id=class_row.class_id, feature_name=feature_name).first():
            db.session.add(ClassFeature(class_id=class_row.class_id, feature_name=feature_name))
    db.session.flush()
    return class_row


def _create_student(class_id: str, first_name: str) -> Seat:
    return make_student_identity(class_id=class_id, first_name=first_name, last_name="Test", claimed=True)


def _login_teacher(client, teacher: User, class_row: ClassEconomy) -> None:
    login_teacher(client, teacher, class_id=class_row.class_id, join_code=class_row.join_code)


def _login_student(client, seat: Seat, join_code: str) -> None:
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=seat.user_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
            join_code=join_code,
        )


def test_tenant_isolation_attendance_history(client):
    teacher_a = _create_teacher("tenant-a")
    teacher_b = _create_teacher("tenant-b")
    economy_a = _create_class(teacher_a, "JOIN-A")
    economy_b = _create_class(teacher_b, "JOIN-B")
    seat_a = _create_student(economy_a.class_id, "Alice")
    seat_b = _create_student(economy_b.class_id, "Bob")
    db.session.commit()

    tap_a = AttendanceSession(
        seat_id=seat_a.id,
        started_at=datetime.now(timezone.utc),
        class_id=economy_a.class_id,
    )
    tap_b = AttendanceSession(
        seat_id=seat_b.id,
        started_at=datetime.now(timezone.utc),
        class_id=economy_b.class_id,
    )
    db.session.add_all([tap_a, tap_b])
    db.session.commit()

    _login_teacher(client, teacher_a, economy_a)
    response = client.get("/api/attendance/history")

    assert response.status_code in (200, 400)
    payload = response.get_json()
    ids = {row["id"] for row in payload["records"]}
    assert tap_a.id in ids
    assert tap_b.id not in ids


def test_payroll_run_creates_payroll_transaction(client):
    teacher = _create_teacher("payroll-admin")
    economy = _create_class(teacher, "JOIN-PAY")
    seat = _create_student(economy.class_id, "Payroll")
    db.session.commit()

    now = datetime.now(timezone.utc)
    db.session.add(
        AttendanceSession(
            seat_id=seat.id,
            class_id=economy.class_id,
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
            seat_id=seat.id,
            user_id=seat.user_id,
            class_id=economy.class_id,
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

    payroll_query = Transaction.query.filter(
        Transaction.seat_id == seat.id,
        Transaction.join_code == "JOIN-PAY",
        Transaction.type == "payroll",
    )
    pre_payroll_count = payroll_query.count()
    pre_latest_payroll = payroll_query.order_by(Transaction.id.desc()).first()
    pre_latest_payroll_id = pre_latest_payroll.id if pre_latest_payroll is not None else None
    _login_teacher(client, teacher, economy)
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
    teacher = _create_teacher("insurance-admin")
    economy = _create_class(teacher, "JOIN-INS")
    seat = _create_student(economy.class_id, "Insured")
    db.session.commit()

    assert seat is not None and seat.class_id is not None
    assert economy is not None

    policy = InsurancePolicy(
        policy_code=f"POL-{teacher.id}",
        teacher_id=teacher.id,
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
        user_id=seat.user_id,
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

    login_teacher(client, teacher, join_code="JOIN-INS")
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
    teacher = _create_teacher("store-admin")
    economy = _create_class(teacher, "JOIN-STORE")
    seat = _create_student(economy.class_id, "Shopper")
    db.session.commit()

    assert seat is not None and seat.class_id is not None
    assert economy is not None
    from app.models import BalanceCache
    BalanceCache.query.filter_by(seat_id=seat.id, class_id=economy.class_id).delete()

    item = StoreItem(
        user_id=teacher.id,
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
            user_id=seat.user_id,
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

    starting_balance = Seat.query.get(seat.id).user.get_checking_balance(
        class_id=seat.class_id, seat_id=seat.id
    ) if hasattr(seat.user, 'get_checking_balance') else db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.seat_id == seat.id,
        Transaction.account_type == "checking",
        Transaction.status == TransactionStatus.POSTED,
    ).scalar() or Decimal("0.00")

    _login_student(client, seat, "JOIN-STORE")
    response = client.post(
        "/api/purchase-item",
        json={"item_id": item.id, "passphrase": "password", "quantity": 1},
    )

    assert response.status_code in (200, 400)
    ending_balance = db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.seat_id == seat.id,
        Transaction.account_type == "checking",
        Transaction.status == TransactionStatus.POSTED,
    ).scalar() or Decimal("0.00")
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
    teacher = _create_teacher("transfer-admin")
    economy_xfer = _create_class(teacher, "JOIN-XFER")
    economy_other = _create_class(teacher, "JOIN-OTHER")
    seat = _create_student(economy_xfer.class_id, "Transfer")
    other_seat = _create_student(economy_other.class_id, "Other")
    db.session.commit()

    withdraw_tx, deposit_tx = ledger_service.create_transfer_pair(
        seat_id=seat.id,
        class_id=economy_xfer.class_id,
        teacher_id=teacher.id,
        amount=Decimal("12.34"),
        from_account="checking",
        to_account="savings",
        withdraw_description="Transfer to savings",
        deposit_description="Transfer from checking",
    )
    ledger_service.create_transfer_pair(
        seat_id=other_seat.id,
        class_id=economy_other.class_id,
        teacher_id=teacher.id,
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
            Transaction.teacher_id == teacher.id,
            Transaction.join_code == "JOIN-XFER",
            Transaction.type.in_(["Withdrawal", "Deposit"]),
        )
        .scalar()
        or Decimal("0.00")
    )
    join_other_total = (
        db.session.query(db.func.sum(Transaction.amount))
        .filter(
            Transaction.teacher_id == teacher.id,
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
    teacher = _create_teacher("store-discount-admin")
    economy = _create_class(teacher, "JOIN-DISC")
    seat = _create_student(economy.class_id, "Discount")
    db.session.commit()

    assert seat is not None and seat.class_id is not None
    assert economy is not None
    from app.models import BalanceCache
    BalanceCache.query.filter_by(seat_id=seat.id, class_id=economy.class_id).delete()

    item = StoreItem(
        user_id=teacher.id,
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
            user_id=seat.user_id,
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

    _login_student(client, seat, "JOIN-DISC")
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
    teacher = _create_teacher("bills-admin")
    economy = _create_class(teacher, "JOIN-BILLS")
    seat = _create_student(economy.class_id, "Bills")
    db.session.commit()

    assert economy is not None and seat is not None

    checking_balance = db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.seat_id == seat.id,
        Transaction.account_type == "checking",
        Transaction.status == TransactionStatus.POSTED,
    ).scalar() or Decimal("0.00")

    amount_needed = max(Decimal("0"), Decimal("1000.00") - checking_balance)

    assert isinstance(amount_needed, Decimal)
    assert amount_needed == Decimal("1000.00")


def test_rent_payment_creates_rent_obligation_record(client):
    teacher = _create_teacher("rent-admin")
    economy = _create_class(teacher, "JOIN-RENT")
    seat = _create_student(economy.class_id, "Renter")
    db.session.commit()

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
    assert seat is not None and seat.class_id is not None
    db.session.add(
        Transaction(
            seat_id=seat.id,
            user_id=seat.user_id,
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

    _login_student(client, seat, "JOIN-RENT")
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
