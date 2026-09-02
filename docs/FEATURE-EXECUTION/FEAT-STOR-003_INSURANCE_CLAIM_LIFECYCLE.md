# FEAT-STOR-003: Insurance Claim Lifecycle

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-STOR-003 | 1.2 | 2026-09-01 | 1.1 | Normative |

> **1.2 revision note.** Claim-time authority is the **immutable `insurance_policies`
> definition**, resolved via the GRANTED entitlement's `policy_uuid`, not a
> `frozen_contract` payload snapshot. Because a policy edit mints a *new*
> `policy_uuid`, the exact row the entitlement references cannot change after
> purchase — it *is* the frozen contract, with the same non-retroactivity guarantee
> and no duplicated terms in the entitlement payload (INV-ARC-009, DOM-STORE-001
> §VII.A). Throughout this document, "frozen contract" / "frozen purchased contract"
> denotes that immutable policy row; the claim FEAT reads its terms
> (`policy.premium`, `policy.reimbursement_percentage`, etc.) directly.
>
> **1.1 revision note.** TRANSACTION insurance economics are now *resolved*, not
> deferred. This revision replaces the earlier "to be defined by policy" language
> around claim allowance with the implemented **two-resource rule** (§X, §XII).

## I. Purpose

Define the lawful lifecycle for insurance claims made under active insurance entitlements.

Insurance is a conditional entitlement. Purchasing insurance grants the covered seat the right to submit qualifying claims during the active coverage cycle. It does not guarantee that any individual claim will be approved.

This FEAT coordinates:

- claim submission;
- claim validation;
- teacher approval or rejection;
- transaction-insurance compensation;
- productivity-insurance compensation;
- non-monetary claim completion.

Claim activity does not consume the insurance entitlement.

This FEAT does not create or satisfy debt. If an insurance product requires premium assessment or renewal settlement, that work belongs to Obligations and Ledger through the canonical debt lifecycle.

## II. Authority

Store and Entitlements owns:

- existence of the insurance claim;
- claim status;
- claim basis stored by the claim contract;
- teacher claim decision;
- claim lifecycle correlation.

Class Configuration owns:

- insurance definition;
- insurance type;
- coverage period;
- eligibility rules;
- claim allowance;
- reimbursement percentage or benefit rules;
- future cancellation of the offering.

Ledger owns monetary transaction truth.

Productivity and Payroll owns productivity facts, payroll events, and `MANUAL_CREDIT` payroll classification.

## III. Required Context

### Student submission

Required canonical context:

- `user_id`
- `class_id`
- `seat_id`
- `actor_role = student`

The submitting seat SHALL be the target seat covered by the referenced insurance entitlement unless another explicitly documented workflow permits teacher-assisted submission.

The FEAT SHALL NOT assume that claim submission itself creates an obligation event.

### Teacher decision

Required canonical context:

- `user_id`
- `class_id`
- `seat_id`
- `actor_role = teacher`

The teacher seat SHALL be lawful for the claim's class boundary.

## IV. Insurance Entitlement Preconditions

Before submission, the FEAT SHALL establish:

1. the referenced `entitlement_id` exists;
2. the entitlement belongs to the target seat and class;
3. the entitlement references a configured insurance capability;
4. the coverage cycle is currently active under canonical temporal resolution;
5. no terminal `EXPIRED` event or other authoritative termination exists;
6. configured claim allowance remains available.

Teacher cancellation of the insurance offering SHALL NOT invalidate an already-active entitlement.

An active entitlement remains eligible for claim submission until its configured coverage boundary.

## V. Claim Submission

Submission invokes:

- `submit_insurance_claim(...)`

and creates:

- `status = SUBMITTED`.

Submission SHALL NOT:

- create `CONSUMED`;
- create `EXPIRED`;
- alter the insurance entitlement;
- move money;
- create payroll;
- create or satisfy an obligation.

The claim SHALL reference the insurance `entitlement_id`.

### A. Transaction insurance

A transaction-based claim SHALL reference exactly one canonical Ledger `transaction_id`.

The FEAT SHALL validate that the transaction:

- belongs to the covered seat and class;
- falls within the configured claim window;
- is of a type eligible under the configured insurance definition;
- has not already been claimed in a manner prohibited by the policy;
- otherwise satisfies mechanical eligibility rules.

One transaction-based claim covers exactly one transaction.

The eligible-transaction predicate is **system law**, not Class Configuration.
CTH owns a global, non-configurable disallowed set (premiums, reimbursements,
penalty fees, income/reward credits, transfers, obligation charges, and
collective-goal charges are never an insurable loss); a teacher can neither widen
nor narrow it. If the source transaction is **item-related**, the associated
entitlement must have been purchased **and used** (a `CONSUMED` event exists) and
must **not** be `REVOKED` or `EXPIRED` — an item that never delivered lasting
value, or was clawed back, is not an insurable loss.

The **filing window** is evaluated in class-local calendar dates: a transaction on
class-local date `D` under a frozen `claim_window_days = N` may be filed through
the end of class-local date `D + N`.

### B. Productivity insurance

A productivity-based claim is a **multi-date evidentiary form**. It SHALL identify
one or more canonical class-local dates permitted by the configured policy. Each
claimed date entry SHALL carry:

- `date` — a canonical class-local calendar date;
- `hours` — the student-asserted claimed hours for that date;
- `explanation` — a **required**, non-empty, student-authored account of the loss
  for that date. This is student-submitted evidence; it is never derived,
  fabricated, or backfilled. A missing or blank explanation fails submission with
  `INVALID_CLAIM_BASIS`.

The claim MAY additionally carry one claim-wide OPTIONAL `additional_information`
string. It is persisted on `InsuranceClaim.claim_basis` (JSON) — there is no
parent column — and surfaced to the teacher at review. If present it SHALL be a
string, else submission fails with `INVALID_CLAIM_BASIS`.

The FEAT SHALL use authoritative Productivity and Payroll reads to determine whether the dates are mechanically eligible.

The FEAT SHALL NOT rewrite:

- attendance;
- productivity sessions;
- worked minutes;
- historical payroll.

#### Weekly-hours guidance is ADVISORY only (never a submission gate)

`expected_weekly_hours` is economic normalization plus guidance — it is **not** an
authorization limit and SHALL NOT reject a claim. For each canonical
(Monday-anchored) week the submission touches, the FEAT derives the aggregate
`actual_worked_week + claimed_week` and compares it with `expected_weekly_hours`,
where:

- `actual_worked_week` sums authoritative worked attendance across the seven
  class-local days of the week;
- `claimed_week` sums the existing persisted claimed/approved contribution for the
  week (per lifecycle status) plus the newly-added dates in this submission.

When the aggregate exceeds `expected_weekly_hours` the FEAT surfaces a non-blocking
warning to the student at submission and to the teacher at review. This guidance is
**derived, non-authoritative state**. It is carried in the submission result's
`eligibility_flags` (keys: `expected_weekly_hours`, `weekly_guidance_exceeded`,
`weekly_guidance_warnings`) and MUST NOT be persisted as eligibility truth. The
daily-hours limit remains a hard boundary; only the weekly-hours check is advisory.

### C. Non-monetary insurance

A non-monetary claim records use of a teacher-defined external insurance benefit.

CTH may validate configured allowance and timing rules.

CTH does not own or verify the external benefit itself.

## VI. Teacher Decision

Every submitted insurance claim requires teacher decision.

A claim may transition only:

- `SUBMITTED -> APPROVED`
- `SUBMITTED -> REJECTED`

A decided claim SHALL NOT return to `SUBMITTED`.

The teacher retains decision authority even when the claim satisfies mechanical eligibility rules.

Mechanical eligibility establishes that the claim may be considered; it does not force approval.

## VII. Approval: Transaction Insurance

Upon approval of a `TRANSACTION` claim:

1. revalidate the claim and referenced Ledger transaction;
2. resolve the reimbursement rule from the **frozen purchased contract** (the
   snapshot captured at purchase time), which is the sole claim-time authority —
   a later edit to the insurance definition SHALL NOT retroactively change the
   terms of an already-purchased entitlement;
3. calculate the gross compensatory amount as `reimbursement_percentage × loss`;
4. **clamp** the credit to the remaining period payout capacity — the frozen
   `premium × payout_multiple` minus the Σ of prior `APPROVED` payouts under this
   coverage period; a claim that mechanically qualifies but would exceed remaining
   capacity is paid only its remaining capacity, and zero remaining capacity fails
   the approval;
5. coordinate the compensatory Ledger credit through the lawful Ledger FEAT;
6. record the claim as `APPROVED`;
7. commit the claim decision and required monetary effect within the lawful coordinated transaction.

The compensatory Ledger event SHALL preserve lineage to:

- the original spending transaction; and
- the insurance claim lifecycle.

No Payroll event is created.

Ledger remains the sole authority over the compensatory monetary transaction.

## VIII. Approval: Productivity Insurance

Upon approval of a `PRODUCTIVITY` claim:

1. revalidate the claimed dates against authoritative Productivity and Payroll facts;
2. resolve the configured compensation rule;
3. calculate the compensation basis from lawful payroll/productivity facts;
4. coordinate the approved claim to the Productivity and Payroll domain;
5. Productivity and Payroll creates a `payroll_event` with:
   - `payroll_type = MANUAL_CREDIT`;
6. the Productivity and Payroll FEAT posts the resulting monetary effect to Ledger;
7. record the insurance claim as `APPROVED`;
8. commit the coordinated lifecycle according to the governing cross-domain transaction contract.

The `MANUAL_CREDIT` does not assert that the student worked.

The original productivity history remains unchanged.

Store and Entitlements SHALL NOT directly create the payroll event or bypass the Productivity and Payroll FEAT.

## IX. Approval: Non-Monetary Insurance

Upon approval of a `NON_MONETARY` claim:

1. revalidate configured claim allowance and timing;
2. record the claim as `APPROVED`;
3. end the CTH claim workflow.

No Ledger or Payroll event is required.

The teacher-defined external fulfillment is outside CTH authority.

## X. Rejection

Upon rejection:

1. require a lawful teacher actor;
2. transition:
   - `SUBMITTED -> REJECTED`;
3. record the decision timestamp and deciding teacher seat;
4. create no Ledger or Payroll effect.

Rejection does not revoke, consume, or expire the insurance entitlement.

Rejected claims **do** consume the period **claim-count allowance** (see §XII, the
two-resource rule): every submitted claim lifecycle — `SUBMITTED`, `APPROVED`, or
`REJECTED` — draws one slot against the period allowance. A rejected claim creates
no `CONSUMED` event and no monetary effect, so it does **not** consume period
**payout capacity**. Both quantities are derived from canonical claim history; the
claim table SHALL NOT maintain a mutable remaining-count field.

## XI. Coverage Cancellation and Expiration

Cancellation of an insurance offering is prospective.

After cancellation:

- no new coverage cycle may be purchased or renewed as permitted by Class Configuration;
- existing paid coverage remains active through its established boundary;
- covered students may continue submitting claims while coverage remains active;
- teachers may continue approving or rejecting those claims.

When the coverage boundary is reached:

- `FEAT-STOR-002` records `EXPIRED` for the insurance entitlement.

Insurance claim activity never creates the terminal entitlement event.

## XII. The Two-Resource Rule (Claim Allowance and Payout Capacity)

A monetary insurance entitlement meters two **independent** resources over each
coverage period. Both are computed from the **frozen purchased contract** and
canonical claim history — never from live policy edits or a mutable counter.

**Resource 1 — period claim-count allowance.** The maximum number of claim
lifecycles that may be *filed* in the period:

```
period_claim_allowance = ceil(frozen.claims_per_week_equivalent × week_equivalent)
```

where `week_equivalent` scales the weekly figure to the coverage period's length
(a weekly cycle is `1`; a monthly cycle is `covered_days / 7`, measured in
class-local calendar days). **Every** submitted claim lifecycle draws exactly one
slot — `SUBMITTED`, `APPROVED`, and `REJECTED` alike. Filing a claim and having it
rejected still spends an allowance slot; the allowance meters *access to
adjudication*, not payouts. A same-`correlation_id` replay is the same lifecycle,
not an additional draw.

**Resource 2 — period payout capacity.** The maximum monetary value the policy
will disburse in the period:

```
maximum_policy_payout = frozen.premium × frozen.payout_multiple
remaining_capacity     = maximum_policy_payout − Σ(APPROVED result_amounts this period)
```

Only **`APPROVED`** monetary payouts consume capacity. `SUBMITTED` and `REJECTED`
claims consume none. An approval is clamped to `remaining_capacity`; a claim that
mechanically qualifies but exceeds remaining capacity is paid only what remains,
and zero remaining capacity fails the approval (`CLAIM_ALLOWANCE_EXHAUSTED`).

**Why two resources.** The allowance bounds how many times a student may invoke
teacher adjudication; the payout capacity bounds how much money the policy is
worth. Decoupling them means a flurry of rejected (or clamped-to-zero) claims
cannot be used to launder additional payout headroom, and a student cannot exhaust
their payout value without also having spent adjudication slots.

The system SHALL NOT persist `claims_remaining`, a mutable claim balance, or a
mutable insurance-use counter. Both resources are always re-derived from immutable
claim history under a row-level lock on the `GRANTED` entitlement event so
concurrent submissions cannot both take the last slot.

## XIII. Idempotency

Submission and decision operations SHALL be idempotent.

Retrying a successful submission SHALL NOT create a duplicate claim.

Retrying a successful approval SHALL NOT:

- create another compensatory Ledger credit;
- create another Payroll `MANUAL_CREDIT`;
- change the decided claim again.

Retrying a successful rejection SHALL return the existing decided outcome without additional effects.

## XIV. Correlation and Lineage

Each claim SHALL have a claim lifecycle `correlation_id`.

Coordinated downstream effects SHALL preserve enough lineage to identify:

- the insurance claim that caused the effect;
- the insured transaction for transaction insurance, where applicable;
- the resulting Payroll event for productivity insurance, where applicable;
- the resulting Ledger transaction(s).

Correlation SHALL NOT collapse distinct domain identifiers into one ambiguous identifier.

## XV. Atomicity

For approval paths requiring downstream mutation, the claim decision SHALL NOT become successfully `APPROVED` while its required economic effect fails.

Transaction insurance requires coordinated success of:

- claim approval;
- compensatory Ledger credit.

Productivity insurance requires coordinated success of:

- claim approval;
- Payroll `MANUAL_CREDIT`;
- required Productivity/Payroll-to-Ledger posting.

Non-monetary insurance requires only the lawful claim decision inside CTH.

## XVI. Failure Contract

Representative failures include:

- `CLAIM_NOT_FOUND`
- `INSURANCE_ENTITLEMENT_NOT_FOUND`
- `COVERAGE_NOT_ACTIVE`
- `COVERAGE_EXPIRED`
- `CLAIM_ALLOWANCE_EXHAUSTED`
- `INVALID_CLAIM_BASIS`
- `TRANSACTION_NOT_ELIGIBLE`
- `PRODUCTIVITY_DATE_NOT_ELIGIBLE`
- `CLAIM_ALREADY_DECIDED`
- `TEACHER_AUTHORITY_REQUIRED`
- `LEDGER_COMPENSATION_FAILED`
- `PAYROLL_COMPENSATION_FAILED`
- `IDEMPOTENCY_CONFLICT`
- `CROSS_DOMAIN_FAILURE`

## XVII. Prohibited Patterns

The following are prohibited:

- writing `CONSUMED` because an insurance claim was filed;
- writing `CONSUMED` because an insurance claim was approved;
- revoking insurance because the teacher cancelled future coverage;
- refunding lawfully purchased insurance after purchase;
- treating mechanical eligibility as mandatory approval;
- directly writing Ledger compensation outside the lawful Ledger FEAT;
- directly creating Payroll events from Store and Entitlements;
- classifying productivity-insurance compensation as ordinary worked payroll;
- mutating historical productivity to justify compensation;
- storing mutable `claims_remaining`;
- allowing a decided claim to return to `SUBMITTED`;
- modelling the claim lifecycle on `PendingAction` (or any generic action queue)
  instead of the dedicated `InsuranceClaim` record, which is the sole owner of
  claim existence, status, basis, decision, and correlation.

## XVIII. Postconditions

### Submitted

On successful submission:

- exactly one `SUBMITTED` claim exists;
- the insurance entitlement remains active and unterminated;
- no monetary or payroll effect has occurred.

### Approved transaction claim

- claim is `APPROVED`;
- exactly one lawful compensatory Ledger effect exists for that approval;
- the insurance entitlement remains active until its coverage boundary.

### Approved productivity claim

- claim is `APPROVED`;
- exactly one lawful Payroll `MANUAL_CREDIT` lifecycle exists;
- the resulting monetary effect is posted through Productivity and Payroll authority;
- historical productivity remains unchanged;
- the insurance entitlement remains active until its coverage boundary.

### Approved non-monetary claim

- claim is `APPROVED`;
- no monetary or payroll effect is required;
- external fulfillment remains outside CTH authority.

### Rejected claim

- claim is `REJECTED`;
- no compensation is created;
- the insurance entitlement remains active until its coverage boundary.

## XIX. Amendment

Revisions must remain consistent with `DOM-STORE-001`, `FEAT-STOR-001`, `FEAT-STOR-002`, Class Configuration authority, Ledger authority, Productivity and Payroll authority, and the governing FEAT, temporal, and cross-domain coordination invariants.
