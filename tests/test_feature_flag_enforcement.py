"""
Test that feature flags properly block access to disabled features.

This ensures that when a teacher disables a feature (banking, payroll, etc.),
students cannot access those routes even via direct URL.
"""

from tests.helpers.v2_fixtures import make_admin
import pytest
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from app.models import Transaction, ClassEconomy, ClassFeature, StoreItem, Seat, User, UserRole, IdentityProfile
from tests.helpers.class_scope import make_student_identity, create_class_scope
from app.extensions import db
from tests.helpers.admin_context import login_teacher
from tests.helpers.canonical_session import set_canonical_context


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
        sess['current_period'] = data.get('period', 'A')
        if transfer_token:
            sess['transfer_token'] = transfer_token


@pytest.fixture
def setup_student_with_disabled_banking(client):
    """Create a student with banking feature disabled."""
    teacher = make_admin("teacher1")
    db.session.flush()

    join_code = "MATH1B"
    economy = create_class_scope(teacher_user=teacher, join_code=join_code, display_name='Math Period 1B')
    db.session.flush()

    student_seat_obj = make_student_identity(class_id=economy.class_id, first_name="Bob", last_name="B", claimed=True)
    db.session.flush()
    student_seat = Seat.query.filter_by(user_id=student_seat_obj.user_id, class_id=economy.class_id, role="student").first()
    user = db.session.get(User, student_seat_obj.user_id)
    user.passphrase_hash = generate_password_hash('password')

    db.session.add(Transaction(
        join_code=join_code,
        class_id=economy.class_id,
        seat_id=student_seat.id,
        amount=100.0,
        account_type='checking',
        type='Initial',
        description='Starting balance',
    ))
    db.session.flush()
    for row in ClassFeature.query.filter_by(class_id=economy.class_id, feature_name='banking').all():
        db.session.delete(row)
    db.session.commit()

    return {
        'teacher': teacher,
        'join_code': join_code,
        'class_id': economy.class_id,
        'seat_id': student_seat.id,
        'user_id': user.id,
        'period': 'Period2',
    }


@pytest.fixture
def setup_student_with_enabled_banking(client):
    """Create a student with banking feature enabled."""
    teacher = make_admin("teacher_enabled_banking")
    db.session.flush()

    join_code = "MATH1A"
    economy = create_class_scope(teacher_user=teacher, join_code=join_code, display_name='Math Period 1A')
    db.session.flush()

    student_seat_obj = make_student_identity(class_id=economy.class_id, first_name="Carol", last_name="C", claimed=True)
    db.session.flush()
    student_seat = Seat.query.filter_by(user_id=student_seat_obj.user_id, class_id=economy.class_id, role="student").first()
    user = db.session.get(User, student_seat_obj.user_id)
    user.passphrase_hash = generate_password_hash('carol_pass')

    db.session.add(Transaction(
        join_code=join_code,
        class_id=economy.class_id,
        seat_id=student_seat.id,
        amount=100.0,
        account_type='checking',
        type='Initial',
        description='Starting balance',
    ))
    db.session.add(ClassFeature(class_id=economy.class_id, feature_name='banking'))
    db.session.commit()

    return {
        'teacher': teacher,
        'join_code': join_code,
        'class_id': economy.class_id,
        'seat_id': student_seat.id,
        'user_id': user.id,
        'period': 'Period1',
    }


def test_transfer_allowed_when_banking_enabled(client, setup_student_with_enabled_banking):
    """Test that transfer routes are not blocked by the feature flag when enabled."""
    data = setup_student_with_enabled_banking
    _login_student(client, data, transfer_token='test-token-allowed')

    response = client.get('/student/transfer', follow_redirects=False)
    assert response.status_code == 200
    assert b'Transfer Details' in response.data or b'Finances' in response.data

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

    response = client.get('/student/payroll', follow_redirects=False)
    assert response.status_code == 200
    assert b'Payroll' in response.data or b'payroll' in response.data


def _create_admin_feature_scope(teacher, *, join_code, block, feature_name, enabled):
    economy = create_class_scope(
        teacher_user=teacher,
        join_code=join_code,
        display_name=f'{feature_name.title()} Period {block}',
    )
    db.session.flush()

    if not enabled:
        for row in ClassFeature.query.filter_by(class_id=economy.class_id, feature_name=feature_name).all():
            db.session.delete(row)
    return economy


def test_admin_banking_rejects_disabled_class_scope(client):
    teacher = make_admin("teacher_admin_feature_scope")
    db.session.flush()

    economy = create_class_scope(teacher_user=teacher, join_code="BANKA1", display_name='Banking Period A')
    db.session.flush()
    for row in ClassFeature.query.filter_by(class_id=economy.class_id, feature_name='banking').all():
        db.session.delete(row)
    db.session.commit()

    login_teacher(client, teacher, class_id=economy.class_id, join_code="BANKA1")

    response = client.get('/admin/banking?settings_block=A')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data


def test_admin_store_rejects_disabled_class_scope(client):
    teacher = make_admin("teacher_admin_store_scope")
    db.session.flush()

    _create_admin_feature_scope(teacher, join_code="STORE1", block="1", feature_name="store", enabled=True)
    disabled_economy = _create_admin_feature_scope(teacher, join_code="STORE2", block="2", feature_name="store", enabled=False)
    db.session.commit()

    login_teacher(client, teacher, class_id=disabled_economy.class_id, join_code="STORE2")

    response = client.get('/admin/store')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data


def test_admin_hall_pass_rejects_disabled_class_scope(client):
    teacher = make_admin("teacher_admin_hall_scope")
    db.session.flush()

    _create_admin_feature_scope(teacher, join_code="HALL1", block="1", feature_name="hall_pass", enabled=True)
    disabled_economy = _create_admin_feature_scope(teacher, join_code="HALL2", block="2", feature_name="hall_pass", enabled=False)
    db.session.commit()

    login_teacher(client, teacher, class_id=disabled_economy.class_id, join_code="HALL2")

    response = client.get('/admin/hall-pass')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data


def test_admin_payroll_rejects_disabled_class_scope(client):
    teacher = make_admin("teacher_admin_payroll_scope")
    db.session.flush()

    _create_admin_feature_scope(teacher, join_code="PAY1", block="1", feature_name="payroll", enabled=True)
    disabled_economy = _create_admin_feature_scope(teacher, join_code="PAY2", block="2", feature_name="payroll", enabled=False)
    db.session.commit()

    login_teacher(client, teacher, class_id=disabled_economy.class_id, join_code="PAY2")

    response = client.get('/admin/payroll')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data


def test_admin_store_delete_rejects_disabled_class_scope(client):
    teacher = make_admin("teacher_admin_store_delete_scope")
    db.session.flush()

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

    login_teacher(client, teacher, class_id=disabled_economy.class_id, join_code="STD2")

    response = client.post(
        f'/admin/store/delete/{store_item.id}',
        data={'join_code': 'STD2'},
        follow_redirects=False,
    )
    assert response.status_code == 404
    db.session.refresh(store_item)
    assert store_item.is_active is True


def test_student_rent_rejects_disabled_feature_scope(client):
    teacher = make_admin("teacher_rent_disabled")
    db.session.flush()

    join_code = "RENT03"
    economy = create_class_scope(teacher_user=teacher, join_code=join_code, display_name='Rent Period 3')
    db.session.flush()

    student_seat_obj = make_student_identity(class_id=economy.class_id, first_name="Riley", last_name="R", claimed=True)
    db.session.flush()
    student_seat = Seat.query.filter_by(user_id=student_seat_obj.user_id, class_id=economy.class_id, role="student").first()
    user = db.session.get(User, student_seat_obj.user_id)

    for row in ClassFeature.query.filter_by(class_id=economy.class_id, feature_name='rent').all():
        db.session.delete(row)
    db.session.commit()

    _login_student(client, {
        'user_id': user.id,
        'join_code': join_code,
        'class_id': economy.class_id,
        'seat_id': student_seat.id,
        'period': 'Period3',
    })

    response = client.get('/student/rent', follow_redirects=False)
    assert response.status_code == 404
