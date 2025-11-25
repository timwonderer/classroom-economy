#!/usr/bin/env python3
"""
Backfill join codes for existing TeacherBlock entries.

This script finds all TeacherBlock entries that don't have join codes
and generates unique join codes for each teacher-block combination.

USAGE:
    python3 scripts/backfill_join_codes.py

NOTE: Run this script from the project root directory.
      Requires environment variables to be set (DATABASE_URL, etc.)

WHAT IT DOES:
    1. Finds all TeacherBlock entries without join codes (NULL or empty)
    2. Groups them by (teacher_id, block)
    3. For each group:
       - If another seat in the same teacher-block has a join code, reuses it
       - Otherwise, generates a new unique join code
    4. Updates all seats in each group with the same join code
    5. Commits changes to database
"""

import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import TeacherBlock
from app.utils.join_code import generate_join_code


def backfill_join_codes():
    """
    Backfill join codes for TeacherBlock entries that are missing them.

    Groups entries by (teacher_id, block) and assigns the same join code
    to all seats in that group.
    """
    app = create_app()

    with app.app_context():
        # Find all TeacherBlock entries without join codes
        blocks_without_codes = TeacherBlock.query.filter(
            db.or_(
                TeacherBlock.join_code == None,
                TeacherBlock.join_code == ''
            )
        ).all()

        if not blocks_without_codes:
            print("✓ All TeacherBlock entries already have join codes!")
            return

        print(f"Found {len(blocks_without_codes)} TeacherBlock entries without join codes")

        # Group by (teacher_id, block)
        groups = {}
        for tb in blocks_without_codes:
            key = (tb.teacher_id, tb.block)
            if key not in groups:
                groups[key] = []
            groups[key].append(tb)

        print(f"Grouped into {len(groups)} unique teacher-block combinations")

        # Generate and assign join codes
        updated_count = 0
        for (teacher_id, block), seats in groups.items():
            # Check if this teacher-block already has any seats with join codes
            existing_seat_with_code = TeacherBlock.query.filter_by(
                teacher_id=teacher_id,
                block=block
            ).filter(
                TeacherBlock.join_code != None,
                TeacherBlock.join_code != ''
            ).first()

            if existing_seat_with_code:
                # Reuse existing join code
                join_code = existing_seat_with_code.join_code
                print(f"  Reusing existing join code {join_code} for teacher {teacher_id}, block {block}")
            else:
                # Generate new unique join code
                while True:
                    join_code = generate_join_code()
                    # Ensure uniqueness across all teachers
                    if not TeacherBlock.query.filter_by(join_code=join_code).first():
                        break
                print(f"  Generated new join code {join_code} for teacher {teacher_id}, block {block}")

            # Assign join code to all seats in this group
            for seat in seats:
                seat.join_code = join_code
                updated_count += 1

        # Commit changes
        try:
            db.session.commit()
            print(f"\n✓ Successfully backfilled {updated_count} TeacherBlock entries!")

            # Verify
            remaining = TeacherBlock.query.filter(
                db.or_(
                    TeacherBlock.join_code == None,
                    TeacherBlock.join_code == ''
                )
            ).count()

            if remaining > 0:
                print(f"⚠ Warning: {remaining} entries still don't have join codes")
            else:
                print("✓ All TeacherBlock entries now have join codes!")

        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Error during commit: {str(e)}")
            sys.exit(1)


if __name__ == '__main__':
    print("=" * 60)
    print("TeacherBlock Join Code Backfill Script")
    print("=" * 60)
    print()

    backfill_join_codes()
