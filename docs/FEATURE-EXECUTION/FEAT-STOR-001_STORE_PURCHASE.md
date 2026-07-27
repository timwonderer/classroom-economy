# FEAT-STOR-001: Store Purchase and Entitlement Grant

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-STOR-001 | 3.0 | 2026-07-27 | 2.0 | Normative |

## I. Purpose

Define the lawful orchestration path for a student purchase of a configured product and the resulting entitlement grant.

This FEAT is the single lawful path for:

- resolving canonical request context;
- evaluating policy-defined purchase eligibility;
- coordinating Ledger purchase resolution; and
- writing one or more immutable entitlement grant facts.

A purchase may create one or more entitlement-event rows, but it SHALL NOT create a mutable purchase record, remaining-use balance, or entitlement status flag.

## II. Authority

This FEAT is the sole lawful writer for entitlement grants with:

- `acquisition_type = PURCHASE`
- `event_type = GRANTED`

when the acquisition originates from a user-initiated purchase.

It does not own:

- class configuration;
- policy definitions;
- Ledger truth;
- obligation truth;
- pending request storage;
- consumption or revocation history;
- external-domain exercise events.

## III. Dependencies

- `FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `DOM-LED-001_LEDGER_DOMAIN.md`
- lawful Policy FEAT contracts
- lawful Ledger FEAT contracts
- lawful Obligations FEAT contracts when purchase fulfillment produces a perk
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

## IV. Required Execution Context

The caller SHALL resolve canonical request context before entering this FEAT.

Required canonical context:

- `user_id`
- `class_id`
- `seat_id`
- `actor_role`

For a student purchase:

- `seat_id` is both the actor seat and the target seat.

The FEAT SHALL NOT reconstruct class or seat authority from:

- `join_code`
- display names
- route-local lookups
- cached UI labels
- username-only identity

## V. Required Inputs

The FEAT accepts:

- canonical request context;
- `product_id` — policy-owned product definition identifier;
- `quantity` — positive integer number of units requested;
- `idempotency_key` — request replay guard.

The FEAT generates or resolves:

- `correlation_id` — one identifier for the coordinated purchase lifecycle;
- canonical transaction timestamp through the temporal model.

`quantity` is an orchestration input only. It SHALL NOT be persisted as entitlement quantity or remaining entitlement balance.

## VI. Read-Only Validation Phase

All validation SHALL complete before mutation begins.

### A. Canonical context validation

Verify:

- the actor is lawful for the class boundary;
- the target seat is canonical for the request;
- the seat exists within the class boundary.

### B. Class Configuration validation

Read the configured product definition through the lawful Class Configuration / Policies interface.

Validate, as applicable:

- the product exists for `class_id`;
- the product is currently purchasable;
- the product version is lawful and effective for the current temporal context;
- the requested quantity is permitted;
- class-level feature enablement allows the product;
- any product-specific eligibility rules permit purchase;
- the product has not been prospectively disabled for new acquisition.

The FEAT SHALL NOT copy product configuration into Store and Entitlements persistence merely to make later reads convenient.

### C. Prior entitlement history

Where policy defines inventory, per-seat limits, bundles, or similar constraints, the FEAT SHALL evaluate those rules from canonical policy plus authoritative entitlement history.

Mutable counters such as:

- `inventory_remaining`
- `uses_remaining`
- `bundle_remaining`
- `purchases_remaining`

SHALL NOT be introduced into entitlement persistence as authority when deterministically derivable.

### D. Obligation purchase guard

Call the lawful Obligations read surface when the product acquisition is conditioned on an obligation outcome.

If purchase is blocked by an outstanding obligation rule, abort before monetary mutation.

The exact denial reason SHALL come from Obligations authority rather than being reconstructed in Store code.

### E. Financial resolution

Calculate the intended purchase amount from authoritative Policy configuration.

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

### B. Entitlement grants

After the Ledger purchase is lawfully established, create one entitlement event per purchased unit.

For each purchased unit:

- `class_id` = canonical context class;
- `target_seat_id` = purchasing seat;
- `actor_seat_id` = purchasing seat;
- `product_id` = configured product identifier;
- `acquisition_type` = `PURCHASE`;
- `event_type` = `GRANTED`;
- `entitlement_type` = lawful entitlement kind for the product;
- `correlation_id` = purchase lifecycle correlation;
- `timestamp` = canonical transaction timestamp;
- `payload` = canonical type-specific facts required by the entitlement contract.

A purchase of quantity `5` SHALL create five distinct entitlement-event rows with:

- five distinct `event_id` values;
- the same `entitlement_id` lineage for the grant lifecycle when lawfully required by the product contract;
- the same `class_id`;
- the same target and actor seat;
- the same `product_id`;
- the same `acquisition_type`;
- the same `correlation_id`.

### C. Instant-use capability

If the configured product is immediate-use, the purchase FEAT SHALL coordinate the grant and lawful consumption in the same transaction.

If Store and Entitlements owns the consumption:

1. create the entitlement grant event;
2. create the `CONSUMED` event for the same entitlement lifecycle;
3. do not persist a duplicate or mutable consumption balance.

If another domain owns the consumption:

1. create the entitlement grant event;
2. invoke the lawful consuming-domain FEAT or primitive;
3. require the consuming record to reference the exact entitlement lineage;
4. do not create a duplicate Store-and-Entitlements consumption record.

### D. Perk capability

If an entitlement is produced as a perk, the purchase FEAT SHALL NOT decide whether the perk was earned.

The lawful upstream FEAT or coordinating domain supplies the entitlement-grant authority.

This FEAT only writes the resulting entitlement grant event when the upstream authority has lawfully established the right to receive it.

### E. Collective-goal capability

Collective-goal purchases use the ordinary purchase path.

The FEAT SHALL NOT create a collective-progress record merely because the configured offering is collective.

Each purchased unit creates one entitlement lifecycle according to the product contract.

Collective activation or exercisability remains a projection over:

- Policy rules;
- authoritative qualifying economic events; and
- canonical temporal context.

## VIII. Purchase Reversal Boundary

This FEAT does not itself reverse completed purchases.

If a separate lawful reversal/refund FEAT exists, it may revoke the purchase outcome only when:

- the entitlement remains unused;
- no authoritative terminal or cross-domain consumption event exists;
- the configured capability is lawfully refundable;
- the capability is not insurance;
- the Ledger reversal/refund succeeds within the coordinated transaction.

Revocation SHALL be recorded as a separate entitlement event with:

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
