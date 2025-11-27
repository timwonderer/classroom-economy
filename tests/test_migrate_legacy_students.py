"""
Test migrate-legacy-students CLI command.

This test suite verifies that the migration command correctly:
- Identifies legacy students (have teacher_id but no StudentTeacher record)
- Creates StudentTeacher many-to-many associations
- Creates TeacherBlock entries marked as claimed
- Generates stable join codes per teacher-block combination
- Handles idempotency (running twice should not create duplicates)
- Normalizes block names for consistent grouping
"""

import pyotp
from click.testing import CliRunner

from app import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock
from app.cli_commands import migrate_legacy_students_command
from hash_utils import get_random_salt, hash_username


def _create_admin(username: str) -> Admin:
    """Helper to create an admin user."""
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin


def _create_legacy_student(first_name: str, teacher: Admin, block: str = "A") -> Student:
    """
    Helper to create a legacy student (has teacher_id but no StudentTeacher or TeacherBlock).
    
    This simulates a student that was created before the multi-tenancy system
    was implemented.
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
        dob_sum=12,
        last_name_hash_by_part=["hash1", "hash2"],
        first_half_hash=hash_username(f"{first_name}-fhash", salt)  # Make unique per student
    )
    db.session.add(student)
    db.session.commit()
    return student


def _create_modern_student(first_name: str, teacher: Admin, block: str = "A") -> Student:
    """
    Helper to create a modern student (has teacher_id, StudentTeacher, and TeacherBlock).
    """
    salt = get_random_salt()
    first_half_hash = hash_username(f"{first_name}-mhash", salt)  # Make unique per student
    student = Student(
        first_name=first_name,
        last_initial="M",
        block=block,
        salt=salt,
        username_hash=hash_username(first_name.lower(), salt),
        pin_hash="pin",
        teacher_id=teacher.id,
        dob_sum=15,
        last_name_hash_by_part=["hash3", "hash4"],
        first_half_hash=first_half_hash
    )
    db.session.add(student)
    db.session.flush()
    
    # Create StudentTeacher association
    st = StudentTeacher(student_id=student.id, admin_id=teacher.id)
    db.session.add(st)
    
    # Create TeacherBlock entry
    tb = TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        first_name=first_name,
        last_initial="M",
        last_name_hash_by_part=["hash3", "hash4"],
        dob_sum=15,
        salt=salt,
        first_half_hash=first_half_hash,
        join_code="TEST123",
        is_claimed=True,
        student_id=student.id
    )
    db.session.add(tb)
    db.session.commit()
    return student


def test_migrate_no_legacy_students(client):
    """Test migration when there are no legacy students."""
    runner = CliRunner()
    result = runner.invoke(migrate_legacy_students_command)
    
    assert result.exit_code == 0
    assert "No legacy students found" in result.output


def test_migrate_single_legacy_student(client):
    """Test migration of a single legacy student."""
    teacher = _create_admin("teacher1")
    student = _create_legacy_student("Legacy1", teacher, block="A")
    
    # Verify initial state
    assert StudentTeacher.query.filter_by(student_id=student.id).count() == 0
    assert TeacherBlock.query.filter_by(student_id=student.id).count() == 0
    
    # Run migration
    runner = CliRunner()
    result = runner.invoke(migrate_legacy_students_command)
    
    assert result.exit_code == 0
    assert "Found 1 legacy student to migrate" in result.output
    assert "Created 1 StudentTeacher associations" in result.output
    assert "Created 1 TeacherBlock entries" in result.output
    
    # Verify StudentTeacher was created
    st = StudentTeacher.query.filter_by(
        student_id=student.id,
        admin_id=teacher.id
    ).first()
    assert st is not None
    
    # Verify TeacherBlock was created
    tb = TeacherBlock.query.filter_by(
        teacher_id=teacher.id,
        block="A",
        student_id=student.id
    ).first()
    assert tb is not None
    assert tb.is_claimed is True
    assert tb.join_code is not None
    assert len(tb.join_code) > 0
    assert tb.first_name == "Legacy1"
    assert tb.last_initial == "L"
    assert tb.dob_sum == 12
    assert tb.last_name_hash_by_part == ["hash1", "hash2"]
    # first_half_hash should match the student's hash (which is unique per student)
    assert tb.first_half_hash == student.first_half_hash


def test_migrate_multiple_students_same_block(client):
    """Test migration of multiple legacy students in the same teacher-block."""
    teacher = _create_admin("teacher2")
    student1 = _create_legacy_student("Legacy2", teacher, block="A")
    student2 = _create_legacy_student("Legacy3", teacher, block="A")
    
    # Run migration
    runner = CliRunner()
    result = runner.invoke(migrate_legacy_students_command)
    
    assert result.exit_code == 0
    assert "Found 2 legacy students to migrate" in result.output
    assert "Created 2 StudentTeacher associations" in result.output
    assert "Created 2 TeacherBlock entries" in result.output
    
    # Verify both students have the same join code
    tb1 = TeacherBlock.query.filter_by(student_id=student1.id).first()
    tb2 = TeacherBlock.query.filter_by(student_id=student2.id).first()
    assert tb1.join_code == tb2.join_code


def test_migrate_multiple_blocks(client):
    """Test migration of students in different blocks."""
    teacher = _create_admin("teacher3")
    student_a = _create_legacy_student("LegacyA", teacher, block="A")
    student_b = _create_legacy_student("LegacyB", teacher, block="B")
    
    # Run migration
    runner = CliRunner()
    result = runner.invoke(migrate_legacy_students_command)
    
    assert result.exit_code == 0
    assert "Found 2 unique teacher-block combinations" in result.output
    
    # Verify different blocks have different join codes
    tb_a = TeacherBlock.query.filter_by(student_id=student_a.id).first()
    tb_b = TeacherBlock.query.filter_by(student_id=student_b.id).first()
    assert tb_a.join_code != tb_b.join_code


def test_migrate_block_name_normalization(client):
    """Test that block names are normalized (strip and uppercase)."""
    teacher = _create_admin("teacher4")
    
    # Create students with blocks that should normalize to the same value
    salt1 = get_random_salt()
    student1 = Student(
        first_name="Student1",
        last_initial="N",
        block=" a ",  # lowercase with spaces
        salt=salt1,
        username_hash=hash_username("student1", salt1),
        pin_hash="pin",
        teacher_id=teacher.id
    )
    db.session.add(student1)
    
    salt2 = get_random_salt()
    student2 = Student(
        first_name="Student2",
        last_initial="N",
        block="A",  # uppercase no spaces
        salt=salt2,
        username_hash=hash_username("student2", salt2),
        pin_hash="pin",
        teacher_id=teacher.id
    )
    db.session.add(student2)
    db.session.commit()
    
    # Run migration
    runner = CliRunner()
    result = runner.invoke(migrate_legacy_students_command)
    
    assert result.exit_code == 0
    assert "Found 1 unique teacher-block combinations" in result.output
    
    # Verify both students have the same join code (because blocks normalize to "A")
    tb1 = TeacherBlock.query.filter_by(student_id=student1.id).first()
    tb2 = TeacherBlock.query.filter_by(student_id=student2.id).first()
    assert tb1.join_code == tb2.join_code
    assert tb1.block == "A"
    assert tb2.block == "A"


def test_migrate_idempotency(client):
    """Test that running migration twice doesn't create duplicates."""
    teacher = _create_admin("teacher5")
    student = _create_legacy_student("Legacy5", teacher, block="A")
    
    # Run migration first time
    runner = CliRunner()
    result1 = runner.invoke(migrate_legacy_students_command)
    assert result1.exit_code == 0
    assert "Created 1 StudentTeacher associations" in result1.output
    
    # Count records after first migration
    st_count_1 = StudentTeacher.query.filter_by(student_id=student.id).count()
    tb_count_1 = TeacherBlock.query.filter_by(student_id=student.id).count()
    assert st_count_1 == 1
    assert tb_count_1 == 1
    
    # Run migration second time
    result2 = runner.invoke(migrate_legacy_students_command)
    assert result2.exit_code == 0
    assert "No legacy students found" in result2.output
    
    # Verify no duplicates were created
    st_count_2 = StudentTeacher.query.filter_by(student_id=student.id).count()
    tb_count_2 = TeacherBlock.query.filter_by(student_id=student.id).count()
    assert st_count_2 == 1
    assert tb_count_2 == 1


def test_migrate_partial_migration_state(client):
    """Test migration when StudentTeacher exists but TeacherBlock doesn't."""
    teacher = _create_admin("teacher6")
    salt = get_random_salt()
    student = Student(
        first_name="Partial",
        last_initial="P",
        block="A",
        salt=salt,
        username_hash=hash_username("partial", salt),
        pin_hash="pin",
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.flush()
    
    # Create only StudentTeacher, not TeacherBlock
    st = StudentTeacher(student_id=student.id, admin_id=teacher.id)
    db.session.add(st)
    db.session.commit()
    
    # Verify initial state
    assert StudentTeacher.query.filter_by(student_id=student.id).count() == 1
    assert TeacherBlock.query.filter_by(student_id=student.id).count() == 0
    
    # Run migration - should skip creating StudentTeacher but create TeacherBlock
    runner = CliRunner()
    result = runner.invoke(migrate_legacy_students_command)
    
    assert result.exit_code == 0
    # Should report no legacy students since StudentTeacher exists
    assert "No legacy students found" in result.output
    
    # Verify no additional StudentTeacher was created
    assert StudentTeacher.query.filter_by(student_id=student.id).count() == 1


def test_migrate_skip_modern_students(client):
    """Test that modern students (already migrated) are skipped."""
    teacher = _create_admin("teacher7")
    _create_legacy_student("Legacy7", teacher, block="A")  # Creates side-effect, not referenced
    modern = _create_modern_student("Modern7", teacher, block="A")
    
    # Run migration
    runner = CliRunner()
    result = runner.invoke(migrate_legacy_students_command)
    
    assert result.exit_code == 0
    # Should only find 1 legacy student
    assert "Found 1 legacy student to migrate" in result.output
    
    # Verify modern student's records are unchanged
    st_count = StudentTeacher.query.filter_by(student_id=modern.id).count()
    tb_count = TeacherBlock.query.filter_by(student_id=modern.id).count()
    assert st_count == 1
    assert tb_count == 1


def test_migrate_reuses_existing_join_code(client):
    """Test that migration reuses existing join codes when available."""
    teacher = _create_admin("teacher8")
    
    # Create a modern student with a join code
    modern = _create_modern_student("Modern8", teacher, block="A")
    existing_tb = TeacherBlock.query.filter_by(student_id=modern.id).first()
    existing_join_code = existing_tb.join_code
    
    # Create a legacy student in the same block
    legacy = _create_legacy_student("Legacy8", teacher, block="A")
    
    # Run migration
    runner = CliRunner()
    result = runner.invoke(migrate_legacy_students_command)
    
    assert result.exit_code == 0
    assert f"Reusing existing join code {existing_join_code}" in result.output
    
    # Verify legacy student got the same join code
    legacy_tb = TeacherBlock.query.filter_by(student_id=legacy.id).first()
    assert legacy_tb.join_code == existing_join_code


def test_migrate_multiple_teachers(client):
    """Test migration with students from multiple teachers."""
    teacher1 = _create_admin("teacher9a")
    teacher2 = _create_admin("teacher9b")
    
    student1 = _create_legacy_student("Legacy9a", teacher1, block="A")
    student2 = _create_legacy_student("Legacy9b", teacher2, block="A")
    
    # Run migration
    runner = CliRunner()
    result = runner.invoke(migrate_legacy_students_command)
    
    assert result.exit_code == 0
    assert "Found 2 legacy students to migrate" in result.output
    assert "Found 2 unique teacher-block combinations" in result.output
    
    # Verify each teacher-block has a different join code
    tb1 = TeacherBlock.query.filter_by(student_id=student1.id).first()
    tb2 = TeacherBlock.query.filter_by(student_id=student2.id).first()
    assert tb1.join_code != tb2.join_code


def test_migrate_verification_passes(client):
    """Test that verification step passes after successful migration."""
    teacher = _create_admin("teacher10")
    _create_legacy_student("Legacy10", teacher, block="A")
    
    runner = CliRunner()
    result = runner.invoke(migrate_legacy_students_command)
    
    assert result.exit_code == 0
    assert "Verification passed" in result.output
    assert "No remaining legacy students" in result.output
