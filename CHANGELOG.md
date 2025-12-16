# Changelog

All notable changes to the Classroom Token Hub project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows semantic versioning principles.


## [Unreleased]

### Changed
- **Insurance Policy Edit Page** - Redesigned with collapsible accordion sections to eliminate overflow issues and reduce visual clutter
  - Moved from crowded 2x2 grid layout to clean vertical stacking with progressive disclosure
  - Kept frequently-edited sections (Basic Information, Pricing & Payment) always visible
  - Organized advanced features into Bootstrap accordion: Coverage & Claims (default open), Repurchase Restrictions, Bundle Discounts, and Grouped Insurance
  - Added visual badges to accordion headers indicating when sections have active settings
  - Significantly improved mobile responsiveness and eliminated horizontal scrolling
- Simplified admin feature settings into single-column, collapsible cards to reduce page crowding.

### Added
- **TEMPLATE_REDESIGN_RECOMMENDATIONS.md** - Documentation of UI redesign patterns and guidelines
  - Best practices for when to use accordion/collapsible patterns vs traditional layouts
  - Analysis of other admin templates that could benefit from similar improvements
  - Implementation checklist for future template redesigns
  - Color scheme guidelines for consistent visual hierarchy


## [1.2.0] - 2025-12-24

### Added
- **Mobile Experience** - Dedicated mobile templates for student portal with responsive navigation and improved touch targets.
- **PWA Support** - Added mobile web app capability meta tags.
- **Accessibility** - Added ARIA labels to mobile navigation and interactive elements.

### Changed
- **Mobile Dashboard** - Simplified single-column layout with attendance card and tap in/out buttons.
- **Mobile Store** - Improved item list layout with larger purchase buttons.
- **Theme Consistency** - Aligned mobile templates with main application theme colors.

## [1.1.1] - 2025-12-15

### Fixed
- Secured teacher recovery verification by hashing date-of-birth sums and migrating existing records to the new salted hash format (#637)
- Hardened student login redirects and UTC-normalized dashboard earnings/spending calculations to prevent redirect abuse and negative totals (#638)
- Applied the green theme to standalone admin/auth pages and corrected admin heading hierarchy to resolve styling regressions (#635, #639)
- Added cache-busting static asset helper defaults and fallback coverage to stop `static_url` undefined errors across templates (#628-633)
- Stopped insurance management and edit screens from crashing when legacy forms lack the tier grouping field (#640)
- Added one-time prompt for legacy insurance policies and supporting script to encourage migration to tiered plans (#641)

## [1.1.0] - 2024-12-13

### Added
- **Student Analytics Dashboard** - Weekly statistics showing days tapped in, minutes attended, earnings, and spending
- **Savings Projection Graph** - Interactive 12-month visualization of savings growth on bank page using Chart.js
- **Long-Term Goal Items** - Option to mark store items that should be exempt from CWI balance checks (for expensive class rewards)
- **Enhanced Economy Health Warnings** - Specific recommended ranges and actionable guidance for all economy settings
- **Weekly Analytics Calculations** - Backend logic to calculate unique days tapped, total minutes, and transaction summaries
- **Savings Projection Algorithm** - Respects simple/compound interest and compounding frequency settings

### Changed
- **Complete UI Redesign** - Modern interface with softer colors, improved navigation, and better layout
- **Color Scheme** - Reduced brightness and contrast for better eye comfort (primary: #1a4d47, secondary: #d4a574)
- **Student Dashboard Layout** - Added sticky left sidebar navigation for quick access to all features
- **Economy Health Messages** - Improved warnings with absolute values and specific dollar recommendations
- **Tab Navigation** - Fixed CSS scoping to restore visibility across 15+ multi-tab pages

### Fixed
- **Critical: Restored Pending Actions section** on admin dashboard (store approvals, hall passes, insurance claims were missing)
- **Critical: Fixed invisible tabs** on Student Management, Store Management, and other multi-tab pages
- **Fixed missing navigation links** on login screens (account setup, recovery, privacy/terms)
- **Fixed CSS scoping issue** where `.nav-link` styles were applied globally instead of scoped to sidebar
- **Added missing Bootstrap Icons CSS** imports to admin and student layouts
- **Added missing utility classes** (`.btn-white`, `.icon-circle`) for redesigned UI

### Technical
- Database migration `a7b8c9d0e1f2` adds `is_long_term_goal` column to `store_items` table
- Updated `economy_balance.py` to skip long-term goal items in CWI validation
- Added Chart.js (v4.4.0) for savings projection visualization
- Improved query performance for weekly analytics calculations
- Updated forms.py with `is_long_term_goal` BooleanField

## [1.0.0] - 2024-11-29

### Milestone
First stable release of Classroom Token Hub! All critical security issues resolved and production-ready.

## [Unreleased] - Version 0.9.0 (Pre-1.0 Candidate)

### Project Status
The project is ready for version 1.0 release. All critical blockers have been resolved:
- ✅ **P0 Critical Data Leak:** Fixed and deployed (2025-11-29) - See [docs/security/CRITICAL_SAME_TEACHER_LEAK.md](docs/security/CRITICAL_SAME_TEACHER_LEAK.md)
- ✅ **P1 Deprecated Patterns:** All updated to Python 3.12+ and SQLAlchemy 2.0+ (2025-12-06)
- 🔄 **Backfill:** Legacy transaction data being backfilled with interactive verification

### Added (2025-12-11)
- **DEVELOPMENT.md** — Unified development priorities document consolidating all TODO files and roadmap
- **docs/technical-reference/ECONOMY_SPECIFICATION.md** — Financial system specification (moved from root)
- **docs/development/ECONOMY_BALANCE_CHECKER.md** — CWI implementation guide (moved from root)

### Changed (2025-12-11)
- **Major documentation consolidation:**
  - Merged `docs/development/TODO.md`, `docs/development/MULTI_TENANCY_TODO.md`, and `ROADMAP_TO_1.0.md` into single `DEVELOPMENT.md`
  - Updated all references to point to new unified documentation structure
  - Updated README.md to reflect v1.0 readiness (all critical blockers resolved)
  - Moved implementation reports to `docs/archive/` for historical reference
- **Security documentation updates:**
  - Updated `CRITICAL_SAME_TEACHER_LEAK.md` status to RESOLVED (deployed with backfill in progress)
  - Updated `docs/README.md` to remove "P0 BLOCKER" label

### Removed (2025-12-11)
- `docs/development/TODO.md` — Consolidated into DEVELOPMENT.md
- `docs/development/MULTI_TENANCY_TODO.md` — Consolidated into DEVELOPMENT.md
- `docs/development/TECHNICAL_DEBT_ISSUES.md` — Superseded by DEPRECATED_CODE_PATTERNS.md
- `ROADMAP_TO_1.0.md` — Consolidated into DEVELOPMENT.md

### Added (2025-12-04)
- **PROJECT_HISTORY.md** — Comprehensive document capturing project philosophy, evolution, and key milestones
- **docs/development/DEPRECATED_CODE_PATTERNS.md** — Technical debt tracking for Python 3.12+ and SQLAlchemy 2.0+ compatibility
- Documentation index updated with new security and archive sections

### Changed (2025-12-04)
- **Major documentation reorganization:**
  - Moved security audits to `docs/security/` (CRITICAL_SAME_TEACHER_LEAK.md, MULTI_TENANCY_AUDIT.md)
  - Moved development guides to `docs/development/` (JULES_SETUP.md, SEEDING_INSTRUCTIONS.md, TESTING_SUMMARY.md, MIGRATION_STATUS_REPORT.md)
  - Moved operations docs to `docs/operations/` (MULTI_TENANCY_FIX_DEPLOYMENT.md)
  - Archived historical fix summaries to `docs/archive/` (FIXES_SUMMARY.md, JOIN_CODE_FIX_SUMMARY.md, MIGRATION_FIX_SUMMARY.md, STAGING_MIGRATION_FIX.md)
- Updated `docs/README.md` with comprehensive documentation map including security and archive sections
- Updated main README with version 0.9.0 status and platform-agnostic deployment language
- Removed hardcoded IP addresses from GitHub Actions workflows (now use `secrets.PRODUCTION_SERVER_IP`)

### Removed (2025-12-04)
- **scripts/cleanup_duplicates.py** — Obsolete duplicate cleanup script (superseded by cleanup_duplicates_flask.py)
- Debug print statement in `app/routes/api.py:1198` (replaced with proper logging)

### Fixed (2025-12-04)
- Security: Removed hardcoded production server IP from CI/CD workflows

### Fixed (2025-12-05)
- Student portal: Removed the non-functional class switch button from the class banner and eliminated hover animations to reduce UI confusion.
- Student portal: Scoped payroll attendance and projection data to the currently selected class so multi-class students only see the active class statistics.

### Previous Changes
- Continued repository organization and documentation cleanup
- Moved `UPTIMEROBOT_SETUP.md` to `docs/operations/` for better organization
- Moved additional PR-specific reports to `docs/archive/pr-reports/`
- Updated `docs/operations/README.md` with comprehensive guide listings
- Added migration to align `rent_settings` schema with application model by including the `block` column
- Added migration to bring the `banking_settings` table in sync with the model by introducing the missing `block` column

---

## [2025-11-25] - Maintenance & Bypass Enhancements

### Added
- Persistent maintenance mode across deploys (`deploy_updates.sh`) with `--end-maintenance` explicit exit flag
- System admin and token-based maintenance bypass with session persistence (`maintenance_global_bypass`)
- System admin login access during maintenance (`/sysadmin/login`) and login link on `maintenance.html`
- Badge icon/text server-side mapping and status description rendering fallback when JS disabled
- Documentation for maintenance variables and operational workflow (see `docs/DEPLOYMENT.md`)

### Changed
- `deploy_updates.sh` now detects existing maintenance state instead of resetting it
- Bypass logic promotes valid sysadmin/token to global session for teacher/student role testing
- Tests expanded for bypass persistence and login accessibility

### Security
- Bypass token now stored only in environment and session flag; recommends rotation post-window

## [2025-11-24] - Repository Housekeeping

### Added
- Archive directory for historical PR reports (`docs/archive/pr-reports/`)
- README documentation for scripts directory
- README documentation for archived PR reports
- CLI command `normalize-claim-credentials` to backfill student and roster claim hashes to the canonical format

### Changed
- Moved utility scripts to `scripts/` directory for better organization:
  - `check_migration.py`
  - `check_orphaned_insurance.py`
  - `cleanup_duplicates.py`
  - `cleanup_duplicates_flask.py`
- Updated script references in documentation to reflect new paths
- Removed hardcoded paths from `check_orphaned_insurance.py`
- Repository housekeeping: organized files, removed obsolete files, and updated documentation
- Improved repository structure for better maintainability and navigation

### Removed
- Duplicate file: `SECURITY_AUDIT_INSURANCE_OVERHAUL (1).md`
- Moved PR-specific reports to archive (no longer in root):
  - `PR_DESCRIPTION.md`
  - `PR_DESCRIPTION_SECURITY_FIXES.md`
  - `CODE_REVIEW_SECURITY_FIXES.md`
  - `CODE_REVIEW_TECHNICAL_ANALYSIS.md`
  - `FINAL_CODE_REVIEW_SUMMARY.md`
  - `MIGRATION_REPORT_STAGING.md`
  - `REGRESSION_TEST_REPORT_STAGING.md`
  - `SECURITY_FIXES_CONSOLIDATED.md`
  - `SECURITY_FIX_VERIFICATION.md`
  - `SECURITY_FIX_VERIFICATION_UPDATED.md`
  - `SECURITY_AUDIT_INSURANCE_OVERHAUL.md`
  - `PRODUCTION_DEPLOYMENT_INSTRUCTIONS.md`

## [2025-11-20] - Feature Updates

### Added
- Align tap projected pay with payroll settings (#235)
- Simple vs compound interest options with configurable frequency (#233)

### Fixed
- Savings rate input validation error for hidden fields (#231)
- Normalize tap event actions for payroll counts (#230)
- Hall pass network errors and missing status updates (#229)
- Student template redesign to match admin layout (#225, #227)

## [2025-11-19] - Architecture Refactor

### Added
- Comprehensive system architecture documentation
- System admin portal with error logging
- Custom error pages for all major HTTP errors
- GitHub Actions CI/CD to DigitalOcean

### Changed
- Refactored monolithic app.py to modular blueprint architecture

---

## Documentation Maintenance

This changelog tracks significant changes to the codebase. For:
- **Current development tasks**: See [docs/development/TODO.md](docs/development/TODO.md)
- **Planned features**: See [docs/development/TODO.md](docs/development/TODO.md) Roadmap section
- **Technical details**: See [docs/technical-reference/architecture.md](docs/technical-reference/architecture.md)

## Changelog Guidelines

When adding entries:
- Group changes by type: Added, Changed, Deprecated, Removed, Fixed, Security
- Reference PR/issue numbers where applicable
- Use present tense for entries
- Keep entries concise but informative
- Update the date when moving Unreleased to a version

**Last Updated:** 2025-12-04
