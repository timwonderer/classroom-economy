# INV-ARC-019: Identity and Ownership Model

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-019      | 1.0     | 2026-06-08     | None | Constitutional |

---

## I. Purpose

This document defines the canonical identity and ownership boundaries for Classroom Token Hub (CTH) V2. It ensures a clear separation between global authentication principals, class-local operational actors, isolation boundaries, public reference keys, and presentation profiles.

---

## II. Scope

This model applies system-wide to database schema design, session management, routing logic, and capability validation across all domains and feature executors.

---

## III. Authority Level

Constitutional (Tier 1) within `INV-ARC`. Derived from `INV-CORE-000` Section III.4, `Principal and Actor Authority`, and governed within the hierarchy described by `INV-CORE-001`. This protocol is subordinate to foundational invariants.

---

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`

---

## V. Core Principle

Every runtime object has one authoritative owner.

Identity resolution must answer these questions separately:

1. Who authenticated?
2. Who acted?
3. In which boundary?
4. How is the actor referenced publicly?
5. What capability is being granted?

No identifier answers more than its assigned question.

## VI. Authentication Principal

### `users.id`

`users.id` identifies the authenticated human principal.

`users` owns:

- login
- passkeys
- TOTP
- recovery
- session establishment
- account deletion

`users` does not own:

- attendance
- hall passes
- economy operations
- student interactions
- support tickets
- class-local claim verification artifacts
- display identity

Passkey metadata may be implemented by dedicated credential tables, but the owning
principal is always `users.id`.

## VII. Operational Actor

### `seats.id`

`seats.id` identifies one actor operating inside one class.

`seats` owns actor attribution for:

- attendance
- hall passes
- payroll
- banking
- store
- rent
- insurance
- support tickets
- student detail pages
- classroom actions

`seats` also owns class-local claim state:

- claim lifecycle
- claim verification hashes
- claimed/unclaimed state
- authority to bind one user to one participant position in one class

Name-lookup hashes used during roster claim belong on the seat because they prove
entitlement to a specific class-local participant position. They are not global user
identity and they are not display identity.

Teacher seats and student seats follow the same actor model.

## VIII. Isolation Boundary

### `classes.class_id`

`classes.class_id` defines the boundary in which actors operate.

`classes` owns:

- membership boundary
- economy configuration
- policies
- feature enablement
- class labels
- classroom state

`join_code` is a human-facing class alias. It may locate a class for invitation,
claim, or routing convenience, but it MUST resolve to `class_id` before any
authority-sensitive operation.

## IX. Public Actor Identity

### `seats.public_id`

`seats.public_id` is the single canonical deidentified public actor identifier.

Rules:

- It is a UUID encoded as a 36-character string.
- It carries no human-readable or role-specific meaning.
- It is stable for the lifetime of the seat.
- It is safe to expose where a class-scoped actor must be referenced without exposing
  the internal `seats.id`.
- It MUST resolve under the active `class_id`.
- It MUST NOT grant authority by itself.

Use `seats.public_id` for:

- actor URLs
- teacher-facing participant lookup
- support correlation
- ticket actor attribution
- class-scoped analytics drilldowns

The following are invalid v2 residue, not supported identity alternatives:

- `Admin.public_id`
- `Admin.teacher_public_id`
- `Student.opaque_reference`
- separate TLCP actor identity families

`Student.internal_reference` is separate internal-locator residue. The canonical
internal actor key is `seats.id`.

Named cleanup debt:

- `TLCP-SCHEMA-001` — complete as of 2026-06-02. Physical TLCP actor
  columns/API labels now use `actor_public_id` and store `Seat.public_id`.

## X. Display Identity

### `identity_profiles`

`identity_profiles` owns presentation-only identity, including display names and
visible identity attributes.

Display identity does not participate in authentication, authority, ownership
resolution, or actor lookup.

Do not store claim artifacts, credential artifacts, or class authority in
`identity_profiles`.

## XI. Capability Tokens

Capability tokens grant permission to perform one defined action. They are not users,
seats, classes, or public actor identities.

Examples:

- `hall_pass_verify_token`
- recovery tokens
- claim tokens
- passkey credential metadata

Every capability design must answer two questions explicitly:

1. Which object owns the token?
2. Which `class_id`, if any, constrains its use?

Settled ownership:

- recovery capability is owned by `users` and implemented by `user_recovery_tokens`
- passkey capability is owned by `users`; compatibility credential metadata tables
  must key ownership by `user_id`
- roster claim verification is owned by `seats`

Ownership of `hall_pass_verify_token` remains under investigation. Its current
teacher-table ownership is not accepted as the final v2 design.

## XII. Roster Provisioning and Seat Claim

Roster upload provisions a future participant position. It does not create a
student-authenticated principal.

When a teacher uploads a roster:

1. A class exists or is created.
2. A `users` row is provisioned as an inactive authentication shell.
3. A `seats` row is provisioned and bound to the class.
4. An `identity_profiles` row is provisioned and bound one-to-one to the seat.
5. Claim artifacts are stored on the seat.
6. No credentials are activated yet.

Claim/setup later proves entitlement to the seat and activates credentials on
`users`.

## XIII. Runtime Context

The authenticated principal and active classroom context remain separate:

- `users.id` establishes who authenticated.
- `seats.id` establishes who acts.
- `classes.class_id` establishes where the actor acts.
- `seats.public_id` exposes the actor externally without exposing `seats.id`.

The session MUST NOT infer an actor or boundary from display fields, role-specific
public identifiers, legacy numeric participant IDs, or aliases once canonical context
is available.

## XIV. Settled Decisions

- `users.id` = authentication principal
- `seats.id` = operational actor
- `classes.class_id` = isolation boundary
- `seats.public_id` = canonical deidentified public actor identity
- `identity_profiles` = display-only identity
- `join_code` = boundary alias that resolves to `class_id`
- roster lookup hashes = seat-owned claim verification artifacts
- recovery tokens = user-owned recovery capability
- passkey metadata = user-owned authentication capability

## XV. Open Decisions

- `hall_pass_verify_token` ownership and boundary scope
- invalid public identifier residue removal order
- bridge-table retirement order

---

## XVI. Amendment

Revisions to this document must increment the version number, update the effective date, and remain consistent with foundational documentation standards and core invariants.
