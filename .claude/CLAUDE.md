# Claude Development Guide for Classroom Token Hub

This document provides essential guidance for Claude (or any AI assistant) working on the Classroom Token Hub project. Following these guidelines ensures consistency, prevents common pitfalls, and maintains the project's high standards.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Critical Rules](#critical-rules)
3. [Architecture Patterns](#architecture-patterns)
4. [FEAT Execution Model](#feat-execution-model)
5. [Domain Authority Model](#domain-authority-model)
6. [Database Migrations](#database-migrations)
7. [Documentation Standards](#documentation-standards)
8. [Testing Requirements](#testing-requirements)
9. [Security Principles](#security-principles)
10. [Multi-Tenancy Scoping](#multi-tenancy-scoping)
11. [Common Pitfalls](#common-pitfalls)
12. [Workflow Checklist](#workflow-checklist)

---

## Project Overview

**Classroom Token Hub** is an educational banking simulation platform for teaching financial literacy in classrooms. It's built with Flask, SQLAlchemy, PostgreSQL, and follows a multi-tenant architecture where:

- **Teachers** manage multiple class periods via join codes
- **Students** can be enrolled in multiple periods with different teachers
- **System Admins** oversee the entire platform

**Active Branch:** `codex/v2.0` — v2 architecture stabilization
**License:** PolyForm Noncommercial 1.0.0
**Python:** 3.10+
**Database:** PostgreSQL with Alembic migrations

### v2 Status

The codebase is in an active v2 rebuild on `codex/v2.0`. The v2 architecture introduces:
- A capability-based authority model (INV → DOM → FEAT hierarchy)
- `seat_id` as the primary activity anchor (replacing raw `student_id` usage)
- `class_id` (UUID) as the canonical class boundary (with `join_code` as its public alias)
- A `feats/` execution layer that owns all state mutation
- Domain-bounded services in `app/services/`

Legacy v1 models (`Admin`, `Student`, `TeacherBlock`, etc.) still exist and are used for authentication; the `User`/`Seat` unified identity model is present in the schema but not yet the primary auth path. When reading or writing code, always confirm which model layer is actually in use for the feature you are touching.

---

## Critical Rules

### MUST FOLLOW EVERY TIME

1. **ALWAYS read existing code before proposing changes**
   - Never suggest modifications to files you haven't read
   - Understand context before making changes

2. **ALWAYS scope database queries by `class_id` (or `join_code`)**
   - Every query for student/seat data MUST be scoped to the current class
   - `class_id` is the canonical UUID boundary; `join_code` is its public alias
   - `seat_id` anchors per-user activity within a class
   - See `.claude/rules/multi-tenancy.md` for detailed rules

3. **ALWAYS route state mutations through a FEAT**
   - Routes, background jobs, and CLI scripts MUST NOT call `db.session.add/commit` directly on domain models
   - All writes go through `app/feats/` — see [FEAT Execution Model](#feat-execution-model)

4. **ALWAYS create a migration for database schema changes**
   - Never modify models without creating a migration
   - See `.claude/rules/database-migrations.md` for the complete workflow

5. **ALWAYS update documentation when adding features**
   - Update CHANGELOG.md for all changes
   - Update relevant user guides and technical docs
   - See `.claude/rules/documentation.md` for standards

6. **ALWAYS write tests for new features**
   - Minimum: happy path + error cases
   - Include multi-tenancy scoping tests
   - See `.claude/rules/testing.md` for requirements

7. **NEVER commit secrets or PII**
   - Use environment variables for sensitive data
   - Encrypt PII at rest using the encryption utilities

8. **NEVER skip CSRF protection**
   - All forms must include CSRF tokens
   - All POST/PUT/DELETE routes must validate CSRF

---

## Architecture Patterns

### Blueprint Structure

```
app/
├── routes/
│   ├── admin.py          # Teacher/admin routes
│   ├── analytics.py      # Teacher analytics dashboard + APIs
│   ├── student.py        # Student routes
│   ├── system_admin.py   # System admin routes
│   ├── api.py            # API endpoints
│   ├── docs.py           # In-app documentation browser
│   ├── main.py           # Public/site routes
│   └── recovery.py       # Student recovery flow
├── feats/                # FEAT execution layer (all state mutation goes here)
│   ├── base.py
│   ├── admin_adjustment_feat.py
│   ├── insurance_claim_feat.py
│   ├── insurance_purchase_feat.py
│   ├── rent_payment_feat.py
│   ├── store_purchase_feat.py
│   ├── transaction_void_feat.py
│   └── transfer_feat.py
├── services/             # Domain-bounded read/validation services
│   ├── access_policy_service.py
│   ├── attendance_service.py
│   ├── balance_service.py
│   ├── identity_service.py
│   ├── ledger_service.py
│   ├── obligations_service.py
│   ├── store_service.py
│   └── tlcp.py
├── auth.py               # Auth helpers and scoped access helpers
├── models.py             # SQLAlchemy models (55+ runtime models)
├── utils/                # Utility and domain helpers
├── scheduled_tasks.py    # Background scheduler jobs
└── __init__.py           # App factory
```

### Key Files

- `wsgi.py` — Application entry point
- `app/forms.py` — WTForms form definitions
- `app/auth.py` — Admin/student access helpers and auth/session utilities
- `app/payroll.py` — Payroll automation logic
- `app/services/ledger_service.py` — Balance reads and ledger helpers (seat+class scoped)
- `app/services/balance_service.py` — Balance settlement helpers
- `app/utils/analytics_engine.py` — Analytics computation backend
- `app/utils/seat_scope.py` — Seat/class scope resolution helpers
- `app/scheduled_tasks.py` — Hourly and nightly background jobs

### Database Models

**55+ SQLAlchemy models.** The v2 canonical identity models are:

- **v2 canonical identity:**
  - `User` — global login principal (table exists; auth still uses legacy tables during transition)
  - `Seat` — class-local participant binding (`seat_id` is the primary activity anchor)
  - `IdentityProfile` — display identity (names, initials), one-to-one with `seats`
  - `ClassEconomy` — class universe anchor; `class_id` (UUID PK) is the canonical boundary; `join_code` is the public alias

- **Legacy auth (still active):**
  - `Admin` (teachers), `Student`, `SystemAdmin` — v1 tables still used for authentication
  - `TeacherBlock` — roster seat records (claim flow)
  - `StudentTeacher`, `ClassMembership` — ownership and membership records

- **Financial and attendance (seat-scoped):**
  - `Transaction`, `BalanceCache` — use `seat_id` + `class_id`
  - `PayrollSettings`, `RentSettings`, `BankingSettings`, `FeatureSettings` — scoped by `class_id`
  - `TapEvent`, `HallPassLog` — scoped by `join_code`/`class_id`

- **Support and observability:**
  - `Issue`, `IssueCategory`, `IssueStatusHistory`, `IssueResolutionAction`
  - `ErrorLog`, `ErrorEvent`, `ActorRequestTrace`, `UserReport`

- **Analytics:**
  - `AnalyticsAlert`, `AnalyticsSnapshot`, `AnalyticsEvent`

---

## FEAT Execution Model

The FEAT layer is the **only legal mechanism** for state mutation in v2.

### What is a FEAT?

A FEAT is an atomic orchestration unit that:
1. Resolves identity context (`user_id`, `seat_id`, `class_id`) before any domain interaction
2. Validates intent across domains (read-only domain guards)
3. Executes all state mutations within a **single transaction boundary**
4. Emits an auditable execution trace

### The Rule

```
Routes → call FEAT → FEAT calls domain services → FEAT commits
```

**Routes and background jobs MUST NOT:**
- call `db.session.add()` / `db.session.commit()` directly on domain models
- orchestrate multi-domain logic themselves
- bypass the FEAT layer

### FEAT directory: `app/feats/`

Existing FEATs: `transfer_feat`, `store_purchase_feat`, `rent_payment_feat`, `transaction_void_feat`, `insurance_claim_feat`, `insurance_purchase_feat`, `admin_adjustment_feat`.

Use `app/feats/base.py` (`feat_shell`) as the scaffolding for new FEATs.

### Domain Guard Pattern

Domain services expose capability checks as guards:

```python
# Domain guard — read-only, returns (allowed, reason)
allowed, reason = dom_led.check_solvency(seat_id, class_id, amount)
if not allowed:
    return deny(reason)

# Mutation only happens inside FEAT after all guards pass
```

### GET Requests Must Be Pure

**`INV-ARC-007`**: GET handlers must not trigger DB writes or commits. Any reconciliation, interest posting, or lazy expiration that currently happens on GET is a known v2 violation under active remediation. Do not introduce new GET-triggered writes.

---

## Domain Authority Model

The v2 authority hierarchy is: **INV → DOM → FEAT**

Specs live in `docs/`:
- `SPECS/` — target-state architecture and authority contracts
- `TRACKING/` — launch checklists and current status
- `INVARIANT/` — core invariants
- `DOMAIN/` — per-domain authority specs
- `FEATURE-EXECUTION/` — FEAT contracts

### Domain Summary

| Domain | Authority | Primary Tables |
|---|---|---|
| Identity & Class Binding (`DOM-IDEN-001`) | Global identity, seat binding, class creation | `users`, `seats`, `identity_profiles`, `classes` |
| Class Configuration (`DOM-CLASS-001`) | Policy/directives (rates, schedules, limits) | `payroll_settings`, `rent_settings`, `banking_settings`, `class_features` |
| Attendance (`DOM-ATT-001`) | Time-tracking facts and hall pass execution | `attendance_sessions`, `hall_pass_logs` |
| Obligations (`DOM-OBL-001`) | Seat-scoped debt lifecycles | `assessment_events`, `obligation_lifecycle` |
| Ledger (`DOM-LED-001`) | Monetary truth — domain-blind | `ledger_transaction`, `ledger_balance_snapshot` |
| Store & Entitlements (`DOM-STORE-001`) | Catalog and purchased perk redemption | `store_purchases`, `redemption_events`, `store_items` |
| Operations (`DOM-OPS-001`) | Observability, audit, incidents | `audit_log`, `operational_events`, `incidents` |
| Interpretation (`DOM-ITR-001`) | Behavioral and structural analytics signals | `interpretation_snapshots` |
| Support (`DOM-SUP-001`) | Issue lifecycle and communications | `issues`, `issue_resolution_actions`, `announcements` |

**Key invariants:**
- Domains MUST NOT call other domains directly
- All cross-domain coordination MUST occur inside a FEAT
- Domains expose read-only guard checks; they never mutate during validation
- `seat_id` is the primary key for all activity-tracking in non-identity domains
- `class_id` is the class boundary anchor; `join_code` is its public alias

---

## Database Migrations

**See `.claude/rules/database-migrations.md` for complete workflow.**

### Quick Reference

```bash
# 1. Sync with main FIRST
git fetch origin main && git merge origin/main

# 2. Verify single head
flask db heads  # must show exactly 1

# 3. Modify model in app/models.py
# 4. Generate migration
flask db migrate -m "Description of change"

# 5. Add idempotency helpers (column_exists, table_exists, etc.)
# 6. Wrap all CREATE ops in existence checks
# 7. Test upgrade
flask db upgrade

# 8. Test downgrade
flask db downgrade

# 9. Re-upgrade
flask db upgrade

# 10. Run tests
pytest tests/
```

### Migration Naming Convention

- `add_<field>_to_<table>` — Adding columns
- `create_<table>` — New tables
- `remove_<field>_from_<table>` — Removing columns
- `rename_<old>_to_<new>_in_<table>` — Renaming
- `add_<table>_<relationship>_relationship` — Adding relationships

### Common Migration Mistakes (DON'T DO THIS)

❌ Modifying models without creating migrations
❌ Editing old migration files after they're merged
❌ Creating migrations with generic names like "update database"
❌ Skipping migration testing before committing
❌ Forgetting to add idempotency helpers (`column_exists`, `table_exists`, etc.)
❌ Hardcoding constraint names in downgrade (use `get_foreign_keys_by_column()`)

---

## Documentation Standards

**See `.claude/rules/documentation.md` for complete standards.**

### Files to Update for New Features

1. **CHANGELOG.md** — All changes, following Keep a Changelog format
2. **DEVELOPMENT.md** — Add to roadmap or mark as completed
3. **README.md** — Update if it affects installation/quick start
4. **Architecture docs** in `docs/ARCHITECTURE/` — For architecture changes
5. **Domain specs** in `docs/DOMAIN/` — For domain authority changes

### Documentation Organization

```
docs/
├── README.md
├── INV-CORE-000_Core_Invariants.md   # Constitutional root
├── INV-CORE-001_Authority_Model.md   # Constitutional root
├── ARCHITECTURE/              # Cross-domain architectural rules
├── DOMAIN/                    # Per-domain authority specs
├── DOMAINS/                   # Domain-level design specs
├── FEATURE-EXECUTION/         # FEAT contracts
├── FEATURES/                  # Feature specifications
├── INVARIANT/                 # Core and architecture invariants
├── MAP/                       # Domain-to-FEAT capability maps
├── TESTING/                   # Test creation and validation
├── SPECS/                     # Target-state architecture specs
├── TRACKING/                  # Launch readiness and status
├── LOGS/                      # Historical audit and release logs
├── SECURITY/                  # Security audits, controls, incidents
├── STANDARD_OPERATING_PROCEDURES/  # Database, deployment, devops SOPs
├── self-hosting/              # Self-hosting guide
└── archive/                   # v1 docs (user-guides, GitHub Pages, etc.)
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

### Current Baseline (as of 2026-04-25)

`619 passed, 123 failed, 1 skipped` — active stabilization in progress. Reducing the failing count is an ongoing priority before v2 live test.

---

## Security Principles

**See `.claude/rules/security.md` for complete guidelines.**

### Critical Security Rules

1. **PII Encryption**
   - All student names encrypted at rest via `PIIEncryptedType`
   - Use `encrypt_value()` and `decrypt_value()` from `hash_utils.py`
   - No raw DOB storage; no contact info stored

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

**EVERY query involving student/seat data MUST be scoped by `class_id` (or `join_code`).**

### v2 Scoping Model

The canonical boundary is `class_id` (UUID from `class_economies`). `join_code` is its public-facing alias and both are acceptable scoping keys. `seat_id` anchors per-user activity within a class.

- **Class boundary:** `class_id` / `join_code`
- **Per-user activity anchor:** `seat_id`
- **Global identity:** `user_id` (for auth/recovery only — does NOT grant class scope)

```python
# ✅ CORRECT — seat + class scope
transactions = Transaction.query.filter_by(
    seat_id=seat_id,
    class_id=class_id,
).all()

# ✅ CORRECT — class membership scope
students = (
    Student.query
    .join(ClassMembership, ClassMembership.student_id == Student.id)
    .filter(ClassMembership.join_code == join_code)
    .all()
)

# ❌ WRONG — teacher/user ownership alone is not class scope
students = Student.query.all()

# ❌ WRONG — student_id without class scope
Transaction.query.filter_by(student_id=student_id).all()
```

### Getting Current Class Context

**Student routes:**
```python
from app.routes.student import get_current_class_context

context = get_current_class_context()
if not context:
    return redirect(url_for("student.select_class"))

join_code = context["join_code"]
class_id = context.get("class_id")
seat_id = context.get("seat_id")
```

**Admin routes:**
```python
join_code = session.get("current_join_code")
class_id = session.get("current_class_id")
```

### Tables That MUST Be Scoped

- `transactions` (by `seat_id` + `class_id`)
- `balance_cache` (by `seat_id` + `class_id`)
- `tap_events`, `hall_pass_logs` (by `join_code`/`class_id`)
- `student_blocks`, `payroll_settings`, `rent_settings`, `banking_settings`, `feature_settings`
- `store_purchases`, `student_items`, `student_insurance`, `insurance_claims`
- All student/seat-associated data

---

## Common Pitfalls

### 1. Bypassing the FEAT Layer

**Problem:** Writing `db.session.add/commit` directly in a route handler for domain models.

**Solution:** Route logic should invoke a FEAT from `app/feats/`. Add new FEATs when needed rather than adding mutation logic to routes.

### 2. Using `join_code` When `class_id` Is Available

**Problem:** New code added in v2 uses `join_code` as if it's the primary key when `class_id` is the canonical anchor.

**Solution:** Use `class_id` (UUID) for new domain-level queries. `join_code` is acceptable as a public-facing alias but the underlying join should resolve to `class_id` when possible.

### 3. Teacher Ownership ≠ Class Scope

**Problem:** Queries scoped only by `teacher_id` or `admin_id` return data across multiple class periods.

**Solution:** Always add `class_id`/`join_code` + seat/membership filter on top of ownership checks.

### 4. GET Handlers With Side Effects

**Problem:** Adding DB writes (reconciliation, lazy expiration, interest posting) inside GET handlers.

**Solution:** Never add new write-on-read patterns. Mutations must be explicitly triggered through a FEAT, not happen as a side effect of reading a page.

### 5. Ignoring Idempotency on New FEATs

**Problem:** New FEATs that don't accept or generate an `idempotency_key` can produce duplicate effects on retry.

**Solution:** Every FEAT must accept or generate an `idempotency_key` and check it before executing. Use `app/utils/transaction_idempotency.py` patterns.

### 6. Database Migration Issues

**Problem:** Missing idempotency helpers, hardcoded constraint names, or broken migration chains.

**Solution:** Follow `.claude/rules/database-migrations.md` exactly. Run the migration linter before committing.

---

## Workflow Checklist

### For New Features

- [ ] Read existing relevant code (routes, feats, services, models)
- [ ] Identify which domain(s) are involved
- [ ] Create/update database models if needed
- [ ] Generate and test migration (with idempotency helpers)
- [ ] Implement mutation logic inside a FEAT (`app/feats/`)
- [ ] Implement read/guard logic inside the relevant service (`app/services/`)
- [ ] Wire route to call the FEAT
- [ ] Add CSRF protection if needed
- [ ] Write comprehensive tests (including scoping tests)
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

- [ ] Sync with main: `git fetch origin main && git merge origin/main`
- [ ] Verify single head: `flask db heads`
- [ ] Modify model in `app/models.py`
- [ ] Generate migration: `flask db migrate -m "description"`
- [ ] Add idempotency helpers from `migrations/migration_template.py.mako`
- [ ] Wrap all CREATE ops in existence checks
- [ ] Run linter: `python scripts/lint_migrations.py migrations/versions/abc*.py`
- [ ] Test upgrade: `flask db upgrade`
- [ ] Test downgrade: `flask db downgrade`
- [ ] Re-upgrade: `flask db upgrade`
- [ ] Verify single head still: `flask db heads`
- [ ] Run tests: `pytest`
- [ ] Update `docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md` if significant
- [ ] Update CHANGELOG.md
- [ ] Commit migration with model changes

---

## Additional Resources

- **v2 Invariants:** `docs/INVARIANT/`
- **v2 Domain specs:** `docs/DOMAIN/`
- **v2 FEAT specs:** `docs/FEATURE-EXECUTION/`
- **v2 Architecture specs:** `docs/SPECS/`
- **v2 Launch status:** `docs/TRACKING/`
- **Detailed Rules:** `.claude/rules/` for in-depth guidance
- **Security Audits:** `docs/SECURITY/`
- **Architecture:** `docs/ARCHITECTURE/`

---

## Questions or Clarifications?

When uncertain about:
- **v2 architecture decisions** → `docs/DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md`
- **FEAT execution rules** → `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- **Core invariants** → `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- **Multi-tenancy** → `.claude/rules/multi-tenancy.md` and `docs/SECURITY/AUDITS/SEC-AUD-015_Multi_Tenancy_Audit.md`
- **Database design** → `docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md`
- **Deployment** → `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide.md`

Always prefer reading existing code and documentation before making assumptions.

---

**Last Updated:** 2026-04-25
**Branch:** `codex/v2.0`
**For:** Claude Code and AI assistants working on Classroom Token Hub
