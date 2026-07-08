"""
Tests for collective goal expiration feature.

Covers:
- process_expired_collective_goals: refunds pending purchases and deactivates items on expiry
- Expiration only affects items past their deadline
- Items with no expiration are never auto-expired
- Goals already met ('processing' status) are not disturbed
- Teacher deleting an active collective item refunds pending purchases
- Purchase API blocks purchases when goal has expired
- Reactivated items start with zero progress (voided items excluded from count)
- Expiration is scoped by teacher_id, not across teachers
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from werkzeug.security import generate_password_hash

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from app.extensions import db
from app.models import User, UserRole, Admin, StoreItem, StorePurchase, Transaction, Seat, IdentityProfile, ClassEconomy, ClassFeature
from app.utils.store import process_expired_collective_goals, refund_pending_collective_purchases
from tests.helpers.admin_context import login_admin
from tests.helpers.class_scope import create_class_scope
from tests.helpers.canonical_session import set_canonical_context


def _login_student(client, student_id, join_code):
    with client.session_transaction() as sess:
        seat = Seat.query.filter_by(user_id=student_id).order_by(Seat.id.asc()).first()
        if seat:
            set_canonical_context(
                sess,
                user_id=student_id,
                class_id=seat.class_id,
                seat_id=seat.id,
                role="student",
            )


def _login_admin(client, admin_id, join_code=None):
    login_admin(client, admin_id, join_code)


def _create_teacher(username):
    """Create an Admin (teacher) and flush to get an id."""
    teacher = make_admin(username, 'secret')
    db.session.add(teacher)
    db.session.flush()
    return teacher


def _create_student(teacher, first_name, join_code, block='A'):
    """Create canonical student identity enrolled in the given class period."""
    profile = IdentityProfile(profile_type='student', first_name=first_name, last_name='S')
    db.session.add(profile)
    db.session.flush()
    student_user = User(
        user_role=UserRole.STUDENT,
        username_hash=f"auto_{first_name.lower()}_{join_code.lower()}",
        username_lookup_hash=f"auto_l_{first_name.lower()}_{join_code.lower()}",
        passphrase_hash=generate_password_hash("password"),
    )
    db.session.add(student_user)
    db.session.flush()
    class_row = create_class_scope(
        teacher=teacher,
        join_code=join_code,
        block=block,
        display_name=block,
    )
    seat = Seat(
        user_id=student_user.id,
        class_id=class_row.class_id,
        block=block,
        block_identifier=block,
        role="student",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(seat)
    db.session.flush()
    profile.seat_id = seat.id
    # Give the student funds so purchases succeed
    db.session.add(Transaction(
        seat_id=seat.id,
        user_id=student_user.id,
        class_id=class_row.class_id,
        join_code=join_code,
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    return seat


import uuid

def _collective_item(teacher, name, goal_type='fixed', target=2,
                     expires_at=None, is_active=True):
    """Create a collective StoreItem."""
    class_row = ClassEconomy.query.filter_by(user_id=teacher.id).order_by(ClassEconomy.class_id.asc()).first()
    item = StoreItem(
        user_id=teacher.id,
        class_id=class_row.class_id if class_row else None,
        name=name,
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type=goal_type,
        collective_goal_target=target if goal_type == 'fixed' else None,
        collective_goal_expires_at=expires_at,
        is_active=is_active,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    db.session.add(item)
    db.session.flush()
    return item


def _past():
    """A datetime that is clearly in the past."""
    return datetime.now(timezone.utc) - timedelta(days=1)


def _future():
    """A datetime that is clearly in the future."""
    return datetime.now(timezone.utc) + timedelta(days=1)


# ---------------------------------------------------------------------------
# process_expired_collective_goals utility
# ---------------------------------------------------------------------------

def test_process_expired_goals_refunds_pending_and_deactivates(client):
    """Expired collective goal: pending StudentItems are voided and item is deactivated."""
    teacher = _create_teacher('teacher_exp_refund')
    student = _create_student(teacher, 'Alice', 'JOINEXP1')
    db.session.flush()

    item = _collective_item(teacher, 'Expired Pizza', expires_at=_past())

    # Create a purchase transaction and a pending StudentItem
    purchase_tx = Transaction(
        seat_id=student.id,
        user_id=student.user_id,
        amount=Decimal('-10.00'),
        account_type='checking',
        type='purchase',
        description=f'Purchase: {item.name}',
    )
    db.session.add(purchase_tx)
    db.session.flush()

    si = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='pending',
        ledger_tx_id=purchase_tx.id,
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add(si)
    db.session.commit()

    count = process_expired_collective_goals(teacher.id)

    assert count == 1, "Should have processed one expired item"

    db.session.refresh(item)
    assert item.is_active is False, "Item should be deactivated after expiration"

    db.session.refresh(si)
    assert si.status == 'voided', "Pending purchase should be voided"

    # A refund transaction should have been created
    refund_txs = Transaction.query.filter_by(
        user_id=student.user_id,
        type='refund',
    ).all()
    assert len(refund_txs) == 1
    assert refund_txs[0].amount == Decimal('10.00'), "Refund amount should match original purchase"


def test_process_expired_goals_skips_non_expired_items(client):
    """Items with a future expiration date are not affected."""
    teacher = _create_teacher('teacher_exp_future')
    student = _create_student(teacher, 'Bob', 'JOINEXP2')
    db.session.flush()

    item = _collective_item(teacher, 'Future Goal', 'JOINEXP2', expires_at=_future())
    si = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='pending',
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add(si)
    db.session.commit()

    count = process_expired_collective_goals(teacher.id)

    assert count == 0, "No items should be processed for future expiration"

    db.session.refresh(item)
    assert item.is_active is True, "Item should remain active"

    db.session.refresh(si)
    assert si.status == 'pending', "Purchase status should be unchanged"


def test_process_expired_goals_ignores_items_without_expiration(client):
    """Items with no expiration date are never auto-expired."""
    teacher = _create_teacher('teacher_exp_none')
    student = _create_student(teacher, 'Carol', 'JOINEXP3')
    db.session.flush()

    # No expires_at set
    item = _collective_item(teacher, 'No Expiry Goal', 'JOINEXP3', expires_at=None)
    si = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='pending',
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add(si)
    db.session.commit()

    count = process_expired_collective_goals(teacher.id)

    assert count == 0
    db.session.refresh(item)
    assert item.is_active is True
    db.session.refresh(si)
    assert si.status == 'pending'


def test_process_expired_goals_ignores_already_inactive_items(client):
    """Already-deactivated items are not re-processed even if past the deadline."""
    teacher = _create_teacher('teacher_exp_inactive')
    student = _create_student(teacher, 'Dan', 'JOINEXP4')
    db.session.flush()

    # is_active=False and past deadline
    item = _collective_item(teacher, 'Already Inactive', 'JOINEXP4',
                            expires_at=_past(), is_active=False)
    si = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='pending',
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add(si)
    db.session.commit()

    count = process_expired_collective_goals(teacher.id)

    assert count == 0, "Inactive items should not be processed"
    db.session.refresh(si)
    assert si.status == 'pending', "Purchase should not be modified for inactive items"


def test_process_expired_goals_only_voids_pending_not_processing(client):
    """Only 'pending' StudentItems are voided; 'processing' ones (goal already met) are left alone."""
    teacher = _create_teacher('teacher_exp_processing')
    student_a = _create_student(teacher, 'Eve', 'JOINEXP5')
    student_b = _create_student(teacher, 'Frank', 'JOINEXP5B', block='B')
    db.session.flush()

    item = _collective_item(teacher, 'Mixed Status Goal', 'JOINEXP5', expires_at=_past())

    si_processing = StorePurchase(
        seat_id=student_a.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='processing',  # Goal was already met for this student
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    si_pending = StorePurchase(
        seat_id=student_b.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='pending',
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add_all([si_processing, si_pending])
    db.session.commit()

    process_expired_collective_goals(teacher.id)

    db.session.refresh(si_processing)
    db.session.refresh(si_pending)

    # 'processing' item should be untouched
    assert si_processing.status == 'processing', "'processing' purchases must not be voided"
    # 'pending' item should be voided
    assert si_pending.status == 'voided', "'pending' purchase should be voided on expiration"


def test_process_expired_goals_skips_met_goals_with_no_pending(client):
    """An expired goal with no pending purchases (already met/unlocked) is not deactivated."""
    teacher = _create_teacher('teacher_exp_met')
    student = _create_student(teacher, 'Fay', 'JOINEXPMET')
    db.session.flush()

    item = _collective_item(teacher, 'Met Goal', 'JOINEXPMET', expires_at=_past())
    si_processing = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='processing',
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add(si_processing)
    db.session.commit()

    count = process_expired_collective_goals(teacher.id)

    assert count == 0, "Met goals with no pending purchases should not be expired"
    db.session.refresh(item)
    assert item.is_active is True, "Item should remain active when goal was already met"
    db.session.refresh(si_processing)
    assert si_processing.status == 'processing'


def test_process_expired_goals_scoped_to_teacher(client):
    """Expiration only processes items belonging to the specified teacher."""
    teacher_a = _create_teacher('teacher_exp_scope_a')
    teacher_b = _create_teacher('teacher_exp_scope_b')
    student_a = _create_student(teacher_a, 'Grace', 'JOINEXPA')
    student_b = _create_student(teacher_b, 'Hank', 'JOINEXPB')
    db.session.flush()

    expired_item_a = _collective_item(teacher_a, 'Teacher A Expired', 'JOINEXPA', expires_at=_past())
    expired_item_b = _collective_item(teacher_b, 'Teacher B Expired', 'JOINEXPB', expires_at=_past())

    si_a = StorePurchase(
        seat_id=student_a.id,
        class_id=expired_item_a.class_id,
        store_item_id=expired_item_a.id,
        quantity=1,
        price_at_purchase=expired_item_a.price,
        total_price=expired_item_a.price,
        status='pending',
        collective_goal_instance_code=expired_item_a.collective_goal_instance_code,
    )
    si_b = StorePurchase(
        seat_id=student_b.id,
        class_id=expired_item_b.class_id,
        store_item_id=expired_item_b.id,
        quantity=1,
        price_at_purchase=expired_item_b.price,
        total_price=expired_item_b.price,
        status='pending',
        collective_goal_instance_code=expired_item_b.collective_goal_instance_code,
    )
    db.session.add_all([si_a, si_b])
    db.session.commit()

    # Process only teacher A's items
    count = process_expired_collective_goals(teacher_a.id)

    assert count == 1

    db.session.refresh(si_a)
    db.session.refresh(si_b)
    db.session.refresh(expired_item_a)
    db.session.refresh(expired_item_b)

    # Teacher A's item and student item affected
    assert expired_item_a.is_active is False
    assert si_a.status == 'voided'

    # Teacher B's item and student item should be untouched
    assert expired_item_b.is_active is True
    assert si_b.status == 'pending'


def test_process_expired_goals_refund_fallback_to_item_price(client):
    """When no original purchase transaction is found, refund falls back to item price."""
    teacher = _create_teacher('teacher_exp_fallback')
    student = _create_student(teacher, 'Ivy', 'JOINEXPFB')
    db.session.flush()

    item = _collective_item(teacher, 'No TX Item', 'JOINEXPFB', expires_at=_past())
    # StudentItem with no corresponding purchase Transaction
    si = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='pending',
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add(si)
    db.session.commit()

    process_expired_collective_goals(teacher.id)

    refund_txs = Transaction.query.filter_by(
        user_id=student.user_id,
        type='refund',
    ).all()
    assert len(refund_txs) == 1
    assert refund_txs[0].amount == item.price, "Should fall back to item price when no purchase tx found"


# ---------------------------------------------------------------------------
# refund_pending_collective_purchases utility (called on teacher delete)
# ---------------------------------------------------------------------------

def test_refund_pending_collective_purchases_marks_voided_and_creates_refund(client):
    """refund_pending_collective_purchases voids all pending items and creates refund txs."""
    teacher = _create_teacher('teacher_refund_direct')
    student = _create_student(teacher, 'Jay', 'JOINREFUND')
    db.session.flush()

    item = _collective_item(teacher, 'Direct Refund Item', 'JOINREFUND', expires_at=None)
    purchase_tx = Transaction(
        seat_id=student.id, user_id=student.user_id, amount=Decimal('-10.00'),
        account_type='checking', type='purchase',
        description=f'Purchase: {item.name}',
    )
    db.session.add(purchase_tx)
    db.session.flush()

    si = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='pending',
        ledger_tx_id=purchase_tx.id,
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add(si)
    db.session.commit()

    count = refund_pending_collective_purchases(item, description_suffix='Teacher Removed')
    db.session.commit()

    assert count == 1
    db.session.refresh(si)
    assert si.status == 'voided'

    refund_txs = Transaction.query.filter_by(
        seat_id=student.id, type='refund'
    ).all()
    assert len(refund_txs) == 1
    assert 'Teacher Removed' in refund_txs[0].description


def test_refund_matching_uses_purchase_transaction_id_after_item_rename(client):
    """Refund matching should remain correct even if the store item name changes."""
    teacher = _create_teacher('teacher_refund_id_match')
    student = _create_student(teacher, 'Jules', 'JOINIDMATCH')
    db.session.flush()

    item = _collective_item(teacher, 'Original Name', 'JOINIDMATCH')
    purchase_tx = Transaction(
        seat_id=student.id, user_id=student.user_id, amount=Decimal('-13.00'),
        account_type='checking', type='purchase',
        description='Purchase: Original Name',
    )
    db.session.add(purchase_tx)
    db.session.flush()

    si = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='pending',
        ledger_tx_id=purchase_tx.id,
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add(si)

    item.name = 'Renamed Item'
    item.price = Decimal('99.00')
    db.session.commit()

    count = refund_pending_collective_purchases(item, description_suffix='Teacher Removed')
    db.session.commit()

    assert count == 1
    refund_tx = Transaction.query.filter_by(
        seat_id=student.id, type='refund'
    ).one()
    assert refund_tx.amount == Decimal('13.00'), "Refund should use linked purchase transaction amount"
    assert refund_tx.original_transaction_id == purchase_tx.id


def test_refund_pending_skips_non_pending_statuses(client):
    """refund_pending_collective_purchases does not touch 'processing' or 'completed' items."""
    teacher = _create_teacher('teacher_refund_skip')
    student = _create_student(teacher, 'Kim', 'JOINSKIP')
    db.session.flush()

    item = _collective_item(teacher, 'Skip Status Item', 'JOINSKIP')
    si_proc = StorePurchase(seat_id=student.id, class_id=item.class_id, store_item_id=item.id, quantity=1, price_at_purchase=item.price, total_price=item.price, status='processing', collective_goal_instance_code=item.collective_goal_instance_code)
    si_comp = StorePurchase(seat_id=student.id, class_id=item.class_id, store_item_id=item.id, quantity=1, price_at_purchase=item.price, total_price=item.price, status='completed', collective_goal_instance_code=item.collective_goal_instance_code)
    db.session.add_all([si_proc, si_comp])
    db.session.commit()

    count = refund_pending_collective_purchases(item, description_suffix='Test')
    db.session.commit()

    assert count == 0
    db.session.refresh(si_proc)
    db.session.refresh(si_comp)
    assert si_proc.status == 'processing'
    assert si_comp.status == 'completed'


# ---------------------------------------------------------------------------
# Admin delete route triggers refund
# ---------------------------------------------------------------------------

def test_delete_active_collective_item_refunds_pending(client):
    """DELETE /admin/store/delete/<id> refunds pending purchases before deactivating."""
    teacher = _create_teacher('teacher_del_refund')
    student = _create_student(teacher, 'Leo', 'JOINDEL')
    db.session.flush()

    item = _collective_item(teacher, 'Delete Me', 'JOINDEL')
    db.session.add(ClassFeature(class_id=item.class_id, feature_name='store'))
    purchase_tx = Transaction(
        seat_id=student.id,
        user_id=student.user_id, amount=Decimal('-10.00'),
        account_type='checking', type='purchase',
        description=f'Purchase: {item.name}',
    )
    db.session.add(purchase_tx)
    db.session.flush()

    si = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='pending',
        ledger_tx_id=purchase_tx.id,
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add(si)
    db.session.commit()

    _login_admin(client, teacher.id, 'JOINDEL')
    resp = client.post(f'/admin/store/delete/{item.id}')
    # Redirect expected after delete
    assert resp.status_code in (200, 302)

    db.session.refresh(item)
    assert item.is_active is False, "Item should be deactivated"

    db.session.refresh(si)
    assert si.status == 'voided', "Pending purchase should be voided on delete"

    refund_txs = Transaction.query.filter_by(
        user_id=student.user_id, type='refund'
    ).all()
    assert len(refund_txs) == 1, "One refund transaction should be created"


def test_delete_inactive_collective_item_does_not_refund(client):
    """Deleting an already-inactive collective item does not generate extra refunds."""
    teacher = _create_teacher('teacher_del_inactive')
    student = _create_student(teacher, 'Mia', 'JOINDELINACT')
    db.session.flush()

    item = _collective_item(teacher, 'Already Inactive Del', 'JOINDELINACT', is_active=False)
    db.session.add(ClassFeature(class_id=item.class_id, feature_name='store'))
    si = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='pending',
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add(si)
    db.session.commit()

    _login_admin(client, teacher.id, 'JOINDELINACT')
    resp = client.post(f'/admin/store/delete/{item.id}')
    assert resp.status_code in (200, 302)

    db.session.refresh(si)
    # Pending items are NOT refunded when the item was already inactive
    assert si.status == 'pending', "Pending items should not be voided for already-inactive items"

    refund_txs = Transaction.query.filter_by(
        user_id=student.user_id, type='refund'
    ).all()
    assert len(refund_txs) == 0, "No refund transactions should be created for inactive items"


# ---------------------------------------------------------------------------
# Purchase API blocks expired goals
# ---------------------------------------------------------------------------

def test_purchase_blocked_when_collective_goal_expired(client):
    """POST /api/purchase-item returns 400 when the collective goal has expired."""
    teacher = _create_teacher('teacher_api_expired')
    student = _create_student(teacher, 'Nora', 'JOINAPIEXP')
    db.session.flush()

    item = _collective_item(teacher, 'Expired API Goal', 'JOINAPIEXP', expires_at=_past())
    db.session.add(ClassFeature(class_id=item.class_id, feature_name='store'))
    db.session.commit()

    _login_student(client, student.user_id, 'JOINAPIEXP')
    resp = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert 'expired' in data['message'].lower()

    # No store purchase should be created
    assert StorePurchase.query.filter_by(
        seat_id=student.id, store_item_id=item.id
    ).count() == 0


def test_purchase_allowed_for_non_expired_collective_goal(client):
    """POST /api/purchase-item succeeds for a collective goal with a future expiration."""
    teacher = _create_teacher('teacher_api_future')
    student = _create_student(teacher, 'Owen', 'JOINAPIFUT')
    db.session.flush()

    item = _collective_item(teacher, 'Future API Goal', 'JOINAPIFUT', expires_at=_future())
    db.session.add(ClassFeature(class_id=item.class_id, feature_name='store'))
    db.session.commit()

    _login_student(client, student.user_id, 'JOINAPIFUT')
    resp = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp.status_code == 200
    assert StorePurchase.query.filter_by(
        seat_id=student.id, store_item_id=item.id).count() == 1


# ---------------------------------------------------------------------------
# Reactivated item starts at zero progress
# ---------------------------------------------------------------------------

def test_reactivated_item_voided_purchases_excluded_from_progress(client):
    """
    After expiration, voided StudentItems are not counted toward goal progress.
    When the teacher reactivates the item, progress effectively starts at zero.
    """
    teacher = _create_teacher('teacher_reactivate')
    student = _create_student(teacher, 'Pam', 'JOINREACT')
    db.session.flush()

    item = _collective_item(teacher, 'Reactivated Goal',
                            goal_type='fixed', target=2, expires_at=_past())
    db.session.add(ClassFeature(class_id=item.class_id, feature_name='store'))

    # Simulate a previously-voided purchase (from a prior expiration cycle)
    si_voided = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='voided',
        collective_goal_instance_code="OLD_INSTANCE_CODE",
    )
    db.session.add(si_voided)

    # Reactivate the item
    item.is_active = True
    item.collective_goal_expires_at = _future()
    db.session.commit()

    # Student views the shop — progress should be 0, not 1
    _login_student(client, student.user_id, 'JOINREACT')
    resp = client.get('/student/shop')
    assert resp.status_code == 200
    # Voided items must not count toward the displayed progress
    assert b'0/2' in resp.data


def test_process_expired_goals_multiple_items_same_teacher(client):
    """Multiple expired items for the same teacher are all processed in one call."""
    teacher = _create_teacher('teacher_exp_multi')
    student_a = _create_student(teacher, 'Quinn', 'JOINMULTA')
    student_b = _create_student(teacher, 'Rita', 'JOINMULTB')
    db.session.flush()

    item_a = _collective_item(teacher, 'Multi Expired A', 'JOINMULTA', expires_at=_past())
    item_b = _collective_item(teacher, 'Multi Expired B', 'JOINMULTB', expires_at=_past())

    si_a = StorePurchase(seat_id=student_a.id, class_id=item_a.class_id, store_item_id=item_a.id, quantity=1, price_at_purchase=item_a.price, total_price=item_a.price, status='pending', collective_goal_instance_code=item_a.collective_goal_instance_code)
    si_b = StorePurchase(seat_id=student_b.id, class_id=item_b.class_id, store_item_id=item_b.id, quantity=1, price_at_purchase=item_b.price, total_price=item_b.price, status='pending', collective_goal_instance_code=item_b.collective_goal_instance_code)
    db.session.add_all([si_a, si_b])
    db.session.commit()

    count = process_expired_collective_goals(teacher.id)

    assert count == 2

    for item in [item_a, item_b]:
        db.session.refresh(item)
        assert item.is_active is False

    for si in [si_a, si_b]:
        db.session.refresh(si)
        assert si.status == 'voided'


def test_shop_page_triggers_expiration_lazily(client):
    """Loading /student/shop triggers expiration processing for the teacher's items."""
    teacher = _create_teacher('teacher_lazy_exp')
    student = _create_student(teacher, 'Sam', 'JOINLAZY')
    db.session.flush()

    item = _collective_item(teacher, 'Lazy Expired Goal', 'JOINLAZY', expires_at=_past())
    db.session.add(ClassFeature(class_id=item.class_id, feature_name='store'))
    si = StorePurchase(
        seat_id=student.id,
        class_id=item.class_id,
        store_item_id=item.id,
        quantity=1,
        price_at_purchase=item.price,
        total_price=item.price,
        status='pending',
        collective_goal_instance_code=item.collective_goal_instance_code,
    )
    db.session.add(si)
    db.session.commit()

    _login_student(client, student.user_id, 'JOINLAZY')
    resp = client.get('/student/shop')
    assert resp.status_code == 200

    # Loading the shop does not mutate collective-goal expiry state in v2.
    db.session.refresh(item)
    assert item.is_active is True

    db.session.refresh(si)
    assert si.status == 'pending'
