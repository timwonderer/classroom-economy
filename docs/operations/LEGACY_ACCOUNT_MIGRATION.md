# Legacy Account Migration Guide

**Date:** 2025-12-19
**Version:** 1.2.x
**Status:** Ready for deployment

## Overview

This document describes the comprehensive migration process for transitioning all legacy accounts and NULL `join_code` data to the new multi-tenancy system. This migration is the final step in hardening the multi-tenancy system before deprecating the old `teacher_id`-based linkage system.

## Background

### Historical Context

The Classroom Token Hub platform evolved through several phases of multi-tenancy implementation:

1. **Phase 1 (Pre-2024):** Single-teacher, single-period model
   - Students linked directly to teachers via `Student.teacher_id`
   - No support for students in multiple classes

2. **Phase 2 (2024-2025):** Multi-teacher support
   - Added `StudentTeacher` many-to-many table
   - Students can enroll with multiple teachers
   - Still used `teacher_id` as primary scoping mechanism

3. **Phase 3 (2025-11-29):** Join code introduction
   - Added `join_code` to `Transaction` and `TapEvent` tables
   - Fixed P0 data leak between same-teacher periods
   - Introduced `TeacherBlock` claim-based enrollment

4. **Phase 4 (2025-12-06):** Complete isolation
   - Added `join_code` to all student-related tables
   - Added `StudentBlock` for per-period student state
   - Made `join_code` the absolute source of truth

5. **Phase 5 (2025-12-19):** Legacy migration (this document)
   - Comprehensive migration of all legacy accounts
   - Backfill all NULL `join_code` values
   - Prepare for `teacher_id` deprecation

### What is "Legacy Data"?

Legacy data includes:

1. **Legacy Students:** Students with `Student.teacher_id` set but missing:
   - `StudentTeacher` association records
   - `TeacherBlock` claimed seat entries

2. **NULL Join Codes:** Records in tables that should have `join_code` but don't:
   - `TeacherBlock` entries without `join_code`
   - `Transaction` records with NULL `join_code`
   - `TapEvent` records with NULL `join_code`
   - `student_items`, `student_insurance`, `hall_pass_logs`, `rent_payments` with NULL `join_code`

### Why This Migration is Critical

**Before Migration:**
- Legacy students may not appear in teacher rosters correctly
- Data isolation may fail for legacy records
- Cannot safely deprecate `Student.teacher_id` column
- Cannot enforce NOT NULL constraint on `join_code` columns

**After Migration:**
- All students properly enrolled via claim-based system
- Complete data isolation by `join_code`
- Ready to deprecate `teacher_id`-based queries
- Can enforce schema constraints for data integrity

## Migration Strategy

### The Comprehensive Migration Script

The migration is performed by a single comprehensive script:

```
scripts/comprehensive_legacy_migration.py
```

This script combines and extends the functionality of three previous migration scripts:
- `migrate_legacy_students.py` - Creates StudentTeacher and TeacherBlock entries
- `backfill_join_codes.py` - Backfills TeacherBlock join codes
- `fix_missing_student_teacher_associations.py` - Creates missing associations

### Migration Phases

The migration runs in 5 sequential phases:

#### Phase 1: Legacy Student Migration

**Purpose:** Create proper associations for students with `teacher_id`

**Steps:**
1. Find all students with `Student.teacher_id` set
2. Check for existing `StudentTeacher` associations
3. Create missing `StudentTeacher(student_id, admin_id)` records
4. Group students by `(teacher_id, block)` combination
5. Generate or reuse `join_code` for each group
6. Create `TeacherBlock` entries (marked as claimed) for each student

**Example:**
```
Student: John Doe (ID: 123, teacher_id: 5, block: "Period 1")
→ Creates: StudentTeacher(student_id=123, admin_id=5)
→ Creates: TeacherBlock(teacher_id=5, block="Period 1", join_code="ABC123",
                        student_id=123, is_claimed=True)
```

#### Phase 2: TeacherBlock Join Code Backfill

**Purpose:** Ensure all TeacherBlock entries have join codes

**Steps:**
1. Find all `TeacherBlock` entries with NULL or empty `join_code`
2. Group by `(teacher_id, block)` combination
3. For each group:
   - If another seat in same teacher-block has a code, reuse it
   - Otherwise, generate a new unique code
4. Update all seats in the group with the same `join_code`

**Example:**
```
TeacherBlock entries for Teacher 5, Period 1:
- Seat 1: join_code = NULL → Updated to "ABC123"
- Seat 2: join_code = NULL → Updated to "ABC123"
- Seat 3: join_code = "ABC123" → Already has code (used as source)
```

#### Phase 3: Transaction Join Code Backfill

**Purpose:** Backfill `join_code` for all transactions

**Strategy:**
- Match transactions to `TeacherBlock` entries by `student_id`
- Use the `join_code` from the corresponding claimed seat
- Bulk SQL update for performance

**SQL Used:**
```sql
UPDATE transaction AS t
SET join_code = tb.join_code
FROM teacher_blocks AS tb
WHERE t.join_code IS NULL
  AND t.student_id = tb.student_id
  AND tb.is_claimed = TRUE
  AND tb.join_code IS NOT NULL
  AND tb.join_code != '';
```

**Limitations:**
- Transactions without matching `TeacherBlock` remain NULL (orphaned data)
- Legacy test data may remain with NULL `join_code`

#### Phase 4: Tap Event Join Code Backfill

**Purpose:** Backfill `join_code` for attendance tap events

**Strategy:**
- Match tap events to `TeacherBlock` by `(student_id, period)`
- Period matching is case-insensitive
- Bulk SQL update for performance

**SQL Used:**
```sql
UPDATE tap_events AS te
SET join_code = tb.join_code
FROM teacher_blocks AS tb
WHERE te.join_code IS NULL
  AND te.student_id = tb.student_id
  AND UPPER(te.period) = UPPER(tb.block)
  AND tb.is_claimed = TRUE
  AND tb.join_code IS NOT NULL
  AND tb.join_code != '';
```

**Note:** Migration `aa5697e97c94` may have already performed this backfill.

#### Phase 5: Related Tables Join Code Backfill

**Purpose:** Backfill `join_code` for other student-related tables

**Tables Covered:**
- `student_items` - Store purchase records
- `student_insurance` - Insurance enrollment records
- `hall_pass_logs` - Hall pass request records
- `rent_payments` - Rent payment records

**Strategy:**
- Match records to `StudentBlock` by `student_id`
- Use the `join_code` from `StudentBlock`
- Bulk SQL update for performance

**SQL Pattern:**
```sql
UPDATE {table_name} AS t
SET join_code = sb.join_code
FROM student_blocks AS sb
WHERE t.join_code IS NULL
  AND t.student_id = sb.student_id
  AND sb.join_code IS NOT NULL
  AND sb.join_code != '';
```

### Safety Features

The migration script includes multiple safety features:

1. **Idempotency:** Safe to run multiple times
   - Checks for existing records before creating
   - Uses UPDATE, not INSERT for backfills
   - Skips already-migrated data

2. **Dry Run Mode:** Preview changes without applying them
   - Use `--dry-run` flag
   - Shows what would be migrated
   - No database changes made

3. **Batch Processing:** Efficient handling of large datasets
   - Preloads data to avoid N+1 queries
   - Uses bulk SQL updates
   - Commits at end (atomic operation)

4. **Error Handling:** Graceful failure and rollback
   - All-or-nothing transaction
   - Automatic rollback on errors
   - Detailed error logging

5. **Verification:** Post-migration integrity checks
   - Counts remaining legacy students
   - Checks for NULL `join_code` values
   - Reports warnings for manual review

## Running the Migration

### Prerequisites

1. **Database Backup**
   ```bash
   pg_dump $DATABASE_URL > backup_before_legacy_migration.sql
   ```

2. **Environment Setup**
   ```bash
   # Ensure environment variables are set
   source .env  # or equivalent

   # Verify database connection
   flask db current
   ```

3. **Application Code Up-to-Date**
   ```bash
   git pull origin main
   pip install -r requirements.txt
   ```

### Step 1: Dry Run

**Always run a dry run first to preview changes:**

```bash
python3 scripts/comprehensive_legacy_migration.py --dry-run
```

Expected output:
```
================================================================================
COMPREHENSIVE LEGACY ACCOUNT MIGRATION
================================================================================
🔍 DRY RUN MODE - No changes will be made
================================================================================

================================================================================
PHASE 1: LEGACY STUDENT MIGRATION
================================================================================

Found 15 legacy students to migrate:
  - John Doe (ID: 123, Teacher: 5, Block: Period 1)
  - Jane Smith (ID: 124, Teacher: 5, Block: Period 1)
  ...

🔍 DRY RUN: Would create StudentTeacher associations and TeacherBlock entries

...

================================================================================
MIGRATION SUMMARY
================================================================================

Legacy Account Migration:
  Legacy students found: 15
  StudentTeacher associations created: 0 (dry run)
  ...

ℹ️  This was a dry run. Run without --dry-run to apply changes.
```

### Step 2: Review Dry Run Output

**Check for:**
1. Expected number of legacy students
2. Any errors or warnings
3. Tables that will be updated
4. Number of records affected

**If anything looks unexpected, investigate before proceeding!**

### Step 3: Run Migration

**Once satisfied with dry run:**

```bash
python3 scripts/comprehensive_legacy_migration.py
```

Expected output:
```
================================================================================
COMPREHENSIVE LEGACY ACCOUNT MIGRATION
================================================================================

================================================================================
PHASE 1: LEGACY STUDENT MIGRATION
================================================================================

Found 15 legacy students to migrate:
  - John Doe (ID: 123, Teacher: 5, Block: Period 1)
  ...

Creating StudentTeacher associations...
  ✓ Created StudentTeacher for John Doe
  ...

Grouping students by teacher and block...
Found 3 unique teacher-block combinations

Creating TeacherBlock entries...
  → Generated join code ABC123 for teacher 5, block Period 1
    ✓ Created TeacherBlock for John Doe
  ...

✅ Phase 1 complete: 15 associations, 15 blocks created

...

================================================================================
COMMITTING CHANGES
================================================================================

✅ All changes committed successfully!

================================================================================
VERIFICATION
================================================================================

1. Checking for legacy students...
  ✓ All students have proper StudentTeacher associations

2. Checking TeacherBlock join codes...
  ✓ All TeacherBlock entries have join codes

3. Checking transaction join codes...
  ✓ All transactions have join codes

4. Checking tap event join codes...
  ✓ All tap events have join codes

================================================================================

================================================================================
MIGRATION SUMMARY
================================================================================

Legacy Account Migration:
  Legacy students found: 15
  StudentTeacher associations created: 15
  TeacherBlock entries created: 15
  TeacherBlock entries updated: 0

Join Code Management:
  New join codes generated: 3
  Existing join codes reused: 0

Data Backfill:
  Transactions backfilled: 450
  Tap events backfilled: 120
  Student items backfilled: 35
  Student insurance backfilled: 8
  Hall pass logs backfilled: 22
  Rent payments backfilled: 10

✅ No errors encountered!
================================================================================
```

### Step 4: Verify Migration

**Manual verification checks:**

1. **Check for remaining legacy students:**
   ```sql
   SELECT s.id, s.full_name, s.teacher_id
   FROM students s
   WHERE s.teacher_id IS NOT NULL
     AND NOT EXISTS (
       SELECT 1 FROM student_teachers st
       WHERE st.student_id = s.id AND st.admin_id = s.teacher_id
     );
   ```
   Expected: 0 rows

2. **Check TeacherBlock join codes:**
   ```sql
   SELECT COUNT(*) FROM teacher_blocks
   WHERE join_code IS NULL OR join_code = '';
   ```
   Expected: 0

3. **Check transaction join codes:**
   ```sql
   SELECT COUNT(*) FROM transaction
   WHERE join_code IS NULL;
   ```
   Expected: 0 or very small number (orphaned test data)

4. **Check tap event join codes:**
   ```sql
   SELECT COUNT(*) FROM tap_events
   WHERE join_code IS NULL;
   ```
   Expected: 0

5. **Test student login and data access:**
   - Log in as a migrated student
   - Verify balance displays correctly
   - Verify transaction history shows
   - Verify no data from other periods visible

### Step 5: Monitor Production

**After deployment, monitor for:**
- Student login issues
- Missing balances or transaction history
- Data visibility errors
- Join code mismatches

**Check logs for:**
```bash
grep -i "join_code" /path/to/logs/application.log
grep -i "legacy" /path/to/logs/application.log
```

## Troubleshooting

### Issue: Legacy Students Still Exist After Migration

**Symptoms:**
- Verification shows students with `teacher_id` but no `StudentTeacher` record
- Students missing from teacher rosters

**Diagnosis:**
```sql
SELECT s.id, s.full_name, s.teacher_id, s.block
FROM students s
WHERE s.teacher_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM student_teachers st
    WHERE st.student_id = s.id AND st.admin_id = s.teacher_id
  );
```

**Solution:**
1. Check if the admin account exists:
   ```sql
   SELECT id, username FROM admins WHERE id = <teacher_id>;
   ```

2. If admin exists, manually create association:
   ```sql
   INSERT INTO student_teachers (student_id, admin_id, created_at)
   VALUES (<student_id>, <teacher_id>, NOW());
   ```

3. Re-run migration to create TeacherBlock entries

### Issue: Transactions Still Have NULL join_code

**Symptoms:**
- Verification shows transactions with NULL `join_code`
- Student balances appear incorrect

**Diagnosis:**
```sql
SELECT t.id, t.student_id, t.teacher_id, t.amount, t.description
FROM transaction t
WHERE t.join_code IS NULL
LIMIT 10;
```

**Possible Causes:**

1. **No matching TeacherBlock:**
   - Transaction's student_id doesn't match any claimed TeacherBlock
   - Student may have been deleted
   - Orphaned test data

2. **TeacherBlock missing join_code:**
   - Run Phase 2 again to backfill TeacherBlock codes

**Solution for Orphaned Data:**
```sql
-- Option 1: Delete orphaned transactions
DELETE FROM transaction
WHERE join_code IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM students WHERE id = transaction.student_id
  );

-- Option 2: Manually assign join_code
UPDATE transaction
SET join_code = '<appropriate_join_code>'
WHERE id = <transaction_id>;
```

### Issue: Students Can't See Their Data After Migration

**Symptoms:**
- Student logs in successfully
- Balance shows as $0.00
- No transaction history visible
- Error: "No class context found"

**Diagnosis:**
1. Check if student has a claimed TeacherBlock:
   ```sql
   SELECT tb.id, tb.teacher_id, tb.block, tb.join_code, tb.is_claimed
   FROM teacher_blocks tb
   WHERE tb.student_id = <student_id>;
   ```

2. Check if StudentBlock exists:
   ```sql
   SELECT sb.id, sb.student_id, sb.join_code, sb.period
   FROM student_blocks sb
   WHERE sb.student_id = <student_id>;
   ```

3. Check if transactions have matching join_code:
   ```sql
   SELECT t.id, t.join_code, t.amount
   FROM transaction t
   WHERE t.student_id = <student_id>
   LIMIT 5;
   ```

**Solution:**

If TeacherBlock exists but StudentBlock is missing:
```sql
INSERT INTO student_blocks (student_id, join_code, period, tap_enabled, created_at)
SELECT tb.student_id, tb.join_code, tb.block, true, NOW()
FROM teacher_blocks tb
WHERE tb.student_id = <student_id>
  AND tb.is_claimed = TRUE
  AND NOT EXISTS (
    SELECT 1 FROM student_blocks sb
    WHERE sb.student_id = tb.student_id
      AND sb.join_code = tb.join_code
  );
```

### Issue: Student Appears in Multiple Periods Unexpectedly

**Symptoms:**
- Student shows multiple class contexts
- Student sees combined data from multiple periods

**This may be correct behavior if:**
- Student is legitimately enrolled in multiple periods
- Student has multiple teachers

**Diagnosis:**
```sql
SELECT tb.teacher_id, tb.block, tb.join_code, a.username
FROM teacher_blocks tb
JOIN admins a ON a.id = tb.teacher_id
WHERE tb.student_id = <student_id>
  AND tb.is_claimed = TRUE;
```

**If enrollment is incorrect:**
1. Verify with teacher which periods student should be in
2. Manually remove incorrect TeacherBlock entries:
   ```sql
   -- DO NOT delete if you're not 100% certain!
   UPDATE teacher_blocks
   SET is_claimed = FALSE, student_id = NULL, claimed_at = NULL
   WHERE id = <teacher_block_id>;
   ```

## Post-Migration Tasks

### Immediate (Complete Within 1 Week)

- [ ] Monitor application logs for errors
- [ ] Verify student and teacher access
- [ ] Check for any NULL `join_code` values
- [ ] Review any warnings from migration script
- [ ] Document any manual interventions required

### Short-term (Complete Within 1 Month)

- [ ] Analyze performance of `join_code`-based queries
- [ ] Optimize indexes if needed
- [ ] Review and clean up orphaned test data
- [ ] Update test fixtures to use new system
- [ ] Train support staff on new data model

### Long-term (Complete Within 3 Months)

- [ ] Make `join_code` NOT NULL on all tables
- [ ] Remove `Student.teacher_id` column
- [ ] Remove deprecated `get_current_teacher_id()` function
- [ ] Remove legacy fallback code in balance calculations
- [ ] Create explicit `ClassPeriod` model (optional)
- [ ] Update API documentation

## Future: Deprecating teacher_id

Once the migration is complete and stable, the next phase is to deprecate `teacher_id`:

### Step 1: Make join_code NOT NULL

**Create a new migration:**
```python
# migrations/versions/xxxxx_make_join_code_not_null.py

def upgrade():
    # Make join_code NOT NULL on all tables
    op.alter_column('transaction', 'join_code', nullable=False)
    op.alter_column('tap_events', 'join_code', nullable=False)
    op.alter_column('student_items', 'join_code', nullable=False)
    # ... etc for all tables
```

### Step 2: Remove teacher_id Column

**After ensuring join_code is working:**
```python
# migrations/versions/xxxxx_remove_teacher_id_from_student.py

def upgrade():
    # Remove the deprecated teacher_id column
    op.drop_column('students', 'teacher_id')

def downgrade():
    # This is a one-way migration!
    raise Exception("Cannot downgrade - teacher_id column permanently removed")
```

### Step 3: Code Cleanup

**Remove deprecated code:**
- `get_current_teacher_id()` function
- Legacy balance calculation methods
- Teacher_id fallback logic in queries
- Teacher_id-based filtering

## References

- **Security Audit:** `docs/security/CRITICAL_SAME_TEACHER_LEAK.md`
- **Multi-Tenancy Rules:** `.claude/rules/multi-tenancy.md`
- **Database Schema:** `docs/technical-reference/database_schema.md`
- **Related Migrations:**
  - `00212c18b0ac_add_join_code_to_transaction.py`
  - `aa5697e97c94_add_join_code_to_tap_events.py`
  - `b1c2d3e4f5g6_add_join_code_to_related_tables.py`

## Support

For questions or issues:
1. Review this documentation
2. Check related security audits
3. Search existing issues on GitHub
4. Create a new issue with:
   - Migration output
   - Error messages
   - SQL diagnostics
   - Steps to reproduce

---

**Document Version:** 1.0
**Last Updated:** 2025-12-19
**Author:** Claude (AI Assistant)
**Status:** Ready for deployment
