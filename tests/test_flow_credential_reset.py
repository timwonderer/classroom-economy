"""
End-to-end test for the account recovery flow:
  1. Admin generates reset code for student
  2. Student uses join_code + reset_code to begin recovery
  3. Student proceeds directly to username + credential setup
  4. Existing teacher-managed identity is preserved
  5. Economic data is preserved
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import pytest
from werkzeug.security import generate_password_hash
from app import db
from app.models import User, UserRole, Admin, StudentBlock, Transaction, Seat, IdentityProfile
from app.hash_utils import hash_username, hash_username_lookup, get_random_salt
from app.utils.name_utils import hash_last_name_parts
from app.utils.claim_credentials import compute_primary_claim_hash
from datetime import datetime, timezone
from tests.helpers.class_scope import make_student_identity


@pytest.fixture
def test_data(app):
    """Setup: Admin, Class, Student with completed setup and a balance."""
    with app.app_context():
        admin = make_admin('admin_flow2', 'dummy_secret')
        db.session.add(admin)
        db.session.commit()

        salt = get_random_salt()
        dob_sum = 20100101

        last_name_hashes = hash_last_name_parts('TeacherLast', salt)
        first_half = compute_primary_claim_hash('F', dob_sum, salt)

        u_hash = hash_username('olduser', salt)
        ul_hash = hash_username_lookup('olduser')
        p_hash = generate_password_hash('1234')
        pp_hash = generate_password_hash('old-passphrase-word')

        student = make_student_identity(first_name='Flow', last_name='T', block='A', join_code='FLOW2A', class_id=class_row.class_id)
        student.pin_hash = p_hash
        student.passphrase_hash = pp_hash
        student.has_completed_setup = True
        student.recovery_status = 'active'
        db.session.add(student)
        db.session.commit()

        seat = student

        db.session.add(StudentBlock(
            user_id=student.user_id, period='A', join_code='FLOW2A',
        ))

        tx = Transaction(
            user_id=student.user_id,amount=100.0,
            type='deposit',
            description='Initial Balance',
            account_type='checking',
            join_code='FLOW2A',
        )
        db.session.add(tx)
        db.session.commit()

        return {
            'admin_id': admin.id,
            'student_id': student.id,
            'join_code': 'FLOW2A',
            'seat_id': seat.id,
        }


def test_credential_reset_flow(client, test_data):
    """
    Full recovery flow:
      1. Admin generates reset code (via edit modal toggle).
      2. Verify student detail shows reset code.
      3. Student enters join_code + reset_code.
      4. Student proceeds directly to credential setup.
      5. Verify identity is preserved while credentials are reset.
    """
    admin_id = test_data['admin_id']
    student_id = test_data['student_id']
    join_code = test_data['join_code']

    # ── Step 1: Admin generates reset code ──
    with client.session_transaction() as sess:
        sess['admin_id'] = admin_id
        sess['is_admin'] = True

    resp = client.post(
        f'/recovery/admin/generate-code/{student_id}',
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Reset code generated" in resp.data

    # Retrieve the generated code from DB
    with client.application.app_context():
        s = db.session.merge(test_data["student"])
        reset_code = s.reset_code
        assert reset_code is not None
        assert len(reset_code) == 8
        assert s.recovery_status == 'to_be_claimed'

    # ── Step 2: Verify redirected student detail page shows recovery info ──
    assert b"Account Recovery In Progress" in resp.data
    assert reset_code.encode() in resp.data
    assert b"FLOW2A" in resp.data

    # ── Step 3: Student enters join_code + reset_code ──
    # (Clear admin session first)
    client.get('/logout')

    resp = client.post('/recovery/lookup', data={
        'join_code': join_code,
        'reset_code': reset_code,
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert '/student/create-username' in resp.location

    # Verify state after lookup and before credentials are re-established.
    with client.application.app_context():
        s = db.session.merge(test_data["student"])
        assert s.has_completed_setup is False
        assert s.username_hash is None
        assert s.pin_hash is None
        assert s.passphrase_hash is None
        assert s.reset_code is not None
        assert s.recovery_status == 'to_be_claimed'

    # Complete credential setup so recovery is consumed.
    resp = client.post('/student/create-username', data={
        'write_in_word': 'rocket',
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert '/student/setup-pin-passphrase' in resp.location

    resp = client.post('/student/setup-pin-passphrase', data={
        'pin': '1234',
        'confirm_pin': '1234',
        'passphrase': 'new-passphrase-flow',
        'confirm_passphrase': 'new-passphrase-flow',
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert '/setup-complete' in resp.location

    # ── Step 5: Verify state after full recovery completion ──
    with client.application.app_context():
        s = db.session.merge(test_data["student"])

        # student_id unchanged
        assert s.id == student_id

        # Teacher-managed identity preserved
        assert s.display_first_name == 'Flow'
        assert s.display_last_initial == 'T'

        # Credentials re-established
        assert s.has_completed_setup is True
        assert s.username_hash is not None
        assert s.pin_hash is not None
        assert s.passphrase_hash is not None

        # Recovery state cleared
        assert s.reset_code is None
        assert s.recovery_status == 'active'

        # Economic data preserved
        tx_count = Transaction.query.filter_by(
            student_id=student_id, join_code=join_code,
        ).count()
        assert tx_count == 1

        checking = sum(
            t.amount for t in Transaction.query.filter_by(
                student_id=student_id,
                join_code=join_code,
                account_type='checking',
            ).all()
            if not t.is_void
        )
        assert checking == 100.0
