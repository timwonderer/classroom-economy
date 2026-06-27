# V2 Banking Ledger Settlement Plan

> **Terminology Note:** This spec was written during the v1→v2 transition. Where it references `student_id` as activity key, the v2 canonical target is `seat_id`. Where it references `join_code` as the class boundary, read `class_id` (UUID) as the canonical internal boundary with `join_code` as its public alias.

**Status:** Deferred post-launch rebuild plan  
**Last Updated:** 2026-04-19

## Purpose

This document records the intended V2 banking ledger rewrite for the rebuild lane.

It defines the future authoritative model for:

- per-account balance checkpoints
- pending vs posted transaction lifecycle
- hourly settlement
- reconciliation and invariant checks

This is not part of the current live-test blocker lane. It is a saved implementation plan
for the future post-launch rebuild project.

## Summary

Implement a V2 banking model where:

- `transactions` is the only source of money movement
- `account_balances` is a per-`class_id + seat_id + account_type` checkpoint/cache table
- `available_balance` is operational and updated immediately inside the same DB transaction as the pending transaction write
- `current_balance` is authoritative and updated only by hourly settlement
- settlement is incremental from the eligible pending slice, not a full rescan on each run
- rollout is a hard V2 cutover with `class_id + seat_id` as the only canonical scope for the new ledger path

This plan intentionally does not preserve `join_code` as a ledger authority. Existing
ledger code must be replaced or isolated behind the V2 path rather than dual-run.

## Key Changes

### Data model

Create a new per-account balance table instead of a single mixed-account row.

`account_balances`

- primary key `id`
- unique key on `(class_id, seat_id, account_type)`
- columns:
  - `class_id`
  - `seat_id`
  - `account_type` in `('checking', 'savings')`
  - `available_balance_cents`
  - `current_balance_cents`
  - `available_balance_updated_at`
  - `current_balance_updated_at`
  - `last_settlement_at`
  - `created_at`
  - `updated_at`

Do not store `balance_diff`. Treat it as
`available_balance_cents - current_balance_cents`.

Replace or supersede the current transaction ledger shape with a V2 transaction record
scoped by `class_id + seat_id + account_type`.

`transactions`

- primary key `id`
- required scope:
  - `class_id`
  - `seat_id`
  - `account_type`
- event fields:
  - `created_at`
  - `effective_at`
  - `description`
  - `category`
  - `direction`
  - `amount_cents` signed
- lifecycle fields:
  - `status` enum `pending|posted|void`
  - `posted_at`
  - `voided_at`
- idempotency/lineage:
  - `idempotency_key` unique
  - `correlation_id`
  - `lineage_transaction_id` nullable self-reference
- actor/metadata:
  - `created_by_actor_type`
  - `created_by_actor_id`
  - `metadata`

Remove duplicate authority where possible:

- do not keep both `status='void'` and `is_void` in the final V2 schema unless a short migration bridge is unavoidable during migration execution
- do not treat `join_code` as part of ledger scope
- do not use `student_id` as the balance key (v2 canonical activity key is `seat_id`)

### Write path

Create one canonical ledger service for all balance mutations.

For transaction creation:

1. Begin DB transaction.
2. Lock the `account_balances` row for `(class_id, seat_id, account_type)` with `FOR UPDATE`, creating it if absent.
3. Enforce idempotency by inserting or claiming the `idempotency_key` within the same transaction boundary.
4. Insert a `pending` transaction row.
5. Apply the signed `amount_cents` directly to `available_balance_cents`.
6. Update `available_balance_updated_at`.
7. Commit.

For pending void:

1. Begin DB transaction.
2. Lock the same balance row.
3. Lock the target pending transaction row.
4. Validate it is still `pending` and not already void.
5. Mark it `void` and set `voided_at`.
6. Reverse its pending effect from `available_balance_cents`.
7. Update `available_balance_updated_at`.
8. Commit.

For refund or reversal of settled activity:

1. Never edit the settled transaction amount or effect.
2. Create a new compensating `pending` transaction with opposite signed amount.
3. Reuse the same `correlation_id` and set `lineage_transaction_id` to the source row.
4. Send it through normal settlement.

### Settlement

Add an hourly settlement job that runs on the hour in server time and processes accounts
with eligible pending work.

Per account:

1. Begin DB transaction.
2. Lock the `account_balances` row with `FOR UPDATE`.
3. Capture a settlement-owned `cutoff_timestamp`.
4. Lock eligible transactions for that `(class_id, seat_id, account_type)` where:
   - `status = 'pending'`
   - `created_at <= cutoff_timestamp`
5. Sum their signed `amount_cents`.
6. Mark those rows `posted` and set `posted_at = cutoff_timestamp`.
7. Increment `current_balance_cents` by the pending-slice net delta.
8. Set `current_balance_updated_at = now()`.
9. Set `last_settlement_at = cutoff_timestamp`.
10. Commit.

Rules:

- settlement must never use `available_balance_updated_at` as its boundary
- transactions created after the cutoff remain pending and continue affecting only `available_balance`
- settlement must be safe to retry; only rows still in `pending` are eligible
- processing should be chunked by account context, not as one giant transaction

### Invariants and reconciliation

Define the primary operational invariant:

`available_balance_cents = current_balance_cents + sum(pending non-void amount_cents for the same account)`

Define the authoritative post-settlement invariant:

`current_balance_cents = sum(posted amount_cents for the same account with posted_at <= last_settlement_at)`

Use cases:

- real-time UI reads show `available_balance`
- banking summary shows both `available_balance` and `current_balance`
- invariant checks and reconciliation use only `current_balance`, posted transactions, and `last_settlement_at`

Implement a separate reconciliation job or admin command:

- recompute account truth from posted ledger history
- compare against `current_balance_cents`
- report or repair drift explicitly
- never run this inside the normal request path

### Application and UI integration

Update all money-producing flows to use the new ledger service only:

- payroll
- manual adjustments
- rent
- store purchases and refunds
- transfers
- overdraft-related charges
- insurance or other monetary corrections

Update student banking views:

- account header shows:
  - `Checking Available Balance`
  - `Checking Current Balance (last updated ...)`
  - same for savings if shown
- transaction table shows:
  - timestamp
  - description
  - category
  - direction or type
  - status
  - amount
  - running available balance only if the UI explicitly needs per-row projection; otherwise show account header balances and transaction rows separately

Do not compute balances by scanning all transactions during page render.

## Public Interfaces

Add or standardize these service interfaces:

- `create_pending_transaction(...)`
  - requires `class_id`, `seat_id`, `account_type`, `amount_cents`, `category`, `direction`, `description`, `idempotency_key`, `correlation_id`
- `void_pending_transaction(transaction_id, ...)`
- `create_compensating_transaction(source_transaction_id, ...)`
- `get_account_balances(class_id, seat_id)`
  - returns available and current for checking and savings
- `settle_due_accounts(limit=None, cutoff=None)`
- `reconcile_account_balance(class_id, seat_id, account_type)`

All existing money mutations should call these services rather than constructing
transaction rows directly.

## Test Plan

Add coverage for:

- pending transaction creation updates `available_balance` immediately and leaves `current_balance` unchanged
- pending void restores `available_balance` and leaves `current_balance` unchanged
- settlement posts only rows at or before cutoff
- settlement increments `current_balance` by the pending-slice delta
- transactions arriving during settlement remain pending for the next run
- duplicate `idempotency_key` cannot create duplicate financial effects
- same logical event grouped by `correlation_id` across purchase, void, and refund chains
- concurrent writes on the same account serialize correctly under row locks
- concurrent writes on different accounts proceed independently
- settlement retry after partial failure is idempotent
- post-settlement refund creates a new compensating transaction rather than editing history
- reconciliation detects forced drift if balances are tampered with
- UI and API account reads use cached balances, not ledger scans
- negative balance and overdraft rules validate against `available_balance`, not `current_balance`

## Assumptions

- V2 is a hard cutover for ledger authority: `class_id + seat_id + account_type` is canonical.
- `join_code` is not part of the new ledger scope.
- Per-account balance rows are the target shape.
- Settlement is incremental from pending rows plus a separate full reconciliation path.
- All currency math is integer cents.
- A single canonical ledger service owns transaction creation, voiding, and compensation logic.
