# FEAT-CLASS-003: Insurance Policy Management

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-CLASS-003 | 0.1 | 2026-07-23 | N/A | Normative |

## I. Purpose

Define the canonical class-configuration workflow for managing insurance policy offerings within a class.

This FEAT governs:

- creating an insurance policy offering;
- editing an existing policy by creating a new prospective version;
- marking a policy inactive so it is not offered for new enrollment;
- deleting a policy lineage after existing coverage has drained;
- defining same-group switching rules;
- defining bundle eligibility rules across standalone and tiered policies;
- producing student-visible policy-change notifications.

This FEAT owns orchestration only.

It SHALL NOT mutate entitlement, obligation, or ledger records directly.

## II. Authority

This FEAT is authorized by:

- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

This FEAT is the sole lawful orchestrator for class-side insurance policy configuration changes.

## III. Required Context

Required canonical context:

- `user_id`
- `class_id`
- `seat_id`
- `actor_role = teacher`

The teacher seat SHALL be lawful for the class boundary.

This FEAT SHALL NOT reconstruct authority from labels, block names, join codes, or route-local state.

## IV. Scope and Model

Insurance policy configuration is class-scoped lineage.

Each change that materially alters policy terms SHALL create a new prospective version rather than mutating the historical contract in place.

The canonical policy lineage SHALL capture, at minimum:

- policy identity within the class;
- `entitlement_item_id` mapping to the configured Store-and-Entitlements offering used for purchase grant;
- group identity for tier-switch eligibility;
- version number;
- pricing and waiting-period terms;
- claim-related limits;
- bundle definitions;
- active/inactive offering state;
- deletion scheduling state;
- student-facing notification payload.

This FEAT SHALL NOT add foreign keys from class configuration into entitlement, obligation, or ledger tables.

## V. Create Policy

Policy creation SHALL:

1. create a new class-scoped insurance policy lineage row;
2. initialize the first version for that policy;
3. record its prospective enrollment rules;
4. bind the policy to the configured entitlement item used by FEAT-STOR-001 to grant the purchased insurance entitlement;
5. expose the policy to class reads if it is active;
6. create a student-visible notice that a new policy is available, when the product is meant to be discoverable by students.

## VI. Edit Policy

Policy edit SHALL create a new prospective version when the teacher changes contractual terms.

The edit workflow SHALL preserve historical versions.

The following are versioned policy terms:

- title;
- description;
- premium;
- charge frequency;
- autopay behavior;
- waiting period;
- claim window;
- claim limits;
- payout limits;
- repurchase restrictions;
- bundle definitions;
- tier-group assignment;
- tier label and display color;
- configured entitlement item binding;
- active/inactive offering state.

When an edit materially changes terms, the FEAT SHALL:

1. create the new version row;
2. mark the version active for future enrollment, if applicable;
3. preserve existing enrollments on their current terms;
4. emit a persistent student-visible banner describing the change.

## VII. Inactivate Policy

Inactivation means:

- the policy remains part of class history;
- the policy is not available for new enrollment;
- existing entitlements and obligations remain unchanged;
- the policy may be reactivated later if the teacher chooses.

Inactivation SHALL NOT mutate entitlement, obligation, or ledger facts.

## VIII. Delete Policy

Deletion is a class-configuration operation.

Deletion means:

- remove all class-owned insurance policy lineage rows for the policy within the class;
- do not change entitlement rows;
- do not change obligation rows;
- do not change ledger rows;
- do not rewrite historical events owned by other domains.

Deletion SHALL be deferred until the last currently enforced entitlement for the policy lineage has ended.

Before scheduling deletion, the FEAT SHALL ask the Entitlement authority for:

- the end boundary of the last currently enforced entitlement for the policy lineage in the class.

If no currently enforced entitlement exists, deletion MAY proceed immediately.

If at least one entitlement remains in force, the FEAT SHALL schedule the hard delete for the resolved end boundary.

Deletion SHALL produce a persistent student-visible banner stating that:

- the policy is discontinued;
- no new enrollment is available;
- current coverage remains valid through the applicable end date;
- the configuration will be permanently removed.

## IX. Switching

Switching is enrollment into a different policy within the same tier group.

Switching SHALL:

- require the source policy and target policy to belong to the same group;
- treat the switch as a new policy enrollment rather than a cancellation;
- set the source policy end date equal to the target policy waiting-period start date;
- preserve any configured waiting period on the target policy;
- not bypass the target policy waiting period.

The waiting period on the new policy SHALL begin when the new policy begins.

If a target policy is withdrawn before its effective start, the pending switch SHALL fail and the student SHALL be notified.

## X. Bundle Eligibility

Bundle discounts are class-configuration rules.

The bundle eligibility rule SHALL operate in one of two ways:

1. concurrent enrollment in the specified standalone non-grouped policies; or
2. concurrent enrollment in one policy from the referenced tiered group plus the other specified policy.

A bundle definition MAY reference:

- standalone non-grouped policies; or
- a policy group, where any tier in the group satisfies that bundle slot.

If any bundled item belongs to a tier group, the entire group SHALL be eligible for that bundle slot.

Bundle evaluation SHALL treat concurrent enrollment in the qualifying policies as the eligibility condition.

## XI. Student Notifications

Policy create, edit, inactivate, switch-affecting change, and delete scheduling SHALL emit a student-visible notification.

The notification SHALL be rendered as a persistent banner until dismissed.

The banner content SHALL identify:

- the policy name;
- the type of change;
- the effective boundary when applicable;
- whether the policy remains available for new enrollment;
- whether existing coverage remains valid.

## XII. Delegation

This FEAT delegates read/write authority to:

- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- the canonical entitlement boundary read surface for deletion scheduling
- the lawful student notification persistence surface
- the lawful cross-domain enrollment orchestration FEATs that consume this class configuration

## XIII. Guarantees

This FEAT guarantees:

- policy edits never silently mutate historical coverage;
- switching stays within the configured policy group;
- bundle eligibility honors tier groups as a whole;
- policy deletion does not rewrite downstream domain facts;
- students receive visible notice of policy changes.
