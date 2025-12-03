# Multi-Tenancy Security Fix - Deployment Instructions

## Overview

This document provides step-by-step instructions for deploying the multi-tenancy security fix that prevents teachers from seeing students belonging to other teachers.

## Issue Summary

**Severity:** P0 CRITICAL
**Impact:** Teachers could see students from other teachers

### Root Cause
The `get_admin_student_query()` function was filtering by both:
1. `Student.teacher_id` column (deprecated, can have stale data)
2. `StudentTeacher` association table

This dual-filtering approach caused a security leak when:
- Student records had incorrect `teacher_id` values
- A new teacher's ID matched a deleted teacher's ID (ID reuse)
- Data migration issues left orphaned student records

### The Fix
Changed the query to use **ONLY** the `StudentTeacher` association table as the source of truth, eliminating reliance on the deprecated `teacher_id` column.

## Pre-Deployment Checklist

### 1. Database Backup
```bash
# Create a backup of the production database
# Example for PostgreSQL:
pg_dump your_database_name > backup_before_multi_tenancy_fix_$(date +%Y%m%d_%H%M%S).sql
```

### 2. Verify Current State
```bash
# Check for students with teacher_id but no StudentTeacher record
python3 << 'EOF'
from app import app, db
from app.models import Student, StudentTeacher

with app.app_context():
    orphaned = Student.query.filter(
        Student.teacher_id.isnot(None)
    ).outerjoin(
        StudentTeacher,
        (StudentTeacher.student_id == Student.id) & 
        (StudentTeacher.admin_id == Student.teacher_id)
    ).filter(
        StudentTeacher.id.is_(None)
    ).count()
    
    print(f"Students with teacher_id but no StudentTeacher record: {orphaned}")
    
    if orphaned > 0:
        print("\n⚠️  WARNING: Found orphaned students that need migration!")
        print("   Run the migration script before deploying the fix.")
EOF
```

## Deployment Steps

### Step 1: Run Migration Script (CRITICAL)

**Before deploying the code fix**, run the migration script to create StudentTeacher records for legacy students:

```bash
# Set required environment variables
export DATABASE_URL="your_database_url"
export SECRET_KEY="your_secret_key"
export FLASK_ENV="production"
export ENCRYPTION_KEY="your_encryption_key"
export PEPPER_KEY="your_pepper_key"

# Run the migration script
python scripts/fix_missing_student_teacher_associations.py
```

Expected output:
```
============================================================
Fixing Missing StudentTeacher Associations
============================================================

✓ Created StudentTeacher for student 123 -> teacher 1
✓ Created StudentTeacher for student 456 -> teacher 2
...

✅ Fixed X students with missing StudentTeacher associations
   Y students already had correct associations

============================================================
Complete!
============================================================
```

### Step 2: Verify Migration Success

```bash
# Re-run the verification script
python3 << 'EOF'
from app import app, db
from app.models import Student, StudentTeacher

with app.app_context():
    orphaned = Student.query.filter(
        Student.teacher_id.isnot(None)
    ).outerjoin(
        StudentTeacher,
        (StudentTeacher.student_id == Student.id) & 
        (StudentTeacher.admin_id == Student.teacher_id)
    ).filter(
        StudentTeacher.id.is_(None)
    ).count()
    
    if orphaned == 0:
        print("✅ Migration successful! All students have StudentTeacher records.")
    else:
        print(f"❌ ERROR: {orphaned} students still missing StudentTeacher records!")
        print("   DO NOT PROCEED with deployment until this is fixed.")
EOF
```

### Step 3: Deploy Code Changes

```bash
# Pull the latest code
git fetch origin
git checkout copilot/fix-multi-tenancy-leak
git pull origin copilot/fix-multi-tenancy-leak

# Install any new dependencies (if needed)
pip install -r requirements.txt

# Restart the application
# (Your specific restart command, e.g., systemctl restart your-app)
```

### Step 4: Post-Deployment Verification

#### Test 1: Teacher Can See Their Own Students
```bash
# Login as a test teacher and verify they can see their students
# Navigate to /admin/students
# Expected: Should see only their own students
```

#### Test 2: Teacher Cannot See Other Students
```bash
# Login as Teacher A
# Check the student count on dashboard
# Note the count

# Login as Teacher B
# Check the student count on dashboard
# Expected: Different count, no overlap unless students are explicitly shared
```

#### Test 3: Brand New Teacher Sees Zero Students
```bash
# Create a brand new teacher account
# Login and check dashboard
# Expected: 0 students until they upload a roster or students claim seats
```

## Rollback Plan

If issues are detected post-deployment:

### Emergency Rollback

```bash
# 1. Revert to previous code version
git checkout <previous_commit_hash>

# 2. Restart application
# (Your specific restart command)

# 3. Restore database backup (if necessary)
psql your_database_name < backup_before_multi_tenancy_fix_YYYYMMDD_HHMMSS.sql

# 4. Report the issue to the development team
```

### Rollback Implications

- Teachers will revert to the insecure behavior (seeing students with matching teacher_id)
- The security vulnerability will remain until fixed
- No data loss should occur from rollback

## Monitoring

### Key Metrics to Monitor

1. **Student Visibility**: Monitor teacher dashboards to ensure correct student counts
2. **Error Rates**: Watch for 404 errors on student-related pages
3. **Support Tickets**: Watch for teachers reporting missing students

### Expected Behavior After Fix

- Teachers see only students linked via StudentTeacher table
- Brand new teachers see 0 students initially
- Teachers cannot access students belonging to other teachers
- Shared students (enrolled in multiple teachers' classes) appear in all relevant teacher dashboards

## Troubleshooting

### Issue: Teacher Reports Missing Students

**Cause:** Student has `teacher_id` set but no `StudentTeacher` record

**Fix:**
```python
from app import app, db
from app.models import Student, StudentTeacher

with app.app_context():
    # Find the student and teacher
    student_id = <student_id>
    teacher_id = <teacher_id>
    
    # Verify student exists and has correct teacher_id
    student = Student.query.get(student_id)
    print(f"Student teacher_id: {student.teacher_id}")
    
    # Check if StudentTeacher record exists
    st = StudentTeacher.query.filter_by(
        student_id=student_id,
        admin_id=teacher_id
    ).first()
    
    if not st:
        # Create the missing record
        st = StudentTeacher(student_id=student_id, admin_id=teacher_id)
        db.session.add(st)
        db.session.commit()
        print("✓ Created StudentTeacher record")
```

### Issue: Teacher Sees Students from Another Teacher

**Cause:** StudentTeacher record exists incorrectly

**Fix:**
```python
from app import app, db
from app.models import StudentTeacher

with app.app_context():
    # Find and remove incorrect association
    incorrect_link = StudentTeacher.query.filter_by(
        student_id=<student_id>,
        admin_id=<wrong_teacher_id>
    ).first()
    
    if incorrect_link:
        db.session.delete(incorrect_link)
        db.session.commit()
        print("✓ Removed incorrect StudentTeacher record")
```

## Support Contacts

- **Development Team:** [Your team contact]
- **Emergency Contact:** [Emergency contact]
- **Documentation:** This file + MULTI_TENANCY_AUDIT.md

## Additional Notes

### Future Deprecation of teacher_id Column

The `Student.teacher_id` column is now deprecated and should be removed in a future migration once all systems have been updated to use only StudentTeacher associations. Timeline: TBD

### Related Issues

- Original bug report: #[issue_number]
- Multi-tenancy audit document: `MULTI_TENANCY_AUDIT.md`
- Test coverage: `tests/test_admin_multi_tenancy.py`

---

**Document Version:** 1.0
**Last Updated:** 2025-12-03
**Author:** GitHub Copilot
