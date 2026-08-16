# DOM-CORE-001: Domain Authority Summary

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-CORE-001 | 1.0 | 2026-04-22 | N/A | Constitutional |

---

## I-A. Authority Level

Foundational. Subordinate to `INV-CORE-000` and `INV-CORE-001`.

## I-B. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`

---

## I. Purpose

This document serves as the central "Restructuring Map" for the V2 Domain Authority Model. It provides a high-level technical summary of all codified domains, ensuring that future implementation (Build Phase) adheres to the established Domain Law.

## II. System-Wide Invariants

All domains listed below are bound by the following structural rules:
1. **Seat-Scoped Isolation**: All activity is anchored to `seat_id`. No cross-class leakage.
2. **Event-Log Authority**: State is derived from immutable event logs. Caches are non-authoritative.
3. **Policy vs. Execution**: Class Configuration owns "Directives"; Operational domains own "Facts."
4. **Global Idempotency**: All write operations require a unique `idempotency_key`.
5. **FEAT Execution Compliance**: All state mutation MUST occur through a compliant FEAT unit governed by [FEAT-CORE-000](../FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md).

---

## III. Master Directives

### 1. Feature Execution Constitutional Directive ([FEAT-CORE-000](../FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md))
- **Authority**: Mandatory execution contract for all cross-domain coordination and state mutation.
- **Enforcement**: Atomic transactions, context-first resolution, mandatory audit logging.

---

## IV. Domain Summary Matrix

### 1. Canonical Identity Model (`DOM-IDEN-001`)
- **Authority**: Sovereign over canonical identity objects and participation model.
- **Version**: 2.0
- **State Classification**:
  - `users`: Authoritative Global Identity.
  - `seats`: Authoritative Local Binding.
  - `classes`: Authoritative Universe Anchor.
  - `identity_profiles`: Display-only human-facing identity.
- **Primary Schema**: `users`, `seats`, `identity_profiles`, `classes`.
- **Companion Documents**:
  - `DOM-IDEN-002` — Student Identity Architecture (includes student recovery)
  - `DOM-IDEN-003` — Teacher Identity Architecture (includes teacher recovery)
  - `DOM-IDEN-005` — Identity Binding and Lifecycle
  - `DOM-IDEN-006` — Canonical Context Resolution

### 2. Class Configuration (`DOM-CLASS-001`)
- **Authority**: Sovereign over "Directives" (Class Law/Policy).
- **State Classification**:
  - `*_settings`: Authoritative Directives (Rates, Schedules, Limits).
  - `class_features`: Authoritative Enablement State.
- **Key Transitions**: `Update Policy`, `Toggle Feature`.
- **Primary Schema**: `class_features` (feature enablement). Class Configuration does **not** own domain-specific policy definitions such as `rent_settings`, `payroll_settings`, `hall_pass_settings`, or `banking_settings` (see `DOM-CLASS-001` §II and §V) — those are stored in the Policies repository (`DOM-POL-001`) as immutable version rows and consumed by the owning operational domain.

### 3. Productivity & Payroll (`DOM-PROD-001`)
- **Authority**: Sovereign over productivity facts, hall-pass consumption records, and payroll business events.
- **State Classification**:
  - `attendance_sessions`: Authoritative append-only productivity fact timeline.
  - `hall_pass_logs`: Authoritative approved hall-pass consumption records.
  - `payroll_event`: Authoritative append-only payroll business event records.
- **Key Transitions**: `Start Work`, `Break`, `Leave`, `Return`, `Approve Hall Pass`, `Run Payroll`, `Manual Credit`, `Reverse Payroll Event`.
- **Primary Schema**: `attendance_sessions`, `hall_pass_logs`, `payroll_event`.

### 4. Obligations & Assessments (`DOM-OBL-001`)
- **Authority**: Sovereign over seat-scoped debt lifecycles and linked entitlements.
- **State Classification**:
  - `assessment_events`: Authoritative Event (Debt Fact).
  - `obligation_lifecycle`: Authoritative Event State (PAID, OVERDUE, REVERSED).
  - `entitlement_events`: Authoritative Event Stream (Perk Ledger).
- **Key Transitions**: `Assess`, `Satisfy`, `Reverse` (with Revocation).
- **Primary Schema**: `assessment_events`, `entitlement_events`.

### 5. Ledger & Money (`DOM-LED-001`)
- **Authority**: Sovereign over monetary truth. Domain-blind.
- **State Classification**:
  - `ledger_transaction`: Authoritative Event (Math Log).
  - `idempotency_lock`: System Guard (Uniqueness).
  - `posted_balance_snapshot`: Cache (Posted funds).
- **Key Transitions**: `Post`, `Void`, `Reverse` (Append-only negation), `Transfer` (Atomic Zero-sum).
- **Primary Schema**: `ledger_transaction`, `ledger_balance_snapshot`.

### 6. Store & Entitlements (`DOM-STORE-001`)
- **Authority**: Sovereign over entitlement grant lineage, entitlement exercise lineage, and unresolved entitlement actions.
- **State Classification**:
  - `entitlement_events`: Authoritative Event Stream.
  - `pending_actions`: Durable unresolved entitlement-action records.
- **Key Transitions**: `Grant`, `Consume`, `Expire`, `Revoke`, `Submit Pending Action`, `Resolve Pending Action`.
- **Primary Schema**: `entitlement_events`, `pending_actions`.

### 7. Operations (`DOM-OPS-001`)
- **Authority**: Sovereign over operational truth, system health, and observability.
- **State Classification**:
  - `operational_events`: Authoritative Event (Telemetry).
  - `audit_log`: Authoritative Event (High-integrity side effects).
  - `incidents`: Authoritative Directive State (Failure lifecycle).
  - `invariant_results`: Authoritative Event (Correctness detection).
- **Key Transitions**: `Emit Log`, `Fail Invariant`, `Create Incident`, `Record Audit`.
- **Primary Schema**: `operational_events`, `audit_log`, `incidents`, `invariant_results`, `job_executions`.

### 8. Interpretation (`DOM-ITR-001`)
- **Authority**: Sovereign over Behavioral signals (actor activity) and Structural signals (Economy Health).
- **Axis Model**: Strictly separates **Behavioral Interpretation** (What happened) from **Structural Interpretation** (What was possible).
- **Cycle-Lock**: Evaluates completed payroll cycles only; resets on CWI or Policy change.
- **State Classification**:
  - `behavioral_metrics` / `structural_metrics`: Derived State.
  - `interpretation_snapshots`: Cache (Performance).
- **Key Transitions**: `Compute Interpretation`, `Materialize Snapshot`.
- **Primary Schema**: `interpretation_snapshots`, `interpretation_annotations`.

### 9. Support & Communication (`DOM-SUP-001`)
- **Authority**: Sovereign over issue lifecycle state, resolution records, and class communications.
- **State Classification**:
  - `issues`: Authoritative Lifecycle State.
  - `resolution_actions`: Authoritative Fact (Audit).
  - `correlation_packs`: Immutable Diagnostic Context.
- **Key Transitions**: `File Issue`, `Escalate`, `Resolve`, `Announce`.
- **Primary Schema**: `issues`, `issue_resolution_actions`, `announcements`.

### 10. Policies (`DOM-POL-001`)
- **Authority**: Append-only, immutable repository of class-scoped policy definitions. Newest addition to the domain list. Does **not** own mutation flows — stores the immutable version rows other domains produce, and hands back a stable `policy_uuid` for downstream provenance references.
- **State Classification**:
  - Definition rows (`rent_settings`, `store_items`, insurance definitions, etc.): Immutable-after-insert version records.
  - Availability state per row: `IN_USE`, `HIDDEN`, `RETIRED`.
- **Key Transitions**: none originated here. New definitions are inserted by the domain that initiates the change (Class Config UI submission, insurance authoring flow, etc.); Policies only exposes `Disable` / `Retire` availability projections (see `DOM-POL-001` §VIII).
- **Primary Schema**: `rent_settings` (consumed by DOM-OBL-001), `payroll_settings` / `payroll_rewards` / `payroll_fines` (consumed by DOM-PROD-001), `hall_pass_settings` (consumed by DOM-PROD-001), `banking_settings` (consumed by Banking domain), `store_items` / `store_item_visibility` (consumed by DOM-STORE-001), insurance policy definitions (consumed by Insurance flow).
- **Boundary**: rent enablement → Class Configuration; rent settings → Policies; rent bill cycles and assessments → Obligations. See `DOM-POL-001` §X for the full boundary table.

---

## IV. Domain Transition Map (Example Flow)

| Step | Action | Initiating Domain | Executing Domain | Impact |
| :--- | :--- | :--- | :--- | :--- |
| 1 | **Bind User** | Identity | System | Validates Global User and restores context via `last_active_seat_id`. |
| 2 | **Tap In** | Attendance | Identity | Validates Seat context ownership. |
| 3 | **Apply Fine** | Payroll FEAT | Ledger | Creates `PENDING` Debit. |
| 4 | **Assess Rent** | Obligations | Class Config | Reads Rent Rate. |
| 5 | **File Issue** | Support | Identity | Snapshots `seat_id` and Captures Correlation Pack. |
| 6 | **Buy Item** | Store | Ledger | Requests balance query and submits transaction intent. |
| 7 | **Post Transaction**| System | Ledger | Updates `Balance Snapshot`. |
| 8 | **Record Audit** | Ledger | Operations | Creates immutable record of money move. |
| 9 | **Detect Violation**| Operations | Ledger | Invariant runner identifies unbalanced transaction. |
| 10| **Open Incident** | Operations | System | Publishes failure to status page and triggers alerts. |
| 11| **Interpret State** | Interpretation | All Domains | Generates Behavioral and Structural signals. |



---

## V. Amendment

This document is the "Source of Truth" for the domain restructuring. Any change to individual `DOM-*` documents must be reflected here.
