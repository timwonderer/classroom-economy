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

How to monitor and clean demo student sessions that power the admin "view as student" experience.

**Use this when:**
- You need to verify demo sessions are expiring after the 10-minute limit
- An expired demo student remains visible in the admin UI
- The background cleanup job is paused or failing

**Key features:**
- Documents automatic cleanup paths (logout, scheduled job, route guard)
- Provides a manual cleanup snippet using `cleanup_demo_student_data`
- Notes the foreign-key-safe deletion order and required transaction commit

### [Public Demo Environment (Teacher + Student)](DEMO_ENV_SETUP.md)

How to stand up the landing-page demo endpoints (teacher and student) using the built-in demo session lifecycle and seeded data.

**Use this when:**
- You need the `docs/index.html` demo iframes/buttons to point at a live demo
- Standing up a separate demo deployment that is isolated from production data
- Creating disposable demo student sessions for public previews

**Key features:**
- Reuses `create_demo_student` and the 10-minute auto-cleanup pipeline
- References existing scheduler job and schema
- Provides curl example to mint a demo session URL for embedding

### [UptimeRobot Monitoring Setup](UPTIMEROBOT_SETUP.md)

Complete guide for setting up UptimeRobot monitoring and creating a public status page.

**Use this when:**
- Setting up uptime monitoring for production
- Creating a public status page for users
- Configuring maintenance windows
- Troubleshooting monitoring issues

**Key features:**
- Health endpoint configuration (`/health`, `/health/deep`)
- Public status page setup
- Firewall configuration for UptimeRobot IPs
- Alert contact configuration

### [DigitalOcean & Cloudflare Setup](DIGITALOCEAN_CLOUDFLARE_SETUP.md)

Infrastructure setup guide for production deployment.

**Use this when:**
- Setting up production infrastructure
- Configuring firewall rules
- Managing Cloudflare proxy settings

### [Grafana Auth Proxy Troubleshooting](GRAFANA_AUTH_PROXY.md)

Checklist for debugging Grafana behind the system admin Nginx auth proxy.

**Use this when:**
- The sysadmin Grafana link is stuck in a redirect loop
- Grafana returns `ERR_CONNECTION_REFUSED` after authentication changes
- You need to verify the expected headers and `grafana.ini` subpath settings

### [PII Audit](PII_AUDIT.md)

Review of personally identifiable information handling in the multi-tenancy system.

**Use this when:**
- Conducting privacy audits
- Reviewing data handling practices
- Verifying PII encryption implementation

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

**Last Updated:** 2025-11-28
**Maintained by:** Project maintainers and operations team
