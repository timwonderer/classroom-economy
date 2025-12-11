# Agent Handoff Notes

These notes orient future agents working on this repository—especially ongoing multi-tenancy hardening—so changes stay consistent and low-disruption.

## Quickstart

- **Branch:** work (current).
- **Tests:** run `pytest -q` before committing; add focused tests for tenancy helpers when changing scoping logic.
- **App entry:** `wsgi.py`; Flask app factory in `app/__init__.py`.
- **Maintenance mode:** toggle via env flags (see `templates/maintenance.html`) to present the downtime page during risky migrations.

## Database Migrations - CRITICAL FOR AGENTS

**⚠️ ALWAYS follow this workflow when creating migrations to prevent multiple heads errors:**

### Before Creating ANY Migration

1. **ALWAYS sync with the latest code first:**

   ```bash
   git fetch origin main
   git merge origin/main
   ```

2. **Verify there is exactly ONE migration head:**

   ```bash
   flask db heads  # MUST show exactly 1 head
   ```

   If you see multiple heads, STOP and create a merge migration first:

   ```bash
   flask db merge heads -m "Merge migration heads"
   ```

3. **Check the current migration revision:**

   ```bash
   flask db current  # Note this revision ID
   ```

### Creating a Migration

1. **Make your model changes in `app/models/`**

2. **Create the migration:**

   ```bash
   flask db migrate -m "Clear description of change"
   ```

3. **IMMEDIATELY verify the new migration:**
   - Open the generated file in `migrations/versions/`
   - Verify `down_revision` matches what `flask db current` showed
   - If it doesn't match, DELETE the migration and restart the workflow

4. **Test the migration:**

   ```bash
   flask db upgrade    # Apply it
   flask db downgrade  # Roll it back
   flask db upgrade    # Apply it again
   ```

5. **Verify single head after creation:**

   ```bash
   flask db heads  # MUST still show exactly 1 head
   # OR use the quick check script:
   bash scripts/check-migration-heads.sh
   ```

### Quick Check Script

Before pushing ANY PR that includes migrations, run:

```bash
bash scripts/check-migration-heads.sh
```

This script will immediately tell you if there are multiple heads and provide fix instructions.

### Why This Matters

The repository has experienced recurring "multiple heads" errors during deployment because agents created migrations without syncing first. Each time this happens:

- Deployment blocks with errors
- Manual intervention required on production
- Risk of data inconsistencies

**The pre-push hook can't catch this when working through the web interface**, so agents MUST follow this workflow manually.

## Multi-Tenancy Snapshot

- **Join codes are the source of truth for class/period isolation.** Students pick a join code from their claimed seats, and all student-facing balances/transactions are scoped by that join code (see `get_current_class_context` in `app/routes/student.py` and the `Transaction.join_code` comment in `app/models.py`).
- **Teacher ownership lives in the link table.** Student access for admins is enforced solely through the `student_teachers` association; the legacy `students.teacher_id` column is deprecated and ignored by scoped helpers (see `get_admin_student_query` in `app/auth.py`).
- Scoped query helpers like `get_admin_student_query` and `get_student_for_admin` are centralized in `app/auth.py`. Admin routes in `app/routes/admin.py` and system-admin tools in `app/routes/system_admin.py` rely on these—prefer them over direct `Student.query` calls.
- Student/admin sessions continue to store `admin_id` and `is_system_admin` for authorization checks; student sessions also persist the selected `current_join_code` for per-class context.
- Maintenance page and middleware exist to keep downtime user-friendly during migrations.

## High-Priority Follow-Ups

1. **Database hardening**
   - Plan the retirement of legacy `students.teacher_id` once all routes depend solely on `student_teachers`.
   - Consider enforcing non-null `join_code` for new ledger/attendance records after backfill verification.
   - Define safe ON DELETE behavior for admins once the legacy column is removed (e.g., reassign links before delete).
2. **Code audit**
   - Replace any residual direct `Student.query.get` usage outside helpers.
   - Remove reliance on the deprecated `teacher_id` column in any remaining legacy paths.
3. **Testing gaps**
   - Add shared-student coverage for payroll and attendance flows.
   - Add DB-level uniqueness test once constraint exists.
4. **Operational docs**
   - Write a runbook for the NOT NULL migration (pre/post checks, maintenance toggle, backfill verification).

## PII/Privacy

- Keep PII minimal (current design uses non-PII identifiers and encrypted first names). Avoid adding new PII fields; prefer hashes or initials.

## Coding Conventions

- Prefer scoped helpers over ad-hoc filters for tenant access.
- Keep try/except blocks off import statements (per repo guidance).
- Update documentation (`DEVELOPMENT.md`) when milestone status changes.

## Checklist Before PR

- Tests pass locally (`pytest -q`).
- Migrations reviewed for safety (lock impact, backfill steps, maintenance banner plan).
- UI changes include screenshots when visually meaningful (if browser tool available).
- Final summary cites files and commands per system instructions.

## PR Template

Please use the following template when creating a PR

<!-- Start of Document -->
## Description

<!-- Provide a brief description of the changes in this PR -->

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Other (please describe):

## Testing

<!-- Describe the tests you ran and how to reproduce them -->

- [ ] Tested locally
- [ ] All existing tests pass
- [ ] Added new tests for new functionality

## Database Migration Checklist

<!-- If this PR includes a database migration, complete the following checklist -->

**Does this PR include a database migration?** [ ] Yes / [ ] No

If **Yes**, confirm:

- [ ] Synced with `main` branch immediately before running `flask db migrate`
- [ ] Migration file reviewed and verified correct `down_revision`
- [ ] Tested `flask db upgrade` successfully
- [ ] Tested `flask db downgrade` successfully
- [ ] Confirmed only ONE migration head exists (pre-push hook should verify this)
- [ ] Migration has a descriptive message/filename
- [ ] Breaking changes or data migrations documented in PR description

**Migration file location:**
<!-- e.g., migrations/versions/abc123_add_user_email.py -->

## Checklist

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code where necessary, particularly in hard-to-understand areas
- [ ] I have updated the documentation accordingly
- [ ] My changes generate no new warnings or errors
- [ ] I have read and followed the [contributing guidelines](../CONTRIBUTING.md)

## Related Issues

<!-- Link any related issues here -->

Closes #

## Additional Notes

<!-- Any additional information that reviewers should know -->

<!-- End of Document -->