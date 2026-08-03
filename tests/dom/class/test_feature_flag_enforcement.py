"""
Test that feature flags properly block access to disabled features.

This ensures that when a teacher disables a feature (banking, payroll, etc.),
students cannot access those routes even via direct URL.
"""

import pytest

from app.extensions import db
from app.models import ClassFeature, StoreItem
from app.feats.base import FEATContext
from tests.helpers.class_domain import disable_class_feature, enable_class_feature
from tests.helpers.classroom_initializer import initialize_as_student, initialize_as_teacher
from tests.helpers.ledger import create_ledger_idempotent_transaction

pytestmark = [pytest.mark.critical, pytest.mark.regression]


@pytest.fixture
def setup_student_with_disabled_banking(client):
    """Create a student with banking feature disabled."""
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)
    teacher = classroom.teacher_user
    user = student.user
    student_seat = student.seat
    with FEATContext("FEAT-LED-001", idempotency_key="feature_flag_enforcement:disabled_banking:seed"):
        create_ledger_idempotent_transaction(
            idempotency_key="feature_flag_enforcement:disabled_banking:seed",
            seat_id=student_seat.id,
            class_id=classroom.class_id,
            user_id=user.id,
            amount="100.00",
            account_type="checking",
            type="purchase",
            description="Starting balance",
            actor_seat_id=student_seat.id,
        )
    disable_class_feature(class_id=classroom.class_id, feature_name='banking')
    db.session.commit()

    return {
        'teacher': teacher,
        'join_code': classroom.join_code,
        'class_id': classroom.class_id,
        'seat_id': student_seat.id,
        'user_id': user.id,
        'period': 'Period2',
    }


@pytest.fixture
def setup_student_with_enabled_banking(client):
    """Create a student with banking feature enabled."""
    classroom, student = initialize_as_student("ap_csp_p3", client, client.application)
    teacher = classroom.teacher_user
    student_seat = student.seat
    user = student.user
    with FEATContext("FEAT-LED-001", idempotency_key="feature_flag_enforcement:enabled_banking:seed"):
        create_ledger_idempotent_transaction(
            idempotency_key="feature_flag_enforcement:enabled_banking:seed",
            seat_id=student_seat.id,
            class_id=classroom.class_id,
            user_id=user.id,
            amount="100.00",
            account_type="checking",
            type="purchase",
            description="Starting balance",
            actor_seat_id=student_seat.id,
        )
    enable_class_feature(class_id=classroom.class_id, feature_name='banking')
    db.session.commit()

    return {
        'teacher': teacher,
        'join_code': classroom.join_code,
        'class_id': classroom.class_id,
        'seat_id': student_seat.id,
        'user_id': user.id,
        'period': 'Period1',
    }


def test_DOM_CLASS_001__transfer_allowed_when_banking_enabled(client, setup_student_with_enabled_banking):
    """Test that transfer routes are not blocked by the feature flag when enabled."""
    data = setup_student_with_enabled_banking
    with client.session_transaction() as sess:
        sess['transfer_token'] = 'test-token-allowed'

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


def test_DOM_CLASS_001__payroll_allowed_when_payroll_enabled(client, setup_student_with_enabled_banking):
    """Test that payroll works normally when payroll is enabled."""
    _ = setup_student_with_enabled_banking

    response = client.get('/student/payroll', follow_redirects=False)
    assert response.status_code == 200
    assert b'Payroll' in response.data or b'payroll' in response.data


def test_DOM_CLASS_001__admin_banking_rejects_disabled_class_scope(client):
    classroom = initialize_as_teacher("chemistry_p1", client, client.application)
    disable_class_feature(class_id=classroom.class_id, feature_name='banking')
    db.session.commit()

    response = client.get('/admin/banking')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data


def test_DOM_CLASS_001__admin_store_rejects_disabled_class_scope(client):
    classroom_b = initialize_as_teacher("ap_csp_p3", client, client.application)
    disable_class_feature(class_id=classroom_b.class_id, feature_name='store')
    db.session.commit()

    response = client.get('/admin/store')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data


def test_DOM_CLASS_001__admin_hall_pass_rejects_disabled_class_scope(client):
    classroom_b = initialize_as_teacher("ap_csp_p3", client, client.application)
    disable_class_feature(class_id=classroom_b.class_id, feature_name='hall_pass')
    db.session.commit()

    response = client.get('/admin/hall-pass')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data


def test_DOM_CLASS_001__admin_payroll_rejects_disabled_class_scope(client):
    classroom_b = initialize_as_teacher("ap_csp_p3", client, client.application)
    disable_class_feature(class_id=classroom_b.class_id, feature_name='payroll')
    db.session.commit()

    response = client.get('/admin/payroll')
    assert response.status_code == 200
    assert b"is disabled for this class" in response.data


def test_DOM_CLASS_001__admin_store_delete_rejects_disabled_class_scope(client):
    classroom_b = initialize_as_teacher("ap_csp_p3", client, client.application)
    disable_class_feature(class_id=classroom_b.class_id, feature_name='store')
    db.session.commit()
    with FEATContext("FEAT-SETTINGS-001", idempotency_key=f"feature_flag_enforcement:store_item:{classroom_b.class_id}"):
        store_item = StoreItem(
            user_id=classroom_b.teacher_user.id,
            class_id=classroom_b.class_id,
            name="Pencil",
            description="Simple item",
            price=1,
            item_type='immediate',
            is_active=True,
        )
        db.session.add(store_item)
        db.session.flush()
    response = client.post(
        f'/admin/store/delete/{store_item.id}',
        data={'join_code': 'STD2'},
        follow_redirects=False,
    )
    assert response.status_code == 404
    db.session.refresh(store_item)
    assert store_item.is_active is True


def test_DOM_CLASS_001__student_rent_rejects_disabled_class_scope(client):
    classroom, student = initialize_as_student("chemistry_p1", client, client.application)
    disable_class_feature(class_id=classroom.class_id, feature_name='rent')
    db.session.commit()

    response = client.get('/student/rent', follow_redirects=False)
    assert response.status_code == 404
