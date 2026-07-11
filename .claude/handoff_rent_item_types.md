# Handoff: test_rent_item_types.py — Session 2026-07-10

## Status
All 31 tests in `tests/test_rent_item_types.py` pass.

## What was fixed

### Production code
- **`app/routes/admin.py`** — FEAT loops that save `RentSettings` and create `RentPolicyVersion` snapshots were calling `require_admin_feature_scope(requested_block=block)` where `block` is a `class_id` UUID, not a block label. Removed those calls; now queries `RentSettings.query.filter_by(class_id=block).first()` directly (INV-ARC-014).
- **`app/routes/admin.py` `_sync_rent_items_to_store`** — was looking up `join_code` from the DB and writing to `StoreItemBlock.block` (varchar(10), overflowed on UUID). Rewrote to use `class_id` as sole scope. Removed all `join_code` and `StoreItemBlock` operations from this function.
- **`app/routes/student.py`** — shop route guard `if teacher_id and class_id and current_block:` was always False (teacher_id=None, current_block=''). Changed to `if class_id and context:` and gets `seat_id = context.seat_id`.
- **`app/feats/rent_payment_feat.py`** — `create_pending_transaction(teacher_id=user_id, ...)` was wrong kwarg. Changed to `user_id=user_id`.

### Test fixes
- Tests that call `_add_rent_payment(..., now=anchor_now)` where `first_rent_due_date = anchor_now - 60 days` were setting `coverage_month=anchor_now.month` but the shop/API queries for `coverage_month` via `_calculate_rent_coverage_due_date(settings, utc_now())` which returns the *most recently passed due date* (may differ from `now.month`). Fixed by passing `now=coverage_due_date` instead.
- Tests that call `/student/rent/pay/A` need a `RentPolicyVersion` to exist first. Fixed by calling `create_and_schedule_rent_policy_version(class_id)` in setup.
- `seat.hall_passes` (legacy int column) replaced with `get_hall_pass_balance(seat.id, seat.class_id)` in assertions — `grant_hall_passes` writes `EntitlementEvent`, not the legacy column.

## Open decisions

### 1. `privilege` + `per_use` combination
Resolved: `/admin/rent-settings` now rejects `rent_item_type="privilege"` rows that are submitted with `purchase_duration="per_use"`. The regression test now asserts rejection, so the defensive mixed-state path is no longer needed for new writes.

### 2. Legacy columns to drop from `StoreItem` / `StoreItemBlock`
Still open. `_sync_rent_items_to_store` no longer writes `join_code` or `StoreItemBlock.block`, but the table is still actively used by:
- `app/routes/admin.py` visibility cleanup and class deletion cleanup
- `app/routes/student.py` store visibility checks
- `app/scheduled_tasks.py` orphan cleanup
- `app/utils/deletion.py` class-collapse cleanup
- several existing tests that seed `StoreItemBlock`

That means the `store_item_blocks` drop is not yet safe without a broader store-visibility migration.

## Key invariants governing this area
- **INV-ARC-014**: Authority is `class_id`, never a label/block/period
- **INV-ARC-015**: Obligation due dates are CLEs; evaluated in class timezone. `_calculate_rent_coverage_due_date` is the canonical source — tests must align their assessment `coverage_month/year` to what this function returns, not to raw `datetime.now()`
- **DOM-OBL-001**: `RentPolicyVersion` must exist for rent to be enforced; no policy version = rent not enforced = no rent items
