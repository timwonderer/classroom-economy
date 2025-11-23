#!/usr/bin/env python3
"""
Script to find and optionally fix orphaned insurance policies with NULL teacher_id.
These policies won't show up in any teacher's admin panel.
"""

import sys
sys.path.insert(0, '/home/user/classroom-economy')

from app import create_app, db
from app.models import InsurancePolicy, Admin

def main():
    app = create_app()
    with app.app_context():
        # Find policies with NULL teacher_id
        orphaned = InsurancePolicy.query.filter(
            InsurancePolicy.teacher_id == None
        ).all()

        print(f"Found {len(orphaned)} orphaned insurance policies (NULL teacher_id):\n")

        if not orphaned:
            print("✅ No orphaned policies found!")
            return

        for policy in orphaned:
            print(f"ID: {policy.id}")
            print(f"Title: {policy.title}")
            print(f"Premium: ${policy.premium}")
            print(f"Active: {policy.is_active}")
            print(f"Created: {policy.created_at}")

            # Check if any students are enrolled
            enrollment_count = policy.student_policies.count()
            print(f"Enrollments: {enrollment_count}")
            print("-" * 50)

        # Show available teachers
        teachers = Admin.query.all()
        print(f"\n\nAvailable teachers to assign orphaned policies to:")
        for teacher in teachers:
            print(f"  - ID {teacher.id}: {teacher.username}")

        print("\n⚠️  These policies are invisible in the admin panel!")
        print("To fix: Assign them to a teacher or delete them using:")
        print("  python3 -c 'from app import create_app, db; from app.models import InsurancePolicy; app=create_app(); ")
        print("           app.app_context().push(); policy=InsurancePolicy.query.get(ID); ")
        print("           policy.teacher_id=TEACHER_ID; db.session.commit()'")

if __name__ == "__main__":
    main()
