# DOM-ECON-003: Ledger Integrity and Determinism

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-ECON-003     | 1.0     | 2026-04-12     | N/A        | Constitutional  |

## I. Purpose
Define the technical and domain-level mechanisms used to ensure the absolute integrity, traceability, and deterministic accuracy of the Classroom Economy ledger.

## II. Scope
Applies to the `Transaction` model, the `balance_service.py`, and all routes/jobs that mutate student balances or class-total supplies.

## III. Authority Level
Constitutional (DOM Tier). Subordinate to INV-CORE-000 (Section 3: Deterministic and Traceable Financial Logic).

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`
- `ARC-OPS-013_Money_Handling.md`

## V. Mathematical Foundation: Integer Cents
To eliminate floating-point drift (a common source of economic inconsistency), the system follows a "Double-Representation" strategy.

1. **Storage/Math**: All internal calculations and database storage must use **signed integers** representing cents (`amount_cents`).
2. **Persistence**: The `Transaction.amount_cents` column is the sole source of truth for value.
3. **Display**: Conversions to formatted currency (e.g., `"$1.50"`) must be performed at the UI/Serialization boundary only, utilizing `Decimal` for quantization.

## VI. Transaction Archetypes
Every balance mutation must be recorded as an immutable `Transaction` row.

- **DEBIT**: Negative `amount_cents` (Student pays).
- **CREDIT**: Positive `amount_cents` (Student receives).
- **REVERSAL**: A counter-entry that exactly offsets a previous transaction.

## VII. The Immutability Invariant
Per `INV-CORE-000`, the transaction log is **append-only**.

- **Prohibited**: `DELETE` or `UPDATE` operations on existing `Transaction` rows are strictly forbidden.
- **Correction**: If a transaction is erroneous (e.g., accidental fine), a new `Transaction` record with the opposite sign must be created.
- **Traceability**: All reversals must include a `note` referencing the original transaction ID to maintain a clean audit trail.

## VIII. Atomic Consistency
Transactions must be processed as atomic units of work.

### 1. The Scoping Anchor
Every transaction MUST be bound to:
- A specific `student_id`.
- A specific `class_id` (scoping container).
- A `type` (e.g., `PAYROLL`, `RENT`, `PURCHASE`).

### 2. Balance Recalculation
Student `balance` and `savings` (cached on the `Student` model) are derived values. In the event of inconsistency, the cached balance must be discarded and recalculated via a `SUM(amount_cents)` query from the `Transaction` table for the target student/class context.

## IX. Amendment
Revisions to the transaction model or financial rounding rules must be documented here and audited for compliance with the integer-cent strategy.
