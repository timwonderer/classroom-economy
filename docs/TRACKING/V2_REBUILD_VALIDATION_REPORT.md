# V2 Rebuild Validation Report — Revision 20

**Generated:** 2026-06-01
**Branch:** `codex/v2.0`  
**Against:** `V2_Full_compliance_migration_plan.md`  
**Methodology:** Direct code inspection (multi-pass), migration chain analysis, model column audit, service/FEAT write-path tracing, test coverage enumeration, CI infrastructure review, adversarial scorecard analysis, INV compliance sweep, auth-path and session-bridge verification (Revision 3 additions)

### Post-Report Update (2026-06-07, `codex/v2.0`) — Tracker Reconciliation and Validation Refresh

- Re-ran a documentation-only validation pass against the active tracker and current rebuild report state.
- Updated the active migration plan with a timestamped checkpoint to reflect the latest confirmed progression without promoting unverified waves.
- Confirmed the tracker still treats Waves 3-6 as the last fully evidenced landed cluster, with Wave 7 open and Waves 8-12 still pending their verification gates.
- No code-path or schema changes were made in this refresh; this pass only aligned the live docs with the most recent validated state.
- Validation:
  - active tracker reconciliation -> pass
  - report/state consistency check -> pass
  - no completion claims advanced beyond current evidence -> pass

### Post-Report Update (2026-06-15, `codex/v2.0`) — Wave 11 Bulk Test TeacherBlock→Seat Refactoring

- Completed bulk migration of ~60 test files from `TeacherBlock` fixtures to canonical `Seat` + `IdentityProfile` + `ClassEconomy` constructs.
- Deleted `tests/helpers/mock_teacher_block.py` shim entirely.
- 7 legacy-only test modules marked `pytest.skip(allow_module_level=True)` for Wave 11 decommissioning.
- `TeacherBlock` test surface reduced from 71 files to 27 (62% reduction). Of remaining 27, only ~8 have active model usage; rest are skip markers or string references.
- Established normative vocabulary standards: `docs/REFERENCE/REF-TERM-001_DEVELOPER_VOCABULARY.md` and `REF-TERM-002_USER_VOCABULARY.md`.
- README rewritten to reflect v2 architecture reality.
- Validation:
  - PR #1220 review feedback (28 comments) all addressed and resolved
  - Missing `datetime`/`timezone` imports fixed
  - Invalid `Seat.teacher_id` / `Seat.is_claimed` references corrected
  - Teacher seat `profile_type` corrected to `teacher_primary`

### Post-Report Update (2026-06-21, `continue-legacy-identity-drop`) — Canonical auth hydration hardening

- Student login now treats `last_active_class_id` as a persisted preference rather than a terminal authority anchor.
- When one or more valid class/seat options exist, the login boundary now routes through explicit class selection instead of hard-failing on a missing or stale persisted class pointer.
- When no valid class/seat pair remains, the login flow fails closed with an invariant-violation log entry and a generic role-appropriate recovery message.
- Verification:
  - auth/context focused pytest slice -> pass
  - canonical context immutability guard -> pass

### Post-Report Update (2026-06-09, `codex/v2.0`) — Wave 7 Insurance Claim Canonical Lifecycle Write

- Completed the previously open Wave 7 write-path gap for insurance-claim resolution.
- `app/services/obligations_service.py` now:
  - emits canonical `assessment_events` + `obligation_lifecycle` rows when a
    claim is filed
  - requires the canonical claim assessment created at filing time during
    resolution; no legacy backfill or compatibility bridge remains in this path
  - records canonical `obligation_satisfaction` rows for approved/paid claims
    and canonical `obligation_reversal` rows for rejected claims
- Regression evidence:
  - `tests/test_insurance_snapshots.py::test_admin_claim_approval_uses_frozen_claim_cap`
    now asserts the live admin approval path produces canonical claim
    assessment/lifecycle/satisfaction rows alongside the reimbursement ledger
    entry
- Wave 7 remains open for remaining legacy-read cutover, parity validation, and
  transitional/legacy obligation-table drops.
- Validation:
  - `python3 -m py_compile app/services/obligations_service.py tests/test_insurance_snapshots.py` -> pass
  - `./venv/bin/pytest -q tests/test_insurance_snapshots.py` -> `3 passed`

### Post-Report Update (2026-06-06, `codex/v2.0`) — Wave 7 Obligations Schema Contract

- Landed transitional migration `0006_obligations_domain.py` and canonical
  correction migration `0007_obligations_schema_contract.py`.
- Runtime `ObligationAssessment` now maps to `assessment_events`; canonical
  `obligation_lifecycle` state is emitted for rent payments and insurance
  enrollments.
- `obligation_satisfaction`, `obligation_reversal`, and `entitlement_events`
  foreign keys now reference `assessment_events`.
- Both the dedicated v2 test database and the repaired development database
  completed `0007 -> 0006 -> 0007` downgrade/re-upgrade validation.
- Development drift was traced to five empty, unreferenced canonical bootstrap
  placeholders. Removing those placeholders allowed `0006` and `0007` to
  recreate the governed schemas; the development database now reports `0007`.
- Wave 7 remains open for insurance-claim lifecycle migration, remaining
  legacy-read cutover, parity validation, and transitional/legacy table drops.
- Validation:
  - migration lint -> pass
  - single Alembic head -> `0007`
  - app factory import -> pass
  - focused obligations and insurance scoping suite -> `35 passed`

### Post-Report Update (2026-06-02, `codex/v2.0`) — TLCP Runtime Actor-Public-ID Cutover

- Support/log actor identity now resolves to class-scoped `Seat.public_id` at runtime:
  - `resolve_actor_context()` emits `actor_public_id`
  - request traces, error events, and ticket correlation packs store the seat UUID
  - student support recent-error prompts resolve from active `seat_id`
  - issue creation requires the submitted class-scoped seat and uses its `public_id`
- Removed the nested TLCP savepoint from `create_issue()` so support-ticket creation
  stays inside the FEAT-owned transaction boundary.
- Completed `TLCP-SCHEMA-001`: physical TLCP actor columns, indexes, log labels, tests,
  and sysadmin copy affordances now use `actor_public_id`.
- Added idempotent migration `f6a7b8c9d0e1_rename_tlcp_actor_public_id.py` and
  validated upgrade, explicit downgrade to `ebb7b66b2176`, and re-upgrade to head.
- Live schema check confirms `actor_request_trace`, `error_events`, and
  `ticket_correlation_pack` expose `actor_public_id` only for TLCP actor identity.
- Validation:
  - `git diff --check` -> pass
  - touched-module `python -m py_compile` -> pass
  - migration lint -> pass
  - migration upgrade/downgrade/re-upgrade -> pass
  - TLCP focused suite -> `6 passed`
  - adjacent public-ID authority suite -> `61 passed`

### Post-Report Update (2026-06-02, `codex/v2.0`) — Support Issue Actor-Public-ID Schema Rename

- Renamed the support issue filing-actor reference from the former student-opaque
  field name to `issues.actor_public_id`.
- Updated ORM, issue creation, sysadmin support templates, and tests to use
  `actor_public_id`.
- Added migration `f7b8c9d0e1f2_rename_issue_actor_public_id.py`; the column stores the
  filing seat's UUID `Seat.public_id`.
- Fixed adjacent stale `collapse_universe()` class lookup so class deletion resolves
  by `join_code` correctly.
- Validation:
  - active grep for former support issue opaque-student field names -> no app/test/doc
    hits
  - touched-module `python -m py_compile` -> pass
  - migration lint -> pass
  - `flask db heads && flask db current` -> `f7b8c9d0e1f2 (head)`
  - live schema check confirms only `issues.actor_public_id` remains
  - affected support/schema/class-deletion suite -> `15 passed`

### Post-Report Update (2026-06-02, `codex/v2.0`) — Teacher-Seat Public Lookup Runtime Reduction

- Provisioned teacher `Seat` rows in class-anchor creation and claim-anchor repair
  paths.
- Removed role-specific teacher-public-ID lookup authority from class-scoped runtime:
  - obsolete `/student/switch-teacher/<teacher_public_id>` returns `404`
  - hall-pass pass-type lookup rejects `teacher_public_id`
  - public hall-pass activity lookup requires matching teacher-seat `Seat.public_id`
    plus explicit `class_id`, and returns only that class's logs
- Removed the obsolete teacher-switch scope resolver and policy branch.
- Closed two adjacent fail-closed defects:
  - unresolved explicit `join_code` aliases no longer fall back to another claimed seat
  - dashboard scope failure now redirects to the live class-selection endpoint
- Validation:
  - `git diff --check` -> pass
  - touched-module `python -m py_compile` -> pass
  - adjacent tenancy, authorization, and class-switch suite -> `61 passed`

### Post-Report Update (2026-06-02, `codex/v2.0`) — UUID Seat Public Identity Contract

- Added `docs/SPECS/V2_IDENTITY_AND_OWNERSHIP_MODEL.md` as the normative
  clean-v2 identity ownership contract.
- Formalized UUID-encoded `seats.public_id` as the single deidentified public actor
  identifier for teacher and student seats.
- Classified `Admin.public_id`, `Admin.teacher_public_id`, `Student.opaque_reference`,
  `Student.internal_reference`, and separate TLCP actor identity families as invalid
  v2 residue rather than compatibility surfaces to preserve.
- Updated `DOM-IDEN-001`, `DOM-SUP-001`, `INV-ARC-008`, the student identity spec, the
  active identity inventory, and the canonical ORM reference model.
- Preserved `hall_pass_verify_token` as an unresolved capability-ownership question,
  separate from actor identity.
- Validation:
  - `git diff --check` -> pass
  - `python -m py_compile app/models_canonical.py app/models.py app/routes/admin.py tests/test_admin_tenancy.py` -> pass
  - focused admin-tenancy suite -> `5 passed, 10 deselected`

### Post-Report Update (2026-06-01, `codex/v2.0`) — Admin Student Detail Seat-Public-ID Scope Closure

- Replaced teacher-facing numeric student-detail URLs with class-local seat public IDs:
  - `/admin/students/<int:student_id>` now returns `404`.
  - `/admin/students/<string:student_public_id>` resolves only `Seat.public_id` values carried by short-lived signed navigation tokens.
  - Teacher-facing templates and post-action redirects now generate student-detail URLs through `student_detail_url(...)`.
- Enforced class-local context authority for student-detail navigation:
  - `Seat.public_id` is the URL identity; neither legacy `student_id` nor role-specific public identity is accepted as a detail-route identifier.
  - resolution filters by `Seat.public_id` + teacher-owned `ClassEconomy`.
  - the resolved `Seat.class_id` must match both the signed navigation token and active `session["current_class_id"]`; mismatch returns `404`.
  - URL generation treats active `current_class_id` as authoritative and does not fall back to another seat when the student is absent from that class.
- Added adversarial tenancy regressions:
  - shared student across two teachers / two classes: teacher A cannot query teacher B's seat public ID, even with a correctly signed token shaped for teacher A.
  - shared student across two classes taught by one teacher: class A URL works in class A context, returns `404` after switching to class B context, and class B context generates seat B's distinct public ID.
- Validation:
  - `python -m py_compile app/routes/admin.py tests/test_admin_tenancy.py` -> pass
  - `pytest -q tests/test_admin_tenancy.py -k "shared_student_accessible_to_multiple_teachers or student_detail_public_url_requires_nav_token or student_detail_public_id_is_seat_scoped_for_shared_student or student_detail_public_id_requires_active_class_for_same_teacher or student_detail_forbids_cross_tenant_access"` -> `5 passed, 10 deselected`

### Post-Report Update (2026-05-30, `codex/v2.0`) — Wave 6 Final Cutover Closure

- Closed the remaining Wave 6 cutover items from Revision 17:
  - `app/attendance.py:get_batch_attendance_events(...)` now reads canonical `attendance_sessions` and synthesizes active/inactive transitions in-memory for payroll/admin calculations (no `tap_events` read dependency in this path).
  - `app/attendance.py:batch_auto_tapout_students(...)` now writes via canonical `student_tap(...)` session-state mutation flow instead of creating legacy `TapEvent` rows directly.
  - Removed hard legacy schema dependency on `TapEvent.student_id`:
    - `app/models.py:TapEvent.student_id` now nullable.
    - `app/models.py:_sync_tap_event_seat(...)` now backfills `student_id` from `seat_id` when absent while keeping class/seat hard invariants enforced.
    - new migration: `migrations/versions/e4a2b7c9d1f0_make_tap_event_student_id_nullable.py`.
- Validation:
  - `python3 scripts/lint_migrations.py migrations/versions/e4a2b7c9d1f0_make_tap_event_student_id_nullable.py` → pass
  - `flask db heads` → `e4a2b7c9d1f0 (head)`
  - `flask db upgrade` → pass (`f2c9d1a6b7e8 -> e4a2b7c9d1f0`)
  - `flask db downgrade f2c9d1a6b7e8` → pass
  - `flask db upgrade` (re-upgrade) → pass
  - `flask db current` → `e4a2b7c9d1f0 (head)`
  - `pytest -q tests/test_attendance_seat_scope.py tests/test_attendance.py tests/test_hall_pass_checkout.py tests/test_tap_flow.py tests/test_admin_payroll_scoped_balances.py tests/test_api_tenancy.py -k "hall_pass or tap_entries or student_block_settings or block_tap_settings or payroll or attendance or seat_scope"` → `33 passed, 10 deselected`
  - `python3 -m py_compile app/attendance.py app/models.py app/feats/attendance.py tests/test_attendance_seat_scope.py migrations/versions/e4a2b7c9d1f0_make_tap_event_student_id_nullable.py` → pass

### Post-Report Update (2026-05-30, `codex/v2.0`) — Wave 6 Validation + Tracker Drift Closure

- Validated current Wave 6 attendance slice against live code/tests and reconciled stale tracker claims.
- Runtime/FEAT reality validated in this slice:
  - `app/feats/attendance.py` exists and owns attendance/hall-pass/admin mutation helpers used by `app/routes/api.py`.
  - `app/services/attendance_service.py` now computes attendance status/duration from canonical `AttendanceSession` + `SeatAttendanceState`.
  - `AttendanceSession` / `SeatAttendanceState` are runtime models in `app/models.py` and are exercised by current attendance suites.
  - Wave 6 migration file exists as `migrations/versions/c6a8f6d1e2b3_create_attendance_sessions_and_state.py`.
- Validation:
  - `python3 -m py_compile app/attendance.py app/services/attendance_service.py app/feats/attendance.py app/routes/api.py tests/test_attendance.py tests/test_hall_pass_checkout.py tests/test_tap_flow.py tests/test_api_tenancy.py` → pass
  - `pytest -q tests/test_attendance.py tests/test_hall_pass_checkout.py tests/test_tap_flow.py tests/test_tap_toggle_and_lock.py` → `23 passed`
  - `pytest -q tests/test_api_tenancy.py -k "hall_pass or tap_entries or student_block_settings or block_tap_settings"` → `9 passed`
  - `pytest -q tests/test_api_admin_tap_scope.py tests/test_attendance_seat_scope.py` → `4 passed`
  - `python3 scripts/lint_migrations.py migrations/versions/c6a8f6d1e2b3_create_attendance_sessions_and_state.py` → pass
  - `flask db heads` → `f2c9d1a6b7e8 (head)`

### Post-Report Update (2026-05-28, `codex/v2.0`) — Attendance Clean-Break Canonicalization (No Transitional Mirror)

- Enforced clean-break direction for attendance runtime and tests:
  - Removed transitional tap-to-canonical mirror listener path; attendance state is now written directly via canonical FEAT/session-state mutation flow.
  - Updated attendance compatibility/service usage to read canonical `attendance_sessions` / `seat_attendance_state` for active status and duration calculations.
  - Converted attendance and hall-pass checkout/checkin regression tests away from `TapEvent` assertions to canonical session/state assertions.
- Validation:
  - `pytest -q tests/test_attendance.py tests/test_tap_flow.py tests/test_hall_pass_checkout.py` → `20 passed`
  - `pytest -q tests/test_tap_toggle_and_lock.py tests/test_api_tenancy.py -k "hall_pass or tap_entries or student_block_settings or block_tap_settings"` → `10 passed`
  - `python3 -m py_compile app/attendance.py app/services/attendance_service.py app/feats/attendance.py app/routes/api.py tests/test_attendance.py tests/test_hall_pass_checkout.py` → pass

### Post-Report Update (2026-05-28, `codex/v2.0`) — Attendance Step-3 FEAT Coverage Closure (Hall Pass Admin Controls)

- Closed remaining hall-pass admin mutation paths in attendance API:
  - Split `/api/hall-pass/settings` into:
    - `GET` read-only handler
    - `POST` handler wrapped in `@feat_shell("FEAT-ATTN-001")`
  - Added FEAT wrappers for:
    - `/api/hall-pass/setup` `POST`
    - `/api/hall-pass/verify-token/rotate` `POST`
- Moved settings/token writes behind attendance FEAT helpers in `app/feats/attendance.py`:
  - `update_hall_pass_queue_settings(...)`
  - `save_hall_pass_setup_config(...)`
  - `rotate_teacher_hall_pass_verify_token(...)`
- Validation:
  - `python3 -m py_compile app/feats/attendance.py app/routes/api.py` → pass
  - `pytest -q tests/test_hall_pass_verify.py tests/test_hall_pass_checkout.py` → `27 passed`
  - `pytest -q tests/test_api_tenancy.py -k "hall_pass or tap_entries or student_block_settings or block_tap_settings"` → `9 passed`
  - `pytest -q tests/test_tap_flow.py tests/test_tap_toggle_and_lock.py tests/test_attendance.py::test_get_session_status tests/test_attendance.py::test_get_all_block_statuses` → `10 passed`
  - `python3 scripts/policy_guardrails.py --git-diff-base origin/main --git-diff-head HEAD` → `Policy guardrails: clean`

### Post-Report Update (2026-05-28, `codex/v2.0`) — Attendance Step-2 FEAT Mutation Ownership (Admin Tap Controls)

- Expanded attendance FEAT ownership for remaining admin mutation routes:
  - `app/routes/api.py:/api/admin/tap-entries/<event_id> DELETE` now delegates soft-delete mutation to `app/feats/attendance.py:soft_delete_tap_entry(...)`.
  - `app/routes/api.py:/api/admin/student-block-settings POST` now delegates canonical toggle mutation to `app/feats/attendance.py:set_student_block_tap_enabled(...)`.
  - `app/routes/api.py:/api/admin/block-tap-settings POST` is now explicitly wrapped with `@feat_shell("FEAT-ATTN-001")` and uses FEAT helper mutation path per seat.
- Preserved tenancy fail-closed behavior while FEAT-izing:
  - `set_student_block_tap_enabled(...)` now detects legacy `StudentBlock(student_id, period)` rows and only promotes rows that can be proven in-scope for the current class.
  - out-of-scope or null-scope legacy rows now raise `PermissionError`, which routes map back to prior expected API behavior:
    - student-block toggle: `403`
    - block-level bulk toggle: `404`
- Validation:
  - `python3 -m py_compile app/feats/attendance.py app/routes/api.py` → pass
  - `pytest -q tests/test_api_tenancy.py -k "student_block_settings or block_tap_settings_post_preserves_out_of_scope_join_code_row"` → `3 passed`
  - `pytest -q tests/test_api_admin_tap_scope.py tests/test_api_tenancy.py -k "tap_entries or student_block_settings or block_tap_settings"` → `6 passed`
  - `pytest -q tests/test_hall_pass_checkout.py tests/test_tap_flow.py tests/test_attendance.py::test_get_session_status tests/test_attendance.py::test_get_all_block_statuses` → `17 passed`
  - `pytest -q tests/test_tap_toggle_and_lock.py tests/test_api_fixes.py` → `7 passed`

### Post-Report Update (2026-05-27, `codex/v2.0`) — Attendance Step-1 Correctness Slice

- Fixed `app/attendance.py:get_session_status(...)` join-code/class-scope ordering bug:
  - `join_code` is now resolved before class lookup and day-window computation.
  - Eliminates the pre-assignment `join_code` reference path.
- Normalized attendance/hall-pass day-bound logic to class-scoped temporal authority in `app/routes/api.py`:
  - daily limit checks now use `get_class_today_range(class_id, ...)` instead of generic `day_bounds_utc(...)`
  - done-for-day local date stamps now use `get_class_now(class_id, ...).date()`
  - simultaneous-pass/day-limit queue windows now resolve from class-local day boundaries
  - auto tap-out loop now computes start/end-of-day per class instead of once from ambient/session timezone
- Removed stale hall-pass templates carrying dead endpoint contracts:
  - deleted `templates/hall_pass_terminal.html` (referenced removed `/api/hall-pass/lookup/*`, `/terminal/use`, `/terminal/return`, `/queue`)
  - deleted `templates/hall_pass_queue.html` (referenced removed `/api/hall-pass/queue`)
  - no active route currently renders either template
- Validation:
  - `pytest -q tests/test_attendance.py::test_get_session_status tests/test_attendance.py::test_get_all_block_statuses` → `2 passed`
  - `python3 -m py_compile app/attendance.py app/routes/api.py` → pass

### Post-Report Update (2026-05-27, `codex/v2.0`) — Attendance Class/Seat Canonical Context Hardening

- Enforced class-context checks for student hall-pass mutations via `class_id` authority:
  - `app/routes/api.py:_enforce_hall_pass_student_context(...)` now resolves active context from `current_class_id`/class context and blocks mutation when a legacy `current_join_code`-only session tries to mutate.
  - mismatch enforcement now keys on `log_entry.class_id` vs active `class_id`.
- Removed internal join-code authority fallback in attendance FEAT pass scope resolution:
  - `app/feats/attendance.py:_resolve_student_pass_scope(...)` now resolves only canonical `seat_id` + `class_id`.
  - checkout/checkin FEAT paths backfill missing `seat_id`/`class_id` on legacy pass rows before mutation and only use `join_code` as a display/logging alias.
- Removed join-code authority lookup from student tap mutation orchestration:
  - `app/routes/api.py:/api/tap` now resolves runtime scope from active class context (`current_class_id`/`Seat`) and canonical seat lookup by `(student_id, class_id)`.
  - class lookup by `join_code` for tap mutations was removed; `join_code` is retained only as a UI/logging alias after class scope is established.
- Updated hall-pass checkout regression coverage to canonical anchors:
  - `tests/test_hall_pass_checkout.py` now seeds a canonical `Seat` for the student fixture and drives class-context assertions with `current_class_id` (not `current_join_code` authority).
- Updated tap-flow coverage fixtures to canonical identity prerequisites:
  - `tests/test_tap_flow.py` helper now seeds claimed, user-bound seats with class anchors.
  - legacy join-code-only auto-tapout test was replaced with canonical no-seat no-op behavior.
- Extracted additional `/api/tap` mutation bodies behind attendance FEAT helpers:
  - `app/feats/attendance.py` adds:
    - `get_or_create_student_block(...)`
    - `apply_standard_tap_mutations(...)`
  - `app/routes/api.py:/api/tap` now delegates:
    - StudentBlock create/retry path through `feat_get_or_create_student_block(...)`
    - Hall-pass request row creation through `feat_request_hall_pass(...)`
    - Standard start/stop mutation writes (auto period switch tap-out, auto hall-pass return, tap append, done-for-day state) through `feat_apply_standard_tap_mutations(...)`
  - Route retains identity/scope resolution (`class_id` + `seat_id`) and response assembly.
- Extracted `/api/tap` remaining domain policy guards behind FEAT helpers:
  - `app/feats/attendance.py` adds:
    - `check_start_work_daily_limit(...)` (read-only daily limit guard)
    - `check_hall_pass_request_policy(...)` (read-only hall-pass feature/queue/policy guard)
  - `app/routes/api.py:/api/tap` now consumes guard results and no longer owns these policy calculations inline.
- Validation:
  - `pytest -q tests/test_hall_pass_checkout.py` → `10 passed`
  - `pytest -q tests/test_tap_flow.py` → `5 passed`
  - `pytest -q tests/test_hall_pass_checkout.py tests/test_tap_flow.py tests/test_attendance.py::test_get_session_status tests/test_attendance.py::test_get_all_block_statuses` → `17 passed`
  - `pytest -q tests/test_attendance.py::test_get_session_status tests/test_attendance.py::test_get_all_block_statuses` → `2 passed`
  - `pytest -q tests/test_admin_tenancy.py -k "enforce_daily_limits_taps_out_when_limit_reached_in_scope"` → `1 passed`
  - `python3 -m py_compile app/feats/attendance.py app/routes/api.py tests/test_hall_pass_checkout.py tests/test_tap_flow.py` → pass

### Post-Report Update (2026-05-27, `codex/v2.0`) — Migration Chain Blocker Closure

- Closed the local `flask db upgrade` blocker at migration `a91cf11e8b2d`:
  - root cause: legacy Postgres RLS policy `teacher_isolation_policy` on `feature_settings` depended on `teacher_id`, so `DROP COLUMN teacher_id` failed with `DependentObjectsStillExist`.
  - fix: `migrations/versions/a91cf11e8b2d_drop_feature_settings_legacy_scope_columns.py` now detects and drops `teacher_isolation_policy` before dropping legacy scope columns.
- Validation:
  - `python3 scripts/lint_migrations.py migrations/versions/a91cf11e8b2d_drop_feature_settings_legacy_scope_columns.py` → pass
  - `flask db upgrade` now completes through:
    - `f84c7ad2c1aa -> a91cf11e8b2d`
    - `a91cf11e8b2d -> b1c2d3e4f5a6`
  - DB revision state:
    - `flask db heads` → `b1c2d3e4f5a6 (head)`
    - `flask db current` → `b1c2d3e4f5a6 (head)`
  - regression sanity:
    - `pytest -q tests/test_admin_tenancy.py tests/test_dashboard_rendering.py tests/test_backfill_transactions.py` → `28 passed`

### Post-Report Update (2026-05-27, `codex/v2.0`)

- DB harness stabilization for Postgres-backed tests:
  - `tests/conftest.py` now serializes full app-fixture lifecycle with `pg_advisory_lock(...)` and rebuilds schema on a single connection before `metadata.create_all(...)`.
  - This closes the intermittent concurrent test-db rebuild races observed as:
    - duplicate enum/type creation (`classmembershiprole`)
    - schema-drop interference during parallel test setup (`relation "teachers" does not exist`)
- Daily-limit enforcement scope correction:
  - `app/routes/admin.py` `enforce_daily_limits()` now passes the resolved `join_code` into `get_daily_limit_seconds(...)`, restoring class-scoped limit lookup for canonical class paths.
- Tenancy regression fixture alignment:
  - `tests/test_admin_tenancy.py` now seeds canonical class scope (`ClassEconomy`/`Seat`) for JOINA/JOINB scenarios and aligns stale-session assertions with current class-resolution behavior.
- Validation:
  - `pytest -q tests/test_admin_tenancy.py -vv` → `12 passed`
  - `pytest -q tests/test_dashboard_rendering.py tests/test_backfill_transactions.py` → `16 passed`
  - `python3 -m py_compile app/routes/admin.py tests/test_admin_tenancy.py tests/conftest.py` → pass

### Post-Report Update (2026-05-24, `codex/v2.0`)

- Closed the FEAT compliance finding for economy snapshot persistence:
  - `app/routes/admin.py` `/api/economy/analyze` is now wrapped in `@feat_shell("FEAT-ADMN-001")`
  - `_get_frozen_economy_analysis_payload(...)` no longer calls `db.session.commit()`; it uses `db.session.flush()` and relies on FEAT transaction ownership
  - analyze endpoint error path now explicitly calls `db.session.rollback()` before returning `500`
- Validation:
  - `pytest -q tests/test_economy_api.py -k "analyze_endpoint_"` → `7 passed`
- Added explicit guardrail coverage for the deferred Wave 3 structural table drops:
  - `scripts/wave3_identity_drop_surface_guardrail.py`
  - `docs/archive/v1-development/tracking/wave3_identity_drop_surface_baseline.json`
  - `tests/test_wave3_identity_drop_surface_guardrail.py`
  - baseline-census confirms current deferred coupling is explicit and now blocked from expansion unless baseline is intentionally re-cut after approved reductions
- Landed first approved reduction slice and refreshed baseline:
  - `app/routes/student.py` no longer directly references `RecoveryRequest` / `StudentRecoveryCode`; student recovery accesses were routed through `app/services/recovery_bridge_service.py`
  - targeted validation: `pytest -q tests/test_recovery_bridge_service.py` → `3 passed`
  - baseline re-cut in `docs/archive/v1-development/tracking/wave3_identity_drop_surface_baseline.json` after verified reductions
- Landed major follow-on reduction slice on admin/runtime recovery paths:
  - `app/routes/admin.py` recovery flow now uses `app/services/recovery_bridge_service.py` for recovery-request/code lifecycle operations instead of direct `RecoveryRequest` / `StudentRecoveryCode` symbol access
  - `app/utils/student_deletion.py` recovery-code cleanup now routes through bridge service
  - targeted validation: `pytest -q tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py` → `6 passed`
  - baseline re-cut confirms `RecoveryRequest` and `StudentRecoveryCode` runtime symbol couplings are removed from `app/**`
- Landed passkey/onboarding decoupling slice:
  - `app/routes/admin.py` now routes passkey credential and onboarding lifecycle operations through `app/services/admin_identity_bridge_service.py`
  - `app/routes/system_admin.py` no longer carries `TeacherOnboarding` symbol dependency
  - targeted validation: `pytest -q tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py` → `10 passed`
  - baseline re-cut confirms `AdminCredential` and `TeacherOnboarding` runtime symbol couplings are removed from `app/**`
- Landed invite-code decoupling slice:
  - `app/routes/system_admin.py` invite-code management now routes through `app/services/admin_identity_bridge_service.py`
  - `app/routes/admin.py` and `app/routes/system_admin.py` no longer carry `AdminInviteCode` symbol dependencies
  - targeted validation: `pytest -q tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py` → `11 passed`
  - baseline re-cut confirms `AdminInviteCode` runtime symbol couplings are removed from `app/**`
- Landed low-risk session principal key reduction slice on docs/main surfaces:
  - `app/routes/main.py` removed direct `session` fallback checks for `is_admin` / `admin_id` / `student_id` in home redirect flow; routing now uses explicit resolver checks (`get_current_admin`, `get_current_seat`)
  - `app/routes/docs.py` removed direct `admin_id` / `student_id` fallback checks in docs audience and user-role resolution paths; sysadmin context now requires both `is_system_admin` and `sysadmin_id`
  - `app/utils/helpers.py` `has_internal_docs_session()` now resolves internal-auth state through auth resolvers instead of direct `admin_id` / `student_id` key checks
  - targeted validation: `pytest -q tests/test_docs_platform_split.py tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py` → `18 passed`
  - guardrail confirms reductions:
    - `session_keys.admin_id` reduced from `app/routes/docs.py`, `app/routes/main.py`, `app/utils/helpers.py`
    - `session_keys.student_id` reduced from `app/routes/docs.py`, `app/routes/main.py`, `app/utils/helpers.py`
    - `session_keys.is_admin` reduced from `app/routes/main.py`
- Landed session principal key reduction slice on API/TLCP/sysadmin resolver surfaces:
  - added `get_current_system_admin()` in `app/auth.py` so sysadmin context is explicitly resolved (flag + id + row), not inferred from raw keys
  - `app/routes/api.py` no longer performs direct `is_admin` / `admin_id` / `is_system_admin` checks for `/api/set-timezone`; `/api/attendance/history` no longer falls back to raw `admin_id`
  - `app/services/tlcp.py` actor context now resolves student/admin/sysadmin identity through explicit auth helpers rather than direct principal-key checks
  - `app/__init__.py` maintenance bypass sysadmin detection and current-sysadmin template injection now use resolver-backed sysadmin context
  - targeted validation:
    - `python3 -m py_compile app/auth.py app/routes/api.py app/services/tlcp.py app/__init__.py` → pass
    - `pytest -q tests/test_tlcp_actor_context_resolution.py tests/test_timezone_fix.py tests/test_api_fixes.py tests/test_api_attendance_history.py tests/test_maintenance_bypass.py tests/test_docs_platform_split.py tests/test_admin_identity_bridge_service.py tests/test_recovery_bridge_service.py tests/test_wave3_identity_drop_surface_guardrail.py` → `41 passed`
  - guardrail confirms reductions:
    - `session_keys.admin_id` reduced from `app/routes/api.py`, `app/services/tlcp.py`
    - `session_keys.is_admin` reduced from `app/routes/api.py`, `app/services/tlcp.py`
    - `session_keys.is_system_admin` reduced from `app/__init__.py`, `app/routes/api.py`, `app/services/tlcp.py`
    - `session_keys.student_id` reduced from `app/services/tlcp.py`
- Adversarial rerun checkpoint (2026-05-25, clean seeded snapshot restore + full Phase 1 run):
  - DB reset and seed replay completed:
    - `bash scripts/adversarial/phase1_seed_and_snapshot.sh .env.redteam.local` → pass
    - `venv/bin/python scripts/adversarial/reset_db.py --snapshot-dir artifacts/adversarial/snapshots/seeded_base --database-url "$DATABASE_URL"` → pass
  - Harness compatibility fix landed:
    - `scripts/adversarial/inject_impossible_state.py` now selects an alternate class that does not collide on `(seat_id, class_id)` in `balance_cache`, avoiding `uq_balance_cache_seat_universe` failures during synthetic injection.
  - Full run outcome (`bash scripts/adversarial/run_phase1.sh`):
    - `cross_class_report.json` → `PASS (0)` unexpected + `expected_injection_count=1` (synthetic mismatch isolated)
    - `lineage_report.json` → `PASS (0)`
    - `runtime_attacks_report.json` → `PASS (0)`
    - rendered sanitized scorecard (`artifacts/adversarial/sanitized/current/scorecard_sanitized.md`) reflects:
      - `Cross-Class Isolation: PASS (0)`
      - `Lineage Verifier: PASS (0)`
      - `Runtime Session Attacks: PASS (0)`
      - `Synthetic Injection Step: PASS (0)`
- Landed Wave 5 balance-scope modernization slice (2026-05-25):
  - `app/services/balance_service.py` now exposes canonical batch APIs:
    - `get_batch_balances_by_class_seat(...)` keyed by `(class_id, seat_id)`
    - `get_batch_balances_by_student_class(...)` keyed by `(student_id, class_id)`
  - `app/routes/admin.py` dashboard/students/payroll/export balance batching no longer keys by `(student_id, join_code)` and now reads through class-scoped batching.
  - legacy `get_batch_balances(join_codes, student_ids)` compatibility wrapper has now been removed; admin/runtime callers are canonical-only.
  - targeted validation:
    - `pytest -q tests/test_admin_export_students_scoping.py tests/test_admin_payroll_scoped_balances.py` → `2 passed`
    - `pytest -q tests/test_admin_tenancy.py -k "student_listing_scoped_to_teacher or shared_student_accessible_to_multiple_teachers"` → `2 passed`
- Landed Wave 5 ledger table-consolidation slice (2026-05-26):
  - Added migration `migrations/versions/b1c2d3e4f5a6_rename_ledger_tables.py` to rename:
    - `transaction` → `ledger_transaction`
    - `balance_cache` → `ledger_balance_snapshot`
  - Updated runtime table bindings in `app/models.py` and related FK targets (`StudentItem.purchase_transaction_id`, `InsuranceClaim.transaction_id`, `Issue.related_transaction_id`, `IssueResolutionAction.related_transaction_id`) to `ledger_transaction`.
  - Updated lineage/audit table-name emissions to `ledger_transaction` in:
    - `app/services/ledger_service.py`
    - `app/utils/transaction_idempotency.py`
  - Preserved verifier compatibility for historical events by accepting both `transaction` and `ledger_transaction` in `app/utils/audit_verifier.py`.
- Updated lineage test fixtures to emit `table_name="ledger_transaction"` in `tests/test_audit_lineage.py`.
  - Validation:
    - `python3 scripts/lint_migrations.py migrations/versions/b1c2d3e4f5a6_rename_ledger_tables.py` → pass
    - `pytest -q tests/test_audit_lineage.py tests/test_admin_export_students_scoping.py tests/test_admin_payroll_scoped_balances.py` → `10 passed`
  - Historical local DB-chain blocker (now closed in Revision 13):
    - prior failure: `flask db upgrade` stopped at `a91cf11e8b2d` because legacy policy `teacher_isolation_policy` depended on `feature_settings.teacher_id`.
- Rule-compliance sweep checkpoint (2026-05-26):
  - Guardrail scans:
    - `python3 scripts/policy_guardrails.py --strict --no-waivers` → `Policy guardrails: clean`
    - `python3 scripts/wave3_identity_drop_surface_guardrail.py` → `clean (no expansion)`
  - FEAT registry coverage check:
    - Added missing registry entries used by active decorators: `FEAT-ANLY-001`, `FEAT-OBL-002` in `app/feats/base.py`
  - Time-helper guardrail alignment:
    - `app/services/audit_service.py` now normalizes datetimes through `ensure_utc(...)` (removed ad-hoc `replace(tzinfo=timezone.utc)`)
    - `app/utils/audit_verifier.py` comment text no longer trips `datetime.now` guardrail regex checks
  - Guardrail regression test bundle:
    - `pytest -q tests/test_v2_authority_guardrails.py tests/test_core_invariants_smoke.py tests/test_time_money_guardrails.py tests/test_wave3_identity_drop_surface_guardrail.py tests/test_tap_event_class_scope_invariant.py` → `39 passed`
  - FEAT lint sweep (`bash scripts/lint-feat-compliance.sh`) follow-on closure:
    - current result: `✅ SUCCESS: No FEAT Constitutional violations detected.`
    - additional closure slice:
      - wrapped remaining mutation helper/job surfaces with explicit FEAT shells and removed route-agnostic direct commits in the touched paths (`cli_commands`, `scheduled_tasks`, `attendance`, `issue_helpers`, `issue_categories`, `deletion`, `analytics_engine`)
      - retained verifier-system commit only under `system_audit_authority` and explicitly allowlisted in lint (`# FEAT-AUTHORIZED-SHELL`)
    - net result: direct-commit/direct-transaction hotspot debt from this lint rule is now cleared at current HEAD
  - INV-ARC-007 follow-on closure (2026-05-26):
    - removed dashboard-triggered mutation call from `GET /admin`:
      - deleted GET-side `auto_tapout_all_over_limit()` invocation in `app/routes/admin.py`
      - daily-limit enforcement remains available via scheduler + explicit POST endpoint `/admin/enforce-daily-limits`
    - validation:
      - `pytest -q tests/test_dashboard_rendering.py tests/test_backfill_transactions.py` → `16 passed`
      - `python3 scripts/policy_guardrails.py --strict --no-waivers` → clean
      - `bash scripts/lint-feat-compliance.sh` → clean

---

## Executive Summary

The v2 rebuild has delivered substantial, production-quality work in four distinct categories:

1. **FEAT execution infrastructure** — `FEATContext`, commit enforcement, registry, and `audit_protected()` audit chain are fully operational and wired at app boot.
2. **Class-scope and single-context authority** — request-level `join_code` class switching eliminated; session-authoritative context enforced; feature gating complete.
3. **Wave 4 class configuration canonicalization** — `FeatureSettings` fully cleaned; policy lineage live; rebalance activation is transition-native; analytics enrollment canonical.
4. **Dual-scope model hardening** — active legacy tables (`tap_events`, plus obligations/store legacy surfaces) enforce canonical class/seat scope, while Wave 5 ledger tables have now been renamed to canonical runtime names.

The first validation report's characterization of "0 of 44 canonical tables written at runtime" was imprecise. The more accurate picture: active runtime surfaces are progressively converging to canonical names (Wave 5 ledger rename now landed), and remaining legacy domains are dual-scoped with canonical columns enforced at the model level pending their wave-specific consolidations.

| Wave | Domain | Status | Revised Confidence |
|------|--------|--------|--------------------|
| 1 | Canonical Model Foundation | ✅ COMPLETE | High |
| 2 | Bootstrap Migration Squash | ✅ COMPLETE | High |
| 3 | Identity Domain (behavioral/routing) | ✅ COMPLETE (re-scoped) | High |
| 3 | Identity Domain (auth table drops / User activation) | ❌ DEFERRED | N/A |
| 4 | Class Configuration | ✅ COMPLETE | High |
| 5 | Ledger Domain | ⚠️ CODE + MIGRATION LANDED — full local upgrade validation blocked by prior chain issue | Medium–High |
| 6 | Attendance Domain | ⚠️ BEHAVIORAL ONLY — table rename/consolidation pending | Medium |
| 7 | Obligations Domain | ⚠️ BEHAVIORAL ONLY — canonical tables not yet used | Medium |
| 8 | Store Domain | ⚠️ BEHAVIORAL ONLY — canonical tables not yet used | Low–Medium |
| 9 | Operations + Interpretation | ⚠️ AUDIT CHAIN OPERATIONAL (non-canonical table) | Low |
| 10 | Support Domain | ❌ LEGACY SCOPE COLUMNS NOT CLEANED | Low |
| 11 | Post-Launch Completion | ⚠️ PARTIAL | Low |
| 12 | Final Validation | ❌ NOT STARTED | — |

**Current migration head:** `b1c2d3e4f5a6` (10 migrations, linear single-head chain ✅)  
**Tables in `models.py`:** ~60 ORM classes, ~66 table names total  
**Legacy tables dual-scoped with canonical columns:** Confirmed for `tap_events`, `hall_pass_logs` (ledger runtime tables now canonicalized as `ledger_transaction` / `ledger_balance_snapshot`)  
**Canonical table names live at runtime:** `classes` (renamed), `users`, `seats`, `ledger_transaction`, `ledger_balance_snapshot`, `feature_settings`, `policy_versions`, `policy_transitions`, `class_features`, `payroll_settings`, `rent_settings`, `banking_settings`, `hall_pass_settings`, `store_items`, `class_memberships`, `identity_profiles`  
**Active adversarial scorecard:** Latest full rerun (2026-05-25) reports Cross-Class Isolation `PASS (0)` (with 1 expected synthetic injection violation classified and excluded), Lineage Verifier `PASS (0)`, Runtime Session Attacks `PASS (0)`, and Synthetic Injection Step `PASS (0)`.

---

## Wave 1 — Canonical Model Foundation

### Status: ✅ COMPLETE (minor smoke test gap)

| Deliverable | Status | Notes |
|---|---|---|
| `app/models_canonical.py` with 44 ORM classes | ✅ EXISTS — 46 classes | `PolicyVersion` + `PolicyTransition` added in Wave 4; justified |
| `tests/domain/test_smoke.py` | ✅ EXISTS | Tests 44 hardcoded classes; does not include Wave 4 additions |
| `docs/archive/v1-development/tracking/V2_SCHEMA_GAP_AUDIT.md` | ✅ EXISTS | Complete table-by-table mapping |

### Gaps

- `test_smoke.py` asserts `len(models) == 44` against a hardcoded list that excludes `PolicyVersion` and `PolicyTransition`. The assertion passes but these two classes are not exercised.
- `models_canonical.py` canonical class bodies are minimal stubs (`id = sa.Column(sa.Integer, primary_key=True)`). This is correct for Wave 1 (reference definitions), but should be fully populated when each domain wave executes.

---

## Wave 2 — Bootstrap Migration Squash

### Status: ✅ COMPLETE

| Deliverable | Status | Notes |
|---|---|---|
| 196 legacy migrations archived | ✅ — exact count confirmed | `migrations/archive/v1_196_migrations/` |
| `migrations/archive/README.md` | ✅ | Correct date, prior head, file count |
| `migrations/versions/0001_bootstrap.py` with `down_revision = None` | ✅ | Root migration; uses `metadata.create_all(checkfirst=True)` for both model sets |
| `scripts/verify_migration_squash.py` | ✅ | Validates 44 canonical tables by name |
| Single migration head | ✅ | Chain: `0001 → 0002a → 3447255cb1af → 53e7c7148fea → 8357d4036478 → c4e36a4ab2f1 → d2f9f1d9be2e → f84c7ad2c1aa → a91cf11e8b2d → b1c2d3e4f5a6` |

### Gaps

- `verify_migration_squash.py` hardcodes head check for `0001`; stale since Waves 3–4 advanced the head. Treat as historical evidence only.
- Bootstrap uses `metadata.create_all(checkfirst=True)` rather than per-table `op.create_table()` + `table_exists()` guards per the migration standards doc. Functionally equivalent; no correctness issue.

---

## Wave 3 — Identity Domain

Wave 3 was re-scoped during execution from the full structural auth migration (activate `User`/`Seat`, drop legacy auth tables) to a behavioral/routing compliance pass. Both scopes are documented below.

### 3A: Routing Authority & Single-Context Enforcement (Re-scoped — Complete)

| Deliverable | Status | Evidence |
|---|---|---|
| `class_economies` → `classes` rename (`0002a`) | ✅ COMPLETE | 37 FK references updated; `ClassEconomy` model maps to `classes` table |
| Auth helpers: `get_current_seat()`, `get_current_class_id()`, `get_current_user()`, `require_seat_context()` | ✅ COMPLETE | `auth.py` lines 338–429 |
| Admin feature gating via `@admin_bp.before_request` | ✅ COMPLETE | `admin.py` lines 402–457; disabled → `admin_feature_disabled.html` |
| Student feature gating with hard `abort(404)` | ✅ COMPLETE | `student.py` lines 147–166; `STUDENT_FEATURE_ENDPOINTS` (10 routes) |
| Single-context: no request-level `join_code` class switching in admin/analytics | ✅ COMPLETE | `analytics.py` uses `resolve_current_class_context()`; admin context is session-authoritative |
| Route commit elimination: `student.py`, `analytics.py`, `system_admin.py`, `api.py` | ✅ COMPLETE | 0 `db.session.commit()` in all four files |
| Admin student detail uses active-class `Seat.public_id` navigation | ✅ COMPLETE | Numeric URLs return `404`; signed seat-public-ID URLs require teacher ownership, token class, and active `current_class_id` to resolve the same seat |
| Legacy claim flow: `join_code + first_name + last_name` (no DOB) | ✅ COMPLETE | `student.py:549–698`; dedupe code for name collisions |
| `last_active_class_id` on `User` model | ✅ COMPLETE | `models.py:192`; migration `8357d4036478` |
| `scripts/policy_guardrails.py` (10 rules, waiver system) | ✅ COMPLETE | Enforces: NO_ROUTE_COMMIT, WRITE_ON_GET, SCOPE_FALLBACK, TAP_NULL_SCOPE, AUDIT_UPDATE_DELETE, and 5 others |
| `.github/workflows/policy-guardrails.yml` | ✅ COMPLETE | PR mode (waivers allowed) + main branch strict mode |
| Test files: `test_feature_flag_enforcement.py`, `test_teacher_student_flow.py`, `test_class_context_and_switching.py`, `test_legacy_student_claim.py` | ✅ COMPLETE | All 4 exist; 28 of 28 tracker-claimed test files verified present |

### 3B: Structural Auth Migration (Original Plan — Deferred)

| Original Deliverable | Status |
|---|---|
| `User` activated as primary auth principal | ❌ NOT DONE — admin login resolves `Admin` model (via canonical teacher user); student login authenticates via `Student` model and then resolves the associated `User`/`Seat` through the onboarding flow; the bridge is fail-closed (returns `None` → session cleared → login rejected if no valid seat is found) |
| `0002_identity_domain.py` migration (drop legacy auth tables) | ❌ DOES NOT EXIST |
| Legacy tables dropped: `teachers`, `students`, `student_teachers`, `student_blocks`, `teacher_blocks`, `class_memberships`, `recovery_requests`, `student_recovery_codes`, `teacher_onboarding`, `passkey_credentials` | ❌ ALL STILL IN SCHEMA AND STILL USED |
| `tests/domain/test_identity.py` | ❌ DOES NOT EXIST |

### 3C: Remaining Routing Compliance Issues (Not Fully Closed)

These are pre-Wave-12 items but were tracked as Wave 3 cleanup targets:

**`join_code` as internal scope key in admin routes (INV-ARC-014 precursor):**  
Significant number of `filter_by(join_code=...)` and `filter(*.join_code ==...)` patterns remain in `admin.py` outside of pure session context reads. Examples:
- Line 982: `TeacherBlock.query.filter_by(join_code=join_code)`
- Lines 1040–1055: class deletion cleanup queries via `join_code`

The prior student-detail examples in this list are closed as of Revision 19: the route resolves a teacher-owned `Seat.public_id`, requires an active-class match, and uses the resolved `seat_id + class_id` scope for participant data.

**INV-ARC-014 — `block` as control key (not closed):**  
`RentSettings` still has `block = db.Column(db.String(10), nullable=True)` at line 1540 (despite `FeatureSettings.block` being dropped in Wave 4). Admin routes use `block` as a scope routing key in several places:
- `admin.py:4087`: `RentSettings.query.filter_by(class_id=class_id, block=current_block)`
- `admin.py:6337–6339`: `require_admin_feature_scope('rent', requested_block=block)` + `RentSettings.query.filter_by(..., block=block)`
- `admin.py:5237, 5351`: `block = request.form.get('block', '').strip()` — still accepts block from request
- `admin.py:973`: `requested_block=request.values.get('cwi_block') or request.values.get('block')`

`V2_CLASS_ID_INVARIANT_BACKLOG.md` explicitly tracks this as a deferred cleanup target: "Revisit settings models that still act like `teacher_id + block` is a durable ownership boundary."

**Wave 3 Exit Criterion 1 revisited:** The criterion states "No scope fallback paths in identity/scope-critical route surfaces." `get_current_seat()` in `auth.py` (lines 338–376) does fall back to `student_id`-based seat lookup when `seat_id` is not in session. **Precision correction (Rev 3):** This fallback is double-gated — it requires BOTH `student_id` (line 360) AND a `class_id`/`current_class_id` value (line 363) in session before attempting the lookup; if `class_id` is absent, the function returns `None` immediately (line 376) rather than falling back to an unscoped query. The fallback cannot produce a cross-class result. This makes it more defensible than the phrase "scope fallback" implies. That said, the canonical seat-first identity path (seat_id in session → direct lookup) is not fully enforced end-to-end, which is the root reason Wave 3B structural work is deferred.

---

## Wave 4 — Class Configuration

### Status: ✅ COMPLETE

All 13 claimed deliverables verified:

| Deliverable | Status |
|---|---|
| Analytics enrollment via `ClassMembership` by `class_id` | ✅ `analytics_engine.py:108–111` |
| `get_active_policy_mode_for_class(class_id)` | ✅ `economy_policy.py:602` |
| `get_analytics_policy(mode)` | ✅ `economy_policy.py:614` |
| `get_feature_settings_row_for_class(class_id)` | ✅ `economy_policy.py:565` |
| Analytics activity queries by `Transaction.class_id`, `TapEvent.class_id` | ✅ Multiple lines in `analytics_engine.py` |
| `Student.get_checking/savings_balance()` require `class_id + seat_id` (ValueError on missing) | ✅ `models.py:491, 498` |
| `PolicyVersion` + `PolicyTransition` in `models.py` + `models_canonical.py` | ✅ `models.py:2997–3054`; `models_canonical.py:64–71` |
| Migration `c4e36a4ab2f1_add_policy_lineage_tables.py` | ✅ Idempotent; correct FK wiring |
| `FeatureSettings.economy_pending_rebalance_json` dropped + migration `d2f9f1d9be2e` | ✅ Column absent; migration present |
| `FeatureSettings.teacher_id`, `.join_code`, `.block` dropped + migration `a91cf11e8b2d` | ✅ Columns absent; migration present |
| Legacy uniqueness constraint dropped + migration `f84c7ad2c1aa` | ✅ `class_id` is now `unique=True` |
| `activate_due_rebalances()` uses `policy_transitions` exclusively | ✅ `economy_rebalance.py:483` |
| Dual-write policy transitions for rebalance scheduling | ✅ `_create_policy_transitions_for_changes()` |

### Caveats

- `RentSettings` still has `teacher_id` (NOT NULL), `join_code`, and `block` columns — Wave 4 only cleaned `FeatureSettings`. The other settings tables (`rent_settings`, `banking_settings`, `payroll_settings`, `hall_pass_settings`) retain legacy scope columns. These are Wave 7, 6, and post-Wave work respectively.
- `StoreItem` model retains mandatory `teacher_id` (NOT NULL), with `class_id` optional — store scope migration is Wave 8.

---

## Wave 5 — Ledger Domain

### Status: ✅ TABLE CONSOLIDATION IMPLEMENTED + LOCAL UPGRADE VALIDATED THROUGH HEAD

The first validation report characterized this as "NOT STARTED." The deeper analysis reveals meaningful progress:

**What IS done:**

| Check | Finding |
|---|---|
| `Transaction` runtime table canonicalization | `Transaction.__tablename__ = 'ledger_transaction'` |
| `ledger_service.py` scope enforcement | `if not class_id or not seat_id: raise ValueError(...)` at service layer |
| All balance reads by `seat_id + class_id` | `get_posted_balance()`, `get_pending_balance_delta()` all scope by both fields |
| Services use `flush()` not `commit()` | Confirmed — commit delegated to FEAT context |
| `BalanceCache` runtime table canonicalization | `BalanceCache.__tablename__ = 'ledger_balance_snapshot'` |
| FEAT validates `seat_id + class_id` before any ledger write | `ledger_service.py:131–133` — FATAL ValueError if missing |
| Ledger table rename migration | `migrations/versions/b1c2d3e4f5a6_rename_ledger_tables.py` exists (idempotent rename guards) |
| Audit emissions aligned to new name | `audit_protected(... table_name='ledger_transaction' ...)` in ledger write paths |

**What is not fully validated yet:**

| Check | Status |
|---|---|
| Full end-to-end `flask db upgrade` on local redteam DB | ✅ PASS through `b1c2d3e4f5a6 (head)` after Revision 13 migration fix |
| Canonical stub models in `models_canonical.py` as runtime source | ❌ NOT APPLICABLE YET — runtime still uses `app/models.py` as the active ORM surface in this rebuild phase |
| `ClassEconomy` import in `ledger_service.py` | ⚠️ — functional alias to `classes`, but naming remains semantically noisy |

**Assessment:** Wave 5 table rename/consolidation is implemented in code and migration form, and local migration-chain validation now reaches `b1c2d3e4f5a6 (head)` cleanly.

---

## Wave 6 — Attendance Domain

### Status: ✅ COMPLETE FOR V2 RUNTIME CUTOVER (LEGACY TAP-EVENT AUDIT SURFACE RETAINED)

**What IS done:**

| Check | Finding |
|---|---|
| `TapEvent` dual-scope | `student_id` (NOT NULL — legacy), `seat_id` (nullable), `class_id` (nullable); enforcement hook mandates both seat_id + class_id on insert/update (raises `ValueError`) |
| `HallPassLog` dual-scope | `student_id` (NOT NULL), `seat_id` (nullable), `class_id` (nullable); legacy `teacher_id` column **removed** |
| INV-ARC-007: `GET /api/student-status` is read-only | ✅ |
| `POST /api/student-status/reconcile` exists, FEAT-wrapped | ✅ `api.py:2940` |
| Wave 3C.8 hall pass scope hardened | ✅ — class context required for mutation paths; fail-closed |
| `FEAT-ATTN-001`, `FEAT-ATTN-002` in FEAT registry | ✅ Both registered |
| `get_class_today_range()` and time helpers for class-local boundaries | ✅ `app/utils/time.py` |
| `get_session_status(...)` join_code/class scope ordering | ✅ Fixed in `app/attendance.py` (Revision 14) |
| Attendance/hall-pass daily boundary checks class-scoped | ✅ `app/routes/api.py` now uses `get_class_today_range(...)` / `get_class_now(...)` for class-local day windows |
| Stale hall-pass template API contracts removed | ✅ dead templates deleted (`hall_pass_terminal.html`, `hall_pass_queue.html`) |
| Attendance FEAT file in active runtime path | ✅ `app/feats/attendance.py` is imported by `app/routes/api.py` for tap/hall-pass/admin attendance mutations |
| `attendance_service.py` canonical runtime reads | ✅ now reads `AttendanceSession` + `SeatAttendanceState` for active-status/duration calculations |
| `AttendanceSession` / `SeatAttendanceState` runtime models | ✅ present in `app/models.py` and used by attendance suites |
| Wave 6 migration artifact | ✅ `migrations/versions/c6a8f6d1e2b3_create_attendance_sessions_and_state.py` (lint clean) |

**What is NOT done:**

| Check | Status |
|---|---|
| Legacy tap-entry audit/history API surface | ⚠️ Intentionally retained for admin history and soft-delete workflows (`/api/attendance/history`, `/api/admin/tap-entries/*`) |
| End-to-end DB upgrade validation through current head | ✅ Verified through `e4a2b7c9d1f0 (head)` with downgrade/re-upgrade cycle in this slice |

**Critical note on `TapEvent`:** Despite being the "legacy" table, it enforces mandatory `seat_id + class_id` via `before_insert`/`before_update` hooks. The enforcement is stricter than most other legacy tables — `TapEvent` **will raise a ValueError** if written without canonical scope. However, `student_id` remains mandatory (NOT NULL) as a legacy requirement, creating a dependency on the legacy `students` table that blocks full Wave 6 completion.

---

## Wave 7 — Obligations Domain

### Status: ⚠️ CANONICAL SCHEMA/PRIMARY WRITES LANDED — READ CUTOVER AND DROPS PENDING

**Behavioral contracts (locked per tracker "System Behavior Contracts" section):**

| Contract | Status | Evidence |
|---|---|---|
| Rent prepay cycle model with explicit `coverage_start_time`, `coverage_end_time` | ✅ IMPLEMENTED | `RentPayment` model has both columns |
| `cycle_idempotency_key` on rent payments | ✅ IMPLEMENTED | Column present |
| `has_received_rent_exemption` on `Seat` | ✅ IMPLEMENTED | Column present |
| Insurance waiting period: calendar-based, class-local midnight boundaries | ✅ IMPLEMENTED | `app/utils/time.py` helpers wired |
| Insurance eligibility evaluated against transaction timestamp (not current time) | ✅ IMPLEMENTED | Canonical rule enforced via shared helper |
| Rent execution class-scoped with deterministic idempotency | ✅ IMPLEMENTED | `rent_cycle_feat.py` exists; scheduler uses class-scoped entrypoints |
| `rent_cycle_feat.py` with FEAT shell | ✅ EXISTS | `app/feats/rent_cycle_feat.py` |
| All temporal logic uses `get_class_cycle_start_utc()`, `get_class_today_range()` | ✅ IMPLEMENTED | `app/utils/time.py:235–257` |

**Schema consolidation (Wave 7 formal deliverables):**

| Check | Status |
|---|---|
| `obligations_service.py` | ⚠️ Rent and insurance enrollment emit canonical assessment/lifecycle rows while compatibility writes remain |
| `AssessmentEvent`, `ObligationLifecycle`, etc. used at runtime | ✅ Runtime models map to `assessment_events` and `obligation_lifecycle` |
| `rent_payment_feat.py`, `insurance_claim_feat.py`, `insurance_purchase_feat.py` write to obligation canonical tables | ⚠️ Rent/enrollment canonical writes landed; insurance claim lifecycle cutover remains |
| Wave 7 migrations | ✅ `0006_obligations_domain.py` transitional layer plus `0007_obligations_schema_contract.py` canonical correction |
| Legacy obligation tables dropped | ❌ `rent_payments`, `rent_waivers`, `rent_items`, `insurance_policies`, `insurance_policy_blocks`, `student_insurance`, `insurance_claims` all still in schema |

---

## Wave 8 — Store Domain

### Status: ⚠️ PARTIAL SCOPE MIGRATION — TABLE CONSOLIDATION PENDING

**What IS done (tracker Wave 3C.9 work):**
- Store item resolution, pricing, purchase eligibility, and redemption-facing paths migrated from teacher-scoped to class-scoped filtering.
- Store mutations (create, edit, delete) wrapped in FEAT contexts with idempotency keys (confirmed at `admin.py:5571`, `5974`, `6023`).

**What is NOT done:**

| Check | Status |
|---|---|
| `store_service.py` | ❌ Still imports `RentItem, Student, StudentItem, TeacherBlock` (legacy tables) |
| `StorePurchase`, `RedemptionEvent`, `StoreItemVisibility` used at runtime | ❌ Stub-only in `models_canonical.py` |
| `StoreItem.teacher_id` dropped | ❌ Still `NOT NULL` — mandatory legacy scope anchor |
| `store_purchase_feat.py` writes to canonical tables | ❌ Writes to legacy `student_items` via `store_service` |
| Wave 8 migration (`0007_store_domain.py`) | ❌ DOES NOT EXIST |
| `student_items`, `store_item_blocks` dropped | ❌ Both still in schema |
| `identity_service.reconcile_rent_hall_pass_top_off()` | ❌ HYBRID — resolves Seat/User but writes to legacy `Student.hall_passes` and `StudentBlock.rent_hall_passes` |

---

## Wave 9 — Operations + Interpretation Domains

### Status: ⚠️ AUDIT CHAIN OPERATIONAL (non-canonical) — CANONICAL OPS TABLES NOT USED

This wave's picture is more nuanced than the first report indicated:

**What IS operational (but not on canonical DOM-OPS-001 tables):**

The `audit_events` / `chain_heads` / `integrity_status` tables form a **cryptographic tamper-evident audit chain** added via migration `3447255cb1af`. This is architecturally distinct from the DOM-OPS-001 canonical `audit_log` table — it provides HMAC-chained lineage verification, sequence numbers, and genesis-seeded chain heads. Key properties:
- `AuditEvent` model — 22-column cryptographic record with `hmac_signature`, `previous_hash`, `event_hash`, `sequence_number`
- `audit_protected()` in `base.py:333–375` writes to `audit_events` after every ledger mutation
- `audit_service.emit_audit_event()` enforces FEAT context before writing
- The lineage chain is **live and writing** — every `Transaction` write triggers an audit event and populates `transaction.lineage_event_id` + `transaction.lineage_token`

**Gap vs DOM-OPS-001:** The canonical `audit_log` table (a simpler operational log) does NOT receive writes — `base.py`'s `audit_protected()` targets `audit_events`, not `audit_log`. The canonical `OperationalEvent`, `IncidentEvent`, etc. are entirely unused stubs.

**Additional non-canonical tables not in DOM-CORE-002:**
- `economy_snapshot` — immutable analytics snapshot per class (live; written by admin route at line 2107)
- `payroll_cache` — performance optimization cache per class (live; class-scoped)
- `redemption_audit_logs` — domain-specific audit trail for store redemptions (live; class + seat scoped)

These serve legitimate purposes and are class_id-scoped, but they are additions outside the 44-table target.

| Check | Status |
|---|---|
| Cryptographic audit chain (`audit_events`, `chain_heads`, `integrity_status`) | ✅ OPERATIONAL — migration `3447255cb1af`; writes live |
| `AuditLog` (canonical DOM-OPS-001 `audit_log`) used at runtime | ❌ UNUSED — stub only |
| `OperationalEvent`, `IncidentEvent`, etc. used at runtime | ❌ ALL UNUSED stubs |
| Wave 9 migration (`0008_operations_domain.py`) | ❌ DOES NOT EXIST |
| Legacy observability tables dropped (`actor_request_trace`, `error_events`, `error_logs`, `analytics_alerts`, `user_reports`) | ❌ ALL STILL IN SCHEMA |
| `InterpretationSnapshot`, `InterpretationAnnotation` used at runtime | ❌ UNUSED stubs |
| Wave 9 interpretation migration (`0009_interpretation_domain.py`) | ❌ DOES NOT EXIST |
| `analytics_snapshots`, `analytics_events` (legacy) dropped | ❌ STILL IN SCHEMA |

Runtime note: rent-waiver add/remove flows no longer emit `analytics_events`
compatibility rows. The table remains only as the broader legacy analytics
surface until a seat-scoped analytics schema replaces it.

---

## Wave 10 — Support Domain

### Status: ❌ LEGACY SCOPE COLUMNS NOT CLEANED

| Check | Status |
|---|---|
| `Issue.join_code` column | ❌ STILL PRESENT AND MANDATORY (`NOT NULL`, line 2436) |
| `Issue.teacher_id` column | ❌ STILL PRESENT AND MANDATORY (`NOT NULL`, line 2433) |
| `Issue.class_id`, `Issue.seat_id` | ✅ PRESENT but optional (nullable) |
| `announcement` table legacy columns | ❌ Not audited in this pass; likely similar |
| Wave 10 migration (`0010_support_domain.py`) | ❌ DOES NOT EXIST |

**Canonical support classes in `models_canonical.py`** map to the same table names as legacy models — there's no actual divergence to reconcile, only column cleanup needed.

---

## Wave 11 — Post-Launch Completion

### Status: ⚠️ PARTIAL

| Deliverable | Status |
|---|---|
| Adversarial harness (13 scripts in `scripts/adversarial/`) | ✅ COMPLETE |
| Sanitized evidence export protocol | ✅ COMPLETE |
| Phase 1 adversarial scorecard — claimed PASS (2026-05-14) | ⚠️ SEE NOTE BELOW |
| INV-ARC-007: `GET /api/student-status` split into GET + `POST /reconcile` | ✅ COMPLETE |
| INV-ARC-007: GET-path snapshot commit | ✅ RESOLVED — `_get_frozen_economy_analysis_payload()` commit was guarded by `persist_snapshot=True` and only reachable from the POST route, not any GET handler; confirmed fully non-GET-path from the start. INV-ARC-007 fully closed. |
| FEAT bypass: `api_economy_analyze()` not FEAT-wrapped | ✅ RESOLVED — Post-report update (2026-05-24): `@feat_shell("FEAT-ADMN-001")` added at `admin.py:12020`; `_get_frozen_economy_analysis_payload()` replaced `db.session.commit()` with `flush()`; FEAT context owns the commit. Zero `db.session.commit()` remain in `admin.py`. |
| `admin.py` decomposition into sub-blueprints | ❌ NOT DONE — 12,862 lines; no `admin_roster.py`, `admin_finance.py`, etc. exist |
| Backup/restore rehearsal | ❌ NOT DONE |
| Operator sign-off flow (`user_invite_tokens`) | ❌ NOT DONE |
| Sysadmin audit (INV-ARC-011 phantom scope) | ❌ NOT DONE |
| `V2_CLASS_ID_INVARIANT_BACKLOG.md` items closed | ❌ ALL OPEN — explicitly deferred to post-launch |
| Full-repo INV-ARC-015 sweep documentation | ❌ NOT DONE |
| INV-ARC-014 full sweep (`block`/`period`/`section` as control keys) | ❌ NOT DONE — multiple `block`-as-scope-key usages confirmed in admin routes |

### ✅ Adversarial Scorecard Discrepancy Resolved

**Tracker claims (2026-05-14):** Cross-Class Isolation PASS(0), Lineage Verifier PASS(0), Runtime Attacks PASS(0).  
**Artifact file (`artifacts/adversarial/sanitized/current/scorecard_sanitized.md`, generated 2026-05-15):**

| Check | Status | Violations |
|---|---|---:|
| Cross-Class Isolation | **FAIL** | 1 |
| Lineage Verifier | **FAIL** | 5 |
| Runtime Session Attacks | PASS | 0 |
| Synthetic Injection Step | PASS | 0 |

The scorecard was generated the day after the tracker's claimed PASS. The Wave 4 work (May 20–24) occurred after this scorecard, so Wave 4 changes are not the cause. Possible explanations:
1. The scorecard was run against a post-injection database state (injected cross-class data was not cleaned before the run).
2. A regression was introduced between the May 14 PASS run and the May 15 scorecard generation.
3. The lineage verifier (5 failures) may reflect transactions created outside the audit chain (pre-lineage rows from legacy test data).

Resolution update (2026-05-25):
1. Restored clean seeded snapshot baseline and reran full Phase 1 harness.
2. Added seeded baseline normalization for stale `balance_cache` class/seat mismatches in `seed_phase1_minimal.py`.
3. Patched synthetic injector alternate-class selection in `inject_impossible_state.py` to avoid uniqueness collisions.

Current result from `artifacts/adversarial/sanitized/current/scorecard_sanitized.md`: PASS on Cross-Class Isolation, Lineage Verifier, Runtime Session Attacks, and Synthetic Injection Step.

---

## Wave 12 — Final Validation

### Status: ❌ NOT STARTED

| Gate | Required | Current |
|---|---|---|
| Exactly 44 canonical tables | 44 | ~66 table-owning ORM classes (40+ legacy + non-canonical additions) |
| `models.py` re-exports only | Yes | Still defines all legacy model classes |
| Clean `User`/`Seat` auth path | Yes | `Admin`/`Student` still primary; `User`/`Seat` supplementary |
| 0 failing tests | 0 | ~123 failing (per plan baseline; not re-measured) |
| All domain tests in `tests/domain/` | Yes | Only `test_smoke.py` exists |
| Zero `*.student_id` scope filters in routes | 0 | Many remain (legitimate during transition) |

---

## FEAT Layer Compliance — Detailed

The FEAT execution layer is the most thoroughly completed component. Revised assessment:

| Check | Status | Evidence |
|---|---|---|
| `FEATContext` class with commit ownership | ✅ COMPLETE | `base.py:107–244` |
| `feat_shell()` decorator for legacy-wrapped routes | ✅ COMPLETE | `base.py:392–425` |
| `FEATContextError` on unauthorized flush/commit | ✅ COMPLETE | `before_flush` + `before_commit` hooks at app boot |
| `init_feat_enforcement(app)` called at boot | ✅ COMPLETE | `app/__init__.py` |
| FEAT registry with all domain codes | ✅ COMPLETE | LED-001/002/003/004, IDEN-001/002, STOR-001/002/003/004/005, ATTN-001/002, ADMN-001, OBL-001 |
| **Services use `flush()`; FEAT owns `commit()`** | ✅ VERIFIED | `ledger_service.py:148, 227` flush; FEAT context `__exit__` commits |
| Store mutations (create, edit, delete) FEAT-wrapped | ✅ VERIFIED | `admin.py:5571` (FEAT-STOR-001), `5974` (FEAT-STOR-001), `6023` (FEAT-STOR-003) |
| Banking settings update FEAT-wrapped | ✅ VERIFIED | `admin.py:10910` (FEAT-ADMN-001) |
| `db.session.commit()` in `student.py`, `analytics.py`, `api.py`, `system_admin.py` | ✅ 0 violations | Confirmed |
| `db.session.commit()` in `admin.py` | ✅ 0 violations | Post-report update (2026-05-24): `@feat_shell("FEAT-ADMN-001")` added to `api_economy_analyze()` at `admin.py:12020`; `admin.py:2107` is now `.first()` read — commit replaced by flush under FEAT ownership. Violation type was FEAT bypass (POST path), not GET-path (INV-ARC-007 was never violated). |
| `audit_protected()` writes to cryptographic chain | ✅ FUNCTIONAL | Targets `audit_events` table (lineage chain), not canonical `audit_log` |
| Transaction enforcement hook mandates FEAT context | ✅ `models.py:903–1062` — `FEATContextError` if ledger mutation outside FEAT |

**Architecture clarification on `audit_protected()`:** The function writes to `audit_events` (the cryptographic HMAC chain added by migration `3447255cb1af`) — not to the DOM-OPS-001 canonical `audit_log` table. Both exist, but only `audit_events` is live. This means the lineage chain is operational but the canonical operations domain is not.

---

## Schema State Audit — Revised

### Current table distribution in `app/models.py` (~66 table-owning classes)

**Canonical tables LIVE at runtime (survive to v2 target state):**  
`users`, `seats`, `classes` (was `class_economies`), `ledger_transaction`, `ledger_balance_snapshot`, `identity_profiles`, `class_features`, `feature_settings` (fully cleaned), `hall_pass_settings`, `payroll_settings`, `payroll_rewards`, `payroll_fines`, `rent_settings`, `banking_settings`, `hall_pass_logs`, `store_items`, `class_memberships`, `issues`, `issue_status_history`, `issue_resolution_actions`, `ticket_correlation_pack`, `issue_categories`, `announcements`, `policy_versions`, `policy_transitions`

**Dual-write or compatibility tables still active:**
`tap_events` → target: `attendance_sessions` + `seat_attendance_state`
`rent_payments` (w/ coverage_start/end + idempotency_key) → canonical
`assessment_events` + `obligation_lifecycle` writes landed; legacy reads remain
`student_insurance` → canonical enrollment assessment/lifecycle write landed;
legacy reads remain
`insurance_claims` → canonical lifecycle migration remains

**Pure legacy tables (used in active write paths, targeted for drop in Waves 5–10):**  
`student_items`, `store_item_blocks` (Wave 8)  
`rent_waivers`, `rent_items`, `insurance_policies`, `insurance_policy_blocks` (Wave 7)  

**Legacy auth tables (deferred Wave 3 structural drops):**  
`teachers`, `students`, `teacher_blocks`, `student_teachers`, `student_blocks`, `recovery_requests`, `student_recovery_codes`, `passkey_credentials`, `teacher_onboarding`, `teacher_invite_codes`

**Legacy observability tables (targeted for drop in Wave 9):**  
`analytics_alerts`, `analytics_snapshots`, `analytics_events`, `actor_request_trace`, `error_logs`, `error_events`, `user_reports`

`analytics_events` no longer receives rent-waiver writes; it remains only for
other legacy analytics annotations pending the seat-scoped analytics cutover.

**Non-canonical additions with legitimate operational purpose (not in DOM-CORE-002 44-table target):**  
`audit_events` — cryptographic HMAC-chained audit lineage (live, actively written)  
`chain_heads` — audit chain head tracking (live, seeded)  
`integrity_status` — nightly verifier status (live, seeded)  
`economy_snapshot` — immutable analytics snapshot (live, written by admin route)  
`payroll_cache` — performance cache (live, class-scoped)  
`redemption_audit_logs` — store redemption audit trail (live, class + seat scoped)

---

## INV-ARC Compliance Summary

| Invariant | Status | Notes |
|---|---|---|
| **INV-ARC-007** (no write-on-GET) | ✅ FULLY CLOSED | No GET-path commits remain. `admin.py:2107` was only reachable from POST route — INV-ARC-007 was never violated at that site. GET/POST reconcile split complete at `api.py:2940` (`def reconcile_student_status` at `api.py:2943`). |
| **FEAT bypass** (POST `/api/economy/analyze`) | ✅ RESOLVED | Post-report update (2026-05-24): `@feat_shell("FEAT-ADMN-001")` added at `admin.py:12020`; `db.session.commit()` replaced with flush. Zero bare commits remain in `admin.py`. |
| **INV-ARC-014** (no label-based routing) | ❌ NOT CLOSED | `block` still used as scope key in `RentSettings` queries and admin route scope resolution; tracked in `V2_CLASS_ID_INVARIANT_BACKLOG.md` |
| **INV-ARC-015** (class-local time everywhere) | ✅ SUBSTANTIALLY COMPLETE | All critical paths (rent, insurance, attendance, analytics) use class-local time helpers |
| **INV-CORE** (FEAT-only mutation) | ✅ ENFORCED RUNTIME | Before-flush/before-commit hooks active; no remaining route-level commits in admin/student/analytics/api/system_admin route surfaces. |
| **INV-ARC-011** (phantom scope access) | ❌ NOT AUDITED | Wave 11 sysadmin audit not done |
| **INV-ARC-013** (archived class behavior) | ❌ NOT DEFINED | Class lifecycle not yet specified |

---

## Corrections to First Validation Report

The first report contained several characterizations that this deeper analysis revises:

1. **"Canonical tables written at runtime: 0 of 44"** — Revised to: Active legacy tables are dual-scoped with canonical columns (`seat_id`, `class_id`) enforced at model level. Wave 5 ledger table names are now canonicalized; remaining rename/consolidation work is concentrated in Waves 6–10.

2. **Wave 5 as "NOT STARTED"** — Revised to: table consolidation now landed in code/migration (`transaction` → `ledger_transaction`, `balance_cache` → `ledger_balance_snapshot`) with targeted validation passing; remaining risk is local migration-chain blockage before the new migration is reached.

3. **Wave 9 as "infrastructure only"** — Revised to: "Cryptographic audit chain fully operational on `audit_events` (non-canonical table). DOM-OPS-001 canonical tables are unused stubs."

4. **Adversarial scorecard status (Revision 5 closure)** — First report characterized it as PASS, while the 2026-05-15 artifact showed FAIL. A full rerun on 2026-05-25 against regenerated seeded baseline now passes: Cross-Class `PASS(0)` with 1 expected synthetic injection violation classified separately, Lineage `PASS(0)`, Runtime `PASS(0)`.

5. **FEAT atomicity model** — First report did not distinguish FEAT-commits vs service-flushes. The correct model is confirmed: FEAT context owns the commit; services only flush. This is working correctly.

6. **Student login auth bridge (Revision 3)** — Second report stated student login "resolves `Student` model" without capturing the post-auth bridge. The precise flow was: `Student` model authenticates the PIN, then the onboarding flow resolves `User`/`Seat`. The bridge was fail-closed: if no valid seat is found, the session is cleared and login is rejected rather than proceeding with a legacy-only session.

7. **`get_current_seat()` fallback precision (Revision 3)** — Second report described this as "falls back to `student_id`-based seat lookup" without capturing the double-gating. The fallback actually requires `class_id` also present in session (lines 363–374 in `auth.py`). A `student_id`-only session cannot use the fallback path; it returns `None` at line 376. Cross-class seat resolution via this path is not possible.

8. **`balance_service.py` interface gap (Revision 7 closure)** — The earlier gap remains closed for active call paths: `balance_service.py` exposes canonical batching (`(class_id, seat_id)` and `(student_id, class_id)`), admin route consumers were migrated off `(student_id, join_code)` batching, and the legacy `get_batch_balances(join_codes, student_ids)` wrapper was removed. Follow-on Wave 5 table consolidation has now also landed (Revision 8).

9. **INV-ARC-007 / FEAT violation reclassification and closure (Revision 4)** — Prior versions mischaracterized the `admin.py:2107` commit as a "GET-path write (INV-ARC-007)." Code inspection confirms the commit was inside `_get_frozen_economy_analysis_payload()` guarded by `persist_snapshot=True`, and the only caller passing that flag was the POST route `api_economy_analyze()`. The GET `economy_health` route never triggers the commit branch — INV-ARC-007 was never violated at this site. The actual issue was a FEAT bypass on the POST endpoint. Per the post-report update (2026-05-24), this FEAT bypass is also now resolved: `@feat_shell("FEAT-ADMN-001")` added at `admin.py:12020`, commit replaced with flush. All FEAT and INV-ARC-007 items are fully closed with 0 `db.session.commit()` remaining in `admin.py`.

---

## Recommended Next Steps (Updated Priority Order)

1. ~~**Re-run adversarial harness against clean seeded state**~~ — **RESOLVED** (2026-05-25): full Phase 1 rerun now PASS; cross-class unexpected violations cleared, expected synthetic injection classified, lineage PASS, runtime PASS.

2. ~~**Wrap `/api/economy/analyze` in a FEAT context**~~ — **RESOLVED** (2026-05-24): `@feat_shell("FEAT-ADMN-001")` added at `admin.py:12020`; `_get_frozen_economy_analysis_payload()` commit replaced with flush. Zero bare commits remain in `admin.py`. All FEAT and INV-ARC-007 items are now closed.

3. ~~**Resolve prior migration-chain blocker and re-run full upgrade validation**~~ — **RESOLVED** (2026-05-27): `a91cf11e8b2d` now drops dependent legacy policy state before `teacher_id` removal; `flask db upgrade` reaches `b1c2d3e4f5a6 (head)`.

4. ~~**Execute final Wave 6 table cutover tasks**~~ — **RESOLVED** (2026-05-30): payroll/admin batch attendance reads now use canonical sessions; daily-limit batch helper no longer writes legacy tap rows; `TapEvent.student_id` made nullable with migration `e4a2b7c9d1f0`; DB downgrade/re-upgrade validated through current head.

5. ~~**Update `test_smoke.py`**~~ — **RESOLVED**: `PolicyVersion` and `PolicyTransition` added to canonical list and assertion bumped to 46.

6. **Close INV-ARC-014 (`block` as routing key)** — `RentSettings.block` column needs to be resolved to `class_id` alone. Tracked in `V2_CLASS_ID_INVARIANT_BACKLOG.md`.

7. **Complete Wave 7 (Obligations)** — canonical schema and primary rent/enrollment
   writes are landed; migrate insurance claims, cut remaining reads, validate
   parity, then drop transitional and legacy tables.

8. **Execute Waves 8–10** in sequence (Store → Operations/Interpretation → Support).

9. **Wave 3 structural completion** — activate `User`/`Seat` as the primary auth path and drop legacy auth tables. This is the largest architectural debt item.

10. **Complete per-domain test files** in `tests/domain/`; obligations now has
    `test_obligations.py`, while remaining domain coverage must be audited
    against the current files.

11. **Decompose `admin.py`** (Wave 11) — 12,862 lines is the single largest maintenance liability.

---

*This report (Revision 19) supersedes all prior versions. Revision 4 corrected the FEAT/INV-ARC-007 misclassification on `admin.py:2107`. Revision 5 closed the adversarial rerun uncertainty with fresh 2026-05-25 evidence and full Phase 1 PASS. Revision 6 added a Wave 5 major slice for canonical balance batching and admin-surface migration. Revision 7 completed that sub-slice by removing the legacy `get_batch_balances(join_codes, student_ids)` wrapper and confirming canonical-only call paths via targeted regression validation. Revision 8 landed Wave 5 ledger table consolidation (`ledger_transaction` / `ledger_balance_snapshot`) and recorded the remaining local migration-chain blocker prior to full upgrade validation. Revision 9 added a rule-compliance sweep checkpoint, closed missing FEAT registry entries for active decorators, aligned time-helper guardrail compliance paths, and reduced FEAT lint hotspots from 13 to 11. Revision 10 closed the remaining FEAT-lint commit/construction hotspots in touched utility/job paths and recorded a clean FEAT constitutional lint result at current HEAD. Revision 11 removed dashboard-triggered write-on-GET auto-tapout behavior, keeping daily-limit enforcement on scheduler and explicit POST path only. Revision 12 closed the Postgres test-db rebuild race in `tests/conftest.py`, restored class-scoped daily-limit lookup in `enforce_daily_limits()`, and validated the full admin-tenancy slice (`12/12` passing). Revision 13 closed the local migration-chain blocker at `a91cf11e8b2d` by dropping dependent legacy RLS policy state before legacy scope-column removal and confirmed full upgrade to `b1c2d3e4f5a6 (head)`. Revision 14 applied attendance Step-1/Step-2 runtime hardening and FEAT ownership expansion across hall-pass/tap mutation paths. Revision 15 closed remaining hall-pass admin mutation FEAT coverage (`/hall-pass/settings` POST, `/hall-pass/setup` POST, `/hall-pass/verify-token/rotate` POST) and re-validated attendance/hall-pass tenancy suites. Revision 16 removed transitional attendance mirror behavior and locked this slice to canonical `attendance_sessions` + `seat_attendance_state` paths. Revision 17 reconciled stale Wave 6 tracker claims to live runtime evidence. Revision 18 closes the final Wave 6 cutover tasks by migrating payroll/admin batch attendance reads to canonical sessions, removing direct legacy tap-event writes from batch daily-limit helper flows, and eliminating hard `TapEvent.student_id` dependency with migration and downgrade/re-upgrade validation through `e4a2b7c9d1f0 (head)`. Revision 19 closes the teacher-facing student-detail URL boundary by requiring active-class `Seat.public_id` resolution and recording adversarial cross-teacher and same-teacher cross-class regressions.*
