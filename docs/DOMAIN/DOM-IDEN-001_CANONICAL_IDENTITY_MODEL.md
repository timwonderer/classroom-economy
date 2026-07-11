# DOM-IDEN-001: Canonical Identity Model

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-001 | 2.2 | 2026-07-10 | 2.1 | Constitutional |

---





## I. Purpose

This document defines the constitutional identities that are valid within the Classroom Token Hub space. Any other identity construction or entity SHALL be considered as invalid and prohibited.

> [!IMPORTANT]
>
> This document defines how Classroom Token Hub constructs canonical identities after the required identity information has been ingested. It governs the construction, binding, lifecycle, and deletion of canonical identity objects.
>
>This document SHALL NOT prescribe how identity information is obtained. Authentication providers, roster sources, district information systems, SSO providers, and other provisioning mechanisms are implementation concerns. Regardless of origin, all identity inputs SHALL be transformed into the canonical identity model defined by this document before participating in the Classroom Token Hub runtime.

---

## II. Scope

This domain governs:

- Human identity (`users`)
- Classroom universes (`classes`)
- Classroom participation (`seats`)
- Human-facing identity (`identity_profiles`)


This domain does **not** govern:
- Teacher onboarding 
- Student roster provisioning 
- Student claim 
- Account recovery 
- Class binding
- Identity lifecycle 
- Identity deletion 
- Runtime request context 
- Financial truth (Ledger)
- Attendance facts
- Store ownership
- Obligations
- Class policy

---

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000`, `INV-CORE-001`, and `INV-ARC-008`.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`

## V. Core Identity and Tenancy

To preserve isolated classroom economies and prevent cross-context authority leaks, Classroom Token Hub separates canonical identity into four distinct architectural responsibilities. Each responsibility owns exactly one concern and SHALL NOT assume responsibilities owned by another identity object.

### `User`
A `User` is the authenticated principal that owns authentication credentials, account lifecycle, recovery, and global authentication state.

### `Class`
A `Class` defines an isolated classroom universe. Every runtime actor, policy, obligation, ledger event, attendance event, and store interaction SHALL occur within exactly one `Class`.

### `Seat`
A `Seat` is the canonical runtime actor within a defined `Class`. It represents the entity that can engage in the classroom economy within the `Class`. A `Seat` represents a single member within the `Class` that is bound to exactly one authenticated `User`.

### `IdentityProfile`
An `IdentityProfile` represents the human-facing display data associated with a `Seat` within a `Class`. Its primary function is ease of use and user experience. `IdentityProfile` SHALL NOT participate in authentication, authorization, ownership determination, canonical context construction, or business logic.

Collectively, these four objects constitute the canonical identity model of Classroom Token Hub. No other object, legacy table, or compatibility bridge may originate identity or classroom participation.


## VI. Participation Model
Participation is represented exclusively through `Seats`. `Users` authenticate the human entity while `Seats` act within the defined economy of `Classes`.

- `Classes` define the universe in which `Seats` act.
- A `User` may participate in multiple `Classes` through multiple `Seats`.
- A `User` may own **at most one `Seat` per `Class`**.
- A `Seat` belongs to exactly one `Class`.

### Participation Existence Law
1. A `User` SHALL exist only while participating in at least one `Class`.
2. Participation is established by binding a `User` to a `Seat`.
3. If a `User` no longer owns any `Seats`, the corresponding `users` row SHALL be removed.
4. This rule applies equally to teachers and students.

### Identity Graph
The following illustration shows how each identity function operates within Classroom Token Hub:

<p align="center"><img src="../assets/DOM-IDEN-001_Identity_Graph.svg" alt="Canonical identity graph. Human exists outside the application boundary. User is the authenticated principal. Class defines an isolated economic universe. Seat is the canonical runtime actor within a Class. IdentityProfile provides human-facing display identity for a Seat and does not participate in authentication, authorization, or business logic." width="500"></p>

## VII. Invariants
- Identity is owned by `Users`.
- Participation is owned by `Seats`.
- `Classes` define participation boundaries.
- One `User` may own many `Seats`.
- One `User` may own at most one `Seat` within a `Class`.
- One `Seat` belongs to exactly one `Class`.
- `IdentityProfiles` never own authentication.
- `Users` SHALL NOT exist without classroom participation.

## VIII. Amendments
Revisions to this document shall:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with INV-CORE-000, INV-ARC-004, and INV-ARC-013
