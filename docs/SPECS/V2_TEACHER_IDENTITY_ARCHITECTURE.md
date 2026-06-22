# Classroom Token Hub (CTH) v2 Teacher Identity Architecture

> **Terminology Note:** This spec was written during the v1→v2 transition. Legacy model references (`Admin`, `StudentTeacher`, `TeacherBlock`, `get_admin_student_query`) describe v1 shadows that are migration targets. The v2 canonical identity model uses `User` (global principal) + `Seat` (class-local binding) with `class_id` as the class boundary.

## Purpose

This document defines the canonical v2 identity model for teacher participation in CTH.

This is a pure v2 architecture document. It is not a migration tracker, it does not define dual-runtime behavior, and it does not authorize non-canonical identity fallback.

## Constitutional References

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-013_MEMBERSHIP_BY_EXISTENCE.md`
- `docs/DOMAIN/DOM-IDEN-001_IDENTITY_CLASS_BINDING_DOMAIN.md`
- `docs/SPECS/V2_STUDENT_IDENTITY_ARCHITECTURE.md`

## Core Design Principle

Teacher identity follows the same three-layer model as student identity:

- `users`: global authentication/security identity
- `seats`: class-local actor identity
- `classes`: class universe boundary

Economic and operational authority is never inferred from `user_id` alone. Scoped actions require a resolved teacher `seat_id` bound to the active `class_id`.

## Teacher Identity Layers

### Users (Teacher Principal)

Purpose: authentication, session security, recovery, and global account state.

Required role law:

- Teacher identity is a `users` row with `user_role='teacher'`.
- Teacher credentials and recovery capability are owned by `users`.
- Passkey metadata may be implemented by credential tables owned by `users.id`.
- DOB and other forbidden claim-era PII are not part of teacher identity.

Sticky context law:

- `users.last_active_class_id` is the durable context pointer.
- Context restoration resolves `class_id` first, then resolves an owned seat within that class.
- If the class no longer has an owned seat for the user, context is invalid and explicit selection is required.

### Seats (Teacher Actor)

Purpose: represent a teacher as an actor in exactly one class universe.

Rules:

- A teacher seat belongs to exactly one `class_id`.
- A teacher may own multiple seats across multiple classes.
- A class has exactly one authoritative teacher seat owner for teacher-scoped mutation surfaces.
- Teacher-scoped writes must be attributable to a teacher `seat_id`.

### Classes (Teacher Universe Anchor)

Purpose: authoritative class boundary for teacher scope.

Rules:

- Teacher dashboards, directives, and class-scoped navigation are resolved by `class_id`.
- `join_code` is entry/display alias only; it is not authority.

## Authority Rules

1. Authentication authority:
- `user_id` proves who is logged in.

2. Scoped authority:
- `seat_id` proves class-local actor authority.
- `class_id` proves universe boundary.

3. Request contract:
- Global teacher routes may use authenticated `user_id` only.
- Any class-scoped teacher operation must resolve and validate `seat_id + class_id` ownership.

4. Membership by existence:
- If a teacher seat exists for (`user_id`, `class_id`), membership exists.
- No implied membership from other tables or duplicated denormalized markers.

## Runtime Context Flow (Teacher)

1. Teacher authenticates to one `users` row.
2. Backend resolves available teacher seats for that user.
3. Backend restores active context from `users.last_active_class_id` if still valid.
4. Backend resolves the teacher-owned seat for that class (`class_id -> seats`).
5. If invalid/absent, teacher explicitly selects a class context.
6. Backend writes `current_class_id`, resolves `current_seat_id`, persists `last_active_class_id`.
7. Class-scoped surfaces operate strictly in that resolved context.

## Teacher Session Invariants

- Context restoration must reject deleted/unowned seats.
- Class switch is explicit and auditable.
- Session context must not be reconstructed from `join_code` alone.
- Any write without valid scoped context is rejected.

## Cross-Domain Binding Requirements

For teacher-initiated domain writes:

- Actor identity: teacher `seat_id`
- Scope boundary: `class_id`
- Optional UI alias: `join_code`

Domains must not accept teacher authority from `join_code` or `user_id` without seat-ownership validation.

## Forbidden Patterns

- Using `Admin` rows as architectural identity authority (v1 shadow — v2 target: `User` + teacher role).
- Treating `join_code` as backend authority boundary.
- Implicitly deriving active scope from unrelated session residue.
- Writing class-scoped state when no teacher seat is resolved.
