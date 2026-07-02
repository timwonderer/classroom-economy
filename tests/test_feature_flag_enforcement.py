"""
Test that feature flags properly block access to disabled features.

This ensures that when a teacher disables a feature (banking, payroll, etc.),
students cannot access those routes even via direct URL.
"""

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from app.models import Student, Admin, Transaction, ClassEconomy, ClassFeature, ClassMembership, StoreItem, Seat, User, UserRole, IdentityProfile
from tests.helpers.class_scope import make_student_identity
from app.extensions import db
from app.hash_utils import get_random_salt, hash_username
from tests.helpers.admin_context import login_admin
from tests.helpers.canonical_session import set_canonical_context

def _bind_canonical_teacher(teacher):
    user = User(
        user_role=UserRole.TEACHER,
        username_hash=teacher.username_hash,
        username_lookup_hash=teacher.username_lookup_hash,
        totp_secret_encrypted=teacher.totp_secret,
    )
    db.session.add(user)
    db.session.flush()
    teacher.user_id = user.id
    return user


def _bind_canonical_student(student):
    user = User(
        user_role=UserRole.STUDENT,
        username_hash=student.username_hash,
        passphrase_hash=student.passphrase_hash,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _login_student(client, data, *, transfer_token=None):
    with client.session_transaction() as sess:
        set_canonical_context(
            sess,
            user_id=data['user_id'],
            class_id=data['class_id'],
            seat_id=data['seat_id'],
            role="student",
            join_code=data['join_code'],
        )
        sess['current_period'] = data['period']
        if transfer_token:
            sess['transfer_token'] = transfer_token


@pytest.fixture
def setup_student_with_disabled_banking(client):
    """Create a student with banking feature disabled."""
    # Create teacher
    teacher = make_admin("teacher1", "secret123")
    db.session.add(teacher)
    db.session.commit()

    # Create student
    student = make_student_identity(block="Period1", first_name="Bob", last_name="B")
    user = _bind_canonical_student(student)
    
    # Link student to teacher
    from app.models import StudentTeacher
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id))
    db.session.commit()

    join_code = "MATH1B"
    
    # Create ClassEconomy first for FK constraint
    economy = ClassEconomy(
        join_code=join_code,
        user_id=teacher.id,
        display_name='Math Period 1B',
        created_by_admin_id=teacher.id
    )
    db.session.add(economy)
    db.session.flush()
    
    # Create TeacherBlock entry (claimed seat)
    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    seat = Seat(user_id=student_user.id, class_id=economy.class_id, join_code=join_code, block="Period1", block_identifier="Period1", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat.id, profile_type='student_claimed', first_name="Bob", last_initial="B"))
    db.session.add(seat)
    student_seat = Seat(
        class_id=economy.class_id,
        role='student',
        join_code=join_code,
        user_id=user.id,
        block="Period1",
        block_identifier="Period1",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(student_seat)
    db.session.commit()

    # Add some money to checking account
    tx = Transaction(join_code=join_code,
        class_id=economy.class_id,
        seat_id=student_seat.id,
        amount=100.0,
        account_type='checking',
        type='Initial',
        description='Starting balance'
    )
    db.session.add(tx)
    db.session.commit()

    for row in ClassFeature.query.filter(
        ClassFeature.class_id == economy.class_id,
        ClassFeature.feature_name.in_(["banking", "payroll"]),
    ).all():
        db.session.delete(row)
    db.session.commit()

    return {
        'teacher': teacher,
        'student': student,
        'join_code': join_code,
        'class_id': economy.class_id,
        'seat_id': student_seat.id,
        'user_id': user.id,
        'period': 'Period1',
    }


def test_transfer_blocked_when_banking_disabled(client, setup_student_with_disabled_banking):
    """Test that transfer route is blocked when banking is disabled."""
    data = setup_student_with_disabled_banking
    _login_student(client, data)
    
    # Try to access transfer page (GET)
    response = client.get('/student/transfer', follow_redirects=False)
    
    assert response.status_code == 404


def test_transfer_post_blocked_when_banking_disabled(client, setup_student_with_disabled_banking):
    """Test that transfer POST is blocked when banking is disabled."""
    data = setup_student_with_disabled_banking
    _login_student(client, data, transfer_token='test-token-blocked')
    
    # Try to submit a transfer (POST)
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '50.00',
        'passphrase': 'bob_pass',
        'transfer_token': 'test-token-blocked'
    }, follow_redirects=False)
    
    assert response.status_code == 404
    
    # Verify no transactions were created
    
    # Should only have the initial transaction, no transfer
    all_transactions = Transaction.query.filter_by(seat_id=data['seat_id']).all()
    assert len(all_transactions) == 1
    assert all_transactions[0].type == 'Initial'


def test_payroll_blocked_when_payroll_disabled(client, setup_student_with_disabled_banking):
    """Test that payroll route is blocked when payroll is disabled."""
    data = setup_student_with_disabled_banking
    _login_student(client, data)
    
    # Try to access payroll page
    response = client.get('/student/payroll', follow_redirects=False)
    
    assert response.status_code == 404


@pytest.fixture
def setup_student_with_enabled_banking(client):
    """Create a student with banking feature enabled."""
    # Create teacher
    teacher = make_admin("teacher2", "secret456")
    db.session.add(teacher)
    db.session.commit()

    # Create student
    student = make_student_identity(block="Period2", first_name="Carol", last_name="C")
    user = _bind_canonical_student(student)

    # Link student to teacher
    from app.models import StudentTeacher
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id))
    db.session.commit()

    join_code = "MATH2C"
    
    # Create ClassEconomy first for FK constraint
    economy = ClassEconomy(
        join_code=join_code,
        user_id=teacher.id,
        display_name='Math Period 2C',
        created_by_admin_id=teacher.id
    )
    db.session.add(economy)
    db.session.flush()
    
    # Create TeacherBlock entry (claimed seat)
    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    seat = Seat(user_id=student_user.id, class_id=economy.class_id, join_code=join_code, block="Period2", block_identifier="Period2", role="student", claimed_at=datetime.now(timezone.utc))
    db.session.add(seat)
    db.session.flush()
    db.session.add(IdentityProfile(seat_id=seat.id, profile_type='student_claimed', first_name="Carol", last_initial="C"))
    db.session.add(seat)
    student_seat = Seat(
        class_id=economy.class_id,
        role='student',
        join_code=join_code,
        user_id=user.id,
        block="Period2",
        block_identifier="Period2",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(student_seat)
    db.session.commit()

    # Add some money to checking account
    tx = Transaction(join_code=join_code,
        class_id=economy.class_id,
        seat_id=student_seat.id,
        amount=100.0,
        account_type='checking',
        type='Initial',
        description='Starting balance'
    )
    db.session.add(tx)
    db.session.flush()
    db.session.add(ClassFeature(class_id=economy.class_id, feature_name='banking'))
    db.session.commit()

    return {
        'teacher': teacher,
        'student': student,
        'join_code': join_code,
        'class_id': economy.class_id,
        'seat_id': student_seat.id,
        'user_id': user.id,
        'period': 'Period2',
    }


def test_transfer_allowed_when_banking_enabled(client, setup_student_with_enabled_banking):
    """Test that transfer routes are not blocked by the feature flag when enabled."""
    data = setup_student_with_enabled_banking
    _login_student(client, data, transfer_token='test-token-allowed')
    
    # Access transfer page (GET) should work
    response = client.get('/student/transfer', follow_redirects=False)
    assert response.status_code == 200
    assert b'Transfer Details' in response.data or b'Finances' in response.data
    
    # Submit a transfer (POST) should not be blocked by the feature flag layer.
    response = client.post('/student/transfer', data={
        'from_account': 'checking',
        'to_account': 'savings',
        'amount': '50.00',
        'passphrase': 'carol_pass',
        'transfer_token': 'test-token-allowed'
    }, follow_redirects=False)

    assert response.status_code == 302
    assert '/student/dashboard' in response.location or '/student/transfer' in response.location


def test_payroll_allowed_when_payroll_enabled(client, setup_student_with_enabled_banking):
    """Test that payroll works normally when payroll is enabled."""
    data = setup_student_with_enabled_banking
    _login_student(client, data)
    
    # Access payroll page should work
    response = client.get('/student/payroll', follow_redirects=False)
    assert response.status_code == 200
    assert b'Payroll' in response.data or b'payroll' in response.data


def test_admin_banking_rejects_disabled_class_scope(client):
    teacher = make_admin("teacher_admin_feature_scope", "secret789")
    db.session.add(teacher)
    db.session.flush()
    user = _bind_canonical_teacher(teacher)

    join_code = "BANKA1"
    economy = ClassEconomy(
        join_code=join_code,
        user_id=teacher.id,
        display_name='Banking Period A',
        created_by_admin_id=teacher.id,
    )
    db.session.add(economy)
    db.session.flush()
    db.session.add(ClassMembership(join_code=join_code, admin_id=teacher.id, role="admin"))
    teacher_seat = Seat(
        class_id=economy.class_id,
        join_code=join_code,
        role="teacher",
        user_id=user.id,
    )
    db.session.add(teacher_seat)

    _tb_seat = Seat(join_code=join_code, block="A", block_identifier="A", role="student")

    db.session.add(_tb_seat)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_unclaimed', first_name="Dana", last_initial="D"))

    for row in ClassFeature.query.filter_by(class_id=economy.class_id, feature_name='banking').all():
        db.session.delete(row)
    db.session.commit()

    login_admin(
        client,
        teacher.id,
        join_code,
        user_id=user.id,
        class_id=economy.class_id,
        seat_id=teacher_seat.id,
    )

    response = client.get('/admin/banking?settings_block=A')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data


def _create_admin_feature_scope(teacher, *, join_code, block, feature_name, enabled):
    economy = ClassEconomy(
        join_code=join_code,
        user_id=teacher.id,
        display_name=f'{feature_name.title()} Period {block}',
        created_by_admin_id=teacher.id,
    )
    db.session.add(economy)
    db.session.flush()

    _tb_seat = Seat(join_code=join_code, block=block, block_identifier=block, role="student")

    db.session.add(_tb_seat)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_unclaimed', first_name=f"{feature_name.title()}Student", last_initial="T"))
    db.session.add(ClassMembership(
        class_id=economy.class_id,
        join_code=join_code,
        admin_id=teacher.id,
        role="admin",
    ))
    teacher_seat = Seat(
        class_id=economy.class_id,
        join_code=join_code,
        role="teacher",
        user_id=teacher.user_id,
    )
    db.session.add(teacher_seat)

    if not enabled:
        for row in ClassFeature.query.filter_by(class_id=economy.class_id, feature_name=feature_name).all():
            db.session.delete(row)
    return economy


def test_admin_store_rejects_disabled_class_scope(client):
    teacher = make_admin("teacher_admin_store_scope", "secret_store_scope")
    db.session.add(teacher)
    db.session.flush()
    user = _bind_canonical_teacher(teacher)

    _create_admin_feature_scope(teacher, join_code="STORE1", block="1", feature_name="store", enabled=True)
    disabled_economy = _create_admin_feature_scope(teacher, join_code="STORE2", block="2", feature_name="store", enabled=False)
    db.session.commit()

    teacher_seat = Seat.query.filter_by(class_id=disabled_economy.class_id, role="teacher").first()
    login_admin(
        client,
        teacher.id,
        'STORE2',
        user_id=user.id,
        class_id=disabled_economy.class_id,
        seat_id=teacher_seat.id,
    )

    response = client.get('/admin/store')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data


def test_admin_hall_pass_rejects_disabled_class_scope(client):
    teacher = make_admin("teacher_admin_hall_scope", "secret_hall_scope")
    db.session.add(teacher)
    db.session.flush()
    user = _bind_canonical_teacher(teacher)

    _create_admin_feature_scope(teacher, join_code="HALL1", block="1", feature_name="hall_pass", enabled=True)
    disabled_economy = _create_admin_feature_scope(teacher, join_code="HALL2", block="2", feature_name="hall_pass", enabled=False)
    db.session.commit()

    teacher_seat = Seat.query.filter_by(class_id=disabled_economy.class_id, role="teacher").first()
    login_admin(
        client,
        teacher.id,
        'HALL2',
        user_id=user.id,
        class_id=disabled_economy.class_id,
        seat_id=teacher_seat.id,
    )

    response = client.get('/admin/hall-pass')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data


def test_admin_payroll_rejects_disabled_class_scope(client):
    teacher = make_admin("teacher_admin_payroll_scope", "secret_payroll_scope")
    db.session.add(teacher)
    db.session.flush()
    user = _bind_canonical_teacher(teacher)

    _create_admin_feature_scope(teacher, join_code="PAY1", block="1", feature_name="payroll", enabled=True)
    disabled_economy = _create_admin_feature_scope(teacher, join_code="PAY2", block="2", feature_name="payroll", enabled=False)
    db.session.commit()
    teacher_seat = Seat.query.filter_by(class_id=disabled_economy.class_id, role="teacher").first()
    assert teacher_seat is not None

    login_admin(
        client,
        teacher.id,
        'PAY2',
        user_id=user.id,
        class_id=disabled_economy.class_id,
        seat_id=teacher_seat.id,
    )

    response = client.get('/admin/payroll')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data




def test_admin_store_delete_rejects_disabled_class_scope(client):
    teacher = make_admin("teacher_admin_store_delete_scope", "secret_store_delete_scope")
    db.session.add(teacher)
    db.session.flush()
    user = _bind_canonical_teacher(teacher)

    _create_admin_feature_scope(teacher, join_code="STD1", block="1", feature_name="store", enabled=True)
    disabled_economy = _create_admin_feature_scope(teacher, join_code="STD2", block="2", feature_name="store", enabled=False)
    store_item = StoreItem(
        user_id=teacher.id,
        class_id=disabled_economy.class_id,
        name="Pencil",
        description="Simple item",
        price=1,
        item_type='immediate',
        is_active=True,
    )
    db.session.add(store_item)
    db.session.commit()

    teacher_seat = Seat.query.filter_by(class_id=disabled_economy.class_id, role="teacher").first()
    login_admin(
        client,
        teacher.id,
        'STD2',
        user_id=user.id,
        class_id=disabled_economy.class_id,
        seat_id=teacher_seat.id,
    )

    response = client.post(
        f'/admin/store/delete/{store_item.id}',
        data={'join_code': 'STD2'},
        follow_redirects=False,
    )
    assert response.status_code == 404
    db.session.refresh(store_item)
    assert store_item.is_active is True


def test_student_rent_rejects_disabled_feature_scope(client):
    teacher = make_admin("teacher_rent_disabled", "secret999")
    db.session.add(teacher)
    db.session.commit()

    student = make_student_identity(block="Period3", first_name="Riley", last_name="R")
    user = _bind_canonical_student(student)

    from app.models import StudentTeacher
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id))

    join_code = "RENT03"
    economy = ClassEconomy(
        join_code=join_code,
        user_id=teacher.id,
        display_name='Rent Period 3',
        created_by_admin_id=teacher.id,
    )
    db.session.add(economy)
    db.session.flush()

    # Auto-injected Canonical User
    student_user = User(username_hash=f"auto_{student.id}", username_lookup_hash=f"auto_l_{student.id}", user_role=UserRole.STUDENT)
    db.session.add(student_user)
    db.session.flush()
    _tb_seat = Seat(user_id=student_user.id, join_code=join_code, block="Period3", block_identifier="Period3", role="student", claimed_at=datetime.now(timezone.utc))

    db.session.add(_tb_seat)

    db.session.flush()

    db.session.add(IdentityProfile(seat_id=_tb_seat.id, profile_type='student_claimed', first_name="Riley", last_initial="R"))
    student_seat = Seat(
        class_id=economy.class_id,
        join_code=join_code,
        role='student',
        user_id=user.id,
        block='Period3',
        block_identifier='Period3',
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(student_seat)

    for row in ClassFeature.query.filter_by(class_id=economy.class_id, feature_name='rent').all():
        db.session.delete(row)
    db.session.commit()

    _login_student(client, {
        'student': student,
        'user_id': user.id,
        'join_code': join_code,
        'class_id': economy.class_id,
        'seat_id': student_seat.id,
        'period': 'Period3',
    })

    response = client.get('/student/rent', follow_redirects=False)
    assert response.status_code == 404
