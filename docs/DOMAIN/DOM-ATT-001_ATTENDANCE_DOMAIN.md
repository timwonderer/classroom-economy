# DOM-ATT-001: Attendance Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-ATT-001 | 2.0 | 2026-06-13 | 1.2 | Normative |

## I. Purpose

Define the Attendance domain as the source of attendance facts, session history, and hall-pass event history.

## II. Scope

This domain owns attendance event persistence, per-seat attendance gate state,
and hall-pass execution history.

This domain does not own:

- payroll amounts or wage policy
- hall-pass configuration (owned by Class Configuration)
- rent-derived hall-pass entitlement quota (owned by Obligations)
- balances or financial state

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`

## V. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `attendance_sessions`
- `hall_pass_logs`
- `seat_attendance_state`

It may read configuration supplied by the Class Configuration domain, but it does not
own payroll, balances, or eligibility policy.

### Legacy Table Note

The legacy v1 runtime table `tap_events` has been retired. `attendance_sessions`
is the canonical and physical attendance fact table in the active v2 runtime and
migration chain.

## VI. Owned Tables

**Event Log Meta-Pattern:** The Attendance domain maintains an "Attendance Event Log" which is conceptually a union of typed event streams (e.g., `attendance_sessions` and `hall_pass_logs`). Both are append-only and lifecycle-driven, establishing a complete immutable timeline of attendance facts.

### 1. `attendance_sessions`

Append-style work-state events and attendance timeline truth. Each row records a
single tap-in or tap-out event for a seat within a class.

### 2. `hall_pass_logs`

Runtime hall-pass history and leave/return event state. Each row is the lifecycle
record for one hall-pass event from request through return.

### 3. `seat_attendance_state`

Per-seat mutable attendance gate state. Records whether a seat is tap-enabled and
whether the seat has been marked done-for-day. One row per seat. This is a
denormalized gate-evaluation record; `attendance_sessions` remains the authoritative timeline.

## VII. Schema Contract

### 1. `attendance_sessions`

Key fields:

- `id`
- `seat_id` — FK to `seats`
- `class_id` — FK to `classes`; canonical isolation boundary
- `status` — `active` | `inactive`
- `timestamp` — UTC
- `reason_code` — enumerated: `DAILY_LIMIT` | `AUTO_SWITCH` | `MANUAL`

Rules:

- `attendance_sessions` is append-only. Rows are never edited after creation.
- Completed session history must not be silently erased. Correction is via a new
  compensating event, not deletion or overwrite.
- Every attendance session is scoped to exactly one class (`class_id`).
- **INV-ATT-010 — Single active session per seat**: At most one active session may exist without a corresponding inactive event for a given `seat_id`. Enforcement MUST be atomic at write time. The system MUST guarantee that no two active sessions can be created concurrently for the same seat.

### 2. `hall_pass_logs`

Key fields:

- `id`
- `seat_id` — FK to `seats` (the student seat holding the pass)
- `class_id` — FK to `classes`; canonical isolation boundary
- `reason` — `bathroom` | `water` | `office` | `nurse` | `counselor`
- `status` — `pending` | `approved` | `rejected` | `left` | `returned`
- `request_time` — UTC
- `decision_time` — UTC; when the teacher approved or rejected
- `left_time` — UTC; when the student physically left
- `return_time` — UTC; when the student returned

Rules:

- Status transitions are one-directional and must follow the defined state machine:
  `pending → approved → left → returned` (or `pending → rejected`).
- Completed hall-pass history must not be silently erased.
- Hall-pass settings (queue limits, pass types) are owned by Class Configuration;
  this table records execution facts only.

### 3. `seat_attendance_state`

Key fields:

- `id`
- `seat_id` — FK to `seats` (UNIQUE; one record per seat)
- `class_id` — FK to `classes`; canonical isolation boundary
- `tap_enabled` — boolean; teacher-controlled toggle; false prevents the seat from
  accumulating tap time for payroll
- `done_for_day_date` — Pacific-local date; when set, the seat is locked from tapping
  until Pacific midnight of that date
- `created_at` / `updated_at`

Rules:

- One row per seat. Created when the seat is first enrolled in the class.
- `done_for_day_date` is a mutable denormalization of the most recent done-for-day
  session event. It exists for O(1) lock evaluation. If it diverges from
  `attendance_sessions`, `attendance_sessions` is authoritative.
- `done_for_day_date` is evaluated relative to the class timezone, not UTC midnight.
- `tap_enabled` is set by teacher action only. Students cannot modify this field. Disabling `tap_enabled` does not affect existing active sessions. It only gates future tap-in events.
- This table does not store balances, earnings, rent-linked pass quotas, or any
  financial state. Those are owned by their respective domains.

## VIII. Constraints

- Attendance returns facts only.
- Attendance does not compute wage policy, payroll amounts, affordability, or solvency.
- Completed session and hall-pass history must not be silently erased.
- Anchors, limits, and policy inputs are supplied from outside this domain.
- Rent-derived hall-pass entitlement quota is owned by the Obligations domain, not
  here. Attendance records the consumption event (a `hall_pass_log` row); Obligations
  tracks remaining quota.

## IX. Derived / Cross-Domain Rules

- Payroll FEAT consumes attendance facts from `attendance_sessions` and requests money
  movement from Ledger. Attendance does not initiate that flow.
- Hall-pass quota from rent obligations is tracked by the Obligations domain.
  Attendance reads the remaining quota when evaluating a pass request but does not
  own or mutate it. The consumption trigger event for rent-linked hall passes is the `approve_pass` transition. Attendance emits this event, but Obligations decides how it is applied.
- Hall-pass settings (queue limits, simultaneous limits, pass types) are owned by
  Class Configuration even though hall-pass execution history is owned here.

## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000` and `DOM-CORE-002`.
