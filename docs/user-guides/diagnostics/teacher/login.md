---
title: Login and Account Security Troubleshooting
description: Resolving teacher sign-in, two-factor, and registration problems.
category: diagnostics
subcategory: teacher
roles: [teacher]
related:
  - user-guides/diagnostics/teacher/onboarding
---

# Login and Account Security Troubleshooting

Diagnostic guide for resolving teacher login access, 2FA, and registration issues.

## Cannot log in

### Symptoms
- Login fails with an "Invalid credentials" error.
- TOTP codes are rejected.
- You are locked out of the system.

### Causes & Solutions
**Cause 1: Incorrect credentials**
- **Check:** Ensure you are using the correct username and current authenticator code, or the correct registered passkey.
- **Fix:** Double-check spelling, try a fresh authenticator code, or use a registered passkey if one is available.

**Cause 2: Unsynchronized TOTP clock**
- **Check:** Compare the time on your authenticator device with the actual time.
- **Fix:** Time drift breaks TOTP. Sync the clock in your authenticator app settings (e.g., Google Authenticator -> Settings -> Time correction for codes).

**Cause 3: Rate limiting active**
- **Check:** Did you fail login multiple times in a row?
- **Fix:** Too many attempts trigger a short rate limit. Wait 5-10 minutes before trying again.

## Cannot sign up

### Symptoms
- The registration form rejects your submission.
- The invite code is invalid.

### Causes & Solutions
**Cause 1: Invalid invite code**
- **Check:** Verify the code provided by your Sysadmin.
- **Fix:** An active, unused invite code is required for first-time admin registration. Request a new code if yours has expired.

**Cause 2: Authenticator setup not completed**
- **Check:** Confirm you scanned the current QR code and entered a fresh code from the same authenticator app.
- **Fix:** Restart setup with a valid invite code if the QR code or setup session expired.

## When to Contact Support
Report this issue if:
- You lose access to your authenticator app and have not registered a passkey. Use the student-assisted teacher recovery flow when available.
- The passkey prompt repeatedly fails on an authorized device.
