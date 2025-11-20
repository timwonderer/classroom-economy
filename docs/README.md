# Classroom Token Hub - Documentation Index

Welcome to the Classroom Token Hub documentation! This index will help you find the information you need quickly.

---

## Quick Start

**New to the project?** Start here:
1. Read the [main README](../README.md) for project overview and setup
2. Review the [Architecture Guide](technical-reference/architecture.md) to understand the system
3. Check the [Development TODO](development/TODO.md) for current priorities

**Want to contribute?** See [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## Documentation Structure

### 📖 User Guides

Documentation for end users of the system:

- **[Student Guide](user-guides/student_guide.md)** - How students use the platform
  - Account setup and login
  - Dashboard features
  - Making purchases and transfers
  - Using hall passes and insurance

- **[Teacher Manual](user-guides/teacher_manual.md)** - Comprehensive guide for teachers/admins
  - Admin dashboard overview
  - Student management
  - Running payroll
  - Managing the store, rent, and insurance systems
  - Attendance tracking

---

### 📚 Technical Reference

Technical documentation for developers:

- **[Architecture Guide](technical-reference/architecture.md)** - Complete system architecture
  - Technology stack
  - Project structure
  - Design patterns and conventions
  - Security architecture
  - Authentication system
  - Development guidelines

- **[Database Schema](technical-reference/database_schema.md)** - Complete database documentation
  - All models and relationships
  - Field descriptions
  - Indexes and constraints

- **[API Reference](technical-reference/api_reference.md)** - REST API documentation
  - All endpoints
  - Request/response formats
  - Authentication requirements
  - Status codes

---

### 🎯 Development

Resources for active development:

- **[TODO](development/TODO.md)** - Current development tasks and priorities
  - Critical bugs
  - High priority features
  - Medium priority features
  - Technical debt
  - Roadmap

- **[Multi-Tenancy Roadmap](development/MULTI_TENANCY_TODO.md)** - Multi-teacher support implementation plan
  - Database changes needed
  - Code changes required
  - Migration strategy
  - Completion status

- **[System Admin Interface Design](development/SYSADMIN_INTERFACE_DESIGN.md)** - System admin features
  - Current capabilities
  - Proposed enhancements
  - Design philosophy

- **[Migration Guide](development/MIGRATION_GUIDE.md)** - Database migration help
  - Migration consolidation
  - Resolving migration conflicts
  - Step-by-step procedures

---

### 🚀 Deployment & Operations

- **[Deployment Guide](DEPLOYMENT.md)** - How to deploy the application
  - Environment variables
  - Deployment platforms
  - CI/CD workflows
  - Production checklist

- **[Operations Guides](operations/)** - Operational procedures and troubleshooting
  - Cleanup duplicate students
  - Database maintenance
  - Production issue resolution

- **[Changelog](../CHANGELOG.md)** - Version history and notable changes
  - Recent updates
  - Feature additions
  - Bug fixes
  - Breaking changes

---

## Common Tasks

### For Students
- **How do I log in?** → [Student Guide - Login](user-guides/student_guide.md#login)
- **How do I make a purchase?** → [Student Guide - Store](user-guides/student_guide.md#store)
- **How do I transfer money?** → [Student Guide - Transfers](user-guides/student_guide.md#transfers)

### For Teachers
- **How do I add students?** → [Teacher Manual - Student Management](user-guides/teacher_manual.md#student-management)
- **How do I run payroll?** → [Teacher Manual - Payroll](user-guides/teacher_manual.md#payroll)
- **How do I manage the store?** → [Teacher Manual - Store Management](user-guides/teacher_manual.md#store-management)

### For Developers
- **How do I set up my dev environment?** → [Architecture Guide - Development Guidelines](technical-reference/architecture.md#development-guidelines)
- **What's the database structure?** → [Database Schema](technical-reference/database_schema.md)
- **Where are the API endpoints?** → [API Reference](technical-reference/api_reference.md)
- **What should I work on next?** → [TODO](development/TODO.md)
- **How do I create a migration?** → [Migration Guide](development/MIGRATION_GUIDE.md)
- **What changed recently?** → [Changelog](../CHANGELOG.md)

### For Operations/DevOps
- **How do I clean up duplicate students?** → [Operations - Cleanup Duplicates](operations/CLEANUP_DUPLICATES.md)
- **What are the deployment steps?** → [Deployment Guide](DEPLOYMENT.md)
- **What's new in this version?** → [Changelog](../CHANGELOG.md)

---

## Documentation Standards

### Keeping Documentation Current

When making changes to the codebase:

- **Adding a new feature?** Update the relevant user guide and API reference
- **Changing database schema?** Update the database schema documentation
- **Completing a task?** Update TODO.md and move to "Recently Completed"
- **Refactoring?** Update the architecture guide if structure changes
- **Adding environment variables?** Update the deployment guide

### Writing Documentation

- Use clear, concise language
- Include code examples where helpful
- Keep table of contents updated
- Link to related documentation
- Update "Last Updated" dates
- Consider your audience (students, teachers, or developers)

---

## Getting Help

### Troubleshooting

1. **Check the documentation** - Most common questions are answered here
2. **Search the codebase** - Look for similar implementations
3. **Review error logs** - System admins can access detailed error logs
4. **Check TODO.md** - Known issues and planned work are tracked there
5. **Read commit history** - `git log` can explain why things were done

### Resources

- **Main README**: [../README.md](../README.md)
- **Contributing Guidelines**: [../CONTRIBUTING.md](../CONTRIBUTING.md)
- **License Information**: [../LICENSE](../LICENSE)
- **GitHub Issues**: For bug reports and feature requests

---

## Documentation Overview

| Document | Audience | Purpose | Last Updated |
|----------|----------|---------|--------------|
| [Architecture Guide](technical-reference/architecture.md) | Developers | System architecture and patterns | 2025-11-19 |
| [Database Schema](technical-reference/database_schema.md) | Developers | Complete database reference | 2025-11-18 |
| [API Reference](technical-reference/api_reference.md) | Developers | REST API documentation | 2025-11-18 |
| [Student Guide](user-guides/student_guide.md) | Students | How to use the platform | 2025-11-18 |
| [Teacher Manual](user-guides/teacher_manual.md) | Teachers | Admin features and workflows | 2025-11-18 |
| [TODO](development/TODO.md) | Developers | Current tasks and priorities | 2025-11-18 |
| [Deployment Guide](DEPLOYMENT.md) | DevOps | Deployment instructions | 2025-11-18 |
| [Multi-Tenancy Roadmap](development/MULTI_TENANCY_TODO.md) | Developers | Multi-teacher feature plan | 2025-11-18 |
| [Migration Guide](development/MIGRATION_GUIDE.md) | Developers | Database migration help | 2025-11-18 |
| [Operations Guides](operations/) | DevOps/Operations | Operational procedures | 2025-11-20 |
| [Changelog](../CHANGELOG.md) | All | Version history and changes | 2025-11-20 |

---

## Project Status

**Current Version:** Active Development
**Production Status:** Controlled classroom testing
**License:** PolyForm Noncommercial 1.0.0

**Recent Major Updates:**
- ✅ Modular blueprint architecture (refactored from monolithic app.py)
- ✅ System admin portal with error logging and teacher management
- ✅ Custom error pages for all major HTTP errors
- ✅ Comprehensive documentation reorganization
- ✅ GitHub Actions CI/CD to DigitalOcean

**Next Major Features:**
- 🔄 Multi-tenancy (teacher data isolation)
- 🔄 Configurable payroll settings
- 🔄 Account recovery system
- 📋 Email notifications
- 📋 Audit logging

See [TODO.md](development/TODO.md) for complete task list and priorities.

---

**Last Updated:** 2025-11-20
**Maintained by:** Project maintainers and AI agents
**Questions?** Check the relevant documentation above or review the main README.
