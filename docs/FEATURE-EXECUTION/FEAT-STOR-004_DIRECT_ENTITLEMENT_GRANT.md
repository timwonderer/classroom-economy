# FEAT-STOR-004: Direct Entitlement Grant

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-STOR-004 | 1.0 | 2026-07-27 | N/A | Normative |

## I. Purpose

Define the lawful orchestration path by which a teacher directly grants an entitlement to a seat.

This FEAT is the single lawful path for:

- teacher-directed entitlement grants;
- direct hall-pass grants;
- direct privilege grants;
- any other entitlement type that the governing policy explicitly allows a teacher to grant directly.

This FEAT SHALL NOT maintain entitlement balances or mutable grant counters.

## II. Authority

This FEAT is the sole lawful writer for entitlement grants with:

- `acquisition_type = GRANT`
- `event_type = GRANTED`

when the grant originates from a teacher-authorized direct grant.

It does not own:

- class configuration;
- policy definitions;
- Ledger truth;
- obligation truth;
- pending request storage;
- consumption or revocation history.

## III. Dependencies

- `FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `DOM-POL-001_POLICIES_DOMAIN.md`
- lawful teacher-directed grant policy contracts
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

## IV. Required Execution Context

The caller SHALL resolve canonical request context before entering this FEAT.

Required canonical context:

- `user_id`
- `class_id`
- `seat_id`
- `actor_role = teacher`

The FEAT SHALL NOT reconstruct teacher authority from route-local lookups or display labels.

## V. Required Inputs

The FEAT accepts:

- canonical request context;
- `policy_uuid` — exact immutable policy locator;
- `target_seat_id` — seat receiving the direct grant;
- `idempotency_key` — request replay guard;
- optional canonical grant payload required by the product type.

The FEAT generates or resolves:

- `correlation_id` — one identifier for the direct grant lifecycle;
- canonical transaction timestamp through the temporal model.

## VI. Read-Only Validation Phase

All validation SHALL complete before mutation begins.

### A. Canonical context validation

Verify:

- the actor is a lawful teacher seat for `class_id`;
- the target seat exists within the class boundary;
- the target seat is allowed to receive the direct grant under the configured policy.

### B. Policy validation

Read the configured product definition through the lawful Class Configuration / Policies interface.

Validate, as applicable:

- the product exists for `class_id`;
- the product supports direct grants;
- the product version is lawful and effective for the current temporal context;
- the requested entitlement type is permitted for direct grant;
- any seat-specific eligibility rules permit the grant.

The FEAT SHALL NOT copy product configuration into Store and Entitlements persistence merely to make later reads convenient.

## VII. Mutation Phase

All coordinated mutations SHALL occur within one lawful transaction boundary.

### A. Entitlement grant

Create one entitlement event per direct grant unit.

For each granted unit:

- `class_id` = canonical context class;
- `target_seat_id` = target seat;
- `actor_seat_id` = teacher seat;
- `product_id` = configured product identifier;
- `acquisition_type` = `GRANT`;
- `event_type` = `GRANTED`;
- `entitlement_type` = lawful entitlement kind for the product;
- `correlation_id` = grant lifecycle correlation;
- `timestamp` = canonical transaction timestamp;
- `payload` = canonical type-specific facts required by the entitlement contract.

### B. Grant quantity

If the direct grant issues multiple units, the FEAT SHALL create one immutable entitlement event per unit.

The FEAT SHALL NOT persist a direct-grant balance counter.

### C. Teacher hall-pass grant

Hall-pass grants are direct grants when the policy permits them.

The FEAT SHALL NOT create a hall-pass balance row.

The FEAT SHALL NOT use productivity consumption records as the entitlement source of truth.

## VIII. Lawful Postconditions

On successful direct grant:

1. the grant event exists as canonical Store and Entitlements truth;
2. the target seat is lawfully entitled according to the product contract;
3. any subsequent consumption or revocation follows the lawful lifecycle FEAT;
4. no mutable grant counter exists.

## IX. Idempotency

`idempotency_key` SHALL protect the complete grant lifecycle.

A replay of the same lawful direct grant SHALL NOT produce duplicate entitlement events.

## X. Failure Contract

Representative failures include:

- `TEACHER_AUTHORITY_REQUIRED`
- `TARGET_SEAT_NOT_FOUND`
- `SCOPE_MISMATCH`
- `PRODUCT_NOT_DIRECT_GRANTABLE`
- `PRODUCT_NOT_EFFECTIVE`
- `ENTITLEMENT_ALREADY_GRANTED`
- `CROSS_DOMAIN_FAILURE`

## XI. Amendment

Revisions must remain consistent with `DOM-STORE-001`, `FEAT-STOR-001`, `FEAT-STOR-002`, `FEAT-STOR-003`, `DOM-CLASS-001`, `DOM-POL-001`, and the governing FEAT and temporal invariants.
