"""
Flask CLI commands for database operations and migrations.
"""

import click
from flask import current_app
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


def init_app(app):
    """Register CLI commands with Flask app."""
    app.cli.add_command(migrate_legacy_students_command)
