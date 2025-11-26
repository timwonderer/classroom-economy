"""
Flask CLI commands for database operations and migrations.
"""

import click
from datetime import datetime

from app.extensions import db
from app.models import Student, StudentTeacher, TeacherBlock
from app.utils.join_code import generate_join_code


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

    legacy_students = []
    for student in all_students_with_teacher_id:
        # Check if StudentTeacher record exists
        has_student_teacher = StudentTeacher.query.filter_by(
            student_id=student.id,
            admin_id=student.teacher_id
        ).first()

        if not has_student_teacher:
            legacy_students.append(student)

    if not legacy_students:
        click.echo("✓ No legacy students found! All students are already migrated.")
        return

    click.echo(f"Found {len(legacy_students)} legacy students to migrate")
    click.echo()

    # Step 2: Create StudentTeacher associations
    click.echo("Step 2: Creating StudentTeacher associations...")
    student_teacher_created = 0

    for student in legacy_students:
        st = StudentTeacher(
            student_id=student.id,
            admin_id=student.teacher_id,
            created_at=datetime.utcnow()
        )
        db.session.add(st)
        student_teacher_created += 1
        click.echo(f"  ✓ Created StudentTeacher for {student.full_name} (ID: {student.id})")

    click.echo(f"Created {student_teacher_created} StudentTeacher associations")
    click.echo()

    # Step 3: Group students by (teacher_id, block) for join code generation
    click.echo("Step 3: Grouping students by teacher and block...")
    groups = {}
    for student in legacy_students:
        key = (student.teacher_id, student.block)
        if key not in groups:
            groups[key] = []
        groups[key].append(student)

    click.echo(f"Found {len(groups)} unique teacher-block combinations")
    click.echo()

    # Step 4: Generate join codes and create TeacherBlock entries
    click.echo("Step 4: Creating TeacherBlock entries...")
    teacher_blocks_created = 0
    join_codes_by_teacher_block = {}

    for (teacher_id, block), students in groups.items():
        # Check if this teacher-block already has a join code
        existing_tb = TeacherBlock.query.filter_by(
            teacher_id=teacher_id,
            block=block
        ).filter(
            TeacherBlock.join_code.isnot(None),
            TeacherBlock.join_code != ''
        ).first()

        if existing_tb:
            join_code = existing_tb.join_code
            click.echo(f"  → Reusing existing join code {join_code} for teacher {teacher_id}, block {block}")
        else:
            # Generate new unique join code
            max_attempts = 100
            join_code = None
            for _ in range(max_attempts):
                candidate = generate_join_code()
                # Ensure uniqueness across all teachers
                if not TeacherBlock.query.filter_by(join_code=candidate).first():
                    join_code = candidate
                    break

            if not join_code:
                click.echo(f"  ✗ Failed to generate unique join code after {max_attempts} attempts", err=True)
                continue

            click.echo(f"  → Generated new join code {join_code} for teacher {teacher_id}, block {block}")

        join_codes_by_teacher_block[(teacher_id, block)] = join_code

        # Create TeacherBlock entry for each student in this group
        for student in students:
            # Check if TeacherBlock already exists for this student
            existing_seat = TeacherBlock.query.filter_by(
                teacher_id=teacher_id,
                block=block,
                student_id=student.id
            ).first()

            if existing_seat:
                click.echo(f"    ⊙ TeacherBlock already exists for {student.full_name}, skipping")
                continue

            # Create new TeacherBlock entry using student's existing credentials
            tb = TeacherBlock(
                teacher_id=teacher_id,
                block=block,
                first_name=student.first_name,
                last_initial=student.last_initial,
                last_name_hash_by_part=student.last_name_hash_by_part or [],
                dob_sum=student.dob_sum or 0,
                salt=student.salt,
                first_half_hash=student.first_half_hash or '',
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
        click.echo(f"Legacy students migrated: {len(legacy_students)}")
        click.echo(f"StudentTeacher associations created: {student_teacher_created}")
        click.echo(f"TeacherBlock entries created: {teacher_blocks_created}")
        click.echo(f"Unique teacher-block combinations: {len(groups)}")
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

        still_legacy = []
        for student in remaining_legacy:
            has_st = StudentTeacher.query.filter_by(
                student_id=student.id,
                admin_id=student.teacher_id
            ).first()
            if not has_st:
                still_legacy.append(student)

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

    students_needing_fix = []
    for student in students_with_setup:
        # Check if student has a claimed TeacherBlock
        claimed_tb = TeacherBlock.query.filter_by(
            student_id=student.id,
            is_claimed=True
        ).first()

        if not claimed_tb:
            students_needing_fix.append(student)

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

    for student in students_needing_fix:
        # Get all teachers this student is linked to
        student_teachers = StudentTeacher.query.filter_by(student_id=student.id).all()

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

            # Check if TeacherBlock already exists for this combination
            existing_tb = TeacherBlock.query.filter_by(
                teacher_id=st.admin_id,
                block=block,
                student_id=student.id
            ).first()

            if not existing_tb:
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

    for (teacher_id, block), associations in groups.items():
        # Check if this teacher-block already has a join code
        existing_tb = TeacherBlock.query.filter_by(
            teacher_id=teacher_id,
            block=block
        ).filter(
            TeacherBlock.join_code.isnot(None),
            TeacherBlock.join_code != ''
        ).first()

        if existing_tb:
            join_code = existing_tb.join_code
            click.echo(f"  → Reusing existing join code {join_code} for teacher {teacher_id}, block {block}")
        else:
            # Generate new unique join code
            max_attempts = 100
            join_code = None
            for _ in range(max_attempts):
                candidate = generate_join_code()
                # Ensure uniqueness across all teachers
                if not TeacherBlock.query.filter_by(join_code=candidate).first():
                    join_code = candidate
                    break

            if not join_code:
                click.echo(f"  ✗ Failed to generate unique join code after {max_attempts} attempts", err=True)
                continue

            click.echo(f"  → Generated new join code {join_code} for teacher {teacher_id}, block {block}")

        join_codes_by_teacher_block[(teacher_id, block)] = join_code

        # Create TeacherBlock entry for each student in this group
        for student, teacher_id, block in associations:
            # Verify student has required fields
            if not student.salt or not student.first_half_hash:
                click.echo(f"    ⚠ Skipping {student.full_name} - missing salt or hash fields")
                continue

            # Create claimed TeacherBlock entry
            tb = TeacherBlock(
                teacher_id=teacher_id,
                block=block,
                first_name=student.first_name,
                last_initial=student.last_initial,
                last_name_hash_by_part=student.last_name_hash_by_part or [],
                dob_sum=student.dob_sum or 0,
                salt=student.salt,
                first_half_hash=student.first_half_hash,
                join_code=join_code,
                is_claimed=True,  # Mark as claimed since student already has account
                student_id=student.id,  # Link to existing student
                claimed_at=datetime.utcnow()
            )
            db.session.add(tb)
            teacher_blocks_created += 1
            click.echo(f"    ✓ Created TeacherBlock for {student.full_name} (teacher {teacher_id}, block {block})")

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

        # Verification
        click.echo("Verifying fix...")
        students_still_missing = []
        for student in students_needing_fix:
            claimed_tb = TeacherBlock.query.filter_by(
                student_id=student.id,
                is_claimed=True
            ).first()

            if not claimed_tb:
                students_still_missing.append(student)

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


def init_app(app):
    """Register CLI commands with Flask app."""
    app.cli.add_command(migrate_legacy_students_command)
    app.cli.add_command(fix_missing_teacher_blocks_command)
