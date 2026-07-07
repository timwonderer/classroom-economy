# LOG-ARC-040: Seat Scope Migration Progress

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|LOG-ARC-040| 1.1 | 2026-03-08 | 1.0 |Informative|

## Summary

This log records the current implementation status of the user/seat identity split and seat-scoped data migration work as carried forward into branch `codex/v2.0`.

## Completed Work

- Removed deprecated demo-session runtime code and deleted demo SOP deployment docs.
- Added `users` and `seats` models and migrations for identity separation.
- Added seat bridge columns and dual-write listeners for:
  - `transaction`
  - `balance_cache`
  - `student_blocks`
  - `tap_events`
  - `hall_pass_logs`
  - `rent_payments`
  - `rent_waivers`
- Added seat-scope helper utilities in `app/utils/seat_scope.py`.
- Refactored student rent flows to use seat-first dual-read filtering during the migration window. v2 runtime docs now treat join-code membership as the intended authority model, not legacy fallback behavior.
- Added regression coverage:
  - `tests/test_user_seat_identity.py`
  - `tests/test_ledger_seat_scope.py`
  - `tests/test_attendance_seat_scope.py`
  - `tests/test_hall_rent_seat_scope.py`
- Hardened selected-class analytics/economy APIs to prevent teacher-global fallback when class context is explicitly selected.
- Extended hall-pass available-types API to resolve class/teacher identity via `join_code` and `teacher_public_id` (with `teacher_id` retained as compatibility fallback).
- Added regression tests for:
  - class-scoped analytics cycle resolution
  - block-scoped economy API payroll resolution behavior
  - hall-pass available-types join-code/public-id routing and out-of-scope rejection

## Remaining Work

- Refactor remaining admin-side hall pass and rent query paths to seat-first dual-read logic.
- Continue replacing classroom/economic table read paths that still rely on `student_id`-only filtering.
- Finalize migration graph hygiene and rehearsal behavior for local test-db runs where legacy multi-head version rows persist in `alembic_version`.
- Add expanded regression tests for join-code isolation in remaining admin flows.
- Complete external identifier policy rollout (`public_id` usage in routes/URLs that still expose integer IDs), including remaining student route parameters and legacy link surfaces.

## Validation Snapshot

- Targeted seat-scope test suite currently passes for ledger, attendance, hall/rent seat linking, and rent display routes.
- New hall/rent seat migration (`l1m2n3o4p5q6`) passes migration lint checks for idempotency helper requirements.
- Global migration validation script still reports pre-existing legacy migration-policy issues unrelated to this specific seat-scope change set.

## Notes

- Local database policy during this work:
  - `classroom_economy_test` is treated as disposable test infrastructure.

