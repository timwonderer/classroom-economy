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
from uuid import uuid4

from werkzeug.security import generate_password_hash

from app.feats.base import FEATContext
from tests.helpers.v2_fixtures import seed_canonical_admin
from app.extensions import db
from app.models import ClassEconomy
from app.models import User, UserRole, StoreItem, StorePurchase, Transaction, Seat, ClassEconomy, ClassFeature
from app.utils.store import process_expired_collective_goals, refund_pending_collective_purchases
from tests.helpers.admin_context import login_admin
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context


def _login_student(client, student_id):
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


def _login_admin(client, teacher, class_id):
    login_admin(client, teacher, class_id=class_id)


def _create_teacher(username):
    """Create an Admin (teacher) and flush to get an id."""
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"FEAT-IDEN-001:test-create-teacher:{username}:{uuid4().hex}"):
        teacher = seed_canonical_admin(username).user
        db.session.flush()
        return teacher


def _create_student(class_id, first_name):
    """Create canonical student identity enrolled in the provided class."""
    with FEATContext("FEAT-IDEN-001", idempotency_key=f"FEAT-IDEN-001:test-create-student:{class_id}:{first_name}:{uuid4().hex}"):
        seat = make_student_identity(
            class_id=class_id,
            first_name=first_name,
            last_name="Smith",
            claimed=True,
        )
        # Give the student funds so purchases succeed.
        db.session.add(Transaction(
            seat_id=seat.id,
            user_id=seat.user_id,
            class_id=class_id,
            amount=Decimal('100.00'),
            account_type='checking',
            type='deposit',
            description='Initial funds',
        ))
        db.session.flush()
        return seat


def _collective_item(teacher_id, class_id, name, goal_type='fixed', target=2,
                     expires_at=None, is_active=True):
    """Create a collective StoreItem."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-collective-item:{class_id}:{name}:{uuid4().hex}"):
        item = StoreItem(
            user_id=teacher_id,
            class_id=class_id,
            name=name,
            price=Decimal('10.00'),
            item_type='collective',
            collective_goal_type=goal_type,
            collective_goal_target=target if goal_type == 'fixed' else None,
            collective_goal_expires_at=expires_at,
            is_active=is_active,
            collective_goal_instance_code=str(uuid4())
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
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-expired-refund:{uuid4().hex}"):
        teacher = _create_teacher('teacher_exp_refund')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Alice')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Expired Pizza', expires_at=_past())

        # Create a purchase transaction and a pending StorePurchase
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
        db.session.flush()

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
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-expired-future:{uuid4().hex}"):
        teacher = _create_teacher('teacher_exp_future')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Bob')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Future Goal', expires_at=_future())
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
        db.session.flush()

        count = process_expired_collective_goals(teacher.id)

        assert count == 0, "No items should be processed for future expiration"

        db.session.refresh(item)
        assert item.is_active is True, "Item should remain active"

        db.session.refresh(si)
        assert si.status == 'pending', "Purchase status should be unchanged"


def test_process_expired_goals_ignores_items_without_expiration(client):
    """Items with no expiration date are never auto-expired."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-expired-none:{uuid4().hex}"):
        teacher = _create_teacher('teacher_exp_none')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Carol')
        db.session.flush()

        # No expires_at set
        item = _collective_item(teacher.id, class_row.class_id, 'No Expiry Goal', expires_at=None)
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
        db.session.flush()

        count = process_expired_collective_goals(teacher.id)

        assert count == 0
        db.session.refresh(item)
        assert item.is_active is True
        db.session.refresh(si)
        assert si.status == 'pending'


def test_process_expired_goals_ignores_already_inactive_items(client):
    """Already-deactivated items are not re-processed even if past the deadline."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-expired-inactive:{uuid4().hex}"):
        teacher = _create_teacher('teacher_exp_inactive')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Dan')
        db.session.flush()

        # is_active=False and past deadline
        item = _collective_item(teacher.id, class_row.class_id, 'Already Inactive',
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
        db.session.flush()

        count = process_expired_collective_goals(teacher.id)

        assert count == 0, "Inactive items should not be processed"
        db.session.refresh(si)
        assert si.status == 'pending', "Purchase should not be modified for inactive items"


def test_process_expired_goals_only_voids_pending_not_processing(client):
    """Only 'pending' StudentItems are voided; 'processing' ones (goal already met) are left alone."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-expired-processing:{uuid4().hex}"):
        teacher = _create_teacher('teacher_exp_processing')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student_a = _create_student(class_row.class_id, 'Eve')
        student_b = _create_student(class_row.class_id, 'Frank')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Mixed Status Goal', expires_at=_past())

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
        db.session.flush()

        process_expired_collective_goals(teacher.id)

        db.session.refresh(si_processing)
        db.session.refresh(si_pending)

        assert si_processing.status == 'processing', "'processing' purchases must not be voided"
        assert si_pending.status == 'voided', "'pending' purchase should be voided on expiration"


def test_process_expired_goals_skips_met_goals_with_no_pending(client):
    """An expired goal with no pending purchases (already met/unlocked) is not deactivated."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-expired-met:{uuid4().hex}"):
        teacher = _create_teacher('teacher_exp_met')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Fay')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Met Goal', expires_at=_past())
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
        db.session.flush()

        count = process_expired_collective_goals(teacher.id)

        assert count == 0, "Met goals with no pending purchases should not be expired"
        db.session.refresh(item)
        assert item.is_active is True, "Item should remain active when goal was already met"
        db.session.refresh(si_processing)
        assert si_processing.status == 'processing'


def test_process_expired_goals_scoped_to_teacher(client):
    """Expiration only processes items belonging to the specified teacher."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-expired-scope:{uuid4().hex}"):
        teacher_a = _create_teacher('teacher_exp_scope_a')
        teacher_b = _create_teacher('teacher_exp_scope_b')
        class_row_a = create_class_scope(teacher_user=teacher_a, display_name='A')
        class_row_b = create_class_scope(teacher_user=teacher_b, display_name='B')
        student_a = _create_student(class_row_a.class_id, 'Grace')
        student_b = _create_student(class_row_b.class_id, 'Hank')
        db.session.flush()

        expired_item_a = _collective_item(teacher_a.id, class_row_a.class_id, 'Teacher A Expired', expires_at=_past())
        expired_item_b = _collective_item(teacher_b.id, class_row_b.class_id, 'Teacher B Expired', expires_at=_past())

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
        db.session.flush()

        count = process_expired_collective_goals(teacher_a.id)

        assert count == 1

        db.session.refresh(si_a)
        db.session.refresh(si_b)
        db.session.refresh(expired_item_a)
        db.session.refresh(expired_item_b)

        assert expired_item_a.is_active is False
        assert si_a.status == 'voided'

        assert expired_item_b.is_active is True
        assert si_b.status == 'pending'


def test_process_expired_goals_refund_fallback_to_item_price(client):
    """When no original purchase transaction is found, refund falls back to item price."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-expired-fallback:{uuid4().hex}"):
        teacher = _create_teacher('teacher_exp_fallback')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Ivy')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'No TX Item', expires_at=_past())
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
        db.session.flush()

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
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-refund-pending:{uuid4().hex}"):
        teacher = _create_teacher('teacher_refund_direct')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Jay')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Direct Refund Item', expires_at=None)
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
        db.session.flush()

        count = refund_pending_collective_purchases(item, description_suffix='Teacher Removed')
        db.session.flush()

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
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-refund-id-match:{uuid4().hex}"):
        teacher = _create_teacher('teacher_refund_id_match')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Jules')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Original Name')
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
        db.session.flush()

        count = refund_pending_collective_purchases(item, description_suffix='Teacher Removed')
        db.session.flush()

        assert count == 1
        refund_tx = Transaction.query.filter_by(
            seat_id=student.id, type='refund'
        ).one()
        assert refund_tx.amount == Decimal('13.00'), "Refund should use linked purchase transaction amount"
        assert refund_tx.original_transaction_id == purchase_tx.id


def test_refund_pending_skips_non_pending_statuses(client):
    """refund_pending_collective_purchases does not touch 'processing' or 'completed' items."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-refund-skip:{uuid4().hex}"):
        teacher = _create_teacher('teacher_refund_skip')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Kim')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Skip Status Item')
        si_proc = StorePurchase(seat_id=student.id, class_id=item.class_id, store_item_id=item.id, quantity=1, price_at_purchase=item.price, total_price=item.price, status='processing', collective_goal_instance_code=item.collective_goal_instance_code)
        si_comp = StorePurchase(seat_id=student.id, class_id=item.class_id, store_item_id=item.id, quantity=1, price_at_purchase=item.price, total_price=item.price, status='completed', collective_goal_instance_code=item.collective_goal_instance_code)
        db.session.add_all([si_proc, si_comp])
        db.session.flush()

        count = refund_pending_collective_purchases(item, description_suffix='Test')
        db.session.flush()

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
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-delete-refund:{uuid4().hex}"):
        teacher = _create_teacher('teacher_del_refund')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Leo')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Delete Me')
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
        db.session.flush()

        _login_admin(client, teacher, class_row.class_id)
        resp = client.post(f'/admin/store/delete/{item.id}')
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
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-delete-inactive:{uuid4().hex}"):
        teacher = _create_teacher('teacher_del_inactive')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Mia')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Already Inactive Del', is_active=False)
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
        db.session.flush()

        _login_admin(client, teacher, class_row.class_id)
        resp = client.post(f'/admin/store/delete/{item.id}')
        assert resp.status_code in (200, 302)

        db.session.refresh(si)
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
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-purchase-expired:{uuid4().hex}"):
        teacher = _create_teacher('teacher_api_expired')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Nora')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Expired API Goal', expires_at=_past())
        db.session.add(ClassFeature(class_id=item.class_id, feature_name='store'))
        db.session.flush()

        _login_student(client, student.user_id)
        resp = client.post('/api/purchase-item', json={
            'item_id': item.id,
            'passphrase': 'password',
            'quantity': 1,
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'expired' in data['message'].lower()

        assert StorePurchase.query.filter_by(
            seat_id=student.id, store_item_id=item.id
        ).count() == 0


def test_purchase_allowed_for_non_expired_collective_goal(client):
    """POST /api/purchase-item succeeds for a collective goal with a future expiration."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-purchase-future:{uuid4().hex}"):
        teacher = _create_teacher('teacher_api_future')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Owen')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Future API Goal', expires_at=_future())
        db.session.add(ClassFeature(class_id=item.class_id, feature_name='store'))
        db.session.flush()

        _login_student(client, student.user_id)
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
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-reactivated-progress:{uuid4().hex}"):
        teacher = _create_teacher('teacher_reactivate')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Pam')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Reactivated Goal',
                                goal_type='fixed', target=2, expires_at=_past())
        db.session.add(ClassFeature(class_id=item.class_id, feature_name='store'))
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

        item.is_active = True
        item.collective_goal_expires_at = _future()
        db.session.flush()

        _login_student(client, student.user_id)
        resp = client.get('/student/shop')
        assert resp.status_code == 200
        assert b'0/2' in resp.data


def test_process_expired_goals_multiple_items_same_teacher(client):
    """Multiple expired items for the same teacher are all processed in one call."""
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-expired-multi:{uuid4().hex}"):
        teacher = _create_teacher('teacher_exp_multi')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student_a = _create_student(class_row.class_id, 'Quinn')
        student_b = _create_student(class_row.class_id, 'Rita')
        db.session.flush()

        item_a = _collective_item(teacher.id, class_row.class_id, 'Multi Expired A', expires_at=_past())
        item_b = _collective_item(teacher.id, class_row.class_id, 'Multi Expired B', expires_at=_past())
        si_a = StorePurchase(seat_id=student_a.id, class_id=item_a.class_id, store_item_id=item_a.id, quantity=1, price_at_purchase=item_a.price, total_price=item_a.price, status='pending', collective_goal_instance_code=item_a.collective_goal_instance_code)
        si_b = StorePurchase(seat_id=student_b.id, class_id=item_b.class_id, store_item_id=item_b.id, quantity=1, price_at_purchase=item_b.price, total_price=item_b.price, status='pending', collective_goal_instance_code=item_b.collective_goal_instance_code)
        db.session.add_all([si_a, si_b])
        db.session.flush()

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
    with FEATContext("FEAT-STOR-002", idempotency_key=f"FEAT-STOR-002:test-lazy-expiration:{uuid4().hex}"):
        teacher = _create_teacher('teacher_lazy_exp')
        class_row = create_class_scope(teacher_user=teacher, display_name='A')
        student = _create_student(class_row.class_id, 'Sam')
        db.session.flush()

        item = _collective_item(teacher.id, class_row.class_id, 'Lazy Expired Goal', expires_at=_past())
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
        db.session.flush()

        _login_student(client, student.user_id)
        resp = client.get('/student/shop')
        assert resp.status_code == 200

        db.session.refresh(item)
        assert item.is_active is True

        db.session.refresh(si)
        assert si.status == 'pending'
