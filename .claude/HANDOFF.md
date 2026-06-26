# Agent Handoff — Drop Legacy Identity Tables

**Date:** 2026-06-20
**Branch:** `drop-legacy-identity-tables`
**Base:** `codex/v2.0`

## Current State

Commit 2 work is in progress and the runtime side is in a good checkpointed state.

Completed commits on this branch:
- `c0591417` `refactor: repoint legacy identity schema to users`
- `d1c1366e` `refactor: enforce tuple-only runtime context`
- `33f26119` `refactor: remove legacy student seat lookups from admin routes`
- `b8881953` `refactor: tighten canonical seat lookups in shared helpers`
- `0fa57568` `refactor: remove legacy student-seat helper paths`
- `bff89b89` `refactor: remove legacy seat-linked model helpers`
- `09acfa14` `test: drop obsolete student-teacher coverage`

## Runtime Status

The app imports cleanly.

The following runtime areas have already been converted away from `StudentTeacher` / `Seat.student_id` style reconstruction:
- `app/routes/admin.py`
- `app/routes/recovery.py`
- `app/routes/analytics.py`
- `app/attendance.py`
- `app/services/attendance_service.py`
- `app/services/store_service.py`
- `app/services/identity_service.py`
- `app/utils/deletion.py`
- `app/utils/seat_scope.py`
- `app/utils/attendance_helpers.py`
- `app/utils/analytics_engine.py`
- `app/models.py` helper methods

## Remaining Work

The remaining major work is the test migration wave.

Current test corpus still has many legacy references to:
- `StudentTeacher`
- `created_by_admin_id`
- `created_by_teacher_id`

The preferred path is to migrate the high-value tests to `canonicalContextFactory` and delete obsolete legacy coverage where it no longer matches the tuple-only model.

## Notes

- Keep the tuple-only runtime boundary intact.
- Do not reintroduce compatibility shims.
- Do not split route files in this commit.
- Leave `.claude/HANDOFF.md` untracked unless the user asks to commit it.
