# DOM-STORE-001: Store and Entitlements Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-STORE-001 | 3.0 | 2026-07-22 | 2.2 | Normative |

## I. Purpose

Define the Store and Entitlements domain as the canonical authority over the economic lifecycle of acquired capabilities.

This domain records:

- which atomic capabilities have been granted to a seat;
- how Store-and-Entitlements-owned entitlements have been consumed, expired, or lawfully revoked;
- insurance claim lifecycle when insurance grants the right to request evaluation of an eligible event.

This domain does not own the configuration that defines what capabilities or insurance products exist. Those definitions belong to the Class Configuration domain.

This domain does not own monetary truth. Monetary effects are posted only through the lawful Ledger boundary.

## II. Scope

The Store and Entitlements domain begins when a configured capability is granted to a seat.

A capability may be granted through:

- purchase;
- manual grant; or
- obligation-related grant.

Each grant creates one or more atomic entitlement records.

An entitlement represents one independently exercisable capability unless the configured item is an insurance product. Insurance is a conditional entitlement: acquisition grants the target seat the right to submit qualifying events for evaluation under the referenced insurance configuration.

This domain owns exercise history only when no other domain owns the authoritative business event produced by exercising the entitlement.

Examples:

- a late-work pass redemption is owned by Store and Entitlements and is written to `entitlement_consumptions`;
- a hall-pass entitlement is consumed through the Productivity and Payroll domain, whose `hall_pass_logs` record is the authoritative consumption event;
- an approved transaction-based insurance claim coordinates a compensatory Ledger credit;
- an approved productivity-based insurance claim coordinates creation of a Payroll `MANUAL_CREDIT`, which is then posted to Ledger through the Productivity and Payroll FEAT path;
- an approved non-monetary insurance claim ends within this domain because the resulting external benefit is outside CTH authority.

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

- atomic entitlement grants;
- entitlement provenance;
- Store-and-Entitlements-owned redemption events;
- insurance claim lifecycle;
- entitlement availability projections derived from canonical grants and lawful consumption events.

The domain does not own:

- store item configuration;
- insurance configuration;
- class configuration;
- monetary balances or Ledger transactions;
- productivity or attendance truth;
- payroll truth;
- obligation assessments or satisfaction truth;
- consumption events whose business meaning is owned by another domain.

Consumers SHALL NOT:

- maintain entitlement counts independently;
- persist `uses_remaining`, `bundle_remaining`, or equivalent mutable entitlement balances;
- infer entitlement existence from labels, cached UI state, or route-local calculations;
- duplicate a consumption event already owned by another domain;
- directly mutate Store and Entitlements persistence;
- treat a configured item definition as proof that a seat possesses the corresponding entitlement.

Consumers SHALL use the canonical Store and Entitlements read and mutation surfaces.

## V. Domain Boundary

### A. Owned truth

This domain owns the following permanent truths:

1. A specific atomic entitlement was granted.
2. The entitlement belongs to a specific target seat within a specific class.
3. A specific actor seat caused or authorized the grant.
4. The entitlement refers to a specific configured capability definition.
5. The grant has a specific provenance: `PURCHASE`, `MANUAL_GRANT`, or `OBLIGATION`.
6. The grant belongs to a specific correlated economic lifecycle.
7. A Store-and-Entitlements-owned entitlement was consumed, expired, or lawfully revoked.
8. An insurance claim was submitted against a specific insurance entitlement.
9. The insurance claim was approved or rejected through a lawful teacher decision.
10. The claim basis identifies the authoritative event or dates being evaluated when CTH owns or can reference that basis.

### B. Cross-domain truth

This domain may lawfully reference but does not own:

- capability and insurance definitions from Class Configuration;
- Ledger transactions used as purchase funding or transaction-insurance claim basis;
- Productivity and Payroll facts used to evaluate productivity-insurance claims;
- `hall_pass_logs` or other domain-owned consumption events;
- obligation facts that cause an entitlement to be granted;
- Ledger transactions produced by compensatory credits;
- Payroll events produced by approved productivity-insurance claims.

### C. Derived state

The following SHALL be derived and SHALL NOT be persisted as canonical entitlement truth:

- entitlement quantity;
- remaining uses;
- entitlement balance;
- whether an atomic entitlement is currently available;
- number of available entitlements of a configured item;
- remaining insurance claim allowance;
- remaining reimbursable transaction count;
- remaining productivity-insurance claim count;
- current display status such as `active`, `used`, `redeemed`, or `expired` when deterministically derivable from canonical facts and configuration.

### D. Display-only state

Names, class labels, item labels, descriptions, and other presentation metadata SHALL be resolved through the lawful display/view-model pipeline and SHALL NOT be cached into canonical Store and Entitlements event rows merely for presentation convenience.

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `entitlements`
- `entitlement_consumptions`
- `insurance_claims`

The following legacy or superseded persistence concepts are not part of the v3 canonical Store and Entitlements contract:

- `store_purchases`
- `redemption_events`
- domain-owned `store_items`
- domain-owned `store_item_visibility`
- persisted purchase quantity as entitlement truth
- `uses_remaining`
- `bundle_remaining`
- mutable purchase lifecycle status used as entitlement authority
- separate obligation-owned entitlement stores

Store item and insurance definitions belong to the Class Configuration domain.

## VII. Canonical Persistence

### A. `entitlements`

`entitlements` is append-only canonical grant history.

One row represents one atomic entitlement.

For ordinary consumable capabilities, one row represents exactly one independently exercisable use.

If a student purchases five late-work passes in one transaction, five entitlement rows SHALL be created. The rows may share the same `correlation_id` and `entitlement_item_id`, but each SHALL have a distinct `entitlement_id`.

Key fields:

- `entitlement_id` — domain-specific unique identifier for the atomic entitlement
- `class_id` — FK to `classes`; canonical class boundary
- `target_seat_id` — FK to `seats`; seat that possesses the entitlement
- `actor_seat_id` — FK to `seats`; seat whose lawful action caused or authorized the grant
- `entitlement_item_id` — cross-domain FK/reference to the Class Configuration capability definition
- `grant_type` — `PURCHASE` | `MANUAL_GRANT` | `OBLIGATION`
- `correlation_id` — identifier tying the grant to the coordinated event or lifecycle that generated it
- `granted_at` — canonical timestamp

Actor rules:

- `PURCHASE`: `actor_seat_id` is the purchasing seat from canonical request context.
- `MANUAL_GRANT`: `actor_seat_id` is the teacher seat from canonical request context.
- `OBLIGATION`: `actor_seat_id` is the teacher seat for the class, resolved lawfully from class authority.

Rules:

- `target_seat_id` and `actor_seat_id` SHALL belong to `class_id`.
- `entitlement_item_id` SHALL refer to a capability definition lawful for the same class boundary.
- `entitlements` SHALL NOT contain quantity, remaining balance, mutable redemption status, or display metadata.
- Grant rows SHALL NOT be edited to represent later consumption.
- Expiration, when defined by Class Configuration, SHALL be evaluated from the configured rule and the canonical temporal model rather than by mutating grant state.

### B. `entitlement_consumptions`

`entitlement_consumptions` is append-only history for terminal entitlement events whose authoritative business meaning is owned by the Store and Entitlements domain.

Key fields:

- `consumption_id` — domain-specific unique identifier
- `entitlement_id` — FK to `entitlements`; the exact atomic entitlement affected
- `class_id` — canonical class boundary
- `target_seat_id` — seat that held the entitlement
- `actor_seat_id` — seat that lawfully caused the terminal event
- `disposition` — `CONSUMED` | `EXPIRED` | `REVOKED`
- `correlation_id` — correlation identifier for the terminal lifecycle event
- `timestamp` — canonical timestamp

Disposition semantics:

- `CONSUMED` means the entitled benefit was exercised.
- `EXPIRED` means the entitlement ceased to be exercisable because its configured validity period ended before exercise.
- `REVOKED` means an otherwise-valid entitlement was lawfully withdrawn before consumption through an authorized revocation path.

Rules:

- Each `entitlement_id` may have no more than one authoritative terminal event.
- A consumption row SHALL reference the exact atomic entitlement affected.
- `REVOKED` is lawful only through a provenance-appropriate revocation path.
- `MANUAL_GRANT` entitlements may be revoked by a lawful teacher action before consumption.
- Ordinary `PURCHASE` entitlements may be revoked only as part of a lawful Ledger reversal/refund workflow and only before authoritative consumption.
- Insurance entitlements SHALL NOT be revoked or refunded after lawful purchase.
- `OBLIGATION` entitlements SHALL NOT be revoked.
- This table SHALL NOT duplicate consumption events whose authoritative business meaning belongs to another domain.
- A late-work pass or similar Store-and-Entitlements-owned benefit SHALL record `CONSUMED` here.
- A hall-pass entitlement SHALL NOT record `CONSUMED` here when the authoritative exercise is recorded by `hall_pass_logs`.
- A consuming domain SHALL reference the exact `entitlement_id` through a lawful cross-domain FK or equivalent schema-enforced reference.
- Availability SHALL be derived by determining whether the atomic entitlement has an authoritative terminal event or authoritative cross-domain consumption event.

### C. `insurance_claims`

`insurance_claims` is the canonical mutable workflow table for claims made under insurance entitlements.

Insurance is a conditional entitlement. Acquisition grants the target seat the right to submit qualifying events for evaluation under the referenced Class Configuration insurance definition. Acquisition does not guarantee approval or payment.

Key fields:

- `claim_id` — domain-specific unique identifier
- `class_id` — canonical class boundary
- `entitlement_id` — FK to `entitlements`; insurance entitlement under which the claim is made
- `target_seat_id` — seat requesting the benefit
- `actor_seat_id` — seat submitting or initiating the claim
- `transaction_id` — nullable cross-domain FK/reference to Ledger; required for transaction-based claims
- `claimed_dates` — nullable structured collection of canonical class-local dates; used for productivity-based claims
- `status` — `SUBMITTED` | `APPROVED` | `REJECTED`
- `submitted_at` — canonical timestamp
- `decided_at` — nullable canonical timestamp
- `decided_by_seat_id` — nullable FK to the teacher seat that approved or rejected the claim
- `correlation_id` — correlation identifier for the claim lifecycle and coordinated effects

Rules:

- `insurance_type` SHALL NOT be duplicated on the claim when it is canonically resolvable through `entitlement_id -> entitlement_item_id -> Class Configuration`.
- coverage percentage, eligibility window, claim allowance, tier, and other policy terms SHALL NOT be duplicated into the claim unless a separate governing versioning contract requires an immutable policy snapshot.
- claim status transitions are forward-only:
  - `SUBMITTED -> APPROVED`
  - `SUBMITTED -> REJECTED`
- Approved or rejected claims SHALL NOT return to `SUBMITTED`.
- Any reversal or correction semantics require a separately defined lawful compensating workflow.
- Teacher approval is required for all insurance claim types.
- The claim table SHALL record the claim workflow; it SHALL NOT become monetary authority.

## VIII. Insurance Types

Insurance definitions are owned by Class Configuration.

The canonical insurance types are:

- `TRANSACTION`
- `PRODUCTIVITY`
- `NON_MONETARY`

### A. Transaction-based insurance

Transaction insurance covers one qualifying Ledger transaction per claim.

The claim SHALL reference exactly one `transaction_id`.

The referenced Ledger transaction is the authoritative economic event being evaluated for reimbursement.

Upon teacher approval:

1. Store and Entitlements validates the claim against the configured insurance definition.
2. The lawful Entitlement FEAT coordinates a compensatory Ledger credit.
3. The compensatory credit SHALL preserve lawful lineage to the original spending event.
4. Ledger remains the sole authority over the monetary transaction.

Transaction insurance SHALL NOT create a Payroll event.

### B. Productivity-based insurance

Productivity insurance covers one or more qualifying dates within the configured eligibility window.

The claim SHALL identify the dates selected for evaluation.

Eligibility SHALL be determined from authoritative Productivity and Payroll facts. Store and Entitlements SHALL NOT alter attendance, productivity sessions, worked minutes, or historical payroll calculations in order to approve a claim.

Upon teacher approval:

1. Store and Entitlements validates the claim against the configured insurance definition and authoritative Productivity/Payroll facts.
2. The approved claim is coordinated to the Productivity and Payroll domain.
3. Productivity and Payroll creates a `payroll_event` using `MANUAL_CREDIT`.
4. The `MANUAL_CREDIT` represents compensation calculated from the applicable insurance rule; it does not assert that the student actually worked.
5. The Productivity and Payroll FEAT posts the resulting monetary effect to Ledger.
6. Productivity and Payroll remains the sole authority over the payroll event.
7. Ledger remains the sole authority over the resulting monetary transaction.

An approved productivity-insurance claim SHALL NOT be represented as ordinary worked payroll.

### C. Non-monetary insurance

Non-monetary insurance provides a teacher-configured claim allowance for a benefit whose underlying event and fulfillment exist outside CTH authority.

Examples may include teacher-defined external classroom accommodations or privileges.

CTH SHALL own only:

- entitlement acquisition;
- claim submission;
- teacher approval or rejection;
- derived count of approved claims within the configured allowance period.

CTH SHALL NOT attempt to model, verify, or persist the external benefit itself.

Upon approval, no Ledger or Payroll mutation is required unless a separate explicitly defined feature introduces one.

### D. Insurance cancellation and coverage continuity

Insurance cancellation is prospective.

A teacher may cancel or disable an insurance offering for future coverage cycles through Class Configuration.

Cancellation SHALL NOT:

- revoke an already-purchased insurance entitlement;
- refund an already-purchased insurance entitlement;
- shorten an already-established coverage cycle; or
- prevent an otherwise eligible seat from submitting claims during its current coverage cycle.

An active insurance entitlement remains claim-eligible until its configured coverage boundary is reached.

The teacher retains claim-decision authority during that remaining coverage period. A claim may be approved or rejected according to the configured policy and teacher decision.

At the end of the active coverage cycle, the insurance entitlement terminates through ordinary expiration. Cancellation prevents future acquisition or renewal; it does not retroactively alter existing coverage.

## IX. Atomic Entitlement Rules

### A. One entitlement equals one exercisable capability

For ordinary entitlements:

> One entitlement row represents exactly one exercisable capability.

Quantity SHALL be represented by row cardinality, not by a mutable quantity field.

Example:

A purchase of five late-work passes creates five rows:

- five distinct `entitlement_id` values;
- the same `target_seat_id`;
- the same `actor_seat_id`;
- the same `entitlement_item_id`;
- the same purchase `correlation_id`;
- the same `grant_type = PURCHASE`.

### B. Instant-use items

An instant-use item creates both acquisition and exercise facts within the same lawful FEAT transaction.

For Store-and-Entitlements-owned exercise:

1. create the entitlement;
2. create its `CONSUMED` event;
3. commit both atomically with coordinated monetary effects.

If the exercise is owned by another domain, the same transaction SHALL create the entitlement and the authoritative consuming-domain event without duplicating the exercise in `entitlement_consumptions`.

### C. No persisted balance

The domain SHALL NOT persist:

- entitlement balance;
- available count;
- remaining uses;
- bundle remainder.

Available entitlement count is a projection over:

- matching lawful entitlement grants;
- Class Configuration rules;
- canonical temporal context;
- authoritative consumption records, whether local or cross-domain.

## X. Collective Goal Items

Collective-goal behavior is a property of the configured capability definition and SHALL NOT create a separate entitlement persistence model.

Class Configuration owns:

- whether an item is collective;
- the collective threshold or target;
- the eligible population;
- contribution or purchase rules;
- activation conditions;
- expiration or validity directives.

A purchase of a defined collective-goal item follows the ordinary acquisition path:

1. the configured collective-goal item exists under Class Configuration;
2. Ledger records the lawful purchase or contribution;
3. the Store and Entitlements FEAT grants the purchasing seat one atomic entitlement for each purchased unit.

The entitlement row does not store collective progress, collective status, or a mutable activation flag.

A seat may therefore possess an entitlement that is not yet exercisable because the configured collective activation condition has not yet been satisfied.

Collective progress and exercisability SHALL be derived from:

- the Class Configuration collective-goal definition;
- authoritative qualifying economic events, including Ledger purchase/contribution facts;
- canonical temporal context where the configured goal is time-bound.

The domain SHALL NOT persist `collective_goal_progress`, `current_progress`, or equivalent mutable counters when the value can be deterministically derived.

The distinction is normative:

> Entitlement possession records that the seat acquired the capability. Exercisability is a derived determination of whether the configured conditions currently permit that capability to be exercised.

## XI. Consumption Authority

Every atomic entitlement has exactly one lawful exercise path.

The fact that an entitlement was exercised SHALL have one authoritative persistence location.

### A. Store-and-Entitlements-owned exercise

When no other domain owns the resulting business event, exercise is written to `entitlement_consumptions` with `disposition = CONSUMED`.

### B. Cross-domain exercise

When exercising an entitlement produces a business event owned by another domain:

- that domain owns the authoritative exercise record;
- the consuming record SHALL reference the exact `entitlement_id`;
- Store and Entitlements SHALL NOT create a duplicate `CONSUMED` row;
- Store and Entitlements may lawfully read that authoritative record when deriving availability or lifecycle projections.

Example:

A hall-pass entitlement is granted by Store and Entitlements.

When used, the authoritative consumption is the Productivity and Payroll domain's `hall_pass_logs` record referencing the exact `entitlement_id`.

## XII. Cross-Domain Contracts

### A. Class Configuration

Class Configuration owns:

- entitlement item definitions;
- store offering configuration;
- price configuration;
- inventory or purchase-limit directives;
- visibility directives;
- insurance definitions;
- insurance type;
- insurance eligibility window;
- insurance tier;
- reimbursement percentage;
- claim allowance;
- other teacher-defined capability rules.

Store and Entitlements SHALL treat these values as configuration inputs, not domain-owned state.

### B. Ledger

Ledger owns all monetary truth.

Store and Entitlements may:

- read Ledger transactions;
- reference a Ledger transaction as purchase funding;
- reference exactly one Ledger transaction as the basis of a transaction-insurance claim;
- coordinate a compensatory Ledger credit through a lawful FEAT.

Store and Entitlements SHALL NOT directly write Ledger persistence outside the lawful Ledger mutation boundary.

### C. Productivity and Payroll

Productivity and Payroll owns:

- attendance sessions;
- productivity history;
- hall-pass logs;
- payroll events;
- payroll-domain interpretation of `MANUAL_CREDIT`.

Store and Entitlements may:

- read authoritative productivity/payroll facts for insurance eligibility;
- coordinate an approved productivity-insurance claim to the Productivity and Payroll domain;
- read `hall_pass_logs` or other lawful consumption records when deriving entitlement availability.

Store and Entitlements SHALL NOT rewrite productivity history to make an insurance claim appear earned.

### D. Obligations

Obligations may cause entitlement grants.

An obligation-related entitlement SHALL be persisted in `entitlements` with:

- `grant_type = OBLIGATION`;
- the target seat that received the capability;
- the teacher seat as `actor_seat_id`, resolved lawfully from Class authority;
- correlation to the obligation lifecycle that caused the grant.

Obligations SHALL NOT maintain a separate canonical entitlement store.

## XIII. Primitive Operations

Primitive operations are derived from the canonical facts represented by the three domain-owned tables. They SHALL NOT introduce state that is absent from the canonical persistence contract.

### A. `entitlements` primitives

#### `grant_entitlement(...)`

Creates exactly one atomic entitlement row.

Required inputs are the facts required by `entitlements`:

- `class_id`
- `target_seat_id`
- `actor_seat_id`
- `entitlement_item_id`
- `grant_type`
- `correlation_id`
- canonical grant timestamp

The operation SHALL:

- validate that target and actor seats are lawful for the class boundary;
- validate that the referenced configured item may lawfully produce an entitlement;
- create exactly one new `entitlement_id`;
- create no quantity, balance, remaining-use, or mutable status state.

A workflow granting multiple units SHALL invoke the primitive once per atomic entitlement within the same lawful FEAT transaction and correlation lifecycle.

The primitive SHALL NOT determine whether the grant originates from purchase, manual grant, or obligation orchestration beyond validating the supplied lawful `grant_type`. The coordinating FEAT owns that workflow decision.

### B. `entitlement_consumptions` primitives

Each primitive creates exactly one authoritative terminal event for an atomic entitlement when Store and Entitlements owns that terminal event.

#### `consume_entitlement(...)`

Creates an `entitlement_consumptions` row with:

- `disposition = CONSUMED`.

The operation SHALL require:

- the exact `entitlement_id`;
- canonical class and seat context;
- lawful actor seat;
- correlation identifier;
- canonical timestamp.

It SHALL reject:

- nonexistent entitlements;
- entitlements outside the resolved class/seat boundary;
- entitlements already having an authoritative terminal event;
- entitlements whose exercise is owned by another domain.

#### `expire_entitlement(...)`

Creates an `entitlement_consumptions` row with:

- `disposition = EXPIRED`.

The operation SHALL require proof, through Class Configuration and canonical temporal resolution, that the entitlement's configured validity has ended.

Expiration SHALL NOT be represented by mutating the entitlement grant.

The operation SHALL reject an entitlement that:

- has already terminated;
- has already been consumed by another authoritative domain;
- has not yet reached its lawful expiration boundary.

#### `revoke_entitlement(...)`

Creates an `entitlement_consumptions` row with:

- `disposition = REVOKED`.

Revocation SHALL be provenance-aware.

For `MANUAL_GRANT`:

- a lawful teacher actor seat may revoke the entitlement before consumption.

For ordinary `PURCHASE`:

- revocation is lawful only through the coordinated Ledger reversal/refund workflow;
- the entitlement must be unused and otherwise available;
- the configured item must not be an insurance contract or another explicitly non-revocable capability.

For `OBLIGATION`:

- revocation is prohibited.

For insurance entitlements:

- revocation and refund are prohibited after lawful purchase.

The operation SHALL reject an entitlement that has already terminated or been consumed by another authoritative domain.

### C. `insurance_claims` primitives

Insurance claim primitives operate on the mutable claim workflow. The referenced insurance definition remains Class Configuration authority.

#### `submit_insurance_claim(...)`

Creates one `insurance_claims` row with:

- `status = SUBMITTED`.

Required facts include:

- `class_id`
- `entitlement_id`
- `target_seat_id`
- `actor_seat_id`
- claim basis required by the configured insurance type
- `correlation_id`
- canonical submission timestamp

Claim-basis requirements are:

- `TRANSACTION` — exactly one qualifying `transaction_id`;
- `PRODUCTIVITY` — one or more qualifying canonical class-local dates;
- `NON_MONETARY` — no Ledger or Productivity basis is required unless the configured definition explicitly requires supported claim metadata.

The operation SHALL validate that:

- the insurance entitlement exists and belongs to the target seat;
- the entitlement references a configured insurance item;
- the claim basis matches the configured insurance type;
- the claim is within the configured eligibility window;
- the configured claim allowance has not been exhausted;
- the same authoritative basis is not being unlawfully claimed more than permitted by configuration.

Submission SHALL NOT create monetary or payroll effects.

#### `approve_insurance_claim(...)`

Advances one claim:

- `SUBMITTED -> APPROVED`.

The operation SHALL require a lawful teacher actor seat.

Approval SHALL revalidate the claim against the authoritative facts required by its configured insurance type before coordinated downstream mutation occurs.

Approval consequences are determined by insurance type:

- `TRANSACTION` — coordinate the lawful compensatory Ledger credit for the referenced transaction;
- `PRODUCTIVITY` — coordinate creation of a Productivity and Payroll `MANUAL_CREDIT`, after which the Productivity and Payroll FEAT owns posting to Ledger;
- `NON_MONETARY` — no downstream CTH economic mutation is required.

The claim decision and all required downstream effects SHALL participate in the lawful coordinated FEAT transaction and correlation contract.

#### `reject_insurance_claim(...)`

Advances one claim:

- `SUBMITTED -> REJECTED`.

The operation SHALL require a lawful teacher actor seat.

Rejection SHALL:

- record the canonical decision timestamp;
- record the deciding teacher seat;
- create no Ledger or Payroll effect.

### D. Pure query primitives

Read primitives SHALL be pure and SHALL derive answers from canonical facts rather than persisted counters or mutable availability flags.

Required query capabilities include:

#### Entitlement reads

- `get_entitlement(...)`
- `list_entitlements_for_seat(...)`
- `list_available_entitlements(...)`
- `is_entitlement_available(...)`
- `list_entitlement_history(...)`

Availability reads SHALL evaluate:

- the atomic grant;
- Class Configuration rules;
- canonical temporal context;
- Store-and-Entitlements-owned terminal events;
- lawful cross-domain consumption records where another domain owns exercise.

#### Insurance reads

- `get_insurance_claim(...)`
- `list_insurance_claims(...)`
- `get_remaining_insurance_allowance(...)`
- `get_eligible_transaction_claim_basis(...)`
- `get_eligible_productivity_claim_basis(...)`

Insurance reads SHALL use:

- the insurance entitlement;
- the referenced Class Configuration insurance definition;
- canonical temporal context;
- existing insurance claim history;
- authoritative Ledger facts for transaction insurance;
- authoritative Productivity and Payroll facts for productivity insurance.

Remaining allowance SHALL be derived from configured allowance rules and canonical claim history. It SHALL NOT be stored as mutable claim balance.

### E. Primitive boundary rule

Primitive operations express the smallest lawful reads and writes supported by canonical persistence.

They SHALL NOT:

- perform route or template orchestration;
- infer canonical context from legacy identifiers;
- directly coordinate unrelated domain mutations;
- create compatibility state;
- reconstruct authority from labels or presentation data.

Cross-domain workflow coordination belongs to FEAT.

## XIV. Legal Mutation Boundary

Every Store and Entitlements mutation SHALL:

1. resolve canonical request context before domain interaction when initiated by an authenticated request;
2. operate on `class_id` and canonical seat identifiers;
3. enter through one lawful FEAT path;
4. use one transaction boundary for coordinated writes;
5. enforce idempotency where replay could duplicate grants, claims, redemptions, or monetary effects;
6. propagate correlation across coordinated domain events;
7. fail closed if required cross-domain authority cannot be resolved.

Routes, background jobs, CLI commands, migrations, tests, and helpers SHALL NOT directly create or mutate canonical Store and Entitlements rows except where an explicitly governed migration contract permits schema/data migration.

## XV. Read Models and Derived Projections

The Store and Entitlements domain may expose pure projections including:

- entitlements currently available to a seat;
- number of available entitlements by configured item;
- entitlement acquisition history;
- entitlement exercise history;
- insurance policies currently held by a seat;
- pending insurance claims;
- approved/rejected insurance claim history;
- remaining insurance claim allowance;
- eligible Ledger transactions for transaction-insurance claims;
- eligible productivity dates for productivity-insurance claims.

A projection may lawfully aggregate facts from other domains but SHALL NOT become a second authority for those facts.

Routes and templates SHALL consume canonical projections rather than recomputing entitlement lifecycle state independently.

## XVI. Temporal Rules

All class-local eligibility windows, expiration calculations, monthly claim allowances, and date-based insurance rules SHALL use the canonical temporal model.

UTC timestamps may be stored for event chronology.

Class-local dates and boundary calculations SHALL be resolved using the class timezone and the canonical temporal resolver.

A route, template, or domain helper SHALL NOT infer class-local insurance eligibility directly from server-local time.

## XVII. Deletion and Retention

Store and Entitlements data is class-scoped.

Deletion of a class SHALL remove class-owned Store and Entitlements state according to the governing hard-deletion and lineage invariants.

Deletion SHALL preserve no orphaned entitlement, redemption, or insurance claim rows.

Cross-domain deletion ordering SHALL respect foreign-key integrity and the lawful ownership model.

No archive state SHALL be introduced as a substitute for required hard deletion.

## XVIII. Forbidden Persistence

The following are forbidden as canonical Store and Entitlements authority:

- `join_code` as scope or authority;
- `student_id` or `teacher_id` legacy identity references;
- label-based scope such as `block`, `period`, or `section`;
- mutable entitlement counts;
- `uses_remaining`;
- `bundle_remaining`;
- duplicated entitlement-consumption records across domains;
- cached display identity as business authority;
- Store-owned copies of Class Configuration item definitions;
- Store-owned copies of insurance policy configuration;
- monetary balances;
- reconstructed productivity history;
- ordinary payroll events created directly by insurance approval;
- polymorphic string identifiers that bypass lawful foreign-key/domain-reference contracts where a canonical reference exists.

## XIX. Reconstruction Disposition of v2.2 Tables

The v2.2 Store and Entitlements schema is superseded as follows:

### `store_items`

Disposition: move authority to Class Configuration.

The existence and behavior of a configured store/entitlement item are class configuration truth, not Store and Entitlements operational truth.

### `store_item_visibility`

Disposition: move authority to Class Configuration.

Visibility is a teacher-defined directive governing which seats may see a configured offering.

### `store_purchases`

Disposition: collapse into atomic `entitlements` plus lawful Ledger purchase history.

A purchase that grants multiple units creates multiple atomic entitlement rows. Purchase quantity, purchase balance, and remaining-use state are not canonical entitlement truth.

### `redemption_events`

Disposition: replace with `entitlement_consumptions` for Store-and-Entitlements-owned terminal events.

The replacement records `CONSUMED`, `EXPIRED`, or narrowly lawful `REVOKED` dispositions against exact atomic entitlements. Request/approval workflows that require mutable state SHALL use an explicitly modeled workflow table such as `insurance_claims` rather than overloading an append-only consumption-event stream.

### obligation-linked entitlement persistence

Disposition: collapse into `entitlements`.

Obligation origin is represented by `grant_type = OBLIGATION` and correlation lineage rather than by a second entitlement authority.

## XX. Canonical Invariants

1. **Atomic grant invariant** — one `entitlements` row represents one atomic entitlement.
2. **No-count invariant** — quantity and remaining entitlement balance are derived, never canonical stored state.
3. **Single-grant-authority invariant** — all entitlement grants, regardless of source, are canonicalized in `entitlements`.
4. **Configuration-separation invariant** — capability and insurance definitions belong to Class Configuration.
5. **Single-consumption-authority invariant** — each entitlement exercise has exactly one authoritative persistence location.
6. **Single-terminal-event invariant** — an atomic entitlement may have no more than one authoritative terminal event.
7. **Revocation-scope invariant** — revocation authority is determined by entitlement provenance and capability semantics: manual grants may be teacher-revoked while unused; ordinary purchases may be revoked only through lawful Ledger reversal/refund while unused; insurance and obligation entitlements are non-revocable.
8. **Grant-history invariant** — a lawful grant row is never mutated or deleted to simulate reversal; later revocation is a separate terminal fact.
9. **Exact-reference invariant** — a consuming event references the exact `entitlement_id` exercised.
10. **Insurance-conditionality invariant** — insurance acquisition grants claim-evaluation capability, not guaranteed benefit.
11. **Insurance-contract invariant** — purchased insurance coverage cannot be revoked or refunded after lawful purchase; cancellation affects only future coverage cycles.
12. **Coverage-continuity invariant** — cancellation of an insurance offering does not end active coverage before its configured boundary.
13. **Teacher-approval invariant** — all insurance claims require teacher approval.
14. **Monetary-authority invariant** — Ledger is the sole monetary authority.
15. **Productivity-integrity invariant** — productivity insurance never rewrites historical productivity truth.
16. **Payroll-classification invariant** — approved productivity-insurance compensation enters Payroll as `MANUAL_CREDIT`, not ordinary worked payroll.
17. **Projection invariant** — availability, balances, and remaining allowances are derived from canonical facts.
18. **Correlation invariant** — coordinated entitlement, claim, payroll, and Ledger effects preserve lawful correlation and lineage.
19. **FEAT-boundary invariant** — cross-domain mutation occurs only through lawful FEAT coordination.
20. **Collective-configuration invariant** — collective-goal behavior is configuration and derived activation logic, not a separate entitlement state model.
21. **Possession-versus-exercisability invariant** — possession of an entitlement does not by itself prove that configured conditions currently permit exercise.

## XXI. Reconstruction and Cutover Requirements

Per `SOP-DEV-002`, implementation SHALL NOT begin by preserving v2.2 helper, route, or template shape.

Before route/template rewiring begins, the reconstruction SHALL define or update:

- Class Configuration capability and insurance definitions;
- canonical Store and Entitlements schema;
- primitive operations;
- lawful FEAT writers;
- cross-domain consumption contracts;
- insurance approval coordination;
- read/projection surfaces;
- application surface inventory.

Each existing Store and Entitlements application surface SHALL then be classified as:

- `REWIRE`
- `REMOVE`
- `COLLAPSE`
- `VERIFY`
- `BLOCKED`

Legacy persistence and compatibility paths SHALL be deleted only after surviving callers have been lawfully rewired, removed, collapsed, or verified and targeted validation has passed.

## XXII. Amendment

Revisions to this document must:

1. increment the version number;
2. update the Effective Date;
3. update the Supersedes field;
4. maintain consistency with governing INV, DOM, and FEAT authority;
5. update `DOM-CORE-002` when canonical table ownership or schema declarations change;
6. update affected Class Configuration, Productivity and Payroll, Obligations, Ledger, FEAT, MAP, and SOP-linked documentation when cross-domain contracts change.
