# INV-ARC-022: Request Context and Page Rendering Pipeline

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-022 | 1.0 | 2026-08-06 | N/A | Foundational |

## I. Purpose

Define the canonical request-to-page rendering pipeline for CTH.

This invariant establishes the architectural separation between runtime authority, temporal interpretation, presentation metadata, domain read models, and template rendering.

---

## II. Scope

Applies to:

- authenticated page requests
- route handlers
- request context assembly
- page rendering
- page view models
- template rendering

Does not govern:

- mutation authority
- domain ownership
- FEAT orchestration
- persistence contracts

---

## III. Authority Level

Foundational within `INV-ARC`.

Derived from:

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`

Governed in conjunction with:

- `INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

---

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

---

## V. Core Rules

### V.1 Canonical Rendering Pipeline

Every authenticated page request MUST follow the canonical rendering pipeline.
```
Request
    ↓
Canonical Context
    ↓
Temporal Context
    ↓
Identity Display Context
    ↓
Lawful Domain Reads / FEAT Commands
    ↓
Page View Model
    ↓
Template
```
No layer may be skipped, reordered, or merged unless explicitly authorized by a governing architectural invariant.

---

### V.2 Separation of Architectural Responsibility

Each layer exists to answer exactly one architectural question.

| Layer | Question |
|--------|----------|
| Canonical Context | What makes you think you can do this? |
| Temporal Context | What time do you think it is? |
| Identity Display Context | How are you presented here? |
| Page View Model | What information belongs on this page? |

A layer MUST NOT answer another layer's question.

Architectural boundaries are defined by responsibility, not by implementation convenience.

---

### V.3 Canonical Context Is Authority Only

Canonical Context defines execution authority.

It MAY contain only canonical execution identity such as:

- `user_id`
- `seat_id`
- `class_id`
- `actor_role`

It MUST NOT contain:

- presentation metadata
- page-specific data
- business projections
- display formatting
- temporal interpretation

---

### V.4 Temporal Context Is Interpretation Only

Temporal Context defines how time is interpreted.

It determines temporal authority only.

It MUST NOT:

- authorize operations
- expose presentation metadata
- compute unrelated business projections
- replace Canonical Context

---

### V.5 Identity Display Context Is Presentation Only

Identity Display Context provides reusable presentation metadata.

It MUST be derived from canonical identity and class records.

It MUST NOT:

- authorize operations
- own business state
- expose legacy identity authority
- duplicate Canonical Context

---

### V.6 Page View Models Are Read Projections

A Page View Model is the presentation contract for one rendered surface.

A Page View Model MUST:

- be built from lawful domain reads
- expose presentation-ready data
- hide persistence shape
- remain independent of storage implementation

A Page View Model MUST NOT:

- mutate state
- own business authority
- perform authorization
- become a persistence model

---

### V.7 Domain Ownership of Presentation

Each domain owns the presentation shape of the information it exposes.

Page-level composition MAY aggregate multiple domain-owned presentation objects into a single page contract.

Page composition MUST NOT:

- reinterpret another domain's presentation contract
- duplicate another domain's business logic
- centralize unrelated domain presentation into a generic builder

---

### V.8 Templates Are Pure Consumers

Templates consume presentation contracts.

Templates MUST NOT:

- query persistence
- compute authoritative business state
- reconstruct domain logic
- perform authorization
- derive canonical context

Templates exist solely to render the supplied presentation contract.

---

### V.9 Routes Assemble the Pipeline

Routes coordinate pipeline execution.

Routes MAY:

- resolve canonical context
- resolve temporal context
- assemble identity display context
- invoke lawful domain reads
- assemble page view models

Routes MUST NOT:

- reconstruct domain truth
- duplicate business calculations
- become business services
- become presentation models

---

## VI. Architectural Intent

This invariant separates execution authority, temporal interpretation, presentation identity, domain projections, and rendering into independent architectural layers.

The objective is to eliminate duplicated business decisions across routes, templates, and presentation code while preserving strict ownership boundaries between runtime authority, domain authority, and presentation.

---

## VII. Downstream Consequences

Domain specifications MAY define presentation read models.

FEAT specifications MAY coordinate mutations but MUST NOT construct page rendering contracts.

Routes MUST assemble page rendering through the canonical rendering pipeline.

Templates MUST consume page view models rather than persistence objects.

Future abstractions MUST fit within this pipeline rather than introducing parallel rendering paths.

---

## VIII. Amendment

Revisions must preserve:

- the canonical rendering pipeline
- strict separation of authority, interpretation, presentation, and rendering
- domain ownership of presentation contracts
- template purity
- route orchestration without business ownership