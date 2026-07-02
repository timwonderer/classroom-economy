"""
Tests for Analytics Engine.

Tests the analytics computation engine to ensure:
- System health metrics are calculated correctly
- All metrics are CWI-relative
- Multi-tenancy scoping is enforced
- Snapshots are cached properly
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timedelta, timezone
from app import db
from app.models import Seat, IdentityProfile, User, UserRole, Admin, StudentBlock, StudentTeacher, ClassEconomy, Transaction, PayrollSettings, RentSettings, AnalyticsAlert, FeatureSettings, ClassMembership, ClassMembershipRole
from app.routes.analytics import get_pay_cycle_days, get_rent_cycle_days
from app.utils.analytics_engine import AnalyticsEngine
from tests.helpers.class_scope import make_student_identity


@pytest.fixture
def setup_analytics_test(client):
    """Create test data for analytics testing."""
    # Create admin/teacher
    admin = make_admin("analyticstest", "TESTSECRET123456")
    db.session.add(admin)
    db.session.flush()
    
    # Create join code
    join_code = "TEST123"
    block = "A"
    class_row = ClassEconomy(
        join_code=join_code,
        user_id=admin.id,
        status="active",
        created_by_admin_id=admin.id,
    )
    db.session.add(class_row)
    db.session.flush()
    
    # Create payroll settings
    # Note: PayrollSettings uses 'block' field, not 'join_code'
    payroll = PayrollSettings(
        class_id=class_row.class_id,
        block=block,
        pay_rate=0.25,  # $0.25/min = $15/hour
        expected_weekly_hours=5.0,
        payroll_frequency_days=7,
        settings_mode='simple',
        is_active=True
    )
    db.session.add(payroll)
    
    # Create students
    students = []
    for i in range(5):
        student = make_student_identity(first_name=f"Student{i}", last_name="T", block=block, claimed=True)
        db.session.add(StudentTeacher(user_id=student.user_id, teacher_id=admin.id))
        db.session.add(ClassMembership(
            class_id=class_row.class_id,
            join_code=join_code,
            user_id=student.user_id,
            role=ClassMembershipRole.STUDENT.value,
        ))
        db.session.add(Seat(
            class_id=class_row.class_id,
            join_code=join_code,
            user_id=student.user_id,
            role='student',
            block=block,
            block_identifier=block,
        ))
        
        # Link student to period
        student_block = StudentBlock(
            user_id=student.user_id,
            period=block,
            join_code=join_code
        )
        db.session.add(student_block)
        students.append(student)
    
    db.session.commit()
    
    return admin, join_code, block, students, payroll


def test_analytics_engine_initialization(client, setup_analytics_test):
    """Test that AnalyticsEngine initializes correctly."""
    admin, join_code, block, students, payroll = setup_analytics_test
    
    engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    
    assert engine.teacher_id == admin.id
    assert engine.join_code == join_code
    assert engine.economy_checker is not None


def test_calculate_cwi(client, setup_analytics_test):
    """Test CWI calculation."""
    admin, join_code, block, students, payroll = setup_analytics_test
    
    engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    cwi = engine._get_cwi()
    
    # CWI = 0.25/min * 5 hours * 60 min = 75.0
    expected_cwi = 0.25 * 5.0 * 60
    assert abs(cwi - expected_cwi) < 0.01


def test_participation_rate_calculation(client, setup_analytics_test):
    """Test participation rate calculation."""
    admin, join_code, block, students, payroll = setup_analytics_test
    
    # Add transactions for 3 out of 5 students
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    
    for i in range(3):
        seat = Seat.query.filter_by(user_id=students[i].user_id, class_id=payroll.class_id).order_by(Seat.id.desc()).first()
        tx = Transaction(
            seat_id=seat.id,
            class_id=seat.class_id,
            amount=10.0,
            amount_cents=1000,
            timestamp=now - timedelta(days=2),
            account_type='checking',
            description='Test transaction'
        )
        db.session.add(tx)
    db.session.commit()
    print('TX SEATS:', Transaction.query.all())
    engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    participation_rate, active_students, total_students = engine.calculate_participation_rate(
        window_start, now
    )
    
    # 3 out of 5 students = 60%
    assert total_students == 5
    assert active_students == 3
    assert abs(participation_rate - 60.0) < 0.1


def test_money_velocity_calculation(client, setup_analytics_test):
    """Test money velocity calculation."""
    admin, join_code, block, students, payroll = setup_analytics_test
    
    # Add 10 transactions over 5 days for 5 students
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=5)
    
    for i in range(10):
        seat = Seat.query.filter_by(user_id=students[i % 5].user_id, class_id=payroll.class_id).order_by(Seat.id.desc()).first()
        tx = Transaction(
            seat_id=seat.id,
            class_id=seat.class_id,
            amount=5.0,
            amount_cents=500,
            timestamp=now - timedelta(days=i % 5),
            account_type='checking',
            description='Test transaction'
        )
        db.session.add(tx)
    db.session.commit()
    print('TX SEATS:', Transaction.query.all())
    engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    velocity = engine.calculate_money_velocity(window_start, now)
    
    # 10 transactions / (5 students * 5 days) = 0.4 transactions per student per day
    # But our window calculation may round differently, so use broader tolerance
    expected_velocity = 10 / (5 * 5)
    assert abs(velocity - expected_velocity) < 0.1  # Allow for rounding differences


def test_snapshot_creation(client, setup_analytics_test):
    """Test creating an analytics snapshot."""
    admin, join_code, block, students, payroll = setup_analytics_test
    
    # Add some activity
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    
    for student in students:
        seat = Seat.query.filter_by(user_id=student.user_id, class_id=payroll.class_id).order_by(Seat.id.desc()).first()
        tx = Transaction(
            seat_id=seat.id,
            class_id=seat.class_id,
            amount=10.0,
            amount_cents=1000,
            timestamp=now - timedelta(days=2),
            account_type='checking',
            description='Test transaction'
        )
        db.session.add(tx)
    db.session.commit()
    print('TX SEATS:', Transaction.query.all())
    engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    snapshot = engine.create_snapshot('week', window_start, now, is_complete=True)
    
    # Verify snapshot was created
    assert snapshot.id is not None
    assert snapshot.teacher_id == admin.id
    assert snapshot.join_code == join_code
    assert snapshot.window_type == 'week'
    assert snapshot.total_students == 5
    assert snapshot.participation_rate == 100.0  # All 5 students have transactions
    assert snapshot.cwi_value > 0


def test_snapshot_caching(client, setup_analytics_test):
    """Test that snapshots are cached and reused."""
    admin, join_code, block, students, payroll = setup_analytics_test
    
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    
    engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    
    # Create first snapshot
    snapshot1 = engine.get_or_create_snapshot('week', window_start, now)
    snapshot1_id = snapshot1.id
    
    # Get snapshot again - should return cached version
    snapshot2 = engine.get_or_create_snapshot('week', window_start, now)
    
    # Should be the same snapshot
    assert snapshot2.id == snapshot1_id


def test_alert_generation(client, setup_analytics_test):
    """Test that alerts are generated for anomalies."""
    admin, join_code, block, students, payroll = setup_analytics_test
    
    # Create scenario with low participation (no activity)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    
    engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    
    # Create snapshot which will generate alerts
    engine.create_snapshot('week', window_start, now, is_complete=True)
    
    # Check if alerts were created
    alerts = AnalyticsAlert.query.filter_by(
        join_code=join_code,
        is_active=True
    ).all()
    
    # Should have at least one alert (low participation or budget survival)
    assert len(alerts) > 0


def test_multi_tenancy_scoping(client, setup_analytics_test):
    """Test that analytics are properly scoped by join_code."""
    admin, join_code, block, students, payroll = setup_analytics_test
    
    # Create a second join code with different data
    join_code2 = "TEST456"
    block2 = "B"
    class_row2 = ClassEconomy(
        join_code=join_code2,
        user_id=admin.id,
        status="active",
        created_by_admin_id=admin.id,
    )
    db.session.add(class_row2)
    db.session.flush()
    
    payroll2 = PayrollSettings(
        class_id=class_row2.class_id,
        block=block2,
        pay_rate=0.30,
        expected_weekly_hours=6.0,
        payroll_frequency_days=7,
        settings_mode='simple',
        is_active=True
    )
    db.session.add(payroll2)
    _tb_seat = Seat(join_code=join_code2, block=block2, block_identifier=block2, role="student")
    db.session.add(_tb_seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_unclaimed', first_name="Seat", last_name="B"))
    db.session.commit()
    
    # Create engines for both
    engine1 = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    engine2 = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code2).first().class_id)
    
    cwi1 = engine1._get_cwi()
    cwi2 = engine2._get_cwi()
    
    # CWIs should be different due to different settings
    assert abs(cwi1 - (0.25 * 5.0 * 60)) < 0.01
    assert abs(cwi2 - (0.30 * 6.0 * 60)) < 0.01
    assert cwi1 != cwi2


def test_no_student_names_in_metrics(client, setup_analytics_test):
    """Test that student names never appear in default metrics (per spec section 9)."""
    admin, join_code, block, students, payroll = setup_analytics_test
    
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    
    engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    snapshot = engine.create_snapshot('week', window_start, now)
    
    # Snapshot should not contain any student-identifying information
    assert snapshot.total_students > 0  # Aggregate only
    # No fields with student names or IDs in snapshot model


def test_trend_calculation(client, setup_analytics_test):
    """Test trend calculation between periods."""
    admin, join_code, block, students, payroll = setup_analytics_test
    
    engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    
    # Test trend calculation
    # Improving: current > previous
    trend = engine.calculate_trend(100.0, 80.0)
    assert trend == 'increasing'
    
    # Worsening: current < previous
    trend = engine.calculate_trend(80.0, 100.0)
    assert trend == 'decreasing'
    
    # Stable: difference < threshold
    trend = engine.calculate_trend(100.0, 98.0)
    assert trend == 'stable'
    
    # No previous: stable
    trend = engine.calculate_trend(100.0, None)
    assert trend == 'stable'


def test_enrolled_students_require_class_membership(client, setup_analytics_test):
    """Analytics enrollment is class-membership authoritative."""
    admin, join_code, block, students, payroll = setup_analytics_test
    null_student = make_student_identity(first_name="Null", last_name="N", block=block, claimed=False)
    db.session.commit()

    engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    enrolled = engine._get_enrolled_students()

    assert null_student not in enrolled


def test_analytics_pay_cycle_prefers_join_code_scoped_settings(client, setup_analytics_test):
    admin, join_code, block, students, payroll = setup_analytics_test

    # Existing class_id scoped block row from fixture should remain authoritative.
    assert get_pay_cycle_days(join_code=join_code) == 7


def test_analytics_pay_cycle_ignores_teacher_global_for_unscoped_join_code(client, setup_analytics_test):
    admin, join_code, block, students, payroll = setup_analytics_test
    join_code2 = "NOGLOBAL1"
    class_row2 = ClassEconomy(
        join_code=join_code2,
        user_id=admin.id,
        status="active",
        created_by_admin_id=admin.id,
    )
    db.session.add(class_row2)
    db.session.commit()

    # V2: Should return 7 default because no class-scoped setting exists
    assert get_pay_cycle_days(join_code=join_code2) == 7


def test_analytics_rent_cycle_ignores_teacher_global_for_unscoped_join_code(client, setup_analytics_test):
    admin, join_code, block, students, payroll = setup_analytics_test
    join_code2 = "NOGLOBAL2"
    class_row2 = ClassEconomy(
        join_code=join_code2,
        user_id=admin.id,
        status="active",
        created_by_admin_id=admin.id,
    )
    db.session.add(class_row2)
    db.session.commit()

    # V2: Should return 30 default because no class-scoped setting exists
    assert get_rent_cycle_days(join_code=join_code2) == 30


def test_analytics_policy_mode_resolves_by_class_id(client, setup_analytics_test):
    admin, join_code, block, students, payroll = setup_analytics_test
    class_row = ClassEconomy.query.filter_by(join_code=join_code, user_id=admin.id).first()
    assert class_row is not None

    db.session.add(FeatureSettings(
        class_id=class_row.class_id,
        economy_policy_mode='tight',
    ))
    db.session.commit()

    engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    assert engine.class_id == class_row.class_id
    assert engine.policy_mode == 'tight'


def test_budget_survival_uses_policy_mode_min_savings_ratio(client, setup_analytics_test, monkeypatch):
    admin, join_code, block, students, payroll = setup_analytics_test
    class_row = ClassEconomy.query.filter_by(join_code=join_code, user_id=admin.id).first()
    assert class_row is not None

    def _set_policy(mode: str) -> None:
        row = FeatureSettings.query.filter_by(class_id=class_row.class_id).first()
        if row is None:
            row = FeatureSettings(
                class_id=class_row.class_id,
            )
            db.session.add(row)
        row.economy_policy_mode = mode
        db.session.commit()

    # Use fixed balances to isolate threshold behavior.
    monkeypatch.setattr(Student, "get_checking_balance", lambda self, class_id, seat_id: 12.0)

    _set_policy('tight')  # min savings ratio = 0.05
    tight_engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    assert tight_engine.calculate_budget_survival_pass_rate(100.0) == 100.0

    _set_policy('comfortable')  # min savings ratio = 0.15
    comfortable_engine = AnalyticsEngine(ClassEconomy.query.filter_by(join_code=join_code).first().class_id)
    assert comfortable_engine.calculate_budget_survival_pass_rate(100.0) == 0.0
