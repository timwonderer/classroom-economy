"""
Test repair_teacher_block_hashes CLI command.

This test suite verifies that the repair command correctly:
- Finds TeacherBlock entries with incorrect first_half_hash values
- Computes the correct hash using last_initial + dob_sum
- Supports dry-run mode to preview changes
- Skips placeholder entries
- Handles entries without required fields gracefully
- Is idempotent (running twice produces consistent results)
"""

import pyotp
from click.testing import CliRunner

from app import db
from app.models import Admin, Student, StudentTeacher, TeacherBlock
from hash_utils import get_random_salt, hash_hmac, hash_username


# Placeholder constant matching the one in admin.py
LEGACY_PLACEHOLDER_FIRST_NAME = "__JOIN_CODE_PLACEHOLDER__"


def _create_admin(username: str) -> Admin:
    """Helper to create an admin user."""
    secret = pyotp.random_base32()
    admin = Admin(username=username, totp_secret=secret)
    db.session.add(admin)
    db.session.commit()
    return admin


def _create_teacher_block_with_wrong_hash(
    teacher: Admin,
    first_name: str,
    last_initial: str,
    dob_sum: int,
    block: str = "A",
    is_claimed: bool = False,
    student_id: int = None
) -> TeacherBlock:
    """
    Create a TeacherBlock with an intentionally wrong first_half_hash.
    
    This simulates TeacherBlock entries created before the hash fix.
    """
    salt = get_random_salt()
    # Create wrong hash (using a bogus formula like the old code)
    wrong_hash = hash_hmac(f"{first_name}-bogus".encode(), salt)
    
    tb = TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        first_name=first_name,
        last_initial=last_initial,
        last_name_hash_by_part=["hash1", "hash2"],
        dob_sum=dob_sum,
        salt=salt,
        first_half_hash=wrong_hash,
        join_code="TEST123",
        is_claimed=is_claimed,
        student_id=student_id
    )
    db.session.add(tb)
    db.session.commit()
    return tb


def _create_teacher_block_with_correct_hash(
    teacher: Admin,
    first_name: str,
    last_initial: str,
    dob_sum: int,
    block: str = "A",
    is_claimed: bool = False,
    student_id: int = None
) -> TeacherBlock:
    """
    Create a TeacherBlock with the correct first_half_hash.
    """
    salt = get_random_salt()
    # Create correct hash using last_initial + dob_sum
    credential = f"{last_initial}{dob_sum}"
    correct_hash = hash_hmac(credential.encode(), salt)
    
    tb = TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        first_name=first_name,
        last_initial=last_initial,
        last_name_hash_by_part=["hash1", "hash2"],
        dob_sum=dob_sum,
        salt=salt,
        first_half_hash=correct_hash,
        join_code="CORRECT123",
        is_claimed=is_claimed,
        student_id=student_id
    )
    db.session.add(tb)
    db.session.commit()
    return tb


def _create_placeholder_teacher_block(teacher: Admin, block: str = "A") -> TeacherBlock:
    """
    Create a placeholder TeacherBlock entry.
    """
    salt = get_random_salt()
    placeholder_hash = hash_hmac("LEGACY0".encode(), salt)
    
    tb = TeacherBlock(
        teacher_id=teacher.id,
        block=block,
        first_name=LEGACY_PLACEHOLDER_FIRST_NAME,
        last_initial="P",
        last_name_hash_by_part=[],
        dob_sum=0,
        salt=salt,
        first_half_hash=placeholder_hash,
        join_code="PLACEHOLDER123",
        is_claimed=False,
        student_id=None
    )
    db.session.add(tb)
    db.session.commit()
    return tb


def test_repair_no_teacher_blocks(client):
    """Test repair when there are no TeacherBlock entries."""
    # Import here to ensure app context is available
    from app.cli_commands import repair_teacher_block_hashes_command
    
    runner = CliRunner()
    result = runner.invoke(repair_teacher_block_hashes_command, ['--dry-run'])
    
    assert result.exit_code == 0
    assert "No TeacherBlock entries found" in result.output


def test_repair_dry_run_wrong_hash(client):
    """Test dry-run mode identifies entries with wrong hashes."""
    from app.cli_commands import repair_teacher_block_hashes_command
    
    teacher = _create_admin("teacher1")
    tb = _create_teacher_block_with_wrong_hash(
        teacher, "John", "S", 2025, block="A"
    )
    original_hash = tb.first_half_hash
    
    runner = CliRunner()
    result = runner.invoke(repair_teacher_block_hashes_command, ['--dry-run'])
    
    assert result.exit_code == 0
    assert "DRY RUN MODE" in result.output
    assert "FIX:" in result.output
    assert "Fixed:                 1" in result.output
    
    # Verify hash was NOT changed (dry-run)
    db.session.refresh(tb)
    assert tb.first_half_hash == original_hash


def test_repair_applies_fix(client):
    """Test that repair actually updates the hash when not in dry-run mode."""
    from app.cli_commands import repair_teacher_block_hashes_command
    
    teacher = _create_admin("teacher2")
    tb = _create_teacher_block_with_wrong_hash(
        teacher, "Jane", "D", 1985, block="B"
    )
    original_hash = tb.first_half_hash
    
    runner = CliRunner()
    result = runner.invoke(repair_teacher_block_hashes_command)
    
    assert result.exit_code == 0
    assert "Fixed:                 1" in result.output
    assert "Repair complete! Fixed 1 entries" in result.output
    
    # Verify hash WAS changed
    db.session.refresh(tb)
    assert tb.first_half_hash != original_hash
    
    # Verify the new hash is correct
    expected_credential = f"{tb.last_initial}{tb.dob_sum}"  # "D1985"
    expected_hash = hash_hmac(expected_credential.encode(), tb.salt)
    assert tb.first_half_hash == expected_hash


def test_repair_skips_correct_entries(client):
    """Test that entries with correct hashes are not modified."""
    from app.cli_commands import repair_teacher_block_hashes_command
    
    teacher = _create_admin("teacher3")
    tb = _create_teacher_block_with_correct_hash(
        teacher, "Alice", "M", 2000, block="C"
    )
    original_hash = tb.first_half_hash
    
    runner = CliRunner()
    result = runner.invoke(repair_teacher_block_hashes_command)
    
    assert result.exit_code == 0
    assert "Already correct:       1" in result.output
    assert "Fixed:                 0" in result.output
    assert "All hashes were already correct" in result.output
    
    # Verify hash was NOT changed
    db.session.refresh(tb)
    assert tb.first_half_hash == original_hash


def test_repair_skips_placeholders(client):
    """Test that placeholder entries are skipped."""
    from app.cli_commands import repair_teacher_block_hashes_command
    
    teacher = _create_admin("teacher4")
    tb = _create_placeholder_teacher_block(teacher, block="A")
    original_hash = tb.first_half_hash
    
    runner = CliRunner()
    result = runner.invoke(repair_teacher_block_hashes_command, ['--dry-run'])
    
    assert result.exit_code == 0
    assert "Skipped (placeholders):1" in result.output
    
    # Verify hash was NOT changed
    db.session.refresh(tb)
    assert tb.first_half_hash == original_hash


def test_repair_mixed_entries(client):
    """Test repair with mix of correct, wrong, and placeholder entries."""
    from app.cli_commands import repair_teacher_block_hashes_command
    
    teacher = _create_admin("teacher5")
    
    # Create entries with different states
    tb_wrong = _create_teacher_block_with_wrong_hash(
        teacher, "Wrong", "W", 100, block="A"
    )
    tb_correct = _create_teacher_block_with_correct_hash(
        teacher, "Correct", "C", 200, block="B"
    )
    tb_placeholder = _create_placeholder_teacher_block(teacher, block="C")
    
    runner = CliRunner()
    result = runner.invoke(repair_teacher_block_hashes_command)
    
    assert result.exit_code == 0
    assert "Total entries checked: 3" in result.output
    assert "Already correct:       1" in result.output
    assert "Fixed:                 1" in result.output
    assert "Skipped (placeholders):1" in result.output
    
    # Verify wrong hash was fixed
    db.session.refresh(tb_wrong)
    expected_credential = f"{tb_wrong.last_initial}{tb_wrong.dob_sum}"
    expected_hash = hash_hmac(expected_credential.encode(), tb_wrong.salt)
    assert tb_wrong.first_half_hash == expected_hash


def test_repair_idempotency(client):
    """Test that running repair twice produces consistent results."""
    from app.cli_commands import repair_teacher_block_hashes_command
    
    teacher = _create_admin("teacher6")
    tb = _create_teacher_block_with_wrong_hash(
        teacher, "Idempotent", "I", 500, block="A"
    )
    
    runner = CliRunner()
    
    # First run
    result1 = runner.invoke(repair_teacher_block_hashes_command)
    assert result1.exit_code == 0
    assert "Fixed:                 1" in result1.output
    
    db.session.refresh(tb)
    fixed_hash = tb.first_half_hash
    
    # Second run
    result2 = runner.invoke(repair_teacher_block_hashes_command)
    assert result2.exit_code == 0
    assert "Already correct:       1" in result2.output
    assert "Fixed:                 0" in result2.output
    
    # Verify hash is unchanged after second run
    db.session.refresh(tb)
    assert tb.first_half_hash == fixed_hash


def test_repair_handles_claimed_and_unclaimed(client):
    """Test that both claimed and unclaimed seats are repaired."""
    from app.cli_commands import repair_teacher_block_hashes_command
    
    teacher = _create_admin("teacher7")
    
    # Create a student to link to claimed seat
    salt = get_random_salt()
    student = Student(
        first_name="Test",
        last_initial="T",
        block="A",
        salt=salt,
        username_hash=hash_username("test", salt),
        pin_hash="pin",
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.commit()
    
    # Create claimed seat with wrong hash
    tb_claimed = _create_teacher_block_with_wrong_hash(
        teacher, "Claimed", "C", 300, block="A", 
        is_claimed=True, student_id=student.id
    )
    
    # Create unclaimed seat with wrong hash
    tb_unclaimed = _create_teacher_block_with_wrong_hash(
        teacher, "Unclaimed", "U", 400, block="B",
        is_claimed=False, student_id=None
    )
    
    runner = CliRunner()
    result = runner.invoke(repair_teacher_block_hashes_command)
    
    assert result.exit_code == 0
    # Should include both in the output (one claimed, one unclaimed)
    assert "claimed" in result.output
    assert "unclaimed" in result.output
    assert "Fixed:                 2" in result.output
    
    # Verify both were fixed
    db.session.refresh(tb_claimed)
    db.session.refresh(tb_unclaimed)
    
    expected_claimed = hash_hmac(f"{tb_claimed.last_initial}{tb_claimed.dob_sum}".encode(), tb_claimed.salt)
    expected_unclaimed = hash_hmac(f"{tb_unclaimed.last_initial}{tb_unclaimed.dob_sum}".encode(), tb_unclaimed.salt)
    
    assert tb_claimed.first_half_hash == expected_claimed
    assert tb_unclaimed.first_half_hash == expected_unclaimed
