# Multi-Tenancy Implementation - TODO

## Overview
The multi-teacher model is live: students can be shared across teachers through `student_teachers`, scoped query helpers enforce isolation, and system admins can manage ownership. **Join codes are the source of truth for per-class isolation**, and the `student_teachers` link table is the authoritative ownership model; `students.teacher_id` is deprecated and ignored by access control helpers.

## Current State
- ✅ Admin (teacher) accounts with TOTP-only authentication
- ✅ System admin accounts with global visibility
- ✅ Students linked to teachers via `student_teachers` with a unique constraint (authoritative source of truth)
- ✅ Scoped helpers in `app/auth.py` (`get_admin_student_query`, `get_student_for_admin`) used across admin routes
- ✅ CSV/manual creation auto-links the creating teacher; system admins can manage sharing/links via `/sysadmin/student-ownership`
- ✅ Maintenance-mode banner/page available for low-disruption migrations
- ✅ Student sessions persist the current join code to scope balances/transactions per class/period

## Goals
- Teachers should only see/manage their own students (including shared students)
- System admins should see everything
- Student creation/upload must always assign at least one teacher link
- Clear path for reassigning or transferring students between teachers

## Database Notes
- `student_teachers` enforces uniqueness on (`student_id`, `admin_id`) and cascades deletes
- `students.teacher_id` is deprecated; plan retirement after confirming all routes depend solely on `student_teachers`
- Consider ON DELETE behavior for admins with legacy references before dropping the column
- Join codes partition transactions/attendance; long-term goal is to enforce `join_code` NOT NULL once backfill is complete

## Code Notes
- Tenant-aware access is centralized in `app/auth.py`; avoid direct `Student.query.get` in routes
- Admin session stores `admin_id` and `is_system_admin`; route guards validate both
- System admin ownership UI: `/sysadmin/student-ownership`

## Remaining Tasks
- [ ] Add migration to drop/lock down legacy `students.teacher_id` once backfill is verified
- [ ] Publish runbook for the enforcement migration (pre-checks, maintenance toggle, rollback plan)
- [ ] Audit for any direct `Student.query` lookups in routes/services and replace with scoped helpers
- [ ] Add audit logging for ownership changes
- [ ] Extend automated tests for payroll/attendance flows with shared students
- [ ] Backfill legacy ledger/attendance records to ensure `join_code` is consistently populated (prep for NOT NULL)

## Migration Strategy
1. **Pre-checks**: confirm every student has at least one `student_teachers` row; identify any orphaned links.
2. **Maintenance Banner**: enable maintenance mode during migration window if risk is medium/high.
3. **Migration**: drop/lock `students.teacher_id` after verifying no remaining dependencies; ensure foreign keys and indexes are optimized for scoped queries and join-code enforcement.
4. **Post-checks**: run smoke tests on admin/student portals and payroll/attendance with shared students.

## Success Criteria
- Teachers see only their students (or shared students) across all admin views
- System admins retain global access
- No routes bypass scoped helpers
- Migration is documented with clear rollback steps
