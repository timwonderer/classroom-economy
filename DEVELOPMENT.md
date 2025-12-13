# Classroom Token Hub - Development Priorities

**Last Updated:** 2025-12-12
**Current Version:** 1.0.0
**Target:** 1.1.0 Feature Release

---

## Quick Links

- **[Architecture Guide](docs/technical-reference/architecture.md)** - System design and patterns
- **[Database Schema](docs/technical-reference/database_schema.md)** - Current data models
- **[API Reference](docs/technical-reference/api_reference.md)** - REST API documentation
- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute
- **[Project History](PROJECT_HISTORY.md)** - Project evolution and philosophy

---

## Version 1.0 Release Status

### ✅ RELEASED - December 12, 2025

**All critical blockers for v1.0 were resolved:**

#### ✅ P0: Same-Teacher Multi-Period Data Leak
**Status:** ✅ **RESOLVED**

Students enrolled in multiple periods with the same teacher now see properly isolated data for each class period. The system correctly uses `join_code` as the source of truth for class boundaries.

#### ✅ P1: Deprecated Code Patterns
**Status:** ✅ **RESOLVED**

All deprecated Python and SQLAlchemy patterns have been updated, ensuring full compatibility with Python 3.12+ and SQLAlchemy 2.0+.

---

## Development Priorities (v1.1)

### 🟠 HIGH PRIORITY

#### 1. Multi-Teacher Hardening
**Status:** In progress (sharing + scoped queries shipped)

**Remaining Tasks:**
- [ ] Finalize migration to remove legacy `students.teacher_id` (deprecated in models)
- [ ] Publish runbook for NOT NULL enforcement / teacher reassignment
- [ ] Audit for direct `Student.query.get` outside scoped helpers → replace with `get_student_for_admin`
- [ ] Add DB safeguard for ownership changes (define ON DELETE strategy)

**Context:** The `student_teachers` link table is the authoritative ownership model. Join codes partition class economies.

#### 2. Shared-Student Test Coverage
**Status:** Pending

**Tasks:**
- [ ] Add pytest coverage for payroll flows with students linked to multiple teachers
- [ ] Add pytest coverage for attendance flows with shared students
- [ ] Add DB-level uniqueness regression test for `student_teachers` constraint

#### 3. Operational Safety Documentation
**Status:** Pending

**Tasks:**
- [ ] Create runbook for schema changes affecting tenancy or payroll
- [ ] Document pre/post checks for migrations with maintenance mode
- [ ] Establish migration validation checklist

### 🟡 MEDIUM PRIORITY

#### 1. Admin Experience Polish
- [ ] System-admin filters to view students by primary/shared teachers
- [ ] Clearer UI messaging when acting on shared students
- [ ] Payroll scope hints in transaction history

#### 2. Data Export Capabilities
- [ ] CSV exports for rosters
- [ ] CSV exports for transactions
- [ ] CSV exports for attendance history
- [ ] CSV exports for payroll history
- [ ] CSV exports for store purchases

#### 3. Mobile & Accessibility
- [x] Responsive navigation for admin portal (completed 2025-12-06)
- [ ] Responsive navigation for student portal
- [ ] Larger touch targets for tap in/out
- [ ] Larger touch targets for store interactions
- [ ] ARIA labels for key buttons and forms

### 🟢 LOWER PRIORITY

- [ ] Enhanced student dashboard insights (balance history, projected earnings)
- [ ] Performance profiling for large rosters (pagination partial; continue optimization)
- [ ] Optional email notifications for teacher/system-admin events

---

## Future Roadmap (Post-1.0)

### Version 1.1 - Analytics & Insights ✅ **RELEASED 2024-12-13**
- ✅ Dashboard visualizations for student progress (weekly stats card with attendance, earnings, spending)
- ✅ Savings projection graph with interactive 12-month forecast
- ✅ Class economy health metrics (enhanced warnings with specific recommendations)
- ✅ Long-term goal items feature for flexible store pricing
- ✅ Complete UI redesign with modern, accessible interface
- 🔄 Teacher analytics for payroll and store performance (partial - economy health page provides CWI analysis)
- ⏳ Enhanced reporting and export capabilities (planned for future release)

**See:** [RELEASE_NOTES_v1.1.0.md](RELEASE_NOTES_v1.1.0.md) for complete details

### Version 1.2 - Mobile Experience
- Progressive Web App (PWA) capabilities
- Native mobile app exploration
- Offline support for attendance tracking
- Improved touch interfaces

### Version 1.3 - Gamification
- Achievement badge system
- Optional leaderboards (privacy-conscious)
- Progress tracking and milestones
- Student engagement metrics

### Version 1.4 - Extended Features
- Parent portal (optional, privacy-controlled)
- Curriculum integration resources
- Pre-built lesson plans
- Financial literacy assessment tools

### Version 2.0 - Internationalization
- Multi-language support
- Currency localization
- Regional educational standard alignment

### Planned Features (Future Releases)

#### 1. In-App Communication & Announcements (v1.5+)
**Status:** Documented, not yet implemented
**Documentation:** `docs/development/SYSADMIN_INTERFACE_DESIGN.md` (Section 6)

**Features:**
- **System-wide announcements** - Broadcast messages to all users
- **Maintenance notifications** - Automated alerts for scheduled maintenance
- **Emergency alerts** - Critical system messages with priority display
- **Message to all teachers** - Admin communication tool
- **Message to all students** - Class-wide or system-wide student messaging

**Route:** `/sysadmin/announcements` (System Admin)

**Use Cases:**
- Notify all users of upcoming maintenance
- Emergency closure announcements
- System-wide policy updates
- Teacher communication for multi-school deployments

**Estimated Effort:** 4-6 weeks
**Priority:** Medium (useful for multi-school deployments)

#### 2. Teacher Self-Serve Account Recovery (Future)
**Status:** Documented, deferred due to security complexity
**Documentation:** `docs/development/SYSADMIN_INTERFACE_DESIGN.md` (mentions TOTP reset)

**Problem:** Teachers who lose access to their TOTP authenticator app are locked out of their accounts. Currently requires sysadmin intervention.

**Security Challenge:** Self-serve recovery requires storing additional sensitive information, which conflicts with the platform's minimal-PII philosophy.

**Potential Approaches:**
- **Backup codes** (one-time use) - Requires secure storage and user safekeeping
- **Recovery email** - Additional PII to protect, phishing risk
- **Security questions** - Generally weak security, social engineering risk
- **SMS verification** - More PII, SIM-swapping attacks
- **Printable recovery key** - User responsibility to secure physical key

**Current Workaround:** System admins can reset teacher TOTP via `/sysadmin` interface (planned feature)

**Estimated Effort:** 3-4 weeks (implementation) + security review
**Priority:** Medium (nice-to-have, but sysadmin reset is acceptable)
**Blocker:** Requires decision on acceptable security/PII tradeoffs

**Recommendation:** Defer until v1.5+ and prioritize sysadmin-assisted TOTP reset as the primary recovery path.

#### 3. Custom Condition Builder (v1.5+)
**Status:** Research completed, deferred to future release

**Description:** Drag-and-drop visual rule builder for custom conditional logic in rent, insurance, store, payroll, and banking features.

**Use Case:** Teachers could define custom triggers like "IF checking balance < $50 AND no insurance THEN charge $5 late fee"

**Implementation Options:**
- Phase 1: JSON-based rules engine with simple form builder (4-6 weeks)
- Phase 2: Enhanced drag-and-drop UI with SortableJS (2-3 weeks)
- Phase 3: Full Blockly integration for visual programming (4-6 weeks)

**Rationale for Deferral:** Power-user feature, not critical for core functionality; prioritize high-demand features first

**Estimated Effort:** 12-18 weeks for full implementation

#### 4. Jobs Feature (v1.5+)
**Status:** Partially implemented, then removed; awaiting completion
**Git History:** Started in commit `0800640`, removed in commit `a04b574` (2025-12-10)

**Description:** Classroom job market system allowing teachers to create job opportunities for students, teaching work ethic and providing earning opportunities beyond attendance-based payroll.

**Two Job Types:**

1. **Employee Jobs** - Long-term positions with regular pay
   - Application and approval process required
   - Regular salary payments (daily/weekly/monthly)
   - Multiple vacancy slots per job
   - Job requirements and qualifications
   - Termination system with notice periods, warnings, and penalties
   - Teacher can fire employees with configurable consequences

2. **Contract Jobs** - One-off bounties, first-come-first-served
   - No application required; students claim available contracts
   - Single bounty payment upon completion
   - Quick turnaround for short-term tasks
   - Teacher marks as complete to trigger payment

**Database Models Created:**
- `JobTemplate` - Reusable job definitions in the teacher's job bank
- `Job` - Instance of a template assigned to a specific period/block
- `JobApplication` - Student applications for employee positions
- `JobEmployee` - Active employment relationships
- `JobContract` - Contract job assignments and completions

**Features Implemented Before Removal:**
- Job bank management for teachers (create/edit templates)
- Job assignment to specific class periods via join_code
- Application system for employee positions
- Contract claiming interface
- Payment processing integration with transactions
- Termination system with warnings and penalties
- Comprehensive test coverage (test files removed with feature)
- Admin routes (`app/routes/admin_jobs.py`, 514 lines)
- Flask forms for all job operations

**Use Cases:**
- **Classroom Helper:** Student job as "Board Eraser" earning $5/week
- **Technology Assistant:** "Chromebook Manager" earning $10/week
- **Project Bounties:** "Design Class Poster" contract for $25 one-time
- **Teaching Work Ethic:** Students learn reliability, job performance, consequences of termination
- **Earning Diversity:** Income beyond attendance, rewarding contribution and responsibility

**Why It Was Removed:**
- Removed during feature cleanup (commit a04b574)
- Only merge migration kept to maintain migration chain integrity
- Code preserved in git history for future reimplementation

**Remaining Work for Completion:**
- [ ] Restore models from commit `0800640`
- [ ] Restore admin routes from commit `e2de8bd`
- [ ] Restore Flask forms from commit `c9378b7`
- [ ] Restore test coverage from commit `8a1b0bd`
- [ ] Update for current join_code scoping patterns
- [ ] Add student-facing job board interface
- [ ] Add application submission and tracking UI
- [ ] Implement contract claiming interface
- [ ] Add job performance tracking (optional: attendance link)
- [ ] Create teacher analytics for job market health

**Estimated Effort:** 6-8 weeks (restoration + modernization + UI polish)
**Priority:** Medium (valuable feature, but not critical for 1.0)
**Complexity:** High (payroll integration, multi-state workflows, termination rules)

**Git References:**
- `0800640` - Add jobs feature database models and migration
- `c9378b7` - Add Flask forms for jobs feature
- `e2de8bd` - Add admin routes for jobs feature (514 lines)
- `8a1b0bd` - Add comprehensive tests and documentation for jobs feature
- `a04b574` - Remove jobs feature code, keep only merge migration
- `e7b38b9` - Fix migration chain: add stub for removed jobs feature migration

---

## Recently Completed Features

### December 2025
- ✅ Teacher display names and custom class labels (2025-12-06)
  - Added `display_name` to Admin model
  - Added `class_label` to TeacherBlock model
  - Created teacher settings page at `/admin/settings`
  - Responsive navigation (icon-only mode on mobile)
- ✅ Economy balancing system with CWI calculations
- ✅ Store item pricing tiers
- ✅ Block-scoped payroll settings

### November 2025
- ✅ Same-teacher multi-period data leak fix (2025-11-29)
- ✅ Configurable payroll settings with advanced schedule/rate options
- ✅ Insurance policies, enrollments, and claims flows
- ✅ Student/teacher sharing via `student_teachers` with scoped queries
- ✅ Join-code roster claiming using `TeacherBlock` seats
- ✅ Documentation reorganization and cleanup

---

## Multi-Tenancy Architecture

### Current State

#### Join Code as Source of Truth
- **Class Isolation:** Join codes partition transactions/attendance between class periods
- **Student Sessions:** Persist `current_join_code` to scope balances/transactions per class
- **Authoritative Model:** `student_teachers` link table enforces ownership
- **Deprecated:** `students.teacher_id` is ignored by access control helpers

#### Access Control
- **Scoped Helpers:** `get_admin_student_query`, `get_student_for_admin` in `app/auth.py`
- **Admin Routes:** Use scoped helpers exclusively (avoid direct `Student.query`)
- **System Admins:** Global visibility across all students and teachers
- **Teacher Isolation:** Each teacher sees only their linked students

#### Database Constraints
- **Uniqueness:** `student_teachers` enforces (`student_id`, `admin_id`) unique constraint
- **Cascading:** Deletes cascade properly through relationships
- **Join Code:** NOT NULL enforcement pending after backfill verification

### Migration Strategy

When ready to finalize multi-teacher model:

1. **Pre-checks:**
   - Verify every student has ≥1 `student_teachers` row
   - Identify orphaned student records
   - Audit direct `Student.query` usage in codebase

2. **Maintenance Banner:**
   - Enable maintenance mode during migration if medium/high risk
   - Use `MAINTENANCE_MODE=true` environment variable

3. **Migration Execution:**
   - Drop/lock `students.teacher_id` after dependency verification
   - Ensure foreign keys optimized for scoped queries
   - Enforce `join_code` NOT NULL on ledger tables

4. **Post-checks:**
   - Smoke tests on admin/student portals
   - Validate payroll/attendance with shared students
   - Verify no routes bypass scoped helpers

---

## Code Quality Standards

### Authentication & Authorization
- Prefer scoped helpers (`get_admin_student_query`, `get_student_for_admin`) over ad-hoc filters
- Always check `is_system_admin` for global access requirements
- Use `@admin_required` and `@system_admin_required` decorators consistently

### Database Best Practices
- **Migrations:** Always sync with main before creating new migrations
- **Queries:** Use scoped helpers for tenant-aware access
- **Timestamps:** Use `datetime.now(timezone.utc)` (not deprecated `utcnow()`)
- **Session Access:** Use `db.session.get(Model, id)` (not deprecated `Model.query.get()`)

### Security Guidelines
- Keep PII minimal (prefer non-PII identifiers, encrypted first names)
- Validate all user input at route level
- Use CSRF protection on all forms
- Encrypt sensitive data at rest
- Avoid adding debug print statements to production code

### Testing Requirements
- Run `pytest -q` before committing
- Add tests for new features and bug fixes
- Focus tests for tenancy helpers when changing scoping logic
- Ensure foreign key constraints enabled in tests

---

## Development Workflow

### Before Creating Migrations

**⚠️ CRITICAL: Always follow this workflow to prevent multiple heads:**

1. **Sync with latest code:**
   ```bash
   git fetch origin main
   git merge origin/main
   ```

2. **Verify exactly ONE migration head:**
   ```bash
   flask db heads  # Must show exactly 1 head
   ```

3. **If multiple heads exist, merge them first:**
   ```bash
   flask db merge heads -m "Merge migration heads"
   ```

4. **Check current revision:**
   ```bash
   flask db current
   ```

5. **Create migration:**
   ```bash
   flask db migrate -m "Clear description"
   ```

6. **Verify new migration:**
   - Open generated file in `migrations/versions/`
   - Verify `down_revision` matches `flask db current` output
   - If mismatch, DELETE migration and restart workflow

7. **Test migration:**
   ```bash
   flask db upgrade    # Apply
   flask db downgrade  # Rollback
   flask db upgrade    # Reapply
   ```

8. **Quick verification:**
   ```bash
   bash scripts/check-migration-heads.sh
   ```

### Before Submitting PR

- [ ] Tests pass locally (`pytest -q`)
- [ ] Migrations reviewed for safety (lock impact, backfill steps)
- [ ] No new deprecation warnings
- [ ] Code follows project conventions
- [ ] Documentation updated where needed
- [ ] Commit messages are clear and descriptive

---

## Effort Snapshot

| Priority | Focus Areas | Notes |
|----------|-------------|-------|
| 🟠 High | Multi-teacher hardening, shared-student tests, migration runbooks | Coordination with ops needed before schema changes |
| 🟡 Medium | UX polish, exports, accessibility | Design alignment required |
| 🟢 Lower | Insights, performance, notifications | Schedule after core hardening |

---

## Documentation Structure

### User Documentation
- **[Student Guide](docs/user-guides/student_guide.md)** - How students use the platform
- **[Teacher Manual](docs/user-guides/teacher_manual.md)** - Comprehensive admin guide

### Technical Reference
- **[Architecture](docs/technical-reference/architecture.md)** - System design and patterns
- **[Database Schema](docs/technical-reference/database_schema.md)** - Data models and relationships
- **[API Reference](docs/technical-reference/api_reference.md)** - REST endpoints
- **[Timezone Handling](docs/technical-reference/TIMEZONE_HANDLING.md)** - UTC storage and conversion
- **[Economy Specification](docs/technical-reference/ECONOMY_SPECIFICATION.md)** - Financial system ratios and rules

### Development Guides
- **[Economy Balance Checker](docs/development/ECONOMY_BALANCE_CHECKER.md)** - CWI implementation guide
- **[Migration Guide](docs/development/MIGRATION_GUIDE.md)** - Alembic best practices
- **[Migration Best Practices](docs/development/MIGRATION_BEST_PRACTICES.md)** - Database migration guidelines
- **[Seeding Instructions](docs/development/SEEDING_INSTRUCTIONS.md)** - Test data setup
- **[Deprecated Patterns](docs/development/DEPRECATED_CODE_PATTERNS.md)** - Code modernization tracking
- **[System Admin Design](docs/development/SYSADMIN_INTERFACE_DESIGN.md)** - Admin interface patterns

### Operations & Deployment
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment
- **[Operations Guides](docs/operations/)** - Maintenance procedures
- **[Security Audits](docs/security/)** - Security assessment reports

### Historical Reference
- **[Project History](PROJECT_HISTORY.md)** - Evolution and philosophy
- **[Changelog](CHANGELOG.md)** - Version history
- **[Archive](docs/archive/)** - Historical reports and fixes

---

## Success Metrics for 1.0 Release

Version 1.0 has been successfully released with the following criteria met:

1. ✅ All P0 and P1 issues resolved
2. ✅ Full test suite passes (100% of existing tests)
3. ✅ No known security vulnerabilities
4. ✅ Codebase uses modern Python 3.12+ and SQLAlchemy 2.0+ patterns
5. ✅ Staging environment validated
6. ✅ Production deployment successful
7. ⏳ No critical bugs reported within 48 hours of release (Monitoring)
8. ✅ Documentation complete and accurate
9. ✅ Rollback plan tested and ready

**Status:** 1.0.0 RELEASED!

---

## Getting Help

- **Documentation Issues:** Check [docs/README.md](docs/README.md) for navigation
- **Technical Questions:** Review [Architecture Guide](docs/technical-reference/architecture.md)
- **Security Concerns:** See [Security Audits](docs/security/)
- **Contributing:** Read [CONTRIBUTING.md](CONTRIBUTING.md)

---

**Next Immediate Actions (v1.2):**

1. Begin mobile experience improvements (PWA capabilities)
2. Complete multi-teacher hardening (remove `students.teacher_id` dependency)
3. Add shared-student test coverage for payroll and attendance
4. Explore offline support for attendance tracking
5. Continue "Admin Experience Polish" initiatives

**Recent Releases:**
- **v1.1.0** (2024-12-13) - Analytics dashboard, savings projections, UI redesign
- **v1.0.0** (2024-11-29) - Initial stable release

---

**Last Updated:** 2024-12-13
**Maintained by:** Project maintainers and contributors
