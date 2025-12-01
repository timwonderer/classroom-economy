# Technical Debt Issues Identified

This document tracks technical debt issues identified during repository cleanup on 2025-11-28. These should be converted to GitHub issues and prioritized based on upcoming Python/SQLAlchemy version upgrades.

---

## Issue 1: Deprecated `datetime.utcnow()` Usage

**Priority:** Medium (Python deprecation warning)

**Title:** Refactor deprecated `datetime.utcnow()` to use timezone-aware objects

**Description:**
Python's `datetime.datetime.utcnow()` is deprecated and scheduled for removal in a future version. The codebase has 45+ occurrences of this deprecated method.

**Locations:**
- `app/routes/admin.py`
- `app/routes/student.py`
- `app/routes/system_admin.py`
- `app/models.py`
- `wsgi.py`
- Various scripts in `scripts/`

**Recommended Fix:**
Replace `datetime.utcnow()` with `datetime.now(datetime.UTC)` for timezone-aware UTC timestamps.

**Labels:** `technical-debt`, `good-first-issue`

---

## Issue 2: Deprecated `Query.get()` Method Usage

**Priority:** Medium (SQLAlchemy 2.0 deprecation)

**Title:** Migrate from deprecated `Query.get()` to `Session.get()`

**Description:**
SQLAlchemy 2.0 deprecates `Query.get()` in favor of `Session.get()`. The codebase has 20+ occurrences of the deprecated pattern.

**Locations:**
- `app/auth.py` (lines 240, 251)
- `app/routes/student.py`
- `app/routes/admin.py`
- `app/routes/system_admin.py`

**Recommended Fix:**
Replace `Model.query.get(id)` with `db.session.get(Model, id)`.

**Labels:** `technical-debt`, `good-first-issue`

---

## Issue 3: SQLAlchemy Subquery Warning in System Admin Routes

**Priority:** Low (warning, not error)

**Title:** Fix SQLAlchemy subquery coercion warning in system_admin.py

**Description:**
Test output shows a warning about coercing Subquery object into a select():
```
SAWarning: Coercing Subquery object into a select() for use in IN(); please pass a select() construct explicitly
```

**Location:**
- `app/routes/system_admin.py` (line 849)

**Recommended Fix:**
Pass an explicit `select()` construct to the IN() clause instead of a Subquery object.

**Labels:** `technical-debt`

---

## Notes

- These issues do not affect current functionality - they are deprecation warnings
- All 75 tests continue to pass
- Priority should increase as Python 3.13+ and SQLAlchemy 2.1+ releases approach
- Consider addressing these during the next major refactoring effort

---

**Identified:** 2025-11-28
**Status:** Open (awaiting GitHub issue creation)
