# Changelog

All notable changes to the Classroom Token Hub project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows semantic versioning principles.


## [Unreleased]

### Security
- **CRITICAL: Fixed PromptPwnd AI Prompt Injection Vulnerability** - Disabled vulnerable `summary.yml` GitHub Actions workflow
  - Workflow used AI inference (`actions/ai-inference@v1`) with untrusted user input from issue titles/bodies
  - Attack vector: Any user could create an issue with malicious prompt injection to leak `GITHUB_TOKEN` or manipulate workflows
  - Remediation: Disabled workflow by renaming to `summary.yml.DISABLED`
  - Impact: No exploitation detected - vulnerability fixed proactively
  - Documentation: See `docs/security/PROMPTPWND_REMEDIATION.md` for full details
  - Reference: [Aikido Security PromptPwnd Disclosure](https://www.aikido.dev/blog/promptpwnd-ai-prompt-injection-in-github-actions) (December 2025)
- **Comprehensive Attack Surface Security Audit Completed** - Full security review of codebase, CI/CD, and infrastructure
  - Audited: GitHub Actions workflows, authentication, authorization, encryption, multi-tenancy, dependencies, and API security
  - Findings: 16 total findings (2 critical, 2 high, 3 medium, 4 low, 5 informational)
  - Critical issues: AI prompt injection (fixed), SSH host key verification disabled (open)
  - Strengths: Excellent CSRF protection, SQL injection prevention, XSS mitigation, PII encryption, multi-tenancy isolation
  - Recommendations: Enable SSH host key verification, update cryptography package, improve secrets management
  - Documentation: See `docs/security/COMPREHENSIVE_ATTACK_SURFACE_AUDIT_2025.md` for complete report

## [1.2.1] - 2025-12-21

### Added
- **Comprehensive Legacy Account Migration Script** - Complete migration tool for transitioning all legacy accounts to new multi-tenancy system
  - Migrates students with `teacher_id` to claim-based enrollment system
  - Creates missing `StudentTeacher` associations and `TeacherBlock` entries
  - Backfills `join_code` for all TeacherBlock entries
  - Backfills `join_code` for transactions, tap events, and related tables with proper multi-tenancy isolation
  - **FIXED:** Transaction backfill now matches on BOTH `student_id` AND `teacher_id` to ensure correct period assignment for students in multiple periods with same teacher
  - **FIXED:** Block names normalized to uppercase for consistency across database
  - **OPTIMIZED:** Phase 5 backfill uses CTE with `DISTINCT ON` instead of correlated subqueries for significantly better performance on large datasets
  - Includes dry-run mode for safe preview before applying changes
  - Provides comprehensive verification and error reporting
  - Located at: `scripts/comprehensive_legacy_migration.py`
- **Comprehensive Test Suite for Legacy Migration** - Full test coverage for migration script
  - Tests all 5 migration phases including Phase 5 (related tables backfill)
  - Tests critical multi-period student scenarios
  - Tests idempotency and error handling
  - Tests block casing normalization
  - Tests rollback on errors
  - Tests CTE performance optimization for Phase 5
  - Tests tables with and without period columns
  - Located at: `tests/test_comprehensive_legacy_migration.py`
- **Legacy Account Migration Documentation** - Complete guide for migration process
  - Historical context and migration strategy
  - Step-by-step deployment instructions
  - Troubleshooting common issues
  - Post-migration verification procedures
  - Roadmap for deprecating `teacher_id` column
  - Located at: `docs/operations/LEGACY_ACCOUNT_MIGRATION.md`
- **Join Code Schema Audit Tool** - `scripts/inspect_join_code_columns.py` lists which tables have or are missing `join_code` to support multi-tenancy audits
- **StudentBlock Join Code Migration** - Added idempotent migration (`a1b2c3d4e5f8`) to create `join_code` column and index on `student_blocks`, with safeguards for partially applied schemas

### Changed
- Preparing for final deprecation of `teacher_id`-based linkage system
- All legacy data now ready for migration to `join_code`-based multi-tenancy
- Hardened migration best practices documentation for avoiding duplicate-column errors in `student_blocks` hotfix scenarios
- Refreshed maintenance page copy and styling for clearer outage messaging

### Fixed
- Closed multi-tenancy gaps by adding `join_code` propagation to overdraft fees, bonus/bulk payroll postings, insurance reimbursements, manual payments, and bug-report rewards
- Improved bonus join_code lookup performance to reduce N+1 queries during mass payouts

## [1.2.0] - 2025-12-18

### Added
- **Progressive Web App (PWA) Support** - Full PWA implementation for improved mobile experience
  - Web app manifest with app metadata and icon configuration
  - Service worker with intelligent caching strategies (cache-first for static assets, network-first for CDN resources)
  - Offline fallback page with user-friendly offline experience
  - PWA installation capability on mobile devices (Add to Home Screen)
  - Multi-tenancy-safe caching that excludes authenticated routes
  - Automatic cache cleanup and version management
- **Mobile Experience Enhancements** - Dedicated mobile templates for student portal with responsive navigation and improved touch targets
- **Accessibility Improvements** - Enhancements following WCAG 2.1 AA guidelines
  - Added ARIA labels to mobile navigation and interactive elements
  - Improved keyboard navigation support
  - Enhanced screen reader compatibility
  - Better color contrast ratios
- **UI Documentation** - Added `docs/PWA_ICON_REQUIREMENTS.md` and `TEMPLATE_REDESIGN_RECOMMENDATIONS.md`
  - PWA icon asset generation instructions
  - UI redesign patterns and guidelines
  - Best practices for accordion/collapsible patterns
  - Color scheme guidelines for consistent visual hierarchy

### Changed
- **Attendance Terminology** - Renamed "Tap In/Out" to "Start Work/Break Done" for clarity
  - Updated user-facing text throughout student portal
  - Updated frontend API actions and documentation
  - Maintained backward compatibility in database actions
- **Admin UI Redesigns** - Modernized admin templates with collapsible accordion sections
  - **Insurance Policy Edit Page** - Eliminated overflow issues with progressive disclosure layout
  - **Store Item Edit Page** - Reduced scrolling with accordion sections for Bundle, Bulk Discount, and Advanced settings
  - **Rent Settings Page** - Better organization with collapsible sections
  - **Feature Settings** - Simplified to single-column, collapsible cards
  - Added visual "Active" badges to accordion headers indicating when sections have configured settings
- **Mobile Dashboard** - Simplified single-column layout with attendance card and tap buttons
- **Mobile Store** - Improved item list layout with larger purchase buttons
- **Theme Consistency** - Aligned mobile templates with main application theme colors

### Fixed
- **Critical: Multi-Tenancy Payroll Bug** - Fixed payroll calculations leaking data across class periods (#664)
  - Ensured all payroll queries properly scoped by join_code
  - Added multi-tenancy tests for payroll system
- **Payroll JSON Error** - Fixed "Run Payroll Now" button returning HTML instead of JSON (#668)
  - Resolved "Unexpected token '<!DOCTYPE'" error
  - Properly returns JSON response for AJAX requests
- **Timezone Handling** - Fixed timezone comparison error in payroll calculation (#666)
  - Corrected UTC normalization for payroll scheduling
  - Fixed edge cases with daylight saving time transitions
- **PWA Icon Rendering** - Fixed Material Symbols icons not loading in PWA mode (#672, #676)
  - Root cause: Service Worker intercepting Google Fonts with incorrect caching strategy
  - Solution: Service Worker now bypasses Google Fonts, letting browser handle natively
  - Added font preload and fallback CSS for Material Symbols
- **Mobile PWA Navigation** - Restored icons and removed horizontal scrolling (#674)
  - Tightened bottom navigation layout for small screens
  - Added overflow-x protection and responsive media queries
- **Desktop PWA Rendering** - Added PWA support to desktop templates for mobile viewing (#675)
  - Added PWA meta tags (theme-color, apple-mobile-web-app-capable)
  - Added mobile bottom navigation when sidebar is hidden
- **Auto Tap-Out Regression** - Fixed test failures due to missing teacher_id context in auto tap-out logic (#670)

### Technical
- Service worker cache bumped to v5 to force updates
- Added comprehensive multi-tenancy tests for payroll
- Improved mobile responsiveness across all admin templates
- Enhanced documentation organization and clarity

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

**Last Updated:** 2025-12-18
