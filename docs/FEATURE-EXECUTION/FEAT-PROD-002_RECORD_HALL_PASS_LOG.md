# FEAT-PROD-002: Record Hall Pass Log

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PROD-002 | 1.0 | 2026-07-19 | N/A | Normative |

---

## I. Purpose

This FEAT records approved hall-pass rows for the Productivity and Payroll domain.

It writes to `hall_pass_logs` and reads class-configuration-owned `hall_pass_settings` to determine whether the pass may be granted.

The row represents the approved hall-pass instruction and the entitlement-consumption event at the same time.

This FEAT uses `CanonicalContext` for live request authority and the canonical temporal resolver for request-time stamping.

---

## II. Execution Context

### 1. Required Inputs

- `ctx`: `CanonicalContext`
- `hall_pass_id`: external hall-pass identifier
- `destination`: teacher-prescribed hall-pass destination
- `requested_by_seat_id`: seat requesting the pass
- `approved_by_seat_id`: seat approving the pass
- `correlation_id`: linkage to the entitlement consumption event
- `reference_time_utc`: optional explicit timestamp for deterministic evaluation

### 2. Canonical Authority

- `ctx.class_id` provides the class boundary
- `ctx.seat_id` provides the approving seat for live teacher actions
- `ctx.actor_role` MUST be teacher or another lawful approving authority

The FEAT MUST not infer approval authority from the destination or hall-pass payload.

---

## III. Canonical Write

### `record_hall_pass_log(...)`

This is the only lawful mutation path for `hall_pass_logs`.

Typical use cases:

- teacher approves a hall pass request
- teacher issues a hall pass directly

Rules:

- MUST require `class_id`, `requested_by_seat_id`, `approved_by_seat_id`, `hall_pass_id`, `destination`, and `correlation_id`
- MUST evaluate class-scoped `hall_pass_settings` before writing the approved pass
- MUST NOT mutate `hall_pass_settings`; mutation of that table belongs to Class Configuration
- MUST fail closed if settings disable the requested destination
- MUST fail closed if queue or simultaneous limits are reached
- MUST record the request timestamp in class canonical time
- MUST represent approval and entitlement consumption together
- MUST not record exit time
- MUST not record return time
- MUST not record hall-pass elapsed time
- MUST not derive attendance state from the hall-pass row

Execution steps:

1. Resolve `CanonicalContext` and confirm the approving actor is lawful for the class.
2. Resolve `CLE` with `canonical_temporal_resolver("CLE", primitive="current_time", canonical_execution_context=ctx, reference_time_utc=reference_time_utc)`.
3. Validate the requested seat, approving seat, hall-pass identifier, and destination.
4. Read Class Configuration's `hall_pass_settings` for the class and evaluate pass-type enablement plus queue/simultaneous limits.
5. Record the approved hall-pass row in `hall_pass_logs` with the shared `correlation_id`.
6. Record the same correlation in the entitlement consumption event owned by Obligations.
7. Return the approved hall-pass instruction as the lawful source for later attendance-session exit/return evidence.

Failure conditions:

- missing approval authority
- missing or duplicate hall-pass identifier
- invalid class or seat boundary
- hall-pass settings prohibit the requested pass
- queue or simultaneous limits are reached
- attempt to backfill exit or return data into the hall-pass table

---

## IV. Temporal Rules

- Hall-pass request timestamps MUST be recorded in class canonical time.
- Exit and return timing remain attendance-session concerns and are not stored here.
- Any hall-pass display or comparison logic MUST use canonical temporal evaluation.

---

## V. Invariants

1. Hall-pass approval consumes entitlement.
2. The correlation ID links the hall-pass log to the entitlement consumption event.
3. If the pass was purchased from Store, the upstream ledger entry uses the same correlation ID.
4. The FEAT must fail closed if approval authority cannot be established.
5. `hall_pass_settings` is a Class Configuration-owned input to the PROD grant decision and must be evaluated before writing `hall_pass_logs`.

---

## VI. Dependencies

- `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md`
- `app/services/context_resolver.py`
- `docs/SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md`
- `app/utils/canonical_temporal_resolver.py`
