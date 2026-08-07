# SPEC-UI-001: Canonical Page Rendering Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-UI-001 | 1.0 | 2026-08-06 | N/A | Normative |

---

## I. Purpose

This specification defines the canonical implementation of the CTH page rendering subsystem.

It establishes the required implementation patterns for authenticated page routes, page view models, builder organization, template composition, and presentation contracts.

Architectural constraints are governed by `INV-ARC-022_REQUEST_CONTEXT_AND_PAGE_RENDERING_PIPELINE.md`.

---

## II. Scope

Applies to:

- authenticated page routes
- page rendering
- page view models
- presentation builders
- template composition
- request context assembly

Does not govern:

- domain authority
- mutation authority
- persistence contracts
- FEAT orchestration

---

## III. Authority Level

Normative.

This specification defines the canonical implementation of the CTH page rendering subsystem.

Implementations SHALL conform to this specification unless superseded by a higher architectural authority.

---

## IV. Dependencies

- `INV-ARC-022_REQUEST_CONTEXT_AND_PAGE_RENDERING_PIPELINE.md`
- `INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- Relevant DOM specifications

---

## V. Canonical Page Structure

Every authenticated page SHALL be implemented using the canonical rendering pipeline defined by `INV-ARC-022`.

A page SHALL expose:

- shared request context
- one page view model

The route SHALL assemble these objects before rendering.

---

## VI. Page View Models

Every rendered page SHALL expose exactly one page view model.

The page view model SHALL represent the complete presentation contract for the rendered surface.

A page view model SHALL:

- expose presentation-ready fields
- hide persistence implementation
- remain immutable after construction
- be independent of database schema

A page view model SHALL NOT:

- mutate application state
- perform authorization
- expose persistence models
- contain business authority

---

## VII. Builder Responsibilities

Builders SHALL construct page view models.

Builders SHALL:

- invoke lawful domain read services
- compose presentation objects
- normalize presentation data
- return immutable page contracts

Builders SHALL NOT:

- perform persistence writes
- bypass domain services
- duplicate domain calculations
- authorize requests

---

## VIII. Domain-Owned Presentation

Each domain SHALL own the presentation contract for the information it exposes.

A consuming page MAY compose multiple domain-owned presentation objects into a single page view model.

A consuming page SHALL NOT:

- reinterpret another domain's presentation contract
- duplicate another domain's business calculations
- expose another domain's persistence structures

---

## IX. Builder Organization

Presentation builders SHALL remain domain-local.

Example:

app/

    identity/
        builders.py

    ledger/
        builders.py

    payroll/
        builders.py

    obligations/
        builders.py

    store/
        builders.py

Cross-domain pages SHALL compose domain-owned builders rather than replacing them with generic presentation builders.

---

## X. Template Contract

Templates SHALL receive:

- shared request context
- one page view model

Templates SHALL NOT receive:

- ORM models
- persistence entities
- raw database rows
- domain services

Templates SHALL NOT:

- query persistence
- evaluate business rules
- compute business state
- authorize operations

Templates exist solely to render the supplied presentation contract.

---

## XI. Route Responsibilities

Routes SHALL:

- resolve request context
- invoke lawful builders
- assemble the page view model
- render the template

Routes SHALL NOT:

- duplicate business calculations
- assemble persistence objects for templates
- perform presentation formatting better suited to builders
- own business logic

---

## XII. Standard Page Composition

A page spanning multiple domains SHALL follow this composition pattern:

Route
    ↓
Domain Builders
    ↓
Page View Model
    ↓
Template

The route owns composition.

Each domain owns its presentation contract.

The template owns rendering.

---

## XIII. Conformance

A page conforms to this specification when:

- it follows the rendering pipeline defined by `INV-ARC-022`
- it exposes exactly one page view model
- presentation is produced by lawful builders
- templates consume presentation contracts only
- routes contain no duplicated business logic
- domain ownership boundaries remain intact

---

## XIV. Reference Implementations

The following implementations are considered canonical examples of this specification:

- Student Dashboard
- Student Payroll
- Teacher Payroll
- Student Obligations
- Teacher Obligations

These examples are informative and do not supersede this specification.

---

## XV. Amendment

Revisions shall preserve:

- domain ownership of presentation
- immutable page view models
- builder-based composition
- template purity
- the rendering pipeline established by `INV-ARC-022`