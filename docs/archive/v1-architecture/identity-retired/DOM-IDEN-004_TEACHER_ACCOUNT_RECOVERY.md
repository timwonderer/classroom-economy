# DOM-IDEN-004: Teacher Account Recovery

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-004     | 2.1     | 2026-06-05     | 2.0 | Normative |

## I. Purpose

This document defines the v2 account recovery architecture for teacher principals.

Teacher recovery is **self-serve and student-assisted**. The teacher proves identity
through their roster. No sysadmin involvement is required. No DOB or personal contact
information is used in the target model.

For student account recovery, see `DOM-IDEN-002_STUDENT_ACCOUNT_RECOVERY.md`.

Supersedes `docs/LOGS/AUDITS/LOG-ARC-011_Recovery_Evaluation.md` (informative).

## II. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-IDEN-001_IDENTITY_CLASS_BINDING_DOMAIN.md`
- `DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`

---

## II-A. Schema Authority Declaration

This document is the sole schema and mutation authority over:

- `recovery_requests`
- `student_recovery_codes`

These tables exist only to support teacher account recovery. No other domain may
define fields, impose lifecycle rules, or mutate these tables directly.

### `recovery_requests`

Key fields: `id`, `user_id` (FK to `users` where `user_role = 'teacher'`),
`status` (`pending` | `verified` | `expired`), `expires_at`, `created_at`,
`completed_at`, `partial_codes` (JSON), `resume_pin_hash`, `resume_new_username`.

Constraints:
- At most one `status = 'pending'` row per user at any time.
- `expires_at` is a hard TTL (5 days). Rows past `expires_at` are inert regardless
  of status.
- `partial_codes` and `resume_new_username` carry in-progress submission state.
  They must be cleared when `status` transitions to `verified` or `expired`.

### `student_recovery_codes`

Key fields: `id`, `recovery_request_id` (FK, CASCADE), `seat_id` (FK to `seats`
where `role = 'student'`), `code_hash` (NULL until student generates their code),
`verified_at`, `notified_at`, `dismissed`.

Constraints:
- One row per selected student seat per recovery request.
- `code_hash` is `HMAC(6-digit-code, b'')`. Plaintext code is never stored.
- `code_hash` is set to NULL and `verified_at` is cleared on any failed submission
  (all-or-nothing invalidation per §III invariant 6).
- These rows become inert when the parent `recovery_request.expires_at` passes.

---

---

## III. Core Invariants

1. **No DOB.** No date of birth, DOB sum, or any birth-date-derived
   value is collected, stored, or used at any point in teacher recovery.

2. **Self-serve.** Teacher recovery does not require system admin intervention.

3. **Identity rebinding only.** Recovery replaces credential access on the same
   identity record. It does not create new records or alter class or economic state.

4. **All classes must be represented.** One student per active class period must
   participate. Partial coverage is rejected.

5. **Distributed trust.** A single compromised student account cannot enable teacher
   account takeover. All represented class periods must verify.

6. **All-or-nothing code validation.** On any failed submission of recovery codes,
   all codes are invalidated immediately and students must regenerate. This prevents
   incremental probing of individual codes.

---

## IV. Scope

Applies to:
- Teacher credential recovery (self-serve, student-assisted)

Does not apply to:
- Student recovery — see `DOM-IDEN-002_STUDENT_ACCOUNT_RECOVERY.md`
- System admin recovery (separate tier)

---

## V. Data Model

Recovery state is tracked via two models:

### `RecoveryRequest`
- `user_id` — FK to teacher identity (`users` table)
- `status` — `pending` | `verified` | `expired`
- `expires_at` — UTC, 5-day TTL from creation
- `partial_codes` — DB-persisted list of codes entered so far (for cross-session resume)
- `resume_pin_hash` — hashed 6-digit PIN for resuming a saved session
- `resume_new_username` — saved new username for resume

### `StudentRecoveryCode`
- `recovery_request_id` — FK to `RecoveryRequest`
- `seat_id` — FK to student seat that will verify
- `code_hash` — `HMAC(6-digit-code, b'')` — set when student completes verification;
  `NULL` means student has not yet generated their code
- `verified_at` — timestamp when student completed their verification

---

## VI. Recovery Flow

### Step 1 — Roster verification and request creation

**Pair resolution chain:**

The backend requires knowing how many pairs to expect and exactly which `join_codes` it is looking for. The sequence is:

1. `join_code → class_id → teacher identifier`
   Resolve the *first* submitted join code to determine the target teacher. If it is unrecognized, reject the entire submission generically.
2. `collect all join_codes under that teacher`
   Retrieve the definitive list of all active class `join_codes` for this teacher from the backend.
3. `verify collected join_code matches backend list`
   Compare the submitted set of `join_codes` against the backend's definitive list. They must match exactly (no missing classes, no extra unrecognized classes, no duplicates). If they do not match, reject the entire submission generically.
4. `verify each username belongs in the correct join_code`
   For each submitted pair, search for the `username_lookup_hash` strictly within the roster of that specific `join_code`. If any username is not found in its corresponding class, reject the entire submission generically.

**Submission rules:**
- One pair is required per active class taught by the teacher.
- The set of `join_codes` submitted must exactly match all active classes — no partial coverage or duplicate submissions are accepted.
- All pairs are validated in full before any are accepted. Partial success is never reported.
- Generic error on any failure. Do not reveal which pair failed, which join code was unrecognized, or whether any student username exists.
- If an active recovery request already exists for this teacher, redirect to
  the recovery status page rather than creating a duplicate.

On success: a `RecoveryRequest` is created with `status = 'pending'` and
`expires_at = now + 5 days`. One `StudentRecoveryCode` row is created per selected
student with `code_hash = NULL`.


### Step 2 — Student verification and code generation

**Student side:**

Each selected student sees a persistent banner at the top of the app on their next
login (or immediately if already logged in). The banner prompts them to verify their
teacher's recovery request.

Student action sequence:
1. Student sees the banner and confirms.
2. Student enters their passphrase (financial-gate verification, same as any financial
   action).
3. On successful passphrase verification, the system generates a **6-digit numeric**
   recovery code and displays it to the student.
4. The code hash (`HMAC(code, b'')`) is stored in `StudentRecoveryCode.code_hash`.
5. Student communicates the plaintext code to their teacher in person.

Rules:
- Each student generates exactly one code per recovery request.
- The 6-digit code is generated by the system, not chosen by the student.
- Once generated, the code is not redisplayed. If the student loses it, the teacher
  must invalidate and restart (or wait for failure invalidation).
- Students cannot confirm outside an active `RecoveryRequest` with `status = 'pending'`.

**Teacher side — recovery status:**

Teacher monitors `/recovery-status` to see how many students have verified
(`code_hash IS NOT NULL`) vs. total required. The page shows a count only —
not individual student names or code values.

### Step 3 — Code entry and submission

Teacher navigates to `/reset-credentials` and enters all recovery codes collected
from students.

**Persistence across sessions:**

Entered codes and the new username are saved to `RecoveryRequest.partial_codes` and
`RecoveryRequest.resume_new_username` in the database when the teacher saves progress.
A 6-digit **resume PIN** is generated, hashed as `HMAC(pin, b'')`, and stored in
`RecoveryRequest.resume_pin_hash`. The teacher uses this PIN at `/resume-credentials`
to reload their saved state on any future browser session within the 5-day window.

Persistence rules:
- Entered codes are DB-persisted, not session-only.
- The teacher may enter codes gradually as students provide them.
- **Before submission, no indication is shown as to which entered codes are valid
  or invalid.** Codes are stored as entered without pre-validation feedback.

**Submission:**

When the teacher submits all entered codes:
- Backend verifies all students have generated codes (`code_hash IS NOT NULL` for all).
- Codes are validated as a set (order-independent): `set(HMAC(entered, b''))` must
  equal `set(stored code_hashes)`.
- **On any failure (wrong count, invalid format, hash mismatch): ALL `StudentRecoveryCode`
  rows are invalidated (`code_hash = NULL`, `verified_at = NULL`).** Students must
  regenerate their codes from the banner.
- **The failure message does not indicate which code failed or why.** A single generic
  error is shown.
- Teacher may attempt resubmission after students regenerate codes, within the 5-day
  window.

### Step 4 — Credential re-establishment

If all codes match:
- Teacher enters new username and scans a newly generated TOTP QR code.
- TOTP code from the new device is verified before credentials are written.
- All previously enrolled user-owned passkeys are revoked.
- New `users.username_hash`, `users.username_lookup_hash`, and
  `users.totp_secret_encrypted` are written atomically.
- `RecoveryRequest.status` is set to `verified`.

### Step 5 — Completion

On successful credential setup:
- `RecoveryRequest.status = 'verified'`, `completed_at` set.
- Session recovery keys cleared.
- Teacher redirected to login with new credentials.
- Audit log: teacher identity + timestamp only; no student PII logged.

---

## VII. Session Expiry

The entire recovery session (Steps 1–5) expires 5 days after Step 1 completion.

On expiry:
- `RecoveryRequest.status` is set to `expired`.
- All `StudentRecoveryCode` rows become inert.
- Entered partial codes and resume PIN are inaccessible.
- Teacher must restart from Step 1.

---

## VIII. Security Properties

| Property | Mechanism |
|----------|-----------|
| Distributed trust | One student per class; all must verify |
| All-or-nothing code validation | Any wrong code wipes all codes — no incremental probing |
| No pre-submission feedback | Entered codes show no valid/invalid state before submit |
| Generic failure messages | No indication of which code or student caused failure |
| Cross-session persistence | Partial codes persisted in DB via resume PIN, not session |
| Resume PIN | 6-digit PIN, hashed — links browser back to DB-stored progress |
| Passphrase gate on students | Student must re-enter passphrase to generate their code |
| No contact PII | No email, phone used at any stage |
| No DOB | No date of birth used anywhere |

---

## VIII-A. Canonical Credential Ownership

Teacher recovery targets the canonical `users` row. The authenticated credential
state is:

- `users.username_hash`
- `users.username_lookup_hash`
- `users.totp_secret_encrypted`
- user-owned passkey metadata

Legacy teacher/admin rows may be synchronized during the migration bridge so existing
routes continue to render, but they are not credential authority. Passkey revocation
must revoke credential metadata where `user_id` is the recovered teacher user.

Any implementation that can reset a teacher username or TOTP secret without resolving
the canonical `users.id` first is non-compliant.

---

## IX. Hard Boundaries

The teacher recovery system must NOT:

- Accept partial class coverage (all active classes must be represented)
- Pre-validate individual codes before the teacher submits all of them
- Reveal which code, student, or class caused a validation failure
- Preserve any `StudentRecoveryCode.code_hash` after a failed submission
- Collect or verify DOB at any point
- Allow student-initiated confirmation outside an active `RecoveryRequest`
- Preserve enrolled passkeys across a recovery event
- Log student PII in recovery audit records

---

## XI. Amendment

Revisions require version increment, effective-date update, and continued consistency
with `INV-CORE-000` and:

- `DOM-IDEN-001_IDENTITY_CLASS_BINDING_DOMAIN.md`
- `DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
