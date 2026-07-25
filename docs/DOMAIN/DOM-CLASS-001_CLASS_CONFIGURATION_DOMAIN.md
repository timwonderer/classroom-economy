# DOM-CLASS-001: Class Configuration Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-CLASS-001 | 2.4 | 2026-07-23 | 2.3 | Constitutional |

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-IDEN-001_CANONICAL_IDENTITY_MODEL.md` (class identity anchor `classes`)

## IV.A Terminology Formalization

- The canonical metadata field for a class-period label is `section`.
- `section` represents labels such as `2`, `Block A`, or `Period 1`.
- `block` is legacy display terminology for the class-period label and should only appear as historical or compatibility language.
- `display_name` represents the human-facing class title such as `Honors Chemistry`.
- Teacher-facing display should prefer `display_name` + `section`.
- Class-period metadata lives on the class record, not on seats.

## V. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `class_features`
- `feature_settings`
- `hall_pass_settings`
- `rent_settings`
- `payroll_settings`
- `payroll_rewards`
- `payroll_fines`
- `banking_settings`
- `policy_versions`
- `policy_transitions`

Policy-defined insurance offerings are class-configuration objects. Their prospective terms, version lineage, bundle eligibility, and withdrawal scheduling are owned here and coordinated by FEAT-CLASS-003. Downstream entitlement, obligation, and ledger records preserve different facts and SHALL NOT be rewritten to represent class configuration changes.
Each insurance policy lineage MUST also carry the configured `entitlement_item_id` used to mint the purchasable insurance entitlement through FEAT-STOR-001. That mapping is class configuration authority; the resulting entitlement row remains Store-and-Entitlements authority.

Insurance configuration rules:

- policy edits create a new prospective version rather than mutating the prior version in place;
- policy switching is only valid within the same tier group;
- if a bundle references a tiered policy, any tier in that group satisfies the bundle slot;
- policy deletion is a class-configuration wipe that removes only class-owned insurance lineage rows;
- deletion scheduling SHALL be derived from the end boundary of the last currently enforced entitlement;
- student-facing policy changes SHALL be surfaced as persistent banners until dismissed.

It returns persisted settings only. FEAT or the owning operational domain interprets them.

## VI. Owned Tables

### 1. `class_features`

Feature enablement by class. One row per enabled feature per class. Absence of a
row means the feature is disabled.

### 2. `feature_settings`

Economy policy mode and rebalance tracking for a class.

### 3. `hall_pass_settings`

Hall-pass queue, timing, and per-type configuration values for a class.

### 4. `rent_settings`

Rent policy configuration: amount, frequency, grace period, late penalty, and billing
rules for a class.

### 5. `payroll_settings`

Payroll rate, schedule, overtime, and automation configuration for a class.

### 6. `payroll_rewards`

Teacher-defined reward presets for payroll bonus events.

### 7. `payroll_fines`

Teacher-defined fine presets for payroll deduction events.

### 8. `banking_settings`

Savings interest, overdraft protection, and transfer behavior configuration for a class.

### 9. `policy_versions`

Immutable economic policy lineage records for a class.

Represents constitutional economic policy truth and historical policy replay state.

### 10. `policy_transitions`

Append-only economic policy transition lineage for a class.

Represents future economic law, activation intent, supersession lineage, and transition state.

## VII. Schema Contract

### 1. `class_features`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE)
- `feature_name` — `payroll` | `insurance` | `banking` | `rent` | `hall_pass` | `store`
- `created_at`

Rules:

- Unique constraint on `(class_id, feature_name)`.
- Feature existence means enabled. Absence means disabled.
- `feature_name` is a closed enumeration; open-ended strings are not permitted.
- This table does not store configuration values — only enablement.

### 2. `feature_settings`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE, UNIQUE; one record per class)
- `join_code` — denormalized human-facing alias; resolves to `class_id`
- `economy_policy_mode`
- `economy_policy_updated_at`
- `economy_last_rebalanced_at`
- `economy_last_rebalanced_by` — `user_id` of the actor who triggered the rebalance
- `economy_pending_rebalance_json` — **DEPRECATED. Scheduled for removal at Wave 4.** Transitional compatibility field only.

Rules:

- One record per class. Created when the class is first configured.
- `economy_policy_mode` controls how economy governance interprets rebalance and solvency semantics.
- `economy_pending_rebalance_json` exists only for transitional compatibility and MUST NOT be used by constitutional policy-governance systems. Any callsite that reads or writes this field outside a Wave 3 compatibility shim is a constitutional violation. This field MUST be removed and all callsites migrated to `policy_versions` / `policy_transitions` no later than Wave 4 of the v2 migration plan.
- Active economic policy truth is governed through `policy_versions` and `policy_transitions`.
- `feature_settings` stores active operational policy projection state only.
- `activate_due_rebalances()` or any equivalent function that mutates `economy_pending_rebalance_json` inside a GET handler or outside FEAT orchestration is a live violation of `INV-ARC-007` and `DOM-ECON-003`. This path is retired by the policy transition system and MUST NOT be called in new code.

### 3. `hall_pass_settings`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE, UNIQUE; one record per class)
- `join_code` — denormalized human-facing alias; resolves to `class_id`
- `queue_enabled` — boolean
- `queue_limit` — max concurrent passes across all types
- `pass_types` — JSON; list of pass-type configurations, each with:
  - `name`
  - `queue_limit`
  - `simultaneous_limit`
  - `enabled`
- `created_at` / `updated_at`

Rules:

- One record per class.
- `pass_types` defaults to the system-defined set of five types when absent.
- This table stores configuration only. Execution history lives in Attendance.

### 4. `rent_settings`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE, UNIQUE; one record per class)
- `join_code` — denormalized human-facing alias; resolves to `class_id`
- `is_enabled`
- `rent_amount` — Numeric
- `frequency_type` — `daily` | `weekly` | `monthly` | `custom`
- `custom_frequency_value` / `custom_frequency_unit`
- `first_rent_due_date`
- `due_day_of_month`
- `grace_period_days`
- `late_penalty_amount`
- `late_penalty_type` — `once` | `recurring`
- `late_penalty_frequency_days`
- `bill_preview_enabled` / `bill_preview_days`
- `allow_incremental_payment`
- `prevent_purchase_when_late`
- `bypass_cwi_warnings`
- `updated_at`

Rules:

- One record per class.
- This table defines rent policy only. Rent payment history lives in Obligations.

### 5. `payroll_settings`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE, UNIQUE; one record per class)
- `join_code` — denormalized human-facing alias; resolves to `class_id`
- `pay_rate` — Numeric; dollars per minute of tap time
- `payroll_frequency_days`
- `daily_limit_hours` — simple-mode auto tap-out threshold
- `time_unit` / `overtime_enabled` / `overtime_threshold`
- `max_time_per_day` / `max_time_per_unit`
- `pay_schedule_type` / `rounding_mode`
- `next_payroll_date`
- `is_active`
- `expected_weekly_hours` — used for economy balance validation only
- `created_at` / `updated_at`

Rules:

- One record per class.
- Payroll execution logic lives in FEAT; this table stores the configuration inputs.

### 6. `payroll_rewards`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE)
- `join_code` — denormalized human-facing alias; resolves to `class_id`
- `name`
- `description`
- `amount` — positive Numeric; bonus amount per occurrence
- `is_active`

Rules:

- Rewards are class-scoped policy definitions. They define what a teacher can offer
  as a payroll bonus; they do not themselves create ledger entries.
- FEAT orchestrates the ledger credit when a reward is applied to a seat.
- `is_active = false` rewards may not be selected for new payroll events but must
  be retained for display on historical payroll records.

### 7. `payroll_fines`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE)
- `join_code` — denormalized human-facing alias; resolves to `class_id`
- `name`
- `description`
- `amount` — positive Numeric; stored as a magnitude; ledger deduction semantics
  are applied by FEAT
- `is_active`

Rules:

- Fines are class-scoped policy definitions. They define what a teacher can apply
  as a payroll deduction; they do not themselves create ledger entries.
- FEAT orchestrates the ledger debit when a fine is applied to a seat.
- `is_active = false` fines may not be selected for new payroll events but must
  be retained for historical display.

### 8. `banking_settings`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE, UNIQUE; one record per class)
- `join_code` — denormalized human-facing alias; resolves to `class_id`
- `savings_apy` / `savings_monthly_rate`
- `interest_calculation_type` — `simple` | `compound`
- `compound_frequency`
- `interest_schedule_type` — `weekly` | `monthly`
- `interest_schedule_cycle_days`
- `interest_payout_start_date`
- `overdraft_protection_enabled`
- `overdraft_fee_enabled`
- `overdraft_fee_type` — `flat` | `progressive`
- `overdraft_fee_flat_amount`
- `overdraft_fee_progressive_1` / `_2` / `_3` / `_cap`
- `is_active`
- `created_at` / `updated_at`

Rules:

- One record per class.
- Interest computation and monetary resolution live in FEAT/Ledger;
  `FEAT-LED-000` resolves intended ledger plans and `FEAT-LED-001` posts the
  resolved plan. This table provides the configuration inputs only.

### 9. `policy_versions`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE)
- `domain`
- `version_number`
- `policy_payload_json`
- `created_at`
- `activated_at`
- `created_by_transition_id`
- `is_active`

Rules:

- Represents immutable constitutional economic policy truth.
- Historical policy versions MUST remain immutable.
- Exactly one active version per `(class_id, domain)` is permitted.
- This table defines constitutional economic policy lineage.
- Operational execution domains consume active policy state but do not own policy lineage.

### 10. `policy_transitions`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE)
- `domain`
- `source_policy_version_id`
- `target_policy_version_id`
- `activation_mode`
- `status`
- `created_at`
- `created_by`
- `applied_at`
- `correlation_id`
- `superseded_by_transition_id`
- `cancelled_at`

Rules:

- Represents append-only economic policy evolution lineage.
- Pending transitions represent publicly visible future economic law.
- Policy transitions MUST remain replayable and auditable.
- Historical transitions MUST NOT be deleted.
- Operational domains determine lawful activation boundaries but MUST NOT directly mutate transition lineage.

## VIII. Constraints

- This domain stores constitutional policy objects and active operational configuration projection state; it does not compute operational outcomes.
- It does not mutate ledger, attendance, obligations, store, or identity tables.
- All settings tables are scoped by `class_id` (from `classes`) as the canonical
  isolation boundary per `INV-CORE-000`. `join_code` is carried as a denormalized
  human-facing alias for routing convenience.
- No settings table uses `teacher_id` as a scoping key. The class (`class_id`) is
  the scope boundary, not the teacher.
- Missing row vs existing row semantics are part of persisted configuration truth
  and must remain explicit.
- Economic policy evolution MUST occur through append-only `policy_transitions` lineage.
- Direct mutation of constitutional economic policy history is prohibited.
- Operational domains MAY consume active projected policy state but MUST NOT own policy lineage.

### Deprecated Transitional Fields

The following fields in `feature_settings` are retired by the policy transition system and are subject to removal at the specified migration wave:

| Field | Status | Removal Gate | Successor |
|---|---|---|---|
| `economy_pending_rebalance_json` | **DEPRECATED** | Wave 4 | `policy_versions` + `policy_transitions` |

**`activate_due_rebalances()` and equivalent GET-path activation functions are retired.** These functions mutate `economy_pending_rebalance_json` outside FEAT orchestration, constituting a live violation of `INV-ARC-007` (no write-on-read) and `DOM-ECON-003` (append-only evolution). No new code may call these functions. Existing callsites MUST be migrated to the policy transition system no later than Wave 4.

`economy_policy_mode` in `feature_settings` is a transitional operational projection field. It reflects the active policy mode derived from `policy_versions` and has no independent authority. Its continued presence after Wave 4 migration is subject to review.

## IX. Derived / Cross-Domain Rules

- Attendance reads hall-pass limits from `hall_pass_settings` but owns the execution
  history in `hall_pass_logs`.
- Payroll FEAT reads `payroll_settings`, `payroll_rewards`, and `payroll_fines` but
  does not own those rows.
- Ledger reads `banking_settings` for interest and overdraft policy but does not own
  that configuration.
- Economic governance consumes `policy_versions` and `policy_transitions` as constitutional policy lineage.
- Operational domains consume active projected configuration state from settings tables.
- FEAT orchestrates lawful activation and projection updates but does not own policy truth.
- Class identity (`classes.class_id`, `classes.join_code`) is owned by Identity.
  This domain reads `class_id` as a FK but does not own the class record.

### 12. Insurance policy lifecycle note

Insurance policy creation, edit, inactivation, switching, bundle eligibility, and deletion scheduling are class-configuration behaviors. A policy edit SHALL create a new prospective version when the terms change. A deletion request SHALL only schedule removal of the class-owned insurance lineage rows after the last enforced entitlement boundary for the class has elapsed. Entitlement, obligation, and Ledger tables SHALL remain unchanged by the configuration delete operation. Student-facing notices for insurance changes SHALL be persistent banners until dismissed.

## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
