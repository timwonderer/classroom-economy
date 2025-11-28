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

### 🚀 Deployment & Operations
- **[Deployment Guide](DEPLOYMENT.md)** — Environment variables, CI/CD references, and production checklist.
- **[Operations Guides](operations/)** — Cleanup, demo session hygiene, and PII audit procedures.
- **[Changelog](../CHANGELOG.md)** — Notable changes and release notes.

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
