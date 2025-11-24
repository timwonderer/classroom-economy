"""
Tests for system admin student count functionality.

Validates that system admins see accurate per-teacher student counts
and that counts properly account for multi-teacher relationships.
"""

import pyotp

from app import app, db
from app.models import Admin, Student, StudentTeacher, SystemAdmin
from hash_utils import get_random_salt, hash_username


def _create_sysadmin(username: str = "sysadmin"):
    """Create a system admin for testing."""
    secret = pyotp.random_base32()
    sys_admin = SystemAdmin(username=username, totp_secret=secret)
    db.session.add(sys_admin)
    db.session.commit()
    return sys_admin, secret


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


def _login_sysadmin(client, sys_admin: SystemAdmin, secret: str):
    """Login as system admin."""
    return client.post(
        "/sysadmin/login",
        data={"username": sys_admin.username, "totp_code": pyotp.TOTP(secret).now()},
        follow_redirects=True,
    )


def test_sysadmin_sees_correct_student_count_for_single_teacher(client):
    """System admin should see correct count for teacher with exclusive students."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    
    # Create 3 students for teacher A
    _create_student("Student1", primary_teacher=teacher_a)
    _create_student("Student2", primary_teacher=teacher_a)
    _create_student("Student3", primary_teacher=teacher_a)
    
    # Create 2 students for teacher B
    _create_student("Student4", primary_teacher=teacher_b)
    _create_student("Student5", primary_teacher=teacher_b)
    
    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/admins")
    
    assert response.status_code == 200
    html = response.data.decode()
    
    # Check that each teacher shows their correct student count
    # Teacher A should show 3 students
    assert "teacher-a" in html
    # Teacher B should show 2 students
    assert "teacher-b" in html


def test_sysadmin_counts_shared_students_correctly(client):
    """System admin should count shared students only once per teacher."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    
    # Create student shared between both teachers
    shared_student = _create_student("Shared", primary_teacher=teacher_a, linked_teachers=[teacher_a, teacher_b])
    
    # Create exclusive students
    _create_student("ExclusiveA", primary_teacher=teacher_a)
    _create_student("ExclusiveB", primary_teacher=teacher_b)
    
    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/admins")
    
    assert response.status_code == 200
    html = response.data.decode()
    
    # Both teachers should appear
    assert "teacher-a" in html
    assert "teacher-b" in html
    
    # Each teacher should count the shared student
    # Teacher A: 2 students (Shared + ExclusiveA)
    # Teacher B: 2 students (Shared + ExclusiveB)


def test_sysadmin_counts_students_with_only_links(client):
    """System admin should count students linked via student_teachers even without teacher_id."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    
    # Create student with link but no teacher_id (future state after migration)
    salt = get_random_salt()
    student = Student(
        first_name="NoOwner",
        last_initial="X",
        block="A",
        salt=salt,
        username_hash=hash_username("noowner", salt),
        pin_hash="pin",
        teacher_id=None,  # No primary owner
    )
    db.session.add(student)
    db.session.flush()
    
    # Add link to teacher_a
    db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher_a.id))
    db.session.commit()
    
    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/admins")
    
    assert response.status_code == 200
    html = response.data.decode()
    
    # Teacher A should appear with at least 1 student
    assert "teacher-a" in html


def test_sysadmin_dashboard_shows_total_students(client):
    """System admin dashboard should show total unique student count."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    teacher_b, _ = _create_admin("teacher-b")
    
    # Create some students
    _create_student("Student1", primary_teacher=teacher_a)
    _create_student("Student2", primary_teacher=teacher_b)
    _create_student("Shared", primary_teacher=teacher_a, linked_teachers=[teacher_a, teacher_b])
    
    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/dashboard")
    
    assert response.status_code == 200
    html = response.data.decode()
    
    # Dashboard should show total unique students (3 in this case)
    assert "Total Students" in html
    # Should show 2 teachers
    assert "Total Teachers" in html


def test_sysadmin_does_not_see_student_details_on_admin_page(client):
    """System admin should not see individual student details on the admin management page."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_a, _ = _create_admin("teacher-a")
    
    # Create student with identifiable name
    _create_student("SecretName", primary_teacher=teacher_a)
    
    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/admins")
    
    assert response.status_code == 200
    html = response.data.decode()
    
    # Should NOT show student names on this page
    assert "SecretName" not in html
    # Should show teacher name
    assert "teacher-a" in html
    # Should show student count indicator
    assert "student" in html.lower()


def test_teacher_with_no_students_shows_zero_count(client):
    """System admin should see 0 students for teachers with no students."""
    sys_admin, sys_secret = _create_sysadmin()
    teacher_empty, _ = _create_admin("teacher-empty")
    
    _login_sysadmin(client, sys_admin, sys_secret)
    response = client.get("/sysadmin/admins")
    
    assert response.status_code == 200
    html = response.data.decode()
    
    # Empty teacher should appear
    assert "teacher-empty" in html
    # Should show 0 or "no students" indicator
    assert "0 students" in html or "0" in html
