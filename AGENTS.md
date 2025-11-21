# Agent Handoff Notes

These notes orient future agents working on this repository—especially ongoing multi-tenancy hardening—so changes stay consistent and low-disruption.

## Quickstart
- **Branch:** work (current).
- **Tests:** run `pytest -q` before committing; add focused tests for tenancy helpers when changing scoping logic.
- **App entry:** `wsgi.py`; Flask app factory in `app/__init__.py`.
- **Maintenance mode:** toggle via env flags (see `templates/maintenance.html`) to present the downtime page during risky migrations.

## Multi-Tenancy Snapshot
- Students have a **primary owner** (`teacher_id`, still nullable pending enforcement) and a **many-to-many association** via `student_teachers` for shared accounts.
- Scoped query helpers live in `app/auth.py` (`_scoped_students`, `_get_student_or_404`, `_get_student_by_username_or_404`). Admin routes in `app/routes/admin.py` and system-admin tools in `app/routes/system_admin.py` rely on these—prefer them over direct `Student.query` calls.
- Session stores `admin_id` and `is_system_admin`; route guards expect both.
- Maintenance page and middleware exist to keep downtime user-friendly during migrations.

## High-Priority Follow-Ups
1. **Database hardening**
   - Add migration to enforce `teacher_id` NOT NULL once all students are mapped.
   - Add DB unique constraint on `(student_id, admin_id)` in `student_teachers`.
   - Define safe ON DELETE behavior for admins (reassign primary before delete).
2. **Code audit**
   - Replace any residual direct `Student.query.get` usage outside helpers.
   - Ensure legacy paths handle missing primary owner gracefully until NOT NULL lands.
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
- Update documentation (`docs/development/MULTI_TENANCY_TODO.md`) when milestone status changes.

## Checklist Before PR
- Tests pass locally (`pytest -q`).
- Migrations reviewed for safety (lock impact, backfill steps, maintenance banner plan).
- UI changes include screenshots when visually meaningful (if browser tool available).
- Final summary cites files and commands per system instructions.
