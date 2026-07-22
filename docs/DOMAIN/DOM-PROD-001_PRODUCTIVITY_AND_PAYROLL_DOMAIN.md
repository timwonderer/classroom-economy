# DOM-PROD-001: Productivity and Payroll Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-PROD-001 | 1.0 | 2026-07-18 | 3.0 | Constitutional |

---

## I. Purpose

This document defines the Productivity and Payroll domain as the sovereign of productivity facts, hall-pass execution history, payroll event records, and the business-side facts that justify payroll settlement.

It is the canonical authority for:

- work and participation timing facts
- payroll event records and settlement history
- hall-pass execution history

This domain provides the business meaning that precedes monetary posting. It does not own monetary truth itself.

---

## II. Scope

This domain governs the runtime persistence and authority of:

- productivity session facts
- hall-pass execution facts
- payroll event records and payroll-run lineage

This domain does not own:

- ledger balance truth
- ledger posting authority
- wage policy directives
- class configuration
- rent-derived entitlement quotas
- store entitlement state
- global identity

Class-level tap enablement is owned by Class Configuration and stored on the `classes` table, not inside this domain.

Productivity and Payroll is a business authority, not a monetary authority. It decides what happened and whether that business event may drive a payroll settlement workflow. Ledger decides what money moved.

---

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

---

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

---

## V. Canonical Business Authority

The Productivity and Payroll domain is the sole business authority responsible for:

- productivity participation facts
- hall-pass execution facts
- payroll events
- payroll eligibility and settlement intent derived from productivity facts
- business-side reversal authorization for payroll-originated monetary facts

Consumers SHALL NOT:

- reconstruct payroll truth from ledger rows alone
- derive productivity state from unrelated domains
- mutate productivity or payroll persistence directly
- reinterpret payroll business meaning outside this domain

Consumers SHALL instead invoke the canonical business operations owned by this domain.

---

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `attendance_sessions`
- `hall_pass_logs`
- `payroll_event`

`DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md` is authoritative for the exact runtime table list. This domain owns the tables listed there that are assigned to it. `payroll_event` is the canonical payroll event table owned by this domain.

The legacy v1 runtime table `tap_events` has been retired. `attendance_sessions` is the canonical productivity fact table in the active v2 runtime and migration chain.

---

## VII. Owned Tables

### 1. `attendance_sessions`

Append-only productivity timeline facts. Each row records a single tap-in or tap-out event for a seat within a class.

Current attendance state, accumulated daily minutes, and hall-pass elapsed time are derived from this timeline and are not stored on this table.

Once written, an `attendance_sessions` row is permanent. It SHALL NOT be edited, deleted, soft-deleted, marked as deleted, hidden from payroll, or corrected in place.

Inactive attendance records must include a reason:

- `hall_pass`
- `done_for_day`
- `daily_limit`

If the inactive reason is `hall_pass`, the row must carry the hall-pass identifier that correlates to `hall_pass_logs`.

This table does not store hall-pass destination or payroll amount.

### 2. `hall_pass_logs`

Canonical immutable table for issued hall passes. Each row records the approved hall-pass and represents consumption of a single hall pass.

Fields:

- `id`
- `timestamp` — request time
- `class_id`
- `requested_by_seat_id`
- `approved_by_seat_id`
- `correlation_id` — linkage to the consumed hall-pass entitlement grant; if the pass was purchased from the Store domain, the same correlation ID is also carried by the upstream ledger entry
- `hall_pass_id` — external hall-pass identifier
- `destination` — preset by teacher

This table does not own actual exit time or return time. Those are logged by `attendance_sessions`.

The presence of a row indicates the pass is approved and consumed.

Hall-pass approval consumes an entitlement. The Entitlement domain records granting or purchasing hall pass.

### 3. `payroll_events`

Canonical append-only table for positive ledger credit events.

This domain must maintain the authoritative payroll event surface that explains why a payroll FEAT exists, what participation was settled, and what business event was approved for monetary posting.

The payroll event is the human-meaningful authority for:

- what productivity window was settled
- which seats were included
- what payroll batch or run occurred
- whether a payroll-originated monetary fact may later be reversed

---

## VIII. Canonical Write Operations

The only lawful write operations for this domain are the following.

### 1. `record_attendance_session(...)`

Owned by `FEAT-PROD-001`.

Writes a new row to `attendance_sessions`.

Use cases:

- student taps in
- student taps out
- student is marked out for a hall pass
- student is marked done for the day
- student is marked out due to the daily limit

Rules:

- MUST be append-only
- MUST treat every written attendance row as immutable and permanent
- MUST require `class_id` and `seat_id`
- MUST set `status` to `active` or `inactive`
- MUST set `reason_code` when writing an inactive row
- MUST set `hall_pass_id` when `reason_code = hall_pass`
- MUST not store current attendance state, accumulated daily minutes, hall-pass destination, or payroll amount
- MUST not infer or mutate hall-pass entitlement state
- MUST NOT provide delete, soft-delete, mark-deleted, edit, or correction-in-place behavior for attendance rows
- MUST NOT correct payroll outcomes by mutating attendance history

If a teacher believes an attendance row produced an incorrect payroll outcome, the correction path is a payroll reversal through `FEAT-PROD-003`, not mutation of the attendance row.

### 2. `record_hall_pass_log(...)`

Owned by `FEAT-PROD-002`.

Writes or updates the canonical approved hall-pass row in `hall_pass_logs`.

Use cases:

- teacher issues a hall pass
- teacher approves a hall pass request
- approved hall pass is recorded for entitlement consumption

Rules:

- MUST require `class_id`, `requested_by_seat_id`, `approved_by_seat_id`, `hall_pass_id`, and `destination`
- MUST read class-scoped `hall_pass_settings` before granting the pass
- MUST fail closed when class-scoped hall-pass settings prohibit the requested destination or limit
- MUST set `correlation_id` to the consumed entitlement grant's `correlation_id`
- MUST be the authoritative approved hall-pass instruction
- MUST not record exit time or return time
- MUST not record hall-pass elapsed time
- MUST not record payroll amount
- MUST not be used to derive current attendance state

### 3. `record_payroll_event(...)`

Owned by `FEAT-PROD-003`.

Writes a new row to `payroll_event`.

Use cases:

- automatic payroll run based on attendance
- teacher-entered manual credit
- reversal of a prior payroll or manual credit event

Rules:

- MUST be append-only
- MUST require `class_id`, `actor_seat_id`, `target_seat_id`, `correlation_id`, `idempotency_key`, `policy_version_id`, `mechanism`, `payroll_event_type`, `recorded_at`, and `summary_json`
- MUST set `payroll_event_type` to `payroll`, `manual_credit`, or `reversal`
- MUST derive payroll amount from authoritative productivity facts or manual credit intent, but MUST not store the amount on the table
- MUST use the same `correlation_id` as the original event when writing a reversal
- MUST write the compensating amount to Ledger with the same correlation linkage
- MUST not store payroll period boundaries as persisted fields

### 4. `record_payroll_reversal(...)`

Owned by `FEAT-PROD-003`.

Writes a compensating `payroll_event` row and coordinates the matching Ledger reversal.

Use cases:

- teacher reverses a payroll credit
- teacher reverses a manual credit

Rules:

- MUST create a new `payroll_event` row with `payroll_event_type = reversal`
- MUST reuse the original event's `correlation_id`
- MUST not mutate the original payroll row
- MUST calculate the compensating ledger amount as the negative of the original ledger amount
- MUST fail closed if the original event cannot be established

---

## IX. State Classification

| State | Classification | Rationale |
| :--- | :--- | :--- |
| **Productivity Session** | Authoritative Event | Immutable record of a participation interval. |
| **Hall Pass Log** | Authoritative Event | Immutable record of an approved hall-pass instruction. |
| **Payroll Event** | Authoritative Event / Record | Canonical business explanation of a payroll settlement run. |
| **Payroll Eligibility** | Derived State | Determined from productivity facts, class policy, and current context. |
| **Payroll Reversal Permission** | Derived / Authority State | Determined by this domain before any payroll-originated monetary reversal request is allowed. |

---

## X. Invariants

- **INV-PROD-001: Seat-Scoped Isolation**. All productivity and payroll state shall be anchored to a `seat_id` and `class_id`. No cross-class leakage is permitted.
- **INV-PROD-002: Append-Only Facts**. Productivity sessions and payroll events must be recorded append-only. Corrections require new events or records, not mutation of the original fact.
- **INV-PROD-002A: Attendance Immutability**. Attendance session rows are forever facts after insertion. They may not be deleted, soft-deleted, edited, marked as deleted, excluded from payroll by mutation, or otherwise corrected in place.
- **INV-PROD-003: Business Truth Ownership**. This domain owns the business truth for productivity-based earning and payroll settlement. Ledger does not own payroll meaning.
- **INV-PROD-004: Payroll Settlement Requires Authority**. A payroll monetary posting may only occur after this domain has established that the underlying productivity record and payroll event authorize it.
- **INV-PROD-005: No Hidden Payroll State**. Payroll status, payroll eligibility, and reversal permission must be explicit domain state or derived from authoritative domain records. They may not be reconstructed from ledger rows alone.
- **INV-PROD-006: Class-Time Evaluation**. Productivity windows and payroll eligibility MUST use class-local temporal evaluation.
- **INV-PROD-007: Hall-Pass History Preservation**. Completed hall-pass history must not be silently erased.
- **INV-PROD-008: No Financial Truth**. This domain does not compute balances, spendable funds, or monetary reconciliation.

---

## XI. Schema Contract

### 1. `attendance_sessions`

Key fields:

- `id`
- `actor_seat_id` — FK to `seats`
- `target_seat_id` - FK to `seats`
- `mechanism` - `self` | `teacher` | `system`
- `target_user_id` - FK to `users`
- `class_id` — FK to `classes`; canonical isolation boundary
- `status` — `active` | `inactive`
- `timestamp` — UTC
- `reason_code` — enumerated: `hall_pass` | `done_for_day` | `start_work`
- `hall_pass_id` — FK to `hall_pass_logs`, required when `reason_code = hall_pass`


Rules:

- `attendance_sessions` is append-only.
- Rows are never edited after creation.
- Rows are never deleted or marked as deleted after creation.
- There is no canonical attendance-row deletion, soft-deletion, or correction API.
- Teacher correction of an already-paid attendance outcome is performed by reversing the affected payroll event, not by changing attendance history.
- Every session is scoped to exactly one `class_id`.
- At most one active session may exist for a given `target_user_id` without a corresponding inactive event.
- The platform SHALL execute the following state transition automatically:
    - Starting an active session SHALL automatically generate an `inactive` row for any `active` session under the same `target_user_id` with the `reason_code = done_for_day`
    - Any `active` sessions SHALL automatically terminate by end of day at canonical class timezone with the `reason_code = done_for_day`. Timestamp for the `inactive` entry SHALL be recorded using the same date as the originating `active` entry.
    - An `inactive` state with `reason_code = hall_pass` exist without a corresponding `active` row (known as "hanging hall pass") SHALL automatically generate an `active` row and an `inactive` + `reason_code = done_for_day` using the same timestamp when the following occurs: the day ends in the canonical class timezone OR when a new `active` session is created under the same `user_id` but with different `class_id`, whichever occurs first.
    - An `active` session reaching or exceeding the set daily limit SHALL generate an `inactive` row with `reason_code = done_for_day`. If the session exceeds the set limit, the closing row shall correct the timestamp so the accumulated time is equal to the set limit.
- System-generated transitions MUST use the canonical teacher seat for the explicit class_id, resolved through the Identity domain’s canonical seat-resolution operation.
- Current attendance state and accumulated daily minutes are derived from this timeline and are not stored here. 
- Hall-pass destination and hall-pass elapsed time are derived elsewhere and are not stored here.
- Payroll amount is derived from this table but is not stored here.

### 2. `hall_pass_logs`

Key fields:

- `id`
- `timestamp` — request time, UTC
- `class_id` — FK to `classes`
- `requested_by_seat_id` — FK to `seats`
- `approved_by_seat_id` — FK to `seats`
- `correlation_id` — internal domain linkage
- `hall_pass_id` — external hall-pass identifier
- `destination` — preset by teacher

Rules:

- This table is immutable, append-only. 
- A row gets created when the pass is approved.
- The presence of a row indicates the pass is approved and consumed.
- Actual exit time and return time are not stored here.
- `hall_pass_logs` is the authoritative hall pass consumption record. Stores and Entitlement Domain SHALL store hall pass grant or purchase.
- Remaining hall pass count is a derived value, not stored.

### 3. `payroll_event`

Key fields:

- `id`
- `class_id` — FK to `classes`; canonical isolation boundary
- `actor_seat_id` — FK to `seats`; the seat that initiated or authorized the payroll event
- `target_seat_id` — FK to `seats`; the seat whose productivity settlement or reversal is affected
- `correlation_id` — workflow correlation identifier linking payroll business and ledger facts; reversals reuse the original event's correlation_id
- `idempotency_key` — unique payroll-run replay guard
- `policy_version_id` — frozen policy version reference for the payroll policy in effect at record time
- `mechanism` — `TEACHER` | `SYSTEM`
- `payroll_event_type` — `payroll` | `manual_credit` | `reversal`
- `recorded_at` — UTC; display in class canonical time
- `summary_json` — structured payroll summary and settlement metadata

Rules:

- `payroll_event` is append-only.
- Each row records one payroll business event for one class.
- Each row records one payroll business event for one affected seat.
- `payroll` events are the only boundary-bearing event type.
- The payroll window for a `payroll` event is derived from the previous `payroll` event timestamp through the current event timestamp.
- `manual_credit` and `reversal` events do not participate in payroll-window boundary derivation.
- `reversal` events must carry the same `correlation_id` as the original event they reverse.
- `policy_version_id` is immutable and must identify the payroll policy version used to evaluate the event.
- The row must identify the productivity window and settlement intent that authorized any downstream ledger write.
- The row must not duplicate ledger monetary truth beyond what is necessary for business provenance.
- `payroll_event_type` carries the event semantics, so no separate lifecycle `status` column is permitted on the canonical table.

---

## XII. Cross-Domain Rules

- **Payroll FEAT ownership**: The payroll FEAT is a coordinator, not the authority over payroll meaning. It consumes productivity facts from this domain and posts monetary facts through Ledger.
- **Ledger coordination**: All payroll monetary effects must go through `FEAT-LED-000` and `FEAT-LED-001`.
- **Class Configuration coordination**: Wage rate, frequency, and payroll policy inputs are owned by Class Configuration.
- **Hall-pass settings coordination**: `hall_pass_settings` is owned and mutated by Class Configuration. `FEAT-PROD-002` reads it before granting a hall pass because those settings constrain whether a PROD hall-pass event may be written.
- **Obligations coordination**: Hall-pass entitlement quotas remain owned by Obligations, and fine/debit manual deductions belong there rather than in `DOM-PROD`.
- **Store coordination**: Store-owned entitlements and redemption state remain separate from productivity and payroll history.
- **Reversal coordination**: Reversal of a payroll-originated monetary fact must consult this domain's authoritative business record before the reversal may proceed.

---

## XIII. Canonical Business Surface

The long-term implementation goal of this domain is to expose a canonical business surface rather than persistence-oriented behavior.

### 1. `record_productivity_session(...)`

Records one append-only productivity session fact for a seat within a class.

Rules:

- MUST require `class_id` and `seat_id`
- MUST be append-only
- MUST not mutate prior session rows
- MUST not delete, soft-delete, mark-delete, or correct prior session rows
- MUST use class-local temporal evaluation for any boundary-sensitive values

### 2. `record_hall_pass_event(...)`

Records one mutable hall-pass issuance fact.

Rules:

- MUST require `class_id` and `seat_id`
- MUST require a `hall_pass_id`
- MUST capture request, approval, and destination information
- MUST not store exit time or return time
- MUST not alter the approved hall-pass row after issuance except through lawful domain mutation

### 3. `record_payroll_event(...)`

Records one append-only payroll business event.

Rules:

- MUST require `class_id`, `actor_seat_id`, `target_seat_id`, `correlation_id`, `idempotency_key`, and `policy_version_id`
- MUST record `payroll_event_type`
- MUST treat `payroll` as the only boundary-bearing event type
- MUST preserve `manual_credit` and `reversal` as non-boundary event types
- MUST use the original event's `correlation_id` for reversals
- MUST not mutate prior payroll event rows

### 4. `get_payroll_event(...)`

Returns the authoritative payroll event record or records for a given class/seat scope.

Rules:

- MUST be read-only
- MUST not derive payroll truth from ledger rows
- MUST return the source payroll event lineage needed by FEATs and presentation surfaces

### 5. `get_payroll_window(...)`

Derives the payroll settlement window for a given payroll event from the previous `payroll` event timestamp through the current `payroll` event timestamp.

Rules:

- MUST ignore `manual_credit` and `reversal` events for boundary derivation
- MUST return the lower/upper productivity boundary used for payroll settlement
- MUST be read-only and deterministic

### 6. `authorize_payroll_reversal(...)`

Determines whether a payroll-originated monetary fact may be reversed.

Rules:

- MUST consult the authoritative payroll event record
- MUST fail closed if the relevant event cannot be established
- MUST not authorize based on ledger rows alone

The exact implementation may evolve, but business consumers SHALL interact with canonical domain operations rather than directly manipulating tables or reconstructing derived business state.

---

## XIV. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
4. Maintain consistency with `DOM-CORE-002`.
