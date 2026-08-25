# INV-ARC-004: Cross Tenant Isolation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-004      | 1.2     | 2026-08-23    | 1.1        | Foundational    |

## I. Purpose

Define the one-tenant-per-request rule.

## II. Scope

Applies to all runtime requests and background execution paths.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`

## V. Core Rule

A single request MUST NOT:

- read across multiple `class_id` boundaries
- write across multiple `class_id` boundaries

All execution is constrained to a single tenant boundary.

### V.1 "Class scoped" means exactly one authorized `class_id`

"Class scoped" is satisfied only when the operation is bound to **exactly one**
canonical `class_id` — the single active class of the request context
(`g.canonical_context.class_id`). The following are NOT valid substitutes for the
active class and are each a P0 cross-tenant violation:

- the set of classes owned by the acting teacher
- any subset of a teacher's classes derived by filtering on
  `ClassEconomy.teacher_user_id` (e.g. `class_id.in_(get_all_classes_by_teacher(...))`)
- any collection of classes reconstructed from a shared label (see V.2)

For every class-local capability, **authorization by teacher ownership is
necessary but never sufficient.** Ownership answers "may this actor act on this
class?"; it never answers "which class is being acted upon?" The active
`class_id` must be resolved from the request context, independently of ownership,
before any read, write, render, export, aggregation, or capability decision.

Teacher-wide behavior MUST NOT be preserved for convenience, reporting,
onboarding, exports, analytics, payroll, support, or dashboard aggregation. If a
teacher operates across classes, they switch the active class per INV-ARC-010
(Explicit Context Switching); the request still executes against exactly one
`class_id`.

### V.2 Section / display name are display-only and confer no scope

`section` (block/period) and `display_name` are display metadata only
(see INV-ARC-014, No Label-Based Logic). They MUST NOT be used to resolve,
group, or enumerate classes. A single section label may map to any number of
classes owned by the same teacher; therefore:

- no scope may be derived from a section or display name
- no uniqueness may be assumed or enforced on `section` or `display_name`
- reconstructing "all classes owned by this teacher" from a shared label is a
  cross-tenant violation, identical in severity to V.1

### V.3 Sole allowed cross-class exception

The **only** sanctioned teacher-wide, cross-class behavior is the hall-pass
verification capability token used by the hall-pass verification page. That
capability may intentionally span a teacher's classes because it authorizes a
narrowly-scoped, read-only verification action rather than a class-local
operation. No other surface may reconstruct a teacher's class set. Any new
cross-class path outside this exception is invalid at this level.

## VI. Rebuild Intent

This rule exists to prevent fan-out reads, cross-tenant writes, and mixed-scope
capability decisions from reappearing in the rebuild.

## VII. Downstream Consequence

Any `DOM` or `FEAT` design that requires more than one tenant boundary inside one
request is invalid at this level.

## VIII. Amendment

Revisions must preserve one-tenant-per-request execution.
