#!/usr/bin/env python3
"""
Cleanup duplicate students using Flask shell.
This script uses the existing Flask database connection from your app config.

IMPORTANT: This script migrates all related records (transactions, tap events, etc.)
from duplicate students to the student being kept, then deletes duplicates.

Usage:
    python cleanup_duplicates_flask.py --list     # Show duplicates
    python cleanup_duplicates_flask.py --delete   # Delete duplicates (with migration)
"""

import sys
from app import create_app
from app.extensions import db
from app.models import (
    Student, Transaction, TapEvent, HallPassLog, StudentItem,
    RentPayment, RentWaiver, StudentInsurance, InsuranceClaim
)
from collections import defaultdict

def list_duplicates():
    """List all duplicate students."""
    app = create_app()

    with app.app_context():
        students = Student.query.order_by(Student.id).all()

        # Group by (first_name, last_initial, block)
        groups = defaultdict(list)
        for student in students:
            if student.block:
                key = (student.first_name, student.last_initial, student.block)
                groups[key].append(student)

        duplicates = {k: v for k, v in groups.items() if len(v) > 1}

        if not duplicates:
            print("✓ No duplicates found!")
            return

        print(f"\n⚠️  Found {len(duplicates)} sets of duplicate students:")
        print("=" * 100)

        total_to_delete = 0
        total_records_to_migrate = 0

        for (first_name, last_initial, block), students_list in sorted(duplicates.items()):
            students_list.sort(key=lambda s: s.id)

            print(f"\n{first_name} {last_initial}. in Block {block}:")
            print(f"  Found {len(students_list)} copies (will keep oldest, delete {len(students_list)-1})")

            keep = students_list[0]
            print(f"  ✓ KEEP: ID={keep.id}, Setup={keep.has_completed_setup}, "
                  f"Checking=${keep.checking_balance:.2f}, Savings=${keep.savings_balance:.2f}")

            for dup in students_list[1:]:
                # Count related records that will be migrated
                txn_count = Transaction.query.filter_by(student_id=dup.id).count()
                tap_count = TapEvent.query.filter_by(student_id=dup.id).count()
                hall_count = HallPassLog.query.filter_by(student_id=dup.id).count()
                item_count = StudentItem.query.filter_by(student_id=dup.id).count()
                rent_count = RentPayment.query.filter_by(student_id=dup.id).count()
                insurance_count = StudentInsurance.query.filter_by(student_id=dup.id).count()
                claim_count = InsuranceClaim.query.filter_by(student_id=dup.id).count()

                total_records = txn_count + tap_count + hall_count + item_count + rent_count + insurance_count + claim_count
                total_records_to_migrate += total_records

                print(f"  ✗ DELETE: ID={dup.id}, Setup={dup.has_completed_setup}, "
                      f"Checking=${dup.checking_balance:.2f}, Savings=${dup.savings_balance:.2f}")
                if total_records > 0:
                    print(f"    → Will migrate {total_records} related records "
                          f"(txns:{txn_count}, taps:{tap_count}, halls:{hall_count}, items:{item_count}, "
                          f"rent:{rent_count}, ins:{insurance_count}, claims:{claim_count})")

                total_to_delete += 1

        print("\n" + "=" * 100)
        print(f"\nTotal: {total_to_delete} duplicate records will be deleted")
        print(f"Total: {total_records_to_migrate} related records will be migrated to kept students")
        print("\nTo delete these duplicates, run:")
        print("  python cleanup_duplicates_flask.py --delete")


def delete_duplicates():
    """Delete duplicate students, keeping the oldest record and migrating all data."""
    app = create_app()

    with app.app_context():
        students = Student.query.order_by(Student.id).all()

        # Group by (first_name, last_initial, block)
        groups = defaultdict(list)
        for student in students:
            if student.block:
                key = (student.first_name, student.last_initial, student.block)
                groups[key].append(student)

        duplicates = {k: v for k, v in groups.items() if len(v) > 1}

        if not duplicates:
            print("✓ No duplicates found!")
            return

        print(f"\n⚠️  Deleting duplicates (migrating data to oldest record for each student)...\n")

        deleted_count = 0
        migrated_count = 0

        for (first_name, last_initial, block), students_list in sorted(duplicates.items()):
            students_list.sort(key=lambda s: s.id)

            keep = students_list[0]
            to_delete = students_list[1:]

            print(f"{first_name} {last_initial}. in Block {block}:")
            print(f"  KEEPING: ID={keep.id}")

            for dup in to_delete:
                print(f"  MIGRATING data from ID={dup.id} to ID={keep.id}...")

                # Migrate all related records
                migrate_count = 0

                # 1. Transactions
                for txn in Transaction.query.filter_by(student_id=dup.id).all():
                    txn.student_id = keep.id
                    migrate_count += 1

                # 2. Tap Events
                for tap in TapEvent.query.filter_by(student_id=dup.id).all():
                    tap.student_id = keep.id
                    migrate_count += 1

                # 3. Hall Pass Logs
                for hall in HallPassLog.query.filter_by(student_id=dup.id).all():
                    hall.student_id = keep.id
                    migrate_count += 1

                # 4. Student Items
                for item in StudentItem.query.filter_by(student_id=dup.id).all():
                    item.student_id = keep.id
                    migrate_count += 1

                # 5. Rent Payments
                for rent in RentPayment.query.filter_by(student_id=dup.id).all():
                    rent.student_id = keep.id
                    migrate_count += 1

                # 6. Rent Waivers
                for waiver in RentWaiver.query.filter_by(student_id=dup.id).all():
                    waiver.student_id = keep.id
                    migrate_count += 1

                # 7. Student Insurance
                for ins in StudentInsurance.query.filter_by(student_id=dup.id).all():
                    ins.student_id = keep.id
                    migrate_count += 1

                # 8. Insurance Claims
                for claim in InsuranceClaim.query.filter_by(student_id=dup.id).all():
                    claim.student_id = keep.id
                    migrate_count += 1

                if migrate_count > 0:
                    print(f"    → Migrated {migrate_count} records")

                migrated_count += migrate_count

                # Now safe to delete the duplicate
                print(f"  DELETING: ID={dup.id}")
                db.session.delete(dup)
                deleted_count += 1

        # Commit all changes
        db.session.commit()

        print(f"\n{'=' * 100}")
        print(f"✓ Successfully deleted {deleted_count} duplicate student records!")
        print(f"✓ Successfully migrated {migrated_count} related records!")
        print(f"✓ Database cleanup complete!")

        # Show final counts
        print(f"\nFinal student counts by block:")
        final_counts = db.session.query(
            Student.block,
            db.func.count(Student.id)
        ).filter(
            Student.block.isnot(None)
        ).group_by(Student.block).order_by(Student.block).all()

        for block, count in final_counts:
            print(f"  Block {block}: {count} students")


if __name__ == "__main__":
    if "--delete" in sys.argv:
        print("⚠️  WARNING: This will permanently delete duplicate student records!")
        print("⚠️  All related data will be migrated to the student being kept.")
        print("Press Ctrl+C within 3 seconds to cancel...")
        import time
        try:
            time.sleep(3)
        except KeyboardInterrupt:
            print("\n\nCancelled.")
            sys.exit(0)
        print("\nProceeding with deletion and migration...\n")
        delete_duplicates()
    else:
        list_duplicates()
