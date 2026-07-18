import pytest
from decimal import Decimal
from app.models import Transaction, StoreItem, StorePurchase, Seat
from app.extensions import db
from app.feats.base import FEATContext
from tests.dom.entitlement.helpers import (
    create_entitlement_store_item,
    login_entitlement_student,
    login_entitlement_teacher,
    purchase_entitlement_item,
    reject_entitlement_redemption,
)
from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher, initialize


@pytest.fixture
def teacher_admin(client, app):
    classroom = initialize("chemistry_p1", app)
    return classroom.teacher_user


@pytest.fixture
def student_in_class(client, teacher_admin, app):
    classroom = initialize("chemistry_p1", app)
    return classroom.students[0].seat


def test_DOM_STORE_001__reject_redemption_refunds_student(client, teacher_admin, student_in_class, app):
    """Test that rejecting a redemption refunds the student and removes the item."""
    student = student_in_class
    seat = Seat.query.filter_by(user_id=student.user_id, class_id=student.class_id, role="student").first()

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"redemption-reject:seed:{student.class_id}:{student.user_id}"):
        item = create_entitlement_store_item(
            teacher_id=teacher_admin.id,
            class_id=student.class_id,
            name='Refundable Item',
            price=Decimal('15.00'),
            item_type='delayed',
        )

        initial_balance = Decimal('100.00')
        tx = Transaction(
            user_id=student.user_id, seat_id=seat.id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=initial_balance,
            account_type='checking',
            type='deposit',
            description='Initial funds'
        )
        db.session.add(tx)
        db.session.flush()

    login_entitlement_student("chemistry_p1", client, app)

    purchase_resp = purchase_entitlement_item(client, item_id=item.id, passphrase='password', quantity=1)
    assert purchase_resp.status_code == 200
    assert purchase_resp.json['status'] == 'success'

    student_item = StorePurchase.query.filter_by(seat_id=seat.id, store_item_id=item.id).first()
    assert student_item is not None
    assert student_item.status == 'purchased'

    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'Please refund me'
    })
    assert use_resp.status_code == 200
    assert use_resp.json['status'] == 'success'

    db.session.refresh(student_item)
    assert student_item.status == 'processing'

    login_entitlement_teacher("chemistry_p1", client, app)

    resp = reject_entitlement_redemption(client, student_item_id=student_item.id)
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

    item_check = db.session.get(StorePurchase, student_item.id)
    assert item_check is not None
    assert item_check.status == 'rejected'

    refund_tx = Transaction.query.filter_by(
        seat_id=seat.id,
        type='refund',
        amount=Decimal('15.00')
    ).first()
    assert refund_tx is not None
    assert "Refund:" in refund_tx.description
    purchase_tx = Transaction.query.filter_by(
        seat_id=seat.id,
        type='purchase',
    ).filter(Transaction.description.like('Purchase: Refundable Item%')).first()
    assert purchase_tx is not None
    assert refund_tx.original_transaction_id == purchase_tx.id


def test_DOM_STORE_001__reject_redemption_refunds_single_unit_from_multi_quantity_purchase(client, teacher_admin, student_in_class, app):
    """Ensure a rejected redemption refunds only one unit from a multi-quantity purchase."""
    student = student_in_class
    seat = Seat.query.filter_by(user_id=student.user_id, class_id=student.class_id, role="student").first()

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"redemption-reject:seed-bulk:{student.class_id}:{student.user_id}"):
        item = create_entitlement_store_item(
            teacher_id=teacher_admin.id,
            class_id=student.class_id,
            name='Bulk Item',
            price=Decimal('10.00'),
            item_type='delayed',
        )

        initial_balance = Decimal('100.00')
        db.session.add(Transaction(
            user_id=student.user_id, seat_id=seat.id,
            target_seat_id=seat.id,
            actor_seat_id=seat.id,
            mechanism="self",
            amount=initial_balance,
            account_type='checking',
            type='deposit',
            description='Initial funds'
        ))
        db.session.flush()

    login_entitlement_student("chemistry_p1", client, app)

    purchase_resp = purchase_entitlement_item(client, item_id=item.id, passphrase='password', quantity=3)
    assert purchase_resp.status_code == 200
    assert purchase_resp.json['status'] == 'success'

    student_item = StorePurchase.query.filter_by(seat_id=seat.id, store_item_id=item.id).first()
    assert student_item is not None

    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'Use one from bulk'
    })
    assert use_resp.status_code == 200
    assert use_resp.json['status'] == 'success'

    db.session.refresh(student_item)
    assert student_item.status == 'processing'

    login_entitlement_teacher("chemistry_p1", client, app)

    resp = reject_entitlement_redemption(client, student_item_id=student_item.id)
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

    refund_tx = Transaction.query.filter_by(
        seat_id=seat.id,
        type='refund',
        amount=Decimal('10.00')
    ).first()
    assert refund_tx is not None
