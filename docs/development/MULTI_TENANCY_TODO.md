# Multi-Tenancy Implementation - TODO

## Overview
This document tracks the multi-tenancy rollout. The core implementation is complete: students now have a primary owner (`teacher_id`), teachers are auto-linked on creation/upload, and a many-to-many `student_teachers` table allows multiple teachers to collaborate on the same student account without duplicating ledgers. Tenant-aware query helpers, ownership enforcement, and system-admin tooling for sharing/reassignment are in place.

## Current State
- ✅ System has Admin (teacher) accounts
- ✅ System has Student accounts
- ✅ System has SystemAdmin accounts (super users)
- ✅ Students have a primary teacher (`teacher_id`) and a `student_teachers` association table for shared access
- ✅ All admin-facing queries are scoped via `_scoped_students()` and related helpers; 404s are returned for cross-tenant access
- ✅ CSV/manual creation auto-links the creating teacher; system admins can manage sharing and primary ownership via `/sysadmin/student-ownership`
- ✅ Maintenance-mode banner/page available for low-disruption migrations
- ⚠️ `teacher_id` remains nullable for backfill safety; some legacy references still expect a primary owner

## Goals
- Teachers should only see their own students
- Teachers should only be able to manage their own students
- System admins should see everything (super user privileges)
- Students should be assigned to a specific teacher during creation
- Support for transferring students between teachers

## Database Changes Required

### 1. Add teacher_id to Students table (DONE)
`migrations/versions/b73c4d92eadd_add_teacher_id_to_students.py` adds the nullable `teacher_id` column with FK to `admins.id` and an index for scoping. Backfill and NOT NULL enforcement are deferred until data is mapped.

### 2. Add student_teachers association (DONE)
`migrations/versions/c1c6f7e5e3a0_add_student_teacher_association.py` introduces the sharing table and backfills from existing `teacher_id` values so primary owners are also linked in the association.

### 3. Remaining schema follow-ups
- [ ] Add a migration to enforce `teacher_id` NOT NULL after all students are mapped
- [ ] Consider ON DELETE behavior (e.g., set primary to another linked teacher before admin deletion)
- [ ] Add unique constraint on (`student_id`, `admin_id`) at the DB level (currently enforced in code/tests)

### 2. Update Student Model
```python
class Student(db.Model):
    # ... existing fields ...
    teacher_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=False)

    # Relationship
    teacher = db.relationship('Admin', backref='students')
```

## Code Changes Required

### 1. Student Creation/Upload (DONE)
- CSV upload and manual creation auto-assign the current teacher and create a `student_teachers` link; system admins can add/override owners.

### 2. Student Queries - Add Filtering (DONE)
- All admin routes now rely on scoped helpers (`_scoped_students`, `_get_student_or_404`, `_get_student_by_username_or_404`) to enforce tenant isolation while allowing shared-student access for linked teachers.

### 3. Session Management (DONE)
- Admin login stores `admin_id` and `is_system_admin`; route guards validate these fields and fail closed.

### 4. System Admin Dashboard (DONE)
- `/sysadmin/student-ownership` lists students, shows owners, allows adding/removing teachers, and sets primary ownership with safe fallback when removing a primary teacher.

### 5. Follow-up Code Tasks
- [ ] Replace any remaining direct `Student.query.get` usage outside helpers (audit before making `teacher_id` NOT NULL)
- [ ] Add graceful handling when a student has no primary owner (should be impossible post-enforcement)
- [ ] Consider adding background job/CLI to reconcile links if future imports bypass the UI

## UI Changes Required

### 1. Admin Dashboard (DONE)
- Student lists and detail pages scope to linked teachers and show ownership where relevant.

### 2. Student Upload (DONE)
- Teachers auto-assign themselves; system admins can adjust ownership after import.

### 3. System Admin Dashboard (DONE)
- Ownership management page plus sidebar entry for quick access; supports add/remove and primary reassignment.

### 4. Follow-up UI Tasks
- [ ] Add optional filters for system admins to view students by primary teacher vs shared links
- [ ] Add flash guidance when a student has multiple teachers (to clarify which teacher initiated an action)

## Testing Requirements

### 1. Unit/Integration Tests (DONE)
- Coverage added for admin session metadata, scoped queries, cross-teacher sharing, and system-admin ownership management.

### 2. Follow-up Tests
- [ ] Add regression coverage for payroll/attendance with shared students across teachers
- [ ] Add tests for maintenance-mode guardrails around tenancy helpers (ensure helpers short-circuit cleanly)
- [ ] Add DB-level uniqueness test for `student_teachers` once constraint is added

## Migration Strategy

### Phase 1: Database Setup (DONE)
- Nullable `teacher_id` added with index; `student_teachers` association backfilled.

### Phase 2: Code Updates (DONE)
- Scoped helpers, session metadata, and shared-teacher support shipped.

### Phase 3: UI Updates (DONE)
- Admin views scoped; system-admin ownership UI added; maintenance page available for low-disruption toggles.

### Phase 4: Testing (PARTIAL)
- Automated coverage for tenancy and ownership flows exists; expand to payroll/attendance sharing scenarios.

### Phase 5: Deployment Hardening (PENDING)
- [ ] Final migration to make `teacher_id` NOT NULL after data mapping
- [ ] Run backfill/reconciliation script in staging, then production
- [ ] Schedule brief maintenance banner (no hard downtime expected) during NOT NULL migration as a safety net

## Backwards Compatibility

**Breaking Changes:**
- Existing students need teacher assignment before enforcement
- Teachers will suddenly see fewer students (only theirs)
- Existing integrations/scripts may need updates

**Mitigation:**
- Add migration script to assign students fairly
- System admin retains global view
- Provide clear documentation for teachers

## Future Enhancements

### 1. Teacher Collaboration
- ✅ Teachers can share students via `student_teachers` while keeping a single account/ledger

### 2. Observability
- [ ] Add audit logging for ownership changes (currently covered by flash messages and DB state only)

### 3. Operations
- [ ] Publish a runbook for the NOT NULL enforcement migration, including pre/post checks and maintenance banner usage
- [ ] Co-teaching support
- [ ] Student transfer requests

### 2. Department/School Hierarchy
- [ ] Group teachers into departments
- [ ] Department admins can see all students in department
- [ ] School admins can see all students in school

### 3. Student Self-Selection
- [ ] Students choose their teacher during setup
- [ ] Teacher approval workflow

## Estimated Effort
- Database changes: 2-3 hours
- Code updates: 8-10 hours
- UI updates: 4-6 hours
- Testing: 4-6 hours
- Documentation: 2-3 hours
- **Total: 20-28 hours (3-4 days)**

## Priority
**Medium-High** - Important for multi-teacher deployments, but current single-teacher setups work fine.

## Dependencies
- None (standalone feature)

## Risks
- Data migration complexity for existing deployments
- Potential for data loss if teacher assignments are incorrect
- Teachers may be surprised by suddenly seeing fewer students

## Success Criteria
- [x] Teachers can only see their own students
- [x] System admins can see all students
- [x] No unauthorized access to other teachers' data
- [x] Clean migration path for existing data
- [x] All tests passing
- [x] Documentation updated
