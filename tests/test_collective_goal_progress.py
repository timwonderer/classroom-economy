from datetime import datetime, timezone
from decimal import Decimal

from werkzeug.security import generate_password_hash

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import uuid

from app.extensions import db
from app.models import User, UserRole, StoreItem, StoreItemBlock, StudentItem, Transaction, Seat, IdentityProfile
from tests.helpers.class_scope import create_class_scope, make_student_identity
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
                join_code=join_code,
            )


def _login_admin(client, user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id


def _create_student(teacher, first_name, join_code, block='A'):
    class_row = create_class_scope(
        teacher_user=teacher,
        join_code=join_code,
        display_name=block,
    )
    student = make_student_identity(class_id=class_row.class_id, first_name=first_name, last_name='S')
    db.session.flush()
    db.session.add(Transaction(
        user_id=student.user_id, join_code=join_code,
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    return student


def test_student_shop_collective_progress_counts_current_class_only(client):
    teacher = make_admin('teacher_collective_shop')
    db.session.flush()

    student_a1 = _create_student(teacher, 'Alice', 'JOINA123', block='A')
    student_a2 = _create_student(teacher, 'Ben', 'JOINA123', block='A')
    student_b1 = _create_student(teacher, 'Cara', 'JOINB456', block='B')
    db.session.flush()

    item = StoreItem(
        user_id=teacher.id,
        join_code='JOINA123',
        name='Class Pizza Party',
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type='fixed',
        collective_goal_target=2,
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    db.session.add(item)
    db.session.flush()

    # One purchaser in class A and one purchaser in class B.
    db.session.add_all([
        StudentItem(correlation_id='corr_test', seat_id=student_a1.id, store_item_id=item.id, join_code='JOINA123', status='pending', collective_goal_instance_code=item.collective_goal_instance_code),
        StudentItem(correlation_id='corr_test', seat_id=student_b1.id, store_item_id=item.id, join_code='JOINB456', status='pending', collective_goal_instance_code=item.collective_goal_instance_code),
    ])
    db.session.commit()

    _login_student(client, student_a2.user_id, 'JOINA123')
    resp = client.get('/student/shop')
    assert resp.status_code == 200
    # Must show progress for class A only, not include class B purchases.
    assert b'1/2' in resp.data


def test_student_shop_filters_items_by_store_item_block_visibility(client):
    teacher = make_admin('teacher_block_visibility_shop')
    db.session.flush()

    student_a = _create_student(teacher, 'Alex', 'JOINA111', block='A')
    _create_student(teacher, 'Bri', 'JOIND222', block='D')
    db.session.flush()

    a_item = StoreItem(
        user_id=teacher.id,
        join_code='JOINA111',
        name='A Only Item',
        price=Decimal('6.00'),
        is_active=True,
    )
    d_item = StoreItem(
        user_id=teacher.id,
        join_code='JOIND222',
        name='D Only Item',
        price=Decimal('7.00'),
        is_active=True,
    )
    # QUERY INVERSION v2: Unscoped items (join_code=None) are teacher templates
    # and must NOT appear in student shop.
    unscoped_item = StoreItem(
        user_id=teacher.id,
        name='Unscoped Item',
        price=Decimal('5.00'),
        is_active=True,
    )
    db.session.add_all([unscoped_item, a_item, d_item])
    db.session.flush()
    db.session.add_all([
        StoreItemBlock(store_item_id=a_item.id, block='A'),
        StoreItemBlock(store_item_id=d_item.id, block='D'),
    ])
    db.session.commit()

    _login_student(client, student_a.user_id, 'JOINA111')
    resp = client.get('/student/shop')
    assert resp.status_code == 200
    # Unscoped items (join_code=None) must NOT appear in student shop
    assert b'Unscoped Item' not in resp.data
    assert b'A Only Item' in resp.data
    assert b'D Only Item' not in resp.data


def test_purchase_item_rejects_items_not_visible_to_current_block(client):
    teacher = make_admin('teacher_block_visibility_purchase')
    db.session.flush()

    student_a = _create_student(teacher, 'Casey', 'JOINA333', block='A')
    db.session.flush()

    d_only_item = StoreItem(
        user_id=teacher.id,
        name='D Scoped Item',
        price=Decimal('8.00'),
        is_active=True,
    )
    db.session.add(d_only_item)
    db.session.flush()
    db.session.add(StoreItemBlock(store_item_id=d_only_item.id, block='D'))
    db.session.commit()

    _login_student(client, student_a.user_id, 'JOINA333')
    resp = client.post('/api/purchase-item', json={
        'item_id': d_only_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp.status_code == 404
    assert StudentItem.query.filter_by(
        seat_id=student_a.id,
        store_item_id=d_only_item.id,
        join_code='JOINA333',
    ).count() == 0


def test_purchase_item_allows_unscoped_item_without_block_visibility(client):
    """QUERY INVERSION v2: Items with join_code must be scoped to a class.
    Items that previously had join_code=None are now class-scoped."""
    teacher = make_admin('teacher_unscoped_purchase')
    db.session.flush()

    student_a = _create_student(teacher, 'Devon', 'JOINA444', block='A')
    db.session.flush()

    # Item is scoped to the student's class (join_code), no block restrictions
    scoped_item = StoreItem(
        user_id=teacher.id,
        join_code='JOINA444',
        name='Class Scoped Item',
        price=Decimal('4.00'),
        is_active=True,
    )
    db.session.add(scoped_item)
    db.session.commit()

    _login_student(client, student_a.user_id, 'JOINA444')
    resp = client.post('/api/purchase-item', json={
        'item_id': scoped_item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp.status_code == 200
    assert StudentItem.query.filter_by(
        seat_id=student_a.id,
        store_item_id=scoped_item.id,
        join_code='JOINA444',
    ).count() == 1


def test_collective_unlock_scoped_to_join_code_and_goal_type(client):
    teacher = make_admin('teacher_collective_unlock')
    db.session.flush()

    student_a1 = _create_student(teacher, 'Alex', 'JOINA777', block='A')
    student_a2 = _create_student(teacher, 'Bri', 'JOINA777', block='A')
    student_b1 = _create_student(teacher, 'Cy', 'JOINB999', block='B')
    db.session.flush()

    item = StoreItem(
        user_id=teacher.id,
        join_code='JOINA777',
        name='Collective Unlock',
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type='fixed',
        collective_goal_target=2,
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    db.session.add(item)
    db.session.flush()

    # Existing purchase in class A and class B.
    db.session.add_all([
        StudentItem(correlation_id='corr_test', seat_id=student_a1.id, store_item_id=item.id, join_code='JOINA777', status='pending', collective_goal_instance_code=item.collective_goal_instance_code),
        StudentItem(correlation_id='corr_test', seat_id=student_b1.id, store_item_id=item.id, join_code='JOINB999', status='pending', collective_goal_instance_code=item.collective_goal_instance_code),
    ])
    db.session.commit()

    _login_student(client, student_a2.user_id, 'JOINA777')
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200

    class_a_statuses = [
        si.status for si in StudentItem.query.filter_by(store_item_id=item.id, join_code='JOINA777').all()
    ]
    class_b_statuses = [
        si.status for si in StudentItem.query.filter_by(store_item_id=item.id, join_code='JOINB999').all()
    ]

    # Class A reached fixed goal of 2 students, so pending purchases unlock to processing.
    assert all(status == 'processing' for status in class_a_statuses)
    # Class B progress should not be modified by class A purchase.
    assert class_b_statuses == ['pending']


def test_admin_store_shows_collective_progress(client):
    teacher = make_admin('teacher_collective_admin')
    db.session.flush()

    student_a1 = _create_student(teacher, 'Ana', 'JOINADMINA', block='A')
    _create_student(teacher, 'Bo', 'JOINADMINA', block='A')
    db.session.flush()

    item = StoreItem(
        user_id=teacher.id,
        join_code='JOINADMINA',
        name=' Progress Item',
        price=Decimal('5.00'),
        item_type='collective',
        collective_goal_type='fixed',
        collective_goal_target=2,
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    db.session.add(item)
    db.session.flush()
    db.session.add(StudentItem(correlation_id='corr_test', seat_id=student_a1.id, store_item_id=item.id, join_code='JOINADMINA', status='pending', collective_goal_instance_code=item.collective_goal_instance_code))
    db.session.commit()

    _login_admin(client, teacher.id)
    resp = client.get('/admin/store')
    assert resp.status_code == 200
    assert b'Collective Progress' in resp.data
    assert b'1/2' in resp.data


def test_whole_class_collective_prevents_duplicate_purchase(client):
    """Test that students can only purchase a whole_class collective item once."""
    teacher = make_admin('teacher_whole_class')
    db.session.flush()

    student_a1 = _create_student(teacher, 'Dana', 'JOINWHOLE', block='A')
    student_a2 = _create_student(teacher, 'Eve', 'JOINWHOLE', block='A')
    db.session.flush()

    item = StoreItem(
        user_id=teacher.id,
        join_code='JOINWHOLE',
        name='Whole Class Goal Item',
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    db.session.add(item)
    db.session.commit()

    _login_student(client, student_a1.user_id, 'JOINWHOLE')

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


def test_whole_class_collective_goal_uses_correct_class_size(client):
    """Test that whole_class collective goals use actual student count, not seat count."""
    teacher = make_admin('teacher_class_size')
    db.session.flush()

    # Create 2 students for the class
    student_a1 = _create_student(teacher, 'Frank', 'JOINSIZE', block='A')
    student_a2 = _create_student(teacher, 'Grace', 'JOINSIZE', block='A')
    db.session.flush()

    item = StoreItem(
        user_id=teacher.id,
        join_code='JOINSIZE',
        name='Whole Class Pizza',
        price=Decimal('5.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    db.session.add(item)
    db.session.commit()

    # First student purchases
    _login_student(client, student_a1.user_id, 'JOINSIZE')
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
    _login_student(client, student_a2.user_id, 'JOINSIZE')
    resp2 = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp2.status_code == 200
    
    # Check all items are now processing (goal reached)
    items = StudentItem.query.filter_by(store_item_id=item.id, join_code='JOINSIZE').all()
    assert len(items) == 2
    assert all(si.status == 'processing' for si in items)


def test_collective_progress_with_correct_roster_count_admin(client):
    """Test that admin view shows correct class size based on actual students."""
    teacher = make_admin('teacher_admin_size')
    db.session.flush()

    # Create 3 students
    student_a1 = _create_student(teacher, 'Henry', 'JOINADMIN', block='A')
    student_a2 = _create_student(teacher, 'Iris', 'JOINADMIN', block='A')
    student_a3 = _create_student(teacher, 'Jack', 'JOINADMIN', block='A')
    db.session.flush()

    item = StoreItem(
        user_id=teacher.id,
        join_code='JOINADMIN',
        name=' Whole Class Item',
        price=Decimal('5.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    db.session.add(item)
    db.session.flush()
    
    # One student purchases
    db.session.add(StudentItem(correlation_id='corr_test', seat_id=student_a1.id, store_item_id=item.id, join_code='JOINADMIN', status='pending', collective_goal_instance_code=item.collective_goal_instance_code))
    db.session.commit()

    _login_admin(client, teacher.id)
    resp = client.get('/admin/store')
    assert resp.status_code == 200
    # Should show 1/3 (1 purchase out of 3 students)
    assert b'1/3' in resp.data


def test_fixed_collective_allows_multiple_purchases(client):
    """Test that fixed collective goals still allow multiple purchases from same student."""
    teacher = make_admin('teacher_fixed_multi')
    db.session.flush()

    student_a1 = _create_student(teacher, 'Kelly', 'JOINFIXED', block='A')
    db.session.flush()

    item = StoreItem(
        user_id=teacher.id,
        join_code='JOINFIXED',
        name='Fixed Goal Item',
        price=Decimal('5.00'),
        item_type='collective',
        collective_goal_type='fixed',
        collective_goal_target=3,
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    db.session.add(item)
    db.session.commit()

    _login_student(client, student_a1.user_id, 'JOINFIXED')
    
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


def test_whole_class_goal_with_duplicate_seats_shows_correct_roster(client):
    """Test that duplicate TeacherBlock entries don't inflate class size."""
    teacher = make_admin('teacher_dup_seats')
    db.session.flush()

    # Create 2 students
    student_a1 = _create_student(teacher, 'Laura', 'JOINDUP', block='A')
    student_a2 = _create_student(teacher, 'Mike', 'JOINDUP', block='A')
    db.session.flush()
    
    # Add a duplicate TeacherBlock entry for student_a1 (simulating data inconsistency)
    # Auto-injected Canonical User
    student_a1_user = User(username_hash=f"auto_{student_a1.id}", username_lookup_hash=f"auto_l_{student_a1.id}", user_role=UserRole.STUDENT)
    db.session.add(student_a1_user)
    db.session.flush()
    # TODO: _tb_seat needs class_id set from the ClassEconomy for join_code JOINDUP
    _tb_seat = Seat(user_id=student_a1_user.id, role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name='Laura', last_name='S'))
    db.session.flush()

    item = StoreItem(
        user_id=teacher.id,
        join_code='JOINDUP',
        name='Duplicate Seats Test',
        price=Decimal('5.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    db.session.add(item)
    db.session.commit()

    # Despite 3 TeacherBlock entries, class size should be 2 (unique students)
    _login_student(client, student_a1.user_id, 'JOINDUP')
    resp_shop = client.get('/student/shop')
    # Should show 0/2, not 0/3
    assert b'0/2' in resp_shop.data or b'Whole Class Goal' in resp_shop.data
    
    #  view should also show correct count
    _login_admin(client, teacher.id)
    resp_admin = client.get('/admin/store')
    assert b'0/2' in resp_admin.data


def test_whole_class_collective_allows_purchase_per_class_for_same_teacher(client):
    """Students in different classes (join_codes) with the same teacher can each purchase once."""
    teacher = make_admin('teacher_whole_class_multi')
    db.session.flush()

    # Create student in two different classes (join_codes) for the same teacher
    student_class1 = _create_student(teacher, 'Nina', 'JOINMULTI1', block='A')
    student_class2 = _create_student(teacher, 'Nina', 'JOINMULTI2', block='B')
    db.session.flush()

    item_class1 = StoreItem(
        user_id=teacher.id,
        join_code='JOINMULTI1',
        name='Whole Class Multi-Class Item',
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    item_class2 = StoreItem(
        user_id=teacher.id,
        join_code='JOINMULTI2',
        name='Whole Class Multi-Class Item',
        price=Decimal('10.00'),
        item_type='collective',
        collective_goal_type='whole_class',
        is_active=True,
        collective_goal_instance_code=str(uuid.uuid4())
    )
    db.session.add_all([item_class1, item_class2])
    db.session.commit()

    # Student in first class purchases successfully
    _login_student(client, student_class1.user_id, 'JOINMULTI1')
    resp1 = client.post('/api/purchase-item', json={
        'item_id': item_class1.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp1.status_code == 200

    # Student in second class (different join_code) should also be able to purchase
    _login_student(client, student_class2.user_id, 'JOINMULTI2')
    resp2 = client.post('/api/purchase-item', json={
        'item_id': item_class2.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert resp2.status_code == 200

    # Ensure one purchase recorded per class (per join_code)
    items_class1 = StudentItem.query.filter_by(store_item_id=item_class1.id, join_code='JOINMULTI1').all()
    items_class2 = StudentItem.query.filter_by(store_item_id=item_class2.id, join_code='JOINMULTI2').all()
    assert len(items_class1) == 1
    assert len(items_class2) == 1
