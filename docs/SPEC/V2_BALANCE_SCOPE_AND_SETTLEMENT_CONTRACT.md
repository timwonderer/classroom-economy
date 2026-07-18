# V2 Balance Scope and Settlement Contract

> **Terminology Note:** This spec defines the v2 runtime contract. Balance reads and settlement are scoped by `class_id + seat_id`; `join_code` is only the public ingress alias.

## Purpose

Define the current runtime contract for student balance reads and settlement behavior in v2, and identify concrete risk against v2 constitutional/domain rules where implementation is still transitional.

This document is implementation-facing and scoped to:

- `Student.get_checking_balance(...)`
- `Student.get_savings_balance(...)`
- `app/utils/banking.py` settlement paths
- overdraft charge preconditions

## Related Authority

- `INV-CORE-000_Core_Invariants`
- `INV-ARC-007` (no write-on-read)
- `INV-ARC-014` (canonical authority keys)
- `FEAT-CORE-000_Feature_Execution_Constitutional_Directive`
- `DOM-CLASS-001_Class_Configuration_Domain`
- `FEAT-LED-001_Post_Ledger_Transaction`
- `V2_BANKING_LEDGER_SETTLEMENT_PLAN` (target-state plan)

## Current Runtime Contract (As Implemented)

### 1. Student balance read helpers are canonical-scope only

`Student.get_checking_balance(...)` and `Student.get_savings_balance(...)` require:

- `class_id` (canonical class boundary)
- `seat_id` (canonical actor boundary)

Behavior:

- Missing either key raises `ValueError`.
- Helper delegates to `ledger_service.get_available_balance(seat_id, class_id, account_type)`.
- No write side effects occur in the balance read path.

### 2. Available balance is ledger-derived, not UI-derived

`get_available_balance` returns:

- `posted_balance + pending_delta`

All components are scoped by:

- `class_id`
- `seat_id`
- `account_type`

No frontend computation is authoritative.

### 3. Settlement now resolves canonical class context

`settle_balances_for_seat(class_id, seat_id)` currently:

- resolves canonical scope from `(class_id, seat_id)`
- rejects execution if canonical scope cannot be resolved
- performs cache and transaction selection with `class_id` scope

### 4. FEAT transaction boundary ownership is preserved

Settlement sweep entrypoint:

- `settle_pending_transaction_contexts` runs under `FEAT-LED-003`
- no direct commit call inside the FEAT body
- FEAT orchestrator owns commit boundary

## Known Transitional Risks Against v2 Rules

### Risk A: Settlement interface must remain keyed by `class_id + seat_id`

Current API shape:

- `settle_balances_for_seat(class_id, seat_id)`

Canonical key:

- `class_id + seat_id`
- `seat_id` is the activity anchor in all settlement interfaces

Impact:

- extra resolution step increases ambiguity and failure modes
- conflicts with hard-cutover authority direction in v2 docs

Priority:

- High

### Risk B: Mixed legacy fields must be isolated from settlement/cache models

Runtime still carries:

- `student_id` (legacy compatibility residue)
- `join_code` (public alias only)

on cache/transaction pathways, despite class/seat canonicalization.

Impact:

- dual-authority drift risk
- maintenance overhead and inconsistent query patterns
- `student_id`-keyed interfaces must not be used in v2 settlement paths

Priority:

- High

### Risk C: Feature execution paths with class feature gating can fail closed in old tests

Store/rent routes now enforce stricter class/seat + feature authority than older tests assumed.

Impact:

- old fixtures can produce `404/403` despite valid legacy-style setup
- indicates tests need canonical fixture construction, not runtime fallback

Priority:

- Medium

## Required v2-Conformant Direction

1. Keep settlement context APIs canonical:
   - `settle_balances_for_seat(class_id, seat_id)`
2. Do not introduce join-code keyed settlement and cache lookup paths.
3. Keep reads pure:
   - no settlement invocation from balance reads.
4. Keep FEAT ownership strict:
   - no direct commits inside FEAT body functions.
5. Ensure tests seed lawful canonical state:
   - claimed seat
   - class feature enablement when route requires it
   - transaction rows with `class_id + seat_id` context where applicable.

## Verification Checklist

- [ ] No callsites invoke student balance helpers without `class_id + seat_id`
- [ ] Settlement tests pass with canonical class/seat context only
- [ ] No FEAT atomicity violations in settlement sweep
- [ ] No write-on-read regressions introduced
- [ ] Route-level store/rent tests pass with canonical fixtures and feature flags
