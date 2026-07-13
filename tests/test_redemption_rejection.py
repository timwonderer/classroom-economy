from tests.helpers.v2_fixtures import seed_canonical_admin
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from app.models import Transaction, StoreItem, StorePurchase, ClassEconomy, Seat
from app.extensions import db
from app.feats.base import FEATContext
from tests.helpers.canonical_session import set_canonical_context
from tests.helpers.class_scope import make_student_identity, create_class_scope


@pytest.fixture
def teacher_admin(client):
    admin = seed_canonical_admin("teacher_r", "secret").user
    db.session.commit()
    return admin


@pytest.fixture
def student_in_class(client, teacher_admin):
    class_row = create_class_scope(teacher_user=teacher_admin, join_code='REJECT123')
    db.session.flush()
    student_seat = make_student_identity(class_id=class_row.class_id, first_name='TestRejection', last_name='S', claimed=True)
    db.session.commit()
    return student_seat


def test_reject_redemption_refunds_student(client, teacher_admin, student_in_class):
    """Test that rejecting a redemption refunds the student and removes the item."""
    student = student_in_class
    seat = Seat.query.filter_by(user_id=student.user_id, class_id=student.class_id, role="student").first()

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"redemption-reject:seed:{student.class_id}:{student.user_id}"):
        item = StoreItem(
            user_id=teacher_admin.id,
            class_id=student.class_id,
            join_code='REJECT123',
            name='Refundable Item',
            price=Decimal('15.00'),
            item_type='delayed',
            is_active=True
        )
        db.session.add(item)
        db.session.flush()

        initial_balance = Decimal('100.00')
        tx = Transaction(
            user_id=student.user_id, seat_id=seat.id, join_code='REJECT123',
            amount=initial_balance,
            account_type='checking',
            type='deposit',
            description='Initial funds'
        )
        db.session.add(tx)
        db.session.flush()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student.user_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )

    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1
    })
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

    with client.session_transaction() as sess:
        teacher_seat = Seat.query.filter_by(user_id=teacher_admin.id, class_id=seat.class_id, role="teacher").first()
        assert teacher_seat is not None
        set_canonical_context(
            sess,
            user_id=teacher_admin.id,
            class_id=seat.class_id,
            seat_id=teacher_seat.id,
            role="teacher",
        )

    resp = client.post('/api/reject-redemption', json={'student_item_id': student_item.id})
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

    item_check = db.session.get(StorePurchase, student_item.id)
    assert item_check is not None
    assert item_check.status == 'rejected'

    refund_tx = Transaction.query.filter_by(
        user_id=student.user_id,
        type='refund',
        amount=Decimal('15.00')
    ).first()
    assert refund_tx is not None
    assert "Refund:" in refund_tx.description
    purchase_tx = Transaction.query.filter_by(
        user_id=student.user_id,
        type='purchase',
    ).filter(Transaction.description.like('Purchase: Refundable Item%')).first()
    assert purchase_tx is not None
    assert refund_tx.original_transaction_id == purchase_tx.id


def test_reject_redemption_refunds_single_unit_from_multi_quantity_purchase(client, teacher_admin, student_in_class):
    """Ensure a rejected redemption refunds only one unit from a multi-quantity purchase."""
    student = student_in_class
    seat = Seat.query.filter_by(user_id=student.user_id, class_id=student.class_id, role="student").first()

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"redemption-reject:seed-bulk:{student.class_id}:{student.user_id}"):
        item = StoreItem(
            user_id=teacher_admin.id,
            class_id=student.class_id,
            name='Bulk Item',
            price=Decimal('10.00'),
            item_type='delayed',
            is_active=True
        )
        db.session.add(item)
        db.session.flush()

        initial_balance = Decimal('100.00')
        db.session.add(Transaction(
            user_id=student.user_id, seat_id=seat.id, join_code='REJECT123',
            amount=initial_balance,
            account_type='checking',
            type='deposit',
            description='Initial funds'
        ))
        db.session.flush()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student.user_id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )

    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 3
    })
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

    with client.session_transaction() as sess:
        teacher_seat = Seat.query.filter_by(user_id=teacher_admin.id, class_id=seat.class_id, role="teacher").first()
        assert teacher_seat is not None
        set_canonical_context(
            sess,
            user_id=teacher_admin.id,
            class_id=seat.class_id,
            seat_id=teacher_seat.id,
            role="teacher",
        )

    resp = client.post('/api/reject-redemption', json={'student_item_id': student_item.id})
    assert resp.status_code == 200
    assert resp.json['status'] == 'success'

    refund_tx = Transaction.query.filter_by(
        user_id=student.user_id,
        type='refund',
        amount=Decimal('10.00')
    ).first()
    assert refund_tx is not None
