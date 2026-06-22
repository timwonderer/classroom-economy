# FEAT-LED-002: Void Reverse Transaction

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-LED-002 | 1.0 | 2026-04-23 | N/A | Normative |

---

## I. Purpose

This FEAT is a **Core Orchestrator** (aliased as `FEAT-MONEY-VOID`). It is the high-integrity mechanism for reversing previous financial operations. It ensures that a void is not just a balance adjustment, but a traceable link in a transaction chain.

---

## II. Execution Context

### 1. Required Inputs
* `original_transaction_id`: The ID of the transaction to be reversed.
* `reason`: Enum explaining the reversal (e.g., `ADMIN_CORRECTION`, `PURCHASE_CANCELLED`).
* `idempotency_key`: Unique request identifier.

### 2. Resolved Context (MANDATORY)
* `original_transaction`: The authoritative record from `DOM-LED`.
* `seat_id`, `class_id`: Derived from the original transaction.
* `correlation_id`: **MUST** inherit or extend the `correlation_id` of the original operation.

---

## III. Orchestration Logic

### 1. Verification Phase (Read-Only)
1. **State Validation**: Verify that the `original_transaction`:
    * Exists in `DOM-LED`.
    * Has not already been voided (`voided_at` is NULL).
    * Is not itself a `VOID` type transaction.
2. **Authorization Guard**: Call `DOM-OPS.check_void_authorization(actor_id, original_transaction_id)`.
3. **Linked State Identification**: Identify any downstream effects that must be reversed (e.g., linked `Entitlements` in `DOM-STORE` or `Obligation` status in `DOM-OBL`).

### 2. Mutation Phase (Atomic Transaction)
1. **Ledger Reversal**:
    * Call `FEAT-LED-001` (Post Ledger Transaction) with:
        * `from_account`: The `to_account` of the original.
        * `to_account`: The `from_account` of the original.
        * `amount_cents`: The exact `amount_cents` of the original.
        * `transaction_type`: `VOID`.
        * `description`: `Reversal of [original_id]: [reason]`.
        * `correlation_id`: The current extended correlation chain.
2. **Audit Finalization**:
    * Update the `original_transaction` record: set `voided_at = NOW`, `voided_by = actor_id`.
3. **Linked State Reversal**:
    * If linked to an `Entitlement`: Call `DOM-STORE` to set `status = REVOKED`.
    * If linked to an `Obligation`: Call `DOM-OBL` to set `status = VOIDED`.
4. **Audit Trace**:
    * Emit `ACT-MONY-003` via `DOM-OPS`.

---

## IV. Invariants & Constraints

1. **Exact Reversal**: A `VOID` operation MUST reverse the exact integer amount of the original. Partial voids are PROHIBITED; a partial correction MUST be handled as a `VOID` followed by a new `FEAT-LED-001` entry.
2. **Chain Integrity**: A voided transaction record is permanent; it MUST NOT be deleted.
3. **No Double-Void**: Idempotency MUST ensure that multiple void requests for the same transaction result in only one reversal.

---

## V. Audit Requirements

The `DOM-OPS` audit log MUST contain:
* `original_transaction_id`
* `reversal_transaction_id`
* `reason`
* `correlation_id`
* `outcome`: (SUCCESS | ALREADY_VOIDED | UNAUTHORIZED)

---

## VI. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
