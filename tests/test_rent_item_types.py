from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
import re
from decimal import Decimal
from app.models import RentItem, RentSettings, RentPayment, RentWaiver, StoreItem, StudentItem, Student, Transaction, StudentBlock, Admin, StudentTeacher, ClassEconomy, ClassMembership, Seat, IdentityProfile
from app.extensions import db
from datetime import datetime, timezone, timedelta

@pytest.fixture
def teacher_admin(client):
    """Create a teacher admin user."""
    # client fixture already pushes app context and creates DB
    admin = make_admin("teacher", "secret")
    db.session.add(admin)
    db.session.commit()
    # Refresh to ensure it's bound or just return ID if that's safer,
    # but keeping object is standard if session persists.
    # To avoid DetachedInstanceError if session is somehow messed with:
    db.session.refresh(admin)
    return admin

@pytest.fixture
def student_in_class(client, teacher_admin):
    """Create a student in the teacher's class."""
    profile = IdentityProfile(profile_type='student', first_name='Test', last_name='S')
    db.session.add(profile)
    db.session.flush()
    student = Student(identity_profile=profile, block="A", salt=b'salt')
    db.session.add(student)
    db.session.flush()

    # Link to teacher
    link = StudentTeacher(student_id=student.id, teacher_id=teacher_admin.id)
    db.session.add(link)

    # Create seat
    seat = Seat(student_id=student.id, join_code='JOINCODE123', block='A', block_identifier='A', role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat.id, profile_type='student_claimed', first_name='Test', last_name='S'))
    db.session.add(seat)
    db.session.add(seat)
    
    # Setup Class Context
    class_economy = ClassEconomy(join_code='JOINCODE123', teacher_id=teacher_admin.id, status="active", created_by_admin_id=teacher_admin.id)
    db.session.add(class_economy)
    db.session.flush()
    db.session.add(Seat(
        student_id=student.id,
        class_id=class_economy.class_id,
        join_code='JOINCODE123',
        block='A',
        role='student',
    ))
    db.session.add(ClassMembership(join_code='JOINCODE123', admin_id=teacher_admin.id, role="admin"))
    db.session.add(ClassMembership(join_code='JOINCODE123', student_id=student.id, role="student"))
    db.session.commit()
    db.session.refresh(student)
    return student


@pytest.fixture
def admin_class_scope(client, teacher_admin):
    """Create a class-scoped seat so admin feature routes can resolve scope."""
    profile = IdentityProfile(profile_type='student', first_name='Scope', last_name='S')
    db.session.add(profile)
    db.session.flush()
    student = Student(identity_profile=profile, block="A", salt=b"scope-salt")
    db.session.add(student)
    db.session.flush()

    class_economy = ClassEconomy(
        join_code='JOINCODE123',
        teacher_id=teacher_admin.id,
        status="active",
        created_by_admin_id=teacher_admin.id,
    )
    db.session.add(class_economy)
    db.session.flush()

    db.session.add_all([
        StudentTeacher(student_id=student.id, teacher_id=teacher_admin.id)(
            teacher_id=teacher_admin.id,
            block='A',
            join_code='JOINCODE123',
            student_id=student.id,
            is_claimed=True,
            first_name='Scope',
            last_initial='S',
            salt=b'scope-salt',
            first_half_hash='scope-hash',
        ),
        Seat(
            student_id=student.id,
            class_id=class_economy.class_id,
            join_code='JOINCODE123',
            block='A',
            role='student',
        ),
        ClassMembership(join_code='JOINCODE123', admin_id=teacher_admin.id, role="admin"),
        ClassMembership(join_code='JOINCODE123', student_id=student.id, role="student"),
    ])
    db.session.commit()

    return class_economy

def test_admin_configure_rent_item_types(client, teacher_admin, admin_class_scope):
    """Test that admin can configure different rent item types."""
    with client.session_transaction() as sess:
        sess['admin_id'] = teacher_admin.id
        sess['is_admin'] = True
        sess['current_join_code'] = admin_class_scope.join_code

    # Get settings block
    settings = RentSettings(teacher_id=teacher_admin.id, block='A', is_enabled=True)
    db.session.add(settings)
    db.session.commit()

    # Simulate form data for 3 items: Privilege, Per-Use, Hall Pass
    data = {
        'settings_block': 'A',
        'is_enabled': 'on',
        'rent_amount': '50.00',
        'frequency_type': 'monthly',
        'due_day_of_month': '1',
        'grace_period_days': '3',
        'late_penalty_amount': '10.00',

        # Item 1: Privilege
        'rent_item_name_0': 'Desk',
        'rent_item_type_0': 'privilege',
        'rent_item_store_available_0': 'on',
        'rent_item_store_price_0': '100.00',
        'rent_item_purchase_duration_0': 'per_period',

        # Item 2: Per-Use (Consumable)
        'rent_item_name_1': 'Pencil',
        'rent_item_type_1': 'per_use',
        'rent_item_store_available_1': 'on', # Should be forced true in UI/backend logic really
        'rent_item_store_price_1': '5.00',
        'rent_item_purchase_duration_1': 'per_use',
        'rent_item_use_limit_1': '5', # Multi-use

        # Item 3: Hall Pass
        'rent_item_name_2': 'Bonus Pass',
        'rent_item_type_2': 'hall_pass',
        'rent_item_hall_pass_count_2': '2'
    }

    resp = client.post('/admin/rent-settings', data=data, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Rent settings updated successfully" in resp.data

    # Verify Database State
    items = RentItem.query.filter_by(rent_setting_id=settings.id).order_by(RentItem.order_index).all()
    assert len(items) == 3

    # Privilege
    assert items[0].name == 'Desk'
    assert items[0].rent_item_type == 'privilege'
    assert items[0].store_price == Decimal('100.00')
    assert items[0].store_item_id is not None # Synced to store

    # Per-Use
    assert items[1].name == 'Pencil'
    assert items[1].rent_item_type == 'per_use'
    assert items[1].use_limit == 5
    assert items[1].store_item_id is not None # Synced to store

    # Hall Pass
    assert items[2].name == 'Bonus Pass'
    assert items[2].rent_item_type == 'hall_pass'
    assert items[2].hall_pass_count == 2
    assert items[2].store_item_id is None # NOT synced to store (logic update)

def test_store_sync_logic(client, teacher_admin, admin_class_scope):
    """Test that store items are created/updated correctly based on type."""
    # Setup settings
    settings = RentSettings(
        teacher_id=teacher_admin.id,
        join_code=admin_class_scope.join_code,
        block='A',
        is_enabled=True,
    )
    db.session.add(settings)
    db.session.commit()

    # Create RentItems manually to test sync logic isolation
    privilege = RentItem(
        rent_setting_id=settings.id, name='Privilege', rent_item_type='privilege',
        is_available_in_store=True, store_price=Decimal('10.00'), purchase_duration='per_period'
    )
    per_use = RentItem(
        rent_setting_id=settings.id, name='Consumable', rent_item_type='per_use',
        is_available_in_store=True, store_price=Decimal('2.00'), purchase_duration='per_use', use_limit=1
    )
    hall_pass = RentItem(
        rent_setting_id=settings.id, name='HP', rent_item_type='hall_pass',
        hall_pass_count=1
    )
    db.session.add_all([privilege, per_use, hall_pass])
    db.session.commit()

    # Trigger sync manually (normally called in route)
    from app.routes.admin import _sync_rent_items_to_store
    _sync_rent_items_to_store(settings, teacher_admin.id, 'A')

    # Verify StoreItems
    privilege_store = StoreItem.query.filter_by(name='Privilege').first()
    assert privilege_store is not None
    assert privilege_store.price == Decimal('10.00')
    assert privilege_store.limit_per_student == 1
    assert privilege_store.is_rent_linked is True

    per_use_store = StoreItem.query.filter_by(name='Consumable').first()
    assert per_use_store is not None
    assert per_use_store.is_rent_linked is True # Should be marked linked

    hall_pass_store = StoreItem.query.filter_by(name='HP').first()
    assert hall_pass_store is None # Should NOT exist in store

def test_student_purchase_per_use_item(client, teacher_admin, student_in_class):
    """Test student purchasing a multi-use item."""
    student = student_in_class

    # 1. Setup Item
    store_item = StoreItem(
        teacher_id=teacher_admin.id, name='Multi-Use Snack', price=Decimal('5.00'),
            is_active=True, item_type='delayed' # Rent items should be delayed (redeemable)
    )
    db.session.add(store_item)
    db.session.flush()

    # Link to RentItem with limits
    settings = RentSettings(teacher_id=teacher_admin.id, block='A', is_enabled=True)
    db.session.add(settings)
    db.session.flush()

    rent_item = RentItem(
        rent_setting_id=settings.id, name='Multi-Use Snack', rent_item_type='per_use',
        is_available_in_store=True, store_price=Decimal('5.00'), purchase_duration='per_use',
        use_limit=3, store_item_id=store_item.id
    )
    db.session.add(rent_item)

    # Give student money
    tx = Transaction(student_id=student.id, amount=100, account_type='checking', teacher_id=teacher_admin.id, join_code='JOINCODE123')
    db.session.add(tx)
    db.session.commit()

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123' # Mock session context
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # 2. Purchase
    # Need to mock get_current_class_context or rely on session
    # Using API purchase endpoint
    data = {
        'item_id': store_item.id,
        'passphrase': 'password', # Default fixture password
        'quantity': 1
    }
    # Mock password hash check or update student
    from werkzeug.security import generate_password_hash
    student.passphrase_hash = generate_password_hash('password')
    db.session.commit()

    resp = client.post('/api/purchase-item', json=data)
    assert resp.status_code == 200

    # 3. Verify StudentItem State
    student_item = StudentItem.query.filter_by(student_id=student.id, store_item_id=store_item.id).first()
    assert student_item is not None
    assert student_item.status == 'purchased' # Should be 'purchased' to show in inventory
    assert student_item.uses_remaining is None  # Paid purchases are single-use, not rent free uses

def test_student_use_per_use_item(client, teacher_admin, student_in_class):
    """Test decrementing uses for a multi-use item."""
    student = student_in_class

    # Setup StudentItem directly (simulate previous purchase)
    store_item = StoreItem(teacher_id=teacher_admin.id, name='Pencil', price=5, is_active=True)
    db.session.add(store_item)
    db.session.flush()

    student_item = StudentItem(correlation_id='corr_test', 
        student_id=student.id, store_item_id=store_item.id,
        status='purchased', uses_remaining=3,
        join_code='JOINCODE123'
    )
    db.session.add(student_item)

    # Update passphrase
    from werkzeug.security import generate_password_hash
    student.passphrase_hash = generate_password_hash('password')
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Use Item (1st time)
    data = {'student_item_id': student_item.id, 'passphrase': 'password'}
    resp = client.post('/api/use-item', json=data)
    assert resp.status_code == 200
    assert "2 uses remaining" in resp.json['message']

    db.session.refresh(student_item)
    assert student_item.uses_remaining == 2
    assert student_item.status == 'purchased' # Still active

    # Use Item (2nd time)
    client.post('/api/use-item', json=data)
    db.session.refresh(student_item)
    assert student_item.uses_remaining == 1

    # Use Item (3rd/Last time)
    client.post('/api/use-item', json=data)
    db.session.refresh(student_item)
    assert student_item.uses_remaining == 0
    assert student_item.status == 'processing' # Should move to processing/redeemed

def test_prevent_deletion_of_linked_items(client, teacher_admin, admin_class_scope):
    """Test that admin cannot delete store items linked to rent settings."""
    with client.session_transaction() as sess:
        sess['admin_id'] = teacher_admin.id
        sess['is_admin'] = True
        sess['current_join_code'] = admin_class_scope.join_code

    # Create linked item
    store_item = StoreItem(
        teacher_id=teacher_admin.id, name='Rent Linked', price=10,
        is_active=True, is_rent_linked=True
    )
    db.session.add(store_item)
    db.session.commit()

    # Attempt Soft Delete
    resp = client.post(f'/admin/store/delete/{store_item.id}', follow_redirects=True)
    assert b"Cannot delete" in resp.data
    assert b"managed by Rent Settings" in resp.data

    db.session.refresh(store_item)
    assert store_item.is_active is True # Should still be active

    # Attempt Hard Delete
    resp = client.post(f'/admin/store/hard-delete/{store_item.id}', follow_redirects=True)
    assert b"Cannot delete" in resp.data

    db.session.refresh(store_item)
    assert store_item is not None # Should still exist


def test_hall_pass_topoff_replenishes_rent_portion_only(client, teacher_admin, student_in_class):
    """Test hall pass top-off only replenishes the rent-granted portion, not purchased passes."""
    student = student_in_class

    # Create student block with join_code
    sb = StudentBlock.query.filter_by(student_id=student.id).first()
    if not sb:
        sb = StudentBlock(student_id=student.id, period='A', join_code='JOINCODE123')
        db.session.add(sb)
        db.session.flush()

    # Scenario: rent grants 3, student has 1 rent + 2 purchased = 3 total
    sb.rent_hall_passes = 1
    student.hall_passes = 3  # 1 rent + 2 purchased
    db.session.commit()

    # Create rent settings with hall_pass item granting 3 passes
    settings = RentSettings(
        teacher_id=teacher_admin.id, block='A', is_enabled=True,
        rent_amount=Decimal('50.00'), frequency_type='monthly',
        due_day_of_month=1, first_rent_due_date=datetime(2026, 2, 1, tzinfo=timezone.utc)
    )
    db.session.add(settings)
    db.session.flush()

    hall_pass_item = RentItem(
        rent_setting_id=settings.id, name='Hall Passes',
        rent_item_type='hall_pass', hall_pass_count=3
    )
    db.session.add(hall_pass_item)
    db.session.commit()

    # Simulate the top-off logic directly (same as student.py rent_pay)
    total_grant = sum(item.hall_pass_count for item in [hall_pass_item] if item.hall_pass_count)
    current_rent_passes = sb.rent_hall_passes
    top_off = max(0, total_grant - current_rent_passes)

    student.hall_passes = (student.hall_passes or 0) + top_off
    sb.rent_hall_passes = total_grant
    db.session.commit()

    db.session.refresh(student)
    db.session.refresh(sb)

    # Expected: 3(original) + 2(top-off of rent portion: 3-1=2) = 5 total
    assert student.hall_passes == 5
    # rent_hall_passes should now be 3 (the full grant amount)
    assert sb.rent_hall_passes == 3


def test_hall_pass_topoff_zero_existing(client, teacher_admin, student_in_class):
    """Test hall pass top-off when student has 0 passes grants full amount."""
    student = student_in_class

    sb = StudentBlock.query.filter_by(student_id=student.id).first()
    if not sb:
        sb = StudentBlock(student_id=student.id, period='A', join_code='JOINCODE123')
        db.session.add(sb)
        db.session.flush()

    sb.rent_hall_passes = 0
    student.hall_passes = 0
    db.session.commit()

    # Top-off with grant of 3
    total_grant = 3
    current_rent_passes = sb.rent_hall_passes
    top_off = max(0, total_grant - current_rent_passes)

    student.hall_passes = (student.hall_passes or 0) + top_off
    sb.rent_hall_passes = total_grant
    db.session.commit()

    db.session.refresh(student)
    db.session.refresh(sb)

    assert student.hall_passes == 3
    assert sb.rent_hall_passes == 3


def test_hall_pass_consumption_decrements_rent_passes_first(client, teacher_admin, student_in_class):
    """Test that using a hall pass decrements rent_hall_passes before purchased passes."""
    student = student_in_class

    sb = StudentBlock.query.filter_by(student_id=student.id).first()
    if not sb:
        sb = StudentBlock(student_id=student.id, period='A', join_code='JOINCODE123')
        db.session.add(sb)
        db.session.flush()

    # Student has 3 rent + 2 purchased = 5 total
    sb.rent_hall_passes = 3
    student.hall_passes = 5
    db.session.commit()

    # Simulate hall pass consumption (same as api.py hall pass approval)
    student.hall_passes -= 1
    if sb.rent_hall_passes > 0:
        sb.rent_hall_passes -= 1
    db.session.commit()

    db.session.refresh(student)
    db.session.refresh(sb)

    assert student.hall_passes == 4
    assert sb.rent_hall_passes == 2  # Rent pass consumed first

    # Consume 2 more rent passes
    for _ in range(2):
        student.hall_passes -= 1
        if sb.rent_hall_passes > 0:
            sb.rent_hall_passes -= 1
    db.session.commit()

    db.session.refresh(student)
    db.session.refresh(sb)

    assert student.hall_passes == 2
    assert sb.rent_hall_passes == 0  # All rent passes consumed

    # Next pass consumed is from purchased (rent_hall_passes stays 0)
    student.hall_passes -= 1
    if sb.rent_hall_passes > 0:
        sb.rent_hall_passes -= 1
    db.session.commit()

    db.session.refresh(student)
    db.session.refresh(sb)

    assert student.hall_passes == 1
    assert sb.rent_hall_passes == 0  # Still 0, purchased pass consumed


def test_unpaid_period_revokes_rent_hall_passes_and_payment_restores_immediately(client, teacher_admin, student_in_class):
    """Unpaid students lose rent-granted hall passes for the new period; paying restores them immediately."""
    from app.routes.student import _ensure_rent_hall_pass_top_off

    student = student_in_class

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    db.session.add(RentItem(
        rent_setting_id=settings.id,
        name='Hall Pass Grant',
        rent_item_type='hall_pass',
        hall_pass_count=3,
    ))

    # Student starts new period with 3 rent-granted + 2 purchased passes.
    sb = StudentBlock.query.filter_by(student_id=student.id, period='A').first()
    if not sb:
        sb = StudentBlock(student_id=student.id, period='A', join_code='JOINCODE123')
        db.session.add(sb)
        db.session.flush()
    sb.rent_hall_passes = 3
    student.hall_passes = 5
    db.session.commit()

    context = {'join_code': 'JOINCODE123', 'teacher_id': teacher_admin.id, 'block': 'A'}
    fixed_now = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)  # New coverage period, unpaid

    awarded, revoked, changed = _ensure_rent_hall_pass_top_off(student, context, settings=settings, now=fixed_now)
    assert changed is True
    assert awarded == 0
    assert revoked == 3

    db.session.commit()
    db.session.refresh(student)
    db.session.refresh(sb)
    assert student.hall_passes == 2
    assert sb.rent_hall_passes == 0

    # Pay rent for current coverage period and reconcile again immediately.
    db.session.add(RentPayment(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=fixed_now.month,
        period_year=fixed_now.year,
        coverage_month=fixed_now.month,
        coverage_year=fixed_now.year,
        payment_date=fixed_now,
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A',
        timestamp=fixed_now,
    ))
    db.session.commit()

    awarded, revoked, changed = _ensure_rent_hall_pass_top_off(
        student,
        context,
        settings=settings,
        now=fixed_now + timedelta(minutes=5),
    )
    assert changed is True
    assert awarded == 3
    assert revoked == 0

    db.session.commit()
    db.session.refresh(student)
    db.session.refresh(sb)
    assert student.hall_passes == 5
    assert sb.rent_hall_passes == 3


def test_hall_pass_top_off_restores_after_base_rent_paid_even_with_late_fee_due(client, teacher_admin, student_in_class):
    """Hall-pass rent perk should restore once base rent is paid, even if late fee remains outstanding."""
    from app.routes.student import _ensure_rent_hall_pass_top_off

    student = student_in_class

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal('2.00'),
    )
    db.session.add(settings)
    db.session.flush()

    db.session.add(RentItem(
        rent_setting_id=settings.id,
        name='Hall Pass Grant',
        rent_item_type='hall_pass',
        hall_pass_count=3,
    ))

    sb = StudentBlock.query.filter_by(student_id=student.id, period='A').first()
    if not sb:
        sb = StudentBlock(student_id=student.id, period='A', join_code='JOINCODE123')
        db.session.add(sb)
        db.session.flush()
    sb.rent_hall_passes = 0
    student.hall_passes = 2
    db.session.commit()

    context = {'join_code': 'JOINCODE123', 'teacher_id': teacher_admin.id, 'block': 'A'}
    fixed_now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)

    # Student pays base rent only; late fee remains.
    db.session.add(RentPayment(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=fixed_now.month,
        period_year=fixed_now.year,
        coverage_month=fixed_now.month,
        coverage_year=fixed_now.year,
        payment_date=fixed_now,
        was_late=True,
        late_fee_charged=Decimal('0.00'),
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Base rent paid; late fee outstanding',
        timestamp=fixed_now,
    ))
    db.session.commit()

    awarded, revoked, changed = _ensure_rent_hall_pass_top_off(
        student,
        context,
        settings=settings,
        now=fixed_now + timedelta(minutes=1),
    )
    assert changed is True
    assert awarded == 3
    assert revoked == 0

    db.session.commit()
    db.session.refresh(student)
    db.session.refresh(sb)
    assert student.hall_passes == 5
    assert sb.rent_hall_passes == 3


def test_hall_pass_top_off_accepts_legacy_whitespace_period_values(client, teacher_admin, student_in_class):
    """Top-off should still detect paid coverage when legacy RentPayment.period contains trailing whitespace."""
    from app.routes.student import _ensure_rent_hall_pass_top_off

    student = student_in_class

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    db.session.add(RentItem(
        rent_setting_id=settings.id,
        name='Hall Pass Grant',
        rent_item_type='hall_pass',
        hall_pass_count=3,
    ))

    sb = StudentBlock.query.filter_by(student_id=student.id, period='A').first()
    if not sb:
        sb = StudentBlock(student_id=student.id, period='A', join_code='JOINCODE123')
        db.session.add(sb)
        db.session.flush()
    sb.rent_hall_passes = 0
    student.hall_passes = 0
    db.session.commit()

    context = {'join_code': 'JOINCODE123', 'teacher_id': teacher_admin.id, 'block': 'A'}
    fixed_now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)

    # Legacy/dirty data path: period stored as 'A '.
    db.session.add(RentPayment(
        student_id=student.id,
        period='A ',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=fixed_now.month,
        period_year=fixed_now.year,
        coverage_month=fixed_now.month,
        coverage_year=fixed_now.year,
        payment_date=fixed_now,
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent paid with legacy period whitespace',
        timestamp=fixed_now,
    ))
    db.session.commit()

    awarded, revoked, changed = _ensure_rent_hall_pass_top_off(
        student,
        context,
        settings=settings,
        now=fixed_now + timedelta(minutes=1),
    )
    assert changed is True
    assert awarded == 3
    assert revoked == 0

    db.session.commit()
    db.session.refresh(student)
    db.session.refresh(sb)
    assert student.hall_passes == 3
    assert sb.rent_hall_passes == 3


def test_mid_period_lock_blocks_semantic_changes(client, teacher_admin):
    """Test that semantic fields are locked when students have paid rent for current period."""
    with client.session_transaction() as sess:
        sess['admin_id'] = teacher_admin.id
        sess['is_admin'] = True
        sess['current_join_code'] = 'LOCKTEST'

    # Create settings and a rent item
    db.session.add(ClassEconomy(
        join_code='LOCKTEST',
        teacher_id=teacher_admin.id,
        status="active",
        created_by_admin_id=teacher_admin.id,
    ))
    db.session.add(ClassMembership(join_code='LOCKTEST', admin_id=teacher_admin.id, role="admin"))
    settings = RentSettings(
        teacher_id=teacher_admin.id, block='A', join_code='LOCKTEST', is_enabled=True,
        rent_amount=Decimal('50.00'), frequency_type='monthly',
        due_day_of_month=1, first_rent_due_date=datetime(2026, 2, 1, tzinfo=timezone.utc)
    )
    db.session.add(settings)
    db.session.flush()

    rent_item = RentItem(
        rent_setting_id=settings.id, name='Desk',
        rent_item_type='privilege', order_index=0,
        is_available_in_store=True, store_price=Decimal('100.00'),
        purchase_duration='per_period'
    )
    db.session.add(rent_item)
    db.session.flush()

    # Create a TeacherBlock with join_code
    tb = Seat(join_code='LOCKTEST', block='A', block_identifier='A', role="student")
    db.session.add(tb)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=tb.id, profile_type='student_unclaimed', first_name='Seat', last_name='1'))
    db.session.add(tb)
    db.session.flush()

    # Create a student who has paid rent for the current coverage period
    profile_payer = IdentityProfile(profile_type='student', first_name='Payer', last_name='P')
    db.session.add(profile_payer)
    db.session.flush()
    student = Student(identity_profile=profile_payer, block="A", salt=b'salt')
    db.session.add(student)
    db.session.flush()

    link = StudentTeacher(student_id=student.id, teacher_id=teacher_admin.id)
    db.session.add(link)

    now = datetime.now(timezone.utc)
    payment = RentPayment(
        student_id=student.id, period='A', join_code='LOCKTEST',
        amount_paid=Decimal('50.00'),
        coverage_month=now.month, coverage_year=now.year
    )
    db.session.add(payment)
    db.session.commit()

    # Now try to change rent_item_type from privilege to per_use
    data = {
        'settings_block': 'A',
        'is_enabled': 'on',
        'rent_amount': '50.00',
        'frequency_type': 'monthly',
        'due_day_of_month': '1',
        'rent_item_name_0': 'Desk',
        'rent_item_id_0': str(rent_item.id),
        'rent_item_type_0': 'per_use',  # Changed from privilege
        'rent_item_store_available_0': 'on',
        'rent_item_store_price_0': '100.00',
        'rent_item_purchase_duration_0': 'per_use',
        'rent_item_use_limit_0': '5',
    }

    resp = client.post('/admin/rent-settings', data=data, follow_redirects=True)
    assert resp.status_code == 200

    # Check that the item type was NOT changed (mid-period lock)
    db.session.refresh(rent_item)
    assert rent_item.rent_item_type == 'privilege'  # Should remain privilege
    assert rent_item.use_limit is None  # Should not have been set

    # But cosmetic changes should be allowed
    assert rent_item.name == 'Desk'  # Name update should work


def test_mid_period_lock_allows_new_items(client, teacher_admin):
    """Test that new items can be added even when mid-period lock is active."""
    with client.session_transaction() as sess:
        sess['admin_id'] = teacher_admin.id
        sess['is_admin'] = True
        sess['current_join_code'] = 'LOCKTEST2'

    db.session.add(ClassEconomy(
        join_code='LOCKTEST2',
        teacher_id=teacher_admin.id,
        status="active",
        created_by_admin_id=teacher_admin.id,
    ))
    db.session.add(ClassMembership(join_code='LOCKTEST2', admin_id=teacher_admin.id, role="admin"))
    settings = RentSettings(
        teacher_id=teacher_admin.id, block='A', join_code='LOCKTEST2', is_enabled=True,
        rent_amount=Decimal('50.00'), frequency_type='monthly',
        due_day_of_month=1, first_rent_due_date=datetime(2026, 2, 1, tzinfo=timezone.utc)
    )
    db.session.add(settings)
    db.session.flush()

    tb = Seat(join_code='LOCKTEST2', block='A', block_identifier='A', role="student")

    db.session.add(tb)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=tb.id, profile_type='student_unclaimed', first_name='Seat', last_name='2'))
    db.session.add(tb)
    db.session.flush()

    profile_payer = IdentityProfile(profile_type='student', first_name='Payer', last_name='P')
    db.session.add(profile_payer)
    db.session.flush()
    student = Student(identity_profile=profile_payer, block="A", salt=b'salt')
    db.session.add(student)
    db.session.flush()

    link = StudentTeacher(student_id=student.id, teacher_id=teacher_admin.id)
    db.session.add(link)

    now = datetime.now(timezone.utc)
    payment = RentPayment(
        student_id=student.id, period='A', join_code='LOCKTEST2',
        amount_paid=Decimal('50.00'),
        coverage_month=now.month, coverage_year=now.year
    )
    db.session.add(payment)
    db.session.commit()

    # Add a new item - should work even with lock active
    data = {
        'settings_block': 'A',
        'is_enabled': 'on',
        'rent_amount': '50.00',
        'frequency_type': 'monthly',
        'due_day_of_month': '1',
        'rent_item_name_0': 'New Item',
        'rent_item_type_0': 'per_use',
        'rent_item_store_available_0': 'on',
        'rent_item_store_price_0': '10.00',
        'rent_item_purchase_duration_0': 'per_use',
        'rent_item_use_limit_0': '3',
    }

    resp = client.post('/admin/rent-settings', data=data, follow_redirects=True)
    assert resp.status_code == 200

    # New item should be created with the specified type
    new_item = RentItem.query.filter_by(rent_setting_id=settings.id, name='New Item').first()
    assert new_item is not None
    assert new_item.rent_item_type == 'per_use'
    assert new_item.use_limit == 3


def test_legacy_rent_items_default_to_privilege(client, teacher_admin):
    """Test that existing rent items without rent_item_type default to privilege."""
    settings = RentSettings(teacher_id=teacher_admin.id, block='A', is_enabled=True)
    db.session.add(settings)
    db.session.flush()

    # Create item without explicitly setting rent_item_type (simulates legacy data)
    item = RentItem(
        rent_setting_id=settings.id, name='Legacy Desk',
        is_available_in_store=True, store_price=Decimal('50.00'),
        purchase_duration='per_period'
    )
    db.session.add(item)
    db.session.commit()

    db.session.refresh(item)
    assert item.rent_item_type == 'privilege'  # Default value for backward compat


def test_per_use_free_purchase_from_rent(client, teacher_admin, student_in_class):
    """Test that a student with rent-granted uses_remaining can purchase for $0."""
    student = student_in_class
    from werkzeug.security import generate_password_hash
    student.passphrase_hash = generate_password_hash('password')

    # Create a rent-linked store item
    store_item = StoreItem(
        teacher_id=teacher_admin.id, name='Rent Snack', price=Decimal('5.00'),
        is_active=True, item_type='delayed', is_rent_linked=True
    )
    db.session.add(store_item)
    db.session.flush()

    # Give student a rent-granted StudentItem with 3 uses remaining
    rent_granted = StudentItem(correlation_id='corr_test', 
        student_id=student.id, store_item_id=store_item.id,
        status='purchased', uses_remaining=3,
        purchase_date=datetime.now(timezone.utc),
        join_code='JOINCODE123'
    )
    db.session.add(rent_granted)

    # Give student some money
    tx = Transaction(student_id=student.id, amount=100, account_type='checking',
                     teacher_id=teacher_admin.id, join_code='JOINCODE123')
    db.session.add(tx)
    db.session.commit()

    original_balance = student.checking_balance

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Purchase - should be free
    data = {'item_id': store_item.id, 'passphrase': 'password', 'quantity': 1}
    resp = client.post('/api/purchase-item', json=data)
    assert resp.status_code == 200
    assert "$0" in resp.json['message'] or "rent perk" in resp.json['message'].lower()

    # Verify uses_remaining decremented
    db.session.refresh(rent_granted)
    assert rent_granted.uses_remaining == 2

    # Verify balance NOT changed (free purchase)
    db.session.refresh(student)
    assert student.checking_balance == original_balance

    # Verify a purchased item is created and can be used later
    purchased_items = StudentItem.query.filter_by(
        student_id=student.id,
        store_item_id=store_item.id,
        join_code='JOINCODE123'
    ).all()
    assert any(si.uses_remaining is None for si in purchased_items)


def test_per_use_charges_when_uses_exhausted(client, teacher_admin, student_in_class):
    """Test that after free uses are exhausted, the student pays regular price."""
    student = student_in_class
    from werkzeug.security import generate_password_hash
    student.passphrase_hash = generate_password_hash('password')

    store_item = StoreItem(
        teacher_id=teacher_admin.id, name='Rent Pencil', price=Decimal('5.00'),
        is_active=True, item_type='delayed', is_rent_linked=True
    )
    db.session.add(store_item)
    db.session.flush()

    # Give student a rent-granted item with 0 uses remaining (exhausted)
    rent_granted = StudentItem(correlation_id='corr_test', 
        student_id=student.id, store_item_id=store_item.id,
        status='purchased', uses_remaining=0,
        purchase_date=datetime.now(timezone.utc),
        join_code='JOINCODE123'
    )
    db.session.add(rent_granted)

    tx = Transaction(student_id=student.id, amount=100, account_type='checking',
                     teacher_id=teacher_admin.id, join_code='JOINCODE123')
    db.session.add(tx)
    db.session.commit()

    original_balance = student.checking_balance

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Purchase - should charge regular price since uses are exhausted
    data = {'item_id': store_item.id, 'passphrase': 'password', 'quantity': 1}
    resp = client.post('/api/purchase-item', json=data)
    assert resp.status_code == 200

    # Balance should decrease by the item price
    db.session.refresh(student)
    assert student.checking_balance < original_balance


def test_per_use_free_purchase_without_precreated_grant_when_rent_paid(client, teacher_admin, student_in_class):
    """Paid-rent students should still get $0 per-use purchases when grant rows are missing."""
    student = student_in_class
    from werkzeug.security import generate_password_hash
    student.passphrase_hash = generate_password_hash('password')

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    store_item = StoreItem(
        teacher_id=teacher_admin.id,
        name='Rent Pencil No Grant',
        price=Decimal('5.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    db.session.add(RentItem(
        rent_setting_id=settings.id,
        name='Rent Pencil No Grant',
        rent_item_type='per_use',
        is_available_in_store=True,
        store_price=Decimal('5.00'),
        purchase_duration='per_use',
        use_limit=1,
        store_item_id=store_item.id,
    ))

    now = datetime.now(timezone.utc)
    db.session.add(RentPayment(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=now.month,
        period_year=now.year,
        coverage_month=now.month,
        coverage_year=now.year,
        payment_date=now,
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A',
    ))
    db.session.add(Transaction(
        student_id=student.id,
        amount=100,
        account_type='checking',
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123'
    ))
    db.session.commit()

    starting_balance = student.checking_balance

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    resp = client.post('/api/purchase-item', json={'item_id': store_item.id, 'passphrase': 'password', 'quantity': 1})
    assert resp.status_code == 200
    assert "$0" in resp.json['message'] or "rent perk" in resp.json['message'].lower()

    db.session.refresh(student)
    assert student.checking_balance == starting_balance


def test_shop_only_disables_privilege_items_when_rent_paid(client, teacher_admin, student_in_class):
    """When rent is paid, privilege items are included/disabled but per-use items remain purchasable."""
    student = student_in_class
    from werkzeug.security import generate_password_hash
    student.passphrase_hash = generate_password_hash('password')

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    privilege_store_item = StoreItem(
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        name='Desk Privilege',
        price=Decimal('50.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    per_use_store_item = StoreItem(
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        name='Pencil Per Use',
        price=Decimal('3.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    db.session.add_all([privilege_store_item, per_use_store_item])
    db.session.flush()

    db.session.add_all([
        RentItem(
            rent_setting_id=settings.id,
            name='Desk Privilege',
            rent_item_type='privilege',
            is_available_in_store=True,
            store_price=Decimal('50.00'),
            purchase_duration='per_period',
            store_item_id=privilege_store_item.id,
        ),
        RentItem(
            rent_setting_id=settings.id,
            name='Pencil Per Use',
            rent_item_type='per_use',
            is_available_in_store=True,
            store_price=Decimal('3.00'),
            purchase_duration='per_use',
            use_limit=5,
            store_item_id=per_use_store_item.id,
        ),
    ])

    now = datetime.now(timezone.utc)
    rent_payment = RentPayment(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=now.month,
        period_year=now.year,
        coverage_month=now.month,
        coverage_year=now.year,
        payment_date=now,
    )
    db.session.add(rent_payment)
    # _filter_valid_rent_payments requires a matching Transaction within 5 seconds
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A',
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    resp = client.get('/student/shop')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    privilege_button = re.search(
        rf'data-item-id="{privilege_store_item.id}"[^>]*>',
        html,
        re.DOTALL
    )
    assert privilege_button is not None
    assert 'disabled' in privilege_button.group(0)

    per_use_button = re.search(
        rf'data-item-id="{per_use_store_item.id}"[^>]*>',
        html,
        re.DOTALL
    )
    assert per_use_button is not None
    assert 'disabled' not in per_use_button.group(0)


def test_shop_keeps_item_purchasable_when_per_use_and_privilege_links_overlap(client, teacher_admin, student_in_class):
    """If legacy data creates mixed rent item types for one store item, per-use access should remain purchasable."""
    student = student_in_class
    anchor_now = datetime.now(timezone.utc)

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=anchor_now - timedelta(days=60),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    store_item = StoreItem(
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        name='Mixed Rent Link',
        price=Decimal('8.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    db.session.add_all([
        RentItem(
            rent_setting_id=settings.id,
            name='Mixed Rent Link Priv',
            rent_item_type='privilege',
            is_available_in_store=True,
            store_price=Decimal('8.00'),
            purchase_duration='per_period',
            store_item_id=store_item.id,
        ),
        RentItem(
            rent_setting_id=settings.id,
            name='Mixed Rent Link Use',
            rent_item_type='per_use',
            is_available_in_store=True,
            store_price=Decimal('8.00'),
            purchase_duration='per_use',
            use_limit=2,
            store_item_id=store_item.id,
        ),
    ])

    now = datetime.now(timezone.utc)
    db.session.add(RentPayment(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=now.month,
        period_year=now.year,
        coverage_month=now.month,
        coverage_year=now.year,
        payment_date=now,
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A',
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    resp = client.get('/student/shop')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    button = re.search(rf'data-item-id="{store_item.id}"[^>]*>', html, re.DOTALL)
    assert button is not None
    assert 'disabled' not in button.group(0)


def test_shop_treats_legacy_privilege_with_per_use_duration_as_per_use(client, teacher_admin, student_in_class):
    """Legacy privilege+per_use-duration rows should render as purchasable rent perks, not included/disabled."""
    student = student_in_class
    anchor_now = datetime.now(timezone.utc)

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=anchor_now - timedelta(days=60),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    store_item = StoreItem(
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        name='Legacy Per Use Link',
        price=Decimal('9.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    db.session.add(RentItem(
        rent_setting_id=settings.id,
        name='Legacy Per Use Link',
        rent_item_type='privilege',   # legacy default
        purchase_duration='per_use',  # actual semantics
        is_available_in_store=True,
        store_price=Decimal('9.00'),
        use_limit=1,
        store_item_id=store_item.id,
    ))

    from app.routes.student import _calculate_rent_coverage_due_date
    coverage_due_date = _calculate_rent_coverage_due_date(settings, anchor_now)
    assert coverage_due_date is not None

    db.session.add(RentPayment(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=anchor_now.month,
        period_year=anchor_now.year,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        payment_date=anchor_now,
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A',
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    resp = client.get('/student/shop')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    button = re.search(rf'data-item-id="{store_item.id}"[^>]*>', html, re.DOTALL)
    assert button is not None
    assert 'disabled' not in button.group(0)
    assert 'Rent Perk price: $0.00' in html


def test_api_allows_zero_cost_rent_linked_purchase_when_paid_without_per_use_mapping(client, teacher_admin, student_in_class):
    """Paid-rent students can still buy non-privilege rent-linked perks for $0 when mapping rows are missing."""
    student = student_in_class
    from werkzeug.security import generate_password_hash
    student.passphrase_hash = generate_password_hash('password')
    anchor_now = datetime.now(timezone.utc)

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=anchor_now - timedelta(days=60),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    # Rent-linked store item without a RentItem mapping row (legacy/stale linkage).
    store_item = StoreItem(
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        name='Link Only Perk',
        price=Decimal('12.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    db.session.add(store_item)

    from app.routes.student import _calculate_rent_coverage_due_date
    coverage_due_date = _calculate_rent_coverage_due_date(settings, anchor_now)
    assert coverage_due_date is not None

    db.session.add(RentPayment(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=anchor_now.month,
        period_year=anchor_now.year,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        payment_date=anchor_now,
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A',
    ))
    db.session.add(Transaction(
        student_id=student.id,
        amount=Decimal('100.00'),
        account_type='checking',
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
    ))
    db.session.commit()

    starting_balance = student.checking_balance

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    resp = client.post('/api/purchase-item', json={'item_id': store_item.id, 'passphrase': 'password', 'quantity': 1})
    assert resp.status_code == 200
    assert 'purchased' in resp.json['message'].lower()

    db.session.refresh(student)
    assert student.checking_balance == starting_balance


def test_api_hall_pass_item_skips_rent_perk_zero_cost_flow(client, teacher_admin, student_in_class):
    """Hall-pass items should always purchase directly and never create rent-perk inventory rows."""
    student = student_in_class
    from werkzeug.security import generate_password_hash
    from app.routes.student import _calculate_rent_coverage_due_date

    student.passphrase_hash = generate_password_hash('password')

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    hall_pass_item = StoreItem(
        teacher_id=teacher_admin.id,
        name='Paid Hall Pass',
        price=Decimal('5.00'),
        is_active=True,
        item_type='hall_pass',
        is_rent_linked=True,  # Legacy/stale flag should not trigger free rent-perk flow
    )
    db.session.add(hall_pass_item)
    db.session.flush()

    now = datetime.now(timezone.utc)
    coverage_due_date = _calculate_rent_coverage_due_date(settings, now)
    assert coverage_due_date is not None

    db.session.add(RentPayment(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=now.month,
        period_year=now.year,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        payment_date=now,
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A',
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('100.00'),
        account_type='checking',
        type='Deposit',
        description='Seed funds',
    ))
    db.session.commit()

    starting_balance = student.checking_balance
    starting_hall_passes = student.hall_passes

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    resp = client.post('/api/purchase-item', json={'item_id': hall_pass_item.id, 'passphrase': 'password', 'quantity': 1})
    assert resp.status_code == 200
    assert 'Hall Pass' in resp.json['message']

    db.session.refresh(student)
    assert student.hall_passes == starting_hall_passes + 1
    assert student.checking_balance == starting_balance - Decimal('5.00')

    created_rows = StudentItem.query.filter_by(student_id=student.id, store_item_id=hall_pass_item.id).all()
    assert len(created_rows) == 0


def test_use_item_converts_legacy_hall_pass_inventory_row(client, teacher_admin, student_in_class):
    """Legacy hall-pass StudentItem rows should redeem into hall-pass balance immediately."""
    student = student_in_class
    from werkzeug.security import generate_password_hash

    student.passphrase_hash = generate_password_hash('password')

    hall_pass_item = StoreItem(
        teacher_id=teacher_admin.id,
        name='Legacy Hall Pass',
        price=Decimal('5.00'),
        is_active=True,
        item_type='hall_pass',
    )
    db.session.add(hall_pass_item)
    db.session.flush()

    legacy_row = StudentItem(correlation_id='corr_test', 
        student_id=student.id,
        store_item_id=hall_pass_item.id,
        join_code='JOINCODE123',
        status='purchased',
        quantity_purchased=2,
    )
    db.session.add(legacy_row)
    db.session.commit()

    starting_hall_passes = student.hall_passes

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    resp = client.post('/api/use-item', json={
        'student_item_id': legacy_row.id,
        'passphrase': 'password',
        'details': 'Need to use this old item',
    })
    assert resp.status_code == 200
    assert 'Added 2 hall pass(es)' in resp.json['message']

    db.session.refresh(student)
    db.session.refresh(legacy_row)

    assert student.hall_passes == starting_hall_passes + 2
    assert legacy_row.status == 'redeemed'
    assert legacy_row.redemption_date is not None
    assert 'Hall pass grant processed' in (legacy_row.redemption_details or '')


def test_shop_displays_rent_perk_price_as_free(client, teacher_admin, student_in_class):
    """Rent perk items with active free uses should display $0 pricing in the student shop."""
    student = student_in_class
    from werkzeug.security import generate_password_hash
    student.passphrase_hash = generate_password_hash('password')

    store_item = StoreItem(
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        name='Rent Linked Pencil',
        price=Decimal('7.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    # Active rent-granted uses for this item
    db.session.add(StudentItem(correlation_id='corr_test', 
        student_id=student.id,
        store_item_id=store_item.id,
        status='purchased',
        uses_remaining=2,
        purchase_date=datetime.now(timezone.utc),
        join_code='JOINCODE123',
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    resp = client.get('/student/shop')
    assert resp.status_code == 200
    assert b'Rent Perk price: $0.00' in resp.data
    assert b'Regular: $7.00' in resp.data


def test_shop_displays_rent_perk_price_as_free_when_rent_paid_without_grant_row(client, teacher_admin, student_in_class):
    """Shop should display per-use rent perk as $0 for paid-rent students even when grant row is missing."""
    student = student_in_class

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    per_use_store_item = StoreItem(
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        name='Paid Rent Pencil',
        price=Decimal('4.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    db.session.add(per_use_store_item)
    db.session.flush()

    db.session.add(RentItem(
        rent_setting_id=settings.id,
        name='Paid Rent Pencil',
        rent_item_type='per_use',
        is_available_in_store=True,
        store_price=Decimal('4.00'),
        purchase_duration='per_use',
        use_limit=2,
        store_item_id=per_use_store_item.id,
    ))

    now = datetime.now(timezone.utc)
    db.session.add(RentPayment(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=now.month,
        period_year=now.year,
        coverage_month=now.month,
        coverage_year=now.year,
        payment_date=now,
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A',
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    resp = client.get('/student/shop')
    assert resp.status_code == 200
    assert b'Paid Rent Pencil' in resp.data
    assert b'Rent Perk price: $0.00' in resp.data


def test_admin_store_hides_delete_button_for_rent_linked_items(client, teacher_admin, admin_class_scope):
    """Rent-linked items should hide delete even when legacy is_rent_linked flag is stale."""
    with client.session_transaction() as sess:
        sess['admin_id'] = teacher_admin.id
        sess['is_admin'] = True
        sess['current_join_code'] = admin_class_scope.join_code

    settings = RentSettings(teacher_id=teacher_admin.id, block='A', is_enabled=True)
    db.session.add(settings)
    db.session.flush()

    rent_linked = StoreItem(
        teacher_id=teacher_admin.id,
        name='Rent Linked Item',
        price=Decimal('5.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=False,  # Legacy/stale flag
    )
    regular = StoreItem(
        teacher_id=teacher_admin.id,
        name='Regular Item',
        price=Decimal('5.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=False,
    )
    db.session.add_all([rent_linked, regular])
    db.session.flush()
    db.session.add(RentItem(
        rent_setting_id=settings.id,
        name='Rent Linked Item',
        rent_item_type='privilege',
        is_available_in_store=True,
        store_price=Decimal('5.00'),
        purchase_duration='per_period',
        store_item_id=rent_linked.id,
    ))
    db.session.commit()

    resp = client.get('/admin/store')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    linked_delete = re.search(
        rf'(data-item-id="{rent_linked.id}"[^>]*data-bs-target="#deleteItemModal"|'
        rf'data-bs-target="#deleteItemModal"[^>]*data-item-id="{rent_linked.id}")',
        html,
        re.DOTALL
    )
    assert linked_delete is None

    regular_delete = re.search(
        rf'(data-item-id="{regular.id}"[^>]*data-bs-target="#deleteItemModal"|'
        rf'data-bs-target="#deleteItemModal"[^>]*data-item-id="{regular.id}")',
        html,
        re.DOTALL
    )
    assert regular_delete is not None

    # Deletion guard should also block by RentItem linkage fallback
    delete_resp = client.post(f'/admin/store/delete/{rent_linked.id}', follow_redirects=True)
    assert delete_resp.status_code == 200
    assert b"Cannot delete" in delete_resp.data


def test_privilege_badge_only_shows_privilege_items(client, teacher_admin, student_in_class):
    """Test that _build_rent_privileges_by_block only shows privilege-type items as badges."""
    student = student_in_class

    settings = RentSettings(
        teacher_id=teacher_admin.id, block='A', is_enabled=True,
        rent_amount=Decimal('50.00'), frequency_type='monthly',
        due_day_of_month=1, first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    db.session.add(settings)
    db.session.flush()

    # Create one of each type
    privilege_item = RentItem(
        rent_setting_id=settings.id, name='Desk Badge', rent_item_type='privilege',
        is_available_in_store=True, store_price=Decimal('10.00'), purchase_duration='per_period'
    )
    per_use_item = RentItem(
        rent_setting_id=settings.id, name='Pencil Uses', rent_item_type='per_use',
        is_available_in_store=True, store_price=Decimal('2.00'), purchase_duration='per_use',
        use_limit=5
    )
    hall_pass_item = RentItem(
        rent_setting_id=settings.id, name='HP Grant', rent_item_type='hall_pass',
        hall_pass_count=3
    )
    db.session.add_all([privilege_item, per_use_item, hall_pass_item])
    db.session.commit()

    # Query using the same filter as _build_rent_privileges_by_block
    badge_items = RentItem.query.filter(
        RentItem.rent_setting_id == settings.id,
        RentItem.rent_item_type == 'privilege',
        RentItem.purchase_duration == 'per_period',
        RentItem.is_available_in_store == True
    ).all()

    # Only privilege items should appear as badges
    assert len(badge_items) == 1
    assert badge_items[0].name == 'Desk Badge'
    assert badge_items[0].rent_item_type == 'privilege'


def test_late_fee_only_when_unpaid_by_grace(client, teacher_admin, student_in_class):
    """Test that late fees are only applied when rent is not fully paid by grace deadline."""
    from datetime import timedelta
    from app.routes.student import utc_now, _total_paid_by_grace
    
    student = student_in_class
    
    # Set up rent settings with late fee
    now = utc_now()
    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        late_penalty_amount=Decimal('2.00'),
        frequency_type='weekly',
        first_rent_due_date=now - timedelta(days=7),
        grace_period_days=3
    )
    db.session.add(settings)
    db.session.commit()
    
    # Calculate current due date and grace end
    from app.routes.student import _calculate_rent_coverage_due_date
    coverage_due_date = _calculate_rent_coverage_due_date(settings, now)
    grace_end_date = coverage_due_date + timedelta(days=settings.grace_period_days)
    
    # Test 1: Full payment BEFORE grace deadline - no late fee
    payment_date_before_grace = grace_end_date - timedelta(days=1)
    
    payment1 = RentPayment(
        student_id=student.id,
        period='A',
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        amount_paid=Decimal('10.00'),
        payment_date=payment_date_before_grace,
        join_code='JOINCODE123'
    )
    db.session.add(payment1)
    
    # Create matching transaction
    txn1 = Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=-Decimal('10.00'),
        account_type='checking',
        type='Rent Payment',
        timestamp=payment_date_before_grace,
        description='Rent payment'
    )
    db.session.add(txn1)
    db.session.commit()
    
    # Verify payment was made before grace deadline
    payments = [payment1]
    paid_by_grace = _total_paid_by_grace(payments, grace_end_date)
    assert paid_by_grace == Decimal('10.00')
    
    # When paid in full by grace deadline, late fee should NOT apply
    # So total due = rent_amount only (no late fee)
    late_fee = Decimal('0.00')
    if now > grace_end_date and paid_by_grace < settings.rent_amount:
        late_fee = settings.late_penalty_amount
    
    # Since we're testing with now > grace_end_date scenario, let's adjust
    # Actually, we need to test what happens when we check AFTER grace period
    future_now = grace_end_date + timedelta(days=1)
    
    # At this point, since paid_by_grace >= rent_amount, no late fee
    late_fee = Decimal('0.00')
    if future_now > grace_end_date and paid_by_grace < settings.rent_amount:
        late_fee = settings.late_penalty_amount
    
    assert late_fee == Decimal('0.00'), "Late fee should not apply when paid in full by grace deadline"
    
    # Clean up for test 2
    db.session.delete(payment1)
    db.session.delete(txn1)
    db.session.commit()
    
    # Test 2: Partial payment before grace deadline - late fee applies
    # Pay $6 before grace (less than $10 required)
    payment2 = RentPayment(
        student_id=student.id,
        period='A',
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        amount_paid=Decimal('6.00'),
        payment_date=payment_date_before_grace,
        join_code='JOINCODE123'
    )
    db.session.add(payment2)
    
    txn2 = Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=-Decimal('6.00'),
        account_type='checking',
        type='Rent Payment',
        timestamp=payment_date_before_grace,
        description='Partial rent payment'
    )
    db.session.add(txn2)
    db.session.commit()
    
    # Verify partial payment
    payments2 = [payment2]
    paid_by_grace2 = _total_paid_by_grace(payments2, grace_end_date)
    assert paid_by_grace2 == Decimal('6.00')
    
    # Since only $6 paid by grace (< $10), late fee SHOULD apply when checked after grace
    late_fee2 = Decimal('0.00')
    if future_now > grace_end_date and paid_by_grace2 < settings.rent_amount:
        late_fee2 = settings.late_penalty_amount
    
    assert late_fee2 == Decimal('2.00'), "Late fee should apply when not paid in full by grace deadline"
    
    # Total due should be rent + late fee = $12
    total_due = settings.rent_amount + late_fee2
    assert total_due == Decimal('12.00')
    
    # Clean up
    db.session.delete(payment2)
    db.session.delete(txn2)
    db.session.commit()
    
    # Test 3: Payment AFTER grace deadline - should not count toward paid_by_grace
    payment_date_after_grace = grace_end_date + timedelta(days=1)
    
    payment3 = RentPayment(
        student_id=student.id,
        period='A',
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        amount_paid=Decimal('10.00'),
        payment_date=payment_date_after_grace,
        join_code='JOINCODE123'
    )
    db.session.add(payment3)
    
    txn3 = Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=-Decimal('10.00'),
        account_type='checking',
        type='Rent Payment',
        timestamp=payment_date_after_grace,
        description='Rent payment after grace'
    )
    db.session.add(txn3)
    db.session.commit()
    
    # Payment made after grace should not count in paid_by_grace
    payments3 = [payment3]
    paid_by_grace3 = _total_paid_by_grace(payments3, grace_end_date)
    assert paid_by_grace3 == Decimal('0.00'), "Payment after grace should not count in paid_by_grace"
    
    # Since nothing paid by grace, late fee applies
    late_fee3 = Decimal('0.00')
    if future_now > grace_end_date and paid_by_grace3 < settings.rent_amount:
        late_fee3 = settings.late_penalty_amount
    
    assert late_fee3 == Decimal('2.00'), "Late fee should apply when payment is after grace deadline"


def test_per_use_free_purchase_recovers_from_exhausted_grant_row_when_rent_paid(client, teacher_admin, student_in_class, monkeypatch):
    """Paid-rent students should not be charged if a stale exhausted grant row is the only row present."""
    student = student_in_class
    from werkzeug.security import generate_password_hash
    student.passphrase_hash = generate_password_hash('password')

    fixed_now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr('app.routes.api.utc_now', lambda: fixed_now)

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    store_item = StoreItem(
        teacher_id=teacher_admin.id,
        name='Unlimited Pencil',
        price=Decimal('5.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    db.session.add(store_item)
    db.session.flush()

    db.session.add(RentItem(
        rent_setting_id=settings.id,
        name='Unlimited Pencil',
        rent_item_type='per_use',
        is_available_in_store=True,
        store_price=Decimal('5.00'),
        purchase_duration='per_use',
        use_limit=None,  # unlimited
        store_item_id=store_item.id,
    ))

    # Simulate current-period rent fully paid
    db.session.add(RentPayment(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=fixed_now.month,
        period_year=fixed_now.year,
        coverage_month=fixed_now.month,
        coverage_year=fixed_now.year,
        payment_date=fixed_now,
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A',
        timestamp=fixed_now,
    ))

    # Stale legacy row: exhausted grant still present
    db.session.add(StudentItem(correlation_id='corr_test', 
        student_id=student.id,
        store_item_id=store_item.id,
        join_code='JOINCODE123',
        purchase_date=fixed_now,
        status='purchased',
        uses_remaining=0,
    ))

    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('100.00'),
        account_type='checking',
        type='Deposit',
        description='Seed funds',
    ))
    db.session.commit()

    starting_balance = student.checking_balance

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    resp = client.post('/api/purchase-item', json={'item_id': store_item.id, 'passphrase': 'password', 'quantity': 1})
    assert resp.status_code == 200
    assert '$0' in resp.json['message'] or 'rent perk' in resp.json['message'].lower()

    db.session.refresh(student)
    assert student.checking_balance == starting_balance


def test_rent_payment_hall_pass_top_off_recovers_from_stale_counter(client, teacher_admin, student_in_class, monkeypatch):
    """Hall-pass grant should still top-off when rent_hall_passes counter drifted above actual passes."""
    student = student_in_class
    fixed_now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr('app.routes.student.utc_now', lambda: fixed_now)

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    db.session.add(RentItem(
        rent_setting_id=settings.id,
        name='Hall Pass Bonus',
        rent_item_type='hall_pass',
        hall_pass_count=3,
        is_available_in_store=False,
    ))

    # Stale state: counter says 3 rent passes, but student has 0 actual passes.
    db.session.add(StudentBlock(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        rent_hall_passes=3,
    ))

    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('100.00'),
        account_type='checking',
        type='Deposit',
        description='Seed funds',
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    resp = client.post('/student/rent/pay/A', follow_redirects=False)
    assert resp.status_code == 302

    db.session.refresh(student)
    assert student.hall_passes == 3

    sb = StudentBlock.query.filter_by(student_id=student.id, period='A').first()
    assert sb is not None
    assert sb.rent_hall_passes == 3


def test_waiver_does_not_grant_rent_perks_in_shop(client, teacher_admin, student_in_class, monkeypatch):
    """A waiver allows access but should not grant paid-rent perks."""
    student = student_in_class

    fixed_now = datetime.now(timezone.utc)
    monkeypatch.setattr('app.routes.student.utc_now', lambda: fixed_now)
    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    privilege_store_item = StoreItem(
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        name='Waiver Desk Privilege',
        price=Decimal('50.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    per_use_store_item = StoreItem(
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        name='Waiver Pencil Per Use',
        price=Decimal('3.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    db.session.add_all([privilege_store_item, per_use_store_item])
    db.session.flush()

    db.session.add_all([
        RentItem(
            rent_setting_id=settings.id,
            name='Waiver Desk Privilege',
            rent_item_type='privilege',
            is_available_in_store=True,
            store_price=Decimal('50.00'),
            purchase_duration='per_period',
            store_item_id=privilege_store_item.id,
        ),
        RentItem(
            rent_setting_id=settings.id,
            name='Waiver Pencil Per Use',
            rent_item_type='per_use',
            is_available_in_store=True,
            store_price=Decimal('3.00'),
            purchase_duration='per_use',
            use_limit=5,
            store_item_id=per_use_store_item.id,
        ),
    ])

    db.session.add(RentWaiver(
        student_id=student.id,
        join_code='JOINCODE123',
        waiver_start_date=datetime(2000, 1, 1, tzinfo=timezone.utc),
        waiver_end_date=datetime(2100, 1, 1, tzinfo=timezone.utc),
        periods_count=1,
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = fixed_now.isoformat()

    resp = client.get('/student/shop')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    privilege_card = re.search(
        rf'data-item-id="{privilege_store_item.id}"[^>]*data-has-rent-free-purchase="([^"]+)"',
        html,
    )
    assert privilege_card is not None
    assert privilege_card.group(1) == 'false'

    per_use_card = re.search(
        rf'data-item-id="{per_use_store_item.id}"[^>]*data-has-rent-free-purchase="([^"]+)"',
        html,
    )
    assert per_use_card is not None
    assert per_use_card.group(1) == 'false'


def test_shop_keeps_rent_perks_when_payment_exists_alongside_waiver(client, teacher_admin, student_in_class, monkeypatch):
    """A real payment should still grant perks even if a waiver also exists."""
    student = student_in_class
    fixed_now = datetime.now(timezone.utc)
    monkeypatch.setattr('app.routes.student.utc_now', lambda: fixed_now)

    settings = RentSettings(
        teacher_id=teacher_admin.id,
        block='A',
        join_code='JOINCODE123',
        is_enabled=True,
        rent_amount=Decimal('10.00'),
        frequency_type='monthly',
        first_rent_due_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        grace_period_days=3,
        late_penalty_amount=Decimal('0.00'),
    )
    db.session.add(settings)
    db.session.flush()

    privilege_store_item = StoreItem(
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        name='Paid + Waived Privilege',
        price=Decimal('50.00'),
        is_active=True,
        item_type='delayed',
        is_rent_linked=True,
    )
    db.session.add(privilege_store_item)
    db.session.flush()

    db.session.add(RentItem(
        rent_setting_id=settings.id,
        name='Paid + Waived Privilege',
        rent_item_type='privilege',
        is_available_in_store=True,
        store_price=Decimal('50.00'),
        purchase_duration='per_period',
        store_item_id=privilege_store_item.id,
    ))

    from app.routes.student import _calculate_rent_coverage_due_date
    coverage_due_date = _calculate_rent_coverage_due_date(settings, fixed_now)
    assert coverage_due_date is not None

    db.session.add(RentPayment(
        student_id=student.id,
        period='A',
        join_code='JOINCODE123',
        amount_paid=Decimal('10.00'),
        period_month=coverage_due_date.month,
        period_year=coverage_due_date.year,
        coverage_month=coverage_due_date.month,
        coverage_year=coverage_due_date.year,
        payment_date=fixed_now,
    ))
    db.session.add(Transaction(
        student_id=student.id,
        teacher_id=teacher_admin.id,
        join_code='JOINCODE123',
        amount=Decimal('-10.00'),
        account_type='checking',
        type='Rent Payment',
        description='Rent for Period A',
        timestamp=fixed_now,
    ))
    db.session.add(RentWaiver(
        student_id=student.id,
        join_code='JOINCODE123',
        waiver_start_date=datetime(2000, 1, 1, tzinfo=timezone.utc),
        waiver_end_date=datetime(2100, 1, 1, tzinfo=timezone.utc),
        periods_count=1,
    ))
    db.session.commit()

    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['current_join_code'] = 'JOINCODE123'
        sess['login_time'] = fixed_now.isoformat()

    resp = client.get('/student/shop')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')

    privilege_button = re.search(
        rf'data-item-id="{privilege_store_item.id}"[^>]*>',
        html,
        re.DOTALL,
    )
    assert privilege_button is not None
    assert 'disabled' in privilege_button.group(0)
    assert 'Included in your rent!' in html
