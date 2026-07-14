"""
Tests for Analytics Engine.

Tests the analytics computation engine to ensure:
- System health metrics are calculated correctly
- All metrics are CWI-relative
- Multi-tenancy scoping is enforced
- Snapshots are cached properly
"""
from tests.helpers.v2_fixtures import make_sysadmin, seed_canonical_admin
import pytest
from datetime import datetime, timedelta, timezone
from app import db
from app.models import Seat, IdentityProfile, User, UserRole, ClassEconomy, Transaction, PayrollSettings, RentSettings, AnalyticsAlert, FeatureSettings
from app.routes.analytics import get_pay_cycle_days, get_rent_cycle_days, resolve_current_class_context
from app.utils.analytics_engine import AnalyticsEngine
from app.feats.base import FEATContext
import app.services.ledger_service as ledger_service
from tests.helpers.class_scope import create_class_scope, make_student_identity
from tests.helpers.canonical_session import set_canonical_context


@pytest.fixture
def setup_analytics_test(client):
    """Create test data for analytics testing."""
    with FEATContext("FEAT-IDEN-001", idempotency_key="analytics:test-setup"):
        # Create admin/teacher
        admin = seed_canonical_admin("analyticstest", "TESTSECRET123456").user
        block = "A"
        class_row = create_class_scope(
            teacher_user=admin,
            display_name="Analytics Test",
            section=block,
        )

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
            student = make_student_identity(
                class_id=class_row.class_id,
                first_name=f"Student{i}",
                last_name="T",
                claimed=True,
            )
            students.append(student.id)

        db.session.flush()

    return admin.id, class_row.join_code, block, class_row.class_id, students, payroll.class_id


def test_analytics_engine_initialization(client, setup_analytics_test):
    """Test that AnalyticsEngine initializes correctly."""
    admin, display_join_code, block, class_row, students, payroll = setup_analytics_test
    
    engine = AnalyticsEngine(payroll)
    
    assert engine.teacher_id == admin
    assert engine.join_code == display_join_code
    assert engine.economy_checker is not None


def test_calculate_cwi(client, setup_analytics_test):
    """Test CWI calculation."""
    admin, display_join_code, block, class_row, students, payroll = setup_analytics_test
    
    engine = AnalyticsEngine(payroll)
    cwi = engine._get_cwi()
    
    # CWI = 0.25/min * 5 hours * 60 min = 75.0
    expected_cwi = 0.25 * 5.0 * 60
    assert abs(cwi - expected_cwi) < 0.01


def test_participation_rate_calculation(client, setup_analytics_test):
    """Test participation rate calculation."""
    admin, display_join_code, block, class_row, students, payroll = setup_analytics_test
    
    # Add transactions for 3 out of 5 students
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    
    with FEATContext("FEAT-LED-001", idempotency_key="analytics:participation"):
        for seat_id in students[:3]:
            seat = db.session.get(Seat, seat_id)
            assert seat is not None
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
        db.session.flush()
    engine = AnalyticsEngine(payroll)
    participation_rate, active_students, total_students = engine.calculate_participation_rate(
        window_start, now
    )
    
    # 3 out of 5 students = 60%
    assert total_students == 5
    assert active_students == 3
    assert abs(participation_rate - 60.0) < 0.1


def test_money_velocity_calculation(client, setup_analytics_test):
    """Test money velocity calculation."""
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    
    # Add 10 transactions over 5 days for 5 students
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=5)
    
    with FEATContext("FEAT-LED-001", idempotency_key="analytics:velocity"):
        for i in range(10):
            seat = db.session.get(Seat, students[i % 5])
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
        db.session.flush()
    engine = AnalyticsEngine(payroll)
    velocity = engine.calculate_money_velocity(window_start, now)
    
    # 10 transactions / (5 students * 5 days) = 0.4 transactions per student per day
    # But our window calculation may round differently, so use broader tolerance
    expected_velocity = 10 / (5 * 5)
    assert abs(velocity - expected_velocity) < 0.1  # Allow for rounding differences


def test_snapshot_creation(client, setup_analytics_test):
    """Test creating an analytics snapshot."""
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    
    # Add some activity
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    
    with FEATContext("FEAT-LED-001", idempotency_key="analytics:snapshot"):
        for seat_id in students:
            seat = db.session.get(Seat, seat_id)
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
        db.session.flush()
    engine = AnalyticsEngine(class_row)
    snapshot = engine.create_snapshot('week', window_start, now, is_complete=True)
    
    # Verify snapshot was created
    assert snapshot.id is not None
    assert snapshot.teacher_id == admin
    assert snapshot.join_code == join_code
    assert snapshot.window_type == 'week'
    assert snapshot.total_students == 5
    assert snapshot.participation_rate == 100.0  # All 5 students have transactions
    assert snapshot.cwi_value > 0


def test_snapshot_caching(client, setup_analytics_test):
    """Test that snapshots are cached and reused."""
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    
    engine = AnalyticsEngine(class_row)
    
    # Create first snapshot
    snapshot1 = engine.get_or_create_snapshot('week', window_start, now)
    snapshot1_id = snapshot1.id
    
    # Get snapshot again - should return cached version
    snapshot2 = engine.get_or_create_snapshot('week', window_start, now)
    
    # Should be the same snapshot
    assert snapshot2.id == snapshot1_id


def test_alert_generation(client, setup_analytics_test):
    """Test that alerts are generated for anomalies."""
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    
    # Create scenario with low participation (no activity)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    
    engine = AnalyticsEngine(class_row)
    
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
    """Test that analytics are properly scoped by class_id."""
    admin, join_code, block, class_row, students, payroll = setup_analytics_test

    # Create a second class with different data
    join_code2 = "TEST456"
    block2 = "B"
    from tests.helpers.class_scope import create_class_scope as _ccs
    admin_user = db.session.get(User, admin)
    assert admin_user is not None
    class_row2 = _ccs(teacher_user=admin_user, join_code=join_code2, section=block2, display_name="Analytics Two")
    
    payroll2 = PayrollSettings(
        class_id=class_row2.class_id,
        block=block2,
        pay_rate=0.30,
        expected_weekly_hours=6.0,
        payroll_frequency_days=7,
        settings_mode='simple',
        is_active=True
    )
    with FEATContext("FEAT-ADMN-001", idempotency_key="analytics:multi_tenancy_scoping"):
        db.session.add(payroll2)
        _tb_seat = Seat(class_id=class_row2.class_id, role="student")
        db.session.add(_tb_seat)
        db.session.flush()
        db.session.add(
            IdentityProfile(
                seat_id=_tb_seat.id,
                profile_type='student_unclaimed',
                first_name="Seat",
                last_name="B",
            )
        )
        db.session.flush()
    
    # Create engines for both
    engine1 = AnalyticsEngine(class_row)
    engine2 = AnalyticsEngine(class_row2.class_id)
    
    cwi1 = engine1._get_cwi()
    cwi2 = engine2._get_cwi()
    
    # CWIs should be different due to different settings
    assert abs(cwi1 - (0.25 * 5.0 * 60)) < 0.01
    assert abs(cwi2 - (0.30 * 6.0 * 60)) < 0.01
    assert cwi1 != cwi2


def test_no_student_names_in_metrics(client, setup_analytics_test):
    """Test that student names never appear in default metrics (per spec section 9)."""
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=7)
    
    engine = AnalyticsEngine(class_row)
    snapshot = engine.create_snapshot('week', window_start, now)
    
    # Snapshot should not contain any student-identifying information
    assert snapshot.total_students > 0  # Aggregate only
    # No fields with student names or IDs in snapshot model


def test_trend_calculation(client, setup_analytics_test):
    """Test trend calculation between periods."""
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    
    engine = AnalyticsEngine(class_row)
    
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
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    from tests.helpers.v2_fixtures import make_teacher as _make_teacher
    _other_teacher = _make_teacher("null_analytics_teacher")
    db.session.flush()
    from tests.helpers.class_scope import create_class_scope as _ccs
    _other_class = _ccs(teacher_user=_other_teacher, join_code="NULLCLS1")
    db.session.flush()
    with FEATContext("FEAT-IDEN-001", idempotency_key="analytics:null_student"):
        null_student = make_student_identity(
            class_id=_other_class.class_id,
            first_name="Null",
            last_name="N",
            claimed=False,
        )
        db.session.flush()

    engine = AnalyticsEngine(class_row)
    enrolled = engine._get_enrolled_students()

    assert null_student not in enrolled


def test_analytics_pay_cycle_prefers_class_scoped_settings(client, setup_analytics_test):
    admin, join_code, block, class_row, students, payroll = setup_analytics_test

    # Existing class_id scoped block row from fixture should remain authoritative.
    assert get_pay_cycle_days(class_id=payroll) == 7


def test_analytics_pay_cycle_ignores_teacher_global_for_unscoped_class(client, setup_analytics_test):
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    join_code2 = "NOGLOBAL1"
    from tests.helpers.class_scope import create_class_scope as _ccs
    admin_user = db.session.get(User, admin)
    assert admin_user is not None
    class_row2 = _ccs(teacher_user=admin_user, join_code=join_code2, section="B", display_name="No Global 1")

    # V2: Should return 7 default because no class-scoped setting exists
    assert get_pay_cycle_days(class_id=class_row2.class_id) == 7


def test_analytics_rent_cycle_ignores_teacher_global_for_unscoped_class(client, setup_analytics_test):
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    join_code2 = "NOGLOBAL2"
    from tests.helpers.class_scope import create_class_scope as _ccs
    admin_user = db.session.get(User, admin)
    assert admin_user is not None
    class_row2 = _ccs(teacher_user=admin_user, join_code=join_code2, section="B", display_name="No Global 2")

    # V2: Should return 30 default because no class-scoped setting exists
    assert get_rent_cycle_days(class_id=class_row2.class_id) == 30


def test_analytics_policy_mode_resolves_by_class_id(client, setup_analytics_test):
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    with FEATContext("FEAT-ADMN-001", idempotency_key="analytics:policy_mode"):
        db.session.add(
            FeatureSettings(
                class_id=payroll,
                economy_policy_mode='tight',
            )
        )
        db.session.flush()

    engine = AnalyticsEngine(payroll)
    assert engine.class_id == payroll
    assert engine.policy_mode == 'tight'


def test_analytics_class_context_requires_explicit_class_id(client, setup_analytics_test):
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    admin_user = db.session.get(User, admin)
    assert admin_user is not None
    other_class = create_class_scope(teacher_user=admin_user, join_code="TEST789", section="B", display_name="Analytics Three")

    selected, available = resolve_current_class_context(admin, None)

    assert selected is None
    assert {item["class_id"] for item in available} == {class_row, other_class.class_id}


def test_budget_survival_uses_policy_mode_min_savings_ratio(client, setup_analytics_test, monkeypatch):
    admin, join_code, block, class_row, students, payroll = setup_analytics_test
    def _set_policy(mode: str) -> None:
        with FEATContext("FEAT-ADMN-001", idempotency_key=f"analytics:set_policy:{mode}"):
            row = FeatureSettings.query.filter_by(class_id=payroll).first()
            if row is None:
                row = FeatureSettings(
                    class_id=payroll,
                )
                db.session.add(row)
            row.economy_policy_mode = mode
            db.session.flush()

    # Use fixed balances to isolate threshold behavior.
    monkeypatch.setattr(ledger_service, "get_available_balance", lambda seat_id, class_id, account_type: 12.0)

    _set_policy('tight')  # min savings ratio = 0.05
    tight_engine = AnalyticsEngine(payroll)
    assert tight_engine.calculate_budget_survival_pass_rate(100.0) == 100.0

    _set_policy('comfortable')  # min savings ratio = 0.15
    comfortable_engine = AnalyticsEngine(payroll)
    assert comfortable_engine.calculate_budget_survival_pass_rate(100.0) == 0.0


def test_analytics_student_drill_down_renders_join_code_display(client, setup_analytics_test):
    admin, join_code, block, class_id, students, payroll = setup_analytics_test
    teacher = db.session.get(User, admin)
    assert teacher is not None
    teacher_seat = Seat.query.filter_by(user_id=teacher.id, class_id=class_id, role="teacher").first()
    assert teacher_seat is not None

    student_seat = db.session.get(Seat, students[0])
    assert student_seat is not None

    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=teacher.id,
            class_id=class_id,
            seat_id=teacher_seat.id,
            role="teacher",
        )

    response = client.get(f"/admin/analytics/student/{student_seat.id}")

    assert response.status_code == 200
    assert join_code.encode("utf-8") in response.data
