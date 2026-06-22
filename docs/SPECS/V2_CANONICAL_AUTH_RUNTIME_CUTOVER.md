# V2 Canonical Auth Runtime Cutover

**Status:** Implemented (Wave 3C.12-H)
**Effective Date:** 2026-06-08

## Purpose

This document records the runtime identity/auth contract for the canonical v2 runtime.
It complements the constitutional identity docs and describes how the current code
must behave while compatibility residue still exists.

## Canonical Runtime Authority

The active authority chain is:

```text
users.id
  authenticates the human principal

seats.id + classes.class_id
  authorizes class-local actor behavior

identity_profiles
  displays the actor
```

`User` authenticates. `Seat` acts. `Class` scopes. `IdentityProfile` displays.

Deprecated tables such as `Student`, `Admin`, `SystemAdmin`, `TeacherBlock`, and
principal-based `ClassMembership` rows are not authoritative identity sources.

## Credential Ownership

`users` owns all credential verification:

- teacher username lookup and TOTP verification
- sysadmin username lookup and TOTP verification
- student username lookup and PIN verification
- student passphrase verification
- session nonce and expiry state
- recovery capability
- passkey capability

Passkey metadata may remain in credential tables while compatibility residue exists:

- `teacher_credentials.user_id`
- `system_admin_credentials.user_id`

Those rows are credential metadata only. Legacy `teacher_id` and `sysadmin_id` values
on those rows are compatibility-only metadata.

Passwordless external IDs must use:

```text
user_<User.id>
```

Legacy external IDs such as `admin_<id>` and `sysadmin_<id>` are invalid v2
principals and must fail closed.

## Session Contract

The session anchor is `session["user_id"]`.

Compatibility session keys may still exist:

- `session["admin_id"]`
- `session["student_id"]`
- `session["sysadmin_id"]`

These keys may only be populated after resolving the canonical `User` and loading the
compatibility rows owned by that user. They are not authentication authority and must
not be accepted as substitutes for `user_id`.

Class-scoped behavior must resolve:

```text
user_id + class_id + seat_id
```

`join_code` may appear at the boundary for entry, routing, or display, but it must
resolve to `class_id` before authority-sensitive work.

## Roster Provisioning

Roster upload creates a future participant position inside a class universe. It does
not create an authenticated student.

The provisioning contract is:

1. A class exists or is created.
2. A `User` row is provisioned as an inactive authentication shell.
3. A `Seat` row is provisioned and bound to the class.
4. An `IdentityProfile` row is provisioned and bound one-to-one to the seat.
5. Claim artifacts are stored on the seat.
6. No authentication credentials are activated.

Claim first-name and last-name lookup hashes belong on `Seat`, because they prove
entitlement to one class-local participant position. They do not identify a human
globally and they do not belong in `IdentityProfile`.

## Recovery Ownership

Recovery is a user-owned capability with a lifecycle. Canonical durable recovery
state belongs in `user_recovery_tokens`, not on `users` as a growing set of
one-off columns.

Recovery token lifecycle state includes:

- `created_at`
- `expires_at`
- `used_at`
- `revoked_at`
- `issued_by`

Short-lived teacher-visible reset-code fields may remain as compatibility residue,
but successful recovery must replace canonical credential hashes on `users`.

## Display Identity Boundary

`IdentityProfile` is presentation-only.

It may contain:

- preferred display name fields
- initials or display-safe labels
- presentation metadata

It must not contain:

- credential hashes
- passkey metadata
- recovery tokens
- claim lookup hashes
- class authority
- financial authority

## Remaining Bridge Debt

The following residue is allowed only while compatibility support remains:

- principal rows used by route templates
- session IDs derived from canonical `User`
- `TeacherBlock` roster mirrors
- principal IDs on class membership rows
- credential metadata role IDs beside canonical `user_id`

The retirement path is to remove consumers after every credential, recovery,
class-scope, and display path resolves from `User + Seat + Class`.
