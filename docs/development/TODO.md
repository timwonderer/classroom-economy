# Classroom Token Hub - Development TODO List

**Last Updated:** 2025-11-23  
**Purpose:** Track active work and near-term follow-ups for the platform.

---

## 🟠 HIGH PRIORITY

### 1. Multi-Teacher Hardening
- **Status:** In progress (sharing + scoped queries shipped)
- **Next Steps:**
  - [ ] Finalize migration to remove legacy reliance on `students.teacher_id` (documented as deprecated in models)
  - [ ] Publish runbook for the NOT NULL enforcement / teacher reassignment path
  - [ ] Audit for any direct `Student.query.get` usages outside scoped helpers and replace with `get_student_for_admin`
  - [ ] Add DB safeguard for ownership changes (decide ON DELETE strategy for admins with primary students)

### 2. Shared-Student Coverage
- **Status:** Pending
- **Next Steps:**
  - [ ] Add pytest coverage for payroll and attendance flows when students are linked to multiple teachers
  - [ ] Add DB-level uniqueness regression test for `student_teachers` (constraint exists at schema level)

### 3. Operational Safety
- **Status:** Pending
- **Next Steps:**
  - [ ] Maintenance/runbook steps for future schema changes that touch tenancy or payroll timing
  - [ ] Document pre/post checks for running migrations with maintenance mode enabled

---

## 🟡 MEDIUM PRIORITY

### 1. Admin Experience Polish
- [ ] Optional system-admin filters to view students by primary/shared teachers
- [ ] Clearer UI messaging when acting on shared students (who created a transaction, payroll scope hints)

### 2. Data Exports
- [ ] CSV exports for roster, transactions, attendance, payroll history, and store purchases

### 3. Mobile & Accessibility
- [ ] Responsive navigation for student/admin portals
- [ ] Larger touch targets for tap in/out and store interactions
- [ ] ARIA labels for key buttons and forms

---

## 🟢 LOWER PRIORITY

- [ ] Enhanced student dashboard insights (balance history, projected earnings)
- [ ] Performance profiling for large rosters (pagination is partial; continue tightening queries)
- [ ] Optional email notifications for teacher/system-admin events

---

## ✅ RECENTLY COMPLETED

- ✅ Configurable payroll settings with advanced schedule/rate options (global + per-block)
- ✅ Insurance policies, enrollments, and claims flows in admin portal
- ✅ Student/teacher sharing via `student_teachers` with scoped queries in `app/auth.py`
- ✅ Join-code roster claiming using `TeacherBlock` seats for safer imports
- ✅ Documentation reorganization and cleanup

---

## 📊 EFFORT SNAPSHOT

| Priority | Focus | Notes |
|----------|-------|-------|
| 🟠 High | Multi-teacher hardening, shared-student tests, migration runbooks | Coordination needed with ops before enforcing schema changes |
| 🟡 Medium | UX polish, exports, accessibility | Design alignment required |
| 🟢 Lower | Insights, performance, notifications | Schedule after core hardening |

---
