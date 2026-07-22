# DOM-OBL-001: Obligations Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-OBL-001 | 2.4 | 2026-07-10 | 2.3 | Constitutional |

---

## I. Purpose

This document defines the Obligations domain as the absolute sovereign of recurring seat-scoped debt, policy-driven charges, and the non-optional entitlements they unlock. It ensures deterministic execution of financial duties and prevents "hidden money bugs" through strict invariant enforcement.

## II. Scope

This domain governs the runtime execution and lifecycle of **seat-scoped obligations**, **satisfaction events**, and **entitlement event streams**.

**Obligations operates on seat-scoped economic actors, not global identities.** All runtime state is anchored to `seat_id`. Debts and perks are class-bound; they shall not follow a seat or user across different class universes.

**Obligations is the sole authority over rent cycle legality and insurance renewal legality.** When a lawful rent cycle boundary or insurance renewal boundary occurs, Obligations determines whether the boundary is valid. Obligations MAY request policy transition activation at a lawful boundary, but MUST NOT mutate policy lineage directly. Policy lineage remains owned by `DOM-CLASS-001` and governed by `DOM-ECON-003`.

This domain does not own:
- **Global Identity**: Owned by `Identity`.
- **Obligation Policy**: Owned by `Class Configuration`. Obligations is an execution domain that reads policies as directives.
- **Currency Balances**: Owned by `Ledger`.
- **Economic Policy Lineage**: Owned by `DOM-CLASS-001`. Obligations may signal a lawful boundary but does not own `policy_versions` or `policy_transitions`.

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Canonical Business Authority

The Obligations domain is the sole business authority responsible for recurring seat-scoped obligations, obligation satisfaction, entitlement lifecycle for obligation-linked entitlements, and operational boundary legality.

Consumers SHALL NOT:

- derive obligation status independently;
- derive entitlement balances independently;
- mutate obligation or entitlement persistence directly;
- reconstruct obligation lifecycle outside this domain; or
- reinterpret obligation legality using alternate business logic.

Consumers SHALL instead invoke the canonical business operations owned by this domain.

Business authority SHALL remain centralized so that obligation semantics are defined exactly once and consumed consistently throughout the application.

## V. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md` (Policy Source)
- `DOM-ECON-003_ECONOMIC_POLICY_AND_TRANSITION.md` (Operational boundary activation protocol)

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `assessment_events` (historical fact of debt)
- `obligation_lifecycle` (current derived lifecycle state per assessment)
- `obligation_satisfaction` (payments, waivers)
- `obligation_reversal` (corrections, nullifications)
- `entitlement_events` (grant/consumption stream)

`DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md` is authoritative for the exact
44-table target. Insurance enrollment and claim state must be represented
within the canonical assessment/lifecycle/event hierarchy; they do not add
separate final-schema tables.

**Policy Ownership:** Class Configuration owns the obligation policy (rates, schedules). Obligations shall execute the policy into runtime events.

## VII. State Classification

| State | Classification | Rationale |
| :--- | :--- | :--- |
| **Assessment Event** | Authoritative Event | Immutable record of a seat's liability. |
| **Satisfaction Event** | Authoritative Event | Immutable record of debt resolution (Payment/Waiver). |
| **Reversal Event** | Authoritative Event | Immutable record of an assessment nullification. |
| **Entitlement Event** | Authoritative Event | Immutable stream of grants, consumptions, and revocations. |
| **Active Entitlement Grant** | Derived State | Strictly derived from the Entitlement Event stream. |
| **Seat Obligation Status** | Derived State | Intersection of Assessment, Satisfaction, and Reversal events. |
| **Due Date (`due_at`)** | Authoritative Event State | Snapshotted at assessment time from policy + calendar logic. |

## VIII. Invariants

- **INV-OBL-001: Seat-Scoped Isolation**. All obligation state shall be anchored to a `seat_id`. Economic reality is class-bound; debt shall not follow a student across classes.
- **INV-OBL-002: Event-Only Entitlements**. The append-only `entitlement_events` stream is the sole authoritative representation of entitlement state. Entitlement grants and balances MUST NOT exist as independently mutable authoritative scalar state (e.g., stored balances or counters). All entitlement balances and active grants SHALL be derived exclusively from the canonical event stream.
- **INV-OBL-003: Consumption Idempotency**. Entitlement consumption triggers MUST be idempotent. A duplicate `trigger_id` shall never result in multiple decrements.
- **INV-OBL-004: Assessment Idempotency**. A policy-period assessment MUST be idempotent. A duplicate trigger for the same `(seat_id, policy_id, period_key)` shall never create multiple assessments.
- **INV-OBL-005: Reversal Primacy**. A reversed assessment shall be treated as non-existent for all downstream interpretations (delinquency, reporting), overriding any prior satisfaction events. **Reversal wins.**
- **INV-OBL-006: Deterministic Entitlement Compensation**. Any `ReversalEvent` targeting an assessment that previously triggered a `GRANT` MUST emit a corresponding `REVOCATION` event.
- **INV-OBL-007: Period Key Determinism**. The `PeriodKey` shall be derived from the `ClassCalendar` and `PolicySchedule`. It ensures a 1:1 mapping between a time-slice and a liability.
- **INV-OBL-008: Overdue Definition**. A seat is `Overdue` if and only if `now > due_at` AND no `SatisfactionEvent` or `ReversalEvent` exists for that assessment.
- **INV-OBL-009: Policy Snapshotting**. Assessments MUST snapshot `amount` and `due_at`. Mid-cycle policy changes shall not retroactively affect existing debt.
- **INV-OBL-010: Local Time Sovereignty**. All due dates and triggers shall be calculated using the `ClassTimeZone`.

## IX. Schema Contract

### 1. `assessment_events`

Records the historical fact of a seat becoming liable for a policy-defined charge.

- `id` (PK)
- `seat_id` (FK to seats)
- `policy_id` (FK to Class Configuration policies)
- `amount_snap` (Decimal)
- `period_key` (String: `[YYYY]-[PERIOD]`) [Unique: `seat_id`, `period_key`]
- `due_at` (Timestamp: Snapshotted from policy + calendar)
- `assessed_at` (Timestamp)

### 2. `obligation_lifecycle`

Stores the current derived lifecycle state for one assessment.

- `id` (PK)
- `assessment_id` (FK; Unique)
- `status` (Enum: `DUE`, `OVERDUE`, `PAID`, `WAIVED`, `REVERSED`)
- `updated_at` (Timestamp)

### 3. `obligation_satisfaction`

Records how a valid debt was resolved.

- `id` (PK)
- `assessment_id` (FK; Unique)
- `method` (Enum: `PAYMENT`, `WAIVER`)
- `satisfied_at` (Timestamp)

### 4. `obligation_reversal`

Records the correction or nullification of an assessment.

- `id` (PK)
- `assessment_id` (FK; Unique)
- `reason` (String)
- `reversed_at` (Timestamp)

### 5. `entitlement_events`

Append-only stream of obligation-linked perks (e.g., hall pass quota).

- `id` (PK)
- `seat_id` (FK to seats)
- `assessment_id` (FK; Nullable)
- `correlation_id` (String; Nullable - links grants, consumptions, revocations, and downstream consumption records)
- `trigger_id` (String; Nullable - for consumption idempotency)
- `quantity_delta` (Integer: +N for Grant, -N for Consumption/Revocation)
- `type` (Enum: `GRANT`, `CONSUMPTION`, `REVOCATION`)
- `occurred_at` (Timestamp)

## X. Derived / Cross-Domain Rules

- **Status Hierarchy**: Status is derived as: `REVERSED` > `WAIVED` > `PAID` > `OVERDUE` (if `now > due_at`) > `DUE`.
- **Entitlement Sovereignty**: Obligations owns **obligation-linked** entitlements (e.g., rent-linked hall passes). Store owns **store-purchased** items.
- **Canonical Business Operations**: Granting, consuming, revoking, adjusting, and evaluating obligation-linked entitlements SHALL occur exclusively through the canonical business operations owned by this domain. FEATs, routes, jobs, migrations, and tests SHALL consume these operations rather than manipulating persistence or deriving business state independently.
- **Consumption Flow**: Attendance emits `ConsumptionIntent`. Obligations validates against the active grant and records the `CONSUMPTION` event.
- **Hall-Pass Consumption Linkage**: When a hall-pass entitlement is consumed by
  PROD, the resulting `hall_pass_logs.correlation_id` SHALL reuse the consumed
  entitlement grant's `correlation_id`. PROD must not generate a new unrelated
  correlation for the approved hall-pass row.
- **Trigger ID Residue**: `trigger_id` currently represents legacy consumption
  idempotency/source metadata. It is not a substitute for `correlation_id` and
  must not be used as the cross-domain hall-pass linkage value.
- **Ledger Coordination**: All assessment and satisfaction events shall emit `PostingRequests` to Ledger via FEAT. Obligations does not own ledger rows.

## XI. Operational Boundary Authority

Obligations is the sole lawful authority for determining:

- **Rent cycle boundary legality**: Whether a rent cycle has closed and a new assessment period has begun.
- **Insurance renewal boundary legality**: Whether an insurance policy period has expired and renewal is required.

When a lawful boundary is detected, Obligations SHALL:
1. Determine boundary validity using `ClassTimeZone` and the active policy snapshot.
2. Emit a boundary event via the FEAT layer if a pending policy transition exists for the affected domain.
3. NOT directly mutate `policy_versions` or `policy_transitions`. These tables are owned by `DOM-CLASS-001`.
4. NOT activate policy transitions independently. Activation is orchestrated by `FEAT-ECON-001` upon boundary request from Obligations.

This authority is referenced by `DOM-ECON-003` and `FEAT-ECON-001` as "Rent domain determines rent cycle closure" and "Insurance domain determines renewal legality." Both phrases refer to this domain.

No other domain, FEAT, OPS job, GET handler, or request-time path may determine rent cycle or insurance renewal legality.

## XII. Canonical Business Surface

The long-term implementation goal of this domain is to expose a canonical business surface rather than persistence-oriented behavior.

Representative operations include:

- `assess_obligation(...)`
- `satisfy_obligation(...)`
- `reverse_obligation(...)`
- `grant_entitlement(...)`
- `consume_entitlement(...)`
- `revoke_entitlement(...)`
- `get_obligation_status(...)`
- `get_entitlement_balance(...)`

`get_entitlement_balance(...)` SHALL derive the current entitlement balance exclusively from the canonical `entitlement_events` stream. The returned balance is a derived business view and SHALL NOT be persisted or treated as authoritative state.

The exact implementation may evolve, but business consumers SHALL interact with canonical domain operations rather than directly manipulating tables or reconstructing derived business state.

## XIII. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
4. Maintain consistency with `DOM-ECON-003` for operational boundary activation protocol.
