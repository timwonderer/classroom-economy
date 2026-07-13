from datetime import datetime, timezone
from decimal import Decimal

from werkzeug.security import generate_password_hash

from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin
from app.extensions import db
from app.feats.base import FEATContext
from app.models import Seat, IdentityProfile, User, UserRole, InsurancePolicy, RentPolicyVersion, StoreItem, InsuranceEnrollment, StorePurchase, Transaction, ClassEconomy
from app.services import obligations_service
from tests.helpers.canonical_session import set_canonical_context


def _login_admin(client, user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['current_session_nonce'] = 'testnonce'


def _login_student(client, student_user):
    seat = Seat.query.filter_by(user_id=student_user.id).order_by(Seat.id.asc()).first()
    assert seat is not None
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=student_user.id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )
        sess["current_class_id"] = seat.class_id
        sess["current_seat_id"] = seat.id


def _build_teacher_student(join_code='VOID123'):
    from tests.helpers.class_scope import create_class_scope, make_student_identity
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"void-rules:{join_code}"):
        teacher_user = seed_canonical_admin(f"teacher_{join_code}").user
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
        db.session.flush()

    return teacher_user, student_user


def _make_store_item(*, owner_id: int, class_id: str, name: str, price: Decimal, item_type: str = 'delayed', is_active: bool = True):
    with FEATContext("FEAT-STOR-002", idempotency_key=f"void-rules:item:{class_id}:{name}"):
        item = StoreItem(
            user_id=owner_id,
            class_id=class_id,
            name=name,
            price=price,
            item_type=item_type,
            is_active=is_active,
        )
        db.session.add(item)
        db.session.flush()
    return item


def _seed_checking_balance(*, seat_id: int, class_id: str, amount: Decimal, description: str):
    with FEATContext("FEAT-LED-001", idempotency_key=f"void-rules:seed:{seat_id}:{class_id}:{description}"):
        db.session.add(Transaction(
            seat_id=seat_id,
            class_id=class_id,
            amount=amount,
            account_type='checking',
            type='deposit',
            description=description,
        ))
        db.session.flush()


def test_void_delayed_purchase_removes_item_and_refunds(client):
    teacher_user, student_user = _build_teacher_student('VOIDDLY1')

    delayed_item = _make_store_item(
        owner_id=teacher_user.id,
        class_id=student_user.last_active_class_id,
        name='Delayed Reward',
        price=Decimal('25.00'),
    )
    _seed_checking_balance(
        seat_id=student_user.last_active_seat_id,
        class_id=student_user.last_active_class_id,
        amount=Decimal('100.00'),
        description='Initial funds',
    )

    _login_student(client, student_user)
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

    delayed_item = _make_store_item(
        owner_id=teacher_user.id,
        class_id=student_user.last_active_class_id,
        name='Notebook',
        price=Decimal('25.00'),
    )
    _seed_checking_balance(
        seat_id=student_user.last_active_seat_id,
        class_id=student_user.last_active_class_id,
        amount=Decimal('100.00'),
        description='Initial funds',
    )

    _login_student(client, student_user)
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

    delayed_item = _make_store_item(
        owner_id=teacher_user.id,
        class_id=student_user.last_active_class_id,
        name='Marker',
        price=Decimal('5.00'),
    )
    _seed_checking_balance(
        seat_id=student_user.last_active_seat_id,
        class_id=student_user.last_active_class_id,
        amount=Decimal('20.00'),
        description='Initial funds',
    )

    _login_student(client, student_user)
    resp = client.post('/api/purchase-item', json={
        'item_id': delayed_item.id,
        'passphrase': 'password',
        'quantity': 'abc',
    })

    assert resp.status_code == 400
    assert resp.get_json()['message'] == 'Quantity must be a whole number.'


def test_purchase_rejects_oversized_client_purchase_id_with_400(client):
    teacher_user, student_user = _build_teacher_student('VOIDLONG1')

    delayed_item = _make_store_item(
        owner_id=teacher_user.id,
        class_id=student_user.last_active_class_id,
        name='Folder',
        price=Decimal('5.00'),
    )
    _seed_checking_balance(
        seat_id=student_user.last_active_seat_id,
        class_id=student_user.last_active_class_id,
        amount=Decimal('20.00'),
        description='Initial funds',
    )

    _login_student(client, student_user)
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

    immediate_item = _make_store_item(
        owner_id=teacher_user.id,
        class_id=student_user.last_active_class_id,
        name='Immediate Reward',
        price=Decimal('15.00'),
        item_type='immediate',
    )
    _seed_checking_balance(
        seat_id=student_user.last_active_seat_id,
        class_id=student_user.last_active_class_id,
        amount=Decimal('100.00'),
        description='Initial funds',
    )

    _login_student(client, student_user)
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
    purchase_tx_id = purchase_tx.id

    _login_admin(client, teacher_user.id)
    resp = client.post(
        f'/admin/void-transaction/{purchase_tx_id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 400
    assert 'Immediate-use item purchases are not voidable.' in resp.get_json()['message']
    assert Transaction.query.filter_by(
        id=purchase_tx_id,
        is_void=True,
    ).count() == 0


def test_void_delayed_purchase_after_redemption_request_is_not_allowed(client):
    teacher_user, student_user = _build_teacher_student('VOIDUSE1')

    delayed_item = _make_store_item(
        owner_id=teacher_user.id,
        class_id=student_user.last_active_class_id,
        name='Delayed Use Reward',
        price=Decimal('20.00'),
    )
    _seed_checking_balance(
        seat_id=student_user.last_active_seat_id,
        class_id=student_user.last_active_class_id,
        amount=Decimal('100.00'),
        description='Initial funds',
    )

    _login_student(client, student_user)
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
    purchase_tx_id = purchase_tx.id

    _login_admin(client, teacher_user.id)
    resp = client.post(
        f'/admin/void-transaction/{purchase_tx_id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 400
    assert 'cannot be voided' in resp.get_json()['message']
    assert Transaction.query.filter_by(
        id=purchase_tx_id,
        is_void=True,
    ).count() == 0


def test_void_already_voided_transaction_is_rejected(client):
    teacher_user, student_user = _build_teacher_student('VOIDDBL1')

    delayed_item = _make_store_item(
        owner_id=teacher_user.id,
        class_id=student_user.last_active_class_id,
        name='Double Void Item',
        price=Decimal('10.00'),
    )
    _seed_checking_balance(
        seat_id=student_user.last_active_seat_id,
        class_id=student_user.last_active_class_id,
        amount=Decimal('100.00'),
        description='Initial funds',
    )

    _login_student(client, student_user)
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
    purchase_tx_id = purchase_tx.id

    _login_admin(client, teacher_user.id)
    # First void should succeed
    resp1 = client.post(
        f'/admin/void-transaction/{purchase_tx_id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp1.status_code == 200
    assert resp1.get_json()['status'] == 'success'

    # Second void of the same transaction should be rejected
    resp2 = client.post(
        f'/admin/void-transaction/{purchase_tx_id}',
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
    now = datetime.now(timezone.utc)

    with FEATContext("FEAT-LED-001", idempotency_key="void-rules:VOIDRNT1:rent"):
        policy_version = RentPolicyVersion(
            class_id=student_user.last_active_class_id,
            version_number=1,
            rent_amount=Decimal('30.00'),
            frequency_type='monthly',
            cycle_length_days=30,
            grace_period_days=3,
            late_penalty_amount=Decimal('10.00'),
            late_penalty_type='once',
            bill_preview_enabled=False,
            bill_preview_days=7,
            allow_incremental_payment=False,
            prevent_purchase_when_late=False,
            frozen_items=[],
        )
        db.session.add(policy_version)
        db.session.flush()

        rent_tx = Transaction(
            seat_id=student_user.last_active_seat_id,
            class_id=student_user.last_active_class_id,
            amount=Decimal('-30.00'),
            account_type='checking',
            type='Rent Payment',
            description=f'Rent for Period A - {now.strftime("%B %Y")}',
            timestamp=now,
        )
        db.session.add(rent_tx)
        db.session.flush()

        rent_assessment = obligations_service.record_rent_payment(
            seat_id=student_user.last_active_seat_id,
            class_id=student_user.last_active_class_id,
            period='A',
            amount_paid=Decimal('30.00'),
            period_month=now.month,
            period_year=now.year,
            coverage_month=now.month,
            coverage_year=now.year,
            was_late=False,
            late_fee_charged=Decimal('0.00'),
            transaction_id=rent_tx.id,
            rent_policy_version_id=policy_version.id,
        )

    _login_admin(client, teacher_user.id)
    resp = client.post(
        f'/admin/void-transaction/{rent_tx.id}',
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 200
    rent_tx_id = rent_tx.id
    rent_assessment_id = rent_assessment.id
    db.session.expire_all()
    rent_tx = Transaction.query.filter_by(id=rent_tx_id).first()
    assert rent_tx.is_void is True
    assert rent_tx.reversal_transaction_id is not None
    assert db.session.get(type(rent_assessment), rent_assessment_id) is None


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
    with FEATContext("FEAT-ADMN-001", idempotency_key="void-rules:VOIDINS1:policy"):
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
        db.session.flush()

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
