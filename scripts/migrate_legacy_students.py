#!/usr/bin/env python3
"""
Migrate legacy students to the new association system.

This script:
1. Finds all legacy students (have teacher_id but no StudentTeacher record)
2. Creates StudentTeacher many-to-many associations
3. Creates TeacherBlock entries (marked as claimed) for each legacy student
4. Generates stable join codes per teacher-block combination

USAGE:
    python3 scripts/migrate_legacy_students.py

NOTE: Run this script from the project root directory.
      Requires environment variables to be set (DATABASE_URL, etc.)

WHAT IT DOES:
    1. Finds all students with teacher_id set but missing StudentTeacher records
    2. Creates StudentTeacher(student_id, admin_id) for each legacy student
    3. Creates TeacherBlock entries marked as claimed, using existing student credentials
    4. Groups students by (teacher_id, block) and assigns shared join codes
    5. Commits changes to database
"""

import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime

from app import create_app
from app.extensions import db
from app.models import Student, StudentTeacher, TeacherBlock
from app.utils.join_code import generate_join_code
from app.routes.admin import MAX_JOIN_CODE_RETRIES


def migrate_legacy_students():
    """
    Migrate legacy students to the new system with StudentTeacher associations
    and proper TeacherBlock entries.
    """
    app = create_app()

    with app.app_context():
        print("=" * 70)
        print("LEGACY STUDENT MIGRATION")
        print("=" * 70)
        print()

        # Step 1: Find all legacy students
        # Legacy = has teacher_id set but no StudentTeacher record
        print("Step 1: Finding legacy students...")

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
            print("✓ No legacy students found! All students are already migrated.")
            return

        print(f"Found {len(legacy_students)} legacy students to migrate")
        print()

        # Step 2: Create StudentTeacher associations
        print("Step 2: Creating StudentTeacher associations...")
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
                print(f"  ✓ Created StudentTeacher for {student.full_name} (ID: {student.id})")
            else:
                print(f"  ⊙ StudentTeacher already exists for {student.full_name}, skipping")

        print(f"Created {student_teacher_created} StudentTeacher associations")
        print()

        # Step 3: Group students by (teacher_id, block) for join code generation
        print("Step 3: Grouping students by teacher and block...")
        groups = {}
        for student in legacy_students:
            # Normalize block name for consistent grouping
            normalized_block = student.block.strip().upper() if student.block else ''
            key = (student.teacher_id, normalized_block)
            if key not in groups:
                groups[key] = []
            groups[key].append(student)

        print(f"Found {len(groups)} unique teacher-block combinations")
        print()

        # Step 4: Generate join codes and create TeacherBlock entries
        print("Step 4: Creating TeacherBlock entries...")
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
                print(f"  → Reusing existing join code {join_code} for teacher {teacher_id}, block {block}")
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
                    print(f"  ✗ Failed to generate unique join code after {max_attempts} attempts for teacher {teacher_id}, block {block}")
                    # Mark all students in this group as skipped
                    skipped_students.extend(students)
                    continue

                print(f"  → Generated new join code {join_code} for teacher {teacher_id}, block {block}")

            join_codes_by_teacher_block[(teacher_id, block)] = join_code

            # Create TeacherBlock entry for each student in this group
            for student in students:
                # Check if TeacherBlock already exists using preloaded set
                if (teacher_id, block, student.id) in existing_seats:
                    print(f"    ⊙ TeacherBlock already exists for {student.full_name}, skipping")
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
                print(f"    ✓ Created TeacherBlock for {student.full_name} (claimed)")

        print(f"Created {teacher_blocks_created} TeacherBlock entries")
        print()

        # Step 5: Commit all changes
        print("Step 5: Committing changes to database...")
        try:
            db.session.commit()
            print("✓ All changes committed successfully!")
            print()

            # Summary
            print("=" * 70)
            print("MIGRATION SUMMARY")
            print("=" * 70)
            print(f"Legacy students found: {len(legacy_students)}")
            print(f"StudentTeacher associations created: {student_teacher_created}")
            print(f"TeacherBlock entries created: {teacher_blocks_created}")
            print(f"Unique teacher-block combinations: {len(groups)}")
            if skipped_students:
                print(f"Students skipped due to errors: {len(skipped_students)}")
            print()

            if join_codes_by_teacher_block:
                print("Join codes by teacher and block:")
                for (teacher_id, block), code in sorted(join_codes_by_teacher_block.items()):
                    print(f"  Teacher {teacher_id}, Block {block}: {code}")
                print()

            print("✓ Migration complete! All legacy students now use the new system.")
            print()

            # Verification
            print("Verifying migration...")
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
                print(f"⚠ Warning: {len(still_legacy)} students still need migration")
                for student in still_legacy:
                    print(f"  - {student.full_name} (ID: {student.id})")
            else:
                print("✓ Verification passed! No remaining legacy students.")

        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Error during commit: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    migrate_legacy_students()
