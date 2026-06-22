# FEAT-STOR-001: Store Purchase

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-STOR-001 | 1.0 | 2026-04-23 | N/A | Normative |

---

## I. Purpose

This FEAT orchestrates the exchange of currency for digital entitlements (items, perks, hall passes). It serves as the primary coordinator between the Ledger, Obligations, and Store domains.

---

## II. Execution Context

### 1. Required Inputs
* `seat_id`: The execution context (buyer).
* `item_id`: The identifier of the store item.
* `quantity`: Number of units to purchase.
* `idempotency_key`: Unique request identifier.

### 2. Resolved Context (MANDATORY)
* `user_id`, `class_id`: Resolved via `seat_id`.
* `item_price`, `item_type`: Resolved via `item_id`.
* `correlation_id`: Generated for this purchase lifecycle.

---

## III. Orchestration Logic

### 1. Validation Phase (Read-Only)
1. **Item Availability**: Verify `item_id` exists, is active in `class_id`, and has sufficient inventory.
2. **Obligation Guard**: Call `DOM-OBL.check_purchase_eligibility(seat_id)`.
    * **Contract**: MUST return `{ allowed: true }` or `{ allowed: false, reason: 'OVERDUE_RENT' }`.
    * **Action**: If `allowed: false`, abort with `OBLIGATION_BLOCK`.
3. **Financial Guard**:
    * Calculate `total_cost_cents`.
    * Call `DOM-LED.check_balance_sufficiency(seat_id, total_cost_cents)`.
    * **Logic**:
        * If `allowed: true`: Proceed.
        * If `allowed: false` AND `metadata.overdraft_available == true`: Mark for `SAVINGS_TRANSFER`.
        * Else: Abort with `INSUFFICIENT_FUNDS`.

### 2. Mutation Phase (Atomic Transaction)
1. **Financial Execution**:
    * **Core Purchase**: Call `FEAT-LED-001` with `transaction_type: PURCHASE`.
    * **Overdraft Transfer** (If marked): Call `FEAT-LED-001` with `transaction_type: OVERDRAFT_RECOVERY`.
2. **Entitlement Delivery**:
    * Call `DOM-STORE` to create an authoritative `Entitlement`.
    * **Entitlement Typing (MANDATORY)**: MUST specify `EntitlementType` Enum:
        * `IMMEDIATE_USE` (e.g., consumable item)
        * `DELAYED_USE` (e.g., ticket for future event)
        * `PRIVILEGE` (e.g., permanent badge/ability)
        * `COLLECTIVE_GOAL` (e.g., class-wide reward contribution)
3. **Inventory Update**:
    * Deduct `quantity` from `StoreItem` inventory.
4. **Audit Trace**:
    * Emit `ACT-STOR-001` via `DOM-OPS` with the full `correlation_id` chain.

---

## IV. Invariants & Constraints

1. **Ordering Guarantee**: No money is moved unless the `DOM-OBL` guard clears the seat for purchase.
2. **Atomic Integrity**: If the ledger write fails, no entitlement is granted.
3. **Idempotency**: Retrying a successful purchase MUST return the existing entitlement ID and not charge the ledger a second time.

---

## V. Special Handling: Hall Passes

If `item_type == 'hall_pass'`:
* The entitlement creation step MUST also increment the `hall_pass_balance` in `DOM-ATT`.
* This cross-domain update MUST be included in the single transaction boundary.

---

## VI. Audit Requirements

The `DOM-OPS` audit log MUST contain:
* `correlation_id`
* `item_id` / `quantity`
* `total_cost`
* `entitlement_id`
* `outcome`: (SUCCESS | INSUFFICIENT_FUNDS | OBLIGATION_BLOCK)

---

## VII. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
