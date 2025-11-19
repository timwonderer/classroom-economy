#!/usr/bin/env python3
"""
Cleanup script to remove duplicate students created due to algorithm bug.

This script identifies and removes duplicate students, keeping the OLDEST record
(the original) and deleting newer duplicates.
"""

from app import create_app
from app.extensions import db
from app.models import Student
from sqlalchemy import func
from collections import defaultdict

def find_duplicates():
    """Find duplicate students (same first_name, last_initial, block)."""
    app = create_app()

    with app.app_context():
        # Get all students
        students = Student.query.order_by(Student.id).all()

        # Group by (first_name, last_initial, block)
        groups = defaultdict(list)
        for student in students:
            if student.block:  # Skip students with no block
                key = (student.first_name, student.last_initial, student.block)
                groups[key].append(student)

        # Find groups with duplicates
        duplicates = {k: v for k, v in groups.items() if len(v) > 1}

        if not duplicates:
            print("✓ No duplicates found!")
            return

        print(f"\n⚠️  Found {len(duplicates)} sets of duplicate students:")
        print("=" * 80)

        total_to_delete = 0
        for (first_name, last_initial, block), students_list in duplicates.items():
            print(f"\n{first_name} {last_initial}. in Block {block}:")
            print(f"  Found {len(students_list)} copies (will keep oldest, delete {len(students_list)-1})")

            # Sort by ID (oldest first)
            students_list.sort(key=lambda s: s.id)

            print(f"  KEEP: ID={students_list[0].id}, Created first")
            for dup in students_list[1:]:
                print(f"  DELETE: ID={dup.id}, Setup={dup.has_completed_setup}, "
                      f"Checking=${dup.checking_balance:.2f}, Savings=${dup.savings_balance:.2f}")
                total_to_delete += 1

        print("\n" + "=" * 80)
        print(f"\nTotal: {total_to_delete} duplicate records will be deleted")
        print("\nTo delete these duplicates, run:")
        print("  python cleanup_duplicates.py --delete")


def delete_duplicates():
    """Delete duplicate students, keeping the oldest record."""
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

        deleted_count = 0
        for (first_name, last_initial, block), students_list in duplicates.items():
            # Sort by ID (oldest first)
            students_list.sort(key=lambda s: s.id)

            # Keep first, delete rest
            keep = students_list[0]
            to_delete = students_list[1:]

            print(f"\n{first_name} {last_initial}. in Block {block}:")
            print(f"  KEEPING: ID={keep.id}")

            for dup in to_delete:
                print(f"  DELETING: ID={dup.id}")
                db.session.delete(dup)
                deleted_count += 1

        db.session.commit()
        print(f"\n✓ Successfully deleted {deleted_count} duplicate records!")
        print(f"✓ Database cleanup complete!")


if __name__ == "__main__":
    import sys

    if "--delete" in sys.argv:
        print("⚠️  WARNING: This will permanently delete duplicate student records!")
        print("Press Ctrl+C within 5 seconds to cancel...")
        import time
        time.sleep(5)
        print("\nProceeding with deletion...")
        delete_duplicates()
    else:
        find_duplicates()
