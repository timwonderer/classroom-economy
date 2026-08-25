# SPEC-INV-001: Invariant Enforcement via Continuous Integration

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| --- | ---: | --- | --- | --- |
| SPEC-INV-001 | 1.0 | 2026-08-23 | N/A | Normative  |

## I. Purpose

This specification defines how Classroom Token Hub (CTH) architectural invariants are translated into automated Continuous Integration (CI) enforcement.

Its purpose is not to define architectural truth. Architectural truth is defined by `INV-CORE` and applied system-wide through `INV-ARC`.

This specification defines:

> **What automated evidence is sufficient for CI to claim that an architectural invariant is enforced.**

CI MUST NOT derive architectural requirements from existing workflows, scripts, tests, historical implementation, repository convention, or prior CI behavior.

The authority chain is:

```text
INV-CORE
    ↓
Defines system law

INV-ARC
    ↓
Defines architectural realization

SPEC-INV-001
    ↓
Defines sufficient automated enforcement evidence

CI implementation
    ↓
Executes the evidence mechanism
```

Existing CI implementation has no authority to redefine any layer above it.

---

## II. Scope

This specification applies to:

- GitHub Actions workflows;
- CI scripts;
- architectural linters;
- migration gates;
- schema validation;
- static analysis;
- automated domain and integration tests used as invariant evidence;
- accessibility gates;
- security-oriented repository gates;
- validation artifacts;
- CI status reporting;
- any future automation represented as enforcing an `INV-ARC` requirement.

This specification does not define:

- domain behavior;
- FEAT behavior;
- release approval;
- deployment procedure;
- browser acceptance scenarios;
- operational incident response;
- manual review requirements.

Those concerns remain governed by their respective normative authorities.

---

## III. Authority

This specification derives from:

- `INV-CORE-000_CORE_INVARIANTS`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL`
- `INV-ARC-000_EXECUTION_MODEL`
- `INV-ARC-017_GENERAL_TESTING_INVARIANTS`

`INV-CORE-001` establishes that `INV-CORE` defines system law and `INV-ARC` defines how that law applies architecturally.

`INV-ARC-017` establishes that validation claims must be proportional, concrete, scoped, and supported by actual execution evidence.

This specification is subordinate to all governing `INV` documents.

Where this specification conflicts with an `INV`, the `INV` controls.

---

## IV. Fundamental Enforcement Principle

A CI gate is valid only when all three conditions are satisfied:

1. a governing invariant defines the truth being protected;
2. the enforcement mechanism is capable of detecting a meaningful violation of that truth;
3. the mechanism actually executes against the applicable surface.

Therefore:

> **The existence of a CI gate is not evidence of invariant enforcement.**

A passing command, workflow, test, linter, or status check MUST NOT be represented as invariant enforcement unless its execution materially evaluates the cited invariant.

---

## V. Truth Before Enforcement

### V.2 Existing CI Has No Grandfathered Authority

Historical existence of a workflow, script, linter, or test does not establish that it remains necessary or valid.

Existing CI MAY be:

- current;
- partially sufficient;
- stale;
- redundant;
- obsolete;
- incapable of enforcing its stated claim;
- or no longer authorized by current invariants.

Existing CI MUST be evaluated against current invariant requirements rather than current invariant requirements being inferred from existing CI.

---

### V.3 No Enforcement by Naming

The name of a workflow, job, test, script, or status check does not establish what it proves.

For example:

```text
accessibility-compliance
tenant-isolation
feat-compliance
security-check
full-suite
```

are labels only.

The enforcement claim is determined by what actually executes and what violations that execution can detect.

---

## VI. Evidence Sufficiency

### VI.1 Capability to Detect Violation

An enforcement mechanism MUST be capable of becoming red when the cited invariant is meaningfully violated.

For every mandatory gate, the enforcement design MUST answer:

> **What realistic violation of the governing invariant would cause this gate to fail?**

If no concrete answer exists, the mechanism MUST NOT be represented as enforcement of that invariant.

---

### VI.2 False-Assurance Analysis

Every architectural CI gate MUST also answer:

> **What realistic violation could occur while this gate remains green?**

Known limitations MUST be documented.

Where the limitation leaves a material portion of the invariant unevaluated, the gate MUST be classified as partial evidence rather than complete enforcement.

---

### VI.3 No No-Op Enforcement

The following do not constitute invariant enforcement:

- unconditional passing assertions;
- placeholder tests;
- empty parameter sets;
- checks that never reach the governed code;
- mocks applied to methods production no longer calls;
- tests that construct impossible or unlawful domain states;
- tests that bypass the canonical producer when the claim depends on producer behavior;
- scripts that search only historical implementation patterns;
- checks that silently skip because required tooling is unavailable.

A no-op mechanism MUST NOT report the corresponding invariant as PASS.

---

### VI.4 Zero Applicable Cases

If an enforcement mechanism discovers zero applicable cases, the result MUST NOT automatically be represented as PASS.

The gate MUST distinguish among:

- **PASS** — applicable evidence executed and no violation was detected;
- **FAIL** — applicable evidence executed and a violation was detected;
- **NOT APPLICABLE** — the current change does not touch the governed surface;
- **NOT EVALUATED** — the gate could not execute sufficient evidence;
- **BLOCKED** — required evidence could not execute because of an environmental or dependency failure.

`NOT EVALUATED` and `BLOCKED` MUST NOT satisfy a mandatory launch or merge gate.

---

## VII. Evidence Layer Selection

CI MUST use the lowest authoritative evidence layer capable of proving the required claim.

No evidence layer may be substituted merely because it is easier to automate.

### VII.1 Static Enforcement

Static enforcement is appropriate for architecture that prohibits identifiable code or dependency structures.

Examples include:

- forbidden imports;
- forbidden domain-to-domain dependencies;
- prohibited direct temporal APIs;
- prohibited mutation patterns;
- prohibited schema references;
- prohibited PII columns.

Static enforcement MUST NOT claim to prove runtime behavior it cannot observe.

---

### VII.2 Runtime Test Enforcement

Runtime tests are required where correctness depends on execution behavior.

Examples include:

- cross-tenant isolation;
- denial behavior;
- hard deletion;
- membership resolution;
- transaction ownership;
- idempotency;
- audit lineage;
- temporal boundary behavior.

Tests used as invariant evidence MUST construct lawful preconditions.

---

### VII.3 Persistence Enforcement

Where an invariant is encoded at the database boundary, CI SHOULD directly exercise the persistence constraint.

Examples include:

- foreign-key behavior;
- uniqueness;
- CHECK constraints;
- immutable-row triggers;
- deletion behavior;
- audit-lineage persistence.

Direct database-boundary tests MAY intentionally bypass application execution when the explicit subject of the test is the persistence guard itself.

Such tests MUST NOT be represented as evidence that the normal application producer is correct.

---

### VII.4 Rendered Browser Enforcement

Rendered-browser evidence is required where the invariant depends on actual browser semantics or user interaction.

Examples include:

- computed color contrast;
- accessible names;
- ARIA semantics;
- keyboard operability;
- focus visibility;
- rendered page structure.

Static HTML inspection alone MUST NOT be represented as complete enforcement of runtime accessibility.

---

### VII.5 Operational or Human Evidence

Some invariant consequences cannot be fully established in ordinary CI.

Where the correct evidence requires:

- deployment rehearsal;
- backup restoration;
- external monitoring;
- long-duration scheduling;
- infrastructure behavior;
- human usability judgment;

CI MUST NOT manufacture a substitute check and claim full enforcement.

The invariant MUST instead be marked as requiring additional certification evidence.

---

## VIII. Required CI Enforcement Families

CI implementation MAY organize jobs and workflows differently, but collectively it MUST provide sufficient evidence for the following enforcement families.

---

### VIII.1 Architectural Execution and FEAT Boundary

#### Governing Invariants

- `INV-ARC-000`
- `INV-ARC-003`
- `INV-ARC-006`
- `INV-ARC-007`
- `INV-ARC-009`
- `INV-ARC-021`

#### Required Truth

CI must provide evidence that:

- capability evaluation precedes mutation;
- capability evaluation remains side-effect free;
- mutation occurs through authorized command boundaries;
- GET execution is read-only;
- domain truth is not independently recomputed by FEAT or route code;
- cross-domain coordination occurs only through authorized FEAT orchestration.

#### Minimum Evidence

This family requires both:

1. structural/static architectural enforcement; and
2. runtime mutation/transaction enforcement tests.

Neither layer alone is sufficient.

---

### VIII.2 Scope, Identity, and Tenant Isolation

#### Governing Invariants

- `INV-ARC-001`
- `INV-ARC-002`
- `INV-ARC-004`
- `INV-ARC-008`
- `INV-ARC-010`
- `INV-ARC-011`
- `INV-ARC-013`
- `INV-ARC-014`
- `INV-ARC-019`

#### Required Truth

CI must provide evidence that:

- execution occurs under explicit `class_id` and `seat_id` scope;
- a request does not cross tenant boundaries;
- `users.id`, `seats.id`, and `classes.class_id` retain distinct authority meanings;
- public actor identifiers resolve only within active class scope;
- no alternate-seat fallback occurs;
- context switching is explicit;
- nonexistent scope fails closed;
- membership is existence-based;
- labels do not become authority.

#### Minimum Evidence

This family requires behavioral isolation tests.

Static analysis MAY supplement but MUST NOT replace cross-boundary runtime evidence.

---

### VIII.3 Temporal Integrity

#### Governing Invariant

- `INV-ARC-015`

#### Required Truth

CI must provide evidence that:

- database timestamps are UTC;
- SLE and CLE temporal authority remain distinct;
- CLE evaluation uses canonical class timezone;
- class timezone is immutable;
- governed execution uses the Canonical Temporal Resolver;
- prior events are not reinterpreted after configuration changes.

#### Structural Prohibitions

CI MUST detect unauthorized:

- direct current-time reads;
- direct datetime comparisons;
- direct timezone conversions;
- independent day-boundary calculations;
- alternate temporal helper systems.

Moving prohibited temporal behavior into the canonical resolver module does not automatically make that behavior lawful.

The resolver's finite normative primitive contract governs what may exist there.

---

### VIII.4 PII and Identity Storage

#### Governing Invariants

- `INV-ARC-005`
- `INV-ARC-018`
- `INV-ARC-019`

#### Required Truth

CI must provide evidence that:

- only invariant-permitted PII fields exist;
- plaintext PII is not stored at rest;
- lookup PII uses the required HMAC representation;
- display PII uses the required encrypted representation;
- execution/logging surfaces do not leak PII;
- PII disappears with its owning identity lifecycle.

Schema and migration checks SHOULD treat the permitted PII field set as a finite allowlist.

---

### VIII.5 Lawful Persistence, Audit Lineage, and Lifecycle

#### Governing Invariants

- `INV-ARC-012`
- `INV-ARC-016`

#### Required Truth

CI must provide evidence that:

- protected rows are created through lawful execution authority;
- required audit lineage is emitted;
- AuditEvent history is immutable;
- invalid lineage is distinguishable from unverified lineage;
- terminal class destruction removes class-scoped history;
- deleted scope cannot remain operationally reachable.

Lifecycle immutability and terminal destruction MUST be tested as separate claims.

A row may be immutable during lawful class existence while still being physically destroyed through the authorized terminal-destruction boundary.

---

### VIII.6 Cross-Domain Dependency and Schema Boundaries

#### Governing Invariant

- `INV-ARC-021`

#### Required Truth

CI must provide evidence that:

- domains do not import or invoke other domain internals;
- only FEAT coordinates cross-domain behavior;
- routes, jobs, and scripts do not independently compose multi-domain capability decisions;
- cross-domain foreign keys target only shared anchors permitted by the invariant;
- event-driven side effects remain declared, scoped, auditable, and idempotent.

Static dependency checks are mandatory for this family.

---

### VIII.7 Rendering and Accessibility

#### Governing Invariants

- `INV-ARC-020`
- `INV-ARC-022`

#### Required Truth

CI must provide evidence that:

- rendering follows the canonical page pipeline;
- templates remain pure consumers;
- view models do not mutate or authorize;
- routes do not become domain or presentation authorities;
- supported rendered UI remains perceivable, understandable, navigable, and operable.

#### Accessibility Evidence

For covered rendered surfaces, complete accessibility enforcement requires actual browser rendering.

A passing static template check alone MUST NOT be represented as full `INV-ARC-020` enforcement.

---

### VIII.8 Validation Integrity

#### Governing Invariant

- `INV-ARC-017`

#### Required Truth

CI itself must provide truthful validation evidence.

CI MUST:

- disclose the actual validation scope;
- distinguish targeted from whole-suite execution;
- preserve skipped/blocked evidence;
- use proportional validation;
- require relevant boundary tests when architecture-sensitive surfaces change;
- avoid representing inferred evidence as executed evidence.

The full test suite MUST NOT be the automatic default response to every repository change.

---

## IX. Change-Sensitive Enforcement

Not every change requires every gate to execute.

CI SHOULD determine the relevant enforcement families from the affected architectural surface.

Class-scope or identity changes require:

- Scope, Identity, and Tenant Isolation
- Architectural Execution where mutation is involved
- affected domain tests

FEAT changes require:

- Architectural Execution and FEAT Boundary
- relevant authority/scoping evidence
- commit/idempotency evidence

Temporal changes require:

- Temporal Integrity
- affected domain tests

Migration changes require:

- schema/migration validation;
- upgrade;
- downgrade;
- re-upgrade;
- head validation;
- relevant persistence invariant tests.

Template/UI changes require:

- Rendering architecture;
- rendered accessibility evidence;
- affected user-surface tests.

PII changes require:

- PII and Identity Storage;
- relevant migration and deletion evidence.

A change classifier MAY over-select gates conservatively.

It MUST NOT under-select a gate required by the governing invariant.

---

## X. CI Result Semantics

Every architectural CI gate MUST produce one of the following semantic outcomes:

| Result | Meaning |
| --- | --- |
| `PASS` | Required applicable evidence executed successfully |
| `FAIL` | Evidence detected a violation |
| `NOT_APPLICABLE` | Governed surface is not affected by the evaluated change |
| `NOT_EVALUATED` | Sufficient evidence was not executed |
| `BLOCKED` | Required evidence could not execute |

Only `PASS` and, where explicitly permitted by the gate contract, `NOT_APPLICABLE` satisfy CI.

Mandatory gates MUST fail closed on `NOT_EVALUATED` or `BLOCKED`.

---

## XI. Test Evidence Requirements

Tests used as invariant enforcement evidence MUST comply with `INV-ARC-017`.

In particular:

1. test state must be lawful for the claim being made;
2. canonical producers must be used where producer behavior is part of the claim;
3. direct persistence setup may be used when persistence enforcement itself is the explicit subject;
4. stale fixtures must not be repaired by manufacturing states production cannot lawfully create;
5. mocked failures must intercept the actual production boundary;
6. test names and reported claims must match what is actually exercised;
7. skipped tests do not constitute passing evidence;
8. a partial run may not be reported as whole-scope validation.

---

## XII. CI Security

Invariant enforcement must not itself create an authority or security bypass.

CI design MUST preserve:

- least-privilege workflow permissions;
- separation of untrusted contributor input from privileged execution;
- secret confidentiality;
- safe handling of pull-request code;
- trusted dependency/action provenance;
- explicit authority for automated mutation of repository state.

A security-sensitive CI workflow MUST NOT execute untrusted content with write-capable credentials unless an explicitly authorized security design permits it.

---

## XIII. Traceability Requirements

Every mandatory CI gate MUST document:

- gate identifier;
- governing `INV-ARC`;
- governing `INV-CORE`;
- evidence mechanism;
- applicable repository surface;
- PASS condition;
- FAIL condition;
- known evidence limitations.

Where one gate enforces multiple invariants, all must be listed.

Where one invariant requires multiple gates, each gate's contribution must be identified.

---

## XIV. CI Audit Classification

Existing CI evaluated against this specification shall be classified using the following taxonomy:

### `MATCH`

The mechanism materially provides the required evidence.

### `PARTIAL`

The mechanism provides valid evidence but does not fully establish the required truth.

### `FALSE_ASSURANCE`

The mechanism appears to certify an invariant but does not meaningfully evaluate it.

### `STALE_MECHANISM`

The governing truth remains valid, but the implementation being inspected or exercised is obsolete.

### `ORPHAN`

No current invariant requires the claimed enforcement.

### `BROKEN`

The intended evidence cannot execute reliably.

### `REDUNDANT`

Equivalent or stronger evidence already exists elsewhere and the duplicate adds no meaningful independent assurance.

### `MISSING`

The governing invariant requires CI evidence and no sufficient mechanism exists.

---

## XV. Audit Method

CI reconstruction MUST occur in the following order:

```text
1. Establish current invariant truth.
2. Derive required evidence.
3. Freeze the requirement set.
4. Inspect existing CI.
5. Map existing CI to requirements.
6. Identify gaps, false assurance, stale enforcement, and redundancy.
7. Propose implementation.
8. Implement only after approval.
```

Existing CI MUST NOT be inspected first and then used to infer what the enforcement requirements ought to be.

---

## XVI. Prohibited CI Design Patterns

The following are prohibited:

1. **Name-based assurance**  
   Treating a gate name as evidence of what it proves.

2. **Placeholder compliance**  
   Empty tests, unconditional passes, or TODO checks represented as enforcement.

3. **Silent skip success**  
   Required tooling unavailable → test skipped → gate green.

4. **Historical-count compliance**  
   Treating expected test counts, decorator counts, warning counts, or similar historical baselines as architectural
