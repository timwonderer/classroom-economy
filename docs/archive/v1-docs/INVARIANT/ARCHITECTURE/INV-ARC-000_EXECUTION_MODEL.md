# INV-ARC-000: Execution Model

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-000      | 1.1     | 2026-04-13     | 1.0        | Foundational    |

## I. Purpose

This document defines the canonical execution model for Classroom Token Hub.

It is the umbrella `INV-ARC` document that governs how request-time decisions are made
and executed across the system.

## II. Scope

This specification applies to:

- HTTP request handling
- capability evaluation
- domain command execution
- cross-domain interaction
- logging and observability

It is binding on all `DOM` and `FEAT` specifications.

## III. Authority Level

Foundational within the `INV-ARC` namespace. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and Section III.3, `Deterministic and Traceable Financial Logic`, and Section III.4, `Principal and Actor Authority`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`

## V. Core Execution Model

Every request MUST follow this sequence:

1. construct request context
2. evaluate capabilities
3. resolve allow or deny
4. execute a single domain command if allowed
5. return response

No deviation from this sequence is permitted.

## VI. Registered INV-ARC Rules

This execution model is elaborated by the following `INV-ARC` documents:

- `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`
- `INV-ARC-002_NO_IMPLICIT_GLOBAL_ACCESS.md`
- `INV-ARC-003_SCOPED_CAPABILITY_EVALUATION.md`
- `INV-ARC-004_CROSS_TENANT_ISOLATION.md`
- `INV-ARC-005_NO_PII_LEAKAGE_IN_EXECUTION_LAYER.md`
- `INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `INV-ARC-007_GET_MUST_BE_PURE.md`
- `INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `INV-ARC-010_EXPLICIT_CONTEXT_SWITCHING.md`
- `INV-ARC-011_NO_PHANTOM_SCOPE_ACCESS.md`
- `INV-ARC-012_HARD_DELETION_ENFORCEMENT.md`
- `INV-ARC-013_MEMBERSHIP_BY_EXISTENCE.md`
- `INV-ARC-014_NO_LABEL_BASED_LOGIC.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`

## VII. Rebuild Intent

This execution model exists to force the v2 rebuild away from the failure modes already
identified in the architecture audit:

- write-on-read behavior
- unscoped capability decisions
- route-local authorization logic
- recomputed state in features
- cross-domain mutation shortcuts

The rebuild intent is not merely cleaner wording. It is to make those patterns
architecturally invalid so `DOM` and `FEAT` cannot normalize them again.

## VIII. Execution Constraints

### VIII.1 Capability Evaluation

- capability checks must be side-effect free
- capability checks must use explicit context only
- capability checks must be evaluated at request time

### VIII.2 Command Execution

- exactly one command path must execute per request
- commands must be idempotent where applicable
- commands must own all mutation logic

### VIII.3 Cross-Domain Interaction

- domains must not directly mutate other domains
- cross-domain effects must be expressed through approved domain contracts

## IX. Downstream Consequence

`DOM` specifications must expose truth, capability checks, and commands in a way that
fits this request model.

`FEAT` specifications must describe action flow only as orchestration of this model, not
as exceptions to it.

## X. Observability Requirements

All decisions MUST be logged with:

- `request_id`
- `action`
- `capability`
- `domain`
- `allowed`
- `reason` when denied
- `join_code`
- `actor_id`

## XI. Enforcement

The following MUST be enforced through CI and runtime guards:

- no database commits in `GET` routes
- no use of unscoped balance properties in execution paths
- capability checks precede command execution
- no cross-domain mutation

## XII. Final Statement

> Domains declare truth. Invariants govern interaction. Capabilities evaluate authority.
> Features execute decisions.

## XIII. Amendment

Revisions to this document must:

1. increment the version number
2. update the Effective Date
3. maintain alignment with all `INV-CORE` specifications
4. preserve the registered `INV-ARC` rule set
