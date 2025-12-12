"""
Comprehensive tests for student-verified teacher account recovery system.

Tests the complete recovery flow:
1. Teacher initiates recovery with student usernames + DOB sum
2. Students receive notification and verify with passphrase
3. Students generate unique recovery codes
4. Teacher collects codes and resets credentials
5. Security edge cases and error handling
"""

import pyotp
import bcrypt
from datetime import datetime, timezone, timedelta

from app import db
from app.models import Admin, Student, RecoveryRequest, StudentRecoveryCode, TeacherBlock
from hash_utils import hash_hmac


def test_teacher_recovery_full_flow(client, app):
    """Test complete end-to-end recovery flow."""
    # Setup: Create teacher with DOB sum
    secret = pyotp.random_base32()
    teacher = Admin(username="teacher1", totp_secret=secret, dob_sum=2028)  # 03+15+2010
    db.session.add(teacher)
    db.session.flush()

    # Create 3 students for the teacher
    students = []
    for i in range(3):
        passphrase = f"secret{i}"
        passphrase_hash = bcrypt.hashpw(passphrase.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        student = Student(
            username=f"student{i}",
            username_hash=hash_hmac(f"student{i}".encode(), b''),
            first_name=f"Test{i}",
            last_initial="S",
            passphrase_hash=passphrase_hash,
            teacher_id=teacher.id,
            has_completed_setup=True
        )
        db.session.add(student)
        students.append(student)

    db.session.commit()

    # Step 1: Teacher initiates recovery
    response = client.post('/admin/recover', data={
        'student_usernames': 'student0, student1, student2',
        'dob_sum': '2028'
    }, follow_redirects=False)

    assert response.status_code == 302
    assert '/admin/recovery-status' in response.location

    # Verify recovery request was created
    recovery_request = RecoveryRequest.query.filter_by(admin_id=teacher.id).first()
    assert recovery_request is not None
    assert recovery_request.status == 'pending'
    assert recovery_request.dob_sum == 2028

    # Verify student recovery codes were created
    student_codes = StudentRecoveryCode.query.filter_by(recovery_request_id=recovery_request.id).all()
    assert len(student_codes) == 3

    # Step 2: Check recovery status (should show 0/3 verified)
    with client.session_transaction() as sess:
        sess['recovery_request_id'] = recovery_request.id

    response = client.get('/admin/recovery-status')
    assert response.status_code == 200
    assert b'0 / 3 Verified' in response.data or b'Waiting for Student Verification' in response.data

    # Step 3: Students verify with passphrase
    generated_codes = []
    for i, student in enumerate(students):
        student_code = StudentRecoveryCode.query.filter_by(
            recovery_request_id=recovery_request.id,
            student_id=student.id
        ).first()

        # Login as student
        with client.session_transaction() as sess:
            sess['student_id'] = student.id
            sess['login_time'] = datetime.now(timezone.utc).isoformat()

        # Student verifies with passphrase
        response = client.post(f'/student/verify-recovery/{student_code.id}', data={
            'passphrase': f'secret{i}'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Verification Successful' in response.data or b'Recovery Code' in response.data

        # Extract generated code from database (we can't get it from response easily)
        db.session.refresh(student_code)
        assert student_code.code_hash is not None
        assert student_code.verified_at is not None

        # For testing, we need to know the codes. In real scenario, students give these to teacher
        # We'll simulate this by generating test codes and storing their hashes
        test_code = f"{100000 + i}"  # 100000, 100001, 100002
        student_code.code_hash = hash_hmac(test_code.encode(), b'')
        db.session.commit()
        generated_codes.append(test_code)

    # Step 4: Check recovery status (should show 3/3 verified)
    with client.session_transaction() as sess:
        sess.clear()  # Clear student session
        sess['recovery_request_id'] = recovery_request.id

    response = client.get('/admin/recovery-status')
    assert response.status_code == 200
    assert b'3 / 3 Verified' in response.data or b'All Students Verified' in response.data

    # Step 5: Teacher resets credentials with codes
    recovery_codes_str = ', '.join(generated_codes)
    response = client.post('/admin/reset-credentials', data={
        'recovery_codes': recovery_codes_str,
        'new_username': 'newteacher1'
    }, follow_redirects=False)

    # Should show QR code for TOTP setup
    assert response.status_code == 200
    assert b'totp_secret' in response.data or b'QR' in response.data.lower()

    # Step 6: Confirm TOTP and complete reset
    with client.session_transaction() as sess:
        new_totp_secret = sess.get('reset_totp_secret')
        assert new_totp_secret is not None

    new_totp_code = pyotp.TOTP(new_totp_secret).now()
    response = client.post('/admin/confirm-reset', data={
        'totp_code': new_totp_code
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'successfully' in response.data.lower() or b'login' in response.data.lower()

    # Verify teacher account was updated
    db.session.refresh(teacher)
    assert teacher.username == 'newteacher1'
    assert teacher.totp_secret == new_totp_secret

    # Verify recovery request was marked as completed
    db.session.refresh(recovery_request)
    assert recovery_request.status == 'verified'
    assert recovery_request.completed_at is not None


def test_recovery_with_wrong_dob_sum(client, app):
    """Test that recovery fails with incorrect DOB sum."""
    secret = pyotp.random_base32()
    teacher = Admin(username="teacher2", totp_secret=secret, dob_sum=2028)
    db.session.add(teacher)
    db.session.flush()

    student = Student(
        username="student_test",
        username_hash=hash_hmac(b"student_test", b''),
        first_name="Test",
        last_initial="S",
        teacher_id=teacher.id,
        has_completed_setup=True
    )
    db.session.add(student)
    db.session.commit()

    # Try recovery with wrong DOB sum
    response = client.post('/admin/recover', data={
        'student_usernames': 'student_test',
        'dob_sum': '9999'  # Wrong!
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Unable to verify your identity' in response.data or b'check your DOB sum' in response.data.lower()

    # Verify no recovery request was created
    recovery_request = RecoveryRequest.query.filter_by(admin_id=teacher.id).first()
    assert recovery_request is None


def test_student_verification_with_wrong_passphrase(client, app):
    """Test that student verification fails with wrong passphrase."""
    secret = pyotp.random_base32()
    teacher = Admin(username="teacher3", totp_secret=secret, dob_sum=2028)
    db.session.add(teacher)
    db.session.flush()

    passphrase = "correctpass"
    passphrase_hash = bcrypt.hashpw(passphrase.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    student = Student(
        username="student3",
        username_hash=hash_hmac(b"student3", b''),
        first_name="Test",
        last_initial="S",
        passphrase_hash=passphrase_hash,
        teacher_id=teacher.id,
        has_completed_setup=True
    )
    db.session.add(student)
    db.session.commit()

    # Create recovery request
    recovery_request = RecoveryRequest(
        admin_id=teacher.id,
        dob_sum=2028,
        status='pending',
        expires_at=datetime.now(timezone.utc) + timedelta(days=5)
    )
    db.session.add(recovery_request)
    db.session.flush()

    student_code = StudentRecoveryCode(
        recovery_request_id=recovery_request.id,
        student_id=student.id
    )
    db.session.add(student_code)
    db.session.commit()

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Try to verify with wrong passphrase
    response = client.post(f'/student/verify-recovery/{student_code.id}', data={
        'passphrase': 'wrongpass'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Incorrect passphrase' in response.data

    # Verify code was not generated
    db.session.refresh(student_code)
    assert student_code.code_hash is None
    assert student_code.verified_at is None


def test_recovery_codes_must_match_exactly(client, app):
    """Test that teacher must provide exact codes (no partial matches)."""
    secret = pyotp.random_base32()
    teacher = Admin(username="teacher4", totp_secret=secret, dob_sum=2028)
    db.session.add(teacher)
    db.session.flush()

    # Create recovery request with 2 students
    recovery_request = RecoveryRequest(
        admin_id=teacher.id,
        dob_sum=2028,
        status='pending',
        expires_at=datetime.now(timezone.utc) + timedelta(days=5)
    )
    db.session.add(recovery_request)
    db.session.flush()

    # Create verified student codes
    code1 = "123456"
    code2 = "789012"

    for i, code in enumerate([code1, code2]):
        student = Student(
            username=f"student_code{i}",
            username_hash=hash_hmac(f"student_code{i}".encode(), b''),
            first_name=f"Test{i}",
            last_initial="S",
            teacher_id=teacher.id,
            has_completed_setup=True
        )
        db.session.add(student)
        db.session.flush()

        student_code = StudentRecoveryCode(
            recovery_request_id=recovery_request.id,
            student_id=student.id,
            code_hash=hash_hmac(code.encode(), b''),
            verified_at=datetime.now(timezone.utc)
        )
        db.session.add(student_code)

    db.session.commit()

    with client.session_transaction() as sess:
        sess['recovery_request_id'] = recovery_request.id

    # Try with only one code (should fail)
    response = client.post('/admin/reset-credentials', data={
        'recovery_codes': '123456',  # Missing code2!
        'new_username': 'newteacher4'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'do not match' in response.data.lower() or b'check the codes' in response.data.lower()

    # Try with wrong code (should fail)
    response = client.post('/admin/reset-credentials', data={
        'recovery_codes': '123456, 999999',  # Wrong second code!
        'new_username': 'newteacher4'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'do not match' in response.data.lower() or b'check the codes' in response.data.lower()

    # Try with correct codes (should succeed)
    response = client.post('/admin/reset-credentials', data={
        'recovery_codes': '123456, 789012',
        'new_username': 'newteacher4'
    }, follow_redirects=False)

    assert response.status_code == 200
    # Should show TOTP setup page


def test_recovery_request_expiration(client, app):
    """Test that expired recovery requests are rejected."""
    secret = pyotp.random_base32()
    teacher = Admin(username="teacher5", totp_secret=secret, dob_sum=2028)
    db.session.add(teacher)
    db.session.flush()

    # Create expired recovery request
    recovery_request = RecoveryRequest(
        admin_id=teacher.id,
        dob_sum=2028,
        status='pending',
        expires_at=datetime.now(timezone.utc) - timedelta(days=1)  # Expired!
    )
    db.session.add(recovery_request)
    db.session.flush()

    student = Student(
        username="student5",
        username_hash=hash_hmac(b"student5", b''),
        first_name="Test",
        last_initial="S",
        teacher_id=teacher.id,
        has_completed_setup=True
    )
    db.session.add(student)
    db.session.flush()

    student_code = StudentRecoveryCode(
        recovery_request_id=recovery_request.id,
        student_id=student.id
    )
    db.session.add(student_code)
    db.session.commit()

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Try to verify expired request
    response = client.post(f'/student/verify-recovery/{student_code.id}', data={
        'passphrase': 'test'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'expired' in response.data.lower()


def test_student_notification_banner_appears(client, app):
    """Test that students see recovery notification banner in dashboard."""
    secret = pyotp.random_base32()
    teacher = Admin(username="teacher6", totp_secret=secret, dob_sum=2028)
    db.session.add(teacher)
    db.session.flush()

    passphrase = "testpass"
    passphrase_hash = bcrypt.hashpw(passphrase.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    student = Student(
        username="student6",
        username_hash=hash_hmac(b"student6", b''),
        first_name="Test",
        last_initial="S",
        passphrase_hash=passphrase_hash,
        teacher_id=teacher.id,
        join_code="TEST123",
        has_completed_setup=True
    )
    db.session.add(student)
    db.session.flush()

    # Create recovery request
    recovery_request = RecoveryRequest(
        admin_id=teacher.id,
        dob_sum=2028,
        status='pending',
        expires_at=datetime.now(timezone.utc) + timedelta(days=5)
    )
    db.session.add(recovery_request)
    db.session.flush()

    student_code = StudentRecoveryCode(
        recovery_request_id=recovery_request.id,
        student_id=student.id
    )
    db.session.add(student_code)
    db.session.commit()

    # Login as student and visit dashboard
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()
        sess['current_join_code'] = "TEST123"

    response = client.get('/student/dashboard')
    assert response.status_code == 200
    assert b'Account Recovery Request' in response.data or b'teacher is trying to recover' in response.data.lower()


def test_dismiss_recovery_notification(client, app):
    """Test that students can dismiss recovery notifications."""
    secret = pyotp.random_base32()
    teacher = Admin(username="teacher7", totp_secret=secret, dob_sum=2028)
    db.session.add(teacher)
    db.session.flush()

    student = Student(
        username="student7",
        username_hash=hash_hmac(b"student7", b''),
        first_name="Test",
        last_initial="S",
        teacher_id=teacher.id,
        has_completed_setup=True
    )
    db.session.add(student)
    db.session.flush()

    recovery_request = RecoveryRequest(
        admin_id=teacher.id,
        dob_sum=2028,
        status='pending',
        expires_at=datetime.now(timezone.utc) + timedelta(days=5)
    )
    db.session.add(recovery_request)
    db.session.flush()

    student_code = StudentRecoveryCode(
        recovery_request_id=recovery_request.id,
        student_id=student.id,
        dismissed=False
    )
    db.session.add(student_code)
    db.session.commit()

    # Login as student
    with client.session_transaction() as sess:
        sess['student_id'] = student.id
        sess['login_time'] = datetime.now(timezone.utc).isoformat()

    # Dismiss notification
    response = client.post(f'/student/dismiss-recovery/{student_code.id}', follow_redirects=True)
    assert response.status_code == 200

    # Verify dismissed flag was set
    db.session.refresh(student_code)
    assert student_code.dismissed is True


def test_recovery_without_dob_sum_configured(client, app):
    """Test that recovery fails if teacher doesn't have DOB sum configured."""
    secret = pyotp.random_base32()
    teacher = Admin(username="teacher8", totp_secret=secret, dob_sum=None)  # No DOB sum!
    db.session.add(teacher)
    db.session.flush()

    student = Student(
        username="student8",
        username_hash=hash_hmac(b"student8", b''),
        first_name="Test",
        last_initial="S",
        teacher_id=teacher.id,
        has_completed_setup=True
    )
    db.session.add(student)
    db.session.commit()

    # Try recovery
    response = client.post('/admin/recover', data={
        'student_usernames': 'student8',
        'dob_sum': '2028'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'not configured for recovery' in response.data.lower() or b'unable to verify' in response.data.lower()
