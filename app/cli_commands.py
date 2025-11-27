"""
Flask CLI commands for database operations and migrations.
"""

import click
import time
from datetime import datetime

from app.extensions import db
from app.models import Student, StudentTeacher, TeacherBlock
from app.utils.join_code import generate_join_code
from app.routes.admin import (
    MAX_JOIN_CODE_RETRIES,
    FALLBACK_BLOCK_PREFIX_LENGTH,
    FALLBACK_CODE_MODULO
)
from hash_utils import hash_hmac


@click.command('migrate-legacy-students')
def migrate_legacy_students_command():
    """
    Migrate legacy students to the new association system.

    This command:
    1. Finds all legacy students (have teacher_id but no StudentTeacher record)
    2. Creates StudentTeacher many-to-many associations
    3. Creates TeacherBlock entries (marked as claimed) for each legacy student
    4. Generates stable join codes per teacher-block combination
    """
    click.echo("=" * 70)
    click.echo("LEGACY STUDENT MIGRATION")
    click.echo("=" * 70)
    click.echo()

    # Step 1: Find all legacy students
    click.echo("Step 1: Finding legacy students...")

    all_students_with_teacher_id = Student.query.filter(
        Student.teacher_id.isnot(None)
    ).all()

    # Batch query: get all existing StudentTeacher associations for these students
    student_ids = [s.id for s in all_students_with_teacher_id]
    existing_associations = set()
    if student_ids:
        existing_associations = set(
            (st.student_id, st.admin_id)
            for st in StudentTeacher.query.filter(
                StudentTeacher.student_id.in_(student_ids)
            ).all()
        )

    # Filter to find legacy students (no StudentTeacher record for (student_id, teacher_id))
    legacy_students = [
        student for student in all_students_with_teacher_id
        if (student.id, student.teacher_id) not in existing_associations
    ]

    if not legacy_students:
        click.echo("✓ No legacy students found! All students are already migrated.")
        return

    student_word = "student" if len(legacy_students) == 1 else "students"
    click.echo(f"Found {len(legacy_students)} legacy {student_word} to migrate")
    click.echo()

    # Step 2: Create StudentTeacher associations
    click.echo("Step 2: Creating StudentTeacher associations...")
    student_teacher_created = 0

    for student in legacy_students:
        # Check if StudentTeacher record already exists (idempotency check)
        existing_st = StudentTeacher.query.filter_by(
            student_id=student.id,
            admin_id=student.teacher_id
        ).first()

        if not existing_st:
            st = StudentTeacher(
                student_id=student.id,
                admin_id=student.teacher_id,
                created_at=datetime.utcnow()
            )
            db.session.add(st)
            student_teacher_created += 1
            click.echo(f"  ✓ Created StudentTeacher for {student.full_name} (ID: {student.id})")
        else:
            click.echo(f"  ⊙ StudentTeacher already exists for {student.full_name}, skipping")

    click.echo(f"Created {student_teacher_created} StudentTeacher associations")
    click.echo()

    # Step 3: Group students by (teacher_id, block) for join code generation
    click.echo("Step 3: Grouping students by teacher and block...")
    groups = {}
    for student in legacy_students:
        # Normalize block name for consistent grouping
        normalized_block = student.block.strip().upper() if student.block else ''
        key = (student.teacher_id, normalized_block)
        if key not in groups:
            groups[key] = []
        groups[key].append(student)

    click.echo(f"Found {len(groups)} unique teacher-block combinations")
    click.echo()

    # Step 4: Generate join codes and create TeacherBlock entries
    click.echo("Step 4: Creating TeacherBlock entries...")
    teacher_blocks_created = 0
    join_codes_by_teacher_block = {}
    skipped_students = []

    # Preload existing join codes for all teacher-block combinations
    teacher_ids = list(set(tid for tid, _ in groups.keys()))
    existing_join_codes_map = {}
    if teacher_ids:
        existing_tbs = TeacherBlock.query.filter(
            TeacherBlock.teacher_id.in_(teacher_ids),
            TeacherBlock.join_code.isnot(None),
            TeacherBlock.join_code != ''
        ).all()
        for tb in existing_tbs:
            existing_join_codes_map[(tb.teacher_id, tb.block)] = tb.join_code

    # Preload all existing join codes into a set for uniqueness checking
    existing_join_code_set = set(
        tb.join_code for tb in TeacherBlock.query.filter(
            TeacherBlock.join_code.isnot(None)
        ).with_entities(TeacherBlock.join_code).all()
    )

    # Preload existing TeacherBlock seats to avoid N+1 queries
    existing_seats = set()
    if teacher_ids:
        seats = TeacherBlock.query.filter(
            TeacherBlock.teacher_id.in_(teacher_ids),
            TeacherBlock.student_id.isnot(None)
        ).all()
        existing_seats = set((tb.teacher_id, tb.block, tb.student_id) for tb in seats)

    for (teacher_id, block), students in groups.items():
        # Check if this teacher-block already has a join code
        if (teacher_id, block) in existing_join_codes_map:
            join_code = existing_join_codes_map[(teacher_id, block)]
            click.echo(f"  → Reusing existing join code {join_code} for teacher {teacher_id}, block {block}")
        else:
            # Generate new unique join code with bounded retries
            # Using 10x standard retry limit for migration scenarios
            max_attempts = MAX_JOIN_CODE_RETRIES * 10
            join_code = None
            for _ in range(max_attempts):
                candidate = generate_join_code()
                # Check uniqueness using preloaded set
                if candidate not in existing_join_code_set:
                    join_code = candidate
                    existing_join_code_set.add(candidate)  # Track newly generated codes
                    break

            if not join_code:
                click.echo(f"  ✗ Failed to generate unique join code after {max_attempts} attempts", err=True)
                # Mark all students in this group as skipped
                skipped_students.extend(students)
                continue

            click.echo(f"  → Generated new join code {join_code} for teacher {teacher_id}, block {block}")

        join_codes_by_teacher_block[(teacher_id, block)] = join_code

        # Create TeacherBlock entry for each student in this group
        for student in students:
            # Check if TeacherBlock already exists using preloaded set
            if (teacher_id, block, student.id) in existing_seats:
                click.echo(f"    ⊙ TeacherBlock already exists for {student.full_name}, skipping")
                continue

            # Create new TeacherBlock entry using student's existing credentials
            # Compute first_half_hash correctly using last_initial + dob_sum
            credential = f"{student.last_initial}{student.dob_sum or 0}"
            first_half_hash = hash_hmac(credential.encode(), student.salt)

            tb = TeacherBlock(
                teacher_id=teacher_id,
                block=block,
                first_name=student.first_name,
                last_initial=student.last_initial,
                last_name_hash_by_part=student.last_name_hash_by_part or [],
                dob_sum=student.dob_sum or 0,
                salt=student.salt,
                first_half_hash=first_half_hash,
                join_code=join_code,
                is_claimed=True,  # Mark as claimed since student already exists
                student_id=student.id,  # Link to existing student
                claimed_at=datetime.utcnow()
            )
            db.session.add(tb)
            teacher_blocks_created += 1
            click.echo(f"    ✓ Created TeacherBlock for {student.full_name} (claimed)")

    click.echo(f"Created {teacher_blocks_created} TeacherBlock entries")
    click.echo()

    # Step 5: Commit all changes
    click.echo("Step 5: Committing changes to database...")
    try:
        db.session.commit()
        click.echo("✓ All changes committed successfully!")
        click.echo()

        # Summary
        click.echo("=" * 70)
        click.echo("MIGRATION SUMMARY")
        click.echo("=" * 70)
        click.echo(f"Legacy students found: {len(legacy_students)}")
        click.echo(f"StudentTeacher associations created: {student_teacher_created}")
        click.echo(f"TeacherBlock entries created: {teacher_blocks_created}")
        click.echo(f"Unique teacher-block combinations: {len(groups)}")
        if skipped_students:
            click.echo(f"Students skipped due to errors: {len(skipped_students)}")
        click.echo()

        if join_codes_by_teacher_block:
            click.echo("Join codes by teacher and block:")
            for (teacher_id, block), code in sorted(join_codes_by_teacher_block.items()):
                click.echo(f"  Teacher {teacher_id}, Block {block}: {code}")
            click.echo()

        click.echo("✓ Migration complete! All legacy students now use the new system.")
        click.echo()

        # Verification
        click.echo("Verifying migration...")
        remaining_legacy = Student.query.filter(
            Student.teacher_id.isnot(None)
        ).all()

        # Batch query: collect all (student_id, teacher_id) pairs
        pairs = [(student.id, student.teacher_id) for student in remaining_legacy]
        still_legacy = []
        if pairs:
            # Query all StudentTeacher records matching these pairs
            student_ids = [sid for sid, _ in pairs]
            st_records = StudentTeacher.query.filter(
                StudentTeacher.student_id.in_(student_ids)
            ).all()
            existing_pairs = set((st.student_id, st.admin_id) for st in st_records)
            still_legacy = [
                student for student in remaining_legacy
                if (student.id, student.teacher_id) not in existing_pairs
            ]

        if still_legacy:
            click.echo(f"⚠ Warning: {len(still_legacy)} students still need migration")
            for student in still_legacy:
                click.echo(f"  - {student.full_name} (ID: {student.id})")
        else:
            click.echo("✓ Verification passed! No remaining legacy students.")

    except Exception as e:
        db.session.rollback()
        click.echo(f"\n✗ Error during commit: {str(e)}", err=True)
        import traceback
        traceback.print_exc()
        raise click.Abort()


@click.command('fix-missing-teacher-blocks')
def fix_missing_teacher_blocks_command():
    """
    Create missing TeacherBlock entries for students with completed setup.

    This command addresses the issue where students have:
    - Completed setup (has_completed_setup=True)
    - StudentTeacher associations
    - BUT no claimed TeacherBlock entries

    This prevents teachers from seeing their rosters because there's no TeacherBlock
    linking the student's block/period to the teacher.
    """
    click.echo("=" * 70)
    click.echo("FIX MISSING TEACHER BLOCKS")
    click.echo("=" * 70)
    click.echo()

    # Step 1: Find students with completed setup but no TeacherBlock
    click.echo("Step 1: Finding students with completed setup but no claimed TeacherBlock...")

    students_with_setup = Student.query.filter_by(has_completed_setup=True).all()
    click.echo(f"Total students with completed setup: {len(students_with_setup)}")

    # Batch query: get all claimed TeacherBlock entries for these students
    student_ids = [student.id for student in students_with_setup]
    claimed_blocks = TeacherBlock.query.filter(
        TeacherBlock.student_id.in_(student_ids),
        TeacherBlock.is_claimed == True
    ).all()
    claimed_student_ids = set(tb.student_id for tb in claimed_blocks)

    students_needing_fix = [student for student in students_with_setup if student.id not in claimed_student_ids]

    click.echo(f"Students without claimed TeacherBlock: {len(students_needing_fix)}")

    if not students_needing_fix:
        click.echo("✓ No students need fixing! All students with completed setup have TeacherBlock entries.")
        return

    click.echo()
    click.echo(f"Found {len(students_needing_fix)} students that need TeacherBlock entries:")
    for student in students_needing_fix[:10]:
        click.echo(f"  - {student.full_name} (ID: {student.id}, Block: {student.block})")
    if len(students_needing_fix) > 10:
        click.echo(f"  ... and {len(students_needing_fix) - 10} more")
    click.echo()

    # Step 2: Get all StudentTeacher associations for these students
    click.echo("Step 2: Analyzing StudentTeacher associations...")

    associations_to_create = []  # (student, teacher_id, block)
    student_ids_needing_fix = [student.id for student in students_needing_fix]

    # Batch query: get all StudentTeacher associations for students needing fix
    all_student_teachers = StudentTeacher.query.filter(
        StudentTeacher.student_id.in_(student_ids_needing_fix)
    ).all()

    # Build a map of student_id -> list of StudentTeacher records
    student_teacher_map = {}
    for st in all_student_teachers:
        if st.student_id not in student_teacher_map:
            student_teacher_map[st.student_id] = []
        student_teacher_map[st.student_id].append(st)

    # Batch query: get all existing TeacherBlock entries for these students
    existing_teacher_blocks = TeacherBlock.query.filter(
        TeacherBlock.student_id.in_(student_ids_needing_fix)
    ).all()

    # Build a set of (teacher_id, block, student_id) for existing TeacherBlocks
    existing_tb_set = set(
        (tb.teacher_id, tb.block, tb.student_id) for tb in existing_teacher_blocks
    )

    for student in students_needing_fix:
        # Get all teachers this student is linked to from the preloaded map
        student_teachers = student_teacher_map.get(student.id, [])

        if not student_teachers:
            click.echo(f"⚠ Warning: Student {student.full_name} (ID: {student.id}) has no StudentTeacher associations")
            continue

        # For each teacher association, we need to create a TeacherBlock
        # The student's block field might contain multiple blocks (comma-separated)
        student_blocks = [b.strip().upper() for b in student.block.split(',') if b.strip()]

        for st in student_teachers:
            # For simplicity, use the first block if multiple blocks exist
            # In a multi-period scenario, you might need more sophisticated logic
            block = student_blocks[0] if student_blocks else 'A'

            # Check if TeacherBlock already exists for this combination using preloaded set
            if (st.admin_id, block, student.id) not in existing_tb_set:
                associations_to_create.append((student, st.admin_id, block))

    click.echo(f"Need to create {len(associations_to_create)} TeacherBlock entries")
    click.echo()

    # Step 3: Group by (teacher_id, block) for join code generation
    click.echo("Step 3: Grouping by teacher and block for join code generation...")

    groups = {}  # (teacher_id, block) -> [(student, teacher_id, block), ...]
    for association in associations_to_create:
        student, teacher_id, block = association
        key = (teacher_id, block)
        if key not in groups:
            groups[key] = []
        groups[key].append(association)

    click.echo(f"Found {len(groups)} unique teacher-block combinations")
    click.echo()

    # Step 4: Create TeacherBlock entries with join codes
    click.echo("Step 4: Creating TeacherBlock entries...")

    teacher_blocks_created = 0
    join_codes_by_teacher_block = {}

    # Preload existing join codes for all teacher-block combinations to avoid N+1 queries
    teacher_ids = list(set(tid for tid, _ in groups.keys()))
    existing_join_codes_map = {}
    if teacher_ids:
        existing_tbs = TeacherBlock.query.filter(
            TeacherBlock.teacher_id.in_(teacher_ids),
            TeacherBlock.join_code.isnot(None),
            TeacherBlock.join_code != ''
        ).all()
        for tb in existing_tbs:
            existing_join_codes_map[(tb.teacher_id, tb.block)] = tb.join_code

    # Preload all existing join codes into a set for uniqueness checking
    # Note: We fetch all join codes (not just for these teachers) because new join codes
    # must be globally unique across all teachers
    existing_join_code_set = set(
        tb.join_code for tb in TeacherBlock.query.filter(
            TeacherBlock.join_code.isnot(None)
        ).with_entities(TeacherBlock.join_code).all()
    )

    for (teacher_id, block), associations in groups.items():
        # Check if this teacher-block already has a join code (from preloaded map)
        if (teacher_id, block) in existing_join_codes_map:
            join_code = existing_join_codes_map[(teacher_id, block)]
            click.echo(f"  → Reusing existing join code {join_code} for teacher {teacher_id}, block {block}")
        else:
            # Generate new unique join code with bounded retries
            join_code = None
            for _ in range(MAX_JOIN_CODE_RETRIES):
                candidate = generate_join_code()
                # Check uniqueness using preloaded set
                if candidate not in existing_join_code_set:
                    join_code = candidate
                    existing_join_code_set.add(candidate)  # Track newly generated codes
                    break

            if not join_code:
                # Fallback to timestamp-based code if unable to generate unique code
                # Format: B + block_initial + timestamp_suffix (e.g., "BA0123" for block "A")
                block_initial = block[:FALLBACK_BLOCK_PREFIX_LENGTH].ljust(FALLBACK_BLOCK_PREFIX_LENGTH, 'X')
                timestamp_suffix = int(time.time()) % FALLBACK_CODE_MODULO
                join_code = f"B{block_initial}{timestamp_suffix:04d}"
                click.echo(
                    f"  ⚠ Failed to generate unique join code after {MAX_JOIN_CODE_RETRIES} attempts. "
                    f"Using fallback code {join_code} for teacher {teacher_id}, block {block}"
                )
            else:
                click.echo(f"  → Generated new join code {join_code} for teacher {teacher_id}, block {block}")

        join_codes_by_teacher_block[(teacher_id, block)] = join_code

        # Create TeacherBlock entry for each student in this group
        for assoc_student, assoc_teacher_id, assoc_block in associations:
            # Verify student has required fields
            if not assoc_student.salt or not assoc_student.first_half_hash:
                click.echo(f"    ⚠ Skipping {assoc_student.full_name} - missing salt or hash fields")
                continue

            # Create claimed TeacherBlock entry
            tb = TeacherBlock(
                teacher_id=assoc_teacher_id,
                block=assoc_block,
                first_name=assoc_student.first_name,
                last_initial=assoc_student.last_initial,
                last_name_hash_by_part=assoc_student.last_name_hash_by_part or [],
                dob_sum=assoc_student.dob_sum or 0,
                salt=assoc_student.salt,
                first_half_hash=assoc_student.first_half_hash,
                join_code=join_code,
                is_claimed=True,  # Mark as claimed since student already has account
                student_id=assoc_student.id,  # Link to existing student
                claimed_at=datetime.utcnow()
            )
            db.session.add(tb)
            teacher_blocks_created += 1
            click.echo(
                f"    ✓ Created TeacherBlock for {assoc_student.full_name} "
                f"(teacher {assoc_teacher_id}, block {assoc_block})"
            )

    click.echo(f"Created {teacher_blocks_created} TeacherBlock entries")
    click.echo()

    # Step 5: Commit changes
    click.echo("Step 5: Committing changes to database...")
    try:
        db.session.commit()
        click.echo("✓ All changes committed successfully!")
        click.echo()

        # Summary
        click.echo("=" * 70)
        click.echo("FIX SUMMARY")
        click.echo("=" * 70)
        click.echo(f"Students analyzed: {len(students_with_setup)}")
        click.echo(f"Students needing fix: {len(students_needing_fix)}")
        click.echo(f"TeacherBlock entries created: {teacher_blocks_created}")
        click.echo(f"Unique teacher-block combinations: {len(groups)}")
        click.echo()

        if join_codes_by_teacher_block:
            click.echo("Join codes by teacher and block:")
            for (teacher_id, block), code in sorted(join_codes_by_teacher_block.items()):
                click.echo(f"  Teacher {teacher_id}, Block {block}: {code}")
            click.echo()

        click.echo("✓ Fix complete! Teachers should now be able to see their rosters.")
        click.echo()

        # Verification - use batch query to avoid N+1 queries
        click.echo("Verifying fix...")
        student_ids = [s.id for s in students_needing_fix]
        claimed_student_ids = set(
            tb.student_id for tb in TeacherBlock.query.filter(
                TeacherBlock.student_id.in_(student_ids),
                TeacherBlock.is_claimed.is_(True)
            ).all()
        )
        students_still_missing = [
            s for s in students_needing_fix
            if s.id not in claimed_student_ids
        ]

        if students_still_missing:
            click.echo(f"⚠ Warning: {len(students_still_missing)} students still missing TeacherBlock:")
            for student in students_still_missing[:10]:
                click.echo(f"  - {student.full_name} (ID: {student.id})")
        else:
            click.echo("✓ Verification passed! All students now have TeacherBlock entries.")
        click.echo()

    except Exception as e:
        db.session.rollback()
        click.echo(f"\n✗ Error during commit: {str(e)}", err=True)
        import traceback
        traceback.print_exc()
        raise click.Abort()


# Placeholder constant for legacy entries that should be skipped
LEGACY_PLACEHOLDER_FIRST_NAME = "__JOIN_CODE_PLACEHOLDER__"


@click.command('repair-teacher-block-hashes')
@click.option('--dry-run', is_flag=True, help='Preview changes without modifying the database')
def repair_teacher_block_hashes_command(dry_run):
    """
    Repair TeacherBlock entries with incorrectly computed first_half_hash values.

    This command:
    1. Finds all TeacherBlock entries
    2. Checks if first_half_hash matches the correct formula: hash_hmac(f"{last_initial}{dob_sum}".encode(), salt)
    3. Fixes entries where the hash doesn't match
    4. Skips placeholder entries

    Use --dry-run to preview changes before applying them.
    """
    click.echo("=" * 70)
    click.echo("TEACHER BLOCK HASH REPAIR")
    click.echo("=" * 70)
    click.echo()

    if dry_run:
        click.echo("🔍 DRY RUN MODE - No changes will be made to the database")
        click.echo()

    # Step 1: Find all TeacherBlock entries
    click.echo("Step 1: Finding all TeacherBlock entries...")

    all_teacher_blocks = TeacherBlock.query.all()

    if not all_teacher_blocks:
        click.echo("✓ No TeacherBlock entries found!")
        return

    click.echo(f"Found {len(all_teacher_blocks)} TeacherBlock entries to check")
    click.echo()

    # Step 2: Check and fix each entry
    click.echo("Step 2: Checking and repairing hashes...")
    click.echo()

    fixed_count = 0
    skipped_count = 0
    error_count = 0
    already_correct_count = 0

    for tb in all_teacher_blocks:
        # Skip placeholder entries
        if tb.first_name == LEGACY_PLACEHOLDER_FIRST_NAME:
            skipped_count += 1
            if dry_run:
                click.echo(f"  ⊙ SKIP: TeacherBlock #{tb.id} (placeholder entry)")
            continue

        # Skip entries without required fields
        if not tb.salt or not tb.last_initial:
            error_count += 1
            click.echo(f"  ✗ ERROR: TeacherBlock #{tb.id} missing salt or last_initial")
            continue

        # Compute the correct hash
        try:
            credential = f"{tb.last_initial}{tb.dob_sum or 0}"
            correct_hash = hash_hmac(credential.encode(), tb.salt)
        except Exception as e:
            error_count += 1
            click.echo(f"  ✗ ERROR: TeacherBlock #{tb.id} - Failed to compute hash: {e}")
            continue

        # Check if hash needs to be fixed
        if tb.first_half_hash == correct_hash:
            already_correct_count += 1
            continue

        # Fix needed
        fixed_count += 1
        status_str = "claimed" if tb.is_claimed else "unclaimed"
        click.echo(f"  → FIX: TeacherBlock #{tb.id} ({tb.first_name} {tb.last_initial}., "
                   f"block={tb.block}, {status_str})")
        if dry_run:
            click.echo(f"         Current:  {tb.first_half_hash[:16]}...")
            click.echo(f"         Correct:  {correct_hash[:16]}...")
        else:
            tb.first_half_hash = correct_hash

    click.echo()

    # Step 3: Commit changes if not dry run
    if not dry_run and fixed_count > 0:
        click.echo("Step 3: Committing changes to database...")
        try:
            db.session.commit()
            click.echo("✓ All changes committed successfully!")
        except Exception as e:
            db.session.rollback()
            click.echo(f"✗ Error during commit: {str(e)}", err=True)
            import traceback
            traceback.print_exc()
            raise click.Abort()
    elif dry_run:
        click.echo("Step 3: Skipped (dry-run mode)")
    else:
        click.echo("Step 3: Skipped (no changes needed)")

    click.echo()

    # Summary
    click.echo("=" * 70)
    click.echo("REPAIR SUMMARY")
    click.echo("=" * 70)
    click.echo(f"Total entries checked: {len(all_teacher_blocks)}")
    click.echo(f"Already correct:       {already_correct_count}")
    click.echo(f"Fixed:                 {fixed_count}")
    click.echo(f"Skipped (placeholders):{skipped_count}")
    click.echo(f"Errors:                {error_count}")
    click.echo()

    if dry_run:
        if fixed_count > 0:
            click.echo("To apply these fixes, run:")
            click.echo("  flask repair-teacher-block-hashes")
        else:
            click.echo("✓ All hashes are correct! No fixes needed.")
    else:
        if fixed_count > 0:
            click.echo(f"✓ Repair complete! Fixed {fixed_count} entries.")
        else:
            click.echo("✓ All hashes were already correct! No changes made.")


def init_app(app):
    """Register CLI commands with Flask app."""
    app.cli.add_command(migrate_legacy_students_command)
    app.cli.add_command(fix_missing_teacher_blocks_command)
    app.cli.add_command(repair_teacher_block_hashes_command)
