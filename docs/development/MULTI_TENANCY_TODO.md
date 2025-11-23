# Multi-Tenancy Implementation - TODO

## Overview
The multi-teacher model is live: students can be shared across teachers through `student_teachers`, scoped query helpers enforce isolation, and system admins can manage ownership. Primary ownership is still stored on `students.teacher_id`, and scoped helpers consider that column the source of truth while the migration to move primary ownership into the link table is in progress.

## Current State
- ✅ Admin (teacher) accounts with TOTP-only authentication
- ✅ System admin accounts with global visibility
- ✅ Students linked to teachers via `student_teachers` with a unique constraint
- ✅ Scoped helpers in `app/auth.py` (`get_admin_student_query`, `get_student_for_admin`) used across admin routes
- ✅ CSV/manual creation auto-links the creating teacher; system admins can manage sharing and primary ownership via `/sysadmin/student-ownership`
- ✅ Maintenance-mode banner/page available for low-disruption migrations
- ⚠️ `students.teacher_id` remains the authoritative primary owner column; code still scopes access off this field alongside `student_teachers`

## Goals
- Teachers should only see/manage their own students (including shared students)
- System admins should see everything
- Student creation/upload must always assign at least one teacher link
- Clear path for reassigning or transferring students between teachers

## Database Notes
- `student_teachers` enforces uniqueness on (`student_id`, `admin_id`) and cascades deletes
- `students.teacher_id` is currently the primary owner marker and must be retired after all records are mapped to links and access control is updated to treat the link as authoritative
- Consider ON DELETE behavior for admins that are primary owners before dropping the column

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

## Migration Strategy
1. **Pre-checks**: confirm every student has at least one `student_teachers` row; identify any orphaned links.
2. **Maintenance Banner**: enable maintenance mode during migration window if risk is medium/high.
3. **Migration**: drop/lock `students.teacher_id`, ensure foreign keys and indexes are optimized for scoped queries.
4. **Post-checks**: run smoke tests on admin/student portals and payroll/attendance with shared students.

## Success Criteria
- Teachers see only their students (or shared students) across all admin views
- System admins retain global access
- No routes bypass scoped helpers
- Migration is documented with clear rollback steps
