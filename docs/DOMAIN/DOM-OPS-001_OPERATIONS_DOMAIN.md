# DOM-OPS-001: Operations Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-OPS-001      | 2.3     | 2026-08-31     | 2.2        | Normative       |

## 0. Authority Level and Dependencies

Normative. Subordinate to `INV-CORE-000` and `INV-ARC-009`.

### Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-004_CROSS_TENANT_ISOLATION.md`

---

## 1. Domain Authority

The Operations domain is the single authority over the **Operational Truth** of the system. It governs how the system observes itself, records its behavior, and communicates its status to external actors.

### Operations OWNS Authority Over:
*   **Health Status**: The aggregated state of system liveness, readiness, and correctness.
*   **Invariant Execution Records**: The trace and result of every runtime invariant check.
*   **Incident Records**: The lifecycle and historical record of system failures.
*   **Structured Operational Logs**: The standard and storage for system-level telemetry.
*   **Audit Trail Standards**: The high-integrity record of security-sensitive and financial side effects.
*   **Background Job Execution Traces**: The history of scheduled or asynchronous work.
*   **Correlation / Trace Identity**: The generation and propagation of workflow identifiers.
*   **Alert State**: The lifecycle of notifications triggered by operational events.
*   **Status Page Publication State**: The public-facing representation of system health and incidents.
*   **Retention Policy State**: The rules governing the lifespan of operational data.

### External Publication During Canonical-Service Unavailability

Independent status infrastructure MAY maintain and publish bounded external communication records when canonical Operations incident publication is unavailable.

An `ExternalStatusNotice` is a communication artifact, not Operational Truth and not a canonical incident. It:

*   may report only independently observed service conditions and explicitly bounded operator guidance;
*   MUST NOT infer internal domain state, internal cause, or the existence of a canonical incident;
*   MUST remain distinguishable from `incident_events` and `incident_summary`;
*   MUST preserve its original observation and publication history without rewriting;
*   MAY be reconciled with or linked to canonical incident lineage when canonical service becomes available, where applicable.

This channel exists only to preserve useful public communication during canonical-service unavailability. It does not create a second Operations authority.

### Operations Explicitly DOES NOT Own:
*   **Business Domain Truth**: It does not define what a balance is, whether a student is present, or if an item is purchased.
*   **Feature Policy**: It does not decide which features are enabled for a class.
*   **Financial Balances**: It does not own the math or current state of the Ledger.
*   **Attendance Facts**: It does not own the tap logs or session status.
*   **Obligation Facts**: It does not own debt or assessment logic.
*   **Entitlement Balances**: It does not own the count of perks or items.
*   **Economic Policy Truth**: It does not own `policy_versions` or `policy_transitions`. Class configuration and `economic-engine` are owned by `DOM-CLASS-001`; `policy_versions` and `policy_transitions` are owned by `DOM-CLASS-003`.
*   **Operational Boundary Legality**: It does not determine whether a rent cycle has closed, an insurance period has expired, or an accrual rollover is lawful. Those determinations belong to the owning operational domain (see §8).

### Interactions:
*   **Reads From**: All domains (Identity, Ledger, Obligations, Attendance, Store, Class Config) to evaluate invariants and health.
*   **Consumed By**: Support Tools (DOM-SUP), External Status Pages, Monitoring Systems, and Incident Response Teams.

---

## 2. State Classification

| State Entity | Classification | Justification |
| :--- | :--- | :--- |
| **Invariant Run Record** | Authoritative Event | A point-in-time detection of system (in)correctness. |
| **Health Check Result** | Authoritative Event | A point-in-time observation of component status. |
| **Structured Log Event** | Authoritative Event | Immutable record of system telemetry. |
| **Audit Event** | Authoritative Event | High-integrity, non-repudiable record of side effects. |
| **Incident Event** | Authoritative Event | Append-only record of an incident's lifecycle change. |
| **Alert Event** | Authoritative Event | Append-only record of a notification's lifecycle change. |
| **Job Execution Event** | Authoritative Event | Append-only record of background work progress/outcome. |
| **Trace / Correlation ID** | System Guard | The technical glue ensuring causality and traceability. |
| **Incident Summary** | Cache | Projection derived from incident events for fast current-state lookup. |
| **Status Page State** | Derived State | Calculated from active incidents and health events. |
| **External Status Notice** | Non-authoritative Communication Artifact | Bounded public communication based on independent external observation; never a canonical incident. |
| **Retention Policy State**| Authoritative Directive State | Defines the legal/technical lifespan of operational records. |

---

## 3. Invariants

### INV-OPS-001: Observability Without Business Mutation
*   **Statement**: The Operations domain may observe and report on any domain state but MUST NOT directly mutate business domain state.
*   **Constraints**:
    *   No direct SQL `UPDATE` or `DELETE` on tables owned by Identity, Ledger, Obligations, Attendance, Store, or Class Config.
*   **Prohibited Action**: An invariant runner automatically adjusting a student's balance or attendance status.

### INV-OPS-002: Append-Only Lifecycle State
*   **Statement**: All lifecycle state changes (Incidents, Alerts, Job Executions, Invariant Runs) MUST be recorded as append-only events.
*   **Constraints**:
    *   The event log is the source of truth.
    *   Any mutable "current state" table is a secondary projection or cache.
*   **Prohibited Action**: Updating a `job_execution` row from `RUNNING` to `SUCCESS` without emitting a corresponding event record.

### INV-OPS-003: Structured Logging Consistency
*   **Statement**: All operational logs must be JSON-structured and include mandatory, indexed trace fields outside the JSON payload.
*   **Constraints**:
    *   Mandatory Top-level Fields: `timestamp`, `correlation_id`, `domain`, `level`.
    *   JSON only for variable payload.
    *   **Critical trace fields MUST NOT exist only inside JSON blobs.**
*   **Prohibited Action**: Hiding a critical `seat_id` or `error_code` inside an opaque JSON string if it is required for primary indexing.

### INV-OPS-004: Correlation Integrity
*   **Statement**: Every request, background job, or internal workflow MUST carry a stable `correlation_id` across boundary hops.
*   **Constraints**:
    *   Identities must be generated at the entry point.
    *   **Incidents MUST anchor at least one originating correlation context.**
*   **Prohibited Action**: Creating an incident that cannot be linked back to a specific trace or invariant run.

### INV-OPS-005: Invariant Runner Authority
*   **Statement**: Runtime invariant runners may detect violations but must not silently "heal" business state.
*   **Prohibited Action**: An automated script "fixing" an out-of-sync ledger without an auditable business-logic transaction.

### INV-OPS-005A: Single-Scope Verification Execution
*   **Statement**: Operations may coordinate verification across the system only by dispatching independently authorized verification executions, each bound to exactly one canonical `class_id`.
*   **Constraints**:
    *   A verification worker MUST read and evaluate one `class_id` boundary per execution.
    *   A coordinator MUST NOT read tenant tables, issue a cross-class domain query, reconstruct a teacher-wide class set, or combine class identifiers in one domain execution.
    *   The coordinator MAY receive a pre-authorized opaque work item and MAY aggregate redacted outcomes such as check name, state, freshness, and failure count without tenant identity.
    *   A worker result MUST be reduced to the approved Operations result boundary before leaving its class-bound execution.
    *   Failed dispatch, missing work, stale results, and worker infrastructure errors remain distinct from a proven invariant violation.
*   **Prohibited Action**: Treating a loop over `class_id` values or a global aggregate query as compliant merely because each inner query is filtered.

### INV-OPS-006: Health Semantics
*   **Statement**: System health must distinguish between Liveness, Readiness, and Correctness.
*   **Prohibited Action**: Reporting "Healthy" when a critical domain invariant (e.g., zero-sum ledger) is failing.

### INV-OPS-007: Audit Completeness and Structure
*   **Statement**: Any action resulting in a financial, security, or identity-binding side effect MUST produce an `Audit Event` with a structured `changes` schema.
*   **Constraints**:
    *   Audit `changes` MUST follow a structured schema (before/after or field-delta format).
*   **Prohibited Action**: Storing arbitrary, unstructured blobs in the `audit_log.changes` field.

### INV-OPS-008: Append-Only Operational History
*   **Statement**: Incident history, invariant results, and audit events must be append-only within their retention window.
*   **Prohibited Action**: Deleting a record of a failed background job because it was eventually retried successfully.

### INV-OPS-009: Failure Visibility
*   **Statement**: Partial failures, retries, rollbacks, and skipped executions must be explicitly visible as distinct events.
*   **Prohibited Action**: Hiding internal retries from the operational trace.

### INV-OPS-010: Retention Enforcement Boundary
*   **Statement**: Retention enforcement MUST be explicit, logged, and never applied across different retention classes (Audit vs Debug).
*   **Constraints**:
    *   Audit and Incident records MUST NOT be purged by generic log cleanup scripts.
*   **Prohibited Action**: Accidental purge scripts nuking audit data due to shared storage keys.

### INV-OPS-011: No Hidden Remediation
*   **Statement**: Any automatic remediation MUST be explicit, logged, and separately classified from detection.
*   **Prohibited Action**: A background job "cleaning up" data without logging the specific records changed and the rationale.

### INV-OPS-012: Class/Seat/User Trace Boundaries
*   **Statement**: Operational records MUST preserve the distinction between `user_id` (human), `seat_id` (economic actor), and `class_id` (universe).
*   **Prohibited Action**: Logging only a `user_id` for a seat-scoped transaction.

---

## 4. State Transitions

### Operational Event Lifecycle
*   **Emit Structured Log**: (System) -> Effect: Appends to `operational_events`.
*   **Record Audit Event**: (Domain Service) -> Effect: Appends to `audit_log`.

### Invariant Runner Lifecycle
*   **Start Invariant Run**: (Scheduler/Trigger) -> Effect: Appends `START` to `invariant_run_events`.
*   **Complete Invariant Run**: (Runner) -> Effect: Appends `PASS` to `invariant_run_events`.
*   **Fail Invariant Run**: (Runner) -> Effect: Appends `FAIL` to `invariant_run_events`.
*   **Coordinate Scoped Runs**: (Operations Coordinator) -> Effect: Dispatches independently class-bound verification executions and receives only bounded redacted results.

### Incident Lifecycle
*   **Create Incident**: (System/Admin) -> Effect: Creates `incident_summary` AND appends `CREATED` to `incident_events`.
*   **Update Incident**: (Admin/System) -> Effect: Appends `UPDATED` to `incident_events`.
*   **Resolve Incident**: (Admin/System) -> Effect: Updates `incident_summary` AND appends `RESOLVED` to `incident_events`.

### External Publication Lifecycle
*   **Publish External Status Notice**: (Independent Status Infrastructure) -> Effect: Appends a bounded communication artifact and its publication event outside the canonical incident lifecycle.
*   **Reconcile External Status Notice**: (Status Infrastructure/System) -> Effect: Adds a linkage to canonical incident lineage when available; never rewrites the original notice or observation.

### Alert Lifecycle
*   **Emit Alert**: (System) -> Effect: Appends `TRIGGERED` to `alert_events`.
*   **Acknowledge Alert**: (Operator) -> Effect: Appends `ACKNOWLEDGED` to `alert_events`.
*   **Resolve Alert**: (System/Operator) -> Effect: Appends `RESOLVED` to `alert_events`.

### Background Job Lifecycle
*   **Start Job**: (Scheduler) -> Effect: Appends `STARTED` to `job_events`.
*   **Complete Job**: (Worker) -> Effect: Appends `SUCCESS` to `job_events`.
*   **Fail Job**: (Worker) -> Effect: Appends `FAILED` or `RETRY` to `job_events`.

### Health Lifecycle
*   **Record Health Check**: (System/Runner) -> Effect: Appends check result to `health_check_events`.

---

## 5. Derived Schema

### `operational_events`
*   `id`: UUID
*   `timestamp`: TIMESTAMPTZ (Indexed)
*   `correlation_id`: UUID (Indexed)
*   `domain`: VARCHAR (Indexed)
*   `level`: ENUM ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
*   `message`: TEXT
*   `payload`: JSONB

### `audit_log`
*   `id`: UUID
*   `timestamp`: TIMESTAMPTZ
*   `actor_id`: UUID
*   `correlation_id`: UUID
*   `action`: VARCHAR
*   `resource_id`: VARCHAR
*   `changes`: JSONB (Strict schema: `before`/`after`)

### `invariant_run_events`
*   `id`: UUID
*   `invariant_id`: VARCHAR (Reference to INV-*)
*   `event_type`: ENUM ('START', 'PASS', 'FAIL', 'ERROR')
*   `timestamp`: TIMESTAMPTZ
*   `correlation_id`: UUID
*   `payload`: JSONB (Specific violations detected)

### `incident_events`
*   `id`: UUID
*   `incident_id`: UUID
*   `timestamp`: TIMESTAMPTZ
*   `event_type`: ENUM ('CREATED', 'UPDATED', 'RESOLVED', 'COMMENT')
*   `payload`: JSONB

### `incident_summary` (Cache)
*   `id`: UUID
*   `correlation_id`: UUID (Originating context)
*   `title`: TEXT
*   `severity`: ENUM ('SEV1', 'SEV2', 'SEV3')
*   `status`: ENUM ('OPEN', 'RESOLVED')
*   `opened_at`: TIMESTAMPTZ

### `alert_events`
*   `id`: UUID
*   `alert_type`: VARCHAR
*   `event_type`: ENUM ('TRIGGERED', 'ACKNOWLEDGED', 'RESOLVED')
*   `timestamp`: TIMESTAMPTZ
*   `correlation_id`: UUID
*   `payload`: JSONB

### `job_events`
*   `id`: UUID
*   `job_name`: VARCHAR
*   `event_type`: ENUM ('STARTED', 'SUCCESS', 'FAILED', 'RETRY', 'SKIPPED')
*   `timestamp`: TIMESTAMPTZ
*   `correlation_id`: UUID
*   `payload`: JSONB

### `health_check_events`
*   `id`: UUID
*   `timestamp`: TIMESTAMPTZ
*   `check_type`: ENUM ('LIVENESS', 'READINESS', 'CORRECTNESS')
*   `component`: VARCHAR
*   `outcome`: ENUM ('PASS', 'FAIL', 'WARN')
*   `correlation_id`: UUID (Nullable)
*   `payload`: JSONB

---

## 6. Edge Case Decisions

1.  **Log vs. Audit vs. Incident vs. Alert**:
    *   **Log**: Telemetry (Telemetry).
    *   **Audit**: Accountability (Integrity).
    *   **Alert**: Attention (Notification lifecycle).
    *   **Incident**: Duration (History of failure).
2.  **Correlation ID Ownership**: Operations owns the standard and propagation rules.
3.  **Health Definitions**:
    *   **Live**: Process is up.
    *   **Ready**: Dependencies are accessible.
    *   **Correct**: Business invariants are passing.
4.  **Auto-Fixing**: No. Invariant runners detect. Remediation must be an explicit, auditable FEAT.
5.  **Audit Requirements**: Mandatory for every Ledger mutation, Identity claim, Store purchase, and Class deletion.
6.  **Incident Correlation**: Incidents must anchor at least one originating correlation context.
7.  **Status Page State**: Derived from (1) active incidents in `incident_summary`, (2) latest `health_check_events`, and (3) severity mapping rules.
8.  **Retention Enforcement**: Must be explicit, logged, and isolated by retention class.
9.  **Repeated Failures**: Recorded as distinct events in `job_events`, `invariant_run_events`, or `health_check_events`.
10. **Avoiding Analytics**: Operations stores diagnostic/correctness data only.
11. **Verification Scope**: Cross-class correctness aggregation is permitted only over redacted results from independently class-bound executions; it is not a cross-class domain read.

---

## 7. Identity & Trace Model Alignment

*   `user_id`, `seat_id`, `class_id`, `correlation_id` must all be preserved in operational records and never collapsed.

---

## 8. Scheduled Activation Infrastructure

Operations owns the **execution evidence** of scheduled policy activation jobs. It does NOT own policy truth or boundary legality.

### 8.1 Activation Sequence

When a scheduled OPS job fires that may trigger pending policy transition activation, the lawful sequence is:

1. **OPS job fires** — Records a `STARTED` event in `job_events`. Carries a stable `correlation_id`.
2. **Operational domain checks boundary legality** — The owning domain (`DOM-OBL-001` for rent/insurance, `DOM-BANK-001` for accrual rollover) determines whether a lawful boundary has occurred. OPS does not make this determination.
3. **If boundary is lawful** — The operational domain signals `FEAT-ECON-001` to validate the pending transition and execute the activation sequence.
4. **FEAT-ECON-001 orchestrates activation** — Creates target policy version as active, marks prior version inactive, marks transition applied, supersedes conflicting pending transitions. All within a single transaction boundary.
5. **DOM-CLASS-001 receives the activated state** — `policy_versions` and `policy_transitions` reflect the new constitutional state.
6. **DOM-OPS records execution evidence** — Appends `SUCCESS` (or `FAILED`) to `job_events`. Appends audit event with `correlation_id`, `class_id`, `domain`, and transition reference.

### 8.2 Prohibited OPS Activation Patterns

The following are constitutionally prohibited:

- OPS job directly mutating `policy_versions` or `policy_transitions`
- OPS job determining rent cycle legality or insurance renewal legality
- OPS job calling GET-style handlers to trigger policy activation as a side effect
- OPS job bypassing `FEAT-ECON-001` to activate transitions directly
- OPS job activating transitions without recording execution evidence in `job_events`

### 8.3 Activation Evidence Requirements

For every scheduled policy activation attempt, OPS MUST record:

- `job_events`: `STARTED`, and `SUCCESS` or `FAILED`
- `audit_log`: activation action with `before`/`after` state reference, `class_id`, `domain`, `correlation_id`
- Any `FAILED` event MUST include the failure reason in `payload`

OPS evidence does not constitute policy truth. Policy truth remains in `policy_versions` under `DOM-CLASS-001` authority.
