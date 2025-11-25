# Changelog

All notable changes to the Classroom Token Hub project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows semantic versioning principles.

## [Unreleased]

### Added
- Archive directory for historical PR reports (`docs/archive/pr-reports/`)
- README documentation for scripts directory
- README documentation for archived PR reports

### Changed
- Moved utility scripts to `scripts/` directory for better organization:
  - `check_migration.py`
  - `check_orphaned_insurance.py`
  - `cleanup_duplicates.py`
  - `cleanup_duplicates_flask.py`
- Updated script references in documentation to reflect new paths
- Removed hardcoded paths from `check_orphaned_insurance.py`

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

## [Recent Updates] - 2025-11-24

### Changed
- Repository housekeeping: organized files, removed obsolete files, and updated documentation
- Improved repository structure for better maintainability and navigation

## [Recent Updates] - 2025-11-20

### Added
- Align tap projected pay with payroll settings (#235)
- Simple vs compound interest options with configurable frequency (#233)

### Fixed
- Savings rate input validation error for hidden fields (#231)
- Normalize tap event actions for payroll counts (#230)
- Hall pass network errors and missing status updates (#229)
- Student template redesign to match admin layout (#225, #227)

## [Previous Updates] - 2025-11-19

### Added
- Comprehensive system architecture documentation
- System admin portal with error logging
- Custom error pages for all major HTTP errors
- GitHub Actions CI/CD to DigitalOcean

### Changed
- Refactored monolithic app.py to modular blueprint architecture

## Documentation Maintenance

This changelog tracks significant changes to the codebase. For:
- **Current development tasks**: See [docs/development/TODO.md](docs/development/TODO.md)
- **Planned features**: See [docs/development/TODO.md](docs/development/TODO.md) Roadmap section
- **Technical details**: See [docs/technical-reference/architecture.md](docs/technical-reference/architecture.md)

---

## Changelog Guidelines

When adding entries:
- Group changes by type: Added, Changed, Deprecated, Removed, Fixed, Security
- Reference PR/issue numbers where applicable
- Use present tense for entries
- Keep entries concise but informative
- Update the date when moving Unreleased to a version

## [Maintenance & Bypass Enhancements] - 2025-11-25

### Added
- Persistent maintenance mode across deploys (`deploy_updates.sh`) with `--end-maintenance` explicit exit flag.
- System admin and token-based maintenance bypass with session persistence (`maintenance_global_bypass`).
- System admin login access during maintenance (`/sysadmin/login`) and login link on `maintenance.html`.
- Badge icon/text server-side mapping and status description rendering fallback when JS disabled.
- Documentation for maintenance variables and operational workflow (see `docs/DEPLOYMENT.md`).

### Changed
- `deploy_updates.sh` now detects existing maintenance state instead of resetting it.
- Bypass logic promotes valid sysadmin/token to global session for teacher/student role testing.
- Tests expanded for bypass persistence and login accessibility.

### Security
- Bypass token now stored only in environment and session flag; recommends rotation post-window.

### Notes
- To end maintenance: workflow toggle, manual `.env` edit, or `./deploy_updates.sh --end-maintenance`.
- Optional future enhancements: explicit disable bypass route, audit logging, token rotation helper.

**Last Updated:** 2025-11-25
