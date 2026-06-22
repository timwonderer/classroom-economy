# MAP-CLASS-002: Class Scope Normalization Target

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| MAP-CLASS-002    | 1.0     | 2026-06-08     | ARC-OPS-014 | Informative |

---

## I. Purpose

This document records the intended long-term class scoping model for the application so current port work does not deepen patterns that will later need to be removed.

This is **not** an active implementation plan for the current port. It is a target-state architecture note and a set of guardrails for ongoing work.

---

## II. Scope

This target model applies to all class-scoped and user-associated database tables, session contexts, API parameters, and query builder logic.

---

## III. Authority Level

Informative. Subordinate to `SOP-DOC-000` and all foundational/constitutional rules.

---

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`

---

## Current Reality

The current v2 runtime still uses `join_code` as the main operational class boundary in
student, teacher, and API flows.

The schema and ORM also contain transitional duplication:

- many class-scoped tables still carry `join_code`
- some also carry `class_id`
- some teacher-wide queries still use `teacher_id` fan-out shortcuts

This is accepted for the port-completion phase and should not be reworked in-line with
launch-critical porting work.

## Target State

The long-term target is:

- `class_id` is the canonical internal class identifier for all internal references
- `join_code` is a user-facing/public code, not an internal scoping key
- `teacher_id` expresses ownership/authorization, not class-data scope

In that target state:

- internal class-scoped tables reference `class_id`
- internal reads and writes scope by `class_id`
- teacher-wide queries first resolve the teacher's active `class_id` set, then query
  downstream tables by `class_id`
- UI and typed-input flows resolve `join_code` from `class_economies` only when needed
  for display or user entry

The future banking ledger is part of this normalization target:

- account balances should be authoritative on `class_id + seat_id + account_type`
- transactions should be scoped by `class_id + seat_id`, not `join_code`
- settlement and invariant checks should anchor to normalized class and seat scope

## Scope Rules

### Canonical Keys

- `class_economies.class_id` is the internal canonical identifier for a class
- `class_economies.join_code` is the public code shown to users and typed by users

### Allowed Uses Of `join_code`

`join_code` should eventually be used only for:

1. Displaying a class code to a user
2. Accepting a user-entered class code
3. Resolving a public class code to the canonical internal `class_id`

### Disallowed Uses Of `join_code`

Once the normalization project begins, `join_code` should no longer be used as:

- the primary internal foreign key across class-scoped tables
- the runtime session scope key for internal data access
- the key used for teacher-wide fan-out reads
- a substitute for ownership or authorization checks

### Allowed Uses Of `teacher_id`

`teacher_id` should be used for:

- ownership of classes
- authorization checks
- teacher account/profile records
- resolving which classes belong to a teacher

### Disallowed Uses Of `teacher_id`

`teacher_id` should not be used as a shortcut for class-scoped data access in tables
that semantically belong to one or more classes.

For teacher-wide flows, the correct pattern is:

1. Resolve the teacher's active `class_id` set from `class_economies`
2. Query downstream class-scoped tables by `class_id`

## Query Model Target

### Single-Class Flow

1. Resolve one class scope to `class_id`
2. Query all downstream data using `class_id`
3. Join to `class_economies` only when `join_code` must be displayed

### Teacher-Wide Flow

1. Resolve all active classes for the teacher from `class_economies`
2. Collect the relevant `class_id` values
3. Query downstream class-scoped tables with `class_id IN (...)`

### Input Flow

1. User enters `join_code`
2. System resolves `join_code -> class_id` via `class_economies`
3. All subsequent internal reads and writes use `class_id`

## Session And Runtime Context Target

The eventual runtime context target is:

- internal session scope uses `current_class_id`
- `current_join_code` becomes a display/input compatibility field only if still needed

Current port work should not attempt to make this change.

## Deferred Migration Work

This normalization effort is intentionally deferred until after port completion.

The future project is expected to include:

- schema normalization across class-scoped tables
- backfill and constraint hardening for `class_id`
- removal of internal `join_code` scoping from queries
- removal of `teacher_id`-only class-data fan-out
- session/context migration from `current_join_code` to `current_class_id`
- banking ledger rewrite to `class_id + seat_id + account_type` authority
- ORM cleanup so model nullability and database nullability match
- test updates for single-class and teacher-wide scope behavior

## Guardrails During Port Completion

Until the normalization project starts:

- do not expand `teacher_id`-only scoping in new code when class scope already exists
- prefer existing v2 class-boundary behavior over partial architecture rewrites
- avoid introducing new schema churn whose only purpose is class-scope normalization
- document any new scope shortcut that would need to be revisited by the normalization
  project

## Active Runtime Guardrail

Current live-test hardening adds one immediate rule ahead of the deferred normalization project:

- admin/teacher writes must originate from an explicit canonical session class context
- `current_join_code` is currently the enforced runtime boundary for admin writes
- request-level `join_code` may help scope reads, but it does not replace canonical session context for writes

This is an interim runtime invariant, not the final target-state architecture. The eventual target remains `current_class_id`-driven internal scope.

## Decision

This architecture target is accepted, but implementation is deferred until the port is complete and can be handled as its own project.

---

## VI. Amendment

Revisions to this document must increment the version number, update the effective date, and remain consistent with foundational documentation standards.
