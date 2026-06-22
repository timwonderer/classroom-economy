# ARC-SYS-001: System Admin Interface Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-SYS-001      | 1.1     | 2026-03-08     | 1.0        | Constitutional  |

## I. Purpose
This document defines the comprehensive architecture and capability set of the System Admin interface, the super-user control panel for the Classroom Token Hub.

## II. Scope
This specification governs the `/sysadmin` namespace, defining authentication requirements, implemented monitoring capabilities, user management tools, and support workflows available to super-users. It strictly defines the separation between teacher (admin) capabilities and system administrator capabilities.

## III. Authority Level
Constitutional (ARC Tier). This document is subordinate only to `INV-CORE-000` and `ARC-CORE-000`.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md` (Authority and Multi-tenancy isolation policies)
- `ARC-IDEN-001_Admin_Identity_Handling.md`

## V. Design Philosophy

### Role Separation
- **System Admins** manage the platform, infrastructure, teacher accounts, system-wide announcements, and escalated support issues.
- **Teachers (Admins)** manage their own distinct class economies and students.
- **Students** interact with their assigned class economy.

### Key Privacy Boundary
System Admins should not inherently manage individual student data directly. This ensures:
- Clear separation of responsibilities
- Reduced privacy exposure
- Proper delegation to the teacher level

## VI. Implemented Capabilities

The System Admin interface (`/sysadmin`) currently provides the following functional areas:

### 1. User and Teacher Management
- **Teacher List & Overview (`/manage-teachers`, `/teacher-overview`):** View all registered teachers, their active class periods, their signup dates, and recent logins.
- **Admin Account List (`/admins`):** Review teacher/admin accounts in a management-focused listing.
- **Invite Code Void (`/manage-teachers/void/<code_id>`):** Invalidate unused teacher signup invite codes.
- **Teacher Deletion (`/manage-teachers/delete/<admin_id>`):** Remove teacher accounts through the sysadmin namespace.
- **Period Deletion (`/delete-period/<admin_id>/<period>`):** Remove a teacher class period from the sysadmin interface.
- **Username Migration (`/username-migration`):** Execute updates for the legacy username standard.

### 2. Authentication & Security
- **Strict Access Control:** All routes gated strictly to System Admin accounts.
- **WebAuthn Passkeys (`/passkey/*`):** Sysadmins can register and authenticate using biometric passkeys, list active passkeys, and manage their credential settings.
- **TOTP Fallback:** Enforced Multi-Factor Authentication for non-passkey sign-ins.
- **Teacher TOTP Reset (`/admins/<admin_id>/reset-totp`):** Reset a teacher/admin's TOTP enrollment when recovery is required.
- **Teacher/Admin Deletion (`/admins/<admin_id>/delete`):** Remove teacher/admin credentials through the admin-account management flow.

### 3. Monitoring & Observability
- **System Dashboard (`/dashboard`):** High-level metrics view.
- **Grafana Integration (`/grafana/*`):** Proxied interface to an embedded or external Grafana dashboards for performance metrics.
- **Log Viewers:** 
  - File-based combined logs (`/combined-logs`)
  - Standard runtime logs (`/logs`)
  - Captured Error Logs (`/error-logs`)
- **Log Testing (`/logs-testing`):** Emit test log traffic to validate the logging pipeline and viewer surfaces.
- **Network Insights (`/network-activity`):** View active connections or incoming rate metrics.
- **Error Simulators (`/test-errors/*`):** Safely trigger and verify custom 400, 401, 403, 404, 500, and 503 error handlers.

### 4. Support and Escalations
- **Support Dashboard (`/support`):** Aggregate view of operations.
- **User Reports (`/user-reports/*`):** Review and update the status of incoming abuse, bug, or feedback reports.
- **Escalated Issues (`/issues/*`):** Triage technical issues escalated from teachers or system flags. Start reviews and mark resolutions.

### 5. Platform Communication
- **System Announcements (`/announcements/*`):** Create, edit, toggle visibility, and delete broadcast messages displayed across the platform to teachers and/or students.

Implementation note:
- The shared `Announcement` model supports both sysadmin-authored announcements and teacher-authored class announcements.
- Teacher announcement management lives in the separate `/admin/announcements/*` namespace and is not a sysadmin capability.

## VII. Future Capabilities (Proposed Roadmap)
- [ ] **Data Export Interfaces:** Web UI to trigger secure database dumps or CSV exports for backup compliance.
- [ ] **Feature Flags Configuration:** UI to dynamically toggle systemic capabilities (e.g., maintenance mode, global signups) without code deployment.
- [ ] **Audit Trail Expansion:** While backend logging tracks these, a fully searchable Sysadmin UI for the internal Audit Log is desired.

## VIII. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. All modifications to the sysadmin capabilities must be strictly reviewed for multi-tenancy and privacy compliance before amending this document.
