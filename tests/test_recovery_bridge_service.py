from __future__ import annotations

from datetime import timedelta

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.hash_utils import get_random_salt, hash_hmac, hash_username_lookup
from app.models import RecoveryRequest, User, UserRole, Student, StudentRecoveryCode, StudentTeacher
from app.services.recovery_bridge_service import (
    create_recovery_request_with_students,
    delete_recovery_codes_for_student,
    delete_recovery_rows_for_teacher,
    dismiss_recovery_code,
    find_recovery_request_by_resume_pin,
    get_active_recovery_request_for_teacher,
    get_pending_recovery_code_for_student,
    get_recovery_request_by_id,
    get_recovery_code_for_student,
    invalidate_recovery_codes,
    list_recovery_codes_for_request,
    mark_recovery_request_verified,
    save_recovery_progress,
    set_recovery_code_verified,
)
from app.utils.time import utc_now
from tests.helpers.v2_fixtures import make_admin


def _seed_teacher_student():
    teacher = make_admin("recovery-bridge", "test-secret")
    db.session.add(teacher)
    db.session.flush()

    student_salt = get_random_salt()
    student = Student(
        first_name="Recover",
        last_initial="S",
        block="A",
        salt=student_salt,
        username_lookup_hash=hash_username_lookup("recover-student"),
        passphrase_hash=generate_password_hash("secret"),
    )
    db.session.add(student)
    db.session.flush()
    db.session.add(StudentTeacher(user_id=student_user.id, teacher_id=teacher.id))
    db.session.flush()
    return teacher, student


def test_pending_recovery_code_for_student_filters_active_pending_request(client):
    teacher, student = _seed_teacher_student()
    request_row = RecoveryRequest(
        user_id=teacher.id,
        status="pending",
        expires_at=utc_now() + timedelta(days=1),
    )
    db.session.add(request_row)
    db.session.flush()
    code_row = StudentRecoveryCode(
        recovery_request_id=request_row.id,
        user_id=student_user.id,
        dismissed=False,
    )
    db.session.add(code_row)
    db.session.commit()

    pending = get_pending_recovery_code_for_student(student.id, utc_now())
    assert pending is not None
    assert pending.id == code_row.id
    assert pending.student_id == student.id
    assert pending.recovery_request.expires_at == request_row.expires_at


def test_get_recovery_code_for_student_respects_student_scope(client):
    teacher, student = _seed_teacher_student()
    request_row = RecoveryRequest(
        user_id=teacher.id,
        status="pending",
        expires_at=utc_now() + timedelta(days=1),
    )
    db.session.add(request_row)
    db.session.flush()
    code_row = StudentRecoveryCode(
        recovery_request_id=request_row.id,
        user_id=student_user.id,
        dismissed=False,
    )
    db.session.add(code_row)
    db.session.commit()

    found = get_recovery_code_for_student(code_row.id, student.id)
    not_found = get_recovery_code_for_student(code_row.id, student.id + 999)
    assert found is not None
    assert found.id == code_row.id
    assert not_found is None


def test_recovery_code_verify_and_dismiss_updates_rows(client):
    teacher, student = _seed_teacher_student()
    request_row = RecoveryRequest(
        user_id=teacher.id,
        status="pending",
        expires_at=utc_now() + timedelta(days=1),
    )
    db.session.add(request_row)
    db.session.flush()
    code_row = StudentRecoveryCode(
        recovery_request_id=request_row.id,
        user_id=student_user.id,
        dismissed=False,
    )
    db.session.add(code_row)
    db.session.commit()

    verified_at = utc_now()
    set_recovery_code_verified(code_row.id, hash_hmac(b"123456", b""), verified_at)
    dismiss_recovery_code(code_row.id)
    db.session.commit()

    refreshed = db.session.get(StudentRecoveryCode, code_row.id)
    assert refreshed is not None
    assert refreshed.code_hash is not None
    assert refreshed.verified_at == verified_at
    assert refreshed.dismissed is True


def test_admin_lifecycle_create_list_and_complete_request(client):
    teacher, student = _seed_teacher_student()
    expires_at = utc_now() + timedelta(days=5)

    created = create_recovery_request_with_students(
        teacher_id=teacher.id,
        student_ids=[student.id],
        expires_at=expires_at,
    )
    assert created.teacher_id == teacher.id
    assert created.status == "pending"

    active = get_active_recovery_request_for_teacher(teacher.id, utc_now())
    assert active is not None
    assert active.id == created.id

    by_id = get_recovery_request_by_id(created.id)
    assert by_id is not None
    assert by_id.id == created.id

    codes = list_recovery_codes_for_request(created.id)
    assert len(codes) == 1
    assert codes[0].student_id == student.id
    assert codes[0].notified_at is not None

    mark_recovery_request_verified(created.id, utc_now())
    db.session.commit()

    completed = get_recovery_request_by_id(created.id)
    assert completed is not None
    assert completed.status == "verified"
    assert completed.completed_at is not None


def test_resume_progress_and_invalidate_and_delete_helpers(client):
    teacher, student = _seed_teacher_student()
    expires_at = utc_now() + timedelta(days=5)
    created = create_recovery_request_with_students(
        teacher_id=teacher.id,
        student_ids=[student.id],
        expires_at=expires_at,
    )
    db.session.flush()

    save_recovery_progress(
        created.id,
        partial_codes=["111111", "222222"],
        resume_pin_hash="resume-hash",
        resume_new_username="new-teacher-name",
    )
    db.session.flush()

    resumed = find_recovery_request_by_resume_pin("resume-hash", utc_now())
    assert resumed is not None
    assert resumed.id == created.id
    assert resumed.partial_codes == ["111111", "222222"]
    assert resumed.resume_new_username == "new-teacher-name"

    code_rows = list_recovery_codes_for_request(created.id)
    assert code_rows
    set_recovery_code_verified(code_rows[0].id, hash_hmac(b"333333", b""), utc_now())
    invalidated = invalidate_recovery_codes(created.id)
    assert invalidated == 1

    db.session.flush()
    refreshed_code = db.session.get(StudentRecoveryCode, code_rows[0].id)
    assert refreshed_code is not None
    assert refreshed_code.code_hash is None
    assert refreshed_code.verified_at is None

    delete_recovery_codes_for_student(student.id)
    db.session.flush()
    db.session.expire_all()
    assert db.session.get(StudentRecoveryCode, code_rows[0].id) is None

    delete_recovery_rows_for_teacher(teacher.id)
    db.session.commit()
    assert get_recovery_request_by_id(created.id) is None
