# FEAT-STOR-002: Entitlement Terminal Lifecycle

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-STOR-002 | 1.0 | 2026-07-22 | N/A | Normative |

## I. Purpose

Define the lawful orchestration paths by which an atomic entitlement reaches a terminal state owned by the Store and Entitlements domain.

Store-and-Entitlements-owned terminal dispositions are:

- `CONSUMED`
- `EXPIRED`
- `REVOKED`

A terminal event does not rewrite or delete the original entitlement grant. It creates a new immutable fact in `entitlement_consumptions`.

This FEAT does not duplicate consumption events whose authoritative business meaning belongs to another domain.

## II. Authority

This FEAT coordinates Store-and-Entitlements-owned terminal lifecycle events.

It does not own:

- entitlement grant history;
- Class Configuration directives;
- Ledger reversal/refund truth;
- cross-domain consumption facts;
- insurance claim decisions;
- productivity, payroll, obligation, or other domain state.

An entitlement may have no more than one authoritative terminal event.

## III. Required Context

Authenticated request paths SHALL enter with canonical context already resolved.

As applicable:

- `user_id`
- `class_id`
- `seat_id`
- `actor_role`

System-driven expiration SHALL use explicit canonical class/seat identifiers and canonical temporal context rather than reconstructing request context.

## IV. Common Preconditions

Before any terminal mutation, the FEAT SHALL establish:

1. the entitlement exists;
2. it belongs to the expected `class_id` and target seat;
3. no Store-and-Entitlements terminal event already exists;
4. no authoritative cross-domain consumption event already exists;
5. the requested disposition is lawful for the entitlement's provenance and configured capability semantics.

Failure to establish any required fact SHALL fail closed.

## V. Consumption Workflow

### A. Store-owned consumption

When exercising the entitlement produces no authoritative business event owned by another domain, this FEAT may create:

- `disposition = CONSUMED`

through `consume_entitlement(...)`.

The FEAT SHALL validate:

- the entitlement is currently exercisable;
- any configured activation condition is satisfied;
- the entitlement has not expired;
- the actor is permitted to exercise or authorize the benefit;
- no prior terminal or cross-domain consumption exists.

The created row SHALL reference the exact `entitlement_id`.

### B. Cross-domain consumption

When exercising the entitlement produces an authoritative event owned by another domain, this FEAT SHALL NOT create `CONSUMED`.

Instead:

1. the consuming domain's lawful FEAT validates the entitlement through Store and Entitlements reads;
2. the consuming domain creates its authoritative event;
3. that event references the exact `entitlement_id`;
4. Store and Entitlements derives that the entitlement is no longer available from the authoritative cross-domain event.

Example:

A hall-pass entitlement is consumed by the Productivity and Payroll domain through `hall_pass_logs`. No duplicate `entitlement_consumptions` row is created.

## VI. Expiration Workflow

Expiration creates:

- `disposition = EXPIRED`

through `expire_entitlement(...)`.

Expiration is lawful only when:

- Class Configuration defines a finite validity or coverage boundary;
- canonical temporal resolution proves that boundary has been reached;
- the entitlement has not already terminated or been consumed elsewhere.

Expiration SHALL NOT rewrite the grant.

### Insurance expiration

Insurance claims do not consume insurance coverage.

During an active coverage cycle, one insurance entitlement may be referenced by multiple `insurance_claims` rows according to configured claim limits.

Claim submission, approval, or rejection SHALL NOT create a terminal entitlement event.

When the coverage boundary is reached, the insurance entitlement terminates through:

- `disposition = EXPIRED`.

Teacher cancellation of an insurance offering is prospective and SHALL NOT cause early expiration of existing coverage.

## VII. Revocation Workflow

Revocation creates:

- `disposition = REVOKED`

through `revoke_entitlement(...)`.

Revocation authority depends on provenance and capability semantics.

### A. Manual grant

A `MANUAL_GRANT` entitlement may be revoked by a lawful teacher actor while unused.

The original grant remains immutable history.

### B. Ordinary purchase

An ordinary `PURCHASE` entitlement may be revoked only through a lawful coordinated Ledger reversal/refund workflow.

The FEAT SHALL require:

- the entitlement remains unused;
- the capability is refundable;
- the capability is not insurance or otherwise explicitly non-revocable;
- the corresponding Ledger reversal/refund is authorized;
- entitlement revocation and monetary reversal participate in the required coordinated transaction.

A route or teacher action SHALL NOT directly revoke an ordinary purchased entitlement independently of Ledger reversal authority.

### C. Insurance

A lawfully purchased insurance entitlement SHALL NOT be revoked or refunded.

Teacher cancellation affects future acquisition or renewal only.

Existing coverage remains valid until its configured coverage boundary and then expires normally.

### D. Obligation grant

An entitlement with:

- `grant_type = OBLIGATION`

SHALL NOT be revoked.

Any correction to the originating obligation lifecycle must follow the lawful Obligations contract and SHALL NOT erase the historical entitlement grant through this FEAT.

## VIII. Instant-Use Coordination

For an instant-use Store-owned capability, `FEAT-STOR-001` may coordinate this FEAT within the original purchase transaction.

The transaction SHALL:

1. create the atomic entitlement;
2. create `CONSUMED` for that exact entitlement;
3. commit the purchase, grant, and consumption atomically.

If another domain owns the immediate exercise, that domain's authoritative consumption event replaces the Store-owned `CONSUMED` write.

## IX. Idempotency

Terminal lifecycle operations SHALL be idempotent.

A replay of the same lawful terminal operation SHALL NOT create a second terminal event.

A request attempting a different disposition after an authoritative terminal event exists SHALL fail.

## X. Correlation and Lineage

Every terminal event SHALL carry a lawful `correlation_id`.

For manual consumption or revocation, the correlation identifies that lifecycle.

For purchase revocation, correlation SHALL preserve lineage to the coordinated Ledger reversal/refund workflow.

For expiration, correlation SHALL identify the lawful expiration operation or batch lifecycle without converting audit lineage into business authority.

## XI. Failure Contract

Representative failures include:

- `ENTITLEMENT_NOT_FOUND`
- `SCOPE_MISMATCH`
- `ENTITLEMENT_NOT_EXERCISABLE`
- `ENTITLEMENT_ALREADY_TERMINATED`
- `ENTITLEMENT_ALREADY_CONSUMED_EXTERNALLY`
- `NOT_YET_EXPIRED`
- `REVOCATION_PROHIBITED`
- `INSURANCE_NON_REVOCABLE`
- `OBLIGATION_GRANT_NON_REVOCABLE`
- `LEDGER_REVERSAL_REQUIRED`
- `CROSS_DOMAIN_FAILURE`

## XII. Prohibited Patterns

The following are prohibited:

- mutating or deleting the original entitlement grant to represent termination;
- storing `status = consumed/expired/revoked` on the entitlement row as canonical authority;
- creating both a Store `CONSUMED` row and a cross-domain consumption record for the same exercise;
- revoking purchased items without lawful Ledger reversal/refund coordination;
- revoking or refunding insurance coverage;
- revoking obligation-derived entitlements;
- treating insurance claim submission, approval, or rejection as entitlement consumption;
- expiring active insurance early because the teacher cancelled future coverage;
- deriving expiration from server-local time instead of canonical temporal context.

## XIII. Postconditions

On successful Store-owned termination:

1. the original entitlement grant remains unchanged;
2. exactly one authoritative terminal fact exists;
3. the terminal fact references the exact entitlement;
4. availability projections exclude the terminated entitlement;
5. any required cross-domain coordinated effect has completed atomically.

## XIV. Amendment

Revisions must remain consistent with `DOM-STORE-001`, `FEAT-STOR-001`, Ledger authority, Class Configuration authority, consuming-domain authority, and the governing FEAT and temporal invariants.
