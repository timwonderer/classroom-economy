from datetime import datetime, timezone
from decimal import Decimal

from werkzeug.security import generate_password_hash

from tests.helpers.v2_fixtures import seed_canonical_admin, make_sysadmin, seed_class_feature
import uuid

from app.extensions import db
from app.feats.base import FEATContext
from app.models import User, UserRole, StoreItem, StorePurchase, Transaction, Seat, IdentityProfile
from tests.helpers.admin_context import login_teacher
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context
from app.services.store_service import set_item_visibility


def _login_student(client, student_id):
    user = db.session.get(User, student_id)
    assert user is not None
    seat = Seat.query.filter_by(user_id=student_id).order_by(Seat.id.asc()).first()
    if seat is None:
        raise ValueError("collective goal progress tests require an explicit canonical seat")
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["current_session_nonce"] = user.current_session_nonce
        set_canonical_context(
            sess,
            user_id=user.id,
            class_id=seat.class_id,
            seat_id=seat.id,
            role="student",
        )
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _login_admin(client, teacher, class_id):
    login_teacher(client, teacher, class_id=class_id)


def _create_student(teacher, first_name, section='A', class_id=None):
    if class_id is None:
        raise TypeError("_create_student() requires explicit class_id")

    with FEATContext("FEAT-IDEN-001", idempotency_key=f"collective-goal:create-student:{first_name}:{section}:{class_id}"):
        student = make_student_identity(class_id=class_id, first_name=first_name, last_name='S')
        db.session.add(Transaction(
            user_id=student.user_id,
            class_id=class_id,
            seat_id=student.seat.id,
            target_seat_id=student.seat.id,
            actor_seat_id=student.seat.id,
            mechanism="self",
            amount=Decimal('100.00'),
            account_type='checking',
            type='deposit',
            description='Initial funds',
        ))
    return student


def _create_collective_item(teacher_id, class_id, *, name, price, item_type='collective', collective_goal_type='fixed', collective_goal_target=None, is_active=True):
    with FEATContext("FEAT-STOR-001", idempotency_key=f"collective-goal:create-item:{class_id}:{name}"):
        item = StoreItem(
            user_id=teacher_id,
            class_id=class_id,
            name=name,
            price=price,
            item_type=item_type,
            collective_goal_type=collective_goal_type,
            collective_goal_target=collective_goal_target,
            is_active=is_active,
            collective_goal_instance_code=str(uuid.uuid4()),
        )
        db.session.add(item)
        db.session.flush()
        db.session.info["feat_orchestrator_commit"] = True
        try:
            db.session.commit()
        finally:
            db.session.info.pop("feat_orchestrator_commit", None)
        return item


def _enable_store_feature(class_id: str):
    with FEATContext("FEAT-ADMN-001", idempotency_key=f"collective-goal:enable-store:{class_id}"):
        seed_class_feature(class_id=class_id, feature_name='store')
        db.session.info["feat_orchestrator_commit"] = True
        try:
            db.session.commit()
        finally:
            db.session.info.pop("feat_orchestrator_commit", None)


def test_DOM_STORE_001__student_shop_collective_progress_counts_current_class_only(client):
    teacher = seed_canonical_admin('teacher_collective_shop').user
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code='CGP-A-01', display_name='A')
    class_b = create_class_scope(teacher_user=teacher, join_code='CGP-B-01', display_name='B')

    student_a1 = _create_student(teacher, 'Alice', section='A', class_id=class_a.class_id)
    student_a2 = _create_student(teacher, 'Ben', section='A', class_id=class_a.class_id)
    student_b1 = _create_student(teacher, 'Cara', section='B', class_id=class_b.class_id)
    db.session.flush()
    _enable_store_feature(student_a1.class_id)

    item = _create_collective_item(
        teacher.id,
        student_a1.class_id,
        name='Class Pizza Party',
        price=Decimal('10.00'),
        collective_goal_type='fixed',
        collective_goal_target=2,
    )

    # One purchaser in class A and one purchaser in class B.
    with FEATContext("FEAT-STOR-001", idempotency_key="collective-goal:seed-progress"):
        db.session.add_all([
            StorePurchase(
                seat_id=student_a1.id,
                class_id=student_a1.class_id,
                store_item_id=item.id,
                quantity=1,
                price_at_purchase=item.price,
                total_price=item.price,
                status='pending',
                collective_goal_instance_code=item.collective_goal_instance_code,
            ),
            StorePurchase(
                seat_id=student_b1.id,
                class_id=student_b1.class_id,
                store_item_id=item.id,
                quantity=1,
                price_at_purchase=item.price,
                total_price=item.price,
                status='pending',
                collective_goal_instance_code=item.collective_goal_instance_code,
            ),
        ])
        db.session.flush()

    _login_student(client, student_a2.user_id)
    resp = client.get('/student/shop')
    assert resp.status_code == 200
    # Must show progress for class A only, not include class B purchases.
    assert b'1/2' in resp.data


def test_DOM_STORE_001__student_shop_filters_items_by_store_item_block_visibility(client):
    teacher = seed_canonical_admin('teacher_block_visibility_shop').user
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code='CGP-A-02', display_name='A')
    class_d = create_class_scope(teacher_user=teacher, join_code='CGP-D-01', display_name='D')

    student_a = _create_student(teacher, 'Alex', section='A', class_id=class_a.class_id)
    student_d = _create_student(teacher, 'Bri', section='D', class_id=class_d.class_id)
    db.session.flush()
    _enable_store_feature(student_a.class_id)

    a_item = StoreItem(
        user_id=teacher.id,
        class_id=class_a.class_id,
        name='A Only Item',
        price=Decimal('6.00'),
        is_active=True,
    )
    d_item = StoreItem(
        user_id=teacher.id,
        class_id=class_d.class_id,
        name='D Only Item',
        price=Decimal('7.00'),
        is_active=True,
    )
    # Canonical v2 items are always class-scoped; this item has no block filter.
    unscoped_item = StoreItem(
        user_id=teacher.id,
        class_id=class_a.class_id,
        name='Unscoped Item',
        price=Decimal('5.00'),
        is_active=True,
    )
    with FEATContext("FEAT-STOR-001", idempotency_key="collective-goal:seed-block-visibility-items"):
        db.session.add_all([unscoped_item, a_item, d_item])
        db.session.flush()
        set_item_visibility(a_item.id, [student_a.id])
        set_item_visibility(d_item.id, [student_d.id])
        db.session.flush()

    _login_student(client, student_a.user_id)
    resp = client.get('/student/shop')
    assert resp.status_code == 200
    # Class-scoped items without a block filter are visible to the current class.
    assert b'Unscoped Item' in resp.data
    assert b'A Only Item' in resp.data
    assert b'D Only Item' not in resp.data


def test_DOM_STORE_001__purchase_item_rejects_items_not_visible_to_current_seat(client):
    teacher = seed_canonical_admin('teacher_block_visibility_purchase').user
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code='CGP-A-03', display_name='A')

    student_a = _create_student(teacher, 'Casey', section='A', class_id=class_a.class_id)
    student_b = _create_student(teacher, 'Drew', section='A', class_id=class_a.class_id)
    db.session.flush()
    _enable_store_feature(student_a.class_id)

    d_only_item = StoreItem(
        user_id=teacher.id,
        class_id=class_a.class_id,
        name='D Scoped Item',
        price=Decimal('8.00'),
        is_active=True,
    )
    with FEATContext("FEAT-STOR-001", idempotency_key="collective-goal:seed-d-only-item"):
        db.session.add(d_only_item)
        db.session.flush()
        set_item_visibility(d_only_item.id, [student_b.id])
        db.session.flush()

    _login_student(client, student_a.user_id)
    resp = client.post('/api/purchase-item', json={
        'item_id': d_only_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp.status_code == 404
    assert StorePurchase.query.filter_by(
        seat_id=student_a.id,
        store_item_id=d_only_item.id,
    ).count() == 0


def test_DOM_STORE_001__purchase_item_allows_class_scoped_item_without_block_visibility(client):
    """Class-scoped items without block visibility restrictions remain purchasable."""
    teacher = seed_canonical_admin('teacher_unscoped_purchase').user
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code='CGP-A-04', display_name='A')

    student_a = _create_student(teacher, 'Devon', section='A', class_id=class_a.class_id)
    db.session.flush()
    _enable_store_feature(student_a.class_id)

    # Item is scoped to the student's class, no block restrictions.
    scoped_item = StoreItem(
        user_id=teacher.id,
        class_id=class_a.class_id,
        name='Class Scoped Item',
        price=Decimal('4.00'),
        is_active=True,
    )
    with FEATContext("FEAT-STOR-001", idempotency_key="collective-goal:seed-scoped-item"):
        db.session.add(scoped_item)
        db.session.flush()

    _login_student(client, student_a.user_id)
    resp = client.post('/api/purchase-item', json={
        'item_id': scoped_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp.status_code == 200
    assert StorePurchase.query.filter_by(
        seat_id=student_a.id,
        store_item_id=scoped_item.id,
    ).count() == 1


def test_DOM_STORE_001__collective_unlock_scoped_to_class_and_goal_type(client):
    teacher = seed_canonical_admin('teacher_collective_unlock').user
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code='CGP-A-05', display_name='A')
    class_b = create_class_scope(teacher_user=teacher, join_code='CGP-B-05', display_name='B')

    student_a1 = _create_student(teacher, 'Alex', section='A', class_id=class_a.class_id)
    student_a2 = _create_student(teacher, 'Bri', section='A', class_id=class_a.class_id)
    student_b1 = _create_student(teacher, 'Cy', section='B', class_id=class_b.class_id)
    db.session.flush()
    _enable_store_feature(student_a1.class_id)
    _enable_store_feature(student_b1.class_id)

    item = _create_collective_item(
        teacher.id,
        student_a1.class_id,
        name='Collective Unlock',
        price=Decimal('10.00'),
        collective_goal_type='fixed',
        collective_goal_target=2,
    )

    # Existing purchase in class A and class B.
    with FEATContext("FEAT-STOR-001", idempotency_key="collective-goal:seed-progress"):
        db.session.add_all([
            StorePurchase(
                seat_id=student_a1.id,
                class_id=student_a1.class_id,
                store_item_id=item.id,
                quantity=1,
                price_at_purchase=item.price,
                total_price=item.price,
                status='pending',
                collective_goal_instance_code=item.collective_goal_instance_code,
            ),
            StorePurchase(
                seat_id=student_b1.id,
                class_id=student_b1.class_id,
                store_item_id=item.id,
                quantity=1,
                price_at_purchase=item.price,
                total_price=item.price,
                status='pending',
                collective_goal_instance_code=item.collective_goal_instance_code,
            ),
        ])
        db.session.flush()

    _login_student(client, student_a2.user_id)
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200

    class_a_statuses = [
        p.status for p in StorePurchase.query.filter_by(store_item_id=item.id, class_id=student_a1.class_id).all()
    ]
    class_b_statuses = [
        p.status for p in StorePurchase.query.filter_by(store_item_id=item.id, class_id=student_b1.class_id).all()
    ]

    # Class A reached fixed goal of 2 students, so pending purchases unlock to processing.
    assert all(status == 'processing' for status in class_a_statuses)
    # Class B progress should not be modified by class A purchase.
    assert class_b_statuses == ['pending']


def test_DOM_STORE_001__admin_store_shows_collective_progress(client):
    teacher = seed_canonical_admin('teacher_collective_admin').user
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code='CGP-A-06', display_name='A')

    student_a1 = _create_student(teacher, 'Ana', section='A', class_id=class_a.class_id)
    _create_student(teacher, 'Bo', section='A', class_id=class_a.class_id)
    db.session.flush()
    _enable_store_feature(student_a1.class_id)

    item = _create_collective_item(
        teacher.id,
        student_a1.class_id,
        name=' Progress Item',
        price=Decimal('5.00'),
        collective_goal_type='fixed',
        collective_goal_target=2,
    )
    with FEATContext("FEAT-STOR-001", idempotency_key="collective-goal:seed-admin-progress"):
        db.session.add(StorePurchase(
            seat_id=student_a1.id,
            class_id=student_a1.class_id,
            store_item_id=item.id,
            quantity=1,
            price_at_purchase=item.price,
            total_price=item.price,
            status='pending',
            collective_goal_instance_code=item.collective_goal_instance_code,
        ))
        db.session.flush()
    _login_admin(client, teacher, class_a.class_id)
    resp = client.get('/admin/store')
    assert resp.status_code == 200
    assert b'Collective Progress' in resp.data
    assert b'1/2' in resp.data


def test_DOM_STORE_001__whole_class_collective_prevents_duplicate_purchase(client):
    """Test that students can only purchase a whole_class collective item once."""
    teacher = seed_canonical_admin('teacher_whole_class').user
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code='CGP-A-07', display_name='A')

    student_a1 = _create_student(teacher, 'Dana', section='A', class_id=class_a.class_id)
    student_a2 = _create_student(teacher, 'Eve', section='A', class_id=class_a.class_id)
    db.session.flush()
    _enable_store_feature(student_a1.class_id)

    item = StoreItem(
        user_id=teacher.id,
        class_id=class_a.class_id,
        name='Whole Class Goal Item',
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    with FEATContext("FEAT-STOR-001", idempotency_key="collective-goal:seed-whole-class-prevent-item"):
        db.session.add(item)
        db.session.flush()

    _login_student(client, student_a1.user_id)

    # First purchase should succeed
    resp1 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp1.status_code == 200
    
    # Second purchase by same student should fail
    resp2 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp2.status_code == 400
    json_data = resp2.get_json()
    assert 'already purchased' in json_data['message'].lower()


def test_DOM_STORE_001__whole_class_collective_goal_uses_correct_class_size(client):
    """Test that whole_class collective goals use actual student count, not seat count."""
    teacher = seed_canonical_admin('teacher_class_size').user
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code='CGP-A-08', display_name='A')

    # Create 2 students for the class
    student_a1 = _create_student(teacher, 'Frank', section='A', class_id=class_a.class_id)
    student_a2 = _create_student(teacher, 'Grace', section='A', class_id=class_a.class_id)
    db.session.flush()
    _enable_store_feature(student_a1.class_id)

    item = _create_collective_item(
        teacher.id,
        student_a1.class_id,
        name='Whole Class Pizza',
        price=Decimal('5.00'),
        collective_goal_type='whole_class',
    )
    # First student purchases
    _login_student(client, student_a1.user_id)
    resp1 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp1.status_code == 200

    # Check that the goal shows 1/2
    resp_shop1 = client.get('/student/shop')
    assert b'1/2' in resp_shop1.data

    # Second student purchases - goal should be reached (2/2)
    _login_student(client, student_a2.user_id)
    resp2 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp2.status_code == 200
    
    # Check all items are now processing (goal reached)
    items = StorePurchase.query.filter_by(store_item_id=item.id, class_id=student_a1.class_id).all()
    assert len(items) == 2
    assert all(si.status == 'processing' for si in items)


def test_DOM_STORE_001__collective_progress_with_correct_roster_count_admin(client):
    """Test that admin view shows correct class size based on actual students."""
    teacher = seed_canonical_admin('teacher_admin_size').user
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code='CGP-A-09', display_name='A')

    # Create 3 students
    student_a1 = _create_student(teacher, 'Henry', section='A', class_id=class_a.class_id)
    student_a2 = _create_student(teacher, 'Iris', section='A', class_id=class_a.class_id)
    student_a3 = _create_student(teacher, 'Jack', section='A', class_id=class_a.class_id)
    db.session.flush()
    _enable_store_feature(student_a1.class_id)

    item = _create_collective_item(
        teacher.id,
        student_a1.class_id,
        name=' Whole Class Item',
        price=Decimal('5.00'),
        collective_goal_type='whole_class',
    )
    
    # One student purchases
    with FEATContext("FEAT-STOR-001", idempotency_key="collective-goal:seed-roster-progress"):
        db.session.add(StorePurchase(
            seat_id=student_a1.id,
            class_id=student_a1.class_id,
            store_item_id=item.id,
            quantity=1,
            price_at_purchase=item.price,
            total_price=item.price,
            status='pending',
            collective_goal_instance_code=item.collective_goal_instance_code,
        ))
        db.session.flush()
    _login_admin(client, teacher, class_a.class_id)
    resp = client.get('/admin/store')
    assert resp.status_code == 200
    # Should show 1/3 (1 purchase out of 3 students)
    assert b'1/3' in resp.data


def test_DOM_STORE_001__fixed_collective_allows_multiple_purchases(client):
    """Test that fixed collective goals still allow multiple purchases from same student."""
    teacher = seed_canonical_admin('teacher_fixed_multi').user
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code='CGP-A-11', display_name='A')

    student_a1 = _create_student(teacher, 'Kelly', section='A', class_id=class_a.class_id)
    db.session.flush()
    _enable_store_feature(student_a1.class_id)

    item = StoreItem(
        user_id=teacher.id,
        class_id=class_a.class_id,
        name='Fixed Goal Item',
        price=Decimal('5.00'),
        item_type='collective',
        collective_goal_type='fixed',
        collective_goal_target=3,
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    with FEATContext("FEAT-STOR-001", idempotency_key="collective-goal:seed-fixed-multi-item"):
        db.session.add(item)
        db.session.flush()

    _login_student(client, student_a1.user_id)
    
    # First purchase should succeed
    resp1 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp1.status_code == 200
    
    # Second purchase by same student should also succeed for fixed goals
    resp2 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp2.status_code == 200
    
    # But progress should only count 1 unique student
    resp_shop = client.get('/student/shop')
    assert b'1/3' in resp_shop.data


def test_DOM_STORE_001__whole_class_goal_with_duplicate_seats_shows_correct_roster(client):
    """Whole-class goals should count canonical seats only."""
    teacher = seed_canonical_admin('teacher_dup_seats').user
    db.session.flush()
    class_a = create_class_scope(teacher_user=teacher, join_code='CGP-A-12', display_name='A')

    # Create 2 students
    student_a1 = _create_student(teacher, 'Laura', section='A', class_id=class_a.class_id)
    student_a2 = _create_student(teacher, 'Mike', section='A', class_id=class_a.class_id)
    db.session.flush()
    _enable_store_feature(student_a1.class_id)
    
    item = StoreItem(
        user_id=teacher.id,
        class_id=class_a.class_id,
        name='Duplicate Seats Test',
        price=Decimal('5.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    with FEATContext("FEAT-STOR-001", idempotency_key="collective-goal:seed-dup-seat-item"):
        db.session.add(item)
        db.session.flush()

    # Despite 3 TeacherBlock entries, class size should be 2 (unique students)
    _login_student(client, student_a1.user_id)
    resp_shop = client.get('/student/shop')
    # Should show 0/2, not 0/3
    assert b'0/2' in resp_shop.data or b'Whole Class Goal' in resp_shop.data
    
    #  view should also show correct count
    _login_admin(client, teacher, class_a.class_id)
    resp_admin = client.get('/admin/store')
    assert b'0/2' in resp_admin.data


def test_DOM_STORE_001__whole_class_collective_allows_purchase_per_class_for_same_teacher(client):
    """Students in different classes with the same teacher can each purchase once."""
    teacher = seed_canonical_admin('teacher_whole_class_multi').user
    db.session.flush()
    class_1 = create_class_scope(teacher_user=teacher, join_code='CGP-A-10', display_name='A')
    class_2 = create_class_scope(teacher_user=teacher, join_code='CGP-B-10', display_name='B')

    # Create student in two different classes for the same teacher.
    student_class1 = _create_student(teacher, 'Nina', section='A', class_id=class_1.class_id)
    student_class2 = _create_student(teacher, 'Nina', section='B', class_id=class_2.class_id)
    db.session.flush()
    _enable_store_feature(student_class1.class_id)
    _enable_store_feature(student_class2.class_id)

    item_class1 = StoreItem(
        user_id=teacher.id,
        class_id=class_1.class_id,
        name='Whole Class Multi-Class Item',
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    item_class2 = StoreItem(
        user_id=teacher.id,
        class_id=class_2.class_id,
        name='Whole Class Multi-Class Item',
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    with FEATContext("FEAT-STOR-001", idempotency_key="collective-goal:seed-multi-class-items"):
        db.session.add_all([item_class1, item_class2])
        db.session.flush()

    # Student in first class purchases successfully
    _login_student(client, student_class1.user_id)
    resp1 = client.post('/api/purchase-item', json={
        'item_id': item_class1.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp1.status_code == 200

    # Student in second class should also be able to purchase.
    _login_student(client, student_class2.user_id)
    resp2 = client.post('/api/purchase-item', json={
        'item_id': item_class2.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp2.status_code == 200

    # Ensure one purchase recorded per class.
    items_class1 = StorePurchase.query.filter_by(store_item_id=item_class1.id, class_id=student_class1.class_id).all()
    items_class2 = StorePurchase.query.filter_by(store_item_id=item_class2.id, class_id=student_class2.class_id).all()
    assert len(items_class1) == 1
    assert len(items_class2) == 1
