# DOM-IDEN-002: Student Identity Architecture

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-002 | 2.3 | 2026-07-10 | 2.2 | Constitutional |

---

## I. Purpose

This document defines how the canonical identity objects defined by DOM-IDEN-001 are specialized for student participation within Classroom Token Hub. It governs student-specific credential structure, authentication, account recovery, and the claim data model.

This document is subordinate to **DOM-IDEN-001** (Canonical Identity Model) and **DOM-IDEN-005** (Identity Binding and Lifecycle). Those documents define the universal identity objects and lifecycle laws. This document specializes those definitions for the student role.

> [!IMPORTANT]
>
> This document defines the canonical v2 identity model. It does not preserve v1 data model constraints. Legacy tables (`students`, `student_teachers`, `student_blocks`, `class_memberships`) are migration artifacts and SHALL NOT be treated as identity authority.

---

## II. Scope

This document governs:

- Student-specific credential fields on `users`
- Student-specific seat fields (claim artifacts)
- Student authentication flow
- Student session establishment
- Student account recovery
- Student-specific claim data model (field definitions for `roster_fingerprint`, `dedupe_code`, claim hashes)

This document does **not** govern:

- The canonical identity objects themselves (DOM-IDEN-001)
- Identity binding and lifecycle rules (DOM-IDEN-005)
- Canonical context resolution (DOM-IDEN-006)
- Economic activity (Ledger domain)
- Attendance facts
- Store ownership
- Class policy

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

This document does not own any tables exclusively but rather defines how student identity is handled within Classroom Token Hub.

### Schema Contract

Student-specific fields on `users`: `pin_hash`, `passphrase_hash`, `reset_code`, `reset_code_generated_at`, and `reset_code_expires_at`.

Student-specific fields on `seats`: `roster_fingerprint`, `dedupe_code`, claim first-name/last-name lookup hashes, `claimed_at`.

### Constraints

- `pin_hash` and `passphrase_hash` SHALL be `NULL` for non-student users.
- `roster_fingerprint` and `dedupe_code` SHALL be `NULL` for non-student seats.
- `UNIQUE(class_id, roster_fingerprint, dedupe_code)` on `seats`.
- `UNIQUE(user_id, class_id)` on `seats`.

### Derived / Cross-Domain Rules

Economic and activity records reference `seat_id` for actor identity per INV-ARC-019 §VII. This document does not define cross-domain table schemas.

---

## VI. Student Identity Layers

Student identity follows the universal three-layer model defined by DOM-IDEN-001:

- **`User`**: authentication principal — owns credentials, recovery, and global security state
- **`Seat`**: class-local actor - the canonical participant record inside a class
- **`Class`**: economic universe boundary

Economic activity is always tied to `seat_id`, never directly to `user_id`.

### Student `User` Fields

A student `User` is a `users` row with `user_role = 'student'`. Common `users` fields are defined by DOM-IDEN-001. This section defines only the student-specific delta.

Student-specific fields:

- `pin_hash` — hashed PIN used for login
- `passphrase_hash` — hashed passphrase used to gate financial actions
- `recovery_code` - 8-digit alphanumeric code randomly generated and stored on the corresponding student user row for student to reclaim their account
- `recovery_code_issued_at` - timestamp of when the recovery code was issued. Stored as UTC but rendered to canonical class timezone.
- `recovery_code_expires_at` - set to 10 minutes after `recovery_code_issued_at`. Stored as UTC but rendered to canonical class timezone.


Teacher-specific fields (`totp_secret_encrypted`) SHALL be `NULL` for student rows.

Student-specific rules:

- A `users` row may be provisioned before claim; credentials are activated when a student claims a seat and completes setup.
- Recovery capability belongs to `users` and is implemented by `user_recovery_tokens` (per INV-ARC-019 §XI), not by `seats`, `classes`, or display profiles.

### Student `Seat` Fields

A student seat is a `seats` row with `role = 'student'`. Base seat fields and participation rules are defined by DOM-IDEN-001. This section defines only the student-specific delta.

Student-specific claim fields:

- `roster_fingerprint` — derived from minimal claim identity after normalization
- `dedupe_code` — short code for Duplicate-On-Paper-Only (DOPO) disambiguation
- claim first-name/last-name lookup hashes
- `claimed_at`

Student-specific rules:

- `user_id` is nullable until the seat is claimed.
- Claim lookup hashes belong on the seat because they prove entitlement to this class-local participant position (per INV-ARC-019 §VII).

### Student `IdentityProfile`

Defined by DOM-IDEN-001. No student-specific delta. Profiles do not store claim lookup hashes, credentials, or recovery artifacts.

---

## VII. Student Authentication

### Login Flow

```text
1. Student submits username.
2. Backend computes username_lookup_hash and finds the users row.
3. Backend verifies user_role == 'student'.
4. Student submits PIN.
5. Backend verifies pin_hash.
6. On success: write current_session_started_at, current_session_expires_at,
   current_session_nonce.
```

Active seat and class context restoration follows DOM-IDEN-006.

### Session Establishment

- `current_session_started_at` is written at sign-in.
- `current_session_expires_at` is written once at sign-in (fixed window, does not slide forward on activity).
- `current_session_nonce` is regenerated at sign-in and binds requests to one specific login session.
- All three session fields are replaced on the next successful sign-in.

Request-time session validation is governed by DOM-IDEN-006.

### Financial Action Gate

Student financial actions (transfers, purchases, insurance claims) require passphrase re-verification. The passphrase gate is separate from the PIN used at login.

---

## VIII. Roster Provisioning and Claim

Roster provisioning and claim identity are governed by DOM-IDEN-005. This section specifies the student-specific claim data model.

### Roster Provisioning

Roster provisioning rules are defined by DOM-IDEN-005 §VII. This section defines the student-specific claim artifacts that roster provisioning produces.

### Roster Fingerprint

`roster_fingerprint` is derived from minimal claim identity after normalization:

`HMAC(server_secret, normalized_first_name | normalized_last_name | optional_dedupe_code)`

The exact normalization routine is an implementation detail, but the result must be stable for claim lookup inside a class.

### Duplicate-On-Paper-Only (DOPO) Handling

When two or more students in the same class roster share the same name during a single roster upload session:

1. Generate a short `dedupe_code` for colliding seats.
2. Store that code on the seat.
3. Include the code in the fingerprint input for the affected seats.
4. Teacher communicates the code to the affected students during claim.

### Claim Flow

1. Student enters join code, first name, last name, and optional dedupe code.
2. Backend resolves class context from the join code.
3. Backend normalizes the entered name and computes `roster_fingerprint`.
4. Backend looks up the matching seat in that class.
5. If exactly one seat matches, claim proceeds.
6. If duplicate-name seats exist, dedupe code is required to disambiguate.
7. On successful claim, the seat is bound to `user_id` and marked with `claimed_at`.
8. Credential setup activates login on `users`.
9. Initialize `last_active_class_id` and `last_active_seat_id` to the newly bound class and seat context (per DOM-IDEN-006 §XIII, identity lifecycle documents define how these pointers are initialized).

The identity inference prohibition defined in DOM-IDEN-005 §VII applies: unauthenticated claim SHALL NOT search for or infer existing User identities outside the current claim transaction.

### Student Seat State

Student seat state is limited to:

- **unclaimed** — `user_id IS NULL`, `claimed_at IS NULL`
- **claimed** — `user_id IS NOT NULL`, `claimed_at IS NOT NULL`

No intermediate states, soft deletes, archived identities, or dormant participants exist.

---

## IX. Student Account Recovery

> [!IMPORTANT]
>
> Student account recovery operates solely on `users` table, which represents the authenticated principal on Classroom Token Hub. does not require class context, participation state, or personally identifiable information (PII). Any implementation of additional look up is prohibited by this document.

Recovery restores credential access to an existing student `users` identity and therefore `seats` bound to the `users` identity. Per DOM-IDEN-005 §IX, recovery restores authentication capability without altering participation, ownership, or identity bindings.

### Core Invariants

1. **No new PII or external identity linkage.** Recovery methods SHALL NOT require additional information not already collected by the platform.
2. **Ledger immutability.** Recovery SHALL NOT modify, delete, merge, or rewrite historical economic records.
3. **Credential restoration only.** Recovery replaces credential access on the same `users` record. It does not create a new user, create a new seat, merge two records, or transfer economic state. Per DOM-IDEN-005 §IX, recovery SHALL NOT modify participation, ownership, or identity bindings.
4. **Single active code.** Only one active reset code per student identity at any time. New code generation will overwrite the existing code.
5. **Teacher-initiated.** Students cannot self-initiate recovery. A teacher must generate the reset code.

### What Is Recoverable

Student recovery restores access to an existing `users` row. All economic state remains attached to the same `seat_id` and `class_id`.

Credentials that are fully replaced during recovery:

- `username_hash` / `username_lookup_hash`
- `pin_hash`
- `passphrase_hash`

Records that are NOT touched during recovery:

- Economic records (transactions, balance cache)
- Entitlement records (student items, student insurance)
- Attendance records (attendance sessions, hall pass logs, seat attendance state)
- Obligation records (rent payments, insurance claims)

### Recovery Flow

**Step 1 — Teacher initiates**

A teacher with an active administrative seat in the student's class initiates a recovery reset for a claimed student seat. The system:

- Resolve the selected student Seat to its bound User, then issue a new recovery capability on the corresponding users row.
- Generates a new 8-character random alphanumeric reset code
- Fill in `reset_code` field with generated code. Overwrites any existing reset code
- Sets `reset_code_generated_at = now`
- Sets `reset_code_expires_at = reset_code_generated_at + 10 minutes`


The code is displayed to the teacher and communicated verbally to the student. The teacher may redisplay the code until it expires or recovery completes.

> [!NOTE]
>
> Reset codes are short-lived (10-minute TTL), teacher-visible, and communicated in person. Plaintext storage is acceptable for this handoff artifact. 

**Step 2 — Student submits reset code**

Student submits reset code. Backend validates:

- The submitted reset code matches the active recovery code on exactly one `users` row.
- Code has not been used
- Code has not expired (`now < reset_code_expires_at`)


On failure: return a generic failure message. Do not reveal whether a specific identity exists.

**Step 3 — Credential re-establishment**

Student proceeds through the standard credential setup flow:

- Username
- PIN
- Passphrase

No identity verification fields (name, DOB, or any PII) are re-entered. All three credentials are fully replaced atomically. Old credentials become invalid immediately.

**Step 4 — Completion**

On successful credential setup:

- Clear reset code and expiration
- Regenerate `current_session_nonce`
- Replace `users.username_hash`, `users.username_lookup_hash`, `users.pin_hash`, and `users.passphrase_hash` atomically
- Log successful reclaim event


### Recovery Security Constraints

- Reset codes must be random and non-sequential.
- Reset codes are single-use — cleared on successful use or expiry.
- Hard TTL: 10 minutes.
- Rate-limit reset code generation and submission.
- Lock recovery flow after repeated failed submission attempts per identity.
- Never reveal whether a specific student identity exists via error messages.

### Recovery Hard Boundaries

The student recovery system SHALL NOT:

- Create a new identity record during recovery
- Merge two identity records automatically
- Transfer balances between accounts
- Copy, recreate, or void items or entitlements
- Issue refunds during recovery
- Modify transaction history
- Adjust economic balances
- Collect or verify DOB at any point

---

## X. Credential Summary

| Credential | Student |
|------------|---------|
| Username | `username_hash` / `username_lookup_hash` |
| Primary auth factor | PIN (`pin_hash`) |
| Financial action gate | Passphrase (`passphrase_hash`) |
| Recovery | Teacher-initiated reset code → credential re-establishment |
| Session | Nonce + fixed-window expiry |

---

## XI. Forbidden Patterns

- Separate `students` table as identity authority (legacy migration artifact)
- Domain tables keyed primarily by `seat_id` and `class_id`
- Separate roster-stage and claim-stage participant tables that duplicate `seat`
- Business tables using `join_code` as an internal foreign key after class resolution
- DOB or DOB-derived fields for any purpose
- Merging or inferring identity across class boundaries during claim

---

## XII. Amendment

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with DOM-IDEN-001 and DOM-IDEN-005.
4. Maintain consistency with INV-CORE-000.
