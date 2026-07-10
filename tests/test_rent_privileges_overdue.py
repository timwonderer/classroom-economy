from datetime import datetime, timezone, timedelta
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin
from tests.helpers.class_scope import make_student_identity, create_class_scope
from app import db
from app.models import (
    User,
    Seat,
    RentSettings,
    RentItem,
    RentPayment,
    StoreItem,
    Transaction,
)
from app.routes.student import _calculate_rent_coverage_due_date
from tests.helpers.canonical_session import set_canonical_context


def _ensure_class_scope(teacher: User, student, join_code: str) -> "ClassEconomy":
    from app.models import ClassEconomy
    economy = ClassEconomy.query.filter_by(join_code=join_code).first()
    if not economy:
        economy = create_class_scope(teacher_user=teacher, join_code=join_code)
        db.session.flush()
    return economy


def test_overdue_rent_payment_restores_privileges(client):
    teacher = make_admin("rent_teacher_overdue", "secret123")
    db.session.flush()
    db.session.commit()

    join_code = "JOINA"
    economy = _ensure_class_scope(teacher, None, join_code)
    db.session.flush()
    student = make_student_identity(class_id=economy.class_id, first_name="Rent", last_name="P", claimed=True)
    db.session.commit()
    seat = Seat.query.filter_by(user_id=student.user_id, class_id=economy.class_id, role="student").first()
    assert seat is not None

    now = datetime.now(timezone.utc)
    rent_settings = RentSettings(
        class_id=economy.class_id,
        rent_amount=Decimal("50.00"),
        first_rent_due_date=now - timedelta(days=5),
        grace_period_days=3,
        bill_preview_enabled=True,
        bill_preview_days=10,
    )
    db.session.add(rent_settings)
    db.session.commit()

    store_item = StoreItem(
        user_id=teacher.id,
        name="Desk Privilege",
        description="Desk access",
        price=Decimal("5.00"),
        item_type="delayed",
        is_active=True,
    )
    db.session.add(store_item)
    db.session.commit()

    rent_item = RentItem(
        rent_setting_id=rent_settings.id,
        name="Desk Privilege",
        description="Desk access",
        rent_item_type="privilege",
        is_available_in_store=True,
        store_price=Decimal("5.00"),
        store_item_id=store_item.id,
        purchase_duration="per_period",
    )
    db.session.add(rent_item)
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
        user_id=student.user_id,
        class_id=seat.class_id,
        seat_id=seat.id,
        role="student",
    )
        sess["login_time"] = now.isoformat()
        sess["current_join_code"] = join_code

    response = client.get("/student/shop")
    assert response.status_code == 200
    assert b"Included in your rent!" not in response.data

    coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)
    assert coverage_due_date is not None

    payment_date = now
    grace_for_coverage = coverage_due_date + timedelta(days=rent_settings.grace_period_days)
    late_fee_applies = now > grace_for_coverage
    required_amount = rent_settings.rent_amount + (rent_settings.late_fee if late_fee_applies else Decimal("0.00"))
    payment = RentPayment(
        user_id=student.user_id,
        seat_id=seat.id,
        period="A",
        amount_paid=required_amount,
        period_month=now.month,
        period_year=now.year,
        payment_date=payment_date,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        was_late=True,
        late_fee_charged=rent_settings.late_fee if late_fee_applies else Decimal("0.00"),
    )
    transaction = Transaction(
        user_id=student.user_id,
        seat_id=seat.id,
        amount=-required_amount,
        account_type="checking",
        type="Rent Payment",
        description="Overdue rent payment",
        timestamp=payment_date,
    )
    db.session.add_all([payment, transaction])
    db.session.commit()

    response = client.get("/student/shop")
    assert response.status_code == 200
    assert b"Included in your rent!" in response.data


def test_voided_payment_does_not_restore_privileges(client):
    teacher = make_admin("rent_teacher_voided", "secret123")
    db.session.flush()
    db.session.commit()

    join_code = "JOINV"
    economy = _ensure_class_scope(teacher, None, join_code)
    db.session.flush()
    student = make_student_identity(class_id=economy.class_id, first_name="Void", last_name="P", claimed=True)
    db.session.commit()
    seat = Seat.query.filter_by(user_id=student.user_id, class_id=economy.class_id, role="student").first()
    assert seat is not None

    now = datetime.now(timezone.utc)
    rent_settings = RentSettings(
        class_id=economy.class_id,
        rent_amount=Decimal("50.00"),
        first_rent_due_date=now - timedelta(days=5),
        grace_period_days=3,
        bill_preview_enabled=True,
        bill_preview_days=10,
    )
    db.session.add(rent_settings)
    db.session.commit()

    store_item = StoreItem(
        user_id=teacher.id,
        name="Desk Privilege",
        description="Desk access",
        price=Decimal("5.00"),
        item_type="delayed",
        is_active=True,
    )
    db.session.add(store_item)
    db.session.commit()

    rent_item = RentItem(
        rent_setting_id=rent_settings.id,
        name="Desk Privilege",
        description="Desk access",
        rent_item_type="privilege",
        is_available_in_store=True,
        store_price=Decimal("5.00"),
        store_item_id=store_item.id,
        purchase_duration="per_period",
    )
    db.session.add(rent_item)
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student.user_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )
        sess["login_time"] = now.isoformat()
        sess["current_join_code"] = join_code

    coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)
    assert coverage_due_date is not None

    payment_date = now
    grace_for_coverage = coverage_due_date + timedelta(days=rent_settings.grace_period_days)
    late_fee_applies = now > grace_for_coverage
    required_amount = rent_settings.rent_amount + (rent_settings.late_fee if late_fee_applies else Decimal("0.00"))

    payment = RentPayment(
        user_id=student.user_id,
        seat_id=seat.id,
        period="A",
        amount_paid=required_amount,
        period_month=now.month,
        period_year=now.year,
        payment_date=payment_date,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        was_late=True,
        late_fee_charged=rent_settings.late_fee if late_fee_applies else Decimal("0.00"),
    )
    voided_tx = Transaction(
        user_id=student.user_id,
        seat_id=seat.id,
        amount=-required_amount,
        account_type="checking",
        type="Rent Payment",
        description="Voided rent payment",
        timestamp=payment_date,
        is_void=True,
    )
    db.session.add_all([payment, voided_tx])
    db.session.commit()

    response = client.get("/student/shop")
    assert response.status_code == 200
    assert b"Included in your rent!" not in response.data

    valid_tx = Transaction(
        user_id=student.user_id,
        seat_id=seat.id,
        amount=-required_amount,
        account_type="checking",
        type="Rent Payment",
        description="Valid rent payment",
        timestamp=payment_date + timedelta(seconds=10),
    )
    valid_payment = RentPayment(
        user_id=student.user_id,
        seat_id=seat.id,
        period="A",
        amount_paid=required_amount,
        period_month=now.month,
        period_year=now.year,
        payment_date=payment_date + timedelta(seconds=10),
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        was_late=True,
        late_fee_charged=rent_settings.late_fee if late_fee_applies else Decimal("0.00"),
    )
    db.session.add_all([valid_tx, valid_payment])
    db.session.commit()

    response = client.get("/student/shop")
    assert response.status_code == 200
    assert b"Included in your rent!" in response.data


def test_overdue_rent_payment_with_timestamp_drift_restores_privileges(client):
    """A modest transaction/payment timestamp drift should still count as valid payment."""
    teacher = make_admin("rent_teacher_drift", "secret123")
    db.session.flush()
    db.session.commit()

    join_code = "JOIND"
    economy = _ensure_class_scope(teacher, None, join_code)
    db.session.flush()
    student = make_student_identity(class_id=economy.class_id, first_name="Drift", last_name="P", claimed=True)
    db.session.commit()
    seat = Seat.query.filter_by(user_id=student.user_id, class_id=economy.class_id, role="student").first()
    assert seat is not None

    now = datetime.now(timezone.utc)
    rent_settings = RentSettings(
        class_id=economy.class_id,
        rent_amount=Decimal("50.00"),
        first_rent_due_date=now - timedelta(days=5),
        grace_period_days=3,
        bill_preview_enabled=True,
        bill_preview_days=10,
    )
    db.session.add(rent_settings)
    db.session.commit()

    store_item = StoreItem(
        user_id=teacher.id,
        name="Desk Privilege Drift",
        description="Desk access",
        price=Decimal("5.00"),
        item_type="delayed",
        is_active=True,
    )
    db.session.add(store_item)
    db.session.commit()

    db.session.add(RentItem(
        rent_setting_id=rent_settings.id,
        name="Desk Privilege Drift",
        description="Desk access",
        rent_item_type="privilege",
        is_available_in_store=True,
        store_price=Decimal("5.00"),
        store_item_id=store_item.id,
        purchase_duration="per_period",
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student.user_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )
        sess["login_time"] = now.isoformat()
        sess["current_join_code"] = join_code

    coverage_due_date = _calculate_rent_coverage_due_date(rent_settings, now)
    assert coverage_due_date is not None
    grace_for_coverage = coverage_due_date + timedelta(days=rent_settings.grace_period_days)
    late_fee_applies = now > grace_for_coverage
    required_amount = rent_settings.rent_amount + (rent_settings.late_fee if late_fee_applies else Decimal("0.00"))

    payment_date = now
    txn_timestamp = now + timedelta(seconds=45)  # outside old 5s window; inside new tolerance
    db.session.add(RentPayment(
        user_id=student.user_id,
        seat_id=seat.id,
        period="A",
        amount_paid=required_amount,
        period_month=now.month,
        period_year=now.year,
        payment_date=payment_date,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        was_late=True,
        late_fee_charged=rent_settings.late_fee if late_fee_applies else Decimal("0.00"),
    ))
    db.session.add(Transaction(
        user_id=student.user_id,
        seat_id=seat.id,
        amount=-required_amount,
        account_type="checking",
        type="Rent Payment",
        description="Overdue rent payment drifted timestamp",
        timestamp=txn_timestamp,
    ))
    db.session.commit()

    response = client.get("/student/shop")
    assert response.status_code == 200
    assert b"Included in your rent!" in response.data
