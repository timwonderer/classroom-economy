# Classroom Token Hub - Project History & Philosophy

**Document Purpose:** This document preserves the history, philosophy, and key milestones of Classroom Token Hub's development journey.

**Last Updated:** 2025-12-04

---

## Project Vision & Philosophy

### Core Mission

**Classroom Token Hub** was created to teach students financial literacy through hands-on experience in a simulated classroom economy. The platform transforms abstract financial concepts into tangible, interactive learning experiences where students earn, save, spend, and manage virtual currency tied to real classroom participation.

### Educational Philosophy

The project is built on several core educational principles:

1. **Learning by Doing** - Students don't just read about money management; they practice it daily through attendance tracking, payroll systems, savings/checking accounts, and purchasing decisions.

2. **Real-World Simulation** - Features like insurance policies, rent payments, interest calculations, and transaction histories mirror actual financial systems students will encounter in adult life.

3. **Teacher Empowerment** - The platform provides teachers with powerful tools to customize their classroom economies while maintaining security and data integrity.

4. **Student Privacy** - All personally identifiable information (PII) is encrypted at rest, ensuring student data remains protected while still enabling rich classroom interactions.

### Design Principles

#### Join Code as Source of Truth

A fundamental architectural principle emerged during multi-tenancy development:

> **"The class join code should be the absolute source of truth for how students are associated with a class."**

This principle ensures:
- Students can participate in multiple class economies simultaneously
- Data remains isolated between different class periods/sections
- Teachers can share students without data leakage between economies
- Class switching is seamless and deterministic

#### Security-First Development

From the beginning, the project prioritized security:
- Encrypted PII at the database level
- TOTP two-factor authentication for all admin accounts
- Salted and peppered password hashing
- CSRF protection on all forms
- Cloudflare Turnstile integration for bot protection
- Comprehensive input validation and sanitization

#### Educational Use Only

Released under the **PolyForm Noncommercial License 1.0.0**, the project is explicitly designed for educational and nonprofit use. This licensing choice reflects the project's commitment to serving students and educators without commercialization.

---

## Architectural Evolution

### Phase 1: Monolithic Foundation (Pre-Refactor)

The project initially began as a monolithic Flask application in a single `app.py` file that grew to over 4,500 lines. This early phase focused on:
- Basic student and teacher account management
- Simple token earning through attendance
- Manual transaction tracking
- Classroom store with basic items

### Phase 2: Modular Blueprint Refactor

As complexity grew, the application was refactored into a modern Blueprint-based architecture:

**New Structure:**
```
app/
├── __init__.py          # Application factory
├── models.py            # SQLAlchemy models (34 classes)
├── auth.py              # Authentication decorators & helpers
├── routes/
│   ├── admin.py         # Teacher dashboard (5,176 lines)
│   ├── student.py       # Student portal (2,648 lines)
│   ├── system_admin.py  # System admin interface (1,088 lines)
│   ├── api.py           # REST API (2,096 lines)
│   └── main.py          # Public routes (187 lines)
└── utils/               # Utility modules
    ├── encryption.py
    ├── claim_credentials.py
    ├── join_code.py
    └── [other helpers]
```

This refactor:
- Separated concerns into logical modules
- Made the codebase more maintainable
- Enabled parallel development on different features
- Improved testability

### Phase 3: Feature Expansion

The platform evolved from basic token tracking to a comprehensive classroom economy system:

**Financial Systems:**
- Automated payroll with configurable schedules
- Checking and savings accounts with interest calculations
- Transaction audit trails with void/refund capabilities
- Store items with bundles, discounts, and expiration dates

**Advanced Features:**
- Insurance system (policies, enrollments, claims)
- Rent collection with waivers and late fees
- Hall pass management with time tracking
- Tap-in/tap-out attendance system
- Student-to-student transfers

**Administrative Tools:**
- Bulk student roster uploads via CSV
- Join-code-based student claiming
- System admin portal for platform management
- Error logging and user reporting systems
- Feature flags for gradual rollout

### Phase 4: Multi-Tenancy & Security Hardening

A major architectural initiative focused on proper multi-tenancy:

**Problem Identified:** Students could see and interact with data from multiple teachers' classes simultaneously, violating the "join code as source of truth" principle.

**Solutions Implemented:**
- Added `StudentTeacher` many-to-many relationship table
- Created `TeacherBlock` model for unclaimed roster seats
- Implemented scoped query helpers in `auth.py`
- Refactored all transaction queries to filter by `teacher_id`
- Added class-switching interface for multi-enrolled students

**Security Audits Conducted:**
- PII audit and encryption verification
- Access control and secrets review
- Source code vulnerability assessment
- Network vulnerability scanning
- Input/output validation audit

Results: All audits passed with recommendations implemented.

### Phase 5: Known Architectural Debt

**Critical Issue Identified (November 2025):**

Despite multi-tenancy fixes, a P0 data isolation issue remains:

> **Same-Teacher Multi-Period Data Leak:** Students enrolled in multiple periods with the same teacher see aggregated data across all periods instead of period-specific data.

**Root Cause:** The `Transaction` table (and related models) track `teacher_id` but not the specific `join_code` or `block`, causing data aggregation across different class periods taught by the same teacher.

**Status:** Documented in `docs/security/CRITICAL_SAME_TEACHER_LEAK.md` but **not yet fixed**. This is considered a **blocker for 1.0 release**.

**Required Solution:** Add `join_code` column to Transaction, StudentItem, StudentInsurance, RentPayment, and HallPassLog tables, then refactor all queries to scope by join_code instead of teacher_id alone.

---

## Key Technical Milestones

### Database Evolution

**Initial Schema:** Simple Student, Admin, Transaction tables

**Current Schema:** 34 model classes including:
- Multi-tenancy support (StudentTeacher, TeacherBlock)
- Financial products (StoreItem, InsurancePolicy, RentSettings)
- Activity tracking (TapEvent, HallPassLog, PayrollReward)
- System management (ErrorLog, UserReport, DeletionRequest)

**Migration Count:** 73 Alembic migration files managing schema evolution

### Testing Infrastructure

**Test Suite Growth:**
- 47 comprehensive test files
- Coverage includes: admin auth, student features, financial transactions, insurance, deletion cascades, hall passes, multi-tenancy, legacy compatibility
- Uses pytest with in-memory SQLite for fast execution
- Foreign key constraint testing enabled

### Deployment Evolution

**Development:** Local Flask development server

**Staging:** Supabase PostgreSQL with GitHub Actions CI/CD

**Production:** DigitalOcean droplet with:
- PostgreSQL database
- Gunicorn WSGI server with gevent workers
- Redis for rate limiting and caching
- Cloudflare for DNS and bot protection
- UptimeRobot for monitoring
- Automated GitHub Actions deployment pipeline

---

## Notable Bug Fixes & Improvements

### Join Code System Overhaul

**Problem:** Join codes could collide across teachers, and the claiming system had race conditions.

**Solution:** Implemented collision detection, unique constraints, and atomic claiming operations. Documented in `docs/archive/JOIN_CODE_FIX_SUMMARY.md`.

### Migration Chain Consolidation

**Problem:** Parallel development created multiple migration heads and merge conflicts.

**Solution:** Created systematic merge migration strategy with validation checks in CI/CD pipeline. Documented in `docs/development/MIGRATION_GUIDE.md`.

### Duplicate Data Cleanup

**Problem:** Race conditions and legacy code created duplicate student records.

Solution: Developed cleanup scripts with dry-run capabilities, comprehensive logging, and validation. The Flask-context version (`cleanup_duplicates_flask.py`) is preserved, while the obsolete version was removed.

### Timezone Handling

**Problem:** Mixed use of naive and timezone-aware datetimes caused payroll and rent calculation errors.

**Solution:** Standardized on UTC storage with user-timezone conversion at display time. Comprehensive guide in `docs/technical-reference/TIMEZONE_HANDLING.md`.

### Deprecated Code Pattern Updates

**Ongoing:** Migration from deprecated Python and SQLAlchemy patterns:
- `datetime.utcnow()` → `datetime.now(datetime.UTC)` (45+ occurrences)
- `Query.get()` → `db.session.get()` (20+ occurrences)
- SQLAlchemy subquery warnings resolution

---

## Community & Collaboration

### AI-Assisted Development

The project embraces AI assistance as a development tool. The `.claude/AGENTS.md` file provides guidelines for AI agents (like Claude, GitHub Copilot, etc.) to contribute effectively while maintaining code quality and security standards.

### Open Source But Noncommercial

The project welcomes contributions from educators, developers, and security researchers under the noncommercial license. See `CONTRIBUTING.md` for contribution guidelines.

---

## Looking Forward: Version 1.0

### Release Criteria

To reach version 1.0, the project must achieve:

1. ✅ **Core Feature Completeness**
   - Multi-tenancy support
   - Complete financial systems (payroll, store, insurance, rent)
   - Comprehensive admin and student interfaces
   - System admin portal

2. ✅ **Security Hardening**
   - PII encryption
   - TOTP authentication
   - Security audits completed
   - Input validation comprehensive

3. ❌ **Critical Bug Resolution** **(BLOCKER)**
   - Same-teacher multi-period data leak must be fixed
   - All P0 security issues resolved

4. ✅ **Documentation**
   - User guides for students and teachers
   - Technical reference documentation
   - API documentation
   - Operations guides

5. ⚠️ **Code Quality** **(IN PROGRESS)**
   - Remove deprecated patterns
   - Clean up debug statements
   - Consolidate duplicate scripts
   - Comprehensive test coverage

6. ✅ **Production Readiness**
   - CI/CD pipeline operational
   - Monitoring and alerting configured
   - Backup and restore procedures documented
   - Deployment automation complete

### Post-1.0 Vision

After achieving version 1.0, the project roadmap includes:

- **Enhanced Analytics:** Dashboard visualizations for student progress and class economy health
- **Mobile Experience:** Responsive design improvements and potential native app
- **Gamification:** Achievement badges, leaderboards (opt-in), and progress tracking
- **Parent Portal:** Optional parent view of student financial activity
- **Curriculum Integration:** Pre-built lesson plans and financial literacy modules
- **Multi-Language Support:** Internationalization for broader educational reach

---

## Conclusion

Classroom Token Hub represents a commitment to practical financial education through technology. From its monolithic origins to its current modular architecture, every evolution has been guided by the needs of real students and teachers using the platform daily.

The journey to version 1.0 has been one of continuous improvement, security hardening, and feature expansion. While critical work remains (particularly the same-teacher data isolation issue), the project has established solid foundations in architecture, security, testing, and deployment.

The project's success is measured not in lines of code or technical complexity, but in the number of students who gain confidence managing money, understanding transactions, and making informed financial decisions—skills they'll carry with them long after leaving the classroom.

---

**For detailed technical history, see:**
- `docs/archive/` - Historical bug fixes and feature summaries
- `CHANGELOG.md` - Version history and release notes
- `docs/security/` - Security audit reports
- `docs/operations/` - Deployment and operational history

**Last Updated:** 2025-12-04
