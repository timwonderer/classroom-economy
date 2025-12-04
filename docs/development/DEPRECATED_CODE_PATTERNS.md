# Deprecated Code Patterns - Technical Debt

**Last Updated:** 2025-12-04
**Priority:** High (P1)
**Blocking 1.0:** No, but recommended before release

---

## Overview

This document tracks deprecated Python and SQLAlchemy patterns that need updating for Python 3.12+ compatibility and modern SQLAlchemy 2.0+ best practices.

---

## 1. Deprecated `datetime.utcnow()` (Python 3.12+)

### Issue
`datetime.utcnow()` is deprecated in Python 3.12+ in favor of `datetime.now(datetime.UTC)`.

### Current Status
- **~45+ occurrences** across the codebase
- Affects: `app/models.py`, `app/routes/*.py`, `wsgi.py`, `scripts/`, and utility modules

### Files Affected
```bash
# Search command to find all occurrences:
grep -r "datetime.utcnow()" --include="*.py" .
```

**Primary locations:**
- `app/models.py` - Model default timestamp columns
- `app/routes/admin.py` - Transaction creation timestamps
- `app/routes/student.py` - Student activity timestamps
- `app/routes/api.py` - API endpoint timestamps
- `wsgi.py` - Scheduled task timestamps
- Various scripts in `scripts/` directory

### Recommended Fix
```python
# OLD (deprecated):
from datetime import datetime
timestamp = datetime.utcnow()

# NEW (Python 3.12+):
from datetime import datetime, UTC
timestamp = datetime.now(UTC)

# Or using timezone:
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc)
```

### Migration Strategy
1. Add `from datetime import UTC` to imports
2. Replace all `datetime.utcnow()` with `datetime.now(UTC)`
3. Run full test suite to ensure no breaking changes
4. Verify timezone handling remains consistent

---

## 2. Deprecated `Query.get()` Method (SQLAlchemy 2.0+)

### Issue
The `Query.get()` method is deprecated in SQLAlchemy 2.0+ in favor of `session.get(Model, id)`.

### Current Status
- **~20+ occurrences** across the codebase
- Affects: `app/auth.py`, `app/routes/*.py`

### Files Affected
```bash
# Search command to find all occurrences:
grep -r "\.query\.get(" app/ --include="*.py"
```

**Primary locations:**
- `app/auth.py` - Authentication helper functions
- `app/routes/admin.py` - Admin dashboard queries
- `app/routes/student.py` - Student portal queries
- `app/routes/system_admin.py` - System admin queries
- `app/routes/api.py` - API endpoint queries

### Recommended Fix
```python
# OLD (deprecated):
student = Student.query.get(student_id)

# NEW (SQLAlchemy 2.0+):
from app.extensions import db
student = db.session.get(Student, student_id)
```

### Migration Strategy
1. Import `db` from `app.extensions` where needed
2. Replace `Model.query.get(id)` with `db.session.get(Model, id)`
3. Test each route to ensure functionality remains unchanged
4. Update any helper functions that use `.query.get()`

---

## 3. SQLAlchemy Subquery Warning

### Issue
SQLAlchemy warning: "Coercing Subquery into select()"

### Location
- `app/routes/system_admin.py:849`

### Context
```python
# Line 849 in system_admin.py needs review
# Warning suggests subquery coercion that could be made explicit
```

### Recommended Fix
Make subquery selection explicit using `.select()` or `.subquery()` as appropriate.

---

## Implementation Priority

### High Priority (Pre-1.0)
1. **Deprecated `datetime.utcnow()`** - Python 3.12 compatibility
2. **Deprecated `Query.get()`** - SQLAlchemy 2.0 compatibility

### Medium Priority (Post-1.0)
3. **SQLAlchemy Subquery Warning** - Code quality improvement

---

## Automation Opportunities

### Search and Replace Patterns

**For datetime.utcnow():**
```bash
# Find all occurrences:
grep -rn "datetime.utcnow()" --include="*.py" app/

# Semi-automated replacement (requires manual verification):
find app/ -name "*.py" -exec sed -i 's/datetime.utcnow()/datetime.now(UTC)/g' {} \;
```

**For Query.get():**
```bash
# Find all occurrences:
grep -rn "\.query\.get(" --include="*.py" app/

# Note: This requires manual refactoring due to varying patterns
```

---

## Testing Checklist

After making deprecation fixes, verify:

- [ ] All unit tests pass (`pytest tests/`)
- [ ] Timezone handling remains consistent
- [ ] Transaction timestamps are correct
- [ ] Payroll calculations still work
- [ ] Attendance tracking functions properly
- [ ] No new SQLAlchemy warnings appear
- [ ] Database migrations still run successfully
- [ ] API endpoints return correct timestamps

---

## References

- [Python 3.12 Release Notes](https://docs.python.org/3/whatsnew/3.12.html#deprecated) - datetime.utcnow() deprecation
- [SQLAlchemy 2.0 Migration Guide](https://docs.sqlalchemy.org/en/20/changelog/migration_20.html) - Query.get() deprecation
- [PEP 615](https://peps.python.org/pep-0615/) - Standard library timezone support

---

## Progress Tracking

- [ ] Create issue for datetime.utcnow() migration
- [ ] Create issue for Query.get() migration
- [ ] Assign to milestone (pre-1.0 or post-1.0)
- [ ] Schedule refactoring sprint
- [ ] Complete implementation
- [ ] Verify all tests pass
- [ ] Update this document with completion date

---

**Next Steps:**
1. Create GitHub issues for each deprecation type
2. Prioritize based on Python/SQLAlchemy version upgrade timeline
3. Schedule dedicated refactoring time
4. Execute changes in feature branch
5. Run comprehensive test suite
6. Merge after validation

**Estimated Effort:**
- datetime.utcnow() migration: ~2-3 hours
- Query.get() migration: ~2-3 hours
- Testing and validation: ~2 hours
- **Total:** ~6-8 hours
