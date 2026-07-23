# FEAT-STOR-001: Store Purchase and Entitlement Grant

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-STOR-001 | 2.0 | 2026-07-22 | 1.0 | Normative |

## I. Purpose

Define the single lawful orchestration path for purchasing a configured Store capability and granting the resulting atomic entitlement or entitlements.

This FEAT coordinates:

- canonical request context;
- Class Configuration purchase directives;
- Obligations purchase eligibility;
- Ledger financial resolution and posting; and
- Store and Entitlements atomic grant creation.

A purchase is an economic exchange that may create one or more atomic entitlements.

The FEAT SHALL NOT persist purchase quantity, remaining-use balance, mutable purchase status, or a second purchase-authority record inside the Store and Entitlements domain.

## II. Authority

This FEAT is the sole lawful writer for entitlement grants with:

- `grant_type = PURCHASE`

when the grant originates from a user-initiated Store purchase.

It does not own:

- capability definitions;
- item price or purchase directives;
- insurance configuration;
- Ledger truth;
- obligation truth;
- entitlement persistence;
- consumption events.

Those authorities remain with their owning domains.

## III. Dependencies

- `FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- Class Configuration governing DOM and FEAT contracts
- `DOM-LED-001_LEDGER_DOMAIN.md`
- lawful Ledger FEAT contracts
- Obligations governing DOM and FEAT contracts
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

## IV. Required Execution Context

The route or caller SHALL resolve canonical request context before entering this FEAT.

Required canonical context:

- `user_id`
- `class_id`
- `seat_id`
- `actor_role`

For a student purchase:

- `seat_id` is both the purchasing actor seat and the target entitlement seat.

The FEAT SHALL NOT reconstruct class or seat authority from:

- `join_code`
- username
- display name
- block/period/section labels
- Store item ownership assumptions
- route-local lookups intended to substitute for canonical context.

## V. Required Inputs

The FEAT accepts:

- canonical request context;
- `entitlement_item_id` — Class Configuration identifier for the configured offering;
- `quantity` — positive integer number of units requested;
- `idempotency_key` — request replay guard.

The FEAT generates or resolves:

- `correlation_id` — one identifier for the coordinated purchase lifecycle;
- canonical transaction timestamp through the temporal model.

`quantity` is an orchestration input only.

It SHALL NOT be persisted as entitlement quantity or remaining entitlement balance.

## VI. Read-Only Validation Phase

All validation SHALL complete before mutation begins.

### A. Canonical context validation

Verify:

- the actor is a lawful student seat for `class_id`;
- the target seat is the canonical context seat;
- the seat exists within the class boundary.

### B. Class Configuration validation

Read the configured capability definition through the lawful Class Configuration interface.

Validate, as applicable:

- the offering exists for `class_id`;
- the offering is currently purchasable;
- the price is valid for the current configuration/version;
- the requested quantity is permitted;
- seat-specific visibility or eligibility directives permit purchase;
- configured inventory or purchase limits permit the requested purchase;
- activation or collective-goal rules are valid;
- insurance configuration is valid when the configured offering is insurance;
- the offering has not been prospectively cancelled or disabled for new acquisition.

The FEAT SHALL NOT copy Class Configuration state into Store and Entitlements persistence merely to make later reads convenient.

### C. Existing purchase/grant history

Where Class Configuration defines inventory, per-seat limits, bundles, or similar constraints, the FEAT SHALL evaluate those rules from canonical configuration plus authoritative purchase/grant history.

Mutable counters such as:

- `inventory_remaining`
- `uses_remaining`
- `bundle_remaining`
- `purchases_remaining`

SHALL NOT be introduced into entitlement persistence as authority when the value is deterministically derivable.

### D. Obligation purchase guard

Call the lawful Obligations read surface to determine whether the seat may make the requested purchase.

If purchase is blocked by an outstanding obligation rule, abort before monetary mutation.

The exact denial reason SHALL come from Obligations authority rather than being reconstructed in Store code.

### E. Financial resolution

Calculate the intended purchase amount from authoritative Class Configuration pricing.

Construct the intended Ledger plan and submit it through the lawful Ledger resolution path.

The Ledger resolution result may:

- accept the plan;
- lawfully transform the plan, such as through configured overdraft/recovery behavior; or
- deny the purchase.

A denied financial plan SHALL abort with no entitlement grant.

## VII. Mutation Phase

All coordinated mutations SHALL occur within one lawful transaction boundary.

### A. Ledger execution

Execute the resolved purchase plan through the lawful Ledger mutation FEAT.

Ledger remains the sole authority over:

- debit/credit postings;
- account balances;
- overdraft or recovery postings;
- transaction identifiers;
- monetary reversal semantics.

The purchase Ledger event SHALL carry the purchase `correlation_id`.

### B. Atomic entitlement grants

After the Ledger purchase is lawfully established, invoke the Store and Entitlements primitive:

- `grant_entitlement(...)`

exactly once for each purchased unit.

For each atomic entitlement:

- `class_id` = canonical context class;
- `target_seat_id` = purchasing seat;
- `actor_seat_id` = purchasing seat;
- `entitlement_item_id` = configured offering identifier;
- `grant_type` = `PURCHASE`;
- `correlation_id` = purchase lifecycle correlation;
- `granted_at` = canonical transaction timestamp.

A purchase of quantity `5` SHALL create five distinct entitlement rows with:

- five distinct `entitlement_id` values;
- the same `class_id`;
- the same target and actor seat;
- the same `entitlement_item_id`;
- the same `grant_type`;
- the same purchase `correlation_id`.

### C. Instant-use capability

If Class Configuration defines the purchased capability as immediate/instant exercise, the purchase FEAT SHALL coordinate the grant and the lawful exercise in the same transaction.

If Store and Entitlements owns the exercise:

1. create the atomic entitlement;
2. create its `entitlement_consumptions` row with `disposition = CONSUMED`.

If another domain owns the exercise:

1. create the atomic entitlement;
2. invoke the lawful consuming-domain FEAT or primitive;
3. require the consuming record to reference the exact `entitlement_id`;
4. do not create a duplicate Store-and-Entitlements `CONSUMED` record.

### D. Collective-goal capability

Collective-goal purchases use the ordinary purchase path.

The FEAT SHALL NOT create a collective-progress record merely because the configured offering is collective.

Each purchased unit creates one atomic entitlement for the purchasing seat.

Collective activation or exercisability remains a projection over:

- Class Configuration collective rules;
- authoritative qualifying economic events; and
- canonical temporal context.

### E. Insurance capability

Insurance purchases use the ordinary atomic entitlement grant path.

A purchased insurance entitlement establishes a coverage contract for its configured coverage cycle.

Once the purchase commits:

- the insurance entitlement SHALL NOT be revoked;
- the purchase SHALL NOT be refunded;
- later teacher cancellation of the insurance offering affects future coverage cycles only;
- active coverage remains claim-eligible until its configured coverage boundary;
- individual claims remain subject to teacher approval or rejection.

The purchase FEAT SHALL NOT create an insurance claim.

## VIII. Purchase Reversal Boundary

This FEAT does not itself reverse completed purchases.

For an ordinary purchased entitlement, a separate lawful reversal/refund FEAT may revoke the entitlement only when:

- the entitlement remains unused;
- no authoritative terminal or cross-domain consumption event exists;
- the configured capability is lawfully refundable;
- the capability is not insurance;
- the Ledger reversal/refund succeeds within the coordinated transaction.

Revocation SHALL be recorded as a separate `entitlement_consumptions` event with:

- `disposition = REVOKED`.

The original entitlement grant SHALL remain immutable historical fact.

Insurance purchases are contractually non-refundable after lawful purchase and SHALL be rejected by any generic purchase-reversal path.

## IX. Idempotency

`idempotency_key` SHALL protect the complete purchase lifecycle.

A replay of a successful request SHALL:

- not create a second Ledger purchase;
- not create additional entitlement rows;
- return or reconstruct the original purchase result through canonical correlation/idempotency evidence.

For multi-unit purchases, idempotency applies to the complete requested batch.

The system SHALL NOT interpret a retry as permission to grant another `quantity` units.

## X. Atomicity

The following SHALL succeed or fail together:

- required Ledger purchase postings;
- every atomic entitlement grant for the requested quantity;
- any required instant-use consumption event;
- any other explicitly authorized cross-domain mutation required by the configured capability.

If any required write fails, the transaction SHALL roll back.

No successful purchase may exist without its complete entitlement grant set.

No purchase-generated entitlement grant may exist without the corresponding lawful purchase Ledger event.

## XI. Correlation and Lineage

One `correlation_id` SHALL identify the coordinated purchase lifecycle.

The correlation SHALL connect, as applicable:

- Ledger purchase transaction(s);
- every atomic entitlement created by the purchase;
- immediate consumption events;
- cross-domain effects explicitly caused by the purchase.

Correlation provides lineage; it does not transfer authority between domains.

## XII. Failure Contract

Representative failures include:

- `INVALID_CONTEXT`
- `ITEM_NOT_FOUND`
- `ITEM_NOT_PURCHASABLE`
- `ITEM_NOT_VISIBLE`
- `QUANTITY_NOT_ALLOWED`
- `PURCHASE_LIMIT_REACHED`
- `INVENTORY_UNAVAILABLE`
- `OBLIGATION_BLOCK`
- `INSUFFICIENT_FUNDS`
- `INVALID_INSURANCE_CONFIGURATION`
- `INSURANCE_NOT_AVAILABLE_FOR_NEW_COVERAGE`
- `IDEMPOTENCY_CONFLICT`
- `CROSS_DOMAIN_FAILURE`

Failures SHALL occur before mutation when determinable during validation.

A mutation-stage failure SHALL roll back the coordinated transaction.

## XIII. Audit Requirements

Audit/lineage evidence SHALL make it possible to establish:

- canonical class and purchasing seat;
- configured item identifier;
- requested quantity;
- resolved monetary amount;
- Ledger transaction identifier(s);
- every generated `entitlement_id`;
- `correlation_id`;
- `idempotency_key` or lawful idempotency reference;
- final outcome.

Audit state SHALL NOT become a second authority for entitlement or monetary truth.

## XIV. Prohibited Patterns

The following are prohibited:

- resolving canonical context from `seat_id` inside the FEAT when request context should already be resolved;
- persisting `quantity` as entitlement balance;
- decrementing a Store-owned mutable `uses_remaining` field;
- maintaining a separate hall-pass balance;
- granting one entitlement row with `quantity = N`;
- special-casing collective goals into a separate entitlement persistence path;
- refunding or revoking purchased insurance coverage;
- granting entitlements before the purchase Ledger write is lawfully established;
- route-level purchase orchestration;
- direct route/helper/test writes to entitlement persistence;
- duplicate purchase authority outside Ledger plus atomic entitlement grants.

## XV. Postconditions

On success:

1. the lawful purchase is represented in Ledger;
2. exactly `quantity` atomic entitlement rows exist for the requested configured capability;
3. every entitlement carries the purchase correlation;
4. any required immediate exercise has exactly one authoritative consumption event;
5. no mutable entitlement count or purchase-status authority is required;
6. the result can be safely returned on idempotent retry without additional economic effects.

## XVI. Amendment

Revisions to this document must:

1. increment the version number;
2. update the Effective Date;
3. update the Supersedes field;
4. remain consistent with `DOM-STORE-001`, Class Configuration authority, Ledger authority, Obligations authority, and `FEAT-CORE-000`;
5. update dependent FEAT, DOM, MAP, schema, and test contracts when the purchase lifecycle changes.
