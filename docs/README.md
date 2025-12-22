# Classroom Token Hub - Documentation Index

Welcome to the Classroom Token Hub documentation! This index points you to the most relevant resources for your role.

---

## Start Here

1. Review the [project README](../README.md) for a high-level overview and setup steps.
2. Skim the [Architecture Guide](technical-reference/architecture.md) for structure, conventions, and security notes.
3. Check [Development Priorities](../DEVELOPMENT.md) for current priorities, roadmap, and active tasks.
4. If you are operating the app, keep the [Deployment Guide](DEPLOYMENT.md) and [Operations README](operations/README.md) handy.

---

## Documentation Map

### 📖 User Guides
- **[Student Guide](user-guides/student_guide.md)** — Login, dashboard, store, transfers, hall passes.
- **[Teacher Manual](user-guides/teacher_manual.md)** — Admin dashboard, payroll, roster uploads, store/rent/insurance management.

### 🧭 Quick References
- **[Architecture Guide](technical-reference/architecture.md)** — Stack, project layout, patterns, and security posture.
- **[Database Schema](technical-reference/database_schema.md)** — Current models and relationships (includes multi-teacher links and payroll/rent/insurance tables).
- **[API Reference](technical-reference/api_reference.md)** — REST endpoints and authentication expectations.
- **[Economy Specification](technical-reference/ECONOMY_SPECIFICATION.md)** — Financial system ratios, CWI calculations, and balancing rules.
- **[Timezone Handling](technical-reference/TIMEZONE_HANDLING.md)** — UTC storage and timezone conversion patterns.

### 🎯 Development
- **[Development Priorities](../DEVELOPMENT.md)** — Current priorities, roadmap, version 1.0 status, and active tasks.
- **[Economy Balance Checker](development/ECONOMY_BALANCE_CHECKER.md)** — CWI implementation guide and API reference.
- **[Deprecated Code Patterns](development/DEPRECATED_CODE_PATTERNS.md)** — Code modernization tracking for Python 3.12+ and SQLAlchemy 2.0+.
- **[System Admin Interface](development/SYSADMIN_INTERFACE_DESIGN.md)** — Capabilities and UX principles for sysadmin flows.
- **[Migration Guide](development/MIGRATION_GUIDE.md)** — Alembic tips, consolidation steps, and conflict resolution.
- **[Jules Setup](development/JULES_SETUP.md)** — Development environment setup guide.
- **[Seeding Instructions](development/SEEDING_INSTRUCTIONS.md)** — Test data seeding procedures.
- **[Testing Summary](development/TESTING_SUMMARY.md)** — Test coverage and validation results.
- **[Migration Status](development/MIGRATION_STATUS_REPORT.md)** — Database migration status tracking.

### 🚀 Deployment & Operations
- **[Deployment Guide](DEPLOYMENT.md)** — Environment variables, CI/CD references, and production checklist.
- **[Operations Guides](operations/)** — Cleanup, demo session hygiene, and PII audit procedures.
- **[Multi-Tenancy Fix Deployment](operations/MULTI_TENANCY_FIX_DEPLOYMENT.md)** — Deployment procedures for multi-tenancy fixes.
- **[Changelog](../CHANGELOG.md)** — Notable changes and release notes.

### 🔒 Security
- **[Security Audit 2025](security/SECURITY_AUDIT_2025.md)** — Comprehensive security audit findings.
- **[Multi-Tenancy Audit](security/MULTI_TENANCY_AUDIT.md)** — Multi-tenancy security analysis.
- **[Critical Same-Teacher Leak](security/CRITICAL_SAME_TEACHER_LEAK.md)** — ✅ **RESOLVED** - Data isolation fix deployed (backfill in progress).
- **[Validation Report](security/VALIDATION_REPORT.md)** — Input/output validation audit.
- **[Access & Secrets Report](security/ACCESS_AND_SECRETS_REPORT.md)** — Access control and secrets review.
- **[Source Code Vulnerability Report](security/SOURCE_CODE_VULNERABILITY_REPORT.md)** — Code security analysis.
- **[Network Vulnerability Report](security/NETWORK_VULNERABILITY_REPORT.md)** — Network security assessment.

### 📦 Archive & Historical Documentation
- **[Archive Index](archive/README.md)** — Complete archive directory guide
- **[Release Notes](archive/releases/)** — All version release notes (v1.0.0 - v1.2.0)
- **[Implementation Reports](archive/implementation-reports/)** — Completed implementation guides and fix summaries
- **[Design Documentation](archive/design-docs/)** — Completed UI/UX design specs and implementation guides
- **[PR Reports](archive/pr-reports/)** — Historical pull request reviews and verifications
- **[Historical Fixes](archive/)** — Legacy fix summaries and migration notes

---

## Common Questions
- **How do I add students?** → [Teacher Manual – Student Management](user-guides/teacher_manual.md#student-management)
- **How do I run payroll?** → [Teacher Manual – Payroll](user-guides/teacher_manual.md#payroll)
- **What's the database structure?** → [Database Schema](technical-reference/database_schema.md)
- **Where are tenancy helpers?** → [`app/auth.py`](../app/auth.py) and [Development Priorities – Multi-Tenancy](../DEVELOPMENT.md#multi-tenancy-architecture)
- **How do I clean demo sessions?** → [Operations – Demo Sessions](operations/DEMO_SESSIONS.md)
- **What are current development priorities?** → [Development Priorities](../DEVELOPMENT.md)
- **How does the economy system work?** → [Economy Specification](technical-reference/ECONOMY_SPECIFICATION.md)

---

## Documentation Standards

- Update relevant docs with every feature, schema, or operational change.
- Keep “Last Updated” stamps current when modifying a document.
- Link related sections across user, developer, and ops docs to avoid duplication.

---

## Last Updated Snapshots

| Document | Audience | Purpose | Last Updated |
|----------|----------|---------|--------------|
| [Architecture Guide](technical-reference/architecture.md) | Developers | System architecture and patterns | 2025-11-23 |
| [Database Schema](technical-reference/database_schema.md) | Developers | Current models and relationships | 2025-11-23 |
| [API Reference](technical-reference/api_reference.md) | Developers | REST API documentation | 2025-11-23 |
| [Student Guide](user-guides/student_guide.md) | Students | How to use the platform | 2025-11-18 |
| [Teacher Manual](user-guides/teacher_manual.md) | Teachers | Admin features and workflows | 2025-11-18 |
| [Development Priorities](../DEVELOPMENT.md) | Developers | Current tasks, roadmap, and version status | 2025-12-22 |
| [Deployment Guide](DEPLOYMENT.md) | DevOps | Deployment instructions | 2025-11-25 |
| [Economy Specification](technical-reference/ECONOMY_SPECIFICATION.md) | Developers | Financial system spec | 2025-12-11 |
| [Migration Guide](development/MIGRATION_GUIDE.md) | Developers | Database migration help | 2025-11-18 |
| [Operations Guides](operations/) | Ops | Operational procedures | 2025-11-28 |
| [Changelog](../CHANGELOG.md) | All | Version history and changes | 2025-12-22 |
| [README](../README.md) | All | Project overview and quick start | 2025-12-22 |
| [Archive](archive/README.md) | All | Historical documentation | 2025-12-22 |

---
