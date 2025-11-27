#!/usr/bin/env python3
"""
Repair script to fix TeacherBlock first_half_hash values.

This script fixes TeacherBlock entries that have incorrectly computed first_half_hash
values. The correct formula is: hash_hmac(f"{last_initial}{dob_sum}".encode(), salt)

Usage:
    python scripts/repair_teacher_block_hashes.py --dry-run  # Preview changes
    python scripts/repair_teacher_block_hashes.py            # Apply fixes

Note: Must be run from the repository root directory.
"""

import sys
import os
import argparse

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import TeacherBlock
from hash_utils import hash_hmac


# Placeholder constant for legacy entries that should be skipped
LEGACY_PLACEHOLDER_FIRST_NAME = "__JOIN_CODE_PLACEHOLDER__"


def repair_teacher_block_hashes(dry_run=True):
    """
    Repair TeacherBlock entries with incorrectly computed first_half_hash values.

    Args:
        dry_run: If True, only preview changes without modifying the database.
    """
    app = create_app()

    with app.app_context():
        print("=" * 70)
        print("TEACHER BLOCK HASH REPAIR SCRIPT")
        print("=" * 70)
        print()

        if dry_run:
            print("🔍 DRY RUN MODE - No changes will be made to the database")
            print()

        # Step 1: Find all TeacherBlock entries
        print("Step 1: Finding all TeacherBlock entries...")

        all_teacher_blocks = TeacherBlock.query.all()

        if not all_teacher_blocks:
            print("✓ No TeacherBlock entries found!")
            return

        print(f"Found {len(all_teacher_blocks)} TeacherBlock entries to check")
        print()

        # Step 2: Check and fix each entry
        print("Step 2: Checking and repairing hashes...")
        print()

        fixed_count = 0
        skipped_count = 0
        error_count = 0
        already_correct_count = 0

        for tb in all_teacher_blocks:
            # Skip placeholder entries
            if tb.first_name == LEGACY_PLACEHOLDER_FIRST_NAME:
                skipped_count += 1
                if dry_run:
                    print(f"  ⊙ SKIP: TeacherBlock #{tb.id} (placeholder entry)")
                continue

            # Skip entries without required fields
            if not tb.salt or not tb.last_initial:
                error_count += 1
                print(f"  ✗ ERROR: TeacherBlock #{tb.id} missing salt or last_initial")
                continue

            # Compute the correct hash
            try:
                credential = f"{tb.last_initial}{tb.dob_sum or 0}"
                correct_hash = hash_hmac(credential.encode(), tb.salt)
            except Exception as e:
                error_count += 1
                print(f"  ✗ ERROR: TeacherBlock #{tb.id} - Failed to compute hash: {e}")
                continue

            # Check if hash needs to be fixed
            if tb.first_half_hash == correct_hash:
                already_correct_count += 1
                continue

            # Fix needed
            fixed_count += 1
            status_str = "claimed" if tb.is_claimed else "unclaimed"
            print(f"  → FIX: TeacherBlock #{tb.id} ({tb.first_name} {tb.last_initial}., "
                  f"block={tb.block}, {status_str})")
            if dry_run:
                print(f"         Current:  {tb.first_half_hash[:16]}...")
                print(f"         Correct:  {correct_hash[:16]}...")
            else:
                tb.first_half_hash = correct_hash

        print()

        # Step 3: Commit changes if not dry run
        if not dry_run and fixed_count > 0:
            print("Step 3: Committing changes to database...")
            try:
                db.session.commit()
                print("✓ All changes committed successfully!")
            except Exception as e:
                db.session.rollback()
                print(f"✗ Error during commit: {str(e)}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
        elif dry_run:
            print("Step 3: Skipped (dry-run mode)")
        else:
            print("Step 3: Skipped (no changes needed)")

        print()

        # Summary
        print("=" * 70)
        print("REPAIR SUMMARY")
        print("=" * 70)
        print(f"Total entries checked: {len(all_teacher_blocks)}")
        print(f"Already correct:       {already_correct_count}")
        print(f"Fixed:                 {fixed_count}")
        print(f"Skipped (placeholders):{skipped_count}")
        print(f"Errors:                {error_count}")
        print()

        if dry_run:
            if fixed_count > 0:
                print("To apply these fixes, run:")
                print("  python scripts/repair_teacher_block_hashes.py")
            else:
                print("✓ All hashes are correct! No fixes needed.")
        else:
            if fixed_count > 0:
                print(f"✓ Repair complete! Fixed {fixed_count} entries.")
            else:
                print("✓ All hashes were already correct! No changes made.")


def main():
    parser = argparse.ArgumentParser(
        description="Repair TeacherBlock first_half_hash values."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying the database"
    )

    args = parser.parse_args()

    repair_teacher_block_hashes(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
