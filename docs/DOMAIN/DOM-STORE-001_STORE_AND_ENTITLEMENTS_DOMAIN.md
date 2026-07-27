# DOM-STORE-001: Store and Entitlements Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-STORE-001 | 4.0 | 2026-07-27 | 3.0 | Normative |

## I. Purpose

Define the Store and Entitlements domain as the canonical authority over what a seat is entitled to and how that entitlement changes over its lifecycle.

This domain records:

- which configured capability was granted to which seat;
- which immutable entitlement lifecycle facts occurred after the grant;
- which entitlement actions are pending authoritative resolution.

This domain does not own class configuration, feature policy, monetary truth, obligations, or the external business event produced by exercising an entitlement when another domain owns that event.

## II. Scope

The domain begins when a configured capability or product is lawfully granted to a seat.

The domain ends where another domain owns the authoritative business fact produced by exercising the entitlement.

Examples:

- a late-use entitlement is granted and later consumed entirely inside Store and Entitlements;
- an insurance entitlement is granted here, but the lawful insurance entitlement outcome may coordinate with Ledger and may carry the claim subject in its canonical payload;
- a hall pass entitlement is granted here, but the authoritative consumption event is recorded by the Productivity/Hall-Pass domain;
- a pending delayed-use redemption is preserved here until the lawful FEAT resolves it.

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants.

It is subordinate to:

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`

## IV. Canonical Business Authority

The Store and Entitlements domain is the sole business authority over:

- entitlement grant lineage;
- entitlement exercise lineage when Store and Entitlements owns the exercise;
- entitlement lifecycle facts for all entitlement types the domain owns;
- pending entitlement actions awaiting authoritative resolution.

The domain does not own:

- class configuration;
- policy definitions;
- monetary balances or Ledger transactions;
- obligations assessments or satisfaction truth;
- productivity or attendance truth;
- the external business event owned by another domain when that event is the authoritative result of exercising the entitlement;
- derived availability, balance, or remaining-use counts.

Consumers SHALL NOT:

- maintain entitlement counts independently;
- persist `uses_remaining`, `bundle_remaining`, `remaining_claims`, or equivalent mutable entitlement balances;
- infer entitlement existence from labels, cached UI state, or route-local calculations;
- treat a configured product definition as proof that a seat possesses the corresponding entitlement;
- mutate Store and Entitlements persistence directly outside FEAT;
- duplicate another domain's authoritative exercise record.

## V. Domain Boundary

### A. Owned truth

This domain owns the following permanent truths:

1. A specific entitlement was granted.
2. The entitlement belongs to a specific `target_seat_id` within a specific `class_id`.
3. A specific `actor_seat_id` caused or authorized the entitlement event.
4. The entitlement refers to a specific configured product definition from the Policies domain.
5. The grant or subsequent event has a specific provenance.
6. The entitlement event may participate in a specific correlated cross-domain operation.
7. A Store-and-Entitlements-owned entitlement was consumed, expired, or lawfully revoked.
8. A claim-like or redemption-like action was submitted and remains pending authoritative resolution.
9. The pending action preserves the canonical submission timestamp and the authoritative FEAT that must resolve it.
10. The canonical payload for an entitlement event records the type-specific facts necessary to interpret that event.

### B. Cross-domain truth

This domain may lawfully reference but does not own:

- class boundary and actor resolution from Class Configuration and Identity;
- product definitions and policy terms from Policies;
- Ledger transactions used as purchase funding or coordinated reimbursement truth;
- Productivity, Attendance, or Hall-Pass facts used to evaluate an entitlement action;
- obligation facts that cause a grant or coordinated entitlement effect.

### C. Derived state

The following SHALL be derived and SHALL NOT be persisted as canonical Store and Entitlements truth:

- entitlement balance;
- available count;
- remaining uses;
- remaining claims;
- current display status such as `active`, `used`, `expired`, or `redeemed` when deterministically derivable from canonical facts and policy;
- approval history summaries when those summaries can be derived from immutable facts.

### D. Display-only state

Names, class labels, product labels, descriptions, and other presentation metadata SHALL be resolved through the lawful display/view-model pipeline and SHALL NOT be cached into canonical Store and Entitlements rows merely for presentation convenience.

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `entitlement_events`
- `pending_actions`

The following legacy or superseded persistence concepts are not part of the v4 canonical Store and Entitlements contract:

- `entitlements` as a mutable grant table separate from lifecycle facts;
- `entitlement_consumptions` as a separate terminal-history table;
- `insurance_claims` as a separate mutable workflow table;
- `store_purchases`;
- `redemption_events`;
- domain-owned `store_items`;
- domain-owned `store_item_visibility`;
- persisted purchase quantity as entitlement truth;
- `uses_remaining`;
- `bundle_remaining`;
- mutable purchase lifecycle status used as entitlement authority;
- separate obligation-owned entitlement stores.

Store and Entitlements SHALL consume product and policy definitions from the Policies domain and SHALL treat those definitions as external authority.

## VII. Canonical Persistence

### A. `entitlement_events`

`entitlement_events` is append-only canonical entitlement history.

One row represents one immutable entitlement fact.

Key fields:

- `event_id` — primary key for the row
- `entitlement_id` — internal Store/Entitlements lineage key for the entitlement lifecycle
- `class_id` — FK to `classes`; canonical class boundary
- `target_seat_id` — FK to `seats`; seat that possesses or is affected by the entitlement
- `actor_seat_id` — FK to `seats`; teacher seat or student seat that lawfully caused the event
- `product_id` — FK/reference to Policies product definition
- `entitlement_type` — closed enum of lawful entitlement kinds
- `acquisition_type` — closed enum describing how the entitlement arose
- `event_type` — `GRANTED` | `CONSUMED` | `EXPIRED` | `REVOKED`
- `correlation_id` — identifier tying the event to the coordinated lifecycle or cross-domain operation
- `payload` — JSON payload containing type-specific canonical facts required to interpret the event
- `timestamp` — canonical timestamp

Closed `entitlement_type`:

- `INSURANCE`
- `PRIVILEGE`
- `IMMEDIATE_USE`
- `DELAYED_USE`
- `COLLECTIVE_GOAL`
- `HALL_PASS`

Closed `acquisition_type`:

- `PURCHASE`
- `GRANT`
- `PERK`

Actor rules:

- `actor_seat_id` SHALL always be a real seat.
- For teacher-directed or system-originated class actions, `actor_seat_id` is the teacher seat for the class.
- For student-originated actions, `actor_seat_id` is the student seat.

Rules:

- `entitlement_id` SHALL remain stable across the lifecycle of the same entitlement.
- `event_id` identifies one immutable row only.
- `correlation_id` is cross-domain lineage.
- `entitlement_id` is internal Store/Entitlements lifecycle lineage.
- `product_id` SHALL refer to a Policy-owned product definition lawful for the same class boundary.
- `payload` SHALL contain only the type-specific authoritative facts necessary to interpret the event.
- `payload` SHALL NOT duplicate monetary truth, policy rules, or derived balances.
- `entitlement_events` SHALL NOT contain quantity, remaining balance, mutable redemption status, or display metadata.
- Grant rows SHALL NOT be edited to represent later consumption.
- Lawful lifecycle permutations are determined by `entitlement_type` and `acquisition_type` and SHALL be constrained by the domain contract.

### B. `pending_actions`

`pending_actions` is the durable unresolved entitlement-action table.

One row represents one submitted entitlement action that has not yet reached canonical resolution.

Key fields:

- `pending_action_id` — primary key for the row
- `class_id` — canonical class boundary
- `seat_id` — seat that submitted or will be affected by the pending action
- `correlation_id` — identifier tying the pending action to the cross-domain operation
- `entitlement_id` — entitlement lifecycle being acted upon
- `authoritative_feat` — the FEAT that is lawfully authorized to resolve the pending action
- `payload` — canonical typed request inputs produced and validated by the submitting FEAT and required by the authoritative FEAT for later resolution
- `submitted_at` — canonical submission timestamp

Rules:

- `pending_actions` exists only while an entitlement action is unresolved.
- `authoritative_feat` SHALL identify the one lawful FEAT path for resolution.
- `payload` SHALL be the canonical typed request envelope produced and validated by the submitting FEAT, not an arbitrary dump of unrelated state.
- `submitted_at` is authoritative and SHALL be preserved.
- No generic TTL may delete pending actions.
- A pending action is not canonical entitlement history.
- A successful resolution SHALL atomically write the canonical entitlement event(s) and delete the pending action.
- A failed resolution SHALL leave the pending action intact.

## VIII. Entitlement Semantics

### A. Grant semantics

`GRANTED` records that the seat acquired the entitlement.

The grant payload MAY be small and need only preserve the minimal authoritative facts required by the entitlement type.

### B. Consumption semantics

`CONSUMED` records that the entitlement was exercised or otherwise reached final disposition for the lawful entitlement lifecycle.

For entitlement types where the exercise is repeatable, multiple `CONSUMED` rows MAY exist for the same `entitlement_id`.

For entitlement types where the exercise is terminal, `CONSUMED` ends the entitlement lifecycle unless the type explicitly allows further terminal facts.

### C. Expiration semantics

`EXPIRED` records that the entitlement ceased to be exercisable because the configured validity period or goal boundary ended without further lawful exercise.

### D. Revocation semantics

`REVOKED` records that an otherwise-valid entitlement was lawfully withdrawn through an authorized revocation path.

Revocation law is entitlement-type specific.

### E. Type-specific rules

#### 1. Insurance

Insurance is a continuing entitlement lifecycle.

An insurance purchase SHALL create an entitlement grant and may coordinate an initial obligation assessment/payment lifecycle in the lawful Obligations and Ledger paths.

Insurance claims SHALL be represented through the `pending_actions` path before resolution.

Insurance claim validation SHALL distinguish:

- structural invalidity, which MAY prevent PendingAction creation; and
- policy ineligibility, which SHALL NOT by itself prevent submission where teacher adjudication applies.

Failed policy evaluation SHALL be preserved on the pending action and presented during adjudication.

When an insurance claim is adjudicated, both accepted and rejected claims SHALL record `CONSUMED` as the canonical entitlement event for that claim exercise.

The entitlement event payload SHALL preserve the claimed subject and canonical outcome data required for future eligibility checks.

The entitlement event SHALL NOT duplicate Ledger monetary truth.

The corresponding Ledger event, when any, SHALL remain Ledger authority.

Upon lawful resolution of an insurance claim:

- the insurance entitlement SHALL record a `CONSUMED` event;
- the event payload SHALL preserve the claimed subject and any canonical result data required by future eligibility checks;
- the pending action SHALL be removed.

Insurance claims MAY be repeated against the same entitlement until the governing policy or cycle boundaries are reached.

#### 2. Privilege

Privilege represents a non-counted state such as permission to choose a seat or similar class privilege.

Privilege entitlements SHALL:

- grant `GRANTED`;
- end by `EXPIRED` or `REVOKED`;
- not use `CONSUMED`.

#### 3. Immediate use

Immediate-use entitlements are granted and consumed within the same lawful coordinated action.

Immediate-use entitlements SHALL:

- grant `GRANTED`;
- immediately record `CONSUMED`;
- not use `REVOKED`.

#### 4. Delayed use

Delayed-use entitlements may be redeemed later.

Delayed-use entitlements SHALL:

- grant `GRANTED`;
- support a pending action before resolution;
- record `CONSUMED` on successful redemption;
- record `REVOKED` when redemption is rejected and the entitlement is returned/refunded through the lawful reversal path;
- record `EXPIRED` when the configured expiration boundary is reached without lawful exercise.

#### 5. Collective goal

Collective-goal entitlements are granted under a configured threshold or deadline and may be consumed when the configured collective conditions are satisfied.

Collective-goal entitlements SHALL:

- grant `GRANTED`;
- support `CONSUMED` when lawfully exercised;
- record `EXPIRED` when the goal is not reached by the deadline and coordinate a lawful refund;
- record `REVOKED` when the entitlement is withdrawn individually or classwide and coordinate a lawful refund.

#### 6. Hall pass

Hall-pass entitlements are granted here, but their authoritative exercise may be recorded by another domain.

Hall-pass entitlements SHALL:

- grant `GRANTED`;
- support pending action if the exercise requires approval;
- record `EXPIRED` when a perk-based pass reaches the end of the governing rent period without exercise;
- permit `REVOKED` only for direct-grant hall passes when the governing policy allows revocation;
- not create a duplicate Store-and-Entitlements `CONSUMED` row when another domain is the authoritative consumer.

## IX. Pending Action Semantics

`pending_actions` stores durable unresolved entitlement actions.

The row is a deferred FEAT invocation envelope.

The `authoritative_feat` field SHALL identify the canonical FEAT that will resume or finalize the action.

The `payload` SHALL contain the canonical request inputs, and those inputs SHALL be the same inputs that the authoritative FEAT would accept if the action had been executed synchronously.

The `submitted_at` timestamp is authoritative for any rule that depends on submission-time truth.

Examples:

- an insurance claim submitted while coverage is valid remains eligible even if coverage expires before review;
- a delayed-use redemption submitted before expiration remains governed by the submission timestamp where the policy requires that boundary;
- a hall-pass request remains pending until the authoritative FEAT resolves it.

Pending actions SHALL be deleted only as part of successful lawful resolution or lawful deletion of the governing class boundary.

Pending actions SHALL NOT be interpreted as entitlement consumption, approval, rejection, or revocation.

## X. Cross-Domain Contracts

### A. Policies

The Policies domain owns product definitions and versioned feature rules.

Store and Entitlements SHALL consume:

- the configured product identity;
- the product type;
- the active product version or version lineage;
- the product-specific rule payload.

Store and Entitlements SHALL NOT mutate policy definitions directly.

### B. Class Configuration

Class Configuration owns the class universe, enabled features, and class-wide economic environment.

Store and Entitlements may consume class configuration for:

- entitlement availability;
- feature enablement;
- product activation;
- class-scoped visibility;
- grant eligibility;
- policy mode or economic multipliers where the product definition requires them.

### C. Ledger

Ledger owns all monetary truth.

Store and Entitlements may:

- reference Ledger transactions as purchase funding;
- reference Ledger transactions or results as canonical monetary evidence;
- coordinate a lawful Ledger credit/debit through FEAT.

Store and Entitlements SHALL NOT directly write Ledger persistence outside the lawful Ledger mutation boundary.

### D. Productivity and Attendance

Store and Entitlements may read Productivity or Attendance facts only when a product or entitlement type lawfully depends on them.

The authoritative attendance or productivity record SHALL remain in the owning domain.

### E. Obligations

Obligations may cause entitlement grants or coordinated entitlement effects.

Store and Entitlements SHALL not duplicate obligation truth.

### F. Other domains

When an entitlement type produces a business event owned by another domain, that domain owns the authoritative exercise record.

Store and Entitlements may lawfully read that authoritative record for availability or lifecycle projections.

## XI. Projection Rules

Availability, remaining uses, remaining claim counts, and display status SHALL be derived from:

- canonical entitlement event history;
- lawful pending action state;
- governing policy or product version;
- canonical temporal context;
- authoritative cross-domain records when another domain owns the exercise or settlement fact.

The following SHALL NOT be persisted as canonical truth:

- `uses_remaining`;
- `bundle_remaining`;
- entitlement quantity;
- remaining claims;
- current active/used state;
- current claim allowance;
- current payout allowance;
- other mutable balance-like fields.

## XII. Guarantees

This domain guarantees:

- entitlement facts are immutable;
- pending actions preserve unresolved user intent without pretending to be canonical outcome history;
- product rules are consumed from Policies, not recreated in Store and Entitlements;
- monetary truth remains Ledger-owned;
- other domains retain authority over their own exercise or settlement records;
- availability is derived, not stored;
- no compatibility bridge is required for v4 canonical behavior.
