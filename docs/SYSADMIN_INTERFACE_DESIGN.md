# System Admin Interface - Comprehensive Design

## Overview
The System Admin interface is the super-user control panel for the Classroom Token Hub. It provides complete visibility and control over all aspects of the system.

## Current Capabilities (Implemented)
- ✅ Generate admin invite codes
- ✅ View invite code status
- ✅ View system admins list
- ✅ View system logs (file-based)
- ✅ View error logs (database)
- ✅ Test error pages
- ✅ TOTP-based authentication

## Proposed New Capabilities

### 1. User Management

#### A. Admin (Teacher) Management
**Route:** `/sysadmin/admins`

**Features:**
- View all admin accounts with details:
  - Username
  - Creation date
  - TOTP setup status
  - Number of students (once multi-tenancy is implemented)
  - Last login timestamp
  - Total logins count

- **Delete Admin Account:**
  - Confirmation modal with warnings
  - Options:
    - [ ] Delete admin only (reassign students to another teacher)
    - [ ] Delete admin and all their students (DANGEROUS)
    - [ ] Delete admin and transfer students to specific teacher
  - Show impact before deletion (X students, Y transactions, etc.)
  - Soft delete option (mark as inactive instead of hard delete)

- **Reset Admin TOTP:**
  - Emergency access if admin loses authenticator
  - Generate new TOTP secret
  - Display QR code

- **View Admin Activity:**
  - Last login
  - Recent actions
  - Payroll runs
  - Transaction voids

#### B. Student Management
**Route:** `/sysadmin/students`

**Features:**
- View all students across all teachers:
  - Student ID
  - First name (encrypted, decrypted for display)
  - Username hash (first 8 chars)
  - Associated teacher/admin
  - Balance
  - Last login
  - Account status

- **Search/Filter:**
  - By teacher
  - By name (fuzzy search)
  - By balance range
  - By account status (active/inactive)
  - By creation date

- **Delete Student:**
  - Confirmation modal
  - Show impact (transactions, items owned, etc.)
  - Option to void transactions first
  - Hard delete or soft delete

- **Bulk Operations:**
  - Delete all students for a teacher
  - Export student data to CSV
  - Bulk balance adjustment

- **Transfer Student:**
  - Move student to different teacher
  - Preserve all transaction history

#### C. Orphaned Data Cleanup
**Route:** `/sysadmin/cleanup`

**Features:**
- Identify orphaned records:
  - Students with no teacher (after multi-tenancy)
  - Transactions with deleted students
  - Store items with deleted owners
  - Hall pass logs with deleted students

- Cleanup tools:
  - Reassign orphaned students
  - Archive old transactions
  - Purge soft-deleted records

### 2. System Statistics Dashboard
**Route:** `/sysadmin/stats`

**Features:**
- **Overview Cards:**
  - Total System Admins
  - Total Admins (Teachers)
  - Total Students
  - Total Active Students (logged in last 30 days)
  - Total Transactions
  - Total Tokens in Circulation

- **Charts/Graphs:**
  - Student registrations over time
  - Transaction volume over time
  - Error rates by type
  - Login activity by hour/day

- **Database Statistics:**
  - Table sizes
  - Database size
  - Index health
  - Query performance (if available)

### 3. System Configuration
**Route:** `/sysadmin/config`

**Features:**
- **Global Settings:**
  - Session timeout duration
  - Token to display ($ or tokens)
  - Timezone settings
  - Date/time formats

- **Feature Flags:**
  - Enable/disable insurance system
  - Enable/disable rent system
  - Enable/disable store
  - Enable/disable hall passes

- **Email Settings:**
  - Support email address
  - SMTP configuration (future)

- **Security Settings:**
  - Password requirements
  - Session security
  - TOTP enforcement

### 4. Audit Log
**Route:** `/sysadmin/audit`

**Features:**
- Track critical actions:
  - Admin account creation/deletion
  - Student account deletion
  - Payroll runs
  - Transaction voids
  - Configuration changes
  - TOTP resets

- Filter by:
  - Action type
  - User (who did it)
  - Date range
  - Target (what was affected)

- Export audit log to CSV

### 5. Database Maintenance
**Route:** `/sysadmin/maintenance`

**Features:**
- **Backup/Export:**
  - Export full database to SQL dump
  - Export student data to CSV
  - Export transaction history

- **Data Archival:**
  - Archive old transactions (> 1 year)
  - Archive deleted students
  - Purge error logs older than X months

- **Database Health:**
  - Check for data inconsistencies
  - Verify foreign key integrity
  - Find duplicate records
  - Optimize tables

### 6. Communication (Future)
**Route:** `/sysadmin/announcements`

**Features:**
- System-wide announcements
- Maintenance notifications
- Emergency alerts
- Message to all teachers
- Message to all students

## UI Layout Proposal

### Main Dashboard Structure

```
┌─────────────────────────────────────────────────────────────┐
│  System Admin Dashboard                          [Logout]    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Admin   │  │ Students │  │  Errors  │  │  Stats   │   │
│  │  Mgmt    │  │   Mgmt   │  │   Logs   │  │Dashboard │   │
│  │   👥     │  │    👨‍🎓    │  │    ⚠️     │  │    📊    │   │
│  │  5 admins│  │120 stud. │  │  12 err. │  │  Live    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Quick Actions                                       │   │
│  │  • Generate Invite Code                             │   │
│  │  • Create System Admin                              │   │
│  │  • View Audit Log                                   │   │
│  │  • Test Error Pages                                 │   │
│  │  • Database Backup                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Recent Activity                                     │   │
│  │  • Admin "teacher1" logged in (2 min ago)           │   │
│  │  • Payroll run by "teacher2" (1 hour ago)           │   │
│  │  • Student deleted by sysadmin (3 hours ago)        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  System Health                                       │   │
│  │  Database: ●  Healthy (2.3 GB)                      │   │
│  │  Errors:   ●  12 in last 24h                        │   │
│  │  Uptime:   ●  15 days 3 hours                       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Admin Management Page

```
┌─────────────────────────────────────────────────────────────┐
│  Admin (Teacher) Management                  [Back]          │
├─────────────────────────────────────────────────────────────┤
│  [Search...]  [Filter: All ▼]  [+ Create Admin]             │
├─────────────────────────────────────────────────────────────┤
│  Username   │ Students │ Created    │ Last Login │ Actions  │
├─────────────┼──────────┼────────────┼────────────┼──────────┤
│  teacher1   │   45     │ 2024-01-15 │ 2 hrs ago  │ [View]   │
│             │          │            │            │ [Delete] │
├─────────────┼──────────┼────────────┼────────────┼──────────┤
│  teacher2   │   38     │ 2024-02-20 │ 1 day ago  │ [View]   │
│             │          │            │            │ [Delete] │
└─────────────────────────────────────────────────────────────┘
```

### Delete Admin Modal

```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️  Delete Admin: teacher1                                 │
├─────────────────────────────────────────────────────────────┤
│  This admin has:                                             │
│  • 45 students                                              │
│  • 1,234 transactions                                       │
│  • Last login: 2 hours ago                                  │
│                                                               │
│  What should happen to their students?                      │
│  ⚪ Reassign to another teacher: [Select ▼]                 │
│  ⚪ Delete all students and their data (CANNOT BE UNDONE)   │
│  ⚪ Leave students orphaned (requires cleanup later)        │
│                                                               │
│  ☑️ I understand this action is permanent                   │
│                                                               │
│  [Cancel]  [Delete Admin]                                   │
└─────────────────────────────────────────────────────────────┘
```

### Student Management Page

```
┌─────────────────────────────────────────────────────────────┐
│  Student Management                          [Back]          │
├─────────────────────────────────────────────────────────────┤
│  [Search...]  [Teacher: All ▼]  [Status: All ▼]             │
│  [Export CSV]  [Bulk Actions ▼]                             │
├─────────────────────────────────────────────────────────────┤
│  Name    │ Teacher   │ Balance │ Last Login │ Actions       │
├──────────┼───────────┼─────────┼────────────┼───────────────┤
│  Alice   │ teacher1  │  $45.50 │ 1 hour ago │ [View] [Del]  │
│  Bob     │ teacher1  │  $23.00 │ 2 days ago │ [View] [Del]  │
│  Charlie │ teacher2  │  $67.25 │ 30 min ago │ [View] [Del]  │
└─────────────────────────────────────────────────────────────┘
```

## Navigation Structure

```
System Admin Dashboard
├── Dashboard (Home)
├── User Management
│   ├── Admins (Teachers)
│   │   ├── View All
│   │   ├── Create New
│   │   └── Invite Codes
│   ├── Students
│   │   ├── View All
│   │   ├── Search
│   │   └── Bulk Operations
│   └── System Admins
│       ├── View All
│       └── Create New
├── Monitoring
│   ├── Error Logs (Database)
│   ├── System Logs (File)
│   ├── Audit Log
│   └── Statistics Dashboard
├── Testing & Tools
│   ├── Test Error Pages
│   ├── Database Cleanup
│   └── Data Export
├── System Configuration
│   ├── Global Settings
│   ├── Feature Flags
│   └── Security Settings
└── Maintenance
    ├── Database Backup
    ├── Data Archival
    └── Health Check
```

## Color Scheme

- **Primary (Blue):** General actions, navigation
- **Success (Green):** Successful operations, create
- **Warning (Yellow/Orange):** Caution, test actions
- **Danger (Red):** Delete, critical errors
- **Info (Light Blue):** Information, stats
- **Dark:** System admins, advanced features

## Security Considerations

1. **All admin deletion requires confirmation**
2. **Show impact before any destructive action**
3. **Audit log for all critical actions**
4. **TOTP required for sysadmin login**
5. **Session timeout for inactive sysadmins**
6. **Rate limiting on bulk operations**
7. **Backup before major deletions**

## Implementation Priority

### Phase 1 (Current Session) - High Priority
- [x] Error testing and monitoring (DONE)
- [ ] Admin (teacher) management page
- [ ] Delete admin functionality
- [ ] Student management page
- [ ] Delete student functionality

### Phase 2 (Next Session) - Medium Priority
- [ ] Statistics dashboard
- [ ] Audit log
- [ ] Database cleanup tools
- [ ] Data export features

### Phase 3 (Future) - Low Priority
- [ ] System configuration UI
- [ ] Communication/announcements
- [ ] Advanced analytics
- [ ] Multi-tenancy support

## Mockups / Wireframes

(To be added: Screenshots of actual implementation)

## User Stories

1. **As a system admin, I want to delete a teacher account and reassign their students, so I can clean up after staff changes.**

2. **As a system admin, I want to see all students across all teachers, so I can monitor the entire system.**

3. **As a system admin, I want to view error logs in a friendly interface, so I can debug issues quickly.**

4. **As a system admin, I want to test error pages without breaking anything, so I can verify the user experience.**

5. **As a system admin, I want to see system statistics, so I can monitor growth and usage.**

6. **As a system admin, I want to audit who did what, so I can track accountability.**

## Success Metrics

- ✅ Sysadmin can perform all user management tasks
- ✅ No accidental data loss (confirmations work)
- ✅ All actions are logged for audit
- ✅ Interface is intuitive and requires no training
- ✅ Performance remains good with large datasets
