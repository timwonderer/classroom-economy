# DOM-IDEN-003: Teacher Identity Architecture

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-003     | 1.1     | 2026-06-05     | 1.0 | Normative |

## I. Purpose

This document defines the v2 identity model for teacher (admin) participation inside CTH.

It is a companion to `docs/SPECS/V2_STUDENT_IDENTITY_ARCHITECTURE.md`.
Both roles use the same `users`, `seats`, and `classes` tables, differentiated by
`user_role` on the `users` row and `role` on the `seat`.

This document assumes the clean v2 identity redesign. It is not a v1-to-v2 migration
plan and does not preserve v1 data model constraints.

Supersedes `docs/ARCHITECTURE/IDENTITY/ARC-IDEN-001_Admin_Identity_Handling.md`.

## II. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-IDEN-001_IDENTITY_CLASS_BINDING_DOMAIN.md`
- `DOM-IDEN-002_STUDENT_ACCOUNT_RECOVERY.md`
- `DOM-IDEN-004_TEACHER_ACCOUNT_RECOVERY.md`
- `docs/SPECS/V2_STUDENT_IDENTITY_ARCHITECTURE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`

## III. Core Design Principle

CTH uses a unified identity model. Both teachers and students are represented as `users`
with one or more `seats`. The role differentiates behavior, not the table.

```text
users (user_role = 'teacher' | 'student' | 'sysadmin')
  └─< seats (role = 'teacher' | 'student') >─ classes
         │
         └─1:1 identity_profiles
```

No DOB is stored or used anywhere in the v2 identity model for either role.

---

## Identity Layers

### Users (Unified Credential Store)

Purpose: authentication, recovery, and global security state for all principals.

The `users` table is shared by teachers and students. The `user_role` field identifies
which credential scheme and authentication flow applies.

Key fields:

- `id`
- `user_role` — `'teacher'` | `'student'` | `'sysadmin'`
- `username_hash` — HMAC of the normalized username; primary auth lookup key
- `username_lookup_hash` — secondary lookup index (indexed separately)
- `totp_secret_encrypted` — **teacher only**; base64-encoded encrypted TOTP seed
- passkey capability — **teacher/sysadmin only, optional**; implemented by
  credential metadata rows owned by `users.id`
- `pin_hash` — **student only**; hashed PIN used for login
- `passphrase_hash` — **student only**; hashed passphrase used to gate financial actions
- recovery capability — implemented by canonical recovery-token lifecycle state
- `reset_code_expires_at`
- `current_session_started_at`
- `current_session_expires_at` — fixed window set at login, does not slide forward
- `current_session_nonce` — regenerated at each login; binds requests to one session
- `last_active_class_id` — persisted preference only; login may fall back to explicit class selection when this pointer is missing or stale, but runtime authority still comes from a validated `seat_id + class_id` pair
- `money_action_cooldown_until` — rate-limit guard for financial mutations
- `has_completed_setup`
- `created_at`
- `updated_at`

Rules:

- One `users` row per human identity, regardless of role.
- `user_role` is set at account creation and does not change.
- Teacher/Sysadmin-credential fields are `NULL` for student rows.
- Student-credential fields are `NULL` for teacher/sysadmin rows.
- No DOB, DOB hash, DOB sum, or any birth-date-derived field is stored on `users`.
- A teacher user may own multiple seats across multiple classes (one seat per class).
- A missing or invalid `last_active_class_id` must not be treated as authority failure by itself; the login boundary may surface explicit class selection when valid seats exist, and only fail closed after verifying that no valid class/seat options remain.
- Session window fields behave identically for both roles.
- Only one active session is supported per user identity.
- Passkey credential metadata may live in compatibility tables during migration, but
  the credential owner is always `users.id`.

### Passkey Credential Metadata

Passkey credentials are an authentication capability owned by `users`.

During the compatibility bridge, passkey metadata is implemented in:

- `teacher_credentials.user_id`
- `system_admin_credentials.user_id`

Rules:

- Passwordless external IDs use `user_<User.id>`.
- Legacy external IDs such as `admin_<id>` and `sysadmin_<id>` are invalid v2
  principals.
- Legacy `teacher_id` and `sysadmin_id` columns on credential metadata tables are
  route compatibility shadows only.
- Passkey metadata tables do not authorize class access, seat access, recovery, or
  economic actions.

### Classes

Same as defined in `docs/SPECS/V2_STUDENT_IDENTITY_ARCHITECTURE.md`.
Teachers and students both participate in the same class universe anchored by the
`classes` table.

### Seats

A seat represents one actor inside one class universe.

Seat `role` field values:

- `'student'` — a participant in the economy (earns, spends, claims)
- `'teacher'` — the operator of the economy (administers, configures, approves)

Key fields (shared with student seats, same table):

- `id`
- `public_id`
- `class_id → classes.class_id`
- `user_id → users.id` (nullable until account setup is complete)
- `role` — `'teacher'` | `'student'`
- `block_identifier` — the class period identifier this seat belongs to
- `teacher_notes_encrypted` — optional operator-visible notes (not in student view)
- `roster_fingerprint` — used for claim matching (students); not applicable for teachers
- `dedupe_code` — used for DOPO handling (students); not applicable for teachers
- `claimed_at`
- `created_at`
- `updated_at`

Rules:

- A teacher seat is created when the teacher sets up a class.
- A teacher seat belongs to exactly one class universe.
- `public_id` is the UUID-encoded canonical deidentified public actor identifier.
- A teacher may hold seats in multiple classes (one seat per class).
- Teacher seats do not use `roster_fingerprint` or `dedupe_code`; those fields are
  `NULL` for teacher seats.
- `teacher_notes_encrypted` is accessible only to the seat's teacher and system admins.

### Identity Profiles

Same table and structure as student identity profiles. One profile per seat. Contains
display identity only.

Key fields:

- `id`
- `seat_id → seats.id`
- `first_name_encrypted`
- `last_initial`
- `created_at`
- `updated_at`

Rules:

- One identity profile per seat, regardless of role.
- Teacher display names are stored here, not on a separate teacher table.
- `last_initial` is used for display and does not derive from any PII source.

---

## Authentication Flows

### Teacher Login

```text
1. Teacher submits username.
2. Backend computes username_lookup_hash and finds the users row.
3. Backend verifies user_role == 'teacher' OR 'sysadmin'.
4. If passkey is enrolled and the client supports it → passkey challenge (preferred).
5. Otherwise → TOTP challenge using totp_secret_encrypted.
6. On success: write current_session_started_at, current_session_expires_at,
   current_session_nonce.
7. If user_role == 'teacher': Load teacher's available seats and restore active seat context via `last_active_seat_id` (see DOM-IDEN-001 Section IX.3).
8. If user_role == 'sysadmin': Active seat context is NULL (global access).
```

TOTP is required for all teacher accounts. Passkey is an optional second authentication
method — when enrolled, it replaces the TOTP step for that device.

### Teacher Account Creation

```text
1. System admin or invite flow creates a users row (user_role = 'teacher').
2. Teacher completes TOTP setup (required before has_completed_setup = true).
3. Teacher optionally enrolls a passkey.
4. A seat is created for the teacher's first class (role = 'teacher').
5. An identity profile is created for that seat.
```

### Teacher Session

Session semantics are identical to students:

- `current_session_expires_at` is set once at login. It does not slide forward on activity.
- `current_session_nonce` is checked on every request.
- All three session fields are replaced on the next successful login.

### Teacher Financial Actions

Teachers administering financial actions (adjustments, payroll, approvals) are
authenticated by the existing session. There is no additional passphrase gate for
teachers — the TOTP at login is the authentication signal.

---

## What Is Not In The Target Model

The following patterns are explicitly excluded from the v2 teacher identity model:

- **Separate `teachers` / `admins` table** — target model uses `users` + `seats`
- **DOB or DOB-derived hashes** — no birth date is stored or used for teacher identity
  or recovery at any point
- **Plaintext username** — `username` column does not exist; only `username_hash` and
  `username_lookup_hash`
- **`teacher_public_id` as a separate field** — display identity lives in `identity_profiles`
- **`dob_sum_hash` / `salt` for DOB** — removed; no DOB recovery mechanism
- **`has_assigned_students` flag** — setup state belongs on `has_completed_setup`
- **Passkeys owned by role-specific principal IDs** — passkey metadata may be stored
  in compatibility tables, but ownership is `users.id`

---

## Credential Comparison: Teacher vs. Student

| Credential | Teacher / Sysadmin | Student |
|------------|---------|---------|
| Username | `username_hash` / `username_lookup_hash` | `username_hash` / `username_lookup_hash` |
| Primary auth factor | TOTP (`totp_secret_encrypted`) | PIN (`pin_hash`) |
| Secondary / optional factor | Passkey metadata owned by `users.id` | Passphrase (`passphrase_hash`) |
| Passphrase use | N/A | Gates financial actions only |
| DOB | **Not stored** | **Not stored** |
| Recovery | User-owned recovery-token lifecycle | User-owned recovery-token lifecycle |
| Session | Nonce + expiry window | Nonce + expiry window |

---

## Canonical Identity Invariants

- `users.id` is the internal credential identity key for all principals.
- `seat_id` is the participant identity inside a class for all principals.
- `class_id` is the class-universe identity.
- `user_role` on `users` determines the credential scheme; `role` on `seats` determines
  the operational role within a class.
- No DOB is stored in any form at any point in the identity lifecycle.
- Teacher authentication always requires TOTP or passkey. PIN is for students only.
- Student financial actions always require passphrase re-verification. This gate does
  not apply to teachers.

---

## XII. Amendment

Revisions to this document must increment the version number, update the effective date, and remain consistent with foundational documentation standards.
