# Changelog

All notable changes to the Classroom Token Hub project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project follows semantic versioning principles.

## [Unreleased]

### Added
- Comprehensive documentation reorganization and housekeeping
- Operations documentation directory for operational guides
- Improved migrations README with quick reference commands

### Changed
- Moved cleanup guides to docs/operations/ for better organization

### Removed
- Obsolete merge documentation (MERGE_GUIDE.md, MERGE_STATUS.md)

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

**Last Updated:** 2025-11-20
