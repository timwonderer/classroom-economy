# FEAT-ECON-001: Economy Policy Mode and Rebalancer

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| FEAT-ECON-001 | 1.1 | 2026-03-30 | 1.0 | Normative |

## I. Purpose

This document defines the normative user-facing feature contract for teacher economy policy mode selection, alignment review, and rebalance activation.

## II. Scope

This feature applies to teacher-scoped economy configuration in Economy Health, including policy mode selection, alignment status, rebalance preview, immediate activation, and scheduled activation on due renewal events.

## III. Authority Level

Normative (FEAT Tier). This document is subordinate to `DOM-ECON-001_Economy_Balance_Checker.md` and `DOM-ECON-002_Economy_Specification.md`.

## IV. Dependencies

- `DOM-ECON-001_Economy_Balance_Checker.md`
- `DOM-ECON-002_Economy_Specification.md`
- `FEAT-CORE-000_Feature_Foundation.md`

## V. Canonical Data Model

Primary storage shall remain teacher-scoped `feature_settings` rows.

Required fields:

- `economy_policy_mode`
- `economy_policy_updated_at`
- `economy_policy_alignment_status`
- `economy_last_rebalanced_at`
- `economy_last_rebalanced_by`
- `economy_pending_rebalance_json`

Scope rules:

- `block != NULL` shall represent block-specific policy state.
- `block = NULL` shall represent teacher-global fallback state.

## VI. Lifecycle State Machine

### 1. Policy Mode State

Allowed policy values:

- `tight`
- `default`
- `comfortable`

Invalid values shall be rejected.

### 2. Rebalance Activation State

A classroom economy rebalance shall be in exactly one of the following states:

1. no pending rebalance
2. preview generated but not scheduled
3. scheduled for next renewal
4. applied immediately
5. applied when due on renewal/payroll evaluation

Forbidden transitions:

- Scheduled rebalance shall not bypass teacher selection.
- Applied rebalance shall not rewrite historical transactions.
- Policy change shall not implicitly auto-apply configuration edits.

## VII. Primary User Flow

### 1. Policy Update

1. Teacher opens Economy Health.
2. Teacher selects `tight`, `default`, or `comfortable`.
3. System persists the selected mode.
4. System evaluates alignment through the Economy Balance Checker.
5. System offers a rebalance review when supported settings are misaligned.

### 2. Rebalance Preview

1. Teacher opens the rebalance preview.
2. System displays before/after values for supported settings.
3. Teacher selects which changes to apply.
4. Teacher selects activation timing.

### 3. Activation

Teacher may choose one of the following:

- apply immediately
- schedule for next renewal (rent cycle rollover and/or insurance renewal)

## VIII. Behavior Rules

### 1. Supported Rebalance Categories

The initial implementation shall support rebalance previews and updates for:

- rent amount
- insurance premiums

### 2. Recommendation Source of Truth

All recommendation math for rebalance preview, insurance premium guidance, rent guidance, store guidance, and API recommendation payloads shall originate from `app/utils/economy_policy.py`.

`EconomyBalanceChecker` may expose recommendation payloads, but it shall do so by delegating to the shared economy-policy helper rather than recomputing ratios locally.

Routes and templates shall not contain independent pricing formulas. Templates may render backend-provided recommendation values only.

### 3. Activation Timing

If the teacher selects scheduled activation, the rebalance payload shall be stored and activated when change-level due conditions are met:

- rent changes activate at the next valid rent renewal boundary
- insurance changes activate when the selected policy renews
- legacy `next_payroll` payloads remain supported and are treated as renewal-scheduled for compatibility

### 4. Safety Rules

The feature shall not:

- mutate historical transactions
- mutate posted payroll records
- mutate frozen insurance enrollment snapshots
- cross class or cross teacher boundaries

## IX. API Surface

### 1. Policy Mode Update

`POST /admin/economy-policy`

Required form values:

- `policy_mode`
- `block` (optional, block-scoped if provided)

### 2. Rebalance Apply

`POST /admin/economy-policy/rebalance`

Required form values:

- `selected_changes`
- `activation_mode`
- `block` (optional)

Optional confirmation value:

- `confirm_immediate`

### 3. Shared Validation Surface

The feature shall continue to rely on the shared economy validation API:

- `POST /admin/api/economy/analyze`
- `POST /admin/api/economy/validate/<feature>`

## X. Observability and Audit

At minimum, the system shall log:

- policy mode changes
- immediate rebalance applications
- scheduled rebalance creation
- due rebalance activation events (including payroll-triggered evaluation)

Timestamps shall remain UTC at rest.

## XI. Security and Privacy Requirements

1. Only authenticated teacher users shall be allowed to change policy mode or apply rebalance actions.
2. Rebalance changes shall remain teacher-scoped and block-aware.
3. Student-facing UI shall not expose internal ratio formulas.
4. No action in this feature shall bypass join-code or teacher ownership constraints.

## XII. Acceptance Criteria

1. Economy Health shall display the active policy mode and alignment status.
2. Teachers shall be able to change policy mode without immediate config mutation.
3. Teachers shall be able to review and selectively apply supported rebalance changes.
4. Scheduled activation shall apply pending changes at their due renewal trigger, including payroll-time checks.
5. Rent, store, and insurance settings shall continue to surface CWI-based recommendations.
6. Insurance settings shall validate premium, max claim, period cap, and waiting period.

## XIII. Amendment

Revisions to this document shall:

1. increment the version number
2. update the Effective Date
3. maintain consistency with the governing DOM documents
4. preserve compatibility with `FEAT-CORE-000_Feature_Foundation.md`
