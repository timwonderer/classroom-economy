# Batch B: Operations Verifier Policy Decision Package

| Reference | Version | Effective Date | Supersedes | Status |
|---|---:|---|---|---|
| BATCH-B-OPS-VERIFIER-POLICY | 1.1 | 2026-09-01 | 1.0 | Approved policy record |

## I. Purpose

Present the remaining Operations policy choices required before implementing
the bounded verifier coordinator and external correctness adapter. This package
does not define Ledger truth, replace `SPEC-LED-001` or `SPEC-LED-002`, or
authorize runtime or infrastructure implementation.

## II. Mechanically Settled Rules

The implementation MUST preserve these approved rules:

- each verification execution is bound to exactly one canonical `class_id`;
- Operations consumes Ledger-owned proof results and does not reproduce Ledger
  queries or invariants;
- `PASS`, proven `FAIL`, `UNAVAILABLE`, stale evidence, dispatch failure, and
  conflicting evidence remain distinguishable;
- missing evidence never becomes `PASS`;
- external adapters receive bounded aggregate state only;
- tenant identifiers, monetary values, row identifiers, raw diagnostics, and
  arbitrary payloads do not cross the external boundary;
- liveness, readiness, and correctness remain separate dimensions;
- conflicting observations must not produce an unjustified healthy declaration;
- audit-lineage results are consumed from the canonical verifier;
- retired v1 checks are not reintroduced into the runner.

## III. Owner Decisions

### 3.1 Freshness classes and thresholds — Approved

The implementation must record `checked_at`, `received_at`, freshness class, and
staleness state. The approved classes are:

| Evidence | Freshness class | Cadence | Maximum age |
|---|---|---:|---:|
| posted-balance reconstruction | `PERIODIC_CORRECTNESS` | 15 minutes plus settlement trigger | 30 minutes |
| available-balance reconstruction | `PERIODIC_CORRECTNESS` | 15 minutes plus settlement trigger | 30 minutes |
| transfer verification | `PERIODIC_CORRECTNESS` | 15 minutes plus settlement trigger | 30 minutes |
| audit-lineage verification | `DEEP_INTEGRITY` | 1 hour | 2 hours |
| external liveness/readiness | `REALTIME` | 1 minute | 5 minutes |

The maximum age is measured by wall-clock age from the latest valid result.
Relevant settlement-triggered verification may refresh a periodic result early;
it does not extend an already stale result without a new successful result.

### 3.2 Aggregate correctness mapping — Approved

The class-bound result set maps to Operations correctness as follows:

| Evidence condition | Semantic distinction | Approved mapping |
|---|---|---|
| all required checks pass and fresh | proven healthy correctness evidence | `AVAILABLE` |
| one or more checks prove a violation while capability remains usable | correctness failure | `DEGRADED` |
| proof establishes capability cannot be used | proven outage | `UNAVAILABLE` |
| required proof unavailable | inability to establish correctness | `UNKNOWN` |
| required result stale | freshness failure, not pass | `UNKNOWN` |
| dispatch/worker infrastructure fails | execution infrastructure failure | `UNKNOWN` |
| sources disagree | conflict/uncertainty | `UNKNOWN` with conflict reason |
| no result exists | unknown/missing evidence | `UNKNOWN` |
| audit-verifier infrastructure failure | explicit integrity-verifier degradation | `DEGRADED` |

`CONFLICTING` remains an internal epistemic state; public projection uses
`UNKNOWN` with a bounded conflict reason. Missing, stale, or unavailable
evidence MUST NOT be projected as healthy.

### 3.3 Capability-to-evidence registry — Approved

The approved closed registry names each capability's evidence source,
observation class, required freshness class, and public eligibility.

| Capability | Evidence source | Observation class | Public eligibility |
|---|---|---|---|
| public service reachability | independent external probe | LIVENESS | eligible after capability projection |
| dependency readiness | approved external readiness probe | READINESS | eligible after capability projection |
| Ledger correctness | Ledger proof surfaces + bounded Operations result | CORRECTNESS | eligible after capability projection |
| audit integrity | canonical audit-lineage verifier | CORRECTNESS | eligible after capability projection |
| canonical incident/publication state | DOM-OPS or authorized external notice | publication state | eligible as canonical/publication projection |

Raw evidence is never directly public. All sources pass through a capability-level
DOM-OPS projection. Public output may identify a capability state such as
`AVAILABLE`, `DEGRADED`, `UNAVAILABLE`, or `UNKNOWN`, but never check names,
tenant detail, monetary values, row identifiers, or diagnostic findings.

## IV. Decision Record

The approved policy provides:

1. `REALTIME`: 1-minute cadence, 5-minute maximum age;
2. `PERIODIC_CORRECTNESS`: 15-minute cadence plus settlement trigger,
   30-minute maximum age;
3. `DEEP_INTEGRITY`: hourly cadence, 2-hour maximum age;
4. unavailable, stale, missing, and conflicting evidence map to `UNKNOWN`;
5. proven usable-capability failure maps to `DEGRADED`, proven outage to
   `UNAVAILABLE`, and audit-verifier infrastructure failure to `DEGRADED`;
6. all public output is a capability-level projection only.

No exception should be inferred from current runtime behavior. A choice that
changes domain authority, privacy/security boundaries, or financial semantics
requires amendment of the governing authority document before implementation.

## V. Dependencies

- `DOM-OPS-001_OPERATIONS_DOMAIN.md`
- `DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `SPEC-LED-001_LEDGER_VERIFICATION_PROOF_SURFACES.md`
- `SPEC-LED-002_COMMAND_IDEMPOTENCY_RESERVATION_AND_ENFORCEMENT.md`
- `SPEC-OPS-002_EXTERNAL_STATUS_PERSISTENCE_MODEL.md`
- `SOP-OPS-001_SERVICE_STATUS_AND_INCIDENT_COMMUNICATION.md`
