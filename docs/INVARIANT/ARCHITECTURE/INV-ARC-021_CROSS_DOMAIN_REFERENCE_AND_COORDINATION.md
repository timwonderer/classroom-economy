# INV-ARC-021: Cross-Domain Reference and Coordination Semantics

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-021      | 1.0     | 2026-06-21     | N/A        | Foundational    |

## I. Purpose

Define the canonical rules governing how domains reference, read from, and coordinate with one another at runtime.

## II. Scope

Applies to all inter-domain interaction: imports, data references, capability composition, mutation coordination, and event propagation.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` Section III.3, `Deterministic and Traceable Financial Logic`, and Section III.4, `Principal and Actor Authority`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-000_EXECUTION_MODEL.md`
- `INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`

## V. Core Rules

### V.1 No Direct Domain-to-Domain Calls

A domain MUST NOT import or invoke another domain's internals. No domain service, guard, query, or command may call into another domain's implementation. Domains are isolated units of authority.

### V.2 FEAT as the Sole Coordination Layer

All cross-domain coordination MUST occur inside a FEAT. The FEAT layer is the only construct permitted to compose logic spanning multiple domains within a single execution path.

### V.3 Validation Must Be Side-Effect Free

Domains expose read-only capability checks (guards). A domain MUST NOT mutate state during validation. Guard evaluation is a pure read operation regardless of how many domains a FEAT consults.

### V.4 Shared Identifiers Only

A domain MAY reference another domain's public shared identifiers (`class_id`, `seat_id`, `user_id`). A domain MUST NOT interpret or enforce another domain's business rules based on those identifiers. The identifier is an opaque anchor; its semantics belong to the owning domain.

### V.5 Cross-Domain Reads for Display

Cross-domain data reads for display or presentation purposes are permitted through domain query interfaces. The consuming domain MUST NOT cache, reinterpret, or treat the result as its own authoritative state. Domain authority for state is defined by `INV-ARC-009`.

Display data is not a shared generic view model contract. Each domain that exposes presentation-ready data MUST own the shape of its own display or view object. Page-level orchestration may compose multiple domain-owned presentation objects, but it MUST NOT centralize domain presentation into a single generic builder or reinterpret another domain's display contract as local authority.

### V.6 Capability Composition Restricted to FEAT

Only the FEAT layer may compose capability checks from multiple domains into a single allow/deny decision. No route, background job, CLI script, or domain service may perform multi-domain capability composition.

### V.7 No Foreign Keys to Internal Tables

No domain may hold a foreign key reference to another domain's internal (non-shared) tables. The only legal cross-domain foreign key targets are shared anchor columns: `class_id`, `seat_id`, and `user_id`. All other cross-domain references must be resolved at query time, not enforced at the schema level.

### V.8 Event-Driven Side Effects

If event-driven cross-domain side effects are introduced, each event MUST be:

1. explicitly declared in a FEAT contract
2. auditable with a traceable `request_id` and originating FEAT identifier
3. idempotent on replay
4. subject to the same capability and scoping rules as synchronous execution

Implicit, unregistered, or untraceable cross-domain side effects are forbidden.

## VI. Rebuild Intent

This rule exists to eliminate cross-domain coupling patterns identified in the architecture audit: direct service-to-service imports, domain logic scattered across route handlers, and hidden inter-domain dependencies that bypass the FEAT orchestration boundary.

## VII. Downstream Consequence

`DOM` specifications MUST NOT declare dependencies on other `DOM` specifications. `FEAT` specifications MUST declare all domains they coordinate across. Routes and background jobs MUST delegate all multi-domain logic to a FEAT.

## VIII. Amendment

Revisions must preserve strict domain isolation and FEAT-only coordination.
