# FEAT-PROD-001: Record Attendance Session

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PROD-001 | 1.0 | 2026-07-19 | N/A | Normative |

---

## I. Purpose

This FEAT records lawful attendance-session rows for the Productivity and Payroll domain.

It writes to `attendance_sessions` only.

This FEAT uses `CanonicalContext` for live request authority and `resolve_canonical_temporal_evaluation("CLE", ...)` from `app/utils/temporal.py` for class-local time evaluation.

---

## II. Execution Context

### 1. Required Inputs

- `ctx`: `CanonicalContext`
- `idempotency_key`: when the caller requires replay protection for the write
- `reference_time_utc`: optional explicit timestamp for deterministic evaluation

### 2. Canonical Authority

- `ctx.class_id` provides the class boundary
- `ctx.seat_id` provides the actor/target seat for live requests
- `ctx.actor_role` determines whether the action is a student or teacher attendance action

The FEAT MUST NOT infer class or seat authority from any legacy identity source.

---

## III. Canonical Write

### `record_attendance_session(...)`

This is the only lawful mutation path for `attendance_sessions`.

Typical use cases:

- student taps in
- student taps out
- student is marked out for a hall pass
- student is marked done for the day
- student is marked out due to the daily limit

Rules:

- MUST require `class_id` and `seat_id`
- MUST use class-local canonical time for the timestamp
- MUST set `status` to `active` or `inactive`
- MUST set `reason_code` when writing an inactive row
- MUST set `hall_pass_id` when `reason_code = hall_pass`
- MUST not store current attendance state
- MUST not store accumulated daily minutes
- MUST not store hall-pass destination
- MUST not store payroll amount

Execution steps:

1. Resolve `CanonicalContext` and confirm the request is lawful for the seat and class.
2. Resolve `CLE` with `resolve_canonical_temporal_evaluation("CLE", canonical_execution_context=ctx, reference_time_utc=reference_time_utc)`.
3. Derive the canonical request timestamp in class-local time and normalize it to UTC for persistence.
4. Determine whether the write is an active or inactive attendance row.
5. If the row is hall-pass-related, require the correlated `hall_pass_id`.
6. Persist the append-only row to `attendance_sessions`.

Failure conditions:

- missing class context
- missing seat context
- invalid hall-pass correlation
- attempt to mutate prior attendance state instead of appending a new row

---

## IV. Temporal Rules

- Attendance comparisons MUST use the canonical temporal resolver.
- Attendance rows are recorded in UTC and displayed in class canonical time.
- Any derived attendance duration MUST be computed from the attendance timeline, not stored on the row.

---

## V. Invariants

1. Attendance writes are append-only.
2. Hall-pass attendance rows must correlate to `hall_pass_logs` via `hall_pass_id`.
3. The FEAT must fail closed if `ctx.class_id` or `ctx.seat_id` cannot be established.
4. The FEAT must not mutate hall-pass entitlement state.

---

## VI. Dependencies

- `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `app/services/context_resolver.py`
- `app/utils/temporal.py`
