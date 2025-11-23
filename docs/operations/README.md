# Operations Documentation

This directory contains operational guides and troubleshooting documentation for managing the Classroom Token Hub in production.

## Available Guides

### [Cleanup Duplicate Students](CLEANUP_DUPLICATES.md)

Guide for identifying and safely removing duplicate student records that may have been created due to roster upload issues.

**Use this when:**
- You notice duplicate students in the system
- Students appear multiple times in different blocks
- After fixing a roster upload bug

**Key features:**
- Uses Flask script to properly handle encrypted fields
- Preserves all transaction history and related data
- Safe migration of data from duplicates to primary records
- Preview mode to see what will happen before making changes

### [Demo Session Lifecycle and Cleanup](DEMO_SESSIONS.md)

How to monitor and clean demo student sessions that power the admin “view as student” experience.

**Use this when:**
- You need to verify demo sessions are expiring after the 10-minute limit
- An expired demo student remains visible in the admin UI
- The background cleanup job is paused or failing

**Key features:**
- Documents automatic cleanup paths (logout, scheduled job, route guard)
- Provides a manual cleanup snippet using `cleanup_demo_student_data`
- Notes the foreign-key-safe deletion order and required transaction commit

## Adding New Operational Guides

When creating new operational documentation:

1. **Create a descriptive filename** (e.g., `RESET_DATABASE.md`, `BACKUP_RESTORE.md`)
2. **Include these sections:**
   - Problem/Situation description
   - Prerequisites/Requirements
   - Step-by-step instructions
   - Safety warnings
   - Verification steps
   - Rollback procedures (if applicable)
3. **Update this README** with a link and description
4. **Cross-reference** from relevant technical documentation

## Related Documentation

- **[Deployment Guide](../DEPLOYMENT.md)** - Initial setup and deployment procedures
- **[Migration Guide](../development/MIGRATION_GUIDE.md)** - Database schema migrations
- **[System Admin Design](../development/SYSADMIN_INTERFACE_DESIGN.md)** - Admin interface features

## Emergency Procedures

For critical issues:

1. Check the relevant operational guide in this directory
2. Review error logs via the System Admin portal
3. Consult the [Troubleshooting section](../README.md#troubleshooting) in main docs
4. Review recent changes in [CHANGELOG.md](../../CHANGELOG.md)

---

**Last Updated:** 2025-11-20
**Maintained by:** Project maintainers and operations team
