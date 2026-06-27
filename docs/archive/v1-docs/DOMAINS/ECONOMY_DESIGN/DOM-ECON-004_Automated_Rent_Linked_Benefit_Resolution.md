# DOM-ECON-004: Automated Rent-Linked Benefit Resolution

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-ECON-004     | 1.0     | 2026-04-12     | N/A        | Constitutional  |

## I. Purpose
Define the business logic for resolution of $0 purchases ("perks") for students who have fulfilled their rental obligations.

## II. Scope
Applies to the `RentItem` and `StudentItem` mapping models, the `v1/purchase` and `v1/use-item` API endpoints, and the rent-status calculation logic.

## III. Authority Level
Constitutional (DOM Tier). Subordinate to INV-CORE-000 and FEAT-RENT-002.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`
- `FEAT-RENT-002_Rent_Item_Types.md`
- `DOM-ECON-003_Ledger_Integrity_and_Determinism.md`

## V. The Rent-Perk Calculus
Students who have "Paid" status for the current rent period are eligible to receive specific store items for free ($0.00).

### 1. Eligibility Check
A student is eligible for a perk if:
1. They are a member of a `ClassEconomy` with rent enabled.
2. Their current `rent_status` (calculated periodically) is `PAID`.
3. The store item being purchased is explicitly linked to their rent benefits.

## VI. Benefit Mapping Mechanics
Benefits are mapped using a three-tier hierarchy:

### 1. Granular Mapping: `RentItem`
- A specific `StoreItem` is linked to a `RentSettings` record via a `RentItem` association.
- This is the preferred V2 mapping method.

### 2. Legacy Fallback: `is_rent_linked`
- If an item has the `is_rent_linked` boolean set to `True` but lacks a specific `RentItem` mapping, the system falls back to a global "Classwide Perk" assumption.
- This ensures compatibility for items created before the granular mapping engine was implemented.

## VII. Resolution Flow (Purchase API)
When a student attempts to purchase an item:
1. **Detection**: Check if the item is "Rent Linked" (via `RentItem` or boolean flag).
2. **Status Fetch**: Calculate the student's current rent status.
3. **Price Override**: If Status == `PAID`, override the transaction amount to `0`.
4. **Log Emission**: Create a `Transaction` of type `PURCHASE` with `amount_cents = 0` and a note indicating "Rent Perk Applied".

## VIII. Inventory Redemption (`use-item`)
If a student previously purchased or was granted a "Hall Pass" item (a virtual inventory row), the redemption flow must verify if the item was originally granted as a rent benefit.
- Inventory rows created from $0 rent-perk purchases remain valid even if the student's rent status later changes to `OVERDUE`, as the benefit was locked at the time of "purchase".

## IX. Amendment
Revisions to the perk resolution logic or mapping structures must be documented here.
