"""
Test for dynamic rent display with persistent itemized information.

Tests the following features:
1. Rent items display persistently (before and after bill is due)
2. Dynamic color coding based on days until rent is due
3. Status text changes based on payment status and due date proximity
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timezone, timedelta
import os

from werkzeug.security import generate_password_hash

from app import db
from app.models import User, UserRole, Admin, RentSettings, RentItem, ClassEconomy, Transaction, TransactionStatus, Seat, IdentityProfile, StudentTeacher
from tests.helpers.class_scope import make_student_identity
from tests.helpers.canonical_session import set_canonical_context


@pytest.fixture
def setup_rent_with_items(client):
    """Create teacher, student, rent settings, and rent items."""
    teacher = make_admin("test_teacher", "secret123")
    db.session.add(teacher)
    db.session.commit()

    student_seat = make_student_identity(
        join_code="TESTA",
        block="A",
        first_name="Test",
        last_name="S",
    )
    db.session.add(StudentTeacher(user_id=student_seat.user_id, teacher_id=teacher.id))
    db.session.commit()

    economy = ClassEconomy(
        join_code="TESTA",
        user_id=teacher.id,
        display_name='Test Rent Class',
        status='active',
        created_by_admin_id=teacher.id
    )
    db.session.add(economy)
    db.session.flush()

    student_seat.class_id = economy.class_id
    db.session.commit()

    # Create rent settings (join-code scoped)
    now = datetime.now(timezone.utc)
    rent_settings = RentSettings(join_code="TESTA",
        block="A",
        is_enabled=True,
        rent_amount=50.0,
        first_rent_due_date=now + timedelta(days=10),  # Due in 10 days
        grace_period_days=3,
        bill_preview_enabled=True,
        bill_preview_days=5,
    )
    db.session.add(rent_settings)
    db.session.commit()

    # Create rent items
    item1 = RentItem(
        rent_setting_id=rent_settings.id,
        name="Desk",
        description="A comfortable desk space",
        order_index=1,
        is_available_in_store=True,
        store_price=15.0,
        purchase_duration='per_period'
    )
    item2 = RentItem(
        rent_setting_id=rent_settings.id,
        name="Locker",
        description="Secure storage locker",
        order_index=2,
        is_available_in_store=True,
        store_price=20.0,
        purchase_duration='per_use'
    )
    db.session.add_all([item1, item2])
    db.session.commit()

    return {
        'teacher': teacher,
        'student': student_seat,
        'rent_settings': rent_settings,
        'items': [item1, item2],
        'join_code': "TESTA"
    }


def test_rent_items_display_before_due_date(client, setup_rent_with_items):
    """Test that rent items are visible even before the rent is due."""
    data = setup_rent_with_items
    
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    
    # Check that rent items are displayed
    assert b'Desk' in response.data
    assert b'Locker' in response.data
    assert b'A comfortable desk space' in response.data
    assert b'Secure storage locker' in response.data


def test_rent_items_display_after_due_date(client, setup_rent_with_items):
    """Test that rent items are still visible after the rent is due."""
    data = setup_rent_with_items
    
    # Update rent settings to have due date in the past
    now = datetime.now(timezone.utc)
    data['rent_settings'].first_rent_due_date = now - timedelta(days=2)
    db.session.commit()
    
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    
    # Check that rent items are still displayed
    assert b'Desk' in response.data
    assert b'Locker' in response.data


def test_overdue_rent_payment_uses_coverage_month_in_transaction_description(client, setup_rent_with_items, monkeypatch):
    """Overdue students should pay the oldest unpaid coverage month first."""
    data = setup_rent_with_items
    fixed_now = datetime(2026, 2, 17, 12, 0, tzinfo=timezone.utc)

    # Make this mirror the reported scenario: due day 28, preview enabled.
    data['rent_settings'].first_rent_due_date = datetime(2026, 1, 28, tzinfo=timezone.utc)
    data['rent_settings'].bill_preview_enabled = True
    data['rent_settings'].bill_preview_days = 14
    data['rent_settings'].late_penalty_amount = 20
    data['rent_settings'].rent_amount = 570
    data['student'].is_rent_enabled = True
    db.session.add(
        Transaction(
            student_id=data['student'].id,join_code=data['join_code'],
            amount=1000,
            account_type='checking',
            status=TransactionStatus.POSTED,
            type='Deposit',
            description='Seed funds for rent test',
        )
    )
    db.session.commit()

    monkeypatch.setattr('app.routes.student.utc_now', lambda: fixed_now)

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.post('/student/rent/pay/A', follow_redirects=False)
    assert response.status_code == 302

    rent_txn = Transaction.query.filter_by(
        student_id=data['student'].id,
        join_code=data['join_code'],
        type='Rent Payment',
    ).order_by(Transaction.id.desc()).first()

    assert rent_txn is not None
    assert 'January 2026' in rent_txn.description
    assert 'late fee' in rent_txn.description


def test_overdue_current_period_does_not_show_future_due_countdown(client, setup_rent_with_items, monkeypatch):
    """When current coverage is overdue, status should not count down to a future period."""
    data = setup_rent_with_items
    fixed_now = datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc)

    data['rent_settings'].first_rent_due_date = datetime(2026, 1, 28, tzinfo=timezone.utc)
    data['rent_settings'].bill_preview_enabled = True
    data['rent_settings'].bill_preview_days = 20
    data['rent_settings'].grace_period_days = 5  # Keep this within grace to isolate due-date selection
    data['student'].is_rent_enabled = True
    db.session.commit()

    monkeypatch.setattr('app.routes.student.utc_now', lambda: fixed_now)

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    assert b'Past due, pay now' in response.data
    assert b'Rent will be due in' not in response.data


def test_days_until_due_calculation(client, setup_rent_with_items):
    """Test that days_until_due is correctly calculated and passed to template."""
    data = setup_rent_with_items
    now = datetime.now(timezone.utc)
    # Activate preview so the countdown is visible (due in 10 days, preview for 12)
    data['rent_settings'].bill_preview_enabled = True
    data['rent_settings'].bill_preview_days = 12
    data['rent_settings'].first_rent_due_date = now + timedelta(days=10, hours=1)
    db.session.commit()
    
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    
    # Since the rent is due in 10 days (from setup_rent_with_items)
    # We should see some indication that it's more than 7 days away
    # The status should show "Rent will be due in X days" (>7 days uses warning color)
    assert b'Rent will be due in 10 days' in response.data


def test_status_text_more_than_7_days(client, setup_rent_with_items):
    """Test status text when rent is more than 7 days away."""
    data = setup_rent_with_items
    
    # Set rent due date to 8 days from now (within preview period so it's active)
    now = datetime.now(timezone.utc)
    data['rent_settings'].first_rent_due_date = now + timedelta(days=8, hours=1)
    data['rent_settings'].bill_preview_enabled = True
    data['rent_settings'].bill_preview_days = 9  # Activate preview before the due date
    db.session.commit()
    
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    
    # Should display "Rent will be due in X days" with warning color
    # Since we're 8 days before due, this should be active and show the countdown
    assert b'Rent will be due in 8 days' in response.data


def test_status_text_between_3_and_7_days(client, setup_rent_with_items):
    """Test status text when rent is between 3 and 7 days away (inclusive)."""
    data = setup_rent_with_items
    
    # Set rent due date to 3 days from now
    now = datetime.now(timezone.utc)
    data['rent_settings'].first_rent_due_date = now + timedelta(days=3, hours=1)
    db.session.commit()
    
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    
    # Should display "Rent due in X days" with light red color
    assert b'Rent due in 3 days' in response.data


def test_status_text_within_2_days(client, setup_rent_with_items):
    """Test status text when rent is within 2 days."""
    data = setup_rent_with_items
    
    # Set rent due date to 2 days from now
    now = datetime.now(timezone.utc)
    data['rent_settings'].first_rent_due_date = now + timedelta(days=2, hours=1)
    db.session.commit()
    
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    
    # Should display "Due, pay soon" with crimson color
    assert b'Due, pay soon' in response.data


def test_status_text_past_due(client, setup_rent_with_items):
    """Test status text when rent is past due."""
    data = setup_rent_with_items
    
    # Set rent due date to 5 days ago (past grace period)
    now = datetime.now(timezone.utc)
    due_date = now - timedelta(days=5)
    data['rent_settings'].first_rent_due_date = due_date
    data['rent_settings'].grace_period_days = 0
    db.session.commit()
    
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    
    # Should display "Past due, pay now" with black color
    assert b'Past due, pay now' in response.data


def test_status_text_due_today(client, setup_rent_with_items):
    """Test status text when rent is due today."""
    data = setup_rent_with_items
    
    now = datetime.now(timezone.utc)
    data['rent_settings'].first_rent_due_date = now + timedelta(hours=1)
    db.session.commit()
    
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    
    # Due today should show the urgent state
    assert b'Due, pay soon' in response.data


def test_status_text_no_rent_yet(client, setup_rent_with_items):
    """Test status text when rent is not yet active (before first due date and preview period)."""
    data = setup_rent_with_items
    
    # Set rent due date to 20 days from now with 5-day preview
    # So we're more than 5 days before the due date
    now = datetime.now(timezone.utc)
    data['rent_settings'].first_rent_due_date = now + timedelta(days=20)
    data['rent_settings'].bill_preview_enabled = True
    data['rent_settings'].bill_preview_days = 5
    db.session.commit()
    
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    
    # Should display "No rent is due yet" with blue color
    assert b'No rent is due yet' in response.data or b'Not yet due' in response.data


def test_rent_items_show_store_availability(client, setup_rent_with_items):
    """Test that rent items show store availability information."""
    data = setup_rent_with_items
    
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    
    # Check that store availability info is shown
    assert b'Available separately in store' in response.data
    assert b'$15.00' in response.data  # Desk price
    assert b'$20.00' in response.data  # Locker price
    assert b'per use' in response.data
    assert b'valid until next rent is due' in response.data


def test_incremental_rent_form_shows_even_when_full_balance_is_short(client, setup_rent_with_items):
    """Incremental mode should still render the payment form even if full amount isn't affordable."""
    data = setup_rent_with_items

    now = datetime.now(timezone.utc)
    data['rent_settings'].first_rent_due_date = now - timedelta(days=1)
    data['rent_settings'].allow_incremental_payment = True
    db.session.commit()

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['student'].user_id,
            class_id=data['student'].class_id,
            seat_id=data['student'].id,
            role="student",
            join_code=data['join_code'],
        )

    response = client.get('/student/rent')
    assert response.status_code == 200
    assert b'Payment Amount' in response.data
    assert b'Insufficient Funds' not in response.data
