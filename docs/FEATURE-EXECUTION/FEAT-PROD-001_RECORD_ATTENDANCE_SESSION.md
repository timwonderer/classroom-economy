# FEAT-PROD-001: Record Attendance Session

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PROD-001 | 1.1 | 2026-07-20 | 1.0 | Normative |

---

## I. Purpose

This FEAT is the sole lawful mutation path for `attendance_sessions`.

It records attendance-session rows for the Productivity and Payroll domain and
replaces any other FEAT or route path that would otherwise write to that table.

This FEAT uses `CanonicalContext` for live request authority and `canonical_temporal_resolver("CLE", primitive="current_time", ...)` from `app/utils/canonical_temporal_resolver.py` for class-local time evaluation.

---

## II. Execution Context

### 1. Required Inputs

- `ctx`: `CanonicalContext`
- `idempotency_key`: when the caller requires replay protection for the write
- `reference_time_utc`: optional explicit timestamp for deterministic evaluation
- `actor_seat_id`: the seat performing the action
- `target_seat_id`: the seat whose attendance state is being recorded
- `target_user_id`: the user bound to the target seat
- `mechanism`: `self`, `teacher`, or `system`

### 2. Canonical Authority

- `ctx.class_id` provides the class boundary
- `ctx.seat_id` provides the actor/target seat for live requests
- `ctx.actor_role` determines whether the action is a student or teacher attendance action

The FEAT MUST fail closed if `ctx.class_id` or `ctx.seat_id` cannot be established.
The FEAT MUST NOT infer authority from legacy identity sources.

The FEAT MUST NOT infer class or seat authority from any legacy identity source.

---

## III. Canonical Write

### `record_attendance_session(...)`

This is the only lawful mutation path for `attendance_sessions`.

Canonical business actions:

- start work
- return from hall pass
- leave for hall pass
- end of day
- automatic session closure when a new active session opens
- automatic session closure at the time limit
- automatic session closure at end of day

Rules:

- MUST require `class_id` and `seat_id`
- MUST treat every written attendance row as immutable and permanent
- MUST require `actor_seat_id`, `target_seat_id`, `target_user_id`, and `mechanism`
- MUST use class-local canonical time for the timestamp
- MUST set `status` to `active` or `inactive`
- MUST set `reason_code` when writing an `inactive` row
- MUST set `hall_pass_id` when `reason_code = hall_pass`
- MUST set `mechanism` to `self`, `teacher`, or `system`
- MUST set `actor_seat_id` to the initiating seat
- MUST set `target_seat_id` to the seat whose attendance state changes
- MUST set `target_user_id` to the user bound to `target_seat_id`
- MUST write `active` with `reason_code = start_work` for start work and hall-pass return
- MUST write `inactive` with `reason_code = hall_pass` for leaving for hall pass
- MUST write `inactive` with `reason_code = done_for_day` for end-of-day closure
- MUST write the automatic closure row(s) rather than mutating prior rows
- MUST append a new `active` row followed by an `inactive` `done_for_day` row when a dangling hall pass is detected at end of day
- MUST use the same timestamp for both rows in that dangling-hall-pass recovery sequence
- MUST not store current attendance state
- MUST not store accumulated daily minutes
- MUST not store hall-pass destination
- MUST not store payroll amount
- MUST NOT delete, soft-delete, edit, mark as deleted, hide, or correct an existing `attendance_sessions` row
- MUST NOT provide a teacher-facing attendance-row deletion or correction endpoint
- MUST NOT use attendance-row mutation to correct a payroll outcome

Correction rule:

- If a written attendance row contributes to an incorrect payroll result, the lawful correction path is `FEAT-PROD-003` payroll reversal.
- The original attendance row remains part of the immutable productivity timeline.

Execution steps:

1. Resolve `CanonicalContext` and confirm the request is lawful for the seat and class.
2. Resolve `CLE` with `canonical_temporal_resolver("CLE", primitive="current_time", canonical_execution_context=ctx, reference_time_utc=reference_time_utc)`.
3. Derive the canonical request timestamp in class-local time and normalize it to UTC for persistence.
4. Determine the correct canonical row shape for the requested attendance action.
5. Populate `actor_seat_id`, `target_seat_id`, `target_user_id`, and `mechanism`.
6. If the row is hall-pass-related, require `hall_pass_id` to reference the consumed entitlement instance's `entitlement_id`.
7. If end-of-day cleanup finds a dangling hall pass, emit `active/start_work` and then `inactive/done_for_day` at the same timestamp.
8. Persist the append-only row or row sequence to `attendance_sessions`.

Failure conditions:

- missing class context
- missing seat context
- invalid hall-pass correlation
- attempt to mutate prior attendance state instead of appending a new row
- attempt to delete, soft-delete, mark-delete, or correct an existing attendance row
- attempt to write `attendance_sessions` outside this FEAT

---

## IV. Temporal Rules

- Attendance comparisons MUST use the canonical temporal resolver.
- Attendance rows are recorded in UTC and displayed in class canonical time.
- Any derived attendance duration MUST be computed from the attendance timeline, not stored on the row.
- End-of-day cleanup MUST respect the current class-local day boundary.

---

## V. Write Authority

`FEAT-PROD-001` is the exclusive writer for `attendance_sessions`.

No other FEAT, route, background job, service, or migration logic may write to
`attendance_sessions` directly.

All other attendance-related behavior MUST delegate to this FEAT.

---

## VI. Invariants

1. Attendance writes are append-only.
2. Attendance rows are immutable and permanent after insertion.
3. There is no delete, soft-delete, mark-deleted, or correction-in-place attendance path.
4. Payroll correction is handled through payroll reversal, not attendance mutation.
5. Hall-pass attendance rows must carry the same consumed entitlement instance `entitlement_id` recorded as `hall_pass_logs.hall_pass_id`.
6. The FEAT must fail closed if `ctx.class_id` or `ctx.seat_id` cannot be established.
7. The FEAT must not mutate hall-pass entitlement state.
8. The FEAT must be the only writer to `attendance_sessions`.

---

## VII. Dependencies

- `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `app/services/context_resolver.py`
- `docs/SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md`
- `app/utils/canonical_temporal_resolver.py`
