import pytest
from decimal import Decimal
from app.models import Transaction, StoreItem, StorePurchase, Seat
from app.extensions import db
from app.feats.base import FEATContext
from app.feats.store_purchase_feat import execute_store_purchase
from tests.dom.entitlement.helpers import (
    create_entitlement_store_item,
    login_entitlement_teacher,
    reject_entitlement_redemption,
)
from tests.helpers.classroom_initializer import initialize
from tests.helpers.canonical_classroom import login_student, login_teacher
from app.models import StorePurchase


@pytest.fixture
def teacher_admin(client, app):
    return initialize("chemistry_p1", app)


@pytest.fixture
def student_in_class(client, teacher_admin, app):
    return teacher_admin.students[0].seat


def test_DOM_STORE_001__reject_redemption_leaves_entitlement_available(client, teacher_admin, student_in_class, app):
    """Test that rejecting a redemption does not refund or terminate the entitlement."""
    student = student_in_class
    student_user_id = student.user_id
    student_seat_id = student.id
    class_id = student.class_id
    seat = Seat.query.filter_by(user_id=student_user_id, class_id=class_id, role="student").first()

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"redemption-reject:seed:{class_id}:{student_user_id}"):
        item = create_entitlement_store_item(
            teacher_id=teacher_admin.teacher_user.id,
            class_id=class_id,
            name='Refundable Item',
            price=Decimal('15.00'),
            item_type='delayed',
        )

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"redemption-reject:funds:{class_id}:{student_user_id}"):
        initial_balance = Decimal('100.00')
        tx = Transaction(
            user_id=student_user_id, seat_id=student_seat_id,
            target_seat_id=student_seat_id,
            actor_seat_id=student_seat_id,
            mechanism="self",
            amount=initial_balance,
            account_type='checking',
            type='deposit',
            description='Initial funds'
        )
        db.session.add(tx)
        db.session.flush()

    login_student(client, teacher_admin.students[0])

    with FEATContext("FEAT-STOR-001", idempotency_key=f"redemption-reject:purchase:{class_id}:{student_user_id}"):
        result = execute_store_purchase(
            ctx=type("Ctx", (), {"class_id": class_id})(),
            seat=seat,
            item=item,
            quantity=1,
            total_price=Decimal("15.00"),
            purchase_description=f"Purchase: {item.name}",
            banking_settings=None,
            is_instant_use=False,
        )
        db.session.add(StorePurchase(
            seat_id=seat.id,
            class_id=class_id,
            store_item_id=item.id,
            quantity=1,
            price_at_purchase=Decimal('15.00'),
            total_price=Decimal('15.00'),
            status='purchased',
        ))
        db.session.flush()

    student_item = StorePurchase.query.filter_by(seat_id=seat.id, store_item_id=item.id).first()
    assert student_item is not None
    assert student_item.status == 'purchased'

    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': teacher_admin.students[0].passphrase,
        'details': 'Please refund me'
    })
    assert use_resp.status_code == 200
    assert use_resp.json['status'] == 'success'

    db.session.refresh(student_item)
    assert student_item.status == 'processing'

    login_teacher(client, teacher_admin)

    resp = reject_entitlement_redemption(client, student_item_id=student_item.id)
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

    item_check = db.session.get(StorePurchase, student_item.id)
    assert item_check is not None
    assert item_check.status == 'processing'

    refund_tx = Transaction.query.filter_by(
        seat_id=seat.id,
        type='refund',
        amount=Decimal('15.00')
    ).first()
    assert refund_tx is None


def test_DOM_STORE_001__reject_redemption_leaves_multi_quantity_entitlement_available(client, teacher_admin, student_in_class, app):
    """Ensure a rejected redemption leaves the entitlement available."""
    student = student_in_class
    student_user_id = student.user_id
    student_seat_id = student.id
    class_id = student.class_id
    seat = Seat.query.filter_by(user_id=student_user_id, class_id=class_id, role="student").first()

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"redemption-reject:seed-bulk:{class_id}:{student_user_id}"):
        item = create_entitlement_store_item(
            teacher_id=teacher_admin.teacher_user.id,
            class_id=class_id,
            name='Bulk Item',
            price=Decimal('10.00'),
            item_type='delayed',
        )

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"redemption-reject:funds-bulk:{class_id}:{student_user_id}"):
        initial_balance = Decimal('100.00')
        db.session.add(Transaction(
            user_id=student_user_id, seat_id=student_seat_id,
            target_seat_id=student_seat_id,
            actor_seat_id=student_seat_id,
            mechanism="self",
            amount=initial_balance,
            account_type='checking',
            type='deposit',
            description='Initial funds'
        ))
        db.session.flush()

    login_student(client, teacher_admin.students[0])

    with FEATContext("FEAT-STOR-001", idempotency_key=f"redemption-reject:purchase-bulk:{class_id}:{student_user_id}"):
        result = execute_store_purchase(
            ctx=type("Ctx", (), {"class_id": class_id})(),
            seat=seat,
            item=item,
            quantity=3,
            total_price=Decimal("30.00"),
            purchase_description=f"Purchase: {item.name} (x3)",
            banking_settings=None,
            is_instant_use=False,
        )
        db.session.add(StorePurchase(
            seat_id=seat.id,
            class_id=class_id,
            store_item_id=item.id,
            quantity=3,
            price_at_purchase=Decimal('10.00'),
            total_price=Decimal('30.00'),
            status='purchased',
        ))
        db.session.flush()

    student_item = StorePurchase.query.filter_by(seat_id=seat.id, store_item_id=item.id).first()
    assert student_item is not None

    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': teacher_admin.students[0].passphrase,
        'details': 'Use one from bulk'
    })
    assert use_resp.status_code == 200
    assert use_resp.json['status'] == 'success'

    db.session.refresh(student_item)
    assert student_item.status == 'processing'

    login_teacher(client, teacher_admin)

    resp = reject_entitlement_redemption(client, student_item_id=student_item.id)
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

    refund_tx = Transaction.query.filter_by(
        seat_id=seat.id,
        type='refund',
        amount=Decimal('10.00')
    ).first()
    assert refund_tx is None
