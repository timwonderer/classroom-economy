# Classroom Token Hub - Development TODO List

**Last Updated:** 2025-12-06
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
- [x] Responsive navigation for admin portal (completed 2025-12-06)
- [ ] Responsive navigation for student portal
- [ ] Larger touch targets for tap in/out and store interactions
- [ ] ARIA labels for key buttons and forms

---

## 🟢 LOWER PRIORITY

- [ ] Enhanced student dashboard insights (balance history, projected earnings)
- [ ] Performance profiling for large rosters (pagination is partial; continue tightening queries)
- [ ] Optional email notifications for teacher/system-admin events

---

## 🔮 FUTURE CONSIDERATIONS (v1.5+)

### Custom Condition Builder (Advanced Feature)
- **Status:** Research completed, deferred to future release
- **Description:** Drag-and-drop visual rule builder allowing teachers to create custom conditional logic for rent, insurance, store, payroll, and banking features
- **Use Case:** Teachers could define custom triggers like "IF checking balance < $50 AND no insurance THEN charge $5 late fee"
- **Implementation Options:**
  - Phase 1: JSON-based rules engine with simple form builder (4-6 weeks)
  - Phase 2: Enhanced drag-and-drop UI with SortableJS (2-3 weeks)
  - Phase 3: Full Blockly integration for visual programming experience (4-6 weeks)
- **Rationale for Deferral:** Power-user feature, not critical for core functionality; prioritize high-demand features first
- **Estimated Effort:** 12-18 weeks for full implementation
- **Dependencies:** None (standalone feature)
- **References:**
  - Research notes in conversation logs
  - Potential libraries: json-rules-engine, Blockly, ZEN Engine (GoRules)

---

## ✅ RECENTLY COMPLETED

- ✅ Teacher display names and custom class labels (2025-12-06)
  - Added `display_name` to Admin model
  - Added `class_label` to TeacherBlock model
  - Created teacher settings page at `/admin/settings`
  - Updated templates to show custom labels instead of "Block X"
  - Added responsive navigation (icon-only mode on mobile)
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
