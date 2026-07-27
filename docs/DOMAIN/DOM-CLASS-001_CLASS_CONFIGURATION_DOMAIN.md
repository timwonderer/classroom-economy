# DOM-CLASS-001: Class Configuration Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-CLASS-001 | 3.0 | 2026-07-27 | 2.5 | Constitutional |

## I. Purpose

This document defines the class-level configuration boundary for Classroom Token Hub.

Class Configuration answers:

> What class exists, who owns it, what is its operating identity, and what class-level economics and feature settings define it?

This domain owns the setup that applies to the class as a whole, not the rules for individual classroom domains.

## II. Scope

This domain governs:

- `classes`
- `feature_settings`
- `class_features`

This domain does not govern domain-specific setup such as rent rules, store offerings, insurance policies, payroll rules, or banking rules.

## III. Authority Level

Tier 1 - Constitutional. This document is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-IDEN-001_CANONICAL_IDENTITY_MODEL.md`

## V. Class-Level Boundary

Class Configuration owns the class boundary and the class-level operating facts used by all other domains.

Owned class-level facts include:

- `class_id`
- teacher user identity binding
- class display name
- `section`
- `timezone`
- feature enablement
- CWI configuration
- expected hours of work per week
- CWI-derived ratio bands
- price-range framing

`timezone` is fixed at class creation and MUST NOT be mutated afterward.

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `classes`
- `feature_settings`
- `class_features`

`classes` establishes the canonical class boundary.
`feature_settings` stores class-level economic setup.
`class_features` stores feature enablement by class.

## VII. Owned Tables

### 1. `classes`

Canonical class boundary records.

Key fields:

- `class_id`
- `join_code`
- `display_name`
- `section`
- `timezone`
- `teacher_user_id`
- `created_at`
- `updated_at`

Rules:

- One record per class.
- `class_id` is the canonical class boundary.
- `join_code` is the public alias for the class.
- `timezone` is fixed at class creation.
- Class deletion removes the class record and all class-owned configuration rows.

### 2. `feature_settings`

Class-level economic setup and projection state.

Key fields:

- `id`
- `class_id`
- `economy_policy_mode`
- `economy_policy_updated_at`
- `economy_last_rebalanced_at`
- `economy_last_rebalanced_by`
- `economy_pending_rebalance_json` - deprecated transitional field

Rules:

- One record per class.
- Stores class-level economic setup only.
- The field set is projection state, not operational execution truth.
- Deprecated transitional fields MUST be removed through the migration plan.

### 3. `class_features`

Feature enablement by class.

Key fields:

- `id`
- `class_id`
- `feature_name`
- `created_at`

Rules:

- One row per enabled feature per class.
- Absence of a row means the feature is disabled.

## VIII. Constraints

- This domain stores class-level configuration only.
- It does not own domain-specific setup for rent, store, insurance, payroll, or banking.
- It does not mutate ledger, attendance, obligations, or entitlement tables.
- All class-level configuration must be scoped by `class_id`.
- `join_code` is display-only and user-entered at boundaries; it does not replace `class_id` as authority and must not be used for internal routing or persistence references.
- Feature enablement is class-level capability state, not domain policy state.

## IX. Derived / Cross-Domain Rules

- Other domains consume class-level configuration from this domain.
- `timezone` governs class-level temporal interpretation.
- FEAT orchestration may read class-level configuration, but it does not own it.
- Class creation and class deletion are class-level mutation workflows.

## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
