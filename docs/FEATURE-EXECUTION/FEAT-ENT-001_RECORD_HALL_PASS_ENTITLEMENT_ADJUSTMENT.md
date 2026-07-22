# FEAT-ENT-001: Record Hall-Pass Entitlement Adjustment

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---:|---|---|---|
| FEAT-ENT-001 | 1.0 | 2026-07-22 | N/A | Normative |

---

## I. Purpose

`FEAT-ENT-001` is the lawful mutation boundary for teacher/admin hall-pass entitlement adjustments that are not PROD hall-pass consumption events.

This FEAT exists because hall-pass availability is derived from append-only entitlement facts. No route, template, service, or test may set a hall-pass balance directly.

---

## II. Authority Boundary

This FEAT owns only the entitlement adjustment facts:

- granting additional hall-pass entitlement quantity;
- removing available hall-pass entitlement quantity by appending REVOCATION rows against unconsumed grant correlations.

It does not own:

- hall-pass request approval;
- hall-pass consumption into `hall_pass_logs`;
- leave/return attendance rows;
- PROD productivity state;
- obligation satisfaction or rent-derived entitlement grant policy.

PROD consumption remains governed by `FEAT-PROD-002`, which consumes an available entitlement grant and records the approved hall-pass business fact in `hall_pass_logs`.

---

## III. Lawful Operations

### Add Hall Passes

Adding hall passes creates new positive entitlement grant events.

Rules:

- quantity must be positive;
- target `seat_id` must be scoped to the teacher's active `class_id`;
- the resulting balance remains a derived projection over entitlement events;
- no seat-level hall-pass counter may be written.

### Remove Hall Passes

Removing hall passes appends negative REVOCATION events against existing unconsumed grant correlations.

Rules:

- quantity must be positive;
- removal must fail if requested quantity exceeds the current derived available balance;
- each REVOCATION row must reuse the grant `correlation_id` it reverses;
- removal must not create uncorrelated negative rows;
- removal must not mutate or delete prior entitlement events.

---

## IV. Prohibited Patterns

The following are prohibited:

- setting hall-pass balance to an arbitrary number;
- calculating a delta from desired balance and writing that delta;
- writing negative entitlement rows without an existing unconsumed grant correlation;
- using `student.hall_passes` or any seat-level hall-pass counter;
- using PROD `hall_pass_logs` as the entitlement balance source.

---

## V. Template Contract

Teacher-facing templates may display the derived hall-pass balance.

Mutation controls must expose only:

- Add hall passes;
- Remove hall passes.

They must not expose:

- Set balance;
- Update number;
- Direct balance edit.

---

## VI. Definition of Done

This FEAT is implemented when:

- admin student-detail hall-pass controls call add/remove entitlement operations only;
- admin roster bulk hall-pass controls call add/remove entitlement operations only;
- no runtime route or template can set a derived hall-pass balance directly;
- removal appends REVOCATION rows tied to existing grant `correlation_id` values;
- targeted tests prove correlation-preserving removal.
