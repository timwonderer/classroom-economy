# FEAT-LED-001: Post Ledger Transaction

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-LED-001 | 1.1 | 2026-06-13 | 1.0 | Normative |

---

## I. Purpose

This is a **Core Orchestrator** (aliased as `FEAT-MONEY-POST`). It is the singular, authoritative mechanism for all monetary movement within the system. Every financial event—payroll, purchases, fines, transfers—MUST eventually invoke this FEAT to commit to the ledger.

---

## II. Execution Context

### 1. Required Inputs
* `seat_id`: The execution context (actor).
* `from_account`: `AccountType` Enum (e.g., `CHECKING`, `SAVINGS`, `RESERVE`).
* `to_account`: `AccountType` Enum.
* `amount_cents`: Positive **Integer** (Transaction value in cents).
* `transaction_type`: `TransactionType` Enum (e.g., `PAYROLL`, `PURCHASE`, `FEE`, `VOID`).
* `description`: Human-readable audit string.
* `idempotency_key`: Unique request identifier.
* `correlation_id`: **MANDATORY** link to the initiating FEAT or event.

### 2. Resolved Context
* `class_id`: Resolved via `seat_id`.

---

## III. Orchestration Logic

### 1. Verification Phase (Read-Only)
1. **Idempotency Check**: Query `DOM-LED` for an existing transaction with the provided `idempotency_key`.
    * **Success**: If found, return the existing transaction record immediately (SUCCESS).
2. **Account Validation**: Verify that `from_account` and `to_account` are valid and accessible within the `class_id` scope.
3. **Limit Validation**:
    * If `from_account` is a seat-held account: Check if the current balance is sufficient for the `amount`.
    * **Note**: This FEAT **DOES NOT** implicitly charge overdraft fees. It simply validates if the transaction is mathematically possible under current policy.

### 2. Mutation Phase (Atomic Transaction)
1. **Ledger Entry**:
    * Create a `LedgerTransaction` record with all metadata (`type`, `description`, `correlation_id`).
2. **Balance Update**:
    * Call `DOM-LED` to update the `LedgerBalanceSnapshot` for both accounts.
    * **Invariant**: The sum of all accounts in a `class_id` MUST remain consistent (Zero-sum for internal transfers).
3. **Audit Trace**:
    * Emit `ACT-MONY-001` via `DOM-OPS`.

---

## IV. Invariants & Constraints

1. **Non-Negativity**: Unless the `transaction_type` is explicitly marked as "Negative-Allowed" (e.g., `SYSTEM_ADJUSTMENT`), a transaction MUST NOT result in a negative balance for a seat-held checking account during this FEAT's execution.
2. **Atomic Totals**: Transaction creation and snapshot updates MUST happen in the same database transaction.

---

## V. Idempotency

* **Mechanism**: Database-level unique constraint on `idempotency_key`.
* **Behavior**: Atomic "Get or Create" pattern. Returns the previous result for identical keys.

---

## VI. Audit Requirements

The `DOM-OPS` audit log MUST contain:
* `idempotency_key`
* `correlation_id`
* `from_account` / `to_account`
* `amount`
* `new_balance_snapshot` (Post-mutation)

---

## VII. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
