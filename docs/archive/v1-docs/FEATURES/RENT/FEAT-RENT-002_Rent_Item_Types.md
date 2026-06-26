# FEAT-ARC-002: Rent Item Types Implementation Plan

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| FEAT-ARC-002     | 1.2     | 2026-03-30     | 1.1        | Normative       |

## I. Purpose
This feature extends the existing itemized rent system by adding distinct item types to each rent item, driving different behaviors for privileges, free-uses, and pass renewals.

## II. Scope
Defines the behavior, data model changes, routing modifications, and guardrails necessary for supporting rent-based privileges, per-use perks, and hall-pass top-offs within the unified rent feature setup.

## III. Authority Level
Normative (FEAT Tier). Subordinate to INV-CORE-000 and FEAT-CORE-000.

## IV. Dependencies
- `FEAT-CORE-000_Feature_Foundation.md`
- `FEAT-HALL-001_Hall_Pass.md`
- `ARC-OPS-007_Database_Schema.md`

## V. Item Types Definition

### 1. Privilege (Badge/Monthly Pass)
**Behavior:** When a student pays rent, they receive a badge on the teacher's roster for each privilege item. This is essentially a "monthly pass".
**Store integration:** Can optionally be listed in store. Student who purchases it gets the same badge. Colors differentiate source (rent vs direct purchase).

### 2. Per-Use Item
**Behavior:** Paying rent grants the student a quota of free uses (store redemptions).
**Rules:**
- Must always be listed in the store.
- Teacher sets a number of free uses per rent period, or single-use if null.
- Cannot be deleted from the store directly, only via rent settings deletion.

### 3. Hall Pass
**Behavior:** Paying rent tops off the student's hall pass count (rent-granted portion only).
**Rules:**
- Teacher enters how many hall passes to grant per rent period.
- System explicitly separates rent-granted vs. purchased passes, top-off only replenishes rent-granted passes without deleting purchased ones.

## VI. Canonical Data Model

### `RentItem` Fields
- `rent_item_type`: `'privilege'`, `'per_use'`, `'hall_pass'`
- `use_limit`: Integer (For per_use).
- `hall_pass_count`: Integer (For hall-pass).

### `StoreItem` Fields
- `is_rent_linked`: Boolean (Prevents deletion).

### `StudentBlock` Fields
- `rent_hall_passes`: Integer (Tracks how many of the student's current hall passes came from rent).

### `StudentItem` Fields
- `uses_remaining`: Integer (direct tracker for per-use).

## VII. Behavior Rules and Guardrails

### Mid-Period Lock
**Rule:** If at least one student has successfully paid rent for the current coverage period, rent item *type semantics* are immutable until the next period rolls over.
**Blocked Changes:** `rent_item_type`, `use_limit`, `hall_pass_count`.

### Cycle Base-Rate Lock
**Rule:** If at least one valid (non-void) rent payment exists in a join-code coverage cycle, the cycle base rent amount is locked to the first valid payer's base amount.
**Implication:** Mid-cycle rent amount changes do not retroactively raise required payment for that active cycle; updated rates apply at the next cycle boundary.

### Waiver-Aware Paid Status
**Rule:** A student coverage period is considered paid when either:
- qualifying rent payments satisfy the required total for the cycle, or
- an active waiver covers that coverage due date for the same join code (or global waiver scope).

### Penalty Reversal Correction
**Rule:** Admins may execute a targeted correction for the active cycle when mid-cycle rate changes caused late penalties to be applied against students who met the locked base rate by grace.
**Effect:**
- creates a positive `Rent Late Fee Reversal` transaction for impacted students
- clears misapplied `late_fee_charged` values for those cycle payments
- preserves legitimate late fees for students who were actually late

### Top-Off Logic
Calculation: `top_off_amount = hall_pass_count - rent_hall_passes`. Added to `Student.hall_passes`, and sets `rent_hall_passes = hall_pass_count`.

## VIII. API Surface and Route Changes
- `POST /admin/rent-settings`: Validates modifications against the mid-period lock rule, automatically toggles store constraints based on item type.
- `POST /admin/rent/reverse-cycle-penalties`: Reverses misapplied late fees for the current cycle using the locked-rate and grace-window checks.
- `POST /student/rent/pay/<period>`: Processes rent payment and distributes grants (privilege badges, uses_remaining updates, pass topoffs).
- `POST /api/purchase-item`: Detects if item is `rent_linked` and processes a zero-cost redemption if the student has remaining uses. Subtracts `uses_remaining`.

## IX. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
