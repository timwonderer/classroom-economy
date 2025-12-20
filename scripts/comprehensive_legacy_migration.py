#!/usr/bin/env python3
"""
Comprehensive Legacy Account Migration Script

This script performs a complete migration of all legacy accounts and NULL join_code
data to the new multi-tenancy system. It combines and extends the functionality
of multiple individual migration scripts.

WHAT THIS SCRIPT DOES:
1. Migrates legacy students (with teacher_id but missing StudentTeacher/TeacherBlock records)
2. Backfills join_codes for all TeacherBlock entries
3. Backfills join_codes for all transaction-related tables:
   - transactions
   - tap_events (usually already handled by migration aa5697e97c94)
   - student_items
   - student_insurance
   - hall_pass_logs
   - rent_payments
4. Verifies data integrity after migration

USAGE:
    python3 scripts/comprehensive_legacy_migration.py [--dry-run]

    --dry-run: Show what would be migrated without making changes

REQUIREMENTS:
    - Run from project root directory
    - DATABASE_URL and other environment variables must be set
    - Database backup recommended before running

SAFETY:
    - Idempotent: Safe to run multiple times
    - Batch processing for performance
    - Comprehensive logging and verification
    - Rollback on errors

AUTHOR: Claude (AI Assistant)
DATE: 2025-12-19
"""

import sys
import os
from collections import defaultdict
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import or_, and_, text
from app import create_app
from app.extensions import db
from app.models import (
    Student, Admin, StudentTeacher, TeacherBlock, StudentBlock,
    Transaction, TapEvent
)
from app.utils.join_code import generate_join_code
from app.routes.admin import MAX_JOIN_CODE_RETRIES


class MigrationStats:
    """Track migration statistics."""
    def __init__(self):
        self.legacy_students_found = 0
        self.student_teacher_created = 0
        self.teacher_blocks_created = 0
        self.teacher_blocks_updated = 0
        self.transactions_backfilled = 0
        self.tap_events_backfilled = 0
        self.student_items_backfilled = 0
        self.student_insurance_backfilled = 0
        self.hall_pass_logs_backfilled = 0
        self.rent_payments_backfilled = 0
        self.join_codes_generated = 0
        self.join_codes_reused = 0
        self.errors = []
        self.warnings = []

    def print_summary(self):
        """Print migration summary."""
        print("\n" + "=" * 80)
        print("MIGRATION SUMMARY")
        print("=" * 80)
        print(f"\nLegacy Account Migration:")
        print(f"  Legacy students found: {self.legacy_students_found}")
        print(f"  StudentTeacher associations created: {self.student_teacher_created}")
        print(f"  TeacherBlock entries created: {self.teacher_blocks_created}")
        print(f"  TeacherBlock entries updated: {self.teacher_blocks_updated}")
        print(f"\nJoin Code Management:")
        print(f"  New join codes generated: {self.join_codes_generated}")
        print(f"  Existing join codes reused: {self.join_codes_reused}")
        print(f"\nData Backfill:")
        print(f"  Transactions backfilled: {self.transactions_backfilled}")
        print(f"  Tap events backfilled: {self.tap_events_backfilled}")
        print(f"  Student items backfilled: {self.student_items_backfilled}")
        print(f"  Student insurance backfilled: {self.student_insurance_backfilled}")
        print(f"  Hall pass logs backfilled: {self.hall_pass_logs_backfilled}")
        print(f"  Rent payments backfilled: {self.rent_payments_backfilled}")

        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print("\n✅ No errors encountered!")

        print("=" * 80 + "\n")


def migrate_legacy_students(stats, dry_run=False):
    """
    Migrate legacy students to the new system.

    Creates StudentTeacher associations and TeacherBlock entries for
    students that have teacher_id but missing proper associations.
    """
    print("\n" + "=" * 80)
    print("PHASE 1: LEGACY STUDENT MIGRATION")
    print("=" * 80 + "\n")

    # Find all students with teacher_id
    all_students_with_teacher_id = Student.query.filter(
        Student.teacher_id.isnot(None)
    ).all()

    if not all_students_with_teacher_id:
        print("✓ No students with teacher_id found (all are fully migrated)")
        return

    # Batch query: get all existing StudentTeacher associations
    student_ids = [s.id for s in all_students_with_teacher_id]
    existing_associations = set()
    if student_ids:
        existing_associations = set(
            (st.student_id, st.admin_id)
            for st in StudentTeacher.query.filter(
                StudentTeacher.student_id.in_(student_ids)
            ).all()
        )

    # Filter to find legacy students (no StudentTeacher record)
    legacy_students = [
        student for student in all_students_with_teacher_id
        if (student.id, student.teacher_id) not in existing_associations
    ]

    stats.legacy_students_found = len(legacy_students)

    if not legacy_students:
        print("✓ No legacy students found! All students have proper associations.")
        return

    print(f"Found {len(legacy_students)} legacy students to migrate:")
    for student in legacy_students[:10]:  # Show first 10
        print(f"  - {student.full_name} (ID: {student.id}, Teacher: {student.teacher_id}, Block: {student.block})")
    if len(legacy_students) > 10:
        print(f"  ... and {len(legacy_students) - 10} more")
    print()

    if dry_run:
        print("🔍 DRY RUN: Would create StudentTeacher associations and TeacherBlock entries")
        return

    # Create StudentTeacher associations
    print("Creating StudentTeacher associations...")
    for student in legacy_students:
        st = StudentTeacher(
            student_id=student.id,
            admin_id=student.teacher_id,
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(st)
        stats.student_teacher_created += 1
        print(f"  ✓ Created StudentTeacher for {student.full_name}")

    # Group students by (teacher_id, block) for TeacherBlock creation
    print("\nGrouping students by teacher and block...")
    groups = defaultdict(list)
    for student in legacy_students:
        normalized_block = student.block.strip().upper() if student.block else ''
        key = (student.teacher_id, normalized_block)
        groups[key].append(student)

    print(f"Found {len(groups)} unique teacher-block combinations\n")

    # Preload existing join codes
    teacher_ids = list(set(tid for tid, _ in groups.keys()))
    existing_join_codes_map = {}
    if teacher_ids:
        existing_tbs = TeacherBlock.query.filter(
            TeacherBlock.teacher_id.in_(teacher_ids),
            TeacherBlock.join_code.isnot(None),
            TeacherBlock.join_code != ''
        ).all()
        for tb in existing_tbs:
            key = (tb.teacher_id, tb.block.upper() if tb.block else '')
            if key not in existing_join_codes_map:
                existing_join_codes_map[key] = tb.join_code

    # Preload all existing join codes for uniqueness checking
    existing_join_code_set = set(
        tb.join_code for tb in TeacherBlock.query.filter(
            TeacherBlock.join_code.isnot(None)
        ).with_entities(TeacherBlock.join_code).all()
    )

    # Preload existing TeacherBlock seats
    existing_seats = set()
    if teacher_ids:
        seats = TeacherBlock.query.filter(
            TeacherBlock.teacher_id.in_(teacher_ids),
            TeacherBlock.student_id.isnot(None)
        ).all()
        existing_seats = set(
            (tb.teacher_id, tb.block.upper() if tb.block else '', tb.student_id)
            for tb in seats
        )

    # Create TeacherBlock entries
    print("Creating TeacherBlock entries...")
    for (teacher_id, block), students in groups.items():
        # Get or generate join code
        if (teacher_id, block) in existing_join_codes_map:
            join_code = existing_join_codes_map[(teacher_id, block)]
            print(f"  → Reusing join code {join_code} for teacher {teacher_id}, block {block}")
            stats.join_codes_reused += 1
        else:
            # Generate new unique join code
            max_attempts = MAX_JOIN_CODE_RETRIES * 10
            join_code = None
            for _ in range(max_attempts):
                candidate = generate_join_code()
                if candidate not in existing_join_code_set:
                    join_code = candidate
                    existing_join_code_set.add(candidate)
                    break

            if not join_code:
                error_msg = f"Failed to generate unique join code for teacher {teacher_id}, block {block}"
                print(f"  ✗ {error_msg}")
                stats.errors.append(error_msg)
                continue

            print(f"  → Generated join code {join_code} for teacher {teacher_id}, block {block}")
            stats.join_codes_generated += 1

        # Create TeacherBlock for each student
        for student in students:
            seat_key = (teacher_id, block, student.id)
            if seat_key in existing_seats:
                print(f"    ⊙ TeacherBlock exists for {student.full_name}, skipping")
                continue

            tb = TeacherBlock(
                teacher_id=teacher_id,
                block=student.block,  # Use original casing
                first_name=student.first_name,
                last_initial=student.last_initial,
                last_name_hash_by_part=student.last_name_hash_by_part or [],
                dob_sum=student.dob_sum or 0,
                salt=student.salt,
                first_half_hash=student.first_half_hash or '',
                join_code=join_code,
                is_claimed=True,
                student_id=student.id,
                claimed_at=datetime.now(timezone.utc)
            )
            db.session.add(tb)
            stats.teacher_blocks_created += 1
            print(f"    ✓ Created TeacherBlock for {student.full_name}")

    db.session.flush()
    print(f"\n✅ Phase 1 complete: {stats.student_teacher_created} associations, {stats.teacher_blocks_created} blocks created")


def backfill_teacher_block_join_codes(stats, dry_run=False):
    """
    Backfill join codes for TeacherBlock entries that are missing them.
    """
    print("\n" + "=" * 80)
    print("PHASE 2: BACKFILL TEACHERBLOCK JOIN CODES")
    print("=" * 80 + "\n")

    # Find TeacherBlock entries without join codes
    blocks_without_codes = TeacherBlock.query.filter(
        or_(
            TeacherBlock.join_code.is_(None),
            TeacherBlock.join_code == ''
        )
    ).all()

    if not blocks_without_codes:
        print("✓ All TeacherBlock entries have join codes!")
        return

    print(f"Found {len(blocks_without_codes)} TeacherBlock entries without join codes")

    # Group by (teacher_id, block)
    groups = defaultdict(list)
    for tb in blocks_without_codes:
        normalized_block = tb.block.strip().upper() if tb.block else ''
        key = (tb.teacher_id, normalized_block)
        groups[key].append(tb)

    print(f"Grouped into {len(groups)} unique teacher-block combinations\n")

    if dry_run:
        print("🔍 DRY RUN: Would backfill join codes for these TeacherBlock entries")
        for (teacher_id, block), seats in groups.items():
            print(f"  - Teacher {teacher_id}, Block {block}: {len(seats)} seats")
        return

    # Preload existing join codes for these teacher-block combinations
    teacher_ids = list(set(tid for tid, _ in groups.keys()))
    existing_codes_by_group = {}
    if teacher_ids:
        existing_with_codes = TeacherBlock.query.filter(
            TeacherBlock.teacher_id.in_(teacher_ids),
            TeacherBlock.join_code.isnot(None),
            TeacherBlock.join_code != ''
        ).with_entities(TeacherBlock.teacher_id, TeacherBlock.block, TeacherBlock.join_code).all()

        for tid, block_value, join_code in existing_with_codes:
            key = (tid, block_value.strip().upper() if block_value else '')
            if key not in existing_codes_by_group:
                existing_codes_by_group[key] = join_code

    # Preload all join codes for uniqueness checks
    existing_join_code_set = set(
        row[0] for row in TeacherBlock.query.filter(
            TeacherBlock.join_code.isnot(None),
            TeacherBlock.join_code != ''
        ).with_entities(TeacherBlock.join_code).all()
    )

    # Generate and assign join codes
    for (teacher_id, block), seats in groups.items():
        # Check if this teacher-block already has seats with join codes
        if (teacher_id, block) in existing_codes_by_group:
            join_code = existing_codes_by_group[(teacher_id, block)]
            print(f"  → Reusing join code {join_code} for teacher {teacher_id}, block {block}")
            stats.join_codes_reused += 1
        else:
            # Generate new unique join code
            max_attempts = MAX_JOIN_CODE_RETRIES * 10
            join_code = None
            for _ in range(max_attempts):
                candidate = generate_join_code()
                if candidate not in existing_join_code_set:
                    join_code = candidate
                    existing_join_code_set.add(candidate)
                    break

            if not join_code:
                error_msg = f"Failed to generate unique join code for teacher {teacher_id}, block {block}"
                print(f"  ✗ {error_msg}")
                stats.errors.append(error_msg)
                continue

            print(f"  → Generated join code {join_code} for teacher {teacher_id}, block {block}")
            stats.join_codes_generated += 1

        # Assign to all seats in this group
        for seat in seats:
            seat.join_code = join_code
            stats.teacher_blocks_updated += 1

    db.session.flush()
    print(f"\n✅ Phase 2 complete: {stats.teacher_blocks_updated} TeacherBlock entries updated")


def backfill_transaction_join_codes(stats, dry_run=False):
    """
    Backfill join codes for transactions using TeacherBlock mapping.

    Strategy:
    1. For each transaction with NULL join_code
    2. Look up the student's TeacherBlock entry matching (student_id, teacher_id, period)
    3. Use the join_code from that TeacherBlock
    """
    print("\n" + "=" * 80)
    print("PHASE 3: BACKFILL TRANSACTION JOIN CODES")
    print("=" * 80 + "\n")

    # Count transactions without join codes
    null_count = Transaction.query.filter(
        Transaction.join_code.is_(None)
    ).count()

    if null_count == 0:
        print("✓ All transactions have join codes!")
        return

    print(f"Found {null_count} transactions without join codes")

    if dry_run:
        print("🔍 DRY RUN: Would backfill transaction join codes using TeacherBlock mapping")
        return

    warning = (
        "Transaction join_code backfill matches only on student_id; "
        "students with multiple claimed classes may have transactions assigned "
        "to an arbitrary join_code because the transaction table lacks period context."
    )
    print(f"⚠️  {warning}")
    stats.warnings.append(warning)

    # Use SQL for efficient bulk update
    # Match transactions to TeacherBlocks by student_id and period (case-insensitive)
    print("Backfilling transaction join codes...")
    result = db.session.execute(text("""
        UPDATE transaction AS t
        SET join_code = tb.join_code
        FROM teacher_blocks AS tb
        WHERE t.join_code IS NULL
          AND t.student_id = tb.student_id
          AND tb.is_claimed = TRUE
          AND tb.join_code IS NOT NULL
          AND tb.join_code != ''
    """))

    stats.transactions_backfilled = result.rowcount
    db.session.flush()
    print(f"✅ Phase 3 complete: {stats.transactions_backfilled} transactions backfilled")

    # Check for remaining NULL join_codes
    remaining = Transaction.query.filter(
        Transaction.join_code.is_(None)
    ).count()

    if remaining > 0:
        warning = f"{remaining} transactions still have NULL join_code (may be orphaned or test data)"
        print(f"⚠️  {warning}")
        stats.warnings.append(warning)


def backfill_tap_event_join_codes(stats, dry_run=False):
    """
    Backfill join codes for tap events using TeacherBlock mapping.

    Note: Migration aa5697e97c94 may have already handled this.
    """
    print("\n" + "=" * 80)
    print("PHASE 4: BACKFILL TAP EVENT JOIN CODES")
    print("=" * 80 + "\n")

    # Count tap events without join codes
    null_count = TapEvent.query.filter(
        TapEvent.join_code.is_(None)
    ).count()

    if null_count == 0:
        print("✓ All tap events have join codes!")
        return

    print(f"Found {null_count} tap events without join codes")

    if dry_run:
        print("🔍 DRY RUN: Would backfill tap event join codes using TeacherBlock mapping")
        return

    # Use SQL for efficient bulk update
    print("Backfilling tap event join codes...")
    result = db.session.execute(text("""
        UPDATE tap_events AS te
        SET join_code = tb.join_code
        FROM teacher_blocks AS tb
        WHERE te.join_code IS NULL
          AND te.student_id = tb.student_id
          AND UPPER(te.period) = UPPER(tb.block)
          AND tb.is_claimed = TRUE
          AND tb.join_code IS NOT NULL
          AND tb.join_code != ''
    """))

    stats.tap_events_backfilled = result.rowcount
    db.session.flush()
    print(f"✅ Phase 4 complete: {stats.tap_events_backfilled} tap events backfilled")

    # Check for remaining NULL join_codes
    remaining = TapEvent.query.filter(
        TapEvent.join_code.is_(None)
    ).count()

    if remaining > 0:
        warning = f"{remaining} tap events still have NULL join_code"
        print(f"⚠️  {warning}")
        stats.warnings.append(warning)


def backfill_related_tables(stats, dry_run=False):
    """
    Backfill join codes for related tables (student_items, student_insurance, etc.)

    Note: These tables were added in migration b1c2d3e4f5g6.
    We'll use StudentBlock to map students to their join_codes.
    """
    print("\n" + "=" * 80)
    print("PHASE 5: BACKFILL RELATED TABLE JOIN CODES")
    print("=" * 80 + "\n")

    # Check if StudentBlock table exists (it should, but let's be safe)
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()

    related_tables = [
        ('student_items', 'student_items'),
        ('student_insurance', 'student_insurance'),
        ('hall_pass_logs', 'hall_pass_logs'),
        ('rent_payments', 'rent_payments')
    ]

    # Filter to only tables that exist
    existing_tables = [(table, name) for table, name in related_tables if table in tables]

    if not existing_tables:
        print("ℹ️  No related tables found (they may not be in use yet)")
        return

    if dry_run:
        print("🔍 DRY RUN: Would backfill join codes for related tables")
        for table, _ in existing_tables:
            print(f"  - {table}")
        return

    # For each table, backfill using StudentBlock mapping
    for table_name, stat_key in existing_tables:
        print(f"\nBackfilling {table_name}...")

        try:
            # First, try to get count of NULL join_codes
            count_query = text(f"SELECT COUNT(*) FROM {table_name} WHERE join_code IS NULL")
            result = db.session.execute(count_query)
            null_count = result.scalar()

            if null_count == 0:
                print(f"  ✓ All {table_name} records have join codes")
                continue

            print(f"  Found {null_count} records without join codes")

            table_columns = [c['name'] for c in inspector.get_columns(table_name)]
            period_match_clause = ""
            if 'period' in table_columns:
                period_match_clause = "AND UPPER(t.period) = UPPER(sb.period)"
            else:
                stats.warnings.append(
                    f"Backfill for {table_name} is ambiguous for students in multiple classes; using first available join_code."
                )

            # Backfill using StudentBlock relationship
            # Strategy: Match by student_id and period (if period column exists)
            update_query = text(f"""
                UPDATE {table_name} AS t
                SET join_code = (
                    SELECT sb.join_code FROM student_blocks AS sb
                    WHERE t.student_id = sb.student_id {period_match_clause}
                    AND sb.join_code IS NOT NULL AND sb.join_code != ''
                    LIMIT 1
                )
                WHERE t.join_code IS NULL
            """)

            result = db.session.execute(update_query)
            backfilled = result.rowcount

            # Store stats
            if stat_key == 'student_items':
                stats.student_items_backfilled = backfilled
            elif stat_key == 'student_insurance':
                stats.student_insurance_backfilled = backfilled
            elif stat_key == 'hall_pass_logs':
                stats.hall_pass_logs_backfilled = backfilled
            elif stat_key == 'rent_payments':
                stats.rent_payments_backfilled = backfilled

            print(f"  ✓ Backfilled {backfilled} {table_name} records")

            # Check for remaining NULL join_codes
            result = db.session.execute(count_query)
            remaining = result.scalar()

            if remaining > 0:
                warning = f"{remaining} {table_name} records still have NULL join_code"
                print(f"  ⚠️  {warning}")
                stats.warnings.append(warning)

        except Exception as e:
            error = f"Error backfilling {table_name}: {str(e)}"
            print(f"  ✗ {error}")
            stats.errors.append(error)

    db.session.flush()
    print("\n✅ Phase 5 complete")


def verify_migration(stats):
    """
    Verify the migration was successful.
    """
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80 + "\n")

    # Check for remaining legacy students
    print("1. Checking for legacy students...")
    all_students_with_teacher_id = Student.query.filter(
        Student.teacher_id.isnot(None)
    ).all()

    if all_students_with_teacher_id:
        student_ids = [s.id for s in all_students_with_teacher_id]
        existing_associations = set(
            (st.student_id, st.admin_id)
            for st in StudentTeacher.query.filter(
                StudentTeacher.student_id.in_(student_ids)
            ).all()
        )

        still_legacy = [
            student for student in all_students_with_teacher_id
            if (student.id, student.teacher_id) not in existing_associations
        ]

        if still_legacy:
            warning = f"{len(still_legacy)} students still need StudentTeacher associations"
            print(f"  ⚠️  {warning}")
            stats.warnings.append(warning)
            for student in still_legacy[:5]:
                print(f"    - {student.full_name} (ID: {student.id})")
        else:
            print("  ✓ All students have proper StudentTeacher associations")
    else:
        print("  ✓ No students with teacher_id (fully migrated)")

    # Check for TeacherBlocks without join codes
    print("\n2. Checking TeacherBlock join codes...")
    missing_codes = TeacherBlock.query.filter(
        or_(
            TeacherBlock.join_code.is_(None),
            TeacherBlock.join_code == ''
        )
    ).count()

    if missing_codes > 0:
        warning = f"{missing_codes} TeacherBlock entries still missing join codes"
        print(f"  ⚠️  {warning}")
        stats.warnings.append(warning)
    else:
        print("  ✓ All TeacherBlock entries have join codes")

    # Check for transactions without join codes
    print("\n3. Checking transaction join codes...")
    null_transactions = Transaction.query.filter(
        Transaction.join_code.is_(None)
    ).count()

    if null_transactions > 0:
        print(f"  ⚠️  {null_transactions} transactions still have NULL join_code")
    else:
        print("  ✓ All transactions have join codes")

    # Check for tap events without join codes
    print("\n4. Checking tap event join codes...")
    null_tap_events = TapEvent.query.filter(
        TapEvent.join_code.is_(None)
    ).count()

    if null_tap_events > 0:
        print(f"  ⚠️  {null_tap_events} tap events still have NULL join_code")
    else:
        print("  ✓ All tap events have join codes")

    print("\n" + "=" * 80)


def main():
    """Main migration entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Comprehensive legacy account migration')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    args = parser.parse_args()

    app = create_app()
    stats = MigrationStats()

    print("\n" + "=" * 80)
    print("COMPREHENSIVE LEGACY ACCOUNT MIGRATION")
    print("=" * 80)
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    print("=" * 80 + "\n")

    with app.app_context():
        try:
            # Phase 1: Migrate legacy students
            migrate_legacy_students(stats, dry_run=args.dry_run)

            # Phase 2: Backfill TeacherBlock join codes
            backfill_teacher_block_join_codes(stats, dry_run=args.dry_run)

            # Phase 3: Backfill transaction join codes
            backfill_transaction_join_codes(stats, dry_run=args.dry_run)

            # Phase 4: Backfill tap event join codes
            backfill_tap_event_join_codes(stats, dry_run=args.dry_run)

            # Phase 5: Backfill related tables
            backfill_related_tables(stats, dry_run=args.dry_run)

            # Commit all changes
            if not args.dry_run:
                print("\n" + "=" * 80)
                print("COMMITTING CHANGES")
                print("=" * 80 + "\n")
                db.session.commit()
                print("✅ All changes committed successfully!\n")

                # Verify migration
                verify_migration(stats)

            # Print summary
            stats.print_summary()

            if args.dry_run:
                print("ℹ️  This was a dry run. Run without --dry-run to apply changes.")

        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERROR: Migration failed: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    main()
