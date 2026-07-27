# DOM-POL-001: Policies Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-POL-001 | 1.0 | 2026-07-27 | N/A | Constitutional |

## I. Purpose

Define the Policies domain as the canonical authority over class-scoped feature rules and product specifications.

Policies answers:

- what rules govern an enabled feature;
- what configuration is required for a product to behave lawfully;
- what version of a product or policy was in effect at a particular time;
- what closed rule schema a FEAT must interpret.

Policies does not own class identity, seat identity, money movement, entitlement history, or the operational facts produced when a rule is executed.

## II. Scope

The domain begins when Class Configuration enables a feature or product family that requires typed rules.

The domain ends where another domain records the actual business fact produced under those rules.

Examples:

- payroll policy defines rate, rounding, and schedule;
- hall-pass policy defines queue and destination rules;
- insurance policy defines claim limits, payout ceilings, and coverage behavior;
- rent policy defines frequency, grace, preview, and linked-item rules;
- ledger policy defines overdraft and interest behavior.

## III. Authority Level

Tier 1 — Constitutional. This document defines the authoritative rule contracts consumed by FEATs and downstream business domains.

It is subordinate to:

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`

## IV. Canonical Business Authority

Policies is the sole business authority over:

- feature-specific rule definitions;
- product specifications;
- policy versions and version lineage when the rule changes are part of the policy contract;
- effective dates for policy applicability;
- closed rule schemas for FEAT interpretation.

Policies does not own:

- class existence or class identity;
- seat identity;
- entitlement history;
- obligations history;
- Ledger truth;
- productivity or attendance truth;
- pending action storage;
- display-only state.

## V. Domain Boundary

### A. Owned truth

This domain owns the following permanent truths:

1. A class-scoped rule exists for an enabled feature or product family.
2. The rule has a closed schema and a lawful version lineage.
3. The rule becomes authoritative at its configured effective time.
4. Downstream FEATs may interpret the rule only according to the published schema.

### B. Cross-domain truth

This domain may lawfully reference but does not own:

- class boundary and enablement truth from Class Configuration;
- identity and seat truth from Identity;
- monetary truth from Ledger;
- entitlement lifecycle history from Store and Entitlements;
- obligation lifecycle facts from Obligations;
- productivity, attendance, and hall-pass execution facts from their owning domains.

### C. Derived state

The following SHALL be derived and SHALL NOT be persisted as canonical Policies truth:

- effective current policy as a materialized convenience if the result can be resolved from version + effective date;
- computed eligibility outcomes;
- current claim allowance usage;
- resolved payout amounts;
- remaining limits.

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `policy_definitions`
- `policy_versions`
- `policy_version_effectivity`

The schema MAY be specialized per policy family, but each policy record SHALL remain append-only and versioned.

Policies SHALL NOT store:

- mutable business outcomes;
- entitlement balances;
- Ledger balances;
- obligations balances;
- mutable class identity;
- display-only UI state.

## VII. Canonical Persistence

### A. `policy_definitions`

`policy_definitions` identifies the rule family for the class-scoped policy.

Key fields:

- `policy_id` — primary key for the policy lineage
- `class_id` — FK to `classes`
- `policy_type` — closed enum such as `PAYROLL`, `HALL_PASS`, `INSURANCE`, `RENT`, `LEDGER`
- `created_at`

Rules:

- one logical policy lineage per class and policy family;
- the row names the rule family only;
- the rule details live in version rows.

### B. `policy_versions`

`policy_versions` stores the append-only versioned rule snapshot.

Key fields:

- `policy_version_id` — primary key for the version row
- `policy_id` — FK to `policy_definitions`
- `version_number`
- `effective_at`
- `created_at`
- `payload` — typed JSON rule payload for the policy family

Rules:

- version rows are append-only;
- `version_number` is monotonic within a policy lineage;
- `effective_at` determines when the version becomes authoritative;
- the authoritative policy at time `T` is the newest version in the lineage whose `effective_at <= T`.

### C. `policy_version_effectivity`

`policy_version_effectivity` is optional and may be used only if the implementation needs explicit scheduling metadata separate from the version snapshot.

If present, it SHALL remain append-only and SHALL NOT mutate the underlying version record.

## VIII. Closed Policy Families

Policies MAY define typed rule families such as:

- payroll;
- hall pass;
- insurance;
- rent;
- ledger;
- store product catalog behavior;
- collective-goal configuration.

Each family SHALL have a closed schema. Arbitrary JSON without a validator is prohibited.

## IX. FEAT Consumption Contract

FEATs that depend on policy truth SHALL:

1. identify the policy family required by the operation;
2. resolve the newest lawful version in effect for the canonical temporal context;
3. validate the payload against the family schema;
4. apply the rule to the current authoritative facts of the owning domains;
5. derive outcomes rather than persisting mutable policy state.

Policies SHALL NOT execute the business outcome itself.

## X. Amendment

Revisions must remain consistent with `DOM-CLASS-001`, the owning business domain, and the governing FEAT and temporal invariants.
