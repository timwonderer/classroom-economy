from tests.helpers.v2_fixtures import make_admin, make_sysadmin
from tests.helpers.class_scope import make_student_identity
import pytest
from app import db, Transaction
from app.payroll import calculate_payroll_breakdown
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

# Tolerance for floating point comparisons
FLOAT_TOLERANCE = 0.0001

@pytest.fixture
def test_teacher(client):
    """Fixture to create a test teacher for payroll tests."""
    from app.models import Admin, Seat, IdentityProfile
    teacher = make_admin("test_teacher", "s")
    db.session.add(teacher)
    db.session.commit()
    return teacher


@pytest.fixture
def test_class(test_teacher):
    from app.models import ClassEconomy

    class_economy = ClassEconomy(
        join_code=f"PAYT{test_teacher.id}",
        user_id=test_teacher.id,
        display_name="Payroll Test Class",
    )
    db.session.add(class_economy)
    db.session.commit()
    return class_economy

def test_calculate_payroll(client):
    from app.models import AttendanceSession, User, UserRole, IdentityProfile, Seat
    from tests.helpers.class_scope import create_class_scope

    # Create Teacher
    teacher = make_admin("prof_payroll", "s")
    db.session.add(teacher)
    db.session.commit()

    # Create a student
    student = make_student_identity(block="A", first_name='Test', last_name='S')
    db.session.commit()

    class_economy = create_class_scope(
        teacher=teacher,
        student=student,
        block="A",
        display_name="A",
    )

    # CRITICAL: Link student to claimed seat scope for payroll.
    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    tb = Seat(user_id=student_user.id, class_id=class_economy.class_id, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(tb)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=tb.id, profile_type='student_claimed', first_name="Test", last_name="S"))
    db.session.add(tb)
    db.session.commit()

    from app.models import Seat
    seat = Seat.query.filter_by(user_id=student_user.id, class_id=class_economy.class_id).first()
    assert seat is not None

    # Create attendance session to simulate attendance.
    now = datetime.now(timezone.utc)
    session_start = now - timedelta(minutes=60)
    session_end = now - timedelta(minutes=30)
    attendance_session = AttendanceSession(
        seat_id=seat.id,
        class_id=class_economy.class_id,
        started_at=session_start,
        ended_at=session_end,
        duration_seconds=1800,
    )
    db.session.add(attendance_session)
    db.session.commit()

    # Calculate payroll
    seat_ids = [seat.id]
    last_payroll_time = now - timedelta(days=1)
    payroll_summary = calculate_payroll_breakdown(class_economy.class_id, seat_ids, last_payroll_time)

    # Assert the payroll amount is correct
    # 30 minutes of attendance = 1800 seconds
    # 1800 seconds * ($0.25 / 60 seconds) = $7.50
    expected_payroll = Decimal("7.50")
    assert seat.id in payroll_summary
    assert payroll_summary[seat.id] == expected_payroll

    # Test case with no attendance
    # NOTE: student2 intentionally has no StudentTeacher link and no TeacherBlock
    # to verify proper skipping behavior in calculate_payroll. Students without
    # these associations should be skipped during payroll processing.
    student2 = make_student_identity(block="B", first_name='Test2', last_name='S')
    db.session.commit()

    payroll_summary2 = calculate_payroll_breakdown(class_economy.class_id, [], last_payroll_time)
    assert seat.id not in payroll_summary2

    # Manual payments after the last payroll should clear projected pay for that student
    manual_time = now - timedelta(minutes=5)
    manual_tx = Transaction(
        user_id=student_user.id,
        amount=3,
        type="manual_payment",
        timestamp=manual_time,
        class_id=class_economy.class_id,
        seat_id=seat.id,
    )
    db.session.add(manual_tx)
    db.session.commit()

    post_manual_summary = calculate_payroll_breakdown(class_economy.class_id, seat_ids, last_payroll_time)
    assert post_manual_summary == {}


def test_calculate_payroll_ignores_other_class_manual_payment_anchor(client):
    from app.models import AttendanceSession, Admin, User, UserRole, IdentityProfile, Seat
    from tests.helpers.class_scope import create_class_scope

    teacher = make_admin("prof_multiclass", "s")
    db.session.add(teacher)
    db.session.commit()

    student = make_student_identity(block="A,B", first_name="Multi", last_name="S")
    db.session.flush()
    class_a = create_class_scope(
        teacher=teacher,
        student=student,
        block="A",
        display_name="A",
    )
    class_b = create_class_scope(
        teacher=teacher,
        student=student,
        block="B",
        display_name="B",
    )
    db.session.flush()

    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    tb_a = Seat(user_id=student_user.id, class_id=class_a.class_id, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))

    db.session.add(tb_a)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=tb_a.id, profile_type='student_claimed', first_name="Multi", last_name="S"))
    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    tb_b = Seat(user_id=student_user.id, class_id=class_b.class_id, block="B", block_identifier="B", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(tb_b)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=tb_b.id, profile_type='student_claimed', first_name="Multi", last_name="S"))
    db.session.add_all([tb_a, tb_b])
    db.session.flush()

    from app.models import Seat
    seat_a = Seat.query.filter_by(user_id=student_user.id, class_id=class_a.class_id).first()
    seat_b = Seat.query.filter_by(user_id=student_user.id, class_id=class_b.class_id).first()
    assert seat_a is not None
    assert seat_b is not None

    now = datetime.now(timezone.utc)
    db.session.add_all([
        AttendanceSession(
            seat_id=seat_a.id,
            class_id=class_a.class_id,
            started_at=now - timedelta(minutes=50),
            ended_at=now - timedelta(minutes=40),
            duration_seconds=600,
        ),
        AttendanceSession(
            seat_id=seat_a.id,
            class_id=class_a.class_id,
            started_at=now - timedelta(minutes=39),
            ended_at=now - timedelta(minutes=35),
            duration_seconds=240,
        ),
        AttendanceSession(
            seat_id=seat_b.id,
            class_id=class_b.class_id,
            started_at=now - timedelta(minutes=30),
            ended_at=now - timedelta(minutes=15),
            duration_seconds=900,
        ),
        Transaction(
            user_id=student_user.id,
            seat_id=seat_a.id,
            class_id=class_a.class_id,
            amount=3,
            type="manual_payment",
            timestamp=now - timedelta(minutes=5),
        ),
    ])
    db.session.commit()

    summary_a = calculate_payroll_breakdown(class_a.class_id, [seat_a.id], now - timedelta(days=1))
    summary_b = calculate_payroll_breakdown(class_b.class_id, [seat_b.id], now - timedelta(days=1))

    expected_class_b_only = Decimal("3.75")
    assert summary_a == {}
    assert summary_b == {seat_b.id: expected_class_b_only}


def test_get_pay_rate_for_block_default(test_teacher, test_class):
    """Test that get_pay_rate_for_block returns default rate when no settings exist."""
    from app.payroll import get_pay_rate_for_block, DEFAULT_PAY_RATE_PER_SECOND

    # Get pay rate when no settings exist - should return default
    rate = get_pay_rate_for_block("A", class_id=test_class.class_id)
    # Default is now Decimal
    from decimal import Decimal
    assert rate == DEFAULT_PAY_RATE_PER_SECOND
    assert isinstance(rate, Decimal)


def test_get_pay_rate_for_block_block_specific(test_teacher, test_class):
    """Test that block-specific settings return correct float values."""
    from app.payroll import get_pay_rate_for_block
    from app.models import PayrollSettings
    from decimal import Decimal

    # Create block-specific payroll settings
    # pay_rate is stored in database as $ per minute
    block_setting = PayrollSettings(
        class_id=test_class.class_id,
        block="A",
        pay_rate=Decimal("0.50"),  # $0.50 per minute
        is_active=True
    )
    db.session.add(block_setting)
    db.session.commit()

    # Get pay rate for the block - should convert to per-second rate
    rate = get_pay_rate_for_block("A", class_id=test_class.class_id)

    # Expected: 0.50 / 60.0 = 0.008333...
    expected_rate = 0.50 / 60.0
    assert abs(float(rate) - expected_rate) < FLOAT_TOLERANCE
    assert isinstance(rate, Decimal)


def test_get_pay_rate_for_block_global_fallback(test_teacher, test_class):
    """Test that global settings fallback works correctly."""
    from app.payroll import get_pay_rate_for_block
    from app.models import PayrollSettings
    from decimal import Decimal

    # Create global payroll settings (block=None)
    global_setting = PayrollSettings(
        class_id=test_class.class_id,
        block=None,  # Global setting
        pay_rate=Decimal("0.30"),  # $0.30 per minute
        is_active=True
    )
    db.session.add(global_setting)
    db.session.commit()

    # Get pay rate for a block that doesn't have specific settings
    # Should fall back to global settings
    rate = get_pay_rate_for_block("B", class_id=test_class.class_id)

    # Expected: 0.30 / 60.0 = 0.005
    expected_rate = 0.30 / 60.0
    assert float(rate) == expected_rate
    assert isinstance(rate, Decimal)


def test_get_pay_rate_for_block_precedence(test_teacher, test_class):
    """Test that block-specific settings take precedence over global settings."""
    from app.payroll import get_pay_rate_for_block
    from app.models import PayrollSettings
    from decimal import Decimal

    # Create global setting
    global_setting = PayrollSettings(
        class_id=test_class.class_id,
        block=None,
        pay_rate=Decimal("0.25"),  # $0.25 per minute
        is_active=True
    )

    # Create block-specific setting (should take precedence)
    block_setting = PayrollSettings(
        class_id=test_class.class_id,
        block="A",
        pay_rate=Decimal("0.75"),  # $0.75 per minute
        is_active=True
    )

    db.session.add_all([global_setting, block_setting])
    db.session.commit()

    # Block A should use block-specific rate
    rate_a = get_pay_rate_for_block("A", class_id=test_class.class_id)
    assert float(rate_a) == 0.75 / 60.0

    # Block B should fall back to global rate
    rate_b = get_pay_rate_for_block("B", class_id=test_class.class_id)
    assert abs(float(rate_b) - (0.25 / 60.0)) < FLOAT_TOLERANCE


def test_get_pay_rate_for_block_per_minute_to_per_second_conversion(test_teacher, test_class):
    """Test that per-minute to per-second conversion is accurate."""
    from app.payroll import get_pay_rate_for_block
    from app.models import PayrollSettings
    from decimal import Decimal

    # Create setting with exact value that's easy to verify
    setting = PayrollSettings(
        class_id=test_class.class_id,
        block="A",
        pay_rate=Decimal("1.20"),  # $1.20 per minute
        is_active=True
    )
    db.session.add(setting)
    db.session.commit()

    # Get pay rate
    rate = get_pay_rate_for_block("A", class_id=test_class.class_id)

    # Expected: 1.20 / 60.0 = 0.02
    assert float(rate) == 0.02
    assert isinstance(rate, Decimal)


def test_get_pay_rate_for_block_json_serialization(test_teacher, test_class):
    """Test that the returned value works properly with JSON serialization."""
    import json
    from app.payroll import get_pay_rate_for_block
    from app.models import PayrollSettings
    from decimal import Decimal

    # Create setting
    setting = PayrollSettings(
        class_id=test_class.class_id,
        block="A",
        pay_rate=Decimal("0.45"),
        is_active=True
    )
    db.session.add(setting)
    db.session.commit()

    # Get pay rate
    rate = get_pay_rate_for_block("A", class_id=test_class.class_id)

    # Should be serializable to JSON without errors (when converted)
    # Note: Standard json.dumps does not support Decimal, but our API uses custom encoders
    # For this test, verifying we can serialize it after conversion is sufficient
    data = {"pay_rate": float(rate)}
    json_str = json.dumps(data)
    assert json_str is not None

    # Deserialize and verify
    deserialized = json.loads(json_str)
    assert abs(deserialized["pay_rate"] - (0.45 / 60.0)) < FLOAT_TOLERANCE


def test_get_pay_rate_for_block_inactive_settings_ignored(test_teacher, test_class):
    """Test that inactive settings are ignored."""
    from app.payroll import get_pay_rate_for_block, DEFAULT_PAY_RATE_PER_SECOND
    from app.models import PayrollSettings
    from decimal import Decimal

    # Create an inactive setting
    inactive_setting = PayrollSettings(
        class_id=test_class.class_id,
        block="A",
        pay_rate=Decimal("0.99"),
        is_active=False  # Inactive
    )
    db.session.add(inactive_setting)
    db.session.commit()

    # Should fall back to default rate since the setting is inactive
    rate = get_pay_rate_for_block("A", class_id=test_class.class_id)
    assert rate == DEFAULT_PAY_RATE_PER_SECOND


def test_get_pay_rate_for_block_requires_class_scope(client):
    """Lookup must fail closed when class scope is missing."""
    from app.payroll import get_pay_rate_for_block

    with pytest.raises(ValueError, match="class_id"):
        get_pay_rate_for_block("A", class_id=None)


def test_get_cached_payroll_with_meta(client):
    """Test the caching logic for payroll."""
    from app.payroll import get_cached_payroll_with_meta
    from app.models import Admin, Seat, IdentityProfile, AttendanceSession, PayrollCache, User, UserRole
    from tests.helpers.class_scope import create_class_scope
    from datetime import datetime, timedelta, timezone

    # Setup Teacher
    teacher = make_admin("prof_cache", "s")
    db.session.add(teacher)
    db.session.commit()

    # Setup seat-scoped student identity
    student = make_student_identity(block="A", first_name="CacheUser", last_name="T")
    db.session.flush()
    class_economy = create_class_scope(
        teacher=teacher,
        student=student,
        block="A",
        display_name="A",
    )
    db.session.commit()

    # Link
    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    tb = Seat(user_id=student_user.id, class_id=class_economy.class_id, block="A", block_identifier="A", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(tb)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=tb.id, profile_type='student_claimed', first_name="CacheUser", last_name="T"))
    db.session.add(tb)
    db.session.commit()

    from app.models import Seat
    seat = Seat.query.filter_by(user_id=student_user.id, class_id=class_economy.class_id).first()
    assert seat is not None

    # Add attendance session (1 hour at default rate).
    now = datetime.now(timezone.utc)
    session_one = AttendanceSession(
        seat_id=seat.id,
        class_id=class_economy.class_id,
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
        duration_seconds=3600,
    )
    db.session.add(session_one)
    db.session.commit()

    seat_ids = [seat.id]
    last_payroll = now - timedelta(days=1)

    # 1. First Call: Cache Miss -> Calculation
    summary, updated_at = get_cached_payroll_with_meta(class_economy.class_id, seat_ids, last_payroll)
    assert seat.id in summary
    assert summary[seat.id] > 0
    # Store initial values to compare later
    initial_amount = summary[seat.id]
    initial_updated_at = updated_at

    # Verify Cache Entry Exists
    cache = PayrollCache.query.filter_by(class_id=class_economy.class_id).first()
    assert cache is not None
    assert str(seat.id) in cache.cached_breakdown

    # 2. Second Call: Cache Hit (Verify Staleness)
    # Add more attendance events that SHOULD increase payroll if recalculated
    # Adding another 15 minutes
    session_two = AttendanceSession(
        seat_id=seat.id,
        class_id=class_economy.class_id,
        started_at=now - timedelta(minutes=30),
        ended_at=now - timedelta(minutes=15),
        duration_seconds=900,
    )
    db.session.add(session_two)
    db.session.commit()

    # Call again - should still return OLD value (Cache Hit)
    summary_cached, updated_at_cached = get_cached_payroll_with_meta(class_economy.class_id, seat_ids, last_payroll)
    # Value should be unchanged
    assert summary_cached[seat.id] == initial_amount
    # Timestamp should be unchanged
    assert updated_at_cached == initial_updated_at

    # 3. Simulate Expiry -> Cache Miss -> Calculation
    # Force cache timestamp to be old (2 hours ago)
    cache.last_calculated_at = now - timedelta(hours=2)
    db.session.commit()

    # Call again - should Recalculate
    summary_fresh, updated_at_fresh = get_cached_payroll_with_meta(class_economy.class_id, seat_ids, last_payroll)
    # Amount should increase due to new events
    assert summary_fresh[seat.id] > initial_amount
    # Timestamp should be newer
    assert updated_at_fresh > initial_updated_at


def test_get_cached_payroll_with_meta_fails_closed(client):
    """Verify that get_cached_payroll_with_meta fails closed if no class boundary is provided."""
    from app.payroll import get_cached_payroll_with_meta
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError, match=r"Class scope \(class_id\) must be explicitly provided."):
        get_cached_payroll_with_meta(None, [], now)
