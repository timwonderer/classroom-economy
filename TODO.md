# Classroom Token Hub - Development TODO List

**Last Updated:** 2025-11-17
**Purpose:** Comprehensive task tracking for all planned features and improvements

---


## 🟠 HIGH PRIORITY - Core Feature Additions

### 1. Payroll Settings & Configuration System
- **Status:** Planned
- **Current State:**
  - Pay rate is hardcoded: `RATE_PER_SECOND = 0.25 / 60` ($0.25/minute)
  - Located in: `payroll.py:15`, `attendance.py:160`, `app.py` (multiple locations)
  - No admin interface to adjust pay rate
  - No per-block pay rate configuration
  - Payroll schedule hardcoded to 14 days
- **Requirements:**
  - [ ] Create `PayrollSettings` database model
    - Global default pay rate (per minute or per hour)
    - Payroll schedule interval (days)
    - Overtime multipliers (optional)
    - Minimum session duration for pay eligibility
    - Grace period for late tap-outs
  - [ ] Create per-block pay rate overrides
    - Allow different pay rates for different blocks/periods
    - Store in separate table or JSON field
  - [ ] Build admin settings interface
    - Route: `/admin/payroll/settings`
    - Form to update global pay rate
    - Form to set per-block rates
    - Preview calculation examples
  - [ ] Update payroll calculation logic
    - Read from database settings instead of hardcoded constants
    - Apply per-block rates when available
    - Fallback to global rate
  - [ ] Migration path for existing data
    - Create settings record with current hardcoded values
    - Ensure backwards compatibility
- **Files to Modify:**
  - `app.py` - Add PayrollSettings model, routes
  - `payroll.py` - Update calculation to use settings
  - `attendance.py` - Update rate constants
  - `forms.py` - Add PayrollSettingsForm
  - `templates/` - Create admin settings page
- **Estimated Effort:** 8-12 hours

### 2. Account Recovery System
- **Status:** Planned
- **Current State:** No recovery mechanism exists for forgotten credentials
- **Requirements:**

#### Student Account Recovery
- [ ] **PIN Reset**
  - Admin-initiated PIN reset from student detail page
  - Generates temporary reset code
  - Student enters code + creates new PIN
  - Logs all PIN resets for audit trail
- [ ] **Passphrase Recovery**
  - Security questions during initial setup (3-5 questions)
  - Student must answer 2-3 questions correctly
  - Allow passphrase reset after verification
  - Admin override option (with logging)
- [ ] **Setup Restart**
  - Admin can force student back to initial setup state
  - Clears PIN and passphrase (keeps account data)
  - Student completes setup flow again
- [ ] **Security Measures**
  - Rate limiting on recovery attempts
  - Email/log notification to admin on recovery
  - Temporary lockout after failed attempts

#### Admin Account Recovery
- [ ] **TOTP Recovery Codes**
  - Generate 10 single-use backup codes during admin creation
  - Display once, admin must save them
  - Store hashed in database
  - Allow login with backup code if TOTP unavailable
  - Mark code as used after redemption
- [ ] **System Admin Password Reset**
  - System admin can reset another admin's password
  - Requires TOTP verification from system admin
  - Forces password change on next login
  - Notification to affected admin (if email available)
- [ ] **TOTP Re-enrollment**
  - System admin can disable TOTP for an admin account
  - Admin must re-enroll with new TOTP secret on next login
  - Logs the re-enrollment event
- [ ] **Emergency Access**
  - Flask CLI command for system admin recovery
  - `flask reset-admin-totp <username>`
  - Requires server access (not web-accessible)
  - Generates temporary login token or disables TOTP

- **Database Changes:**
  - Add `security_questions` JSON field to Student model
  - Add `backup_codes` table for Admin recovery codes
  - Add `account_recovery_log` table for audit trail
- **Files to Create/Modify:**
  - `app.py` - Recovery routes, models
  - `forms.py` - Recovery forms
  - `templates/admin_student_recovery.html`
  - `templates/student_account_recovery.html`
  - `templates/admin_recovery.html`
- **Estimated Effort:** 12-16 hours

### 3. Pagination & Performance for Large Data Sets
- **Status:** Planned
- **Current State:** All data loaded at once, no pagination
- **Problem Pages:**
  - Admin dashboard - All students displayed
  - Student roster - Grows with class size
  - Payroll history - Unlimited records
  - Transaction log - Unlimited records
  - Attendance log - Grows quickly
  - Store purchases - Unlimited records

#### Implementation Strategy
- [ ] **Students Page Pagination**
  - `/admin/students` - Paginate student list
  - Default: 25 students per page
  - Search/filter persistence across pages
  - Total count display
- [ ] **Payroll History Pagination**
  - `/admin/payroll-history` - Paginate records
  - Default: 50 records per page
  - Date range filtering
  - Export full results option (CSV)
- [ ] **Transaction Log Pagination**
  - `/admin/transactions` - Paginate transactions
  - Default: 50 per page
  - Filter by student, type, date range
  - Running balance calculation consideration
- [ ] **Attendance Log Pagination**
  - `/admin/attendance-log` - Already large
  - Default: 100 records per page
  - Real-time updates consideration
- [ ] **Store Purchases Pagination**
  - `/admin/store` purchases tab
  - Default: 50 per page

#### Tab System for Multi-Section Pages
- [ ] **Insurance Page Tabs** (already partially implemented)
  - Policies tab
  - Active enrollments tab
  - Claims tab
  - History tab
- [ ] **Student Detail Page Tabs**
  - Overview tab (current display)
  - Transactions tab (paginated)
  - Attendance tab (paginated)
  - Insurance tab
  - Rent/taxes tab
- [ ] **Payroll Page Tabs**
  - Overview tab (next run, estimate)
  - Recent payrolls tab
  - History tab (paginated)
  - Settings tab (new feature)

- **Technical Requirements:**
  - [ ] Add Flask-SQLAlchemy pagination helper
  - [ ] Create reusable pagination component template
  - [ ] Add page state to URL query params
  - [ ] Implement "Load More" alternative for some pages
  - [ ] Add CSV/Excel export for paginated data
  - [ ] Performance: Add database indexes for common queries
  - [ ] Lazy loading for tabs (load content on click)
- **Files to Modify:**
  - `app.py` - Update all routes with pagination
  - `templates/` - Add pagination controls
  - Create `templates/components/pagination.html`
  - Update CSS for tab styling
- **Estimated Effort:** 10-14 hours

---

## 🟡 MEDIUM PRIORITY - Multi-Tenancy System

### Database Schema Changes
- **Status:** Planned (see MULTI_TENANCY_TODO.md for full details)
- [ ] Add `teacher_id` foreign key to Student model
- [ ] Create migration for existing data (assign students to admins)
- [ ] Add `teacher` relationship to Student model
- [ ] Add `students` backref to Admin model

### Code Changes
- [ ] Create helper functions:
  - `get_current_admin()` - Get logged-in admin object
  - `get_accessible_students()` - Filter students by teacher
- [ ] Update ALL student queries with teacher filtering (27+ routes):
  - Admin dashboard
  - Student management
  - Payroll (all routes)
  - Transactions
  - Attendance
  - Insurance
  - Store
  - Hall pass
  - Rent
- [ ] Add session variables:
  - `admin_id` in addition to `admin_username`
  - `is_system_admin` flag for filtering logic
- [ ] Update CSV student upload:
  - Auto-assign to current admin
  - System admin can choose teacher

### System Admin Features
- [ ] Student-teacher assignment interface
- [ ] Transfer students between teachers
- [ ] Bulk assignment tools
- [ ] Teacher selector on student creation
- [ ] Filter students by teacher in system admin view

### Security & Testing
- [ ] Unit tests for teacher data isolation
- [ ] Integration tests for multi-teacher scenarios
- [ ] Security tests (URL manipulation, unauthorized access)
- [ ] Verify payroll only affects teacher's students
- [ ] Verify transaction filtering

**Estimated Effort:** 20-28 hours (see MULTI_TENANCY_TODO.md)

---

## 🟡 MEDIUM PRIORITY - Insurance System Backend

### Routes to Implement
- **Status:** Frontend complete, backend pending
- **See:** `INSURANCE_SYSTEM_STATUS.md` for complete specification

#### Admin Routes (app.py)
- [ ] `/admin/insurance` - Main insurance management dashboard
- [ ] `/admin/insurance/edit/<id>` - Edit insurance policy
- [ ] `/admin/insurance/deactivate/<id>` - Deactivate policy
- [ ] `/admin/insurance/claim/<id>` - Process claim (approve/reject/pay)
- [ ] `/admin/insurance/policy-view/<id>` - View student policy details

#### Student Routes (app.py)
- [ ] `/student/insurance` - Marketplace and policy management
- [ ] `/student/insurance/purchase/<id>` - Purchase policy
- [ ] `/student/insurance/cancel/<id>` - Cancel policy
- [ ] `/student/insurance/claim/<id>` - File claim
- [ ] `/student/insurance/policy/<id>` - View policy details

#### Business Logic Functions
- [ ] `can_purchase_policy()` - Validate purchase eligibility
- [ ] `validate_claim()` - Validate claim requirements
- [ ] Autopay system (cron job or scheduled task)
- [ ] Auto-deposit for approved monetary claims
- [ ] Auto-reject for invalid claims

#### Features to Support
- ✅ Monetary vs non-monetary claims
- ✅ Waiting periods
- ✅ Claim time limits
- ✅ Max claims per period
- ✅ Autopay functionality
- ✅ Repurchase restrictions
- ✅ Bundle discounts

**Estimated Effort:** 12-16 hours

---

## 🟢 LOWER PRIORITY - Quality of Life Improvements

### CSV Export Functionality
- [ ] Export student roster with all data
- [ ] Export transaction history
- [ ] Export attendance logs
- [ ] Export payroll history
- [ ] Export store purchase history
- [ ] Add "Export to CSV" buttons on relevant admin pages
- **Estimated Effort:** 4-6 hours

### Mobile-Friendly Redesign
- [ ] Responsive navigation for small screens
- [ ] Touch-friendly tap in/out interface
- [ ] Mobile-optimized admin dashboard
- [ ] Hamburger menu for sidebar
- [ ] Larger touch targets for student interfaces
- **Estimated Effort:** 8-12 hours

### Enhanced Student Dashboard
- [ ] Visual charts for balance history
- [ ] Projected earnings calculator
- [ ] Spending insights
- [ ] Goal tracking (save up for items)
- **Estimated Effort:** 6-8 hours

---

## 📋 ROADMAP ITEMS (from README.md)

### Rent & Property Tax System
- **Status:** Partial (settings exist, payment workflow needed)
- [ ] Rent payment workflow (scheduled deductions)
- [ ] Property tax calculations and payments
- [ ] Late payment penalties
- [ ] Rent receipt/history for students
- [ ] Admin dashboard for rent collection status
- **Estimated Effort:** 8-10 hours

### Classroom Store & Inventory
- **Status:** Partial (store items exist, needs expansion)
- [ ] Inventory management system
- [ ] Stock level tracking
- [ ] Restock alerts
- [ ] Purchase history analytics
- [ ] Item categories and filtering
- [ ] Store "hours" (open/closed times)
- **Estimated Effort:** 10-14 hours

### Student Authentication Enhancements
- [ ] Optional TOTP for students (advanced security)
- [ ] Passkey support (WebAuthn)
- [ ] Biometric authentication option
- [ ] Session timeout warnings
- [ ] Remember device option
- **Estimated Effort:** 12-16 hours

### Stock Market Mini-Game
- [ ] Create virtual stocks based on school data
- [ ] Student portfolio management
- [ ] Buy/sell interface
- [ ] Price fluctuation algorithm
- [ ] Leaderboard
- [ ] Market news/events
- **Estimated Effort:** 20-30 hours

---

## 🔧 TECHNICAL DEBT & MAINTENANCE

### Code Quality
- [ ] Add type hints to Python functions
- [ ] Refactor large routes into smaller functions
- [ ] Extract business logic from routes into service layer
- [ ] Create reusable template components
- [ ] Consolidate duplicate code (timezone conversion, etc.)

### Testing
- [ ] Increase test coverage (currently minimal)
- [ ] Add integration tests for critical workflows
- [ ] Add end-to-end tests for student/admin flows
- [ ] Performance testing for large datasets
- [ ] Security testing (OWASP Top 10)

### Documentation
- [x] API documentation for routes
- [x] Database schema documentation
- [x] Deployment guide improvements
- [x] User manual for teachers
- [x] Student quick-start guide
- [x] Contributing guidelines

### Performance Optimization
- [ ] Add database indexes for common queries
- [ ] Implement query result caching
- [ ] Optimize N+1 queries
- [ ] Add database connection pooling
- [ ] Frontend asset minification
- [ ] Lazy loading for images

### Security Hardening
- [ ] Rate limiting on all auth endpoints
- [ ] CSRF token validation everywhere
- [ ] Content Security Policy headers
- [ ] SQL injection prevention audit
- [ ] XSS prevention audit
- [ ] Secure password reset flows
- [ ] Audit logging for sensitive operations

---

## ✅ RECENTLY COMPLETED

- ✅ Repository cleanup - removed obsolete files and configurations (2025-11-18)
- ✅ System Admin Portal with teacher management
- ✅ Comprehensive error handling and logging
- ✅ TOTP-only admin authentication
- ✅ Invite-based admin signup
- ✅ Attendance tracking with tap in/out
- ✅ Automated payroll calculation
- ✅ Transaction logging system
- ✅ GitHub Actions CI/CD pipeline
- ✅ Hall pass system
- ✅ Student first-time setup flow
- ✅ CSV student roster upload
- ✅ Timezone conversion for attendance log (2025-11-17)
- ✅ Fix payroll timestamp display (2025-11-16)

---

## 📊 EFFORT SUMMARY

| Priority | Tasks | Est. Hours |
|----------|-------|------------|
| 🔴 Critical Bugs | 0 | 0 |
| 🟠 High Priority | 3 | 30-42 |
| 🟡 Medium Priority | 2 | 32-44 |
| 🟢 Lower Priority | 3 | 18-26 |
| 📋 Roadmap | 4 | 50-70 |
| **TOTAL** | **13 major features** | **131-184 hours** |

---

## 📝 SESSION NOTES

### Session: 2025-11-18
- Repository housekeeping and cleanup
- Removed obsolete files: test_roster_upload.csv, sample_students.csv, startup.txt
- Removed .vscode/ directory (editor-specific configuration)
- Added .vscode/ to .gitignore
- Updated documentation (README.md, TODO.md)
- Created AGENT.md for future AI assistant sessions

### Session: 2025-11-17
- Identified payroll timestamp display bug (missing JavaScript)
- Created comprehensive TODO.md
- Reviewed payroll system architecture
- Documented insurance system status
- Reviewed multi-tenancy plan

### Instructions for Future Sessions
1. **Update this file** at the start and end of each development session
2. **Move completed items** to the "Recently Completed" section with date
3. **Add new issues** to appropriate priority sections as discovered
4. **Update effort estimates** based on actual time spent
5. **Add session notes** with date and summary of work done
6. **Keep TODO.md in sync** with actual codebase state

---

## 🎯 NEXT SESSION PRIORITIES

1. **Implement payroll settings UI** (8-12 hours) - High impact, frequently requested
2. **Add basic pagination to student list** (3-4 hours) - Performance improvement
3. **Start account recovery system** (4-6 hours initial) - Student PIN reset first

---

*This TODO list should be reviewed and updated at the beginning of every development session to ensure it reflects current priorities and system state.*
