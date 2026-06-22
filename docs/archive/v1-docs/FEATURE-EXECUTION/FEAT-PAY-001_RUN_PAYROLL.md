# FEAT-PAY-001: Run Payroll

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-PAY-001 | 1.0 | 2026-04-23 | N/A | Normative |

---

## I. Purpose

This FEAT orchestrates the conversion of attendance facts into financial transactions. It is responsible for calculating earned tokens based on time tracking and posting the resulting income to the student's checking account.

---

## II. Execution Context

### 1. Required Inputs
* `actor_seat_id`: The seat ID of the teacher/admin running the payroll.
* `target_class_id`: The class for which payroll is being run.
* `idempotency_key`: Unique request identifier.

### 2. Resolved Context (MANDATORY)
* `payroll_policy`: Resolved via `DOM-CLASS` (Pay Rate, Daily Limits).
* `student_list`: All active seats in `target_class_id`.
* `correlation_id`: Generated for this payroll batch.

---

## III. Orchestration Logic

### 1. Verification Phase (Read-Only)
1. **Scope Validation**: Verify `actor_seat_id` has `ADMIN` privileges in `target_class_id`.
2. **Anchor Identification**: For each student seat:
    * Query `DOM-LED` for the timestamp of the last `PAYROLL` or `MANUAL_PAYMENT` transaction (The Individual Anchor).
3. **Attendance Fact Extraction**:
    * Query `DOM-ATT` for all attendance sessions for each student since their individual anchor.
4. **Earnings Calculation**:
    * Apply `payroll_policy` (Pay Rate) to the total seconds tracked.
    * Enforce `daily_limit` constraints if applicable.
    * Quantize final amounts to 2 decimal places.

### 2. Mutation Phase (Atomic Transaction)
1. **Ledger Execution**:
    * For each student with earnings > 0:
        * Call `FEAT-LED-001` (Post Ledger Transaction) with:
            * `from_account`: `SYSTEM_RESERVE`
            * `to_account`: `STUDENT_CHECKING`
            * `type`: `PAYROLL`
            * `correlation_id`: This payroll batch ID.
2. **Post-Commit Side Effects**:
    * **Audit Log**: Emit `ACT-MONY-002` via `DOM-OPS`.
    * **Downstream Events**: Emit `PAYROLL_COMPLETED` event. 
        * **Note**: According to `FEAT-CORE-000`, any economy rebalancing MUST be handled by a separate consumer of this event, not implicitly within this FEAT.

---

## IV. Invariants & Constraints

1. **Individual Anchoring**: Payroll MUST be calculated per-student based on their specific transaction history to prevent "double-dip" earnings.
2. **No Implicit Rebalance**: This FEAT MUST NOT trigger `activate_due_rebalances` or other economy-wide mutations directly.
3. **Idempotency**: Retrying a payroll run with the same `idempotency_key` MUST result in NO new ledger entries if the batch was already processed.

---

## V. Audit Requirements

The `DOM-OPS` audit log MUST contain:
* `correlation_id`
* `target_class_id`
* `batch_summary`:
    * Total students paid.
    * Total tokens distributed.
* `outcome`: (SUCCESS | PARTIAL_FAILURE | NO_EARNINGS)

---

## VI. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-ATT-001_ATTENDANCE_DOMAIN.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
- `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
