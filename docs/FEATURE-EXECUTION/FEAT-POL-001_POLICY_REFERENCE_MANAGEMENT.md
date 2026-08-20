# FEAT-POL-001: Policy Reference Management

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-POL-001 | 2.0 | 2026-07-28 | 1.0 | Normative |

## I. Purpose

Define the lawful execution path for mutating Policies domain reference lineage.

This FEAT is the single lawful path for:

- creating a new policy reference row;
- updating a policy family by creating a new immutable version;
- hiding a policy from new selection;
- retiring a policy definition;
- deleting a retired policy definition once live dependencies have drained.

This FEAT owns orchestration only.

It SHALL NOT mutate downstream domain facts directly.

## II. Authority

This FEAT is authorized by:

- `DOM-POL-001_POLICIES_DOMAIN.md`
- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

## III. Required Context

Required canonical context:

- `user_id`
- `class_id`
- `seat_id`
- `actor_role = teacher`

The teacher seat SHALL be lawful for the class boundary.

This FEAT SHALL NOT reconstruct authority from labels, block names, join codes, or route-local state.

## IV. Scope and Model

Policies are class-scoped reference lineage for domain-specific rules and products.

Each policy submission MUST create a new immutable definition row with a new `policy_uuid`.

Each policy row MUST have an immutable definition payload and a mutable availability state.

The canonical policy lineage SHALL capture, at minimum:

- policy identity within the class;
- policy family;
- stable family/product identifier;
- immutable definition payload;
- availability state.

The exact definition schema is family-specific and is defined by the owning policy family.

## V. New Policy

New Policy SHALL:

1. create a new policy row for the requested family;
2. assign a new immutable `policy_uuid`;
3. persist the family-specific payload;
4. set availability to `IN_USE` unless the caller explicitly requests `HIDDEN`.

## VI. Update Policy

Update Policy SHALL create a new immutable replacement row with a new `policy_uuid`.

Update SHALL NOT rewrite the immutable definition payload in place.

`HIDDEN` rows remain readable and may later return to `IN_USE`.

Any teacher submission that changes the policy settings, even punctuation-only changes, creates a new immutable policy version.

## VII. Retire Policy

Retire Policy SHALL:

1. move the policy row to `RETIRED`;
2. leave downstream authoritative facts unchanged;
3. require downstream facts to remain executable from their copied payload or snapshot data.

`RETIRED` rows MUST NOT be selectable for new work.
`RETIRED` rows MAY remain readable while live dependencies exist.

## VIII. Delete Policy

Delete Policy SHALL remove the retired policy definition only after all live dependencies have drained.

If a downstream domain still requires the policy for a live executable capability, the row SHALL remain readable until that capability ends.

## IX. Downstream Contract

Policies are a reference library, not a runtime dependency for already-created facts.

Downstream domains must snapshot the specifics they need at creation time, or continue to retain the exact `policy_uuid` while the created fact remains executable.

Examples:

- an insurance entitlement must encode or retain the limits, benefits, and claim rules it needs to keep processing claims even if the source policy is later removed;
- a store purchase record must encode the entitlement specifics required to honor that purchase later;
- a rent assessment must carry the policy UUID and the terms needed to continue processing that assessment;
- a claim record must encode the rule details required to evaluate the claim without rereading the source policy.

## X. FEAT-POL Contract

FEAT-POL actions:

- `New` creates a new policy row and immutable definition.
- `Update` creates a new policy row with a new `policy_uuid`.
- `Disable` sets the current row to `HIDDEN`.
- `Retire` sets the current row to `RETIRED`.
- `Delete` removes a retired row only when live dependencies have drained.

FEAT-POL MUST NOT mutate downstream domain facts directly.
FEAT-POL MUST NOT rewrite historical downstream facts to match changed policy terms.

## XI. Persistence and Schema Status

The v2 persistence model is:

- one immutable `policy_uuid` per policy definition row;
- one stable family/product identity per policy concept;
- one mutable availability state per row;
- one immutable definition payload per row;
- no foreign keys from downstream domains to Policies;
- downstream domains store `policy_uuid` as a non-FK locator and freeze the terms they need.

Availability states:

- `IN_USE` - selectable for new work
- `HIDDEN` - not selectable for new work, but may return to `IN_USE`
- `RETIRED` - not selectable for new work, may remain readable while live dependencies drain, and may later be physically deleted

Definition payloads are immutable after insert.
Replacement creates a new `policy_uuid`.
Deletion is allowed only after live dependencies drain.

## XII. Boundary Examples

The intended boundary is:

- rent enablement -> Class Configuration
- rent settings -> Policies
- rent-granted items -> Store and Entitlements
- store offerings -> Policies
- insurance definitions -> Policies
- insurance entitlement lifecycle -> Store and Entitlements

This means Class Configuration decides whether a capability exists in the class, Policies defines the class-customized reference material for that capability, and the consuming domain owns the resulting fact.

### XII.A Hall-Pass Policy Family

Hall-pass settings are immutable policy definitions. Each submission creates a
new row with a new `policy_uuid`, `class_id`, `max_queue_limit`,
`pass_type_payload`, and `effective_date`.

`pass_type_payload` is teacher-provided and each entry SHALL contain exactly:

- `pass_name`;
- `max_queue`;
- `consume_pass` (boolean).

The effective queue capacity is the lower of the class-wide
`max_queue_limit` and the sum of the per-pass `max_queue` values. A teacher
submission SHALL notify the teacher when per-pass limits reduce the effective
capacity below the configured class-wide limit.

The student break-reason selector SHALL read the active hall-pass policy
payload. Historical policy rows SHALL remain readable for provenance.

## XIII. Amendment

Revisions must remain consistent with `DOM-CLASS-001`, the consuming operational domain, and the governing FEAT and temporal invariants.
