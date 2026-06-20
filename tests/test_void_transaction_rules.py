from datetime import datetime, timezone
from decimal import Decimal

from werkzeug.security import generate_password_hash

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import Seat, IdentityProfile, Admin, InsurancePolicy, RentPayment, StoreItem, Student, StudentInsurance, StudentItem, StudentTeacher, Transaction


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess['admin_id'] = admin_id
        sess['is_admin'] = True


def _login_student(client, student_id, join_code):
    with client.session_transaction() as sess:
        sess['student_id'] = student_id
        sess['current_join_code'] = join_code
        sess['login_time'] = datetime.now(timezone.utc).isoformat()


def _build_teacher_student(join_code='VOID123'):
    teacher = make_admin(f"teacher_{join_code}", "secret")
    db.session.add(teacher)
    db.session.flush()

    profile = IdentityProfile(profile_type='student', first_name='Void', last_name='T')
    db.session.add(profile)
    db.session.flush()
    student = Student(identity_profile=profile, block="A", salt=b'salt')
    student.passphrase_hash = generate_password_hash('password')
    db.session.add(student)
    db.session.flush()

    db.session.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.session.add(Seat(
        student_id=student.id,
        join_code=join_code,
        block='A',
        role='student',
    ))
    _tb_seat = Seat(student_id=student.id, join_code=join_code, block='A', block_identifier='A', role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name='Void', last_name='T'))
    db.session.commit()
    return teacher, student


def test_void_delayed_purchase_removes_item_and_refunds(client):
    teacher, student = _build_teacher_student('VOIDDLY1')

    delayed_item = StoreItem(
        teacher_id=teacher.id,
        join_code='VOIDDLY1',
        name='Delayed Reward',
        price=Decimal('25.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code='VOIDDLY1',
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student.id, 'VOIDDLY1')
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200

    purchase_tx = Transaction.query.filter_by(
        student_id=student.id,
        type='purchase',
    ).filter(Transaction.description.like("Purchase: Delayed Reward%")).first()
    assert purchase_tx is not None
    assert StudentItem.query.filter_by(student_id=student.id, store_item_id=delayed_item.id).count() == 1

    _login_admin(client, teacher.id)
    resp = client.post(
        f'/admin/void-transaction/{purchase_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'success'

    db.session.refresh(purchase_tx)
    assert purchase_tx.is_void is True
    voided_item = StudentItem.query.filter_by(student_id=student.id, store_item_id=delayed_item.id).first()
    assert voided_item is not None
    assert voided_item.status == 'voided'

    db.session.refresh(purchase_tx)
    assert purchase_tx.reversal_transaction_id is not None
    assert Transaction.query.filter_by(
        student_id=student.id,
        type='void_item_removed',
        amount=Decimal('0.00'),
    ).filter(Transaction.description == 'item removed - Delayed Reward').count() == 1
    assert Transaction.query.filter_by(
        student_id=student.id,
        type='refund',
        amount=Decimal('25.00'),
    ).filter(Transaction.description.like(f"Void refund for transaction #{purchase_tx.id}:%")).count() == 1
    reversal_tx = db.session.get(Transaction, purchase_tx.reversal_transaction_id)
    assert reversal_tx is not None
    assert reversal_tx.original_transaction_id == purchase_tx.id
    assert reversal_tx.idempotency_key == f"txn:void:transaction:{purchase_tx.id}:refund"


def test_duplicate_purchase_submission_with_same_client_token_is_idempotent(client):
    teacher, student = _build_teacher_student('VOIDIDEMP1')

    delayed_item = StoreItem(
        teacher_id=teacher.id,
        join_code='VOIDIDEMP1',
        name='Notebook',
        price=Decimal('25.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code='VOIDIDEMP1',
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student.id, 'VOIDIDEMP1')
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
        student_id=student.id,
        type='purchase',
    ).filter(Transaction.description.like("Purchase: Notebook%")).all()
    assert len(purchase_txs) == 1
    assert StudentItem.query.filter_by(student_id=student.id, store_item_id=delayed_item.id).count() == 1
    assert purchase_txs[0].idempotency_key == (
        f"txn:purchase:student:{student.id}:join:voididemp1:item:{delayed_item.id}:double-tap-1"
    )


def test_purchase_rejects_non_numeric_quantity_with_400(client):
    teacher, student = _build_teacher_student('VOIDBADQ1')

    delayed_item = StoreItem(
        teacher_id=teacher.id,
        join_code='VOIDBADQ1',
        name='Marker',
        price=Decimal('5.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code='VOIDBADQ1',
        amount=Decimal('20.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student.id, 'VOIDBADQ1')
    resp = client.post('/api/purchase-item', json={
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 'abc',
    })

    assert resp.status_code == 400
    assert resp.get_json()['message'] == 'Quantity must be a whole number.'


def test_purchase_rejects_oversized_client_purchase_id_with_400(client):
    teacher, student = _build_teacher_student('VOIDLONG1')

    delayed_item = StoreItem(
        teacher_id=teacher.id,
        join_code='VOIDLONG1',
        name='Folder',
        price=Decimal('5.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code='VOIDLONG1',
        amount=Decimal('20.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student.id, 'VOIDLONG1')
    resp = client.post('/api/purchase-item', json={
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 1,
        'client_purchase_id': 'x' * 129,
    })

    assert resp.status_code == 400
    assert resp.get_json()['message'] == 'Purchase request ID is too long.'


def test_void_immediate_purchase_is_not_allowed(client):
    teacher, student = _build_teacher_student('VOIDIMM1')

    immediate_item = StoreItem(
        teacher_id=teacher.id,
        join_code='VOIDIMM1',
        name='Immediate Reward',
        price=Decimal('15.00'),
        item_type='immediate',
        is_active=True,
    )
    db.session.add(immediate_item)
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code='VOIDIMM1',
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student.id, 'VOIDIMM1')
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': immediate_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200

    purchase_tx = Transaction.query.filter_by(
        student_id=student.id,
        type='purchase',
    ).filter(Transaction.description.like("Purchase: Immediate Reward%")).first()
    assert purchase_tx is not None

    _login_admin(client, teacher.id)
    resp = client.post(
        f'/admin/void-transaction/{purchase_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 400
    assert 'Immediate-use item purchases are not voidable.' in resp.get_json()['message']

    db.session.refresh(purchase_tx)
    assert purchase_tx.is_void is False


def test_void_delayed_purchase_after_redemption_request_is_not_allowed(client):
    teacher, student = _build_teacher_student('VOIDUSE1')

    delayed_item = StoreItem(
        teacher_id=teacher.id,
        join_code='VOIDUSE1',
        name='Delayed Use Reward',
        price=Decimal('20.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code='VOIDUSE1',
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student.id, 'VOIDUSE1')
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200

    student_item = StudentItem.query.filter_by(
        student_id=student.id,
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
        student_id=student.id,
        type='purchase',
    ).filter(Transaction.description.like("Purchase: Delayed Use Reward%")).first()
    assert purchase_tx is not None

    _login_admin(client, teacher.id)
    resp = client.post(
        f'/admin/void-transaction/{purchase_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 400
    assert 'cannot be voided' in resp.get_json()['message']

    db.session.refresh(purchase_tx)
    assert purchase_tx.is_void is False


def test_void_already_voided_transaction_is_rejected(client):
    teacher, student = _build_teacher_student('VOIDDBL1')

    delayed_item = StoreItem(
        teacher_id=teacher.id,
        join_code='VOIDDBL1',
        name='Double Void Item',
        price=Decimal('10.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(delayed_item)
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code='VOIDDBL1',
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student.id, 'VOIDDBL1')
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200

    purchase_tx = Transaction.query.filter_by(
        student_id=student.id,
        type='purchase',
    ).filter(Transaction.description.like("Purchase: Double Void Item%")).first()
    assert purchase_tx is not None

    _login_admin(client, teacher.id)
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
        student_id=student.id,
        type='refund',
        original_transaction_id=purchase_tx.id,
    ).count()
    assert refund_count == 1


def test_void_rent_payment_reverts_bill_to_unpaid(client):
    teacher, student = _build_teacher_student('VOIDRNT1')

    rent_tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code='VOIDRNT1',
        amount=Decimal('-30.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A - January 2026',
    )
    db.session.add(rent_tx)
    db.session.flush()

    rent_payment = RentPayment(
        student_id=student.id,
        period='A',
        join_code='VOIDRNT1',
        amount_paid=Decimal('30.00'),
        period_month=1,
        period_year=2026,
        coverage_month=1,
        coverage_year=2026,
    )
    db.session.add(rent_payment)
    db.session.commit()

    _login_admin(client, teacher.id)
    resp = client.post(
        f'/admin/void-transaction/{rent_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 200
    db.session.refresh(rent_tx)
    assert rent_tx.is_void is True
    assert rent_tx.reversal_transaction_id is not None
    assert db.session.get(RentPayment, rent_payment.id) is None


def test_void_insurance_premium_marks_enrollment_unpaid(client):
    teacher, student = _build_teacher_student('VOIDINS1')

    policy = InsurancePolicy(
        policy_code='VOIDPOL1',
        teacher_id=teacher.id,
        title='Coverage',
        premium=Decimal('12.00'),
        claim_type='legacy_monetary',
        is_monetary=True,
        is_active=True,
    )
    db.session.add(policy)
    db.session.flush()

    enrollment = StudentInsurance(
        student_id=student.id,
        policy_id=policy.id,
        join_code='VOIDINS1',
        status='active',
        payment_current=True,
        days_unpaid=0,
    )
    db.session.add(enrollment)

    insurance_tx = Transaction(
        student_id=student.id,
        teacher_id=teacher.id,
        join_code='VOIDINS1',
        amount=Decimal('-12.00'),
        account_type='checking',
        type='insurance_premium',
        description='Insurance premium: Coverage',
    )
    db.session.add(insurance_tx)
    db.session.commit()

    _login_admin(client, teacher.id)
    resp = client.post(
        f'/admin/void-transaction/{insurance_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 200
    db.session.refresh(insurance_tx)
    db.session.refresh(enrollment)
    assert insurance_tx.is_void is True
    assert insurance_tx.reversal_transaction_id is not None
    assert enrollment.payment_current is False
    assert enrollment.days_unpaid >= 1
