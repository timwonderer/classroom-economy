# Multi-Tenancy Security Audit Results

**Date:** 2025-12-23
**Auditor:** Claude Code
**Scope:** Full codebase audit for unsafe `Student.query` usage

---

## Executive Summary

Found **31 instances** of `Student.query` usage across the codebase. Classified as:

- 🔴 **CRITICAL** (8): Unscoped queries that can leak data across periods
- 🟠 **HIGH** (6): Using deprecated `teacher_id` column
- 🟡 **MEDIUM** (4): Should use scoped helpers for consistency
- 🟢 **LOW/OK** (10): System admin context or properly scoped
- ℹ️ **INFO** (3): Demo sessions or CLI commands (acceptable)

---

## 🔴 CRITICAL - Data Leak Risks

### 1. app/routes/api.py:415 - Collective Items Block Query
**Issue:** Queries students by block WITHOUT join_code scoping
```python
students_in_block = Student.query.filter_by(block=student.block).all()
```
**Risk:** Returns students from ALL teachers who use the same block name (e.g., "Period 1")
**Fix:** Scope by join_code from current student context

### 2. app/routes/api.py:1693 - Tap Event History
**Issue:** Direct `Student.query.get()` before checking access
```python
student = Student.query.get(student_id)
```
**Risk:** Could expose student data before authorization check
**Fix:** Use `get_student_for_admin(student_id, admin)`

### 3. app/routes/api.py:1772 - Tap Event Processing
**Issue:** Direct `Student.query.get()` without access check
```python
student = Student.query.get(event.student_id)
```
**Risk:** No verification that admin owns this student
**Fix:** Use scoped helper

### 4. app/routes/api.py:1809 - Delete Tap Event
**Issue:** Direct `Student.query.get()`
```python
student = Student.query.get(student_id)
```
**Risk:** No verification that admin owns this student
**Fix:** Use `get_student_for_admin()`

### 5. app/routes/student.py:511 - Student Leaderboard
**Issue:** Queries by block without join_code
```python
all_students = Student.query.filter_by(block=current_student.block).all()
```
**Risk:** Shows students from different teachers' periods
**Fix:** Add join_code scoping via StudentBlock

### 6. app/routes/student.py:622 - Store Purchase (Buyer)
**Issue:** Direct `Student.query.get()`
```python
student = Student.query.get(student_id)
```
**Risk:** Could access wrong student's data
**Fix:** Verify student matches session context

### 7. app/routes/student.py:667 - Store Purchase (Recipient)
**Issue:** Direct `Student.query.get()`
```python
student = Student.query.get(student_id)
```
**Risk:** Could gift to student from different period
**Fix:** Scope recipient to current join_code

### 8. app/routes/admin.py:261 - Bulk Actions
**Issue:** Direct query with student IDs from form
```python
students = Student.query.filter(Student.id.in_(affected_student_ids)).all()
```
**Risk:** No verification that admin owns these students
**Fix:** Use `get_admin_student_query().filter(Student.id.in_(...)))`

---

## 🟠 HIGH - Deprecated teacher_id Usage

### 9. app/routes/system_admin.py:540 - Primary Students Query
**Issue:** Uses deprecated `teacher_id` column
```python
primary_student_ids = [s.id for s in Student.query.filter_by(teacher_id=admin.id)]
```
**Fix:** Query via StudentTeacher table instead

### 10. app/routes/system_admin.py:830 - Legacy Students Query
**Issue:** Uses deprecated `teacher_id`
```python
students_via_legacy = Student.query.filter(Student.teacher_id == admin.id)
```
**Fix:** Use StudentTeacher associations

### 11. app/routes/system_admin.py:851 - Other Periods Query
**Issue:** Uses deprecated `teacher_id`
```python
other_periods = Student.query.filter(Student.teacher_id == admin.id)
```
**Fix:** Use StudentTeacher table

### 12. app/routes/system_admin.py:931 - Affected Students Query
**Issue:** Uses deprecated `teacher_id`
```python
affected_students = Student.query.filter(Student.teacher_id == admin.id)
```
**Fix:** Query via StudentTeacher

### 13. app/routes/admin.py:1019 - Teacher Recovery
**Issue:** Uses `student.teacher_id`
```python
if student.teacher_id:
    teacher_ids.add(student.teacher_id)
```
**Fix:** Query student's teachers via `student.teachers` relationship

### 14. app/cli_commands.py:40 - Legacy Migration CLI
**Issue:** Uses `teacher_id` for migration
```python
all_students_with_teacher_id = Student.query.filter(Student.teacher_id.isnot(None))
```
**Note:** This is a migration command, acceptable for cleanup

---

## 🟡 MEDIUM - Should Use Scoped Helpers

### 15. app/routes/admin.py:1005-1008 - Username Lookup
**Issue:** Direct queries by username
```python
student = Student.query.filter_by(username_lookup_hash=lookup_hash).first()
```
**Fix:** Use `get_admin_student_query().filter_by(...).first()`

### 16. app/routes/admin.py:1765 - Student Get
**Issue:** Direct `Student.query.get()`
```python
student = Student.query.get(student_id)
```
**Context:** In admin route, should verify ownership
**Fix:** Use `get_student_for_admin()`

### 17. app/routes/admin.py:2366 - Duplicate Check
**Issue:** Direct query for duplicates
```python
potential_duplicates = Student.query.filter_by(username_lookup_hash=...)
```
**Fix:** Scope to admin's students only

### 18. app/routes/admin.py:2526 - Another Duplicate Check
**Issue:** Same as above
**Fix:** Use scoped query

---

## 🟢 LOW/OK - Acceptable Usage

### 19. app/routes/system_admin.py:224 - Total Count
**Context:** System admin dashboard, intentionally global
```python
total_students = Student.query.count()
```
**Status:** ✅ OK - System admin context

### 20. app/routes/system_admin.py:572-588 - Student Cleanup
**Context:** System admin bulk operations
**Status:** ✅ OK - System admin has global access

### 21. app/routes/system_admin.py:1121 - Bug Report
**Context:** System admin viewing bug report
```python
student = Student.query.get(report._student_id)
```
**Status:** ✅ OK - System admin context

### 22. app/auth.py:275 - Get Logged In Student
**Context:** Session management helper
```python
return Student.query.get(session['student_id'])
```
**Status:** ✅ OK - Session-scoped, no leak risk

### 23-26. app/auth.py:305-324 - Scoped Helper Implementation
**Context:** Inside `get_admin_student_query()` function
**Status:** ✅ OK - These ARE the scoped helpers

### 27. app/routes/student.py:2620 - Student Login
**Context:** Login flow, looking up by username
```python
student = Student.query.filter_by(username_lookup_hash=lookup_hash).first()
```
**Status:** ✅ OK - Login context, needs global lookup

### 28. app/routes/api.py:714, 984 - Insurance Operations
**Context:** Subqueries for insurance eligibility
**Status:** ⚠️ Needs verification - Check if properly scoped

### 29. app/routes/api.py:1263 - Transaction History
**Context:** Fetching student names for display
**Status:** ⚠️ Needs verification - Should only query students in scope

---

## ℹ️ INFO - CLI/Demo/Utility

### 30. app/scheduled_tasks.py:26 - Scheduled Task
**Context:** Background job processing
**Status:** ℹ️ Review needed - May need scoping per teacher

### 31. app/cli_commands.py - Multiple CLI Commands
**Context:** Administrative CLI tools
**Status:** ℹ️ OK - CLI tools have different security model

### 32. app/utils/demo_sessions.py:67 - Demo Cleanup
**Context:** Demo session cleanup utility
**Status:** ℹ️ OK - Demo context

---

## Recommended Fix Priority

### Phase 1: Critical Fixes (Week 1)
1. ✅ Fix collective items block query (api.py:415)
2. ✅ Fix student leaderboard (student.py:511)
3. ✅ Fix tap event queries (api.py:1693, 1772, 1809)
4. ✅ Fix store purchase queries (student.py:622, 667)
5. ✅ Fix bulk actions (admin.py:261)

### Phase 2: Deprecation Cleanup (Week 1)
6. ✅ Replace teacher_id usage in system_admin.py
7. ✅ Replace teacher_id usage in admin.py (teacher recovery)

### Phase 3: Consistency (Week 2)
8. ✅ Update username lookups to use scoped helpers
9. ✅ Update duplicate checks to use scoped queries
10. ✅ Add comprehensive tests for shared students

### Phase 4: Verification (Week 2)
11. ✅ Verify insurance operation scoping
12. ✅ Verify transaction history scoping
13. ✅ Run full test suite
14. ✅ Manual testing with multi-period students

---

## Testing Requirements

After fixes, ensure tests cover:

- ✅ Student in multiple periods with SAME teacher
- ✅ Student in multiple periods with DIFFERENT teachers
- ✅ Collective items don't leak across periods
- ✅ Leaderboards scoped correctly
- ✅ Tap events isolated by join_code
- ✅ Store purchases can't cross period boundaries
- ✅ Bulk operations respect teacher ownership

---

## Success Criteria

- [ ] All 8 CRITICAL issues resolved
- [ ] All 6 HIGH priority issues resolved
- [ ] Zero usage of deprecated `teacher_id` in queries
- [ ] All student queries use scoped helpers or explicit join_code
- [ ] Comprehensive test coverage added
- [ ] Full test suite passes
- [ ] Manual testing with multi-period scenarios

---

**Next Steps:**
1. Review this audit with team
2. Create branches for each fix phase
3. Implement fixes systematically
4. Add regression tests
5. Update documentation

