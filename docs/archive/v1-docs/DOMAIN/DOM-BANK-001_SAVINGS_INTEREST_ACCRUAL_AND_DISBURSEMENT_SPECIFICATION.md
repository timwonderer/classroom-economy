# DOM-BANK-001: Savings Interest Accrual and Disbursement Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-BANK-001 | 1.0 | 2026-05-21 | Draft | Constitutional |

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000`, `INV-CORE-001`, and `INV-ARC-015`.

**Banking domain is the sole authority over accrual rollover legality.** When a lawful accrual boundary occurs (e.g., end of a daily or monthly accrual window in class timezone), Banking determines whether the boundary is valid and may request policy transition activation from `FEAT-ECON-001`. Banking MUST NOT mutate `policy_versions` or `policy_transitions` directly. Those tables are owned by `DOM-CLASS-001` and governed by `DOM-ECON-003`.

## IV. Dependencies

- `INV-CORE-000` — Core Invariants
- `INV-CORE-001` — Capability-Based Architecture and Authority Model
- `INV-ARC-000` — Execution Model
- `INV-ARC-015` — Temporal Model and Boundary Enforcement
- `DOM-LED-001` — Ledger Domain Authority
- `FEAT-CORE-000` — Feature Execution Constitutional Directive
- `DOM-ECON-003` — Economic Policy and Transition (operational boundary activation protocol)

---

## 1. Purpose

This specification defines the authoritative behavior for savings interest accrual, compounding, scheduling, and payout within Classroom Token Hub (CTH).

The banking domain SHALL model interest as a deterministic, replayable financial process governed by canonical time boundaries and lawful ledger execution.

This specification distinguishes between:

1. Interest accrual
2. Compound participation
3. Interest payout/crediting
4. Savings eligibility
5. Settlement scheduling

These concepts are independent and MUST NOT be conflated into a single implicit operation.

---

## 2. Design Principles

### 2.1 Ledger Authority

The ledger is the sole authoritative financial source of truth.

Interest payouts MUST materialize as lawful ledger transactions through the Ledger Domain.

No derived balances, cached balances, projections, or UI-computed values SHALL possess financial authority.

---

### 2.2 Emergent Compounding

Compounding SHALL emerge from lawful balance participation rules rather than mutable “principal” state.

The system SHALL NOT maintain a mutable “principal” field for savings accounts.

Instead, future accrual eligibility SHALL derive from authoritative eligible balance computation.

---

### 2.3 Temporal Determinism

Interest accrual and payout SHALL operate against canonical class-time boundaries as defined by INV-ARC-015.

All scheduling decisions MUST resolve using:

- class_id
- authoritative class timezone
- canonical settlement windows

UTC calendar shortcuts are prohibited.

---

### 2.4 Separation of Concepts

The following concepts are independent:

| Concept | Purpose |
|---|---|
| Accrual Frequency | How often interest is earned |
| Compound Frequency | How often accrued interest joins future earning base |
| Payout Frequency | How often interest becomes posted ledger balance |
| Eligibility Rules | Which balances qualify |
| Settlement Schedule | When execution occurs |

Implementations MUST preserve these separations.

---

## 3. Definitions

### 3.1 Eligible Savings Balance

The balance eligible to earn interest during an accrual period.

Eligible balance SHALL derive from authoritative posted ledger state.

Eligible balance MUST account for:

- deposits
- withdrawals
- transfers
- reversals
- voids
- settlement timing

Historical deposit totals SHALL NOT independently confer future earning authority.

---

### 3.2 Accrued Interest

Interest earned but not yet paid out to the ledger.

Accrued interest MAY exist as:

- internal accounting state
- append-only accrual records
- derived deterministic calculations

Accrued interest SHALL NOT be treated as spendable balance until payout occurs.

---

### 3.3 Compound Participation

The rule governing whether accrued-but-unpaid interest contributes to future accrual calculations.

If accrued interest participates prior to payout:

- compounding frequency equals accrual frequency.

If accrued interest participates only after payout:

- compounding frequency equals payout capitalization frequency.

---

### 3.4 Interest Payout

A lawful ledger posting that credits accrued interest into the student’s savings balance.

Payout SHALL:

- occur through FEAT orchestration
- generate lawful audit lineage
- create authoritative ledger entries
- obey idempotency guarantees

---

## 4. Supported Interest Models

---

### 4.1 Simple Interest

Simple interest SHALL compute accrual solely from eligible principal balance.

Previously accrued or previously paid interest SHALL NOT participate in future accrual calculations.

Formula:

Where:

- P = eligible principal balance
- r = rate
- t = accrual duration

---

### 4.2 Compound Interest

Compound interest SHALL permit previously accrued or credited interest to participate in future accrual calculations according to compound frequency rules.

Formula:

Where:

- n = compound frequency periods per year

---

## 5. Accrual Rules

### 5.1 Accrual Frequency

The system SHALL support:

- daily
- weekly
- monthly

accrual frequencies.

---

### 5.2 Daily Accrual Formula

Daily accrual SHALL compute as:

Equivalent formulas MAY exist for weekly/monthly accrual periods.

---

### 5.3 Precision

Internal accrual precision SHALL exceed displayed currency precision.

Implementations SHALL NOT discard sub-cent precision during accrual computation.

Rounding SHALL occur only at lawful payout boundaries unless explicitly configured otherwise.

---

## 6. Compound Frequency Rules

### 6.1 Supported Compound Frequencies

The system SHALL support:

- never (simple interest)
- daily
- weekly
- monthly

---

### 6.2 Compound Participation Boundary

Compound frequency determines when accrued interest joins future earning eligibility.

Example:

| Frequency | Behavior |
|---|---|
| Daily | Accrued interest participates next day |
| Weekly | Participation updates weekly |
| Monthly | Participation updates after monthly capitalization |
| Never | Accrued interest never participates |

---

## 7. Payout Rules

### 7.1 Payout Frequency

Payout frequency SHALL determine when accrued interest becomes:

- posted ledger balance
- visible student balance
- spendable funds

---

### 7.2 Supported Frequencies

The system SHALL support:

- daily
- weekly
- monthly

---

### 7.3 Payout Execution

Interest payout SHALL:

- execute through FEAT orchestration
- create lawful ledger transactions
- obey idempotency
- emit audit lineage
- respect class boundaries

Direct database writes are prohibited.

---

## 8. Scheduling

### 8.1 Canonical Settlement Execution

Settlement jobs SHALL execute through scheduled orchestration services.

Execution SHALL:

- iterate lawful class scope
- resolve canonical class time
- determine eligible payout windows
- execute deterministically

---

### 8.2 Idempotency

Each accrual and payout period SHALL possess deterministic idempotency boundaries.

Duplicate payout within the same settlement window is prohibited.

---

## 9. Eligibility Rules

### 9.1 Withdrawal Participation

Withdrawals MUST reduce future eligible balance.

The system SHALL NOT continue paying interest on historical deposits no longer represented in authoritative balance state.

---

### 9.2 Pending Funds

Implementations MUST explicitly define whether pending balances participate in accrual.

The default authoritative rule SHALL be:

- posted balances only.

---

### 9.3 Voided Transactions

Voided transactions SHALL NOT contribute to:

- accrual
- compounding
- payout eligibility

---

## 10. Projection and Forecasting

Projection displays SHALL use the same mathematical rules as authoritative execution.

UI forecasts SHALL NOT diverge from runtime execution semantics.

Hardcoded APY defaults in projections are prohibited.

---

## 11. Architectural Prohibitions

The following are prohibited:

- GET-triggered financial mutation
- mutable principal authority fields
- direct DB transaction insertion outside FEAT orchestration
- UTC calendar shortcuts for payout boundaries
- historical-deposit-only eligibility logic
- projection formulas inconsistent with runtime execution
- hidden default APY behavior

---

## 12. Auditability

Interest execution SHALL be replayable and explainable.

The system MUST support reconstruction of:

- accrual basis
- compounding state
- payout eligibility
- payout timing
- resulting ledger transactions

from authoritative records.

---

## 13. Recommended Default Model

The recommended canonical banking model for CTH is:

| Property | Recommended Setting |
|---|---|
| Accrual Frequency | Daily |
| Compound Frequency | Monthly |
| Payout Frequency | Monthly |
| Eligibility Basis | Posted balance |
| Precision | High internal precision |
| Settlement Boundary | Canonical class midnight |

This mirrors common real-world savings account behavior while preserving deterministic replayability.

---

## 14. Operational Boundary Authority

Banking domain is the sole authority over **accrual rollover legality** within CTH.

This authority is referenced by `DOM-ECON-003` (ECON-CONST-004) and `FEAT-ECON-001` (§VIII) as "Banking domain owns accrual rollover legality." Both phrases refer to this domain.

### 14.1 Boundary Determination

When the scheduled accrual settlement job fires, Banking SHALL:

1. Resolve the canonical class-time boundary using `class_id` and class timezone (per INV-ARC-015).
2. Determine whether the accrual window has closed since the last settled period.
3. Execute interest payout through `FEAT-CORE-000`-compliant FEAT orchestration.
4. If a pending banking policy transition exists and the accrual boundary is lawful, signal `FEAT-ECON-001` to activate the transition.

### 14.2 Policy Transition Activation Protocol

Banking MAY request policy transition activation at a lawful accrual boundary.

Banking MUST NOT:
- Directly mutate `policy_versions` or `policy_transitions`
- Activate policy transitions outside `FEAT-ECON-001` orchestration
- Determine supersession legality
- Perform activation inside a GET handler or read path

Policy lineage remains owned by `DOM-CLASS-001`. Activation is orchestrated by `FEAT-ECON-001`.

---

## 15. Amendment

Revisions to this document SHALL:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000` and `INV-ARC-015`.
4. Maintain consistency with `DOM-ECON-003` for operational boundary activation protocol.
5. Preserve deterministic, replayable accrual semantics.
