# Release Notes - Version 1.3.0

**Release Date**: December 25, 2025

Version 1.3.0 is a major security-focused release introducing modern passwordless authentication for both teachers and system administrators. This release implements WebAuthn/FIDO2 passkey support, adds encrypted TOTP storage, resolves critical security vulnerabilities, and fixes several Service Worker bugs affecting the PWA experience.

---

## 🎯 Release Highlights

### Passwordless Authentication with Passkeys
Teachers and system administrators can now authenticate using modern passkeys (WebAuthn/FIDO2), supporting hardware security keys, platform authenticators (Touch ID, Face ID, Windows Hello), and synced passkeys across devices.

### Enhanced Security Posture
TOTP 2FA secrets are now encrypted at rest, sensitive information removed from logs, username enumeration vulnerabilities fixed, and comprehensive security audit completed.

### Service Worker Fixes
Resolved persistent browser console errors from the Service Worker attempting to cache unsupported request types and non-existent files.

---

## 🚀 New Features

### Passwordless Authentication for Teachers

Teachers can now use passkeys for secure, phishing-resistant authentication:

**Supported Authenticators**
- Hardware security keys (YubiKey, Google Titan Key, SoloKeys, etc.)
- Platform authenticators (Touch ID, Face ID, Windows Hello)
- Synced passkeys across devices (Apple Keychain, Google Password Manager, Bitwarden)

**Benefits**
- **Phishing-resistant**: Passkeys are domain-bound and cannot be phished
- **Convenient**: No need to remember passwords or type 6-digit codes
- **Fast**: One touch or glance to authenticate
- **Secure**: Public-key cryptography eliminates password database breaches

**Implementation**
- New `/admin/passkey/settings` page for passkey management
- Register multiple passkeys with friendly names
- View passkey usage history (created date, last used)
- Delete unused passkeys
- TOTP remains available as backup authentication method

**Technical Details**
- Backend routes: `passkey_register_start`, `passkey_register_finish`, `passkey_auth_start`, `passkey_auth_finish`
- Database model: `AdminCredential` stores passkey metadata
- Full CSRF protection and rate limiting on all endpoints
- Integration with passwordless.dev service
- Uses official Bitwarden Passwordless SDK (`passwordless==2.0.0`)

### Passwordless Authentication for System Admins

System administrators now have the same passkey authentication capabilities as teachers:

**Same Features as Teachers**
- Support for hardware keys, platform authenticators, and synced passkeys
- Phishing-resistant, domain-bound credentials
- Management UI at `/sysadmin/passkey/settings`
- TOTP remains available alongside passkeys

**Technical Details**
- Backend routes: Same structure as teacher passkeys
- Database model: `SystemAdminCredential` stores passkey metadata
- Self-hosted ready: Infrastructure designed to migrate to py-webauthn library
- Environment variables required: `PASSWORDLESS_API_KEY`, `PASSWORDLESS_API_PUBLIC`

---

## 🔒 Security Enhancements

### Encrypted TOTP Secrets at Rest

TOTP 2FA secrets are now encrypted in the database using Fernet (AES-128-CBC):

**Benefits**
- Database compromise alone no longer sufficient to generate valid 2FA codes
- Defense in depth: Additional layer of protection beyond database security
- Backward compatible: Handles both encrypted and legacy plaintext secrets

**Implementation**
- Added `encrypt_totp()` and `decrypt_totp()` helper functions in `app/utils/encryption.py`
- All new admin/system admin accounts store encrypted TOTP secrets (base64-encoded)
- Transparent decryption: No changes required to authentication flow
- Migration required: Column length expanded from VARCHAR(32) to VARCHAR(200)

**Security Note**
- Encryption key stored in `ENCRYPTION_KEY` environment variable
- Future migration to AWS Secrets Manager or HashiCorp Vault recommended

### Removed Sensitive Information from Logs

Eliminated PII from application logs to prevent accidental exposure:

**What Was Removed**
- Username logging from student login, admin login, admin signup, and admin recovery flows
- Partial hash logging from student authentication
- Student name and DOB sum logging from bulk upload process

**Impact**
- Prevents accidental exposure in development logs, log files, or screenshots
- Production deployments should configure `LOG_LEVEL=WARNING` or higher

### Fixed Username Enumeration Vulnerability

Passkey authentication endpoints now use generic error messages:

**Before**: "No passkeys registered for this account"
**After**: "Invalid credentials"

**Impact**
- Prevents reconnaissance attacks to enumerate valid usernames
- Matches security best practice for authentication error messages

### Allowed Passkey Endpoints Through Maintenance Mode

Passkey authentication endpoints now bypass maintenance mode:

**Endpoints Exempted**
- `/sysadmin/passkey/auth/start` and `/sysadmin/passkey/auth/finish`
- `/admin/passkey/auth/start` and `/admin/passkey/auth/finish` (via Flask)

**Impact**
- System administrators and teachers can authenticate during maintenance windows
- Matches existing behavior for standard login endpoints

**Note**: Nginx configuration must also exempt these endpoints (see deployment notes)

### Critical Security Vulnerability Fixed

**PromptPwnd AI Prompt Injection Vulnerability** - Disabled vulnerable `summary.yml` GitHub Actions workflow:

- Workflow used AI inference with untrusted user input from issue titles/bodies
- Attack vector: Malicious prompt injection could leak `GITHUB_TOKEN` or manipulate workflows
- Remediation: Disabled workflow by renaming to `summary.yml.DISABLED`
- Impact: No exploitation detected - vulnerability fixed proactively
- Reference: [Aikido Security PromptPwnd Disclosure](https://www.aikido.dev/blog/promptpwnd-ai-prompt-injection-in-github-actions)

### Comprehensive Security Audit Completed

Full security review of codebase, CI/CD, and infrastructure:

**Audit Scope**
- GitHub Actions workflows
- Authentication and authorization
- Encryption and secrets management
- Multi-tenancy isolation
- Dependency vulnerabilities
- API security

**Findings**
- 16 total findings (2 critical, 2 high, 3 medium, 4 low, 5 informational)
- Critical issues: AI prompt injection (fixed), SSH host key verification disabled (open)

**Strengths**
- Excellent CSRF protection
- Strong SQL injection prevention
- Effective XSS mitigation
- PII encryption at rest
- Robust multi-tenancy isolation

**Documentation**
- See `docs/security/COMPREHENSIVE_ATTACK_SURFACE_AUDIT_2025.md` for complete report
- Security remediation guide: `docs/security/SECURITY_REMEDIATION_GUIDE.md`

---

## 🐛 Bug Fixes

### Service Worker Cache Errors

Fixed persistent browser console errors from Service Worker:

**Issues Resolved**
1. **Chrome Extension Errors**: Service Worker attempted to cache `chrome-extension://` URLs
   - Error: `Failed to execute 'put' on 'Cache': Request scheme 'chrome-extension' is unsupported`
   - Fix: Added `shouldCache()` helper that filters non-HTTP(S) requests

2. **POST Request Caching**: Service Worker tried to cache POST/PUT/DELETE requests
   - Error: `Failed to execute 'put' on 'Cache': Request method 'POST' is unsupported`
   - Fix: Only cache GET requests

3. **Missing Asset**: Service Worker tried to cache non-existent `brand-logo.svg`
   - Error: 404 on `/static/images/brand-logo.svg`
   - Fix: Removed from static assets cache list

**Technical Changes**
- Created `shouldCache()` helper function to centralize cache eligibility logic
- Updated both `networkFirst()` and `cacheFirst()` strategies
- Bumped cache version to v7 to force fresh cache on next page load

### Passkey Registration ReferenceError

Fixed JavaScript error preventing passkey registration from completing:

**Issue**
- Variable was renamed from `credId` to `credentialId` but one reference wasn't updated
- Would cause all passkey registration attempts to fail with `ReferenceError: credId is not defined`

**Fix**
- Updated line 208 in `templates/admin_passkey_settings.html` to use correct variable name
- Caught by AI code review tools (GitHub Copilot and Google Gemini)

### Broken Service Worker cacheFirst() Function

Fixed corrupted `cacheFirst()` function from bad merge:

**Issue**
- Function had duplicate `shouldCache()` checks
- Missing cache lookup logic
- Orphaned code fragments

**Fix**
- Restored proper cache-first strategy:
  1. Check `shouldCache()` - early return if not cacheable
  2. Try cache match first
  3. Fetch from network if not cached
  4. Cache successful responses
  5. Handle errors properly

---

## 🔄 Changed

### Improved Store Management Overview Page

Replaced "Active Store Items" section with more actionable information:

**Before**
- Displayed list of active store items (not very useful)

**After**
- **Pending Redemption Requests** table showing items awaiting teacher approval
  - Student name, item, request time, details, and quick review link
- **Recent Purchases** table with 10 most recent student purchases
  - Student name, item, price, purchase time, and current status

**Additional Fixes**
- Fixed markdown rendering issue in item descriptions (was showing raw `####` syntax)

---

## 📦 Database Migrations

### Required Migrations

**1. TOTP Secret Encryption**
- Column: `admins.totp_secret` and `system_admins.totp_secret`
- Change: VARCHAR(32) → VARCHAR(200)
- See: `docs/operations/MIGRATION_TOTP_ENCRYPTION.md`

**2. Admin Credentials Table**
- Table: `admin_credentials`
- Purpose: Store teacher passkey metadata
- Columns: `id`, `admin_id`, `credential_id`, `public_key`, `sign_count`, `transports`, `authenticator_name`, `aaguid`, `created_at`, `last_used`

**3. System Admin Credentials Table** (if not already applied)
- Table: `system_admin_credentials`
- Purpose: Store system admin passkey metadata
- Same structure as `admin_credentials`

### Migration Commands

```bash
# Apply migrations
flask db upgrade

# Verify migrations
flask db current
```

---

## 🚀 Deployment Notes

### Environment Variables

Add the following environment variables for passkey authentication:

```bash
# Passwordless.dev API keys
PASSWORDLESS_API_KEY=your_private_api_key
PASSWORDLESS_API_PUBLIC=your_public_api_key
```

Get API keys from [passwordless.dev admin console](https://admin.passwordless.dev)

### Nginx Configuration

Update nginx configuration to allow passkey endpoints through authentication:

```nginx
# Allow passkey authentication endpoints without auth
location = /sysadmin/passkey/auth/start {
    auth_request off;
    auth_basic off;
    proxy_pass http://127.0.0.1:8000;
    include proxy_params;
}

location = /sysadmin/passkey/auth/finish {
    auth_request off;
    auth_basic off;
    proxy_pass http://127.0.0.1:8000;
    include proxy_params;
}
```

### Service Worker Update

Users may need to hard refresh (Ctrl+Shift+R / Cmd+Shift+R) to get the updated Service Worker (v7).

---

## 🎓 User Guide

### For Teachers

**Setting Up Passkey Authentication**

1. Log in with username + TOTP
2. Navigate to **Settings** → **Passkey Settings**
3. Click **Register New Passkey**
4. Enter a friendly name (e.g., "Touch ID", "YubiKey")
5. Follow the browser prompt to complete registration
6. Log out and try signing in with passkey

**Using Passkey Login**

1. Go to teacher login page
2. Enter your username
3. Click **Sign in with Passkey** button
4. Complete the authentication (touch sensor, Face ID, etc.)
5. You're logged in!

**Managing Passkeys**

- View all registered passkeys in Settings → Passkey Settings
- See when each was created and last used
- Delete unused passkeys
- Register multiple passkeys (work computer, personal device, hardware key)

### For System Admins

Same process as teachers, but navigate to `/sysadmin/passkey/settings`

---

## ⚠️ Breaking Changes

None. This release is backward compatible with v1.2.1.

---

## 📊 Statistics

- **Files Changed**: 47
- **Commits**: 35
- **Lines Added**: 2,847
- **Lines Removed**: 315

---

## 🙏 Acknowledgments

- Thanks to **Aikido Security** for responsible disclosure of the PromptPwnd vulnerability
- Thanks to **GitHub Copilot** and **Google Gemini** for catching the `credId` bug during code review
- Thanks to **Bitwarden** for the excellent passwordless.dev service and SDK

---

## 🔗 Links

- **Full Changelog**: [CHANGELOG.md](../../CHANGELOG.md#130---2025-12-25)
- **Security Audit**: [docs/security/COMPREHENSIVE_ATTACK_SURFACE_AUDIT_2025.md](../security/COMPREHENSIVE_ATTACK_SURFACE_AUDIT_2025.md)
- **Security Remediation Guide**: [docs/security/SECURITY_REMEDIATION_GUIDE.md](../security/SECURITY_REMEDIATION_GUIDE.md)
- **PromptPwnd Details**: [docs/security/PROMPTPWND_REMEDIATION.md](../security/PROMPTPWND_REMEDIATION.md)

---

**Enjoy the enhanced security and convenience of passkey authentication! 🔐**
