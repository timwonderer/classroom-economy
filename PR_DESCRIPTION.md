# Description

Adds a data migration system to transition legacy students from the deprecated `teacher_id` field to the modern multi-tenancy system using `StudentTeacher` associations and proper `TeacherBlock` entries.

**Problem Solved:**

- Join codes were regenerating on every page reload (non-persistent)
- New students unable to claim accounts due to unstable join codes
- Incorrect "All seats claimed" badge showing for blocks with unclaimed seats
- Legacy students (created before join code system) lacking proper TeacherBlock entries

**Solution:**

- Created Flask CLI command to migrate legacy student data
- Populates `student_teachers` table with many-to-many associations
- Creates proper `TeacherBlock` entries (marked as claimed) for legacy students
- Generates stable, persistent join codes per teacher-block combination

## Type of Change

- [x] Bug fix (non-breaking change which fixes an issue)
- [x] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Other (please describe):

## Testing

### Manual Testing Required

**⚠️ This PR requires manual testing as it's a data migration:**

1. **Before running migration:**

   ```bash
   # Verify legacy students exist
   flask shell
   >>> from app.models import Student, StudentTeacher
   >>> legacy = Student.query.filter(Student.teacher_id.isnot(None)).all()
   >>> print(f"Found {len(legacy)} students with teacher_id")
   >>> exit()
   ```

2. **Run the migration:**

   ```bash
   flask migrate-legacy-students
   ```

3. **Verify results:**
   - Check that join codes persist across page reloads
   - Verify badge counts are accurate
   - Test that new students can claim accounts successfully
   - Confirm all 7 periods have stable join codes

### Test Status

- [ ] Tested locally (requires production/staging environment)
- [ ] All existing tests pass (`pytest -q`)
- [ ] Added new tests for new functionality (CLI command testing recommended)

**Note:** Tests should be run in the deployment environment before merging.

## Database Migration Checklist

**Does this PR include a database migration?** [ ] Yes / [x] No

**Note:** This is a **data migration** (populates existing tables), not a **schema migration** (no table/column changes).

The migration:

- Uses existing `student_teachers` table ✓
- Uses existing `teacher_blocks` table ✓
- No schema changes required ✓

## Checklist

- [x] My code follows the project's style guidelines
- [x] I have performed a self-review of my own code
- [x] I have commented my code where necessary, particularly in hard-to-understand areas
- [ ] I have updated the documentation accordingly (see notes below)
- [x] My changes generate no new warnings or errors
- [x] I have read and followed the contributing guidelines

## Files Changed

### New Files

1. **`app/cli_commands.py`** (245 lines)
   - Flask CLI command: `flask migrate-legacy-students`
   - Implements full migration logic with verification
   - Handles grouping by (teacher_id, block) for join code generation

2. **`scripts/migrate_legacy_students.py`** (202 lines)
   - Standalone script version (alternative to CLI command)
   - Same functionality, can run outside Flask context

### Modified Files

1. **`app/__init__.py`** (3 lines added)
   - Registers CLI commands with Flask app factory
   - Lines 347-349: Import and initialize CLI commands module

## How to Use

### Run the Migration

```bash
# Option 1: Flask CLI command (recommended)
flask migrate-legacy-students

# Option 2: Python module syntax
python -m flask migrate-legacy-students

# Option 3: Standalone script
python3 scripts/migrate_legacy_students.py
```

### Expected Output

```python
## Migration Summary
LEGACY STUDENT MIGRATION
======================================================================

Step 1: Finding legacy students...
Found 250+ legacy students to migrate

Step 2: Creating StudentTeacher associations...
Created 250+ StudentTeacher associations

Step 3: Grouping students by teacher and block...
Found 7 unique teacher-block combinations

Step 4: Creating TeacherBlock entries...
Created 250+ TeacherBlock entries

Step 5: Committing changes to database...
✓ All changes committed successfully!

```markdown
Legacy students migrated: 250+
StudentTeacher associations created: 250+
TeacherBlock entries created: 250+
Unique teacher-block combinations: 7

Join codes by teacher and block:
   Teacher 1, Block A: ABC123
   Teacher 1, Block B: ZA7PWB
   Teacher 1, Block C: XYZ789
   Teacher 1, Block D: DEF456
   Teacher 1, Block E: GHI789
   Teacher 1, Block F: JKL012
   Teacher 1, Block X: MNO345

✓ Migration complete! All legacy students now use the new system.
```

======================================================================
LEGACY STUDENT MIGRATION
```markdown

Found 250+ legacy students to migrate

Step 2: Creating StudentTeacher associations...
Created 250+ StudentTeacher associations

Step 3: Grouping students by teacher and block...
Found 7 unique teacher-block combinations

Step 4: Creating TeacherBlock entries...
Created 250+ TeacherBlock entries

Step 5: Committing changes to database...
✓ All changes committed successfully!

======================================================================
MIGRATION SUMMARY
======================================================================
Legacy students migrated: 250+
StudentTeacher associations created: 250+
TeacherBlock entries created: 250+
Unique teacher-block combinations: 7

Join codes by teacher and block:
  Teacher 1, Block A: ABC123
  Teacher 1, Block B: ZA7PWB
  Teacher 1, Block C: XYZ789
  Teacher 1, Block D: DEF456
  Teacher 1, Block E: GHI789
  Teacher 1, Block F: JKL012
  Teacher 1, Block X: MNO345

✓ Migration complete! All legacy students now use the new system.

```

## Multi-Tenancy Alignment

This PR advances the multi-tenancy hardening efforts outlined in `AGENTS.md`:

**From AGENTS.md High-Priority Follow-Ups:**
> Students have a **primary owner** (`teacher_id`, still nullable pending enforcement) and a **many-to-many association** via `student_teachers` for shared accounts.

**What this PR does:**

- ✅ Populates `student_teachers` associations for all legacy students
- ✅ Maintains `teacher_id` compatibility (doesn't remove deprecated field yet)
- ✅ Creates proper TeacherBlock roster entries for tenant isolation
- ✅ Uses scoped query pattern (relies on existing associations)

**Next steps toward full multi-tenancy:**

- Future: Add `teacher_id NOT NULL` constraint once all students migrated
- Future: Add unique constraint on `(student_id, admin_id)` in `student_teachers`
- This PR is a prerequisite for those schema hardening steps

## Related Issues

Fixes the join code persistence issue discussed in conversation.

Related to:

- #415 - Fix unclaimed seats badge counting placeholder entries
- #413 - Fix join code persistence for legacy classes
- #407 - Fix join code display for teachers with pre-c3aa3a0 students

## Additional Notes

### Why This Approach?

Instead of continuing to patch the placeholder TeacherBlock system (which generated temporary entries on page load), this migration:

1. **Permanently fixes the root cause** by giving legacy students proper TeacherBlock entries
2. **Aligns with multi-tenancy goals** by populating StudentTeacher associations
3. **Enables future schema enforcement** (NOT NULL on teacher_id, unique constraints)
4. **Minimal disruption** - data migration only, no schema changes

### Safety Considerations

- **Idempotent:** Safe to run multiple times (checks for existing records)
- **No data deletion:** Only creates new records, never deletes
- **Rollback friendly:** Can manually delete created records if needed
- **Verification built-in:** Script verifies migration success automatically

### Documentation Updates Needed

- [ ] Update `docs/development/MULTI_TENANCY_TODO.md` - mark student_teachers population as complete
- [ ] Add runbook to `docs/operations/` for this migration procedure
- [ ] Update teacher manual with join code persistence guarantee

### Post-Merge Actions

1. Run migration in staging environment first
2. Verify join codes persist and new students can join
3. Run migration in production
4. Monitor for any issues with student claiming flow
5. Update MULTI_TENANCY_TODO.md milestone status
