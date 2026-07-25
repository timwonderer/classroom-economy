# FEAT-PROD-003: Record Payroll Event

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PROD-003 | 1.0 | 2026-07-19 | N/A | Normative |

---

## I. Purpose

This FEAT records payroll business events for the Productivity and Payroll domain and coordinates the corresponding Ledger posting.

It writes to `payroll_event` only.

The FEAT covers:

- attendance-based payroll credits
- teacher-entered manual credits
- reversals of either of the above

This FEAT uses `CanonicalContext` for live request authority and the canonical temporal resolver for recording and presenting class-local timestamps.

---

## II. Execution Context

### 1. Required Inputs

- `ctx`: `CanonicalContext`
- `target_seat_id`: seat receiving the credit or reversal effect
- `idempotency_key`: replay guard
- `policy_version_id`: the payroll policy version in effect
- `payroll_run_type`: `payroll`, `manual_credit`, or `reversal`
- `correlation_id`: business-to-ledger linkage
- `summary_json`: human-readable and structured metadata
- `reference_time_utc`: optional explicit timestamp for deterministic evaluation

### 2. Canonical Authority

- `ctx.class_id` provides the class boundary
- `ctx.seat_id` provides the lawful actor seat for live requests
- `ctx.actor_role` determines whether the action is teacher-driven or system-driven

The FEAT MUST not infer monetary authority from the target seat.

---

## III. Canonical Write

### `record_payroll_event(...)`

This is the only lawful mutation path for `payroll_event`.

Typical use cases:

- automatic payroll run based on attendance
- teacher-entered manual credit
- reversal of a prior payroll or manual credit event

Rules:

- MUST require `class_id`, `actor_seat_id`, `target_seat_id`, `correlation_id`, `idempotency_key`, `policy_version_id`, `mechanism`, `payroll_run_type`, `recorded_at`, and `summary_json`
- MUST be append-only
- MUST set `payroll_run_type` to `payroll`, `manual_credit`, or `reversal`
- MUST use the original event's `correlation_id` when writing a reversal
- MUST not store the payroll amount on the domain row
- MUST not store payroll period boundaries as persisted fields
- MUST coordinate the ledger post using the same `correlation_id`

Execution steps:

1. Resolve `CanonicalContext` and confirm the actor is lawful for the class.
2. Resolve `CLE` with `canonical_temporal_resolver("CLE", primitive="current_time", canonical_execution_context=ctx, reference_time_utc=reference_time_utc)`.
3. Identify the target seat and the payroll policy version in effect.
4. Compute the payroll amount from authoritative productivity facts or manual credit intent.
5. Write the append-only `payroll_event` row with the immutable correlation ID.
6. Post the matching Ledger credit using the same `correlation_id`.
7. If the event is a reversal, compute and post the compensating negative Ledger amount from the original event lineage.

Failure conditions:

- missing original event for reversal
- missing policy version
- missing target seat or class boundary
- attempt to write a payroll amount directly onto the domain row

### `record_payroll_reversal(...)`

This is a specialized pathway that writes a compensating `payroll_event` row and coordinates the matching Ledger reversal.

Rules:

- MUST create a new `payroll_event` row with `payroll_run_type = reversal`
- MUST reuse the original event's `correlation_id`
- MUST compute the compensating amount from the original event lineage
- MUST post the matching Ledger movement as the negative of the original amount
- MUST not mutate the original payroll row

---

## IV. Temporal Rules

- Payroll event timestamps MUST be recorded in UTC.
- Payroll event timestamps MUST be displayed in class canonical time.
- Payroll period boundaries are derived from the ordered sequence of `payroll_event` rows.
- `manual_credit` and `reversal` rows do not advance the payroll boundary chain.

---

## V. Invariants

1. Payroll writes are append-only.
2. Payroll amount is derived and posted to Ledger, not stored on the domain row.
3. Reversal is a compensating event with the same correlation ID as the original.
4. The FEAT must fail closed if the original event cannot be established.

---

## VI. Dependencies

- `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
- `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `app/services/context_resolver.py`
- `docs/SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md`
- `app/utils/canonical_temporal_resolver.py`
