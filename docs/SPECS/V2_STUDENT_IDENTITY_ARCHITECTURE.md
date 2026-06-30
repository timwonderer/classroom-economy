# Classroom Token Hub (CTH) v2 Student Identity Architecture

> **Terminology Note:** This spec was written during the v1→v2 transition. Legacy model references (`Admin`, `StudentTeacher`, `TeacherBlock`, `get_admin_student_query`) describe v1 shadows that are migration targets. The v2 canonical identity model uses `User` (global principal) + `Seat` (class-local binding) with `class_id` as the class boundary.

## Purpose

This document defines the v2 identity model for student participation inside CTH.

This document defines the canonical v2 identity model. It does not preserve v1 data
model constraints.

It answers four questions:

1. What object represents login credentials?
2. What object represents a participant inside a class universe?
3. Where do roster and claim identity live?
4. What identifier owns economic activity?

This is an identity-model document, not a full class-scope normalization plan. For
class scoping and `class_id` normalization, see:

- `docs/MAP/MAP-CLASS-002_CLASS_SCOPE_NORMALIZATION_TARGET.md`
- `docs/SPECS/V2_CLASS_ID_INVARIANT_BACKLOG.md`

For request-boundary session expiry and mutation replay rules, see:

- `docs/SPECS/V2_SESSION_MUTATION_SAFETY.md`

For the shared identity ownership contract used by teacher and student seats, see:

- `docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`

## Core Design Principle

CTH separates identity into three layers:

- **User**: authentication identity
- **Seat**: participant identity inside one class universe
- **Class**: economic universe container

Economic activity is always tied to `seat_id`, never directly to `user_id`.

## Identity Layers

### Users

Purpose: authentication, recovery, and global security state.

Typical fields:

- `id`
- `username_hash`
- `username_lookup_hash`
- `pin_hash`
- `passphrase_hash`
- recovery capability fields or related `user_recovery_tokens`
- `current_session_started_at`
- `current_session_expires_at`
- `current_session_nonce`
- `money_action_cooldown_until`
- `has_completed_setup`
- `created_at`
- `updated_at`

Rules:

- A user row represents one human identity.
- A user row owns credentials, recovery, and global security state.
- A user row does not represent class membership.
- A user may own multiple seats across one or more classes.
- A user may temporarily exist with no active credentials during roster provisioning
  and claim/setup flow.
- A user with no remaining seats may be garbage collected.
- A user row may be provisioned before claim; credentials are activated when a student
  claims a seat and completes setup.
- Recovery capability belongs to `users` and is implemented by `user_recovery_tokens`,
  not by `seats`, `classes`, or display profiles.
- Session window data belongs on `users`, not on `seats` or `classes`.

Identifier guidance:

- `users.id` is the internal primary key used for foreign keys.
- `users.id` remains the internal FK target.
- Global identity workflows do not expose a separate user public-ID family.

Session guidance:

- `current_session_started_at` is written at sign-in.
- `current_session_expires_at` is written once at sign-in as 10 minutes after
  `current_session_started_at`.
- `current_session_nonce` is regenerated at sign-in and binds requests to one specific
  login session.
- `current_session_expires_at` is fixed for that login session and does not slide forward
  on activity.
- All three session fields are replaced on the next successful sign-in.
- Requests are valid only if the session-held nonce matches `current_session_nonce` and
  the current time is before `current_session_expires_at`.
- This supports one active session per user identity and prevents an older session from
  being revived by a newer login.

### Classes

Purpose: define an isolated classroom economy universe.

Typical fields:

- `class_id`
- `join_code_token`
- `section`
- `display_name`
- `created_at`
- `updated_at`

Rules:

- If the class row exists, that class universe exists.
- `classes` is a class anchor and lookup record, not a membership table.
- `classes` should not use a generic `user_id` field to imply participation.
- `section` is the canonical metadata field for the class section label
  (for example `2`, `Block A`, `Period 1`).
- `display_name` is the human-facing class title
  (for example `Honors Chemistry`).
- Teacher-facing display should treat `display_name` + `section` as the canonical
  pair when both are available.
- CTH does not model archive or inactive class states as identity.
- Deleting a class deletes its seats and class-scoped economic state.

### Seats

Purpose: represent one actor inside one class universe.

Typical fields:

- `id`
- `public_id`
- `class_id`
- `user_id`
- `teacher_notes_encrypted`
- `role`
- `block_identifier`
- `roster_fingerprint`
- claim first-name/last-name lookup hashes
- `dedupe_code`
- `claimed_at`
- `created_at`
- `updated_at`

Rules:

- A seat belongs to exactly one class.
- A seat is the canonical participant record inside that class.
- A user may own multiple seats, but each seat belongs to at most one user.
- `user_id` is nullable until the seat is claimed.
- If the seat exists, the participant exists in that class universe.
- Class-section metadata belongs on `classes.section`, not on `seats`.
  Any remaining seat-level block or section labels are compatibility mirrors only.
- `seats.public_id` is the public identifier for class-scoped participant navigation.
- `seats.public_id` is the canonical deidentified public actor identifier for both teacher and
  student seats when the actor is being referenced inside a class-scoped context.
- `seats.public_id` is a UUID encoded as a 36-character string and carries no
  human-readable or role-specific meaning.
- Teacher-facing participant routes MUST resolve `seats.public_id` within the active
  `class_id`; a public ID from another class MUST return `404`, including when both
  classes belong to the same teacher.
- A role-specific public ID and a legacy numeric student ID MUST NOT be accepted as
  substitutes for `seats.public_id` on class-scoped participant routes.
- Claim lookup hashes belong on the seat because they prove entitlement to this
  class-local participant position.

Recommended constraints:

- `UNIQUE(class_id, roster_fingerprint, dedupe_code)`
- `UNIQUE(user_id, class_id)`

### Identity Profiles

Purpose: store human-facing display identity.

Typical fields:

- `id`
- `seat_id`
- `first_name_encrypted`
- `last_initial`
- `created_at`
- `updated_at`

Rules:

- One profile per seat.
- Profiles contain display identity only.
- Profiles do not replace the seat as the canonical actor.
- Profiles do not store claim lookup hashes, credentials, or recovery artifacts.

## Target Table Reference Map

This section describes the intended reference model for the redesign.

It is not a readout of the current ORM. The current database structure should not be
treated as authoritative for architecture decisions.

### Core Graph

Target hard references:

- `seats.user_id -> users.id`
- `seats.class_id -> classes.class_id`
- `identity_profiles.seat_id -> seats.id`

Shape:

```text
users
  └─< seats >─ classes
         │
         └─1:1 identity_profiles
```

Meaning:

- `users` owns credentials and account recovery.
- `classes` defines the class universe boundary.
- `seats` is the only participant record inside a class.
- `identity_profiles` stores display identity for exactly one seat.

### Reference Rules

- Domain tables that describe a participant in a class should reference `seat_id`.
- Domain tables that describe class-wide policy or configuration should reference
  `class_id`.
- `user_id` should be used for authentication, recovery, and global security state only.
- `join_code` should be used only as a public entry token that resolves to `class_id`.
- Class-scoped participant URLs should use `seats.public_id`, then resolve to
  `seat_id + class_id` under the active request context.

## Runtime Context Flow

The intended runtime flow is:

1. Person logs in.
2. Backend resolves that person to one `users` row.
3. Backend loads the user's available `seats`.
4. Backend selects or restores the active `seat_id`.
5. Backend resolves `class_id` from that active seat.
6. Frontend asks what should be shown for the active class context.
7. Backend returns the active `seat_id`, active `class_id`, and class UI metadata.

Shape:

```text
login
  -> users
  -> seats
  -> current_seat_id
  -> current_class_id
  -> classes
  -> class-specific UI
```

Runtime meaning:

- `current_user_id` answers who is logged in
- `current_seat_id` answers which class-local actor is active
- `current_class_id` answers which class universe is active

UI and data rules:

- class shell, labels, and class-wide configuration load by `class_id`
- participant-specific activity, balances, and permissions load by `seat_id`
- frontend should ask for the active class context, not infer class scope on its own

### Domain Reference Targets

Economic and activity records should reference:

- `seat_id` for actor identity
- `class_id` when class-wide scope is also useful for query or auditing purposes

Examples:

- `ledger_entries.seat_id -> seats.id`
- `payroll_events.seat_id -> seats.id`
- `attendance_events.seat_id -> seats.id`
- `hall_pass_logs.seat_id -> seats.id`
- `rent_payments.seat_id -> seats.id`
- `insurance_enrollments.seat_id -> seats.id`
- `insurance_claims.seat_id -> seats.id`
- `student_items.seat_id -> seats.id`

Class-scoped configuration should reference:

- `class_id`

Examples:

- `feature_settings.class_id -> classes.class_id`
- `banking_settings.class_id -> classes.class_id`
- `payroll_settings.class_id -> classes.class_id`
- `hall_pass_settings.class_id -> classes.class_id`
- `store_items.class_id -> classes.class_id`
- `insurance_policies.class_id -> classes.class_id`

### What Should Not Exist In The Target Model

The redesign should avoid these patterns:

- domain tables keyed primarily by `student_id`
- separate roster-stage and claim-stage participant tables that duplicate `seat`
- business tables using `join_code` as their internal foreign key
- teacher ownership keys standing in for class scope
- separate `Student` and `Teacher/Admin` identity tables
- legacy bridge tables such as `teacher_blocks` and `student_teachers`

### Transitional Reality

Current runtime code still contains older tables such as `students` and `teacher_blocks`
and still uses `join_code` heavily in operational flows.

Those tables and columns should be treated as implementation artifacts, not
target-state identity anchors.

If a table map is meant to drive the redesign, the correct mental model is:

1. `users` is the credential principal.
2. `classes` is the universe anchor.
3. `seats` is the only class-local actor.
4. `identity_profiles` is a seat-owned display record.
5. participant activity hangs off `seat_id`.
6. class policy hangs off `class_id`.

## Canonical Identity Invariants

- `users.id` is the internal credential identity key.
- `seat_id` is the participant and economic identity.
- `class_id` is the class-universe identity.
- The target model replaces separate `Student` and `Teacher/Admin` identity tables with
  `users`, `seats`, and `classes`.
- A student's presence in a class is expressed by seat existence, not by a separate
  membership lifecycle model.
- Student seat state is limited to:
  - unclaimed
  - claimed

## Legacy Table Interpretation

Some existing tables should be treated as legacy implementation structures, not as part
of the target identity design.

Deprecated identity and membership structures:

- `students`
- `teachers` / `admins`
- `teacher_blocks`
- `student_teachers`
- `student_blocks`
- `classMemberships`

The use of these tables is strictly forbidden.



## Roster And Claim Identity

Roster and claim identity live directly on `seats`.

CTH does not need a separate `claim_identity`, `roster_entry`, or enrollment staging
table because:

- roster upload already creates the participant record
- roster upload may provision the inactive `users` auth shell that will later own
  credentials
- there is no separate approval or enrollment staging workflow
- historical enrollment tracking is intentionally out of scope
- editing a pending participant can be handled by deleting or replacing the seat

This keeps one canonical object through the full lifecycle:

- roster-created pending participant
- eventually claimed participant
- ongoing economic actor
- human-facing display identity remains in `identity_profiles`, not duplicated into a
  second participant-name table

The invariant is simple:

**If the seat exists, the participant exists in that class universe.**

### Claim-Related Seat Fields

Claim data stored on `seats`:

- `roster_fingerprint`
- `claim_first_name_hash`
- `claim_last_name_hash`
- `dedupe_code`
- `claimed_at`
- `user_id`

### Recommended Lookup Indexes

- index on `(class_id, roster_fingerprint)`
- index on `(user_id)`
- index on `(class_id, role)`
- optional index on `(class_id, claimed_at)` if pending-seat queries become common

## Claim Flow

1. Student enters join code, first name, last name, and optional dedupe code.
2. Backend resolves class context from the join code.
3. Backend normalizes the entered name and computes `roster_fingerprint`.
4. Backend looks up the matching seat in that class.
5. If exactly one seat matches, claim proceeds.
6. If duplicate-name seats exist, dedupe code is required to disambiguate.
7. On successful claim, the seat is bound to `user_id` and marked with `claimed_at`.
8. Credential setup activates login on `users`.
9. Set `current_class_id` to resolved class context from join code.

## Roster Fingerprint

`roster_fingerprint` is derived from minimal claim identity after normalization.

Conceptually:

`HMAC(server_secret, normalized_first_name | normalized_last_name | optional_dedupe_code)`

The exact normalization routine is an implementation detail, but the result must be
stable for claim lookup inside a class.

## Duplicate-On-Paper-Only Handling

Duplicate-On-Paper-Only (DOPO) means two or more students in the same class roster
share the same name during a single roster upload session.

Behavior:

1. Generate a short `dedupe_code` for colliding seats.
2. Store that code on the seat.
3. Include the code in the fingerprint input for the affected seats.
4. Teacher communicates the code to the affected students during claim.

This keeps duplicate-name handling local to the seat without inventing a separate
identity object.

## Economic Invariant

All economic state attaches to `seat_id`.

Examples:

- `ledger_entries`
- `payroll_events`
- any other class-local transactional record

This is the core boundary that keeps login identity separate from classroom economic
identity.
