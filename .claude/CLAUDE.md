# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Classroom Token Hub — a multi-tenant educational banking simulation. Flask + SQLAlchemy + PostgreSQL. Python 3.10+. License: PolyForm Noncommercial 1.0.0.

**Active branch:** `CTH_v2.0` — all work merges here, never to `main`. Older docs call this
same branch `codex/v2.0`; that name is retired and no ref by it exists. If a tool, workflow,
or instruction names `codex/v2.0`, it is stale and pointing at nothing — fix it rather than
creating the branch.

## Commands

```bash
# Run all tests (requires TEST_DATABASE_URL in .env pointing to a Postgres DB)
pytest

# Run a single test file
pytest tests/test_student_recovery.py

# Run tests matching a pattern
pytest -k "recovery"

# Run with coverage
pytest --cov=app tests/

# Database migrations
flask db heads          # Must show exactly 1 head
flask db current        # Note current revision before generating
flask db migrate -m "Add X to Y"
flask db upgrade
flask db downgrade      # Test rollback
flask db upgrade        # Re-apply

# Start dev server
flask run

# Production entry point
gunicorn wsgi:app
```

Tests run against a real Postgres database (not SQLite). `conftest.py` drops and recreates the schema per session. Set `FEAT_BYPASS_AUDIT=1` to enable FEAT bypass mutation auditing.

## Architecture

### Identity Model (Constitutional — INV-ARC-019, DOM-IDEN-001)

```
User (users)              — global auth principal (login, credentials, recovery)
Seat (seats)              — class-local operational actor (ALL activity keys off seat_id)
IdentityProfile           — display-only name/identity, 1:1 with Seat
ClassEconomy (classes)    — isolation boundary; class_id (UUID) is canonical, join_code is public alias
```

**Resolution chain:** `User.id` → `Seat` (via `Seat.user_id`) → `IdentityProfile` (via `IdentityProfile.seat_id`)

**CanonicalContext** (`app/services/context_resolver.py`): Frozen dataclass with `user_id`, `class_id`, `seat_id`, `actor_role`. Accessing `join_code`, `teacher_id`, `student_id`, or `block` on it raises `AttributeError` by design.

**Legacy tables still in runtime:** `Admin` (teachers table), `Student` (students table), `TeacherBlock`, `StudentTeacher`, `ClassMembership`. These are bridge-period artifacts. The `Student` table is NOT part of the canonical identity model — `INV-IDEN-001` states "No separate students or teachers tables." Do not introduce new dependencies on these tables.

### Mutation Model (FEAT Layer)

All state mutation goes through `app/feats/`. Routes must not call `db.session.add/commit` on domain models directly.

```
Route → FEAT (app/feats/) → Domain Services (app/services/) → commit
```

GET handlers must be pure — no DB writes (INV-ARC-007).

### Multi-Tenancy

Every query involving student/seat data MUST be scoped by `class_id`. `join_code` is acceptable as an ingress alias but must resolve to `class_id` before any authority-sensitive operation. Never scope by `teacher_id` alone. See `.claude/rules/multi-tenancy.md`.

### Blueprint Layout

| Blueprint | Prefix | File |
|-----------|--------|------|
| admin | `/admin` | `app/routes/admin.py` (~12K lines) |
| student | `/student` | `app/routes/student.py` (~4K lines) |
| analytics | `/admin/analytics` | `app/routes/analytics.py` |
| sysadmin | `/sysadmin` | `app/routes/system_admin.py` |
| api | `/api` | `app/routes/api.py` |
| recovery | `/recovery` | `app/routes/recovery.py` |
| main | `/` | `app/routes/main.py` |

### Key Services

- `app/services/context_resolver.py` — `resolve_canonical_context()`, the sole legal way to get identity in routes
- `app/services/ledger_service.py` — balance reads (seat+class scoped)
- `app/services/identity_service.py` — identity resolution helpers
- `app/auth.py` — decorators (`admin_required`, `login_required`), session utilities
- `app/feats/base.py` — `feat_shell` decorator, `FEATContext` manager

### Test Helpers

- `tests/helpers/v2_fixtures.py` — `make_admin()`, `make_sysadmin()` with proper credential hashing
- `tests/helpers/class_scope.py` — `create_class_scope()` builds canonical User+Seat+ClassEconomy+IdentityProfile fixtures; `make_student_seat()` and `make_student_with_seat()` for student test data
- `tests/helpers/context_factory.py` — canonical context mocking
- `tests/helpers/admin_context.py` — admin session setup

## Critical Rules

1. **Read before writing.** Never modify files you haven't read.
2. **Scope by `class_id`.** Every student/seat query needs class isolation. See `.claude/rules/multi-tenancy.md`.
3. **Mutate through FEATs.** No direct `db.session.add/commit` in routes. See `app/feats/base.py`.
4. **Migrations require idempotency helpers.** Copy helpers from `migrations/migration_template.py.mako`, wrap all CREATE ops in existence checks. See `.claude/rules/database-migrations.md`.
5. **CSRF on all forms.** Include `{{ form.csrf_token }}` in templates, validate on POST.
6. **Encrypt PII.** Use `PIIEncryptedType` for names. Use `hash_password()`/`verify_password()` from `hash_utils.py`.
7. **`class_id` is canonical, `join_code` is alias.** New domain queries must use `class_id`. `join_code` is only for ClassEconomy boundary lookups and user-facing display.
8. **`seat_id` is the activity anchor.** All activity records (transactions, attendance, hall passes) key off `seat_id`, not `student_id`.
9. **No GET side effects.** GET handlers must not write to the database.

## Documentation Hierarchy

Constitutional authority flows: `INV-CORE → INV-ARC → DOM → FEAT`

- `docs/INVARIANT/CORE/` — foundational invariants (highest authority)
- `docs/INVARIANT/ARCHITECTURE/` — architectural invariants (INV-ARC-019 governs identity)
- `docs/DOMAIN/` — domain authority specs (DOM-IDEN-001 governs identity/class binding)
- `docs/FEATURE-EXECUTION/` — FEAT contracts (execution-level, subordinate to above)
- `docs/TRACKING/` — migration status and audit tracking
- `.claude/rules/` — detailed development rules (testing, migrations, security, multi-tenancy, docs)

When specs and implementation disagree, the constitutional docs (`INV-*`, `DOM-*`) define the target state. Implementation is often in a transitional bridge state.

## Active Migration Context

The codebase is mid-migration from v1 (legacy `Student`/`Admin` tables as identity authority) to v2 (`User`/`Seat` as canonical identity). Key implications:

- Many routes still resolve `Student` objects and use `student_id` — this is legacy bridge code, not the target architecture
- Credentials are currently duplicated on both `Student` and `User` during the bridge period
- `ClassMembership` is deprecated; `ClassEconomy` is the canonical teacher-to-class linkage
- The claim flow (`student.py:claim_account`) currently creates `Student` records — this violates INV-IDEN-001/INV-IDEN-010 and is under active remediation
- `block`/`period` is display metadata only, never a scoping key

## Common Mistakes

- **`Seat.user_id` ≠ `Student.id`**: `Seat.user_id` points to `User.id`. Querying `Seat.filter_by(user_id=student.id)` is always wrong.
- **Teacher ownership ≠ class scope**: `teacher_id` alone returns data across all class periods. Always add `class_id`.
- **Using `join_code` for domain queries**: Domain models have both `class_id` and `join_code` columns. Use `class_id` for filtering; `join_code` is only for ClassEconomy lookups.
- **Bypassing FEAT layer**: Adding `db.session.commit()` directly in a route handler. Wrap in a FEAT instead.
- **GET handlers with writes**: Reconciliation, interest posting, or lazy expiration in GET handlers violates INV-ARC-007.
