# DOM-POL-001: Policies Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-POL-001 | 2.0 | 2026-07-28 | 1.0 | Constitutional |

## I. Purpose

Define the Policies domain as the class-scoped reference library for teacher-defined products, rules, and entitlements.

Policies answers:

- what definition a teacher configured for a specific capability or product family;
- which exact immutable definition UUID applies to a specific row;
- what contract terms a downstream domain may consume at creation time;
- what class-scoped configuration item is currently selectable for new work.

Policies does not own class identity, class feature enablement, seat identity, money movement, obligations truth, entitlement history, or any other operational fact created after a Policy definition is consumed.

Policies rows are locators, not foreign keys. A row has:

- an immutable `policy_uuid`;
- an immutable family/product identity;
- an immutable definition payload;
- a mutable availability state.

Consumers use the `policy_uuid` to locate the exact definition. Downstream facts own any terms they must preserve after the Policy row is later hidden, retired, or deleted.

## II. Scope

The domain begins when a teacher submits a policy definition for a class-scoped capability.

The domain ends where another domain records the actual business fact produced from that definition.

Examples:

- rent settings define the current or future rent contract and its rent-linked items;
- store items define purchasable or rent-linked entitlement offerings;
- insurance definitions define the insurance product and its claim/coverage terms;
- any other teacher-defined policy family follows the same pattern.

## III. Authority Level

Tier 1 — Constitutional. This document defines the authoritative rule contracts consumed by FEATs and downstream business domains.

It is subordinate to:

- `../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-012_HARD_DELETION_ENFORCEMENT.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-013_MEMBERSHIP_BY_EXISTENCE.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `../INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`

## IV. Canonical Business Authority

Policies is the sole business authority over:

- class-scoped policy definitions for teacher-customized products and rules;
- immutable policy UUIDs that identify exact definitions;
- the payload contract required for downstream domains to consume a definition;
- policy availability for new work.

Policies does not own:

- class existence or class identity;
- feature enablement;
- seat identity;
- entitlement history;
- obligations history;
- Ledger truth;
- productivity or attendance truth;
- display-only state.

## V. Domain Boundary

### A. Owned truth

This domain owns the following permanent truths:

1. A class-scoped policy definition exists for a family or product concept.
2. The policy has a stable `policy_uuid` that identifies the exact definition.
3. The definition payload is immutable after insert.
4. The policy availability state determines whether the definition may be used for new work.
5. A downstream fact may record the `policy_uuid` it used for provenance.
6. A downstream fact that must remain executable after Policy removal must own the terms it needs.

### B. Cross-domain truth

This domain may lawfully reference but does not own:

- class boundary and enablement truth from Class Configuration;
- identity and seat truth from Identity;
- monetary truth from Ledger;
- entitlement lifecycle history from Store and Entitlements;
- obligation lifecycle facts from Obligations;
- operational execution facts from their owning domains.

### C. Derived state

The following SHALL be derived and SHALL NOT be treated as canonical Policies truth:

- current visible item list;
- computed eligibility outcomes;
- current claim allowance usage;
- resolved payout amounts;
- remaining limits;
- downstream business facts.

## VI. Insert and Availability Contract

### 0. `policy_uuid` is the version

`policy_uuid` **is** the version identifier for a policy definition. There is no separate version pointer, version number, or active/next-version column layered on top of it.

- Each row in the Policies repository has exactly one immutable `policy_uuid`, assigned at insert and never rewritten.
- Every new submission (first-time or resubmission of an existing family) produces a new row with a new `policy_uuid`.
- Consumers pin provenance by recording the exact `policy_uuid` in force at the moment they created their operational fact (see `DOM-POL-001` §V.A and §VII).
- Availability state (`IN_USE` / `HIDDEN` / `RETIRED`) is a mutable projection *over* the immutable row, not a version pointer.

Any schema element that attempts to create an alternative "current version" or "next version" pointer alongside `policy_uuid` — whether a self-referential FK on a Policies table or an external version-tracking table — is redundant and prohibited. `DOM-CLASS-003` (`policy_versions` / `policy_transitions`) records economic-policy evolution only and is not a domain-policy versioning mechanism; per `DOM-CLASS-003` §V, domain-specific versioning belongs here.

### 1. Repository behavior

Policies is an append-only, immutable repository. It does not originate mutation flows on behalf of other domains — the domain that initiates a policy change (Class Config UI, insurance authoring flow, store curation flow, etc.) submits a new definition through Policies, and Policies records it as a new immutable row keyed by a new `policy_uuid`.

FEAT-POL is the only surface through which rows enter or change availability in this repository.

It supports only these user-visible actions:

1. Insert: record a new policy definition row with a new `policy_uuid` (may be a first-time submission or a resubmission of an existing family)
2. Disable: mark an existing row `HIDDEN` (availability projection only; the definition payload is untouched)
3. Retire: mark an existing row `RETIRED` (availability projection only; the definition payload is untouched)
4. Delete: remove a retired policy row after all live dependencies have drained

Any submission — first-time or resubmission — produces a new `policy_uuid`. The backend MUST NOT infer whether a change is meaningful; a submission is a new contract.

Definition payload columns are immutable after insert. There is no "update in place."

When a teacher resubmits Rent Settings, Store Items, Insurance settings, or any other policy family, the result is a new immutable row with a new `policy_uuid`. Prior rows remain readable for provenance.

`HIDDEN` means temporarily unavailable for new selection and may later return to `IN_USE`.
`RETIRED` means permanently unavailable for new selection and may remain readable while live dependencies drain.

## VII. Downstream Domain Contract

Policies is a reference library, not a runtime dependency for already-created facts.

Downstream domains must take the terms they need at the moment they create their own authoritative fact.

Examples:

- an entitlement created from a Store item must carry the terms it needs to keep executing even if the source Policy row is later removed;
- an obligation assessment must carry the terms it needs to interpret that assessment without rereading the source Policy row later;
- a rent-linked entitlement created from a rent cycle must be able to stand on its own until the rent-period boundary closes it out;
- an insurance entitlement must carry the limits, benefits, and claim rules needed for later claim processing.

Policies may be consulted during creation, but they are not the authority for the later operational fact.

## VIII. FEAT-POL Contract

FEAT-POL actions:

- `New` creates a new policy row and immutable definition.
- `Update` creates a new policy row with a new `policy_uuid`.
- `Disable` sets the current row to `HIDDEN`.
- `Retire` sets the current row to `RETIRED`.
- `Delete` removes a retired row only when live dependencies have drained.

FEAT-POL MUST NOT mutate downstream domain facts directly.
FEAT-POL MUST NOT rewrite historical downstream facts to match changed policy terms.

## IX. Persistence and Schema Status

The v2 persistence model is:

- one immutable `policy_uuid` per policy definition row;
- one stable family/product identity per policy concept;
- one mutable availability state per row;
- one immutable definition payload per row;
- no foreign keys from downstream domains to Policies;
- downstream domains store `policy_uuid` as a non-FK locator and freeze the terms they need;
- rent-linked item rows may exist before a rent cycle becomes current, but they are not reachable until OBL makes their rent UUID current.

Availability states:

- `IN_USE` - selectable for new work if the current class/cycle rules make it reachable
- `HIDDEN` - not selectable for new work, but may return to `IN_USE`
- `RETIRED` - not selectable for new work, may remain readable while live dependencies drain, and may later be physically deleted

Definition payloads are immutable after insert.
Replacement creates a new `policy_uuid`.
Deletion is allowed only after live dependencies drain.

## X. Boundary Examples

The intended boundary is:

- rent enablement -> Class Configuration
- rent settings -> Policies
- rent-granted items -> Store and Entitlements
- payroll enablement -> Class Configuration
- payroll settings (wage rate, frequency, reward/fine catalog) -> Policies
- payroll events -> Productivity & Payroll (`DOM-PROD-001`)
- hall-pass enablement -> Class Configuration
- hall-pass settings (allowed destinations, limits) -> Policies
- hall-pass consumption records -> Productivity & Payroll (`DOM-PROD-001`)
- store offerings -> Policies
- insurance definitions -> Policies
- insurance entitlement lifecycle -> Store and Entitlements
- banking / interest / overdraft (savings APY, overdraft fees, interest formulas) -> Class Configuration / `economic-engine` (**not** Policies)

This means Class Configuration decides whether a capability exists in the class, Policies stores the class-customized reference material for that capability as immutable version rows, and the consuming operational domain owns the resulting fact.

## XI. Amendment

Revisions must remain consistent with `DOM-CLASS-001`, the consuming operational domain, and the governing FEAT and temporal invariants.
