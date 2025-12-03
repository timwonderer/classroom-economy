"""
Test legacy student upgrade when editing and duplicate detection in roster upload.

Tests that:
1. Editing a legacy student creates StudentTeacher record if missing
2. Editing a legacy student creates TeacherBlock entries if missing
3. Duplicate detection in roster upload includes dob_sum to distinguish students
"""

import io
import pyotp
from datetime import datetime, timezone
from app import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock
from hash_utils import get_random_salt, hash_username


def _create_admin(username: str) -> tuple[Admin, str]:
    """Helper to create an admin user with TOTP secret."""
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin, secret


def _login_admin(client, admin: Admin, secret: str):
    """Login an admin user."""
    with client.session_transaction() as sess:
        sess["is_admin"] = True
        sess["admin_id"] = admin.id
        sess["is_system_admin"] = False
        sess["last_activity"] = datetime.now(timezone.utc).isoformat()


def _create_legacy_student(first_name: str, teacher: Admin, block: str = "A", dob_sum: int = 2025) -> Student:
    """
    Create a legacy student (has teacher_id but no StudentTeacher or TeacherBlock).
    
    This simulates a student created before the multi-tenancy system was implemented.
    """
    salt = get_random_salt()
    student = Student(
        first_name=first_name,
        last_initial="L",
        block=block,
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin",
        teacher_id=teacher.id,
        dob_sum=dob_sum,
        last_name_hash_by_part=["hash1", "hash2"],
        first_half_hash=hash_username(f"{first_name}-fhash", salt)
    )
    db.session.add(student)
    db.session.commit()
    return student


def test_edit_legacy_student_creates_student_teacher_record(client):
    """Test that editing a legacy student creates a StudentTeacher record."""
    # Create admin
    teacher, secret = _create_admin("teacher1")
    
    # Create legacy student (no StudentTeacher or TeacherBlock)
    legacy_student = _create_legacy_student("John", teacher, block="A")
    
    # Verify no StudentTeacher record exists
    st = StudentTeacher.query.filter_by(
        student_id=legacy_student.id,
        admin_id=teacher.id
    ).first()
    assert st is None, "StudentTeacher record should not exist initially"
    
    # Login as admin
    _login_admin(client, teacher, secret)
    
    # Edit the student
    response = client.post('/admin/student/edit', data={
        'student_id': legacy_student.id,
        'first_name': 'John',
        'last_name': 'Smith',
        'blocks': ['A'],
        'dob_sum': '2025'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify StudentTeacher record was created
    st = StudentTeacher.query.filter_by(
        student_id=legacy_student.id,
        admin_id=teacher.id
    ).first()
    assert st is not None, "StudentTeacher record should be created when editing legacy student"


def test_edit_legacy_student_creates_teacher_block_entries(client):
    """Test that editing a legacy student creates TeacherBlock entries."""
    # Create admin
    teacher, secret = _create_admin("teacher2")
    
    # Create legacy student with multiple blocks
    legacy_student = _create_legacy_student("Jane", teacher, block="A,B")
    
    # Verify no TeacherBlock records exist
    tbs = TeacherBlock.query.filter_by(
        student_id=legacy_student.id,
        teacher_id=teacher.id
    ).all()
    assert len(tbs) == 0, "No TeacherBlock records should exist initially"
    
    # Login as admin
    _login_admin(client, teacher, secret)
    
    # Edit the student
    response = client.post('/admin/student/edit', data={
        'student_id': legacy_student.id,
        'first_name': 'Jane',
        'last_name': 'Doe',
        'blocks': ['A', 'B'],
        'dob_sum': '2025'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify TeacherBlock records were created for both blocks
    tbs = TeacherBlock.query.filter_by(
        student_id=legacy_student.id,
        teacher_id=teacher.id
    ).all()
    assert len(tbs) == 2, "TeacherBlock records should be created for all blocks"
    
    # Verify the blocks are correct
    blocks = sorted([tb.block for tb in tbs])
    assert blocks == ['A', 'B'], "TeacherBlock entries should be created for both blocks"
    
    # Verify each TeacherBlock has a join code
    for tb in tbs:
        assert tb.join_code is not None, "TeacherBlock should have a join code"
        assert len(tb.join_code) > 0, "Join code should not be empty"


def test_edit_legacy_student_idempotent(client):
    """Test that editing a legacy student multiple times doesn't create duplicates."""
    # Create admin
    teacher, secret = _create_admin("teacher3")
    
    # Create legacy student
    legacy_student = _create_legacy_student("Bob", teacher, block="C")
    
    # Login as admin
    _login_admin(client, teacher, secret)
    
    # Edit the student twice
    for _ in range(2):
        response = client.post('/admin/student/edit', data={
            'student_id': legacy_student.id,
            'first_name': 'Bob',
            'last_name': 'Johnson',
            'blocks': ['C'],
            'dob_sum': '2025'
        }, follow_redirects=True)
        assert response.status_code == 200
    
    # Verify only one StudentTeacher record exists
    st_count = StudentTeacher.query.filter_by(
        student_id=legacy_student.id,
        admin_id=teacher.id
    ).count()
    assert st_count == 1, "Only one StudentTeacher record should exist"
    
    # Verify only one TeacherBlock record exists per block
    tb_count = TeacherBlock.query.filter_by(
        student_id=legacy_student.id,
        teacher_id=teacher.id
    ).count()
    assert tb_count == 1, "Only one TeacherBlock record should exist per block"


def test_roster_upload_duplicate_detection_with_different_dob(client):
    """Test that students with same name but different DOB are both created."""
    # Create admin
    teacher, secret = _create_admin("teacher4")
    
    # Login as admin
    _login_admin(client, teacher, secret)
    
    # First upload: John Smith with DOB 01/15/2010 (sum = 1+15+2010 = 2026)
    csv_content1 = (
        "First Name,Last Name,Date of Birth (MM/DD/YYYY),Period/Block\n"
        "John,Smith,01/15/2010,A\n"
    )
    
    response1 = client.post('/admin/upload-students', data={
        'csv_file': (io.BytesIO(csv_content1.encode()), 'roster1.csv')
    }, follow_redirects=False)
    
    assert response1.status_code == 302  # Redirect after successful upload
    
    # Verify first student was created
    # Note: first_name is encrypted, so we can't filter by it directly
    tbs = TeacherBlock.query.filter_by(
        teacher_id=teacher.id,
        last_initial="S",
        block="A",
        dob_sum=2026
    ).all()
    tb1 = next((tb for tb in tbs if tb.first_name == "John"), None)
    assert tb1 is not None, "First student (John Smith with DOB sum 2026) should be created"
    
    # Second upload: John Summit with DOB 03/22/2011 (sum = 3+22+2011 = 2036)
    csv_content2 = (
        "First Name,Last Name,Date of Birth (MM/DD/YYYY),Period/Block\n"
        "John,Summit,03/22/2011,A\n"
    )
    
    response2 = client.post('/admin/upload-students', data={
        'csv_file': (io.BytesIO(csv_content2.encode()), 'roster2.csv')
    }, follow_redirects=False)
    
    assert response2.status_code == 302  # Redirect after successful upload
    
    # Verify second student was also created (not skipped as duplicate)
    # Note: first_name is encrypted, so we can't filter by it directly
    tbs2 = TeacherBlock.query.filter_by(
        teacher_id=teacher.id,
        last_initial="S",
        block="A",
        dob_sum=2036
    ).all()
    tb2 = next((tb for tb in tbs2 if tb.first_name == "John"), None)
    assert tb2 is not None, "Second student (John Summit with DOB sum 2036) should be created"
    
    # Verify both students exist
    all_johns = TeacherBlock.query.filter_by(
        teacher_id=teacher.id,
        last_initial="S",
        block="A"
    ).all()
    johns = [tb for tb in all_johns if tb.first_name == "John"]
    assert len(johns) == 2, "Both John S. students with different DOBs should exist"


def test_roster_upload_duplicate_detection_with_same_dob(client):
    """Test that actual duplicates (same name AND DOB) are still skipped."""
    # Create admin
    teacher, secret = _create_admin("teacher5")
    
    # Login as admin
    _login_admin(client, teacher, secret)
    
    # First upload: Alice Brown with DOB 05/10/2009
    csv_content = (
        "First Name,Last Name,Date of Birth (MM/DD/YYYY),Period/Block\n"
        "Alice,Brown,05/10/2009,B\n"
    )
    
    response1 = client.post('/admin/upload-students', data={
        'csv_file': (io.BytesIO(csv_content.encode()), 'roster1.csv')
    }, follow_redirects=False)
    
    assert response1.status_code == 302  # Redirect after successful upload
    
    # Second upload: Same student (duplicate)
    response2 = client.post('/admin/upload-students', data={
        'csv_file': (io.BytesIO(csv_content.encode()), 'roster2.csv')
    }, follow_redirects=False)
    
    assert response2.status_code == 302  # Redirect after successful upload
    
    # Verify only one student exists (duplicate was skipped)
    # Note: first_name is encrypted, so we can't filter by it directly
    all_b_students = TeacherBlock.query.filter_by(
        teacher_id=teacher.id,
        last_initial="B",
        block="B",
        dob_sum=5+10+2009  # 2024
    ).all()
    alices = [tb for tb in all_b_students if tb.first_name == "Alice"]
    assert len(alices) == 1, "Duplicate student should be skipped, only one record should exist"


def test_roster_upload_mixed_names_different_dobs(client):
    """Test a realistic scenario with multiple students having similar names."""
    # Create admin
    teacher, secret = _create_admin("teacher6")
    
    # Login as admin
    _login_admin(client, teacher, secret)
    
    # Upload roster with three "Sarah S." students with different last names and DOBs
    csv_content = (
        "First Name,Last Name,Date of Birth (MM/DD/YYYY),Period/Block\n"
        "Sarah,Smith,01/05/2010,C\n"
        "Sarah,Sullivan,02/10/2010,C\n"
        "Sarah,Santos,03/15/2010,C\n"
    )
    
    response = client.post('/admin/upload-students', data={
        'csv_file': (io.BytesIO(csv_content.encode()), 'roster.csv')
    }, follow_redirects=False)
    
    assert response.status_code == 302  # Redirect after successful upload
    
    # Verify all three students were created
    # Note: first_name is encrypted, so we can't filter by it directly
    all_s_students = TeacherBlock.query.filter_by(
        teacher_id=teacher.id,
        last_initial="S",
        block="C"
    ).all()
    sarahs = [tb for tb in all_s_students if tb.first_name == "Sarah"]
    assert len(sarahs) == 3, "All three Sarah S. students with different DOBs should be created"
    
    # Verify they have different dob_sums
    dob_sums = sorted([s.dob_sum for s in sarahs])
    expected_sums = sorted([
        1+5+2010,   # 2016 - Sarah Smith
        2+10+2010,  # 2022 - Sarah Sullivan
        3+15+2010   # 2028 - Sarah Santos
    ])
    assert dob_sums == expected_sums, "Each Sarah S. should have different dob_sum"
