# DOM-IDEN-001: Identity Class Binding Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-001 | 1.5 | 2026-06-05 | 1.4 | Constitutional |

---

## I. Purpose

This document defines the Identity and Class Binding domain as the absolute sovereign of human identity (users), classroom participation (seats), and the logical boundaries of the classroom economy (classes). It ensures that every economic action is anchored to a verified participant and prevents identity leakage or cross-class contamination.

## II. Scope

This domain governs:
- **Global Human Identity**: The origin, authentication capability, and lifecycle of `users` records.
- **Class Context**: The definition and lifecycle of `classes`.
- **Actor Binding**: The "Claim" lifecycle that links a global user to a class-local seat.
- **Session Resolution**: The mapping of an authenticated session to an active class context.

This domain does not own:
- **Financial Truth**: Owned by `Ledger`.
- **Operational Facts**: Owned by `Attendance`.
- **Policy/Directives**: Owned by `Class Configuration`.

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000`, `INV-CORE-001`, and `INV-ARC-008`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE.md`
- `docs/SPECS/V2_STUDENT_IDENTITY_ARCHITECTURE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`

## V. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `users`
- `seats`
- `identity_profiles`
- `classes`

## VI. Owned Tables

### 1. `users`

Global human identity. Owns authentication credentials, passkey capability, recovery
capability, and session nonces.

### 2. `seats`

Class-local participant record. The "Economic Identity." Every activity record in other domains MUST reference `seat_id`.

### 3. `identity_profiles`

Human-facing display identity (Names, initials). One-to-one with `seats`.

### 4. `classes`

The universe anchor. Defines the boundary of a classroom economy.

Key metadata:
- `display_name` — human-facing class title (for example `Honors Chemistry`)
- `section` — human-facing section label (for example `2`, `Block A`, `Period 1`)

---

## VII. Schema Contract

### 1. `users`

Key fields:
- `id` (PK)
- `user_role` — `'teacher'` | `'student'` | `'sysadmin'`
- `username_lookup_hash` — HMAC-based lookup
- `totp_secret_encrypted` / `pin_hash` / `passphrase_hash`
- `username_hash` — canonical credential verifier for username-based login
- `last_active_class_id` — nullable class-context restoration preference; the login boundary may use it when valid, but it is never runtime authority
- `current_session_nonce` — binds requests to a specific login event
- `last_active_seat_id` — nullable FK to `seats`; tracks the last resolved context for multi-device continuity

Rules:
- One row per human identity.
- `user_role` is immutable after creation.
- No PII (Date of Birth) shall be stored.
- Credential metadata tables may implement authentication capabilities, but their
  authority is always derived from `users.id`.
- If `last_active_class_id` is missing or stale, the login boundary may surface explicit class selection when valid seats exist; it must fail closed only after confirming that no valid class/seat pair remains.

### 2. `seats`

Key fields:
- `id` (PK)
- `public_id` — UUID-encoded canonical deidentified public actor identifier
- `user_id` — nullable; FK to `users` (The Binding)
- `class_id` — FK to `classes` (The Anchor)
- `role` — `'teacher'` | `'student'`
- `claim_first_name_hash` / `claim_last_name_hash` — class-local seat-claim
  verification artifacts
- `claimed_at` — timestamp of binding

Rules:
- A seat is "Unclaimed" if `user_id` is NULL.
- A seat is "Claimed" if `user_id` is NOT NULL.
- Claim verification hashes belong to the seat. They prove entitlement to this
  class-local participant position; they do not authenticate the user globally.
- **INV-IDEN-011: One-to-One Binding per Class**: A single `user_id` may own multiple seats across the system, but at most ONE seat per `class_id`.
- **INV-IDEN-013: Seat Public-ID Scope**: Class-scoped participant URLs MUST expose `seats.public_id` and resolve it under the active `class_id`. A public ID from another class MUST be rejected, including when both classes belong to the same teacher.
- `seats.public_id` is the canonical deidentified public actor identifier for both teacher and student
  seats inside class-scoped runtime, support, and navigation contexts.
- `seats.public_id` is a UUID encoded as a 36-character string. It carries no
  human-readable or role-specific meaning and MUST resolve under the active `class_id`.
- Section or period metadata belongs to `classes.section`. Any remaining seat-level
  block or section fields are compatibility mirrors only and MUST NOT be treated as
  canonical class identity.

---

## VIII. Identity Lifecycle & Provisioning Law

### 1. User Origin
- **Teacher Origin**: Created via Sysadmin provisioning or verified Invite flow.
- **Student Origin**: May be provisioned before claim as an inactive auth shell.
  Roster upload must not activate credentials or create a separate student principal.
  Claim/setup activates credentials on the same `users` row or binds the seat to an
  already-authenticated compatible `users` row.
- **Sysadmin Origin**: Bootstrapped via secure environment configuration or existing Sysadmin promotion.

### 2. Seat Provisioning
- **Teacher Seat**: Created automatically when a Teacher initializes a class.
- **Student Seat**: Created by a Teacher (Roster Upload) or as a "Generic Placeholder" waiting for a claim.

### 3. Roster Provisioning Contract
When a teacher uploads a roster:

1. A `classes` row already exists or is created.
2. A `users` row is provisioned as the future authentication principal, with no
   active credentials.
3. A `seats` row is provisioned and bound to the class.
4. An `identity_profiles` row is provisioned one-to-one with the seat for display.
5. Claim artifacts are stored on the seat.
6. No authentication credentials are activated yet.

The roster upload creates a future participant position inside a class universe. It
does not create an authoritative `Student`, `TeacherBlock`, or other role-specific
principal.

---

## IX. Seat Binding & Context Law

### 1. The Claim Lifecycle
Binding a global user to a class-local seat is a non-reversible transaction (within the scope of a single class cycle).

- **Claim Logic**: A user provides a `join_code` + `claim_credentials` (e.g. roster name).
- **Binding**: On match, the `user_id` is written to the `seats` row. This seat is now "Claimed."
- **Immutable Association**: Once `claimed_at` is set, the `user_id` on a seat MUST NOT be changed to a different `user_id`.
- **Credential Activation**: PIN/passphrase setup activates authentication on `users`;
  it does not move display identity or claim authority out of the seat.

### 2. Context Resolution (The Binding Guard)
Every request operating within a class MUST be resolved to a specific `seat_id`.

- **INV-IDEN-012: Context Authority**: The system MUST verify that the authenticated `user_id` owns the `seat_id` provided in the request context for that `class_id`.
- **INV-IDEN-013: Seat Public-ID Scope**: A participant URL is valid only when `seats.public_id`, the signed navigation context, and the active `class_id` all resolve to the same seat.
- **Global vs. Scoped Requests**:
  - **Global Requests**: Authentication only (`user_id`). Permitted for identity management, class selection, and Sysadmin actions.
  - **Scoped Requests**: Authentication + Authorization (`user_id` + `seat_id`). MANDATORY for all activity in Ledger, Obligations, Attendance, and Store domains.
- Cross-seat or cross-class requests where the `user_id` does not own the target `seat_id` MUST be rejected.
- Class-scoped participant routes MUST NOT accept numeric student IDs or role-specific public IDs as aliases for `seats.public_id`.

### 3. Context Restoration Law (The Sticky Context)
To support multi-device continuity and prevent "Class Drift," the system maintains a persistent pointer to the last used context.

- **Storage**: The `users.last_active_seat_id` is updated every time a user explicitly switches their active class context. This includes initial seat claim/setup.
- **Restoration**: On initial authentication (or session recovery), if no context is provided, the backend SHOULD resolve the request to the `last_active_seat_id`.
- **Validation**: Restored context must still pass `INV-IDEN-012` validation. If the seat is no longer valid (e.g. deleted or unassigned), the user must be prompted to select a new context.

---

## X. Invariants

- **INV-IDEN-001: Unified Role Model**. No separate `students` or `teachers` tables. All role differentiation happens via `user_role` (Global) and `role` (Seat).
- **INV-IDEN-002: Seat Sovereignty**. `seat_id` is the primary key for all activity-tracking in other domains.
- **INV-IDEN-010: Roster Provisioning Is Not Student Creation**. Roster upload
  provisions a user shell, a class-local seat, a display profile, and claim artifacts;
  it does not create an authenticated student principal.
- **INV-IDEN-011: One-to-One Binding per Class**. A user shall not hold multiple seats in the same class universe.
- **INV-IDEN-012: Context Authority**. Requests must prove ownership of the `seat_id` context.
- **INV-IDEN-013: Seat Public-ID Scope**. Participant URLs expose a class-local `seats.public_id` and fail closed on any active-class mismatch.

---

## XI. Derived / Cross-Domain Rules

- Other domains reference `seat_id` (activity) and `class_id` (policy).
- `user_id` is for authentication, recovery, and global security only.
- Identity does not grant financial or attendance authority; it only provides the *binding* for those domains to record facts.

---

## XII. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000` and `INV-ARC-008`.
