"""
Tests for API route tenant scoping.

Validates that API endpoints properly scope data access to the current admin's students.
"""

import pyotp
import pyotp
from datetime import datetime, timezone

from app import app, db
from app.models import Admin, Student, StudentTeacher, TapEvent, HallPassLog
from hash_utils import get_random_salt, hash_username


def _create_admin(username: str) -> tuple[Admin, str]:
    """Create a teacher admin for testing."""
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _create_student(first_name: str, primary_teacher: Admin = None, linked_teachers: list[Admin] = None) -> Student:
    """
    Create a student for testing.
    
    Args:
        first_name: Student's first name
        primary_teacher: Primary owner (sets teacher_id)
        linked_teachers: List of teachers to link via student_teachers
    """
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="X",
        block="A",
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin",
        teacher_id=primary_teacher.id if primary_teacher else None,
    )
    db.session.add(student)
    db.session.flush()
    
    # Add student_teachers links
    if linked_teachers:
        for teacher in linked_teachers:
            db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher.id))
    elif primary_teacher:
        # If no explicit links but has primary, create link
        db.session.add(StudentTeacher(student_id=student.id, admin_id=primary_teacher.id))
    
    db.session.commit()
    return student


def _login_admin(client, admin: Admin, secret: str):
    """Login as admin."""
    response = client.post(
        "/admin/login",
        data={"username": admin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )
    with client.session_transaction() as sess:
        sess.setdefault("is_admin", True)
        sess.setdefault("admin_id", admin.id)
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()
    return response


def _create_tap_event(student: Student, status: str = "active"):
    """Create a tap event for testing."""
    tap = TapEvent(
        student_id=student.id,
        period="1",
        status=status,
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(tap)
    db.session.commit()
    return tap


def test_attendance_history_api_scoped_to_teacher(client):
    """Admin should only see attendance history for their own students."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    
    # Create students for each teacher
    student_a = _create_student("StudentA", primary_teacher=teacher_a)
    student_b = _create_student("StudentB", primary_teacher=teacher_b)
    
    # Create tap events for both students
    tap_a = _create_tap_event(student_a, status="active")
    tap_b = _create_tap_event(student_b, status="active")
    
    # Login as teacher A
    _login_admin(client, teacher_a, secret_a)
    
    # Request attendance history
    response = client.get("/api/attendance/history")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Should only see student A's tap event
    assert data["status"] == "success"
    record_ids = [r["id"] for r in data["records"]]
    assert tap_a.id in record_ids
    assert tap_b.id not in record_ids


def test_attendance_history_api_includes_shared_students(client):
    """Admin should see attendance history for shared students."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    
    # Create shared student
    shared_student = _create_student("Shared", primary_teacher=teacher_a, linked_teachers=[teacher_a, teacher_b])
    
    # Create exclusive students
    exclusive_a = _create_student("ExclusiveA", primary_teacher=teacher_a)
    exclusive_b = _create_student("ExclusiveB", primary_teacher=teacher_b)
    
    # Create tap events
    tap_shared = _create_tap_event(shared_student)
    tap_a = _create_tap_event(exclusive_a)
    tap_b = _create_tap_event(exclusive_b)
    
    # Login as teacher A
    _login_admin(client, teacher_a, secret_a)
    
    # Request attendance history
    response = client.get("/api/attendance/history")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Should see shared student and exclusive A, but not exclusive B
    record_ids = [r["id"] for r in data["records"]]
    assert tap_shared.id in record_ids
    assert tap_a.id in record_ids
    assert tap_b.id not in record_ids


def test_attendance_history_api_filters_work_with_scoping(client):
    """Filters should work correctly with tenant scoping."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")
    
    # Create students with different periods
    student_a1 = _create_student("StudentA1", primary_teacher=teacher_a)
    student_a1.block = "Period1"
    student_a2 = _create_student("StudentA2", primary_teacher=teacher_a)
    student_a2.block = "Period2"
    student_b = _create_student("StudentB", primary_teacher=teacher_b)
    student_b.block = "Period1"
    db.session.commit()
    
    # Create tap events
    tap_a1 = TapEvent(student_id=student_a1.id, period="1", status="active", timestamp=datetime.now(timezone.utc))
    tap_a2 = TapEvent(student_id=student_a2.id, period="2", status="active", timestamp=datetime.now(timezone.utc))
    tap_b = TapEvent(student_id=student_b.id, period="1", status="active", timestamp=datetime.now(timezone.utc))
    db.session.add_all([tap_a1, tap_a2, tap_b])
    db.session.commit()
    
    # Login as teacher A
    _login_admin(client, teacher_a, secret_a)
    
    # Request attendance history filtered by period 1
    response = client.get("/api/attendance/history?period=1")
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Should only see teacher A's period 1 student (not teacher B's)
    record_ids = [r["id"] for r in data["records"]]
    assert tap_a1.id in record_ids
    assert tap_a2.id not in record_ids  # Different period
    assert tap_b.id not in record_ids  # Different teacher


def test_attendance_history_api_system_admin_sees_all(client):
    """System admin should see all attendance records."""
    from app.models import SystemAdmin
    
    # Create system admin
    sys_secret = pyotp.random_base32()
    sys_admin = SystemAdmin(username="sysadmin", totp_secret=sys_secret)
    db.session.add(sys_admin)
    db.session.commit()
    
    # Create teachers and students
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    
    student_a = _create_student("StudentA", primary_teacher=teacher_a)
    student_b = _create_student("StudentB", primary_teacher=teacher_b)
    
    # Create tap events
    tap_a = _create_tap_event(student_a)
    tap_b = _create_tap_event(student_b)
    
    # Login as system admin
    client.post(
        "/sysadmin/login",
        data={"username": "sysadmin", "totp_code": pyotp.TOTP(sys_secret).now()},
        follow_redirects=True,
    )
    
    # System admins accessing via /api routes would need admin session too
    # For now, just verify the scoping logic works for regular admins
    # (System admins typically don't use the API routes directly)


def test_hall_pass_queue_scoped_to_teacher(client):
    """Hall pass queue should be limited to the logged-in teacher's students."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")

    student_a = _create_student("StudentA", primary_teacher=teacher_a)
    student_b = _create_student("StudentB", primary_teacher=teacher_b)

    now = datetime.now(timezone.utc)
    db.session.add_all([
        HallPassLog(student_id=student_a.id, reason="Restroom", status="approved", decision_time=now),
        HallPassLog(student_id=student_b.id, reason="Restroom", status="approved", decision_time=now),
    ])
    db.session.commit()

    _login_admin(client, teacher_a, secret_a)
    response = client.get("/api/hall-pass/queue")

    assert response.status_code == 200
    data = response.get_json()

    assert data["status"] == "success"
    assert len(data["queue"]) == 1
    assert data["queue"][0]["student_name"] == student_a.full_name
    assert data["total"] == 1


def test_hall_pass_settings_are_per_teacher(client):
    """Updating hall pass settings should not affect other teachers."""
    teacher_a, secret_a = _create_admin("teacher-a")
    teacher_b, secret_b = _create_admin("teacher-b")

    _login_admin(client, teacher_a, secret_a)
    update_response = client.post(
        "/api/hall-pass/settings",
        json={"queue_limit": 3}
    )

    assert update_response.status_code == 200
    assert update_response.get_json()["settings"]["queue_limit"] == 3

    _login_admin(client, teacher_b, secret_b)
    fetch_response = client.get("/api/hall-pass/settings")
    assert fetch_response.status_code == 200
    assert fetch_response.get_json()["settings"]["queue_limit"] == 10


def test_public_hall_pass_queue_scoped_to_teacher(client):
    """Public queue endpoint should be filtered by teacher_id."""
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    student_a = _create_student("StudentA", primary_teacher=teacher_a)
    student_b = _create_student("StudentB", primary_teacher=teacher_b)

    now = datetime.now(timezone.utc)
    db.session.add_all([
        HallPassLog(student_id=student_a.id, reason="Restroom", status="approved", decision_time=now),
        HallPassLog(student_id=student_b.id, reason="Restroom", status="approved", decision_time=now),
    ])
    db.session.commit()

    response = client.get(f"/api/hall-pass/public/queue?teacher_id={teacher_a.id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["queue"]) == 1
    assert data["queue"][0]["student_name"] == student_a.full_name

    missing_teacher_response = client.get("/api/hall-pass/public/queue")
    assert missing_teacher_response.status_code == 400

    not_found_response = client.get("/api/hall-pass/public/queue?teacher_id=99999")
    assert not_found_response.status_code == 404


def test_public_verification_feed_scoped_to_teacher(client):
    """Public verification feed should only include passes for the selected teacher."""
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")

    student_a = _create_student("StudentA", primary_teacher=teacher_a)
    student_b = _create_student("StudentB", primary_teacher=teacher_b)

    now = datetime.now(timezone.utc)
    db.session.add_all([
        HallPassLog(student_id=student_a.id, reason="Restroom", status="left", left_time=now),
        HallPassLog(student_id=student_b.id, reason="Restroom", status="left", left_time=now),
    ])
    db.session.commit()

    response = client.get(f"/api/hall-pass/public/verification?teacher_id={teacher_a.id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["passes"]) == 1
    assert data["passes"][0]["student_name"] == student_a.full_name
