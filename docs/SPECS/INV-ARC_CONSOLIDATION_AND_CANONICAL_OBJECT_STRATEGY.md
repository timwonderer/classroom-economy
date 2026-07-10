# INV-ARC Consolidation and Canonical Object Strategy

## I. Purpose

This specification establishes the organizing rule for the `INV-ARC` namespace.

The purpose of an `INV-ARC` document is not to describe every architectural preference as a standalone document. The purpose of an `INV-ARC` document is to define a foundational architectural authority that either:

1. creates a unique canonical runtime object, helper, resolver, builder, guard, or execution model; or
2. defines a global execution constraint that governs all canonical architectural objects.

If a proposed `INV-ARC` cannot satisfy one of these criteria, it SHOULD NOT exist as an independent `INV-ARC` and SHOULD instead be incorporated into the existing architectural owner that already governs the relevant runtime object or execution constraint.

---

## II. Core Principle

Each canonical `INV-ARC` SHOULD own exactly one architectural authority.

That authority SHOULD be expressed as one of the following:

- a canonical runtime object,
- a canonical helper,
- a canonical resolver,
- a canonical builder,
- a canonical guard,
- a canonical execution model,
- or a global execution constraint.

An `INV-ARC` SHALL NOT be created merely because a rule is important. Importance alone is insufficient. The rule must either define a distinct architectural authority or constrain all architectural authorities.

---

## III. Canonical Object Requirement

Each Canonical Runtime Specification SHALL identify its canonical runtime representation.

Examples:

| Architectural Area | Canonical Runtime Representation |Target Implementation|
|---|---|---|
| Execution | `ExecutionContext`, FEAT execution shell |v2.1+|
| Context | `CanonicalContext` / scoped request context |v2.0|
| Identity | `CanonicalIdentity`, identity resolution pipeline |v2.0|
| Temporal | `CanonicalTemporalEvaluation` |v2.0|
| Audit | `AuditContext`, `AuditLineage`, `CorrelationPack` |v2.0|
| Domain Coordination | FEAT-only coordination boundary |v2.0|

Downstream DOM, FEAT, route, job, migration, and test code SHALL consume these canonical representations rather than reconstructing the architectural concept independently.

---

## IV. INV-ARC Admission Test

Before creating a new `INV-ARC`, the author SHALL answer:

1. What unique canonical runtime representation does this specification create?
2. If it does not create one, what global execution constraint does it enforce?
3. Is this rule already a consequence of an existing canonical object?
4. Would this specification be better represented as a section of an existing architectural owner?

If the answer to both questions 1 and 2 is `none`, the proposed document SHALL NOT be admitted as a standalone `INV-ARC`.

---

## V. Consolidation Rule

An existing `INV-ARC` SHOULD be consolidated when its rule is better understood as a property, guarantee, or constraint of another canonical architectural object.

For example:

- Cross-tenant isolation is a guarantee of canonical context resolution.
- Phantom scope prevention is a guarantee of canonical context resolution.
- Explicit context switching is a controlled operation of canonical context resolution.
- Scoped capability evaluation is an execution concern owned by the execution model.
- GET purity and command-only mutation are execution constraints owned by the execution model.

Consolidation SHOULD preserve the original rule, but relocate it under the architectural owner that actually enforces it.

---

## VI. Proposed INV-ARC Ownership Model

Target Implementation: v2.1+

### 1. Execution Architecture

Owner document: `INV-ARC-000_EXECUTION_MODEL.md`

Owns:

- FEAT execution shell
- execution context
- capability evaluation
- command boundary for mutation
- GET purity
- route/job delegation rules
- global execution sequencing

Likely absorbs or references:

- `INV-ARC-003_SCOPED_CAPABILITY_EVALUATION.md`
- `INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `INV-ARC-007_GET_MUST_BE_PURE.md`

### 2. Canonical Context Architecture

Owner document: `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md` or a renamed `INV-ARC-001_CANONICAL_CONTEXT_RESOLUTION.md`

Owns:

- canonical request context
- `user_id`, `class_id`, `seat_id` tuple
- no implicit global access
- one-tenant-per-request rule
- explicit context switching
- no phantom scope access
- fail-closed context establishment

Likely absorbs or references:

- `INV-ARC-002_NO_IMPLICIT_GLOBAL_ACCESS.md`
- `INV-ARC-004_CROSS_TENANT_ISOLATION.md`
- `INV-ARC-010_EXPLICIT_CONTEXT_SWITCHING.md`
- `INV-ARC-011_NO_PHANTOM_SCOPE_ACCESS.md`

### 3. Canonical Identity Architecture

Owner document: `INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`

Owns:

- authentication principal
- operational actor
- ownership model
- public actor identity
- display identity
- capability tokens
- roster provisioning and seat claim
- membership by existence
- no label-based identity logic

Likely absorbs or references:

- `INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `INV-ARC-013_MEMBERSHIP_BY_EXISTENCE.md`
- `INV-ARC-014_NO_LABEL_BASED_LOGIC.md`

### 4. Canonical Temporal Architecture

Owner document: `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`

Owns:

- System-Level Evaluations (SLEs)
- Class-Level Evaluations (CLEs)
- Canonical Class Timezone
- `CanonicalTemporalEvaluation`
- finite temporal primitives
- temporal boundary derivation
- prohibition on direct datetime interpretation

This document should remain standalone.

### 5. Audit and Lawful Existence Architecture

Owner document: `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`

Owns:

- lawful existence
- audit event lineage
- audit chain integrity
- correlation packs
- protected row provenance
- lawful write paths

This document should remain standalone.

### 6. Privacy and PII Architecture

Owner documents:

- `INV-ARC-005_NO_PII_LEAKAGE_IN_EXECUTION_LAYER.md`
- `INV-ARC-018_PII_STORAGE_AND_RETENTION_ENFORCEMENT.md`

These may either remain separate because they govern different layers, or be consolidated into a single privacy architecture document with two major sections:

- execution-layer PII exposure
- persistence-layer PII storage and retention

### 7. Testing Architecture

Owner document: `INV-ARC-017_GENERAL_TESTING_INVARIANTS.md`

Owns:

- required coverage categories
- validation reporting
- evidence requirements
- prohibition on unsubstantiated test claims

This may remain standalone because it is a global validation constraint rather than a runtime object.

### 8. Accessibility Architecture

Owner document: `INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`

Owns:

- template accessibility contract
- semantic structure
- keyboard operation
- ARIA naming
- template PR requirements

This may remain standalone because it governs user-facing runtime behavior across the app.

### 9. Cross-Domain Coordination Architecture

Owner document: `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

Owns:

- no direct domain-to-domain calls
- FEAT-only cross-domain coordination
- cross-domain references
- coordination boundaries

This may remain standalone because it defines the legal boundary between DOM and FEAT layers.

---

## VII. Packaging Goal

Target Implementation: v2.5+ to v3.0

All canonical architectural code SHOULD eventually be packaged under a dedicated architectural namespace.

Suggested package structure:

```text
app/architecture/
    execution/
        context.py
        shell.py
        capability.py
        command_boundary.py

    context/
        canonical_context.py
        resolver.py
        switching.py
        isolation.py

    identity/
        canonical_identity.py
        resolver.py
        ownership.py

    temporal/
        evaluation.py
        primitives.py

    audit/
        context.py
        lineage.py
        correlation_pack.py

    privacy/
        pii_contract.py
        retention.py

    coordination/
        feat_boundary.py
```

DOM and FEAT code SHALL import canonical architectural objects from this architectural namespace rather than constructing equivalent logic locally.

---

## VIII. Contributor Rule

Canonical architectural objects are shared authority objects consumed by the entire application.

Contributors SHALL NOT modify a canonical architectural object to satisfy a single feature request.

If a feature appears incompatible with a canonical architectural object, the contributor SHALL determine whether:

1. the feature is incorrect,
2. the feature belongs in a different domain,
3. the existing architecture already provides the correct expression, or
4. the architecture genuinely requires deliberate amendment.

Canonical architectural objects evolve rarely and deliberately. A feature adapts to the invariant; the invariant does not bend around the feature.

---

## IX. Final Statement

An `INV-ARC` is not merely an architecture document.

An `INV-ARC` is the specification for a canonical architectural authority.

If the authority creates a runtime object, the implementation SHALL create exactly one canonical object for downstream consumers.

If the authority defines a global constraint, the implementation SHALL enforce that constraint across all applicable execution paths.

If the proposed authority does neither, it is not an `INV-ARC`.
