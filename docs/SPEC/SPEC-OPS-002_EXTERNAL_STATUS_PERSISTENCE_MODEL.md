# SPEC-OPS-002: External Status Persistence Model

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-OPS-002 | 1.2 | 2026-08-31 | 1.1 | Normative |

## I. Purpose

Define the minimum logical persistence model for independent external status infrastructure. This specification stops at object semantics and does not authorize provisioning, indexes, retention schedules, or runtime implementation.

## II. Scope

This model governs externally observed service conditions, independently publishable status notices, public projections, bounded history, and optional reconciliation references. It does not persist, reproduce, or replace canonical Operations incidents or any CTH business-domain state.

## III. Authority Level

Normative (SPEC Tier). Subordinate to `INV-CORE-000`, `INV-CORE-001`, `INV-ARC-009`, `INV-ARC-016`, `DOM-OPS-001`, `DOM-OPS-002`, and `SOP-OPS-001`.

## IV. Dependencies

- `DOM-OPS-001_OPERATIONS_DOMAIN.md`
- `DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `SOP-OPS-001_SERVICE_STATUS_AND_INCIDENT_COMMUNICATION.md`

## V. Persistence Objects

### 5.1 External Observation — append-only

Records one externally performed observation of one public capability or infrastructure dependency.

Required logical fields:

- stable observation ID;
- observed-at timestamp and correlation ID;
- capability/component key from a closed registry;
- observation class: `LIVENESS`, `READINESS`, `CORRECTNESS`, or `INFRASTRUCTURE_FAILURE`;
- outcome: `PASS`, `FAIL`, or `UNKNOWN`;
- epistemic state: `KNOWN` or `UNAVAILABLE`;
- bounded diagnostic code and bounded latency/result metadata;
- probe version.

Observations MUST NOT contain tenant identifiers, PII, credentials, raw response bodies, stack traces, arbitrary payloads, or inferred internal causes. They cannot be updated or deleted during their retention window. `CONFLICTING` is not a raw-observation state; it belongs to derived assessment or projection state composed from multiple observations.

The fields have distinct meanings: `outcome` records the result of this observation; `epistemic_state` records whether the capability state can be established from the available evidence. A single observation cannot claim aggregate disagreement.

#### Observation State Matrix

| Outcome | Epistemic state | Validity | Meaning |
|---|---|---|---|
| `PASS` | `KNOWN` | Valid | The probe established the tested condition successfully. |
| `FAIL` | `KNOWN` | Valid | The probe established that the tested condition failed. |
| `FAIL` | `UNAVAILABLE` | Valid | The probe could not reach or obtain a usable result from the target; the target is not thereby proven internally faulty. |
| `UNKNOWN` | `UNAVAILABLE` | Valid | No usable result was obtained and no pass/fail conclusion is lawful. |
| `PASS` | `UNAVAILABLE` | **Invalid** | A successful result cannot simultaneously be unavailable. |
| `UNKNOWN` | `KNOWN` | **Invalid** | An unknown outcome cannot assert that the condition is known. |

The Cartesian product of the declared raw-observation enums consists of six possible combinations. Only the four combinations explicitly marked valid are lawful; the remaining two are invalid and MUST be rejected before persistence. `CONFLICTING` is excluded from the raw-observation enum and may appear only on a derived assessment or public projection.

The public capability state is derived from the set of observations and applicable canonical publication information. A `PASS + KNOWN` observation may support a public `AVAILABLE` state only when no newer valid failure or unresolved disagreement controls the projection. A `FAIL + KNOWN`, `FAIL + UNAVAILABLE`, or derived `CONFLICTING` state MUST NOT be projected as healthy. Missing observations do not imply `PASS`.

### 5.2 External Status Notice — append-only publication history

Records a bounded communication artifact published independently when canonical Operations publication is unavailable or when an explicitly authorized external communication is required.

Required logical fields:

- stable external notice ID;
- append-only notice event ID, event type, and publication timestamp;
- notice state: `INVESTIGATING`, `IDENTIFIED`, `MONITORING`, or `RESOLVED`;
- affected capability key;
- impact statement;
- recommended user action, including `NO_ACTION_REQUIRED` where applicable;
- recovery expectation state: `KNOWN`, `ESTIMATED`, or `UNAVAILABLE`;
- recovery expectation only when supported by the state;
- next-update timestamp or explicit `NEXT_UPDATE_UNAVAILABLE` state;
- source observation IDs and bounded author/provenance metadata;
- optional reconciliation reference.

The notice is not a canonical incident. Its existence MUST NOT imply that a canonical incident exists.

### 5.3 Public Status Projection — replaceable derived state

Contains the current public view derived from retained observations and notice publication events. It MAY be replaced or rebuilt. It MUST identify whether the current view is based on external observation, canonical publication, or an unresolved disagreement, and MUST NOT be treated as authoritative incident state.

### 5.4 Historical Rollup — optional derived state

Aggregates system-level, non-tenant observations for availability and status-history presentation only. It is optional and must not be introduced until a concrete product need is identified. Rollups are replaceable derivatives, never source evidence.

## VI. Reconciliation

Reconciliation is optional linkage, not conversion. Store only:

- the stable external notice ID;
- the canonical incident identifier, when one exists;
- linkage timestamp and reconciliation outcome.

Do not copy canonical incident content into external storage. Do not require linkage for publication. Never rewrite the original observation, notice event, or public message after reconciliation.

## VII. Authority and Availability Rules

- Firestore MUST NOT contain `canonical_incidents`, authoritative `incident_events`, or authoritative `incident_summary`.
- External notices MAY be published while canonical incident publication is unavailable.
- When canonical publication is available, ordinary canonical incidents MUST NOT be duplicated automatically as external notices.
- Conflicting external observations produce an explicit `CONFLICTING` state; nulls and free-form strings MUST NOT encode epistemic meaning.
- No layer may infer internal cause or canonical domain state from external reachability alone.

## VIII. Retention Classes

The implementation must define separate retention classes before provisioning:

- detailed external observations and publication events: bounded operational evidence;
- public status projections: replaceable current state;
- historical rollups: longer-lived derived history only if justified;
- reconciliation links: retained long enough to preserve lineage, subject to Operations policy.

Generic cleanup MUST NOT cross retention classes or delete append-only evidence before its authorized retention boundary.

## IX. Deferred Implementation Decisions

This specification intentionally does not decide collection names, document paths, indexes, TTL values, probe cadence, Scheduler, Cloud Run, Firestore regions, deployment topology, authentication mechanisms, or public UI structure. Those decisions require review against this model.

## X. Amendment

Revisions require incrementing the version, updating the Effective Date and Supersedes fields, preserving the distinction between canonical Operations truth and external communication artifacts, and updating the documentation index.
