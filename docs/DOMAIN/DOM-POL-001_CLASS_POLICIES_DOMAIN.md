# DOM-POL-001: Class Policies Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-POL-001 | 1.0 | 2026-07-27 | N/A | Constitutional |

## I. Purpose

This document defines the class-specific policy boundary for Classroom Token Hub.

Policies answer:

> What customized setup has this class established for each domain?

This domain owns domain-specific setup, not class-level setup.

## II. Scope

This domain governs customized setup for class domains such as:

- rent
- store
- insurance
- payroll
- banking
- hall pass

This domain does not govern class-level setup such as timezone, class identity, join code, class display name, or feature enablement.

## III. Authority Level

Tier 1 - Constitutional. This document is subordinate to `INV-CORE-000`, `INV-CORE-001`, and `DOM-CLASS-001`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`

## V. Policy Boundary

Policy owns the class-specific setup that shapes how a domain behaves in this class.

Examples include:

- `rent_settings`
- `store_items`
- `insurance_policies`
- `payroll_settings`
- `payroll_rewards`
- `payroll_fines`
- `banking_settings`
- `hall_pass_settings`

Policy is not the execution of those domains. It is the teacher-customized setup those domains consume.

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `rent_settings`
- `store_items`
- `insurance_policies`
- `payroll_settings`
- `payroll_rewards`
- `payroll_fines`
- `banking_settings`
- `hall_pass_settings`
- `policy_versions`
- `policy_transitions`

Policy-owned tables are class-scoped and may be versioned when the domain requires historical or future validity.
All policy-owned tables MUST carry an explicit version number when the table represents domain rules that are applied over time. Rule consumers MUST reference the specific version in effect for the relevant action or boundary.

## VII. Owned Tables

### 1. `rent_settings`

Class-specific rent setup.

Key fields:

- `id`
- `class_id`
- `version_number`
- `is_enabled`
- `rent_amount`
- `frequency_type`
- `grace_period_days`
- `late_penalty_amount`
- `late_penalty_type`
- `prevent_purchase_when_late`
- `bypass_cwi_warnings`

### 2. `store_items`

Class-specific store offering setup.

Key fields:

- `id`
- `class_id`
- `version_number`
- `title`
- `description`
- `price`
- `is_active`
- `is_bundle`
- `collective_goal_type`
- `collective_goal_target`

### 3. `insurance_policies`

Class-specific insurance setup.

Key fields:

- `id`
- `class_id`
- `version_number`
- `title`
- `description`
- `premium`
- `max_claim_amount`
- `max_payout_per_period`
- `max_claims_count`
- `max_claims_period`
- `claim_time_limit_days`
- `is_active`

### 4. `payroll_settings`

Class-specific payroll setup.

Key fields:

- `id`
- `class_id`
- `version_number`
- `pay_rate`
- `payroll_frequency_days`
- `daily_limit_hours`
- `time_unit`
- `overtime_enabled`
- `overtime_threshold`
- `max_time_per_day`
- `max_time_per_unit`
- `pay_schedule_type`
- `rounding_mode`
- `is_active`

### 5. `payroll_rewards`

Class-specific payroll reward setup.

Key fields:

- `id`
- `class_id`
- `version_number`
- `name`
- `description`
- `amount`
- `is_active`

### 6. `payroll_fines`

Class-specific payroll fine setup.

Key fields:

- `id`
- `class_id`
- `version_number`
- `name`
- `description`
- `amount`
- `is_active`

### 7. `banking_settings`

Class-specific banking setup.

Key fields:

- `id`
- `class_id`
- `version_number`
- `savings_apy`
- `savings_monthly_rate`
- `interest_calculation_type`
- `interest_schedule_type`
- `interest_schedule_cycle_days`
- `overdraft_protection_enabled`
- `overdraft_fee_enabled`
- `overdraft_fee_type`
- `is_active`

### 8. `hall_pass_settings`

Class-specific hall-pass setup.

Key fields:

- `id`
- `class_id`
- `version_number`
- `queue_enabled`
- `queue_limit`
- `pass_types`

### 9. `policy_versions`

Immutable policy lineage records for a class and domain.

### 10. `policy_transitions`

Append-only policy transition lineage for a class and domain.

## VIII. Constraints

- This domain stores domain-specific setup only.
- It does not own class-level setup.
- It does not compute operational outcomes.
- It does not mutate ledger, attendance, obligations, or identity tables.
- Policy changes that require historical integrity MUST use append-only version or transition lineage where applicable.
- `class_id` remains the isolation boundary for all policy rows.

## IX. Derived / Cross-Domain Rules

- Policy rows are consumed by the owning operational domain during execution.
- Class Configuration determines whether the relevant capability exists.
- Policy determines the customized setup for that capability in the class.
- FEAT orchestration may create or update policy rows only through the lawful policy workflow.

## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
