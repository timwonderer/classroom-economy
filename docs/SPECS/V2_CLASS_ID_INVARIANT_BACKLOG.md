# V2 Class ID Invariant Backlog

> **Terminology Note:** This spec was written during the v1→v2 transition. Legacy model references (`Admin`, `StudentTeacher`, `TeacherBlock`, `get_admin_student_query`) describe v1 shadows that are migration targets. The v2 canonical identity model uses `User` (global principal) + `Seat` (class-local binding) with `class_id` as the class boundary.

**Status:** Deferred / backburner  
**Priority:** Post-launch hardening  
**Scope:** Remove class-lifecycle and membership-lifecycle semantics that conflict with the v2 class-identity model

## Problem Statement

Some remaining code and compatibility shims still imply that class scope or class membership can be described with labels such as `active`, `inactive`, `archived`, or similar lifecycle states.

That is not the v2 model.

## Canonical Invariants

- `class_id` either exists or never existed.
- `class_id` (UUID) is the canonical internal class boundary and authority key.
- `join_code` is the public ingress alias that resolves to `class_id`; it is not the internal authority boundary.
- Labels such as `block`, `period`, `section`, and `display_name` are metadata only, not identity.
- The canonical class-section metadata field is `classes.section`; legacy `block`
  naming should be retired in favor of `section`.
- Teacher-facing class naming should use `display_name` + `section`
  (for example `Honors Chemistry`, section `2`).
- A student exists in a class only if that student has a valid association with that class universe.
- Student-in-class state is limited to:
  - unclaimed
  - claimed
- Deletion from a `class_id` means erasure from that universe as if the student never existed there.
- If a student loses the last remaining class association, that student is erased from the system.

## Deferred Cleanup Targets

- Remove compatibility-only `ClassEconomy.status` semantics and any writes that imply class lifecycle state.
- Eliminate any membership code that models class participation as `active` / `inactive` / `archived` instead of existence.
- Replace cleanup and lifecycle logic that keys off labels or teacher-wide label groupings instead of surviving class associations.
- Revisit settings models and cleanup rules that still act like `teacher_id + block` is a durable ownership boundary (v1 pattern — v2 uses `class_id` as the canonical ownership boundary via `ClassEconomy`).
- Move period/block metadata onto `classes.section` and remove remaining identity-adjacent
  `block` fields or mirrors from seat and roster surfaces once compatibility paths are retired.
- Remove stale tests that still construct impossible class worlds through deprecated lifecycle fields.
- Retire `join_code`-authoritative banking and ledger scope once the V2 ledger rebuild plan lands (`class_id` is the canonical internal scope; `join_code` is a public alias only).

## Current Guardrail

- Teacher/admin write flows now fail at the request boundary unless the session carries a valid canonical class context.
- For current runtime behavior, admin writes are session-authoritative on `current_join_code` (legacy — v2 target: resolve to `class_id` as the canonical internal boundary); request-level scope alone is not sufficient.
- Test fixtures for admin writes must establish canonical class scope explicitly instead of relying on teacher-only or block-only setup.
- Class-scoped participant URLs expose UUID-encoded `seats.public_id`, not legacy numeric student IDs or role-specific public IDs. Resolution must match the signed navigation context and active `current_class_id`; it must not fall back to another seat when the participant exists in another class.

## Explicit Non-Goals For Current Launch Work

- No broad architecture rewrite during live-test blocker reduction.
- No taxonomy-wide documentation rewrite tied to this cleanup.
- No schema migration churn unless required by a validated post-launch implementation plan.

## Trigger To Resume

Resume this backlog after launch-critical validation blockers are closed and the post-port refactor lane is open, alongside:

- `docs/SPECS/V2_ADMIN_ROUTE_REFACTOR.md`
- `docs/MAP/MAP-CLASS-002_CLASS_SCOPE_NORMALIZATION_TARGET.md`
- `docs/SPECS/V2_BANKING_LEDGER_SETTLEMENT_PLAN.md`
