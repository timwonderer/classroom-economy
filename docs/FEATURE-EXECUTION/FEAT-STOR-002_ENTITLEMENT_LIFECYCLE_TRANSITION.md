# FEAT-STOR-002: Entitlement Lifecycle Transition

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-STOR-002 | 2.0 | 2026-07-27 | 1.0 | Normative |

## I. Purpose

Define the lawful orchestration path by which an entitlement reaches a Store-owned lifecycle disposition.

This FEAT coordinates:

- Store-owned consumption;
- Store-owned expiration;
- Store-owned revocation;
- cross-domain consumption handoff when another domain owns the authoritative exercise event.

The FEAT SHALL NOT mutate the entitlement grant row to represent terminal state.
It SHALL write immutable entitlement events only.

## II. Authority

This FEAT is the sole lawful writer for entitlement lifecycle events with:

- `event_type = CONSUMED`
- `event_type = EXPIRED`
- `event_type = REVOKED`

when Store and Entitlements owns the lifecycle disposition.

It does not own:

- grant creation;
- class configuration;
- policy definitions;
- Ledger truth;
- obligations truth;
- Productivity or Attendance truth;
- another domain's authoritative exercise event.

## III. Dependencies

- `FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `DOM-POL-001_POLICIES_DOMAIN.md`
- `DOM-LED-001_LEDGER_DOMAIN.md`
- lawful consuming-domain FEAT contracts
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

System-driven expiration SHALL use explicit canonical class/seat identifiers and canonical temporal context.

The FEAT SHALL NOT reconstruct seat or class authority from labels, route-local lookups, or cached UI state.

## V. Common Preconditions

Before any lifecycle mutation, the FEAT SHALL establish:

1. the entitlement exists;
2. it belongs to the expected `class_id` and target seat;
3. no conflicting terminal lifecycle event already exists;
4. the requested disposition is lawful for the entitlement type and acquisition provenance;
5. any required cross-domain event has not already been recorded.

Failure to establish any required fact SHALL fail closed.

## VI. Store-Owned Consumption

When Store and Entitlements owns the exercise of the entitlement, this FEAT may create:

- `event_type = CONSUMED`

through `consume_entitlement(...)`.

The FEAT SHALL validate:

- the entitlement is currently exercisable;
- any configured activation condition is satisfied;
- the entitlement has not already terminated;
- the actor is permitted to exercise or authorize the benefit;
- no prior terminal or cross-domain consumption exists.

The created event SHALL reference the exact `entitlement_id`.

An entitlement type may lawfully support multiple `CONSUMED` events when its lifecycle semantics permit repeated exercise.

## VII. Cross-Domain Consumption

When exercising the entitlement produces an authoritative event owned by another domain, this FEAT SHALL NOT create a Store-owned `CONSUMED` event for the same exercise.

Instead:

1. the consuming domain's lawful FEAT validates the entitlement through Store and Entitlements reads;
2. the consuming domain creates its authoritative exercise event;
3. that event references the exact `entitlement_id`;
4. Store and Entitlements derives that the entitlement is no longer available from the authoritative cross-domain event.

Example:

A hall-pass entitlement is exercised by the Productivity/Hall-Pass domain through `hall_pass_logs`. No duplicate Store-owned consumption row is created.

## VIII. Expiration

Expiration creates:

- `event_type = EXPIRED`

through `expire_entitlement(...)`.

Expiration is lawful only when:

- the governing policy or product defines a finite validity or coverage boundary;
- canonical temporal resolution proves that boundary has been reached;
- the entitlement has not already terminated or been exercised elsewhere.

Expiration SHALL NOT rewrite the grant.

### Insurance expiration

Insurance entitlements may be exercised multiple times during an active coverage cycle according to policy and claim rules.

When the coverage boundary is reached, the insurance entitlement terminates through:

- `event_type = EXPIRED`.

Teacher cancellation of an insurance offering is prospective and SHALL NOT cause early expiration of existing coverage.

## IX. Revocation

Revocation creates:

- `event_type = REVOKED`

through `revoke_entitlement(...)`.

Revocation authority depends on provenance, entitlement type, and policy semantics.

### A. Direct grant

A direct teacher grant may be revoked by a lawful teacher actor while unused.

The original grant remains immutable history.

### B. Ordinary purchase

An ordinary purchased entitlement may be revoked only through a lawful coordinated Ledger reversal/refund workflow when that entitlement type permits revocation.

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

### D. Obligations-derived perks

An entitlement with acquisition provenance `PERK` SHALL NOT be revoked by this FEAT unless the owning policy explicitly allows it.

Any correction to the originating obligation lifecycle must follow the lawful Obligations contract and SHALL NOT erase the historical entitlement event through this FEAT.

## X. Instant-Use Coordination

For an instant-use Store-owned capability, `FEAT-STOR-001` may coordinate this FEAT within the original purchase transaction.

The transaction SHALL:

1. create the entitlement grant event;
2. create the `CONSUMED` event for that exact entitlement lifecycle;
3. commit the purchase, grant, and consumption atomically.

If another domain owns the immediate exercise, that domain's authoritative exercise event replaces the Store-owned `CONSUMED` write.

## XI. Idempotency

Lifecycle operations SHALL be idempotent.

A replay of the same lawful lifecycle operation SHALL NOT create duplicate terminal events.

A request attempting a different terminal disposition after an authoritative event exists SHALL fail.

## XII. Correlation and Lineage

Every terminal event SHALL carry a lawful `correlation_id`.

For manual consumption or revocation, the correlation identifies that lifecycle.

For purchase reversal, correlation SHALL preserve lineage to the coordinated Ledger reversal/refund workflow.

For expiration, correlation SHALL identify the lawful expiration operation or batch lifecycle without converting audit lineage into business authority.

## XIII. Failure Contract

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

## XIV. Prohibited Patterns

The following are prohibited:

- mutating or deleting the original entitlement grant to represent termination;
- storing status on the grant row as canonical authority;
- creating both a Store `CONSUMED` row and a cross-domain consumption record for the same exercise;
- revoking purchased items without lawful Ledger reversal/refund coordination when revocation is permitted;
- revoking or refunding insurance coverage;
- revoking obligation-derived entitlements contrary to policy;
- treating insurance claim submission, approval, or rejection as entitlement consumption;
- expiring active insurance early because the teacher cancelled future coverage;
- deriving expiration from server-local time instead of canonical temporal context.

## XV. Postconditions

On successful Store-owned termination:

1. the original entitlement grant remains unchanged;
2. exactly one authoritative lifecycle fact exists for the disposition;
3. the terminal fact references the exact entitlement;
4. availability projections exclude the terminated entitlement;
5. any required cross-domain coordinated effect has completed atomically.

## XVI. Amendment

Revisions must remain consistent with `DOM-STORE-001`, `FEAT-STOR-001`, `DOM-CLASS-001`, `DOM-POL-001`, `DOM-LED-001`, and the governing FEAT and temporal invariants.
