# Release Notes - Version 1.4.0

**Release Date**: December 27, 2025

Version 1.4.0 is a feature-rich release focused on enhancing classroom communication and user experience. This release introduces a comprehensive announcement system for teachers, major UI/UX improvements across both teacher and student dashboards, streamlined authentication flows, and critical security fixes for URL redirection and Grafana access.

---

## 🎯 Release Highlights

### Announcement System for Class Communication
Teachers can now create and manage announcements for their class periods, with global announcement capability for system admins. Students see announcements prominently on their dashboards with the ability to dismiss them.

### Major UI/UX Redesign
Complete overhaul of dashboard interfaces with personalized greetings, enhanced account balance displays, accordion-style navigation, and improved mobile responsiveness throughout the application.

### Enhanced Security
Fixed critical open redirect vulnerabilities in student enrollment flow, resolved Grafana access issues with dual-layer solution, and improved authentication flow with better error handling.

---

## 🚀 New Features

### Announcement System

Teachers now have a powerful announcement system for communicating with their students:

**Core Capabilities**
- Create, edit, and delete announcements for specific class periods
- Rich text formatting support for announcement content
- Toggle announcement visibility (active/inactive)
- Announcements automatically filtered by class period
- System admins can create global announcements visible across all classes

**Student Experience**
- Announcements display prominently on student dashboard
- Dismiss capability for individual announcements
- Clean, non-intrusive design that doesn't overwhelm the interface

**Access**
- Teacher navigation sidebar includes new "Announcements" link under Classroom section
- Dedicated management page at `/admin/announcements`

### UI/UX Improvements

#### Personalized Greetings

**Teacher Dashboard**
- Centered "Hi, [Display Name]" greeting with info icon tooltip linking to settings
- Clean, professional appearance

**Student Dashboard**
- Dynamic time-based greeting with student's first name
- Morning (5am-12pm): "Good morning"
- Afternoon (12pm-5pm): Randomizes between friendly greetings:
  - "Howdy"
  - "Good day to you"
  - "Good to see you again"
  - "Great timing"
  - "Let us get started"
- Evening (5pm-5am): "Good evening"

#### Enhanced Student Dashboard

**Account Balance Cards**
- Removed redundant left navigation sidebar for cleaner layout
- Side-by-side account balance cards for Checking and Savings accounts
- Light gray card backgrounds for better visibility
- Savings account displays projected monthly interest when balance > $0
- Encouragement message when savings balance is $0 to promote saving habits
- Fully responsive design (side-by-side on desktop, stacked on mobile)

#### Accordion-Style Admin Navigation

**Reorganized Sidebar Navigation**
- Collapsible accordion categories for better organization
- Categories: Classroom, Economy, Bills, Settings
- Bootstrap accordion ensures only one section open at a time
- Smooth transitions and modern styling

**Consolidated Settings**
- Unified Settings section includes:
  - Personalization
  - Passkey
  - Features
  - Help & Support
- Removed non-functional "Mobile Site" link from navigation

**Improved Sign Out Button**
- Enhanced contrast with red filled button and white text
- Better visibility and accessibility

#### Streamlined Authentication Flow

**Improved Login Experience**
- Login forms now present two authentication method buttons upfront
- "Use my authenticator" button reveals TOTP field with Back button
- "Use my passkey" button triggers WebAuthn flow
- Automatic fallback to TOTP on passkey failure
- Applied to both admin and system admin login pages
- Cleaner, more intuitive authentication experience
- Proper error handling and user feedback

---

## 🔒 Security Enhancements

### CodeQL Security Alerts Remediation

Comprehensively addressed 62 security alerts identified by CodeQL scanning (#737):

**Clear-text Logging of Sensitive Information**
- Removed TOTP secret printing from `create_admin.py`
- Removed TOTP secret printing from `wsgi.py` CLI command
- Removed TOTP secrets from seed script output
- TOTP secrets now encrypted in database with secure access only
- Prevents TOTP secrets from appearing in logs, console output, or command history

**DOM XSS Vulnerabilities**
- Fixed unsafe `innerHTML` usage in `templates/student_transfer.html`
- Fixed unsafe `innerHTML` usage in `static/js/attendance.js`
- Replaced with safe DOM manipulation using `createElement` and `textContent`
- Prevents XSS attacks via user-controlled data

**GitHub Actions Workflow Permissions**
- Added explicit permissions to `toggle-maintenance.yml`
- Added explicit permissions to `check-migrations.yml`
- Added explicit permissions to `deploy.yml`
- Follows principle of least privilege for workflow security
- Reduces workflow attack surface

**Summary**
- Fixed: 23+ real security issues
- Suppressed: 2 false positives in test files
- Reviewed: 37 false positives (already mitigated)
- All 62 alerts addressed appropriately

**Documentation**
- Added `SECURITY_FIXES_SUMMARY.md` with complete analysis of all alerts
- Documents remaining alerts as false positives with justification

### Enhanced Open Redirect Protection

Fixed critical URL redirection vulnerabilities in student class enrollment flow:

**What Was Fixed**
- Upgraded `_is_safe_url()` function to use same-origin validation
- Now uses `urljoin()` to resolve relative URLs against application's base URL
- Validates that redirect targets match the application's scheme and domain
- Prevents protocol-relative URLs and external redirects
- Added explicit security annotations (`# nosec`) with justification at all redirect points

**Impact**
- Addresses all 9 CodeQL security scanner findings for URL redirection vulnerabilities
- Affects student add-class flow redirect handling (`app/routes/student.py:710-877`)
- Prevents attackers from using the application as an open redirector

### Grafana Access Fix

Resolved "connection refused" error when accessing Grafana from system admin dashboard:

**Root Cause**
- Nginx `proxy_pass` had trailing slash that stripped URL path, causing infinite redirects

**Dual-Layer Solution**

**Flask Proxy (Fallback)**
- Added `/sysadmin/grafana` route that proxies to Grafana service
- Works immediately without Nginx configuration changes
- Maintains system admin authentication via `@system_admin_required`
- Configurable via `GRAFANA_URL` environment variable (defaults to `http://localhost:3000`)
- Rate-limit exempt for smooth dashboard operation
- Graceful error handling with user-friendly messages
- Initially added `requests==2.32.3` dependency, which was later updated (see Dependency Updates section).

**Nginx Fix (Production)**
- Corrected configuration provided in `nginx-grafana-fix.conf`
- Remove trailing slash from `proxy_pass http://127.0.0.1:3000/` → `proxy_pass http://127.0.0.1:3000`
- Nginx intercepts requests before Flask (faster performance)
- Auto-fallback to Flask proxy if Nginx not configured

**Documentation**
- See `GRAFANA_FIX_GUIDE.md` for detailed implementation guide

---

## 🐛 Bug Fixes

### Teacher Invite Code Validation

Fixed critical bugs preventing teacher signup with invite codes (#738):

**Whitespace Handling**
- Strip whitespace from invite codes during creation and validation
- Prevents copy-paste errors where whitespace causes "invalid invite code" errors
- Ensures consistency between code creation (system admin/CLI) and validation (signup)
- Added cleanup script (`cleanup_invite_codes.py`) for existing codes with whitespace

**Timezone Comparison Error**
- Fixed TypeError when comparing invite code expiration dates
- Database stores datetimes as timezone-naive (UTC)
- Comparison was using timezone-aware datetime.now(timezone.utc)
- Added conversion to make database datetime timezone-aware before comparison
- Fixes: TypeError: can't compare offset-naive and offset-aware datetimes

**TOTP Form Validation**
- Properly handle TOTP confirmation form submission separate from initial signup form
- Use AdminTOTPConfirmForm for TOTP submissions instead of AdminSignupForm
- Populate form data fields before rendering for proper WTForms validation
- Pass date string (YYYY-MM-DD) instead of integer for dob_sum field in TOTP confirmation
- Fixes: "dob_sum field is required" error when submitting TOTP code

**Debug Logging**
- Added comprehensive logging for invite code creation and validation
- Log TOTP code receipt, length, and verification result
- Log form validation errors and submission details
- Helps diagnose signup issues quickly

### TOTP Setup UI

Updated TOTP setup page to match new brand theme:

**Theme Consistency**
- Replaced hardcoded colors with CSS variables (--primary, --secondary, etc.)
- Updated gradient to use var(--primary) and var(--primary-hover)
- Changed logo from teacher-logo-192.png to logo_teacher_transparent_512.png
- Updated QR panel and manual code styling to use theme variables
- Added pattern background to branding side to match signup page
- Updated button hover states to match new brand guidelines

### Onboarding Templates

- Updated color scheme and text for better consistency with new brand theme
- Improved visual consistency across all onboarding flows

### Admin Dashboard
- Fixed duplicate greeting that was appearing in both page header and content section
- Now shows single, centered greeting for cleaner appearance

### Student Dashboard
- Improved account balance cards with clearer styling
- Using light backgrounds instead of semi-transparent overlays for better readability
- Enhanced mobile responsiveness with proper Bootstrap column classes (col-12 col-md-6)

---

## 📝 Technical Details

### Dependency Updates
- `requests==2.32.4` - For Grafana proxy functionality (updated from 2.32.3)
- `click==8.3.1` - Updated from 8.1.8 for improved CLI functionality
- `beautifulsoup4==4.14.3` - Updated from 4.13.4 for HTML parsing improvements

### Database Changes
None - This is a feature and UI-focused release with no schema changes

### Configuration Changes

**New Environment Variables**
- `GRAFANA_URL` (optional) - URL for Grafana service (defaults to `http://localhost:3000`)

### Files Changed

**Major File Updates**
- `app/routes/admin.py` - Announcement system routes, invite code validation fixes, TOTP form handling
- `app/routes/system_admin.py` - Grafana proxy, global announcements, invite code whitespace handling
- `app/routes/student.py` - Enhanced redirect protection
- `app/templates/admin_layout.html` - Accordion navigation
- `app/templates/student_dashboard.html` - Enhanced dashboard with greetings and balance cards
- `app/templates/admin_dashboard.html` - Personalized greeting
- `app/templates/admin_login.html` - Streamlined authentication flow
- `app/templates/system_admin_login.html` - Streamlined authentication flow
- `app/templates/admin_signup_totp.html` - TOTP setup UI with new brand theme
- `app/templates/admin_onboarding.html` - Updated color scheme and text
- `cleanup_invite_codes.py` - New script for cleaning up whitespace in existing invite codes
- `manage_invites.py` - Updated to strip whitespace from invite codes
- `static/css/style.css` - Minor style updates for onboarding

### Security Improvements
- CodeQL security alerts remediation (62 alerts addressed)
- Clear-text logging of sensitive information eliminated
- DOM XSS vulnerabilities fixed
- GitHub Actions workflow permissions hardened
- URL validation strengthened in student enrollment flow
- Same-origin policy enforcement for redirects
- All CodeQL security scanner findings addressed

---

## 🔄 Upgrade Notes

### For Administrators

1. **Announcement System**
   - New navigation link appears under "Classroom" section in admin sidebar
   - No database migration required - uses existing models
   - Start creating announcements immediately after upgrade

2. **Grafana Access**
   - Flask proxy works immediately without configuration
   - For optimal performance, update Nginx configuration (see `nginx-grafana-fix.conf`)
   - Set `GRAFANA_URL` environment variable if Grafana is not on localhost:3000

3. **Teacher Signup Fixes**
   - Teacher signup with invite codes now works reliably
   - If you have existing invite codes with whitespace issues, run `python cleanup_invite_codes.py`
   - TOTP setup page now matches new brand theme

4. **UI Changes**
   - Navigation reorganized into accordion sections
   - All existing functionality remains accessible, just better organized
   - Students will see new dashboard layout on next login

### For Developers

1. **Security Scanner**
   - All CodeQL security alerts now resolved (62 total, including 9 URL redirection findings)
   - Review `_is_safe_url()` implementation in `app/routes/student.py`
   - See `SECURITY_FIXES_SUMMARY.md` for detailed analysis

2. **Dependencies**
   - Run `pip install -r requirements.txt` to update dependencies:
     - `requests==2.32.4`
     - `click==8.3.1`
     - `beautifulsoup4==4.14.3`

### For Students

1. **Dashboard Updates**
   - New personalized greeting based on time of day
   - Improved account balance display with side-by-side cards
   - Announcements from teachers now visible on dashboard

---

## 📖 Documentation Updates

### New Documentation
- `GRAFANA_FIX_GUIDE.md` - Grafana access troubleshooting and configuration

### Updated Documentation
- `CHANGELOG.md` - Updated with all v1.4.0 changes
- `CLAUDE.md` - Updated version to 1.4.0
- `README.md` - Updated project status for v1.4.0
- `DEVELOPMENT.md` - Updated current version

---

## 🎓 User-Facing Changes

### For Teachers

**New Capabilities**
- Create and manage class announcements
- View announcement engagement (when students dismiss)
- Global announcements (system admins only)

**UI Improvements**
- Personalized greeting on dashboard
- Better organized navigation with accordion sections
- Streamlined login process
- Improved sign out button visibility

### For Students

**New Features**
- See announcements from teachers on dashboard
- Dismiss announcements individually

**UI Improvements**
- Time-based personalized greeting
- Enhanced account balance display with projected interest
- Encouragement to save when savings balance is zero
- Cleaner dashboard layout
- Better mobile responsiveness

---

## 🚦 Testing Recommendations

After upgrading to v1.4.0, test the following:

1. **Announcement System**
   - Create a test announcement
   - Verify it appears on student dashboard
   - Test dismissing announcements
   - Toggle announcement active/inactive status

2. **Grafana Access**
   - Access Grafana from system admin dashboard
   - Verify no "connection refused" errors

3. **UI Navigation**
   - Verify accordion navigation works correctly
   - Test collapsing/expanding sections
   - Verify all navigation links are accessible

4. **Authentication Flow**
   - Test TOTP login with new streamlined flow
   - Test passkey authentication if enabled
   - Verify fallback behavior

5. **Student Dashboard**
   - Verify personalized greeting appears
   - Check account balance cards display correctly
   - Test on mobile devices for responsiveness

---

## 🔗 Related Links

- [Full Changelog](../../CHANGELOG.md#140---2025-12-27)
- [Version 1.3.0 Release Notes](RELEASE_NOTES_v1.3.0.md)
- [Project README](../../README.md)
- [Development Priorities](../../DEVELOPMENT.md)

---

## 📞 Support

If you encounter any issues with this release:

1. Check the [CHANGELOG](../../CHANGELOG.md) for known issues
2. Review the [Documentation](../../docs/README.md)
3. Report bugs via GitHub Issues

---

**Released by**: Classroom Token Hub Team
**Release Type**: Minor Version (Feature Release)
**Compatibility**: Compatible with v1.3.x databases (no migration required)
