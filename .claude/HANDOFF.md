# Agent Handoff — Drop Legacy Identity Tables (Commit 2 + 3)

**Date:** 2026-06-20
**Branch:** `drop-legacy-identity-tables` (based on `consolidate-identity-fields`, merges to `codex/v2.0`)
**Status:** Commit 1 schema changes DONE, Commit 2 consumer migration IN PROGRESS (not started)

---

## What's Been Done (Commit 1 — COMPLETE, NOT YET COMMITTED)

All changes are staged but uncommitted. Three files are modified/new:

### app/models.py — Schema changes complete
Every FK that pointed to `teachers.id` or `students.id` has been repointed to `users.id` or removed:

**FK repoints (teachers.id → users.id):**
- ClassEconomy.teacher_id, Transaction.teacher_id, StoreItem.teacher_id, RedemptionAuditLog.teacher_id, InsurancePolicy.teacher_id, Announcement.teacher_id, Announcement.target_teacher_id, AnalyticsSnapshot.teacher_id, AnalyticsEvent.teacher_id, Issue.teacher_id, AdminCredential (dropped teacher_id entirely, user_id made NOT NULL)

**FK repoints (students.id → users.id):**
- StudentRecoveryCode.student_id → user_id, ClassMembership collapsed admin_id+student_id → single user_id

**student_id columns REMOVED from:** Seat, StudentBlock, AttendanceSession, SeatAttendanceState, TapEvent, HallPassLog, StudentItem, RentPayment, RentWaiver, StudentInsurance, Issue

**Column renames:**
- ClassEconomy.created_by_admin_id → created_by_user_id
- RentWaiver.created_by_teacher_id → created_by_user_id
- TapEvent.deleted_by FK repointed to users.id

**Deleted:** StudentTeacher model, `_resolve_seat_id` helper, `Student.teachers` relationship, `Student.get_all_teachers()`, 7 dual-write sync listeners simplified/removed

**Fixed:** Issue index from student_id to seat_id

### migrations/versions/f0f0f0f0f0f0_merge_all_heads.py — NEW
Merges 3 migration heads: `0a1b2c3d4e5f`, `a2b3c4d5e6f7`, `d1e2f3a4b5c6`

### migrations/versions/f1f1f1f1f1f1_repoint_legacy_fks_to_users.py — NEW
Hand-written migration covering all schema changes. Uses idempotency helpers (column_exists, safe_drop_column, etc.). Downgrade raises NotImplementedError (clean DB, no data).

### .claude/ files — ALREADY COMMITTED
Fixed references from `main` to `codex/v2.0` in AGENTS.md, CLAUDE.md, rules/database-migrations.md. These are committed on the branch already.

---

## What Needs to Be Done

### Commit 2 — Consumer Migration

The app currently CANNOT IMPORT because `app/routes/api.py` (and many other files) import `StudentTeacher` which was deleted from models.py. Every consumer of deleted/renamed symbols must be fixed.

#### Breaking changes that need fixing:

**1. `StudentTeacher` deleted — ALL references must be replaced**

Files in `app/` that import or use StudentTeacher:
- `app/auth.py` (line ~766) — `get_admin_student_query()` joins through StudentTeacher to find students for a teacher
- `app/attendance.py` (line ~286) — uses StudentTeacher to get student IDs for admin
- `app/routes/admin.py` (line ~58 import, ~1240, ~1448-1460, ~1563-1596, ~2063-2079, ~5486, ~5655, ~11595-11596) — creates/queries/deletes StudentTeacher links
- `app/routes/student.py` (lines ~484, ~754) — imports StudentTeacher
- `app/routes/system_admin.py` (line ~31) — imports StudentTeacher
- `app/utils/student_deletion.py` (lines ~20, ~143-165) — deletes StudentTeacher rows
- `app/routes/api.py` (line ~22) — imports StudentTeacher

The v2 replacement for StudentTeacher: teacher-to-class ownership is `ClassEconomy.teacher_id` (now → users.id). Student-to-class membership is via `Seat` (user_id + class_id). So "students for this teacher" = students with seats in classes owned by this teacher.

**CRITICAL JOIN PATH:** Seat no longer has `student_id`. The link from Student to Seat is: `Student.user_id == Seat.user_id` (Student model has a `user_id` column, verify by reading models.py around line 370-390). If Student.user_id doesn't exist yet, you'll need to check what Phase A (`consolidate-identity-fields`) added.

**2. `created_by_admin_id` renamed to `created_by_user_id` on ClassEconomy**

In `app/`:
- `app/routes/admin.py` lines ~1964-1970 — references `economy.created_by_admin_id`

In `tests/` — ~80 occurrences across many test files. Use `replace_all` to rename `created_by_admin_id` to `created_by_user_id` in each file.

**3. `created_by_teacher_id` renamed to `created_by_user_id` on RentWaiver**
- `tests/test_rent_penalty_reversal.py` line ~171

**4. `student_id` removed from many models — consumer code accessing `.student_id`**

Run: `grep -rn "\.student_id" --include="*.py" app/ | grep -v __pycache__ | grep -v models.py | grep -v migrations/`

These need case-by-case fixes — most should become `.seat_id` or join through Seat.

**5. `.teacher` relationships now return `User` not `Admin`**

Any code doing `thing.teacher.some_admin_property` will break. The `.teacher` relationship on ClassEconomy, Transaction, StoreItem, etc. now points to User model.

#### User's directive on test fixtures:

The user explicitly requested: **"develop the canonical context for all tests instead of making them every time. there should be a contextFactory creating the context just like how the app would create them in production. one script, use for all."**

There is already a `tests/helpers/context_factory.py` with a `ClassroomContextFactory`. Read it (and the `classroom_context` / `classroom_with_students` fixtures in `tests/conftest.py` lines 321-368). The user wants ALL tests migrated to use this factory instead of manually creating Admin/Student/StudentTeacher/ClassEconomy objects. This is the right time because we're touching every test file anyway.

The factory should:
- Create User (not Admin) as the teacher
- Create ClassEconomy with teacher_id pointing to User
- Create Seat records (not StudentTeacher links) for students
- Create IdentityProfile for display names
- Handle all the wiring that individual tests currently do manually

Read `tests/helpers/context_factory.py` to understand the current implementation, then expand it to cover all test scenarios and migrate tests to use it.

#### conftest.py changes needed:

`tests/conftest.py` has:
- Lines 56-146: Transaction shims that reference `student_id`, `Seat.student_id`, `student_teachers` table — all need updating
- `test_student` fixture (lines 296-317): Creates a bare Student — needs to also create User + Seat

### Commit 3 — Delete Legacy Models

After Commit 2 makes everything work with User+Seat:
- Delete the `Admin` class from models.py
- Delete the `Student` class from models.py  
- Delete the `StudentTeacher` class (already done in Commit 1)
- Drop `teachers`, `students`, `student_teachers` tables via migration
- Update `ClassroomContextFactory` to not create legacy Admin/Student rows
- Remove any remaining legacy references

---

## Key Architecture Rules (from user's memory + CLAUDE.md)

1. **Base branch is `codex/v2.0`** — never `main`
2. **No compat shims** — rewrite directly to canonical terminology, don't create bridge services or DTOs
3. **"Classroom context?" rule** — if entity represents an event within a classroom, canonical actor is Seat (seat_id). Otherwise, canonical actor is User (user_id)
4. **ClassMembership is legacy** — ClassEconomy/classes is the canonical teacher-to-class linkage
5. **block/period is display metadata** — never a scoping key; class_id is the only authority
6. **Don't replace "student/teacher" in UX** — only fix architectural/schema references
7. **FEAT layer** — all state mutations through app/feats/
8. **class_id is canonical boundary** — join_code is public alias

## Database State

The migration chain has multiple heads (5 were found). The user said: **"if the migration chain is broken, feel free to drop the entire db and rebuild. this is dev v2 and there's no data at all."** The merge migration (`f0f0f0f0f0f0`) consolidates them. After Commit 2 makes the app importable, you can test with:
```bash
# Drop and recreate
psql -U postgres -c "DROP DATABASE IF EXISTS classroom_economy"
psql -U postgres -c "CREATE DATABASE classroom_economy"
source venv/bin/activate
flask --app wsgi db upgrade
```

The .env DATABASE_URL points to `production_dev` but user's memory says to use `classroom_economy`. You may need to update .env.

## Verification Commands

```bash
# Check no remaining StudentTeacher references
grep -rn "StudentTeacher" --include="*.py" app/ | grep -v __pycache__

# Check no remaining student_teachers table references  
grep -rn "student_teachers" --include="*.py" app/ tests/ | grep -v __pycache__ | grep -v migrations/

# Check app imports cleanly
python3 -c "from app import app; print('OK')"

# Run tests
source venv/bin/activate && pytest -x -q
```

## File Quick Reference

| File | Purpose | Status |
|------|---------|--------|
| `app/models.py` | All ORM models | Commit 1 DONE |
| `app/auth.py` | `get_admin_student_query`, `get_student_for_admin` | NEEDS FIX (StudentTeacher) |
| `app/attendance.py` | Attendance/tap logic | NEEDS FIX (StudentTeacher) |
| `app/routes/admin.py` | Teacher routes (~12K lines) | NEEDS FIX (StudentTeacher, created_by_admin_id) |
| `app/routes/student.py` | Student routes | NEEDS FIX (StudentTeacher import) |
| `app/routes/api.py` | API endpoints | NEEDS FIX (StudentTeacher import) |
| `app/routes/system_admin.py` | Sysadmin routes | NEEDS FIX (StudentTeacher import) |
| `app/utils/student_deletion.py` | Student deletion util | NEEDS FIX (StudentTeacher) |
| `tests/conftest.py` | Test fixtures/shims | NEEDS FIX (student_id refs, student_teachers) |
| `tests/helpers/context_factory.py` | ClassroomContextFactory | NEEDS EXPANSION per user directive |
| `migrations/versions/f0f0f0f0f0f0_*.py` | Merge heads | DONE |
| `migrations/versions/f1f1f1f1f1f1_*.py` | FK repoint migration | DONE |
