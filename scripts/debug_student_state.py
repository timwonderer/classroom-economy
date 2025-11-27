#!/usr/bin/env python3
"""
Debug script to check the current state of students and their associations.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Student, StudentTeacher, TeacherBlock, Admin

def debug_student_state():
    app = create_app()

    with app.app_context():
        print("=" * 70)
        print("STUDENT DATABASE STATE ANALYSIS")
        print("=" * 70)
        print()

        # Get all students
        all_students = Student.query.all()
        print(f"Total students in database: {len(all_students)}")
        print()

        # Check teacher_id field
        students_with_teacher_id = Student.query.filter(Student.teacher_id.isnot(None)).all()
        students_without_teacher_id = Student.query.filter(Student.teacher_id.is_(None)).all()

        print(f"Students WITH teacher_id set: {len(students_with_teacher_id)}")
        print(f"Students WITHOUT teacher_id set: {len(students_without_teacher_id)}")
        print()

        # Check StudentTeacher associations
        total_st = StudentTeacher.query.count()
        print(f"Total StudentTeacher associations: {total_st}")
        print()

        # Check TeacherBlock entries
        total_tb = TeacherBlock.query.count()
        claimed_tb = TeacherBlock.query.filter_by(is_claimed=True).count()
        unclaimed_tb = TeacherBlock.query.filter_by(is_claimed=False).count()

        print(f"Total TeacherBlock entries: {total_tb}")
        print(f"  - Claimed: {claimed_tb}")
        print(f"  - Unclaimed: {unclaimed_tb}")
        print()

        # Check for students with accounts (have setup completed)
        students_with_accounts = Student.query.filter(Student.has_completed_setup == True).all()
        students_without_accounts = Student.query.filter(Student.has_completed_setup == False).all()

        print(f"Students with completed setup: {len(students_with_accounts)}")
        print(f"Students without completed setup: {len(students_without_accounts)}")
        print()

        # Check for discrepancies
        print("=" * 70)
        print("DISCREPANCY CHECK")
        print("=" * 70)
        print()

        # Students with accounts but no StudentTeacher
        # Efficiently find students with accounts but no StudentTeacher association
        student_ids_with_accounts = [s.id for s in students_with_accounts]
        students_with_st = set(
            st.student_id for st in StudentTeacher.query.filter(
                StudentTeacher.student_id.in_(student_ids_with_accounts)
            ).all()
        )
        problematic = [s for s in students_with_accounts if s.id not in students_with_st]
        if problematic:
            print(f"⚠ Found {len(problematic)} students WITH accounts but NO StudentTeacher associations:")
            for s in problematic[:10]:  # Show first 10
                print(f"  - {s.full_name} (ID: {s.id}, Block: {s.block}, teacher_id: {s.teacher_id})")
            if len(problematic) > 10:
                print(f"  ... and {len(problematic) - 10} more")
        else:
            print("✓ All students with accounts have StudentTeacher associations")
        print()

        # Students with accounts but no claimed TeacherBlock
        # Efficiently find students with accounts but no claimed TeacherBlock (avoid N+1 queries)
        student_ids_with_accounts = [s.id for s in students_with_accounts]
        claimed_tb_students = set(
            tb.student_id for tb in TeacherBlock.query.filter(
                TeacherBlock.student_id.in_(student_ids_with_accounts),
                TeacherBlock.is_claimed == True
            ).all()
        )
        no_tb = [s for s in students_with_accounts if s.id not in claimed_tb_students]

        if no_tb:
            print(f"⚠ Found {len(no_tb)} students WITH accounts but NO claimed TeacherBlock:")
            for s in no_tb[:10]:  # Show first 10
                print(f"  - {s.full_name} (ID: {s.id}, Block: {s.block}, teacher_id: {s.teacher_id})")
            if len(no_tb) > 10:
                print(f"  ... and {len(no_tb) - 10} more")
        else:
            print("✓ All students with accounts have claimed TeacherBlock entries")
        print()

        # Check all teachers
        all_teachers = Admin.query.all()
        print(f"Total teachers in database: {len(all_teachers)}")
        for teacher in all_teachers:
            print(f"  Teacher ID {teacher.id}: {teacher.username}")

            # Count students by different methods
            direct = Student.query.filter_by(teacher_id=teacher.id).count()
            via_st = StudentTeacher.query.filter_by(admin_id=teacher.id).count()
            roster_seats = TeacherBlock.query.filter_by(teacher_id=teacher.id).count()
            claimed_seats = TeacherBlock.query.filter_by(teacher_id=teacher.id, is_claimed=True).count()

            print(f"    - Students via teacher_id: {direct}")
            print(f"    - Students via StudentTeacher: {via_st}")
            print(f"    - Total TeacherBlock entries: {roster_seats}")
            print(f"    - Claimed TeacherBlock entries: {claimed_seats}")
        print()

        # Additional analysis: Check for students with StudentTeacher but no TeacherBlock
        print("=" * 70)
        print("DETAILED ANALYSIS: Students with StudentTeacher but no TeacherBlock")
        print("=" * 70)
        print()

        for teacher in all_teachers:
            students_via_st = Student.query.join(
                StudentTeacher, Student.id == StudentTeacher.student_id
            ).filter(
                StudentTeacher.admin_id == teacher.id,
                Student.has_completed_setup == True
            ).all()

            if students_via_st:
                print(f"Teacher ID {teacher.id} ({teacher.username}):")
                print(f"  Total students with accounts: {len(students_via_st)}")

                # Check how many have claimed TeacherBlock
                # Bulk fetch all claimed TeacherBlocks for these students and this teacher
                student_ids = [s.id for s in students_via_st]
                claimed_tbs = set(
                    tb.student_id for tb in TeacherBlock.query.filter(
                        TeacherBlock.teacher_id == teacher.id,
                        TeacherBlock.student_id.in_(student_ids),
                        TeacherBlock.is_claimed == True
                    ).all()
                )
                with_tb = len(claimed_tbs)
                without_tb = [s for s in students_via_st if s.id not in claimed_tbs]

                print(f"  Students with claimed TeacherBlock: {with_tb}")
                print(f"  Students WITHOUT claimed TeacherBlock: {len(without_tb)}")

                if without_tb:
                    print(f"  Sample students without TeacherBlock (first 10):")
                    # Fetch all unclaimed TeacherBlocks for this teacher in one query
                    unclaimed_tbs = TeacherBlock.query.filter_by(
                        teacher_id=teacher.id,
                        is_claimed=False
                    ).all()
                    # Build a lookup dictionary by (first_name, last_initial)
                    unclaimed_tb_lookup = {
                        (tb.first_name, tb.last_initial): tb for tb in unclaimed_tbs
                    }
                    for s in without_tb[:10]:
                        key = (s.first_name, s.last_initial)
                        status = "has unclaimed seat" if key in unclaimed_tb_lookup else "no seat found"
                        print(f"    - {s.full_name} (ID: {s.id}, Block: {s.block}, {status})")
                print()

if __name__ == '__main__':
    debug_student_state()
