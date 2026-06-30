# DOM-IDEN-003: Teacher Identity Architecture

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-003 | 2.0 | 2026-06-29 | 1.2 | Constitutional |

---

## I. Purpose

This document defines how the canonical identity objects defined by DOM-IDEN-001 are specialized for teacher participation within Classroom Token Hub. It governs teacher-specific credential structure, authentication, step-up authentication, and account recovery.

This document is subordinate to **DOM-IDEN-001** (Canonical Identity Model) and **DOM-IDEN-005** (Identity Binding and Lifecycle). Those documents define the universal identity objects and lifecycle laws. This document specializes those definitions for the teacher role.

> [!IMPORTANT]
>
> This document defines the canonical v2 identity model. It does not preserve v1 data model constraints. Legacy tables (`admins`/`teachers`, `teacher_blocks`, `student_teachers`, `class_memberships`) are migration artifacts and SHALL NOT be treated as identity authority.

---

## II. Scope

This document governs:

- Teacher credential structure on `users`
- Teacher seat structure
- Teacher authentication flow (TOTP and passkey)
- Teacher session semantics
- Teacher account recovery (self-serve, student-assisted)
- Passkey credential metadata
- Teacher class provisioning identity

This document does **not** govern:

- The canonical identity objects themselves (DOM-IDEN-001)
- Identity binding and lifecycle rules (DOM-IDEN-005)
- Canonical context resolution (DOM-IDEN-006)
- Economic activity (Ledger domain)
- Student identity (DOM-IDEN-002)
- Class policy configuration
- Store ownership

---

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000`, `INV-CORE-001`, `INV-ARC-008`, `DOM-IDEN-001`, and `DOM-IDEN-005`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`
- `DOM-IDEN-001_CANONICAL_IDENTITY_MODEL.md`
- `DOM-IDEN-005_IDENTITY_BINDING_AND_LIFECYCLE.md`

---

## V. Schema Authority Declaration

### Owned Tables

This document is the sole schema and mutation authority over the following tables:

**`recovery_requests`**

Key fields: `id`, `user_id` (FK to `users` where `user_role = 'teacher'`), `status` (`pending` | `verified` | `expired`), `expires_at`, `created_at`, `completed_at`, `partial_codes` (JSON), `resume_pin_hash`, `resume_new_username`.

**`student_recovery_codes`**

Key fields: `id`, `recovery_request_id` (FK, CASCADE), `seat_id` (FK to `seats` where `role = 'student'`), `code_hash` (NULL until student generates their code), `verified_at`, `notified_at`, `dismissed`.

**`teacher_credentials`**

Teacher passkey credential metadata. Owned by `users.id` (per INV-ARC-019 §XI). Sysadmin credential metadata (`system_admin_credentials`) is not governed by this document.

### Schema Contract

Teacher-specific fields on `users`: `totp_secret_encrypted`.

### Constraints

- `recovery_requests`: At most one `status = 'pending'` row per user at any time. `expires_at` is a hard TTL (5 days). Rows past `expires_at` are inert regardless of status. `partial_codes` and `resume_new_username` must be cleared when `status` transitions to `verified` or `expired`.
- `student_recovery_codes`: One row per selected student seat per recovery request. `code_hash` is `HMAC(6-digit-code, b'')`. Plaintext code is never stored. `code_hash` is set to NULL and `verified_at` is cleared on any failed submission (all-or-nothing invalidation per §IX invariant 6). Rows become inert when the parent `recovery_request.expires_at` passes.
- `teacher_credentials`: Passwordless external IDs use `user_<User.id>`. Legacy external IDs such as `admin_<id>` are invalid v2 principals. Legacy `teacher_id` columns are compatibility-only metadata. Passkey metadata does not authorize class access, seat access, recovery, or economic actions.

### Derived / Cross-Domain Rules

The `user_recovery_tokens` table is a shared recovery capability table owned by `users` (per INV-ARC-019 §XI). This document governs the teacher-specific recovery workflow that produces and consumes those tokens.

---

## VI. Teacher Identity Layers

Teacher identity follows the universal three-layer model defined by DOM-IDEN-001:

- **`User`**: authentication principal — owns credentials, recovery, and global security state
- **`Seat`**: class-local actor — the canonical operator record inside a class
- **`Class`**: economic universe boundary

Economic and operational authority is never inferred from `user_id` alone. Scoped actions require a resolved teacher `seat_id` bound to the active `class_id`.

### Teacher `User` Fields

A teacher `User` is a `users` row with `user_role = 'teacher'`. Common `users` fields are defined by DOM-IDEN-001. This section defines only the teacher-specific delta.

Teacher-specific fields:

- `totp_secret_encrypted` — base64-encoded encrypted TOTP seed

> [!IMPORTANT]
>
> Teacher users may optionally enable passkey for authentication. Passkey-related metadata is stored on a unified `passkey_metadata` table with the following fields: `id`, `user_id` (FK to `users.id`), `credential_id`, `authenticator_name`, `created_at`, `last_used`. Actual field requirements should consult Bitwarden Passwordless SDK requirements.

Student-specific fields (`pin_hash`, `passphrase_hash`, `money_action_cooldown_until`) SHALL be `NULL` for teacher rows.

Teacher-specific rules:

- Teacher maximum session length is 60 minutes.
- A missing or invalid `last_active_class_id` must not be treated as authority failure by itself; the login boundary may surface explicit class selection when valid seats exist, and only fail closed after verifying that no valid class/seat options remain.

### Teacher `Seat` Fields

A teacher seat is a `seats` row with `role = 'teacher'`. Base seat fields and participation rules are defined by DOM-IDEN-001. This section defines only the teacher-specific delta.

Teacher-specific rules:

- A teacher seat is provisioned when the teacher sets up a class.
- Teacher seats do not use `roster_fingerprint` or `dedupe_code`; those fields are `NULL` for teacher seats.
- `teacher_notes_encrypted` is accessible only to the seat's teacher and system admins.
- A class has exactly one authoritative teacher seat owner for teacher-scoped mutation surfaces.
- Teacher-scoped writes must be attributable to a teacher `seat_id`.

### Teacher `IdentityProfile`

Defined by DOM-IDEN-001. No teacher-specific delta. Teacher display names are stored here, not on a separate teacher table.

---

## VII. Teacher Authentication

### Login Flow

```text
1. Teacher submits username.
2. Backend computes username_lookup_hash and finds the users row.
3. Backend verifies user_role == 'teacher'.
4. If passkey is enrolled and the client supports it → passkey challenge (preferred).
5. Otherwise → TOTP challenge using totp_secret_encrypted.
6. On success: write current_session_started_at, current_session_expires_at,
   current_session_nonce.
```

TOTP is required for all teacher accounts. Passkey is an optional second authentication method — when enrolled, it replaces the TOTP step for that device.

Active seat and class context restoration follows DOM-IDEN-006. Sysadmin authentication may share the same login surface but is not governed by this document.

### Account Provisioning

Teacher account provisioning follows DOM-IDEN-005 §VI. The constitutional provisioning sequence is:

1. Provision a canonical `User` (with `user_role = 'teacher'`).
2. Provision an initial `Class`.
3. Provision one administrative `Seat`.
4. Bind the administrative `Seat` to the newly provisioned `User`.
5. Initialize the active class and seat pointers (per DOM-IDEN-006 §XIII).
6. Permit runtime participation through DOM-IDEN-006.

Teacher-specific credential setup (TOTP enrollment, optional passkey enrollment) occurs within this sequence. TOTP setup is required before `has_completed_setup = true`.

Per DOM-IDEN-005 §VI, the initial Class and administrative Seat MUST be provisioned atomically with the User. Failure to provision the initial Class SHALL invalidate the entire teacher provisioning transaction.

### Session Establishment

- `current_session_started_at` is written at sign-in.
- `current_session_expires_at` is written once at sign-in (fixed 60-minute window, does not slide forward on activity).
- `current_session_nonce` is regenerated at sign-in and binds requests to one specific login session.
- All three session fields are replaced on the next successful sign-in.

Request-time session validation is governed by DOM-IDEN-006.

### Financial Action Gate

Teachers administering financial actions (adjustments, payroll, approvals) are authenticated by the existing session. There is no additional passphrase gate for teachers — the TOTP at login is the authentication signal.

### Step-Up Authentication

Certain privileged identity mutations SHALL require step-up authentication beyond the existing session. Step-up authentication is a fresh re-authentication challenge issued at the time of the privileged action, not a replay or reuse of the login-time credential.

The following actions SHALL require step-up authentication:

- Final classroom deletion (destruction of the teacher's last class, which triggers identity destruction per DOM-IDEN-005 §VI)
- Disabling or replacing the enrolled TOTP secret
- Registering or removing passkey credentials
- Initiating student account recovery (issuing a reset code for another actor)

Step-up authentication is a constitutional requirement. The specific mechanism, validity window, and binding rules are defined by the governing FEAT contract.

---

## VIII. Authority Rules

1. **Authentication authority:** `user_id` proves who is logged in.
2. **Scoped authority:** `seat_id` proves class-local actor authority. `class_id` proves universe boundary.
3. **Request contract:** Global teacher routes may use authenticated `user_id` only. Any class-scoped teacher operation must resolve and validate `seat_id + class_id` ownership.
4. **Membership by existence:** If a teacher seat exists for (`user_id`, `class_id`), membership exists. No implied membership from other tables or duplicated denormalized markers.

Domains SHALL NOT accept teacher authority from `join_code` or `user_id` without seat-ownership validation.

---

## IX. Teacher Account Recovery

Teacher recovery is **self-serve and student-assisted**. The teacher proves identity through their roster. No sysadmin involvement is required. No DOB or personal contact information is used.

### Core Invariants

1. **No DOB.** No date of birth, DOB sum, or any birth-date-derived value is collected, stored, or used at any point in teacher recovery.
2. **Self-serve.** Teacher recovery does not require system admin intervention.
3. **Credential restoration only.** Recovery replaces credential access on the same identity record. Per DOM-IDEN-005 §IX, recovery SHALL NOT modify participation, ownership, or identity bindings. It does not create new records or alter class or economic state.
4. **All classes must be represented.** One student per active class period must participate. Partial coverage is rejected.
5. **Distributed trust.** A single compromised student account cannot enable teacher account takeover. All represented class periods must verify.
6. **All-or-nothing code validation.** On any failed submission of recovery codes, all codes are invalidated immediately and students must regenerate. This prevents incremental probing of individual codes.

### Recovery Flow

**Step 1 — Roster verification and request creation**

The teacher submits one (`join_code`, `student_username`) pair per active class period.

Pair resolution chain:

1. `join_code → class_id → teacher identifier` — resolve the first submitted join code to determine the target teacher. If unrecognized, reject the entire submission generically.
2. Collect all `join_codes` under that teacher — retrieve the definitive list from the backend.
3. Verify the submitted set matches the backend's definitive list exactly (no missing classes, no extras, no duplicates).
4. For each submitted pair, verify the `username_lookup_hash` exists strictly within the roster of that specific `join_code`.

Submission rules:

- One pair is required per active class.
- All pairs are validated in full before any are accepted. Partial success is never reported.
- Generic error on any failure. Do not reveal which pair failed, which join code was unrecognized, or whether any student username exists.
- If an active recovery request already exists for this teacher, the system SHALL present the existing request status rather than creating a duplicate.

On success: a `RecoveryRequest` is provisioned with `status = 'pending'` and `expires_at = now + 5 days`. One `StudentRecoveryCode` row is provisioned per selected student seat with `code_hash = NULL`.

**Step 2 — Student verification and code generation**

Each selected student SHALL be notified of the pending recovery request upon their next authenticated session. The student:

1. Sees the banner and confirms.
2. Enters their passphrase (financial-gate verification).
3. On successful passphrase verification, the system generates a 6-digit numeric recovery code and displays it.
4. The code hash (`HMAC(code, b'')`) is stored in `StudentRecoveryCode.code_hash`.
5. Student communicates the plaintext code to their teacher in person.

Rules:

- Each student generates exactly one code per recovery request.
- The 6-digit code is system-generated, not student-chosen.
- Once generated, the code is not redisplayed.
- Students cannot confirm outside an active `RecoveryRequest` with `status = 'pending'`.

**Step 3 — Code entry and submission**

Teacher enters all recovery codes collected from students.

Persistence across sessions: entered codes and the new username are saved to `RecoveryRequest.partial_codes` and `RecoveryRequest.resume_new_username` in the database. A 6-digit resume PIN is generated, hashed as `HMAC(pin, b'')`, and stored in `RecoveryRequest.resume_pin_hash`. The teacher uses this PIN to reload saved state on any future browser session within the 5-day window.

Submission rules:

- Before submission, no indication is shown as to which entered codes are valid or invalid.
- Backend verifies all students have generated codes (`code_hash IS NOT NULL` for all).
- Codes are validated as a set (order-independent): `set(HMAC(entered, b''))` must equal `set(stored code_hashes)`.
- **On any failure:** ALL `StudentRecoveryCode` rows are invalidated (`code_hash = NULL`, `verified_at = NULL`). Students must regenerate.
- The failure message does not indicate which code failed or why.
- Teacher may reattempt after students regenerate, within the 5-day window.

**Step 4 — Credential re-establishment**

If all codes match:

- Teacher enters new username and scans a newly generated TOTP QR code.
- TOTP code from the new device is verified before credentials are written.
- All previously enrolled user-owned passkeys are revoked.
- New `users.username_hash`, `users.username_lookup_hash`, and `users.totp_secret_encrypted` are written atomically.
- `RecoveryRequest.status` is set to `verified`.

**Step 5 — Completion**

On successful credential setup:

- `RecoveryRequest.status = 'verified'`, `completed_at` set.
- Session recovery keys cleared.
- Teacher must re-authenticate with new credentials.
- Audit log: teacher identity + timestamp only; no student PII logged.

### Session Expiry

The entire recovery session (Steps 1–5) expires 5 days after Step 1 completion. On expiry:

- `RecoveryRequest.status` is set to `expired`.
- All `StudentRecoveryCode` rows become inert.
- Entered partial codes and resume PIN are inaccessible.
- Teacher must restart from Step 1.

### Recovery Security Properties

| Property | Mechanism |
|----------|-----------|
| Distributed trust | One student per class; all must verify |
| All-or-nothing code validation | Any wrong code wipes all codes — no incremental probing |
| No pre-submission feedback | Entered codes show no valid/invalid state before submit |
| Generic failure messages | No indication of which code or student caused failure |
| Cross-session persistence | Partial codes persisted in DB via resume PIN, not session |
| Passphrase gate on students | Student must re-enter passphrase to generate their code |
| No contact PII | No email, phone used at any stage |
| No DOB | No date of birth used anywhere |

### Recovery Hard Boundaries

The teacher recovery system SHALL NOT:

- Accept partial class coverage (all active classes must be represented)
- Pre-validate individual codes before the teacher submits all of them
- Reveal which code, student, or class caused a validation failure
- Preserve any `StudentRecoveryCode.code_hash` after a failed submission
- Collect or verify DOB at any point
- Allow student-initiated confirmation outside an active `RecoveryRequest`
- Preserve enrolled passkeys across a recovery event
- Log student PII in recovery audit records

---

## X. Credential Summary

| Credential | Teacher |
|------------|---------|
| Username | `username_hash` / `username_lookup_hash` |
| Primary auth factor | TOTP (`totp_secret_encrypted`) |
| Secondary / optional factor | Passkey metadata owned by `users.id` |
| Passphrase | N/A |
| DOB | **Not stored** |
| Recovery | Student-assisted distributed trust |
| Session | Nonce + 60-minute fixed-window expiry |

For student credential structure, see DOM-IDEN-002.

---

## XI. Forbidden Patterns

- Separate `teachers` / `admins` table as identity authority (legacy migration artifact)
- DOB or DOB-derived hashes for any purpose
- Plaintext username column (only `username_hash` and `username_lookup_hash`)
- `teacher_public_id` as a separate field (display identity lives in `identity_profiles`)
- Passkeys owned by role-specific principal IDs (legacy `admin_<id>` format)
- Treating `join_code` as backend authority boundary
- Implicitly deriving active scope from unrelated session residue
- Writing class-scoped state when no teacher seat is resolved
- Using `teacher_id` alone to scope student data

---

## XII. Amendment

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-001 and DOM-IDEN-005.
4. Maintain consistency with INV-CORE-000.
