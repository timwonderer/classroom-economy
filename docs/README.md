# Classroom Token Hub - Documentation Index

Welcome to the Classroom Token Hub documentation! This index points you to the most relevant resources for your role.

---

## Start Here

1. Review the [project README](../README.md) for a high-level overview and setup steps.
2. Skim the [Architecture Guide](technical-reference/architecture.md) for structure, conventions, and security notes.
3. Check [Development TODO](development/TODO.md) for current priorities and follow-ups.
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

### 🎯 Development
- **[TODO](development/TODO.md)** — Active work, open questions, and recent wins.
- **[Multi-Tenancy Status](development/MULTI_TENANCY_TODO.md)** — Rollout notes and remaining hardening tasks.
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
- **[Critical Same-Teacher Leak](security/CRITICAL_SAME_TEACHER_LEAK.md)** — ⚠️ **P0 BLOCKER** - Data isolation issue requiring fix before 1.0.
- **[Validation Report](security/VALIDATION_REPORT.md)** — Input/output validation audit.
- **[Access & Secrets Report](security/ACCESS_AND_SECRETS_REPORT.md)** — Access control and secrets review.
- **[Source Code Vulnerability Report](security/SOURCE_CODE_VULNERABILITY_REPORT.md)** — Code security analysis.
- **[Network Vulnerability Report](security/NETWORK_VULNERABILITY_REPORT.md)** — Network security assessment.

### 📦 Archive
- **[Archived Fix Reports](archive/)** — Historical bug fix and feature implementation summaries.

---

## Common Questions
- **How do I add students?** → [Teacher Manual – Student Management](user-guides/teacher_manual.md#student-management)
- **How do I run payroll?** → [Teacher Manual – Payroll](user-guides/teacher_manual.md#payroll)
- **What’s the database structure?** → [Database Schema](technical-reference/database_schema.md)
- **Where are tenancy helpers?** → [`app/auth.py`](../app/auth.py) and [Multi-Tenancy Status](development/MULTI_TENANCY_TODO.md)
- **How do I clean demo sessions?** → [Operations – Demo Sessions](operations/DEMO_SESSIONS.md)

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
| [TODO](development/TODO.md) | Developers | Current tasks and priorities | 2025-11-23 |
| [Deployment Guide](DEPLOYMENT.md) | DevOps | Deployment instructions | 2025-11-25 |
| [Multi-Tenancy Status](development/MULTI_TENANCY_TODO.md) | Developers | Multi-teacher rollout plan | 2025-11-23 |
| [Migration Guide](development/MIGRATION_GUIDE.md) | Developers | Database migration help | 2025-11-18 |
| [Operations Guides](operations/) | Ops | Operational procedures | 2025-11-28 |
| [Changelog](../CHANGELOG.md) | All | Version history and changes | 2025-11-28 |

---
