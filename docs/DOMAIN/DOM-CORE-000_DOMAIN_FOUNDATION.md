# DOM-CORE-000: Domain Foundation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-CORE-000      | 1.1     | 2026-04-18     | 1.0        | Constitutional            |

## I. Purpose
To define the structural boundaries, mutation authority rules, and schema ownership model of independent business domains within the system.

## II. Scope
All internally segregated units of business logic supporting the Classroom Token Hub, including the domain-owned schema contracts for runtime tables.

## III. Authority Level
Foundational. Subordinate to `INV-CORE-000` and `INV-CORE-001`.

## III-A. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`

## IV. Domain Rules

### 1. Logical vs Physical Isolation
Domains represent **logical authority boundaries** for specification, mutation, and schema ownership. Physically, the application still uses a unified ORM and large persona-driven route modules, but that does not create shared authority.

### 2. Mutation Authority
Each domain service is the sole mutation authority over its owned tables. Cross-domain coordination occurs only through FEAT orchestration or service interfaces, never by directly mutating another domain's tables.

### 3. Schema Follows Domain Authority
Every runtime table must have exactly one owning domain.

- Field definitions and constraints are defined exactly once, in the owning domain document.
- Cross-domain references do not create shared ownership.
- A global schema document may summarize or index tables, but it may not become an alternate source of truth.

### 4. The `join_code` Anchor
Regardless of the domain, every class-scoped operation, claim, entitlement, attendance event, or configuration row MUST be anchored to the correct `join_code` or a class identity derived from that scope.

### 5. Shared Ledger, Single Owner
The runtime uses a unified ledger, but that does not imply shared write authority. All ledger rows are owned by the Ledger domain. Other domains may require money effects only through FEAT or `ledger_service`.

## V. Required Sections for Domain Docs

Every V2 domain document SHALL include:

- `Schema Authority Declaration`
- `Owned Tables`
- `Schema Contract`
- `Constraints`
- `Derived / Cross-Domain Rules`

## VI. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
