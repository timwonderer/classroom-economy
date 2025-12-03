"""
Fix missing StudentTeacher associations.

This script creates StudentTeacher records for any students that have a teacher_id
but no corresponding StudentTeacher association. This fixes legacy students that
were created before the multi-tenancy system was fully implemented.

Run this script BEFORE deploying the security fix that removes teacher_id filtering
from get_admin_student_query().

Usage:
    python scripts/fix_missing_student_teacher_associations.py
"""

import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from app.models import Student, StudentTeacher


def fix_missing_associations():
    """Create StudentTeacher records for students missing them."""
    with app.app_context():
        # Find all students with teacher_id but no StudentTeacher record
        # Use yield_per for memory efficiency with large datasets
        students_query = Student.query.filter(Student.teacher_id.isnot(None)).yield_per(1000)
        
        fixed_count = 0
        already_ok_count = 0
        batch_size = 100
        batch = []
        
        for student in students_query:
            # Check if StudentTeacher record already exists
            existing = StudentTeacher.query.filter_by(
                student_id=student.id,
                admin_id=student.teacher_id
            ).first()
            
            if not existing:
                # Create missing StudentTeacher record
                st = StudentTeacher(
                    student_id=student.id,
                    admin_id=student.teacher_id
                )
                batch.append(st)
                fixed_count += 1
                print(f"✓ Created StudentTeacher for student {student.id} -> teacher {student.teacher_id}")
                
                # Commit in batches for better performance
                if len(batch) >= batch_size:
                    db.session.bulk_save_objects(batch)
                    db.session.commit()
                    batch = []
            else:
                already_ok_count += 1
        
        # Commit any remaining records in the batch
        if batch:
            db.session.bulk_save_objects(batch)
            db.session.commit()
        
        if fixed_count > 0:
            print(f"\n✅ Fixed {fixed_count} students with missing StudentTeacher associations")
        else:
            print("\n✅ No missing StudentTeacher associations found")
        
        print(f"   {already_ok_count} students already had correct associations")
        
        # Also check for students with StudentTeacher but no teacher_id (orphaned associations)
        orphaned = db.session.query(StudentTeacher).join(Student).filter(
            Student.teacher_id.is_(None)
        ).count()
        
        if orphaned > 0:
            print(f"\n⚠️  Warning: {orphaned} StudentTeacher associations exist for students with NULL teacher_id")
            print("   These may be from shared students. Verify manually if needed.")


if __name__ == '__main__':
    print("=" * 60)
    print("Fixing Missing StudentTeacher Associations")
    print("=" * 60)
    print()
    
    fix_missing_associations()
    
    print()
    print("=" * 60)
    print("Complete!")
    print("=" * 60)
