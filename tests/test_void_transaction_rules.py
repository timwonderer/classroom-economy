from datetime import datetime, timezone
from decimal import Decimal

from werkzeug.security import generate_password_hash

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import Seat, IdentityProfile, User, UserRole, InsurancePolicy, RentPayment, StoreItem, InsuranceEnrollment, StorePurchase, Transaction, ClassEconomy


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['current_session_nonce'] = 'testnonce'
    with client.session_transaction() as sess:
        sess['admin_id'] = admin_id
        sess['is_admin'] = True


def _login_student(client, student_user, join_code):
    with client.session_transaction() as sess:
        sess['user_id'] = student_user.id
        sess['current_session_nonce'] = student_user.current_session_nonce
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()


def _build_teacher_student(join_code='VOID123'):
    from tests.helpers.class_scope import create_class_scope, make_student_identity
    teacher_user = make_admin(f"teacher_{join_code}")
    teacher_user.current_session_nonce = 'testnonce'
    db.session.flush()

    economy = create_class_scope(teacher_user=teacher_user, join_code=join_code)
    db.session.flush()

    student_seat = make_student_identity(class_id=economy.class_id, first_name='Void', last_name='T', claimed=True)
    db.session.flush()

    student_user = db.session.get(User, student_seat.user_id)
    student_user.passphrase_hash = generate_password_hash('password')
    student_user.current_session_nonce = 'testnonce'
    student_user.last_active_class_id = student_seat.class_id
    student_user.last_active_seat_id = student_seat.id
    teacher_user.last_active_class_id = economy.class_id
    db.session.commit()

    return teacher_user, student_user


def test_void_delayed_purchase_removes_item_and_refunds(client):
    teacher_user, student_user = _build_teacher_student('VOIDDLY1')

    print('SEAT ID:', student_user.last_active_seat_id); delayed_item = StoreItem(
        user_id=teacher_user.id,
        name='Delayed Reward',
        price=Decimal('25.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(seat_id=student_user.last_active_seat_id, class_id=student_user.last_active_class_id,
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student_user, 'VOIDDLY1')
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200

    purchase_tx = Transaction.query.filter_by(
        seat_id=student_user.last_active_seat_id,
        type='purchase',
    ).filter(Transaction.description.like("Purchase: Delayed Reward%")).first()
    assert purchase_tx is not None
    assert StorePurchase.query.filter_by(seat_id=student_user.last_active_seat_id, store_item_id=delayed_item.id).count() == 1

    _login_admin(client, teacher_user.id)
    resp = client.post(
        f'/admin/void-transaction/{purchase_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'success'

    purchase_tx_id = purchase_tx.id
    db.session.expire_all()
    purchase_tx = Transaction.query.filter_by(id=purchase_tx_id).first()
    assert purchase_tx.is_void is True
    voided_item = StorePurchase.query.filter_by(seat_id=student_user.last_active_seat_id, store_item_id=delayed_item.id).first()
    assert voided_item is not None
    assert voided_item.status == 'voided'

    assert purchase_tx.reversal_transaction_id is not None
    assert Transaction.query.filter_by(
        seat_id=student_user.last_active_seat_id,
        type='void_item_removed',
        amount=Decimal('0.00'),
    ).filter(Transaction.description == 'item removed - Delayed Reward').count() == 1
    assert Transaction.query.filter_by(
        seat_id=student_user.last_active_seat_id,
        type='refund',
        amount=Decimal('25.00'),
    ).filter(Transaction.description.like(f"Void refund for transaction #{purchase_tx.id}:%")).count() == 1
    reversal_tx = db.session.get(Transaction, purchase_tx.reversal_transaction_id)
    assert reversal_tx is not None
    assert reversal_tx.original_transaction_id == purchase_tx.id
    assert reversal_tx.idempotency_key == f"txn:void:transaction:{purchase_tx.id}:refund"


def test_duplicate_purchase_submission_with_same_client_token_is_idempotent(client):
    teacher_user, student_user = _build_teacher_student('VOIDIDEMP1')

    print('SEAT ID:', student_user.last_active_seat_id); delayed_item = StoreItem(
        user_id=teacher_user.id,
        name='Notebook',
        price=Decimal('25.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(seat_id=student_user.last_active_seat_id, class_id=student_user.last_active_class_id,
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student_user, 'VOIDIDEMP1')
    payload = {
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 1,
        'client_purchase_id': 'double-tap-1',
    }

    first_resp = client.post('/api/purchase-item', json=payload)
    second_resp = client.post('/api/purchase-item', json=payload)

    assert first_resp.status_code == 200
    assert second_resp.status_code == 200
    assert second_resp.get_json()['status'] == 'success'

    purchase_txs = Transaction.query.filter_by(
        seat_id=student_user.last_active_seat_id,
        type='purchase',
    ).filter(Transaction.description.like("Purchase: Notebook%")).all()
    assert len(purchase_txs) == 1
    assert StorePurchase.query.filter_by(seat_id=student_user.last_active_seat_id, store_item_id=delayed_item.id).count() == 1
    assert purchase_txs[0].idempotency_key == (
        f'txn:purchase:student:{student_user.id}:class:{student_user.last_active_class_id}:item:{delayed_item.id}:double-tap-1'
    )


def test_purchase_rejects_non_numeric_quantity_with_400(client):
    teacher_user, student_user = _build_teacher_student('VOIDBADQ1')

    print('SEAT ID:', student_user.last_active_seat_id); delayed_item = StoreItem(
        user_id=teacher_user.id,
        name='Marker',
        price=Decimal('5.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(seat_id=student_user.last_active_seat_id, class_id=student_user.last_active_class_id,
        amount=Decimal('20.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student_user, 'VOIDBADQ1')
    resp = client.post('/api/purchase-item', json={
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 'abc',
    })

    assert resp.status_code == 400
    assert resp.get_json()['message'] == 'Quantity must be a whole number.'


def test_purchase_rejects_oversized_client_purchase_id_with_400(client):
    teacher_user, student_user = _build_teacher_student('VOIDLONG1')

    print('SEAT ID:', student_user.last_active_seat_id); delayed_item = StoreItem(
        user_id=teacher_user.id,
        name='Folder',
        price=Decimal('5.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(seat_id=student_user.last_active_seat_id, class_id=student_user.last_active_class_id,
        amount=Decimal('20.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student_user, 'VOIDLONG1')
    resp = client.post('/api/purchase-item', json={
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 1,
        'client_purchase_id': 'x' * 129,
    })

    assert resp.status_code == 400
    assert resp.get_json()['message'] == 'Purchase request ID is too long.'


def test_void_immediate_purchase_is_not_allowed(client):
    teacher_user, student_user = _build_teacher_student('VOIDIMM1')

    immediate_item = StoreItem(
        user_id=teacher_user.id,
        name='Immediate Reward',
        price=Decimal('15.00'),
        item_type='immediate',
        is_active=True,
    )
    db.session.add(immediate_item)
    db.session.add(Transaction(seat_id=student_user.last_active_seat_id, class_id=student_user.last_active_class_id,
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student_user, 'VOIDIMM1')
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': immediate_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200

    purchase_tx = Transaction.query.filter_by(
        seat_id=student_user.last_active_seat_id,
        type='purchase',
    ).filter(Transaction.description.like("Purchase: Immediate Reward%")).first()
    assert purchase_tx is not None

    _login_admin(client, teacher_user.id)
    resp = client.post(
        f'/admin/void-transaction/{purchase_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 400
    assert 'Immediate-use item purchases are not voidable.' in resp.get_json()['message']

    purchase_tx_id = purchase_tx.id
    db.session.expire_all()
    purchase_tx = Transaction.query.filter_by(id=purchase_tx_id).first()
    assert purchase_tx.is_void is False


def test_void_delayed_purchase_after_redemption_request_is_not_allowed(client):
    teacher_user, student_user = _build_teacher_student('VOIDUSE1')

    print('SEAT ID:', student_user.last_active_seat_id); delayed_item = StoreItem(
        user_id=teacher_user.id,
        name='Delayed Use Reward',
        price=Decimal('20.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(seat_id=student_user.last_active_seat_id, class_id=student_user.last_active_class_id,
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student_user, 'VOIDUSE1')
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200

    student_item = StorePurchase.query.filter_by(
        seat_id=student_user.last_active_seat_id,
        store_item_id=delayed_item.id,
    ).first()
    assert student_item is not None
    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'Request redemption',
    })
    assert use_resp.status_code == 200

    purchase_tx = Transaction.query.filter_by(
        seat_id=student_user.last_active_seat_id,
        type='purchase',
    ).filter(Transaction.description.like("Purchase: Delayed Use Reward%")).first()
    assert purchase_tx is not None

    _login_admin(client, teacher_user.id)
    resp = client.post(
        f'/admin/void-transaction/{purchase_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 400
    assert 'cannot be voided' in resp.get_json()['message']

    purchase_tx_id = purchase_tx.id
    db.session.expire_all()
    purchase_tx = Transaction.query.filter_by(id=purchase_tx_id).first()
    assert purchase_tx.is_void is False


def test_void_already_voided_transaction_is_rejected(client):
    teacher_user, student_user = _build_teacher_student('VOIDDBL1')

    print('SEAT ID:', student_user.last_active_seat_id); delayed_item = StoreItem(
        user_id=teacher_user.id,
        name='Double Void Item',
        price=Decimal('10.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(seat_id=student_user.last_active_seat_id, class_id=student_user.last_active_class_id,
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student_user, 'VOIDDBL1')
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200

    purchase_tx = Transaction.query.filter_by(
        seat_id=student_user.last_active_seat_id,
        type='purchase',
    ).filter(Transaction.description.like("Purchase: Double Void Item%")).first()
    assert purchase_tx is not None

    _login_admin(client, teacher_user.id)
    # First void should succeed
    resp1 = client.post(
        f'/admin/void-transaction/{purchase_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp1.status_code == 200
    assert resp1.get_json()['status'] == 'success'

    # Second void of the same transaction should be rejected
    resp2 = client.post(
        f'/admin/void-transaction/{purchase_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp2.status_code == 400
    assert 'already voided' in resp2.get_json()['message']

    # Verify only one refund was created
    refund_count = Transaction.query.filter_by(
        seat_id=student_user.last_active_seat_id,
        type='refund',
        original_transaction_id=purchase_tx.id,
    ).count()
    assert refund_count == 1


def test_void_rent_payment_reverts_bill_to_unpaid(client):
    teacher_user, student_user = _build_teacher_student('VOIDRNT1')

    rent_tx = Transaction(seat_id=student_user.last_active_seat_id, class_id=student_user.last_active_class_id,
        amount=Decimal('-30.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A - January 2026',
    )
    db.session.add(rent_tx)
    db.session.flush()

    rent_payment = RentPayment(
        seat_id=student_user.last_active_seat_id,
        period='A',
        amount_paid=Decimal('30.00'),
        period_month=1,
        period_year=2026,
        coverage_month=1,
        coverage_year=2026,
    )
    db.session.add(rent_payment)
    db.session.commit()

    _login_admin(client, teacher_user.id)
    resp = client.post(
        f'/admin/void-transaction/{rent_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 200
    rent_tx_id = rent_tx.id
    rent_payment_id = rent_payment.id
    db.session.expire_all()
    rent_tx = Transaction.query.filter_by(id=rent_tx_id).first()
    assert rent_tx.is_void is True
    assert rent_tx.reversal_transaction_id is not None
    assert db.session.get(RentPayment, rent_payment_id) is None


def test_void_insurance_premium_marks_enrollment_unpaid(client):
    teacher_user, student_user = _build_teacher_student('VOIDINS1')

    policy = InsurancePolicy(
        policy_code='VOIDPOL1',
        teacher_id=teacher_user.id,
        title='Coverage',
        premium=Decimal('12.00'),
        claim_type='legacy_monetary',
        is_monetary=True,
        is_active=True,
    )
    db.session.add(policy)
    db.session.flush()

    enrollment = InsuranceEnrollment(
        seat_id=student_user.last_active_seat_id,
        class_id=student_user.last_active_class_id,
        policy_id=policy.id,
        status='active',
        payment_current=True,
        days_unpaid=0,
    )
    db.session.add(enrollment)

    insurance_tx = Transaction(seat_id=student_user.last_active_seat_id, class_id=student_user.last_active_class_id,
        amount=Decimal('-12.00'),
        account_type='checking',
        type='insurance_premium',
        description='Insurance premium: Coverage',
    )
    db.session.add(insurance_tx)
    db.session.commit()

    _login_admin(client, teacher_user.id)
    resp = client.post(
        f'/admin/void-transaction/{insurance_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 200
    insurance_tx_id = insurance_tx.id
    enrollment_id = enrollment.id
    db.session.expire_all()
    insurance_tx = Transaction.query.filter_by(id=insurance_tx_id).first()
    enrollment = InsuranceEnrollment.query.filter_by(id=enrollment_id).first()
    assert insurance_tx.is_void is True
    assert insurance_tx.reversal_transaction_id is not None
    assert enrollment.payment_current is False
    assert enrollment.days_unpaid >= 1
