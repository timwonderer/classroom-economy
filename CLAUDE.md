# Claude Development Guide for Classroom Token Hub

This document provides essential guidance for Claude (or any AI assistant) working on the Classroom Token Hub project. Following these guidelines ensures consistency, prevents common pitfalls, and maintains the project's high standards.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Critical Rules](#critical-rules)
3. [Architecture Patterns](#architecture-patterns)
4. [Database Migrations](#database-migrations)
5. [Documentation Standards](#documentation-standards)
6. [Testing Requirements](#testing-requirements)
7. [Security Principles](#security-principles)
8. [Multi-Tenancy Scoping](#multi-tenancy-scoping)
9. [Common Pitfalls](#common-pitfalls)
10. [Workflow Checklist](#workflow-checklist)

---

## Project Overview

**Classroom Token Hub** is an educational banking simulation platform for teaching financial literacy in classrooms. It's built with Flask, SQLAlchemy, PostgreSQL, and follows a multi-tenant architecture where:

- **Teachers** manage multiple class periods via join codes
- **Students** can be enrolled in multiple periods with different teachers
- **System Admins** oversee the entire platform

**Version:** 1.4.0 - Announcement System & UI Enhancements Release
**License:** PolyForm Noncommercial 1.0.0
**Python:** 3.10+
**Database:** PostgreSQL with Alembic migrations

---

## Critical Rules

### 🚨 MUST FOLLOW EVERY TIME

1. **ALWAYS read existing code before proposing changes**
   - Never suggest modifications to files you haven't read
   - Understand context before making changes

2. **ALWAYS scope database queries by `join_code`**
   - Every query for student data MUST be scoped to the current class period
   - See `.claude/rules/multi-tenancy.md` for detailed rules

3. **ALWAYS create a migration for database schema changes**
   - Never modify models without creating a migration
   - See `.claude/rules/database-migrations.md` for the complete workflow

4. **ALWAYS update documentation when adding features**
   - Update CHANGELOG.md for all changes
   - Update relevant user guides and technical docs
   - See `.claude/rules/documentation.md` for standards

5. **ALWAYS write tests for new features**
   - Minimum: happy path + error cases
   - Include multi-tenancy scoping tests
   - See `.claude/rules/testing.md` for requirements

6. **NEVER commit secrets or PII**
   - Use environment variables for sensitive data
   - Encrypt PII at rest using the encryption utilities

7. **NEVER skip CSRF protection**
   - All forms must include CSRF tokens
   - All POST/PUT/DELETE routes must validate CSRF

---

## Architecture Patterns

### Blueprint Structure

The application uses Flask Blueprints for modular organization:

```
app/
├── routes/
│   ├── admin.py          # Teacher/admin routes
│   ├── student.py        # Student routes
│   ├── system_admin.py   # System admin routes
│   ├── api.py            # API endpoints
│   └── auth.py           # Authentication
├── models.py             # SQLAlchemy models (35+ models)
├── utils/                # Utility functions
└── __init__.py           # App factory
```

### Key Files

- `wsgi.py` - Application entry point
- `forms.py` - WTForms form definitions
- `hash_utils.py` - Hashing and encryption utilities
- `payroll.py` - Payroll automation logic
- `attendance.py` - Attendance tracking logic

### Database Models

**35 SQLAlchemy models** including:
- Core: `Admin`, `Student`, `SystemAdmin`, `TeacherBlock`, `StudentBlock`
- Financial: `Transaction`, `PayrollSettings`, `BankingSettings`
- Features: `StoreItem`, `InsurancePolicy`, `RentSettings`, `HallPassLog`
- Multi-tenancy: `StudentTeacher` (links students to multiple teachers)
- Recovery: `RecoveryRequest`, `StudentRecoveryCode`

---

## Database Migrations

**See `.claude/rules/database-migrations.md` for complete workflow.**

### Quick Reference

```bash
# ALWAYS follow this sequence:

# 1. Modify the model in app/models.py
# 2. Generate migration
flask db migrate -m "Description of change"

# 3. Review the generated migration file
# 4. Test the migration
flask db upgrade

# 5. Test the downgrade
flask db downgrade

# 6. Re-upgrade for production
flask db upgrade

# 7. Run tests
pytest tests/
```

### Migration Naming Convention

- `add_<field>_to_<table>` - Adding columns
- `create_<table>` - New tables
- `remove_<field>_from_<table>` - Removing columns
- `rename_<old>_to_<new>_in_<table>` - Renaming
- `add_<table>_<relationship>_relationship` - Adding relationships

### Common Migration Mistakes (DON'T DO THIS)

❌ Modifying models without creating migrations
❌ Editing old migration files after they're merged
❌ Creating migrations with generic names like "update database"
❌ Skipping migration testing before committing
❌ Forgetting to add foreign key constraints

---

## Documentation Standards

**See `.claude/rules/documentation.md` for complete standards.**

### Files to Update for New Features

1. **CHANGELOG.md** - All changes, following Keep a Changelog format
2. **DEVELOPMENT.md** - Add to roadmap or mark as completed
3. **README.md** - Update if it affects installation/quick start
4. **User guides** in `docs/user-guides/` - If user-facing
5. **Technical reference** in `docs/technical-reference/` - For architecture changes

### Documentation Organization

```
docs/
├── README.md                  # Documentation index
├── user-guides/              # For teachers and students
│   ├── teacher_manual.md
│   └── student_guide.md
├── technical-reference/      # Architecture, database, API
│   ├── architecture.md
│   ├── database_schema.md
│   └── ECONOMY_SPECIFICATION.md
├── operations/               # Deployment, maintenance
│   ├── DEPLOYMENT.md
│   └── MULTI_TENANCY_FIX_DEPLOYMENT.md
├── security/                 # Security audits
│   ├── CRITICAL_SAME_TEACHER_LEAK.md
│   └── MULTI_TENANCY_AUDIT.md
├── development/              # Dev guides
│   ├── DEPRECATED_CODE_PATTERNS.md
│   └── TESTING_SUMMARY.md
└── archive/                  # Historical docs
```

---

## Testing Requirements

**See `.claude/rules/testing.md` for complete requirements.**

### Test Coverage Rules

- **Every new route** must have at least one test
- **Every new model** must have CRUD tests
- **Every bug fix** must have a regression test
- **Multi-tenancy** features must have scoping tests

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_teacher_recovery.py

# Run with coverage
pytest --cov=app tests/

# Run tests matching pattern
pytest -k "recovery"
```

### Test Structure

```python
def test_feature_name(client, app):
    """Test description explaining what this verifies."""
    # Setup: Create necessary data

    # Execute: Perform the action

    # Assert: Verify expected behavior

    # Cleanup: Usually handled by fixtures
```

---

## Security Principles

**See `.claude/rules/security.md` for complete guidelines.**

### Critical Security Rules

1. **PII Encryption**
   - All student names encrypted at rest
   - Use `encrypt_value()` and `decrypt_value()` from `hash_utils.py`

2. **Password Security**
   - All passwords salted AND peppered
   - Use `hash_password()` and `verify_password()` from `hash_utils.py`

3. **TOTP 2FA**
   - All admin accounts require TOTP
   - Never store TOTP secrets in plaintext

4. **CSRF Protection**
   - All forms include `{{ form.csrf_token }}`
   - All POST/PUT/DELETE routes validate CSRF

5. **Input Validation**
   - Always validate and sanitize user input
   - Use WTForms validators
   - Never trust client-side validation alone

6. **SQL Injection Prevention**
   - Always use SQLAlchemy ORM, never raw SQL
   - If raw SQL is absolutely necessary, use parameterized queries

---

## Multi-Tenancy Scoping

**See `.claude/rules/multi-tenancy.md` for complete rules.**

### The Golden Rule

**EVERY query involving student data MUST be scoped by `join_code`.**

### Critical Context

- A **teacher** may teach multiple class periods
- A **student** may be enrolled in multiple periods (different teachers or same teacher)
- Each class period has a unique `join_code`
- `join_code` is the ABSOLUTE source of truth for data isolation

### Examples of Proper Scoping

```python
# ✅ CORRECT - Scoped by join_code
students = Student.query.join(StudentBlock).filter(
    StudentBlock.join_code == current_join_code
).all()

# ✅ CORRECT - Transaction scoped by join_code
transactions = Transaction.query.filter_by(
    join_code=current_join_code
).all()

# ❌ WRONG - Not scoped, will leak data across periods
students = Student.query.filter_by(
    teacher_id=current_teacher_id
).all()
```

### Tables That MUST Be Scoped

- `Student` (via `StudentBlock`)
- `Transaction`
- `TapEvent`
- `PayrollSettings`
- `RentSettings`
- `BankingSettings`
- `InsurancePolicy` (via `InsurancePolicyBlock`)
- `StoreItem` (via `StoreItemBlock`)
- All student-related data

---

## Common Pitfalls

### 1. Database Migration Issues

**Problem:** Modifying models without creating migrations, or creating broken migrations.

**Solution:**
- Always use the migration workflow in `.claude/rules/database-migrations.md`
- Test migrations before committing
- Never edit old migrations after they're merged

### 2. Multi-Tenancy Data Leaks

**Problem:** Queries returning data from other class periods.

**Solution:**
- Always scope queries by `join_code`
- Add multi-tenancy tests for every student-related feature
- Review `.claude/rules/multi-tenancy.md` before any student data query

### 3. Inconsistent Documentation

**Problem:** Features added without updating docs.

**Solution:**
- Update CHANGELOG.md for EVERY change
- Update relevant docs in `docs/` directory
- Check `.claude/rules/documentation.md` for what to update

### 4. Missing Tests

**Problem:** Features or bug fixes without test coverage.

**Solution:**
- Write tests BEFORE or WITH feature implementation
- Every bug fix needs a regression test
- See `.claude/rules/testing.md` for requirements

### 5. Security Vulnerabilities

**Problem:** Forgetting CSRF, exposing PII, or weak authentication.

**Solution:**
- Review `.claude/rules/security.md` before ANY auth/data handling code
- Use the existing encryption and hashing utilities
- Never skip CSRF protection

---

## Workflow Checklist

### For New Features

- [ ] Read existing relevant code
- [ ] Create/update database models if needed
- [ ] Generate and test migration
- [ ] Implement feature with proper scoping
- [ ] Add CSRF protection if needed
- [ ] Write comprehensive tests
- [ ] Update CHANGELOG.md
- [ ] Update relevant documentation
- [ ] Run full test suite
- [ ] Commit with descriptive message

### For Bug Fixes

- [ ] Identify root cause
- [ ] Write regression test that fails
- [ ] Implement fix
- [ ] Verify test now passes
- [ ] Run full test suite
- [ ] Update CHANGELOG.md
- [ ] Document in relevant docs if needed
- [ ] Commit with descriptive message

### For Database Changes

- [ ] Modify model in `app/models.py`
- [ ] Generate migration: `flask db migrate -m "description"`
- [ ] Review generated migration file
- [ ] Test upgrade: `flask db upgrade`
- [ ] Test downgrade: `flask db downgrade`
- [ ] Re-upgrade: `flask db upgrade`
- [ ] Run tests: `pytest`
- [ ] Update docs/technical-reference/database_schema.md if needed
- [ ] Update CHANGELOG.md
- [ ] Commit migration with model changes

---

## Additional Resources

- **Detailed Rules:** See `.claude/rules/` directory for in-depth guidance
- **Project History:** `PROJECT_HISTORY.md` for context and philosophy
- **Development Priorities:** `DEVELOPMENT.md` for roadmap and planned features
- **Security Audits:** `docs/security/` for past security reviews
- **Architecture:** `docs/technical-reference/architecture.md`

---

## Questions or Clarifications?

When uncertain about:
- **Architecture decisions** → Review `docs/technical-reference/architecture.md`
- **Database design** → Review `docs/technical-reference/database_schema.md`
- **Multi-tenancy** → Review `docs/security/MULTI_TENANCY_AUDIT.md`
- **Deployment** → Review `docs/operations/DEPLOYMENT.md`

Always prefer reading existing code and documentation before making assumptions.

---

**Last Updated:** 2025-12-27
**For:** Claude Code and AI assistants working on Classroom Token Hub
