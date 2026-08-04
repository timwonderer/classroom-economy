# FEAT-STOR-003: Insurance Claim Lifecycle

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-STOR-003 | 2.0 | 2026-07-27 | 1.0 | Normative |

## I. Purpose

Define the lawful lifecycle for insurance claims made under active insurance entitlements.

This FEAT coordinates:

- pending claim submission;
- teacher adjudication;
- canonical insurance entitlement outcome;
- coordinated Ledger reimbursement where applicable;
- cross-domain compensation where applicable.

An insurance claim does not itself consume the entitlement when it is merely submitted.
It becomes a canonical entitlement event only when the responsible FEAT resolves the pending action.

## II. Authority

Store and Entitlements owns:

- pending insurance claim existence;
- insurance entitlement event history for the claim lifecycle;
- claim lifecycle correlation;
- canonical payload facts that identify the claim subject and resolution outcome.

Class Configuration / Policies owns:

- insurance product definition;
- coverage period;
- eligibility rules;
- claim allowance;
- reimbursement percentage or benefit rules;
- prospective cancellation of the offering.

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
6. configured claim allowance remains available or the policy allows the claim to be pending.

Teacher cancellation of the insurance offering SHALL NOT invalidate an already-active entitlement.

An active entitlement remains eligible for claim submission until its configured coverage boundary.

## V. Claim Submission

Submission invokes a lawful insurance-claim FEAT and creates:

- a corresponding `pending_actions` row;
- `authoritative_feat` pointing to the insurance claim resolution FEAT;
- a typed claim payload;
- the canonical `submitted_at` timestamp.

The pending action SHALL NOT:

- create `CONSUMED`;
- create `EXPIRED`;
- alter the insurance entitlement;
- move money;
- create payroll;
- create or satisfy an obligation.

### A. Claim subject

A claim submission SHALL reference the entitlement subject required by the insurance product:

- a canonical Ledger `transaction_id` for transaction insurance;
- one or more canonical class-local dates for productivity insurance;
- another closed subject type when the policy defines one.

The payload SHALL encode the canonical subject and any validation result that must be visible to the adjudicating teacher.

### B. Structural validation

The FEAT SHALL reject submissions that are structurally invalid:

- nonexistent entitlement;
- seat/class mismatch;
- malformed payload;
- missing required subject;
- impossible canonical reference.

Structural invalidity prevents the pending action from being created.

### C. Policy evaluation

Policy failures such as:

- claim window exceeded;
- claim count limit reached;
- per-claim value over limit;
- period value over limit;

SHALL be recorded as part of the pending action and presented to the teacher.

Policy ineligibility does not erase the fact that a claim was submitted when teacher adjudication is required.

## VI. Teacher Decision

Every submitted insurance claim requires teacher decision.

A claim may transition only through authoritative resolution of the pending action.

The teacher retains decision authority even when the claim satisfies mechanical eligibility rules.

Mechanical eligibility establishes that the claim may be considered; it does not force approval.

## VII. Resolution Semantics

Resolution of an insurance claim SHALL produce a canonical entitlement event with:

- `entitlement_type = INSURANCE`
- `acquisition_type = PERK`
- `event_type = CONSUMED`

The payload SHALL record the claim subject and outcome.

For example:

- attendance claim: claimed date and accepted/rejected outcome;
- transaction claim: claimed transaction and accepted/rejected outcome.

The payload MAY also record policy override metadata when a teacher chooses to approve a claim that the automatic validator flagged as ineligible.

The payload SHALL NOT duplicate Ledger payout amount or other truth owned by another domain.

### A. Accepted claim

Upon acceptance:

1. revalidate the claim and referenced authoritative facts;
2. resolve the configured reimbursement rule;
3. calculate the lawful compensatory amount;
4. coordinate the compensatory Ledger credit through the lawful Ledger FEAT;
5. write the canonical entitlement event;
6. commit the claim decision and required monetary effect within the lawful coordinated transaction;
7. delete the pending action.

The compensatory Ledger event SHALL preserve lineage to:

- the original claim subject;
- the insurance entitlement lifecycle;
- the claim lifecycle correlation.

### B. Rejected claim

Upon rejection:

1. require a lawful teacher actor;
2. write the canonical entitlement event with rejection outcome in the payload;
3. create no Ledger or Payroll effect unless the governing policy requires a separate refund;
4. delete the pending action.

Rejection does not revoke or expire the insurance entitlement.

The entitlement event still records that the claim was adjudicated and consumed the claim opportunity; the payload distinguishes the rejected outcome.

## VIII. Coverage Cancellation and Expiration

Cancellation of an insurance offering is prospective.

After cancellation:

- no new coverage cycle may be purchased or renewed as permitted by Class Configuration and Policies;
- existing paid coverage remains active through its established boundary;
- covered students may continue submitting claims while coverage remains active;
- teachers may continue approving or rejecting those claims.

When the coverage boundary is reached:

- `FEAT-STOR-002` records `EXPIRED` for the insurance entitlement.

Insurance claim activity never creates `EXPIRED` or `REVOKED` for the coverage entitlement.

## IX. Claim Allowance

Remaining claim allowance is derived from:

- Class Configuration / Policies;
- the active insurance entitlement;
- canonical entitlement history;
- canonical temporal boundaries.

The system SHALL NOT persist:

- `claims_remaining`;
- mutable claim balance;
- mutable insurance-use counter.

The configured policy SHALL determine which claim dispositions count toward an allowance.

## X. Idempotency

Submission and decision operations SHALL be idempotent.

Retrying a successful submission SHALL NOT create a duplicate pending action.

Retrying a successful approval or rejection SHALL NOT:

- create another compensatory Ledger credit;
- create another Payroll `MANUAL_CREDIT`;
- change the decided claim again.

## XI. Correlation and Lineage

Each claim SHALL have a claim lifecycle `correlation_id`.

Coordinated downstream effects SHALL preserve enough lineage to identify:

- the insurance claim that caused the effect;
- the insured transaction for transaction insurance, where applicable;
- the resulting Payroll event for productivity insurance, where applicable;
- the resulting Ledger transaction(s).

Correlation SHALL NOT collapse distinct domain identifiers into one ambiguous identifier.

## XII. Failure Contract

Representative failures include:

- `CLAIM_NOT_FOUND`
- `INSURANCE_ENTITLEMENT_NOT_FOUND`
- `COVERAGE_NOT_ACTIVE`
- `COVERAGE_EXPIRED`
- `CLAIM_ALLOWANCE_EXHAUSTED`
- `INVALID_CLAIM_BASIS`
- `TRANSACTION_NOT_ELIGIBLE`
- `PRODUCTIVITY_DATE_NOT_ELIGIBLE`
- `TEACHER_AUTHORITY_REQUIRED`
- `LEDGER_COMPENSATION_FAILED`

## XIII. Amendment

Revisions must remain consistent with `DOM-STORE-001`, `FEAT-STOR-001`, `FEAT-STOR-002`, `DOM-CLASS-001`, `DOM-POL-001`, `DOM-LED-001`, and the governing FEAT and temporal invariants.
