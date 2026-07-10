from datetime import datetime, timezone
from decimal import Decimal

from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Seat, IdentityProfile, User, UserRole, ClassEconomy, RedemptionAuditLog, StoreItem, StudentItem, Transaction
from tests.helpers.canonical_session import set_canonical_context


@pytest.fixture
def teacher_admin(client):
    admin = make_admin("audit_teacher")
    db.session.commit()
    return admin


@pytest.fixture
def student_in_class(client, teacher_admin):
    profile = IdentityProfile(profile_type='student', first_name='Audit', last_name='Stone')
    db.session.add(profile)
    student_user = User(
        user_role=UserRole.STUDENT,
        username_hash="audit_student_hash",
        username_lookup_hash="audit_student_lookup",
    )
    db.session.add(student_user)
    db.session.flush()

    class_economy = ClassEconomy(
        join_code='AUDIT123',
        user_id=teacher_admin.id,
        display_name='A',
        status='active',
    )
    db.session.add(class_economy)
    db.session.flush()
    seat = Seat(
        user_id=student_user.id,
        class_id=class_economy.class_id,
        join_code='AUDIT123',
        block='A',
        block_identifier='A',
        role="student",
        claimed_at=datetime.now(timezone.utc),
    )
    db.session.add(seat)
    db.session.flush()
    profile.seat_id = seat.id
    db.session.add(IdentityProfile(seat_id=seat.id, profile_type='student_claimed', first_name='Audit', last_name='Stone'))
    db.session.commit()
    return seat


def _login_student(client, student_id):
    class_row = ClassEconomy.query.filter_by(join_code='AUDIT123').first()
    seat = Seat.query.filter_by(user_id=student_id, join_code='AUDIT123').first()
    with client.session_transaction() as sess:
        if seat is not None and class_row is not None:
            set_canonical_context(
                sess,
                user_id=student_id,
                class_id=class_row.class_id,
                seat_id=seat.id,
                role="student",
                join_code='AUDIT123',
            )


def _login_admin(client, admin_id):
    with client.session_transaction() as sess:
        sess['admin_id'] = admin_id
        sess['is_admin'] = True
        class_row = ClassEconomy.query.filter_by(join_code='AUDIT123').first()
        if class_row is not None:
            sess['current_class_id'] = class_row.class_id
            sess['current_join_code'] = class_row.join_code


def _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Audit Item', price=Decimal('10.00')):
    class_row = ClassEconomy.query.filter_by(join_code='AUDIT123').first()
    assert class_row is not None
    item = StoreItem(
        user_id=teacher_admin.id,
        class_id=class_row.class_id,
        join_code='AUDIT123',
        name=item_name,
        price=price,
        item_type='delayed',
        is_active=True,
    )
    db.session.add(item)
    db.session.flush()
    db.session.add(Transaction(
        user_id=student.user_id,
        join_code='AUDIT123',
        amount=Decimal('100.00'),
        account_type='checking',
        type='deposit',
        description='Initial funds',
    ))
    db.session.commit()

    _login_student(client, student.user_id)
    purchase_resp = client.post('/api/purchase-item', json={
        'item_id': item.id,
        'passphrase': 'password',
        'quantity': 1,
    })
    assert purchase_resp.status_code == 200
    assert purchase_resp.json['status'] == 'success'

    student_item = StudentItem.query.filter_by(user_id=student_user.id, store_item_id=item.id).first()
    assert student_item is not None
    return item, student_item


def test_request_approve_reject_write_audit_rows(client, teacher_admin, student_in_class):
    student = student_in_class

    # Request + approve flow
    _, student_item = _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Approval Item')
    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'approve note',
    })
    assert use_resp.status_code == 200
    assert use_resp.json['status'] == 'success'

    request_rows = RedemptionAuditLog.query.filter_by(student_item_id=student_item.id, action='request').all()
    assert len(request_rows) == 1
    assert request_rows[0].notes == 'approve note'
    assert request_rows[0].source.value == 'live'

    _login_admin(client, teacher_admin.id)
    approve_resp = client.post('/api/approve-redemption', json={'student_item_id': student_item.id})
    assert approve_resp.status_code == 200
    assert approve_resp.json['status'] == 'success'

    approved_rows = RedemptionAuditLog.query.filter_by(student_item_id=student_item.id, action='approved').all()
    assert len(approved_rows) == 1

    # Separate reject flow
    _login_student(client, student.id)
    _, reject_item = _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Reject Item')
    reject_use_resp = client.post('/api/use-item', json={
        'student_item_id': reject_item.id,
        'passphrase': 'password',
        'details': 'reject me',
    })
    assert reject_use_resp.status_code == 200

    _login_admin(client, teacher_admin.id)
    reject_resp = client.post('/api/reject-redemption', json={'student_item_id': reject_item.id})
    assert reject_resp.status_code == 200
    assert reject_resp.json['status'] == 'success'

    rejected_rows = RedemptionAuditLog.query.filter_by(action='rejected').all()
    assert len(rejected_rows) == 1
    assert rejected_rows[0].notes is not None
    assert 'reject me' in rejected_rows[0].notes


def test_audit_helper_called_once_per_action(client, teacher_admin, student_in_class, monkeypatch):
    student = student_in_class
    _, student_item = _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Count Item')

    import app.routes.api as api_module
    original_helper = api_module._append_redemption_audit_log
    calls = {'count': 0}

    def wrapped_helper(**kwargs):
        calls['count'] += 1
        return original_helper(**kwargs)

    monkeypatch.setattr(api_module, '_append_redemption_audit_log', wrapped_helper)

    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'single request call',
    })
    assert use_resp.status_code == 200
    assert calls['count'] == 1


def test_no_mutation_if_audit_insert_fails_request_flow(client, teacher_admin, student_in_class, monkeypatch):
    student = student_in_class
    _, student_item = _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Fail Request')
    student_item_id = student_item.id
    original_status = student_item.status

    import app.routes.api as api_module

    def fail_helper(**kwargs):
        raise SQLAlchemyError("forced failure")

    monkeypatch.setattr(api_module, '_append_redemption_audit_log', fail_helper)

    resp = client.post('/api/use-item', json={
        'student_item_id': student_item_id,
        'passphrase': 'password',
        'details': 'should fail before mutation',
    })
    assert resp.status_code == 500

    assert RedemptionAuditLog.query.count() == 0
    reloaded = db.session.get(StudentItem, student_item_id)
    if reloaded is not None:
        assert reloaded.status == original_status


def test_no_mutation_if_audit_insert_fails_approve_reject(client, teacher_admin, student_in_class, monkeypatch):
    student = student_in_class
    _, student_item = _fund_and_purchase_delayed_item(client, teacher_admin, student, item_name='Fail Finalize')

    use_resp = client.post('/api/use-item', json={
        'student_item_id': student_item.id,
        'passphrase': 'password',
        'details': 'finalize',
    })
    assert use_resp.status_code == 200

    # Clear successful request audit row to isolate this test's assertion.
    RedemptionAuditLog.query.delete()
    db.session.commit()

    import app.routes.api as api_module

    def fail_helper(**kwargs):
        raise SQLAlchemyError("forced failure")

    monkeypatch.setattr(api_module, '_append_redemption_audit_log', fail_helper)
    _login_admin(client, teacher_admin.id)

    approve_resp = client.post('/api/approve-redemption', json={'student_item_id': student_item.id})
    assert approve_resp.status_code == 500
    db.session.refresh(student_item)
    assert student_item.status == 'processing'
    assert RedemptionAuditLog.query.count() == 0

    reject_resp = client.post('/api/reject-redemption', json={'student_item_id': student_item.id})
    assert reject_resp.status_code == 500
    db.session.refresh(student_item)
    assert student_item.status == 'processing'
    assert Transaction.query.filter_by(user_id=student_user.id, type='refund').count() == 0
    assert RedemptionAuditLog.query.count() == 0


def test_legacy_adapter_shows_inferred_without_persisting(client, teacher_admin, student_in_class):
    student = student_in_class

    class_row = ClassEconomy.query.filter_by(join_code='AUDIT123').first()
    assert class_row is not None
    item = StoreItem(
        user_id=teacher_admin.id,
        class_id=class_row.class_id,
        join_code='AUDIT123',
        name='Legacy-Like Item',
        price=Decimal('5.00'),
        item_type='delayed',
        is_active=True,
    )
    db.session.add(item)
    db.session.flush()
    db.session.add(StudentItem(correlation_id='corr_test', 
        user_id=student_user.id,
        store_item_id=item.id,
        join_code='AUDIT123',
        status='completed',
        redemption_details='legacy note',
    ))
    db.session.commit()

    _login_admin(client, teacher_admin.id)
    before_count = RedemptionAuditLog.query.count()
    resp = client.get('/admin/store')
    assert resp.status_code == 200
    assert b'Legacy' in resp.data
    assert RedemptionAuditLog.query.count() == before_count
