# DOM-STORE-001: Store and Entitlements Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-STORE-001 | 1.2 | 2026-06-13 | 1.1 | Normative |

## I. Purpose

Define the Store domain as the authority over store inventory, seat-held items,
entitlement lifecycle, and redemption history.

## II. Scope

This domain owns store catalog rows, visibility mappings, purchased/granted items,
collective-goal item state, and redemption audit history.

This domain does not own money movement. Ledger owns transaction creation and reversal.

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`

## V. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `store_items`
- `store_item_visibility`
- `student_items`
- `redemption_audit_logs`

It does not own money movement. Ledger owns transaction creation and reversal.

## VI. Owned Tables

### 1. `store_items`

Catalog definitions, pricing, item behavior, collective-goal setup, and rent-linked
flags.

### 2. `store_item_visibility`

Visibility grants that restrict which seats can see a given store item. Absence of
rows means the item is visible to all seats in the class.

### 3. `student_items`

Purchased or granted seat-held entitlements and use lifecycle.

### 4. `redemption_audit_logs`

Historical request/approval/rejection audit rows for redemptions.

## VII. Schema Contract

### 1. `store_items`

Key fields:

- `id`
- `class_id` — FK to `classes` (CASCADE)
- `join_code` — denormalized human-facing alias; resolves to `class_id`
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
  `join_code` is carried as a denormalized alias.
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

### 3. `student_items`

Key fields:

- `id`
- `seat_id` — FK to seats (the purchasing/receiving seat)
- `store_item_id` — FK to `store_items`
- `join_code` — denormalized human-facing alias; resolves to `class_id`
- `status` — `purchased` | `pending` | `processing` | `completed` | `expired` | `redeemed`
- `purchase_date` — UTC
- `purchase_transaction_id` — FK to `transaction`; cross-domain reference to the
  ledger event that funded the purchase
- `expiry_date` — UTC; when the item expires if not redeemed
- `redemption_date` — UTC; when the item was redeemed
- `redemption_details` — student-provided notes at redemption
- `is_from_bundle` / `bundle_remaining`
- `quantity_purchased` — for bulk discount purchases
- `uses_remaining` — for multi-use items; decremented per use
- `collective_goal_instance_code` — links this holding to a collective goal group

Rules:

- `purchase_transaction_id` is a cross-domain reference to the Ledger domain. It does
  not transfer ledger ownership to this domain.
- Entitlement issuance/use/expiry history must be preserved once committed.
- Status transitions are forward-only. A redeemed or expired item cannot be
  re-activated without a new purchase row.

### 4. `redemption_audit_logs`

Key fields:

- `id` — UUID
- `student_item_id` — nullable FK to `student_items`
- `initiated_by_user_id` — FK to users (the teacher who took the action)
- `join_code` — denormalized human-facing alias; resolves to `class_id`
- `action` — `REQUEST` | `APPROVED` | `REJECTED`
- `source` — `LIVE`
- `notes`
- `seat_display_name` — cached display name at time of action; not a live FK
- `class_display_label` — cached class name at time of action
- `timestamp` — UTC

Rules:

- Audit log rows are append-only. No row is edited after creation.
- `seat_display_name` and `class_display_label` are cached at write time so the audit
  record remains interpretable even if identity or class records change.

## VIII. Constraints

- Store does not create or mutate ledger truth directly.
- Entitlement issuance/use/expiry history must be preserved once committed.
- Collective-goal progress is instance-scoped.
- Redemptions may change entitlement state and audit history, but must not bypass
  Ledger for money effects.
- Per `INV-CORE-000 §6`, no table in this domain may use label strings (`block`,
  `period`, `section`) as scoping or grouping keys. Visibility is expressed per seat
  via `store_item_visibility`.

## IX. Derived / Cross-Domain Rules

- **Purchases are orchestrated through FEAT**: Store owns store-purchased entitlement state, Ledger owns money state.
- **Entitlement Sovereignty**: Obligations owns **obligation-linked** entitlements (e.g., rent-linked hall passes). Store owns **store-purchased** items. The `entitlement_events` in the Obligations domain is a separate stream from `student_items` in the Store domain.
- **Rent-linked store items**: Some store items may be aliases of rent items. The Obligations domain owns the underlying `assessment_events` row; Store owns the `StoreItem` definition used for display/visibility in the catalog.
- `purchase_transaction_id` on `student_items` is a read-only cross-domain reference to Ledger. It does not transfer ledger write authority.

## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
