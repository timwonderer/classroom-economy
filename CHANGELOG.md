# Changelog

All notable changes to the Classroom Token Hub project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows semantic versioning principles.

## [Unreleased]

### Changed
- Continued repository organization and documentation cleanup
- Moved `UPTIMEROBOT_SETUP.md` to `docs/operations/` for better organization
- Moved additional PR-specific reports to `docs/archive/pr-reports/`:
  - `PR_DESCRIPTION.md` (legacy student migration)
  - `FIX_MISSING_TEACHER_BLOCKS.md`
  - `MULTI_TENANCY_READINESS_REPORT.md`
- Updated `docs/operations/README.md` with comprehensive guide listings
- Updated `docs/archive/pr-reports/README.md` with new archived files

### Fixed
- Added migration to align `rent_settings` schema with application model by including the `block` column.
- Added migration to bring the `banking_settings` table in sync with the model by introducing the missing `block` column.
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

**Last Updated:** 2025-11-28
