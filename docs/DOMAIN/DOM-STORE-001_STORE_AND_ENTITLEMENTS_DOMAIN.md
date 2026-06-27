# DOM-STORE-001: Store and Entitlements Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-STORE-001 | 2.0 | 2026-06-26 | 1.2 | Normative |

## I. Purpose

Define the Store domain as the authority over store inventory, seat-held
purchases, entitlement lifecycle, and redemption history.

## II. Scope

This domain owns store catalog rows, visibility mappings, purchase records,
and redemption events.

- **Store** owns store-purchased entitlements.
- **Obligations** owns obligation-linked entitlements (e.g., rent-linked hall passes).
- **Ledger** owns money truth. Store does not create or mutate ledger records directly.

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`

## V. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `store_items`
- `store_item_visibility`
- `store_purchases`
- `redemption_events`

These match the canonical table list in `DOM-CORE-002`.

Legacy tables `student_items`, `store_item_blocks`, and `redemption_audit_logs` are
superseded by the tables above and are not part of the canonical store authority model.

## VI. Owned Tables

### 1. `store_items`

Catalog definitions, pricing, item behavior, collective-goal setup, and rent-linked
flags. Scoped by `class_id`.

### 2. `store_item_visibility`

Per-seat visibility grants that restrict which seats can see a given store item.
Absence of rows means the item is visible to all seats in the class.

### 3. `store_purchases`

Seat-scoped purchase records. Each row represents a single purchase event linking
a seat, a store item, the quantity purchased, and the price at time of purchase.
References the ledger transaction that funded the purchase (read-only cross-domain FK).

### 4. `redemption_events`

Append-only redemption history. Each row records a redemption action (request,
approval, rejection) against a purchase, with cached display context.

## VII. Schema Contract

All tables use `seat_id + class_id` as the canonical scope. No legacy compatibility
columns (`student_id`, `teacher_id`, `join_code`) are part of the v2 contract.

### 1. `store_items`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE); canonical class boundary
- `name`
- `description`
- `price` — Numeric
- `item_type` — `immediate` | `delayed` | `collective`
- `inventory` — nullable integer; NULL means unlimited
- `limit_per_student` — nullable integer
- `is_active`
- `auto_delist_date` — UTC; item automatically deactivates after this date
- `auto_expiry_days` — days a student has to use the item after purchase
- `is_long_term_goal` — boolean; excludes from CWI affordability checks
- `bypass_cwi_warnings` — boolean
- `is_bundle` / `bundle_quantity`
- `bulk_discount_enabled` / `bulk_discount_quantity` / `bulk_discount_percentage`
- Collective goal fields (when `item_type = 'collective'`):
  - `collective_goal_type` — `fixed` | `whole_class`
  - `collective_goal_target`
  - `collective_goal_expires_at`
  - `collective_goal_instance_code`
- `redemption_prompt` — shown to teacher when a delayed item is redeemed
- `is_rent_linked` — boolean; true if this item is a store-facing alias of a rent item

Rules:

- Items are class-scoped by `class_id`. A store item belongs to exactly one class.
- Collective goal progress is tracked at the `collective_goal_instance_code` level.
  Multiple items may share an instance code to compose a single collective goal.
- `is_rent_linked` items are linked to an assessment event in the Obligations
  domain. Store owns the catalog row; Obligations owns the corresponding
  `assessment_events` row.

### 2. `store_item_visibility`

Key fields:

- `store_item_id` — FK to `store_items` (CASCADE)
- `seat_id` — FK to `seats`; the specific seat this visibility grant applies to

Rules:

- Absence of rows means the item is visible to all seats in the class.
- Presence of rows restricts visibility to only those specific seats.
- Per `INV-CORE-000 §6`, label-based grouping (e.g. `block` string labels) must not
  be used for scoping or visibility decisions. Visibility is expressed per seat,
  not per label.

### 3. `store_purchases`

Key fields:

- `id`
- `seat_id` — FK to `seats`; the purchasing seat
- `class_id` — FK to `classes` (CASCADE); canonical class boundary
- `store_item_id` — FK to `store_items`
- `quantity` — integer; number of units purchased
- `price_at_purchase` — Numeric; unit price locked at purchase time
- `total_price` — Numeric; total charge (quantity × price, after discounts)
- `status` — `purchased` | `pending` | `processing` | `completed` | `expired` | `redeemed` | `voided`
- `idempotency_key` — unique key preventing duplicate purchases
- `ledger_tx_id` — FK to `ledger_transaction`; cross-domain reference to the
  ledger event that funded the purchase (read-only)
- `purchased_at` — UTC timestamp
- `expiry_date` — UTC; when the purchase expires if not redeemed
- `is_from_bundle` / `bundle_remaining`
- `uses_remaining` — for multi-use items; decremented per use
- `collective_goal_instance_code` — links this purchase to a collective goal group

Rules:

- `ledger_tx_id` is a cross-domain reference to the Ledger domain. It does
  not transfer ledger write authority.
- Purchase history must be preserved once committed.
- Status transitions are forward-only. A redeemed or expired purchase cannot be
  re-activated without a new purchase row.

### 4. `redemption_events`

Key fields:

- `id` — UUID
- `purchase_id` — FK to `store_purchases`; the purchase being redeemed
- `seat_id` — FK to `seats`; cached for query efficiency
- `class_id` — FK to `classes` (CASCADE); cached for query efficiency
- `action` — `REQUEST` | `APPROVED` | `REJECTED`
- `source` — `LIVE`
- `initiated_by_user_id` — FK to `users`; the user who took the action
- `seat_display_name` — cached display name at time of action; not a live FK
- `class_display_label` — cached class name at time of action
- `notes` — optional text
- `timestamp` — UTC

Rules:

- Redemption event rows are append-only. No row is edited after creation.
- `seat_display_name` and `class_display_label` are cached at write time so the
  record remains interpretable even if identity or class records change.

## VIII. Constraints

- Store does not create or mutate ledger truth directly.
- Purchase and redemption history must be preserved once committed.
- Collective-goal progress is instance-scoped.
- Redemptions may change purchase state and create redemption events, but must not
  bypass Ledger for money effects.
- Per `INV-CORE-000 §6`, no table in this domain may use label strings (`block`,
  `period`, `section`) as scoping or grouping keys. Visibility is expressed per seat
  via `store_item_visibility`.

## IX. Derived / Cross-Domain Rules

- **Purchases are orchestrated through FEAT**: Store owns store-purchased entitlement
  state, Ledger owns money state. All purchase mutations flow through
  `FEAT-STOR-001` / `FEAT-STOR-002`.
- **Entitlement Sovereignty**: Obligations owns **obligation-linked** entitlements
  (e.g., rent-linked hall passes via `entitlement_events`). Store owns
  **store-purchased** items via `store_purchases`. The two streams are separate.
- **Rent-linked store items**: Some store items may be aliases of rent items. The
  Obligations domain owns the underlying `assessment_events` row; Store owns the
  `store_items` definition used for display/visibility in the catalog.
- `ledger_tx_id` on `store_purchases` is a read-only cross-domain reference to
  Ledger. It does not transfer ledger write authority.

## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000` and `DOM-CORE-002`.
