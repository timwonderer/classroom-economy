# FEAT-OBLI-001: Assess Obligation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-OBLI-001 | 1.0 | 2026-04-23 | N/A | Normative |

---

## I. Purpose

This FEAT orchestrates the creation and initial fulfillment attempt of financial obligations (Rent, Fines, Assessments). It manages the lifecycle of debt from assessment to either fulfillment or delinquency.

---

## II. Execution Context

### 1. Required Inputs
* `seat_id`: The target student seat.
* `obligation_type`: (e.g., `RENT`, `FINE`, `ASSESSMENT`).
* `source_id`: Reference to the policy or incident (e.g., `rent_setting_id`, `infraction_id`).
* `amount`: (Optional) Override amount for manual assessments.
* `idempotency_key`: Unique request identifier.

### 2. Resolved Context (MANDATORY)
* `class_id`: Resolved via `seat_id`.
* `obligation_policy`: Resolved via `DOM-CLASS` or `source_id`.
* `correlation_id`: Generated for this assessment.

---

## III. Orchestration Logic

### 1. Verification Phase (Read-Only)
1. **Scope Validation**: Verify the assessment is valid for the target `seat_id` and `class_id`.
2. **Policy Resolution**: Determine the authoritative `amount_cents` and `due_date` based on the `obligation_type`.
3. **Financial Guard**:
    * Call `DOM-LED.check_balance_sufficiency(seat_id, amount_cents)`.
    * **Contract**: MUST return `{ allowed: bool }` based on `checking_balance`.

### 2. Mutation Phase (Atomic Transaction)
1. **Assessment Recording**:
    * Call `DOM-OBL` to create an `AssessmentEvent`.
    * Initialize the `Obligation` record in `PENDING` state.
2. **Fulfillment Attempt**:
    * If policy requires immediate fulfillment (e.g., Rent Day):
        * If `allowed: true`:
            * Call `FEAT-LED-001` with `transaction_type: RENT_PAYMENT` or `FINE_PAYMENT`.
            * Transition `Obligation` to `PAID`.
        * Else:
            * Transition `Obligation` to `OVERDUE`.
            * Mark the `Seat` as **Delinquent** in `DOM-OBL`.
3. **Audit Trace**:
    * Emit `ACT-OBLI-001` via `DOM-OPS` with mandatory `correlation_id`.

---

## IV. Invariants & Constraints

1. **Atomic Assessment**: An obligation MUST NOT be created without an accompanying `AssessmentEvent` audit trail.
2. **State Consistency**: If a ledger payment is successfully posted, the obligation state MUST transition to `PAID` within the same transaction.
3. **Idempotency**: Retrying an assessment with the same `idempotency_key` (e.g., same Rent period) MUST NOT create duplicate obligations.

---

## V. Audit Requirements

The `DOM-OPS` audit log MUST contain:
* `correlation_id`
* `seat_id`
* `obligation_type`
* `amount`
* `outcome`: (PAID | OVERDUE | PENDING)

---

## VI. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md`
