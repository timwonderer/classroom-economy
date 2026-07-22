# Productivity and Payroll Reconstruction Stocktake

| Reference Number | Version | Date | Scope |
|---|---:|---|---|
| PROD-PAYROLL-STOCKTAKE-2026-07-20 | 0.2 | 2026-07-21 | Productivity and Payroll only |

---

## I. Purpose

This stocktake records the current state of the Productivity and Payroll domain reconstruction and template-driven wiring effort.

The template audits remain the authoritative checklist. `MAP-UI-001` is a convenience map; a PROD surface is not complete until the corresponding template audit item is explicitly rewired, removed, collapsed, or otherwise disposed.

This document tracks:

- what has been wired;
- what has been removed or collapsed;
- what remains before PROD can be considered complete;
- what evidence currently supports the checkpoint.

PROD scope is limited to productivity sessions, hall-pass consumption/approval
records, and payroll business events. Obligation satisfaction, including rent,
remains OBL-owned. If satisfying an obligation grants a hall pass or another
item, that grant is entitlement-domain business; PROD only participates later
when an approved hall pass is consumed into `hall_pass_logs` or when
`attendance_sessions` changes. When PROD records approved hall-pass
consumption, `hall_pass_logs.correlation_id` must reuse the consumed entitlement
grant's `correlation_id`; PROD must not generate a new unrelated hall-pass
correlation.

---

## II. Authoritative Inputs

### Domain and FEAT Authority

- `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-001_RECORD_ATTENDANCE_SESSION.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-002_RECORD_HALL_PASS_LOG.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-003_RECORD_PAYROLL_EVENT.md`

### Shared Runtime Authority

- `docs/SPEC/SPEC-TIME-001_CANONICAL_TEMPORAL_RESOLVER.md`
- `app/utils/canonical_temporal_resolver.py`
- `app/utils/display_metadata.py`

### Wiring Checklists

- `docs/TRACKING/TEMPLATE_AUDIT_ADMIN_E-P.md`
- `docs/TRACKING/TEMPLATE_AUDIT_STUDENT.md`
- `docs/TRACKING/TEMPLATE_INTERFACE_AUDIT_2026-07-19.md`
- `docs/TRACKING/TEMPLATE_ROUTE_AUDIT_ADMIN_AND_ANALYTICS.md`
- `docs/TRACKING/TEMPLATE_ROUTE_AUDIT_ADMIN_AND_SHARED.md`
- `docs/TRACKING/TEMPLATE_ROUTE_AUDIT_SYSADMIN_AND_SHARED.md`
- `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md`

---

## III. Built / Wired This Checkpoint

| Surface / Capability | Current Disposition | Evidence |
|---|---|---|
| Canonical temporal resolver | `BUILT` | `SPEC-TIME-001` replaces the historical temporal rebuild plan; PROD FEAT/read paths touched in this slice import `canonical_temporal_resolver`. |
| Display metadata resolver | `BUILT` | `display_metadata` resolves display-only identity/class metadata from `CanonicalContext`; it is not authority. |
| FEAT-PROD registry | `BUILT` | `FEAT-PROD-001`, `FEAT-PROD-002`, and `FEAT-PROD-003` are registered. |
| PROD FEAT module | `BUILT_FOR_CURRENT_SLICE` | `record_attendance_session`, `record_hall_pass_log`, `record_payroll_event`, and `record_payroll_reversal` exist and are used by the wired route surfaces. |
| Ephemeral hall-pass queue | `BUILT` | Pending hall-pass requests are process-local workflow state. Reject/cancel writes no PROD truth; approval commits through `FEAT-PROD-002`. |
| Student dashboard productivity state | `REWIRED_READ` | Template no longer dereferences `student.display_first_name` or `student.hall_passes`; route supplies display metadata and canonical attendance projection. |
| Student dashboard work controls | `REWIRED` | Button set is `Start Work`, contextual `Break`, `Leave`, and `Return`; Done for day writes `inactive/done_for_day` through `FEAT-PROD-001`. |
| Student payroll page | `REWIRED_READ` | Route/template use canonical `attendance_sessions`, `PayrollEvent`, and canonical temporal elapsed-duration evaluation. |
| Admin payroll dashboard | `REWIRED_READ` | Recent payrolls, history, last-payroll stats, and earned totals derive from `PayrollEvent` plus Ledger amount lookup by `correlation_id`. |
| Admin run payroll | `REWIRED` | Teacher clicking Run Payroll records `payroll` events through `FEAT-PROD-003`; it no longer uses `FEAT-LED-004` / `execute_admin_adjustments`. |
| Admin manual credit | `REWIRED` | Direct teacher-to-student money send records `manual_credit` through `FEAT-PROD-003`; manual debits/fines are outside PROD. |
| Admin payroll history | `REWIRED` | Route reads `PayrollEvent`, derives class-local filters through the canonical temporal resolver, and template consumes dict rows. |
| Admin hall-pass page | `REWIRED` | Pending rows come from the ephemeral queue; approval writes `hall_pass_logs`; issued/out state derives from `hall_pass_logs` plus latest `attendance_sessions`. |
| Admin dashboard pending hall-pass panel | `REWIRED_READ` | Pending pass count/list now read from the ephemeral queue, not `hall_pass_logs`. |
| Scheduled daily-limit enforcement | `REWIRED` | Scheduler-only `enforce_daily_limits_job` reads active `attendance_sessions`, groups by `class_id`, resolves class daily limit, closes sessions through `FEAT-PROD-001` with teacher authority and `mechanism=system`, and uses `canonical_temporal_resolver` for elapsed-duration and exact close timestamp calculation. |
| Hall-pass leave/return | `REWIRED` | Leave/return append `attendance_sessions` rows through `FEAT-PROD-001`; `hall_pass_logs` are not mutated for lifecycle state. |
| Attendance helper regression tests | `REWIRED_TEST` | `tests/dom/attendance/test_attendance.py` now uses current DOM-PROD `AttendanceSession` and `PayrollEvent` shapes, writes attendance rows through `FEAT-PROD-001`, and verifies payroll anchors from `payroll_event` rather than legacy Ledger `Transaction.type`; focused test now passes. |
| Public hall-pass verification | `REWIRED_READ` | Public token resolves teacher-scoped read authority; class dropdown submits `class_id`; name lookup checks seat hashed names and displays `IdentityProfile` only after unique match. |
| Admin attendance log | `REWIRED_READ` | `/api/attendance/history` reads append-only `AttendanceSession` fields and uses `canonical_temporal_resolver` for class-local filters. |
| Admin roster bulk Start Work / Break | `REWIRED` | `admin.tap_in_students` / `admin.tap_out_students` call `record_attendance_session` and submit only `seat_ids`; no block or period scope is submitted. |
| Student detail PROD sections | `REWIRED_READ` | Attendance summary/history, hall-pass balance, join-code display, and Payroll tab are rewired; Payroll tab reads `payroll_event` rows plus Ledger amount lookup by `correlation_id`, not legacy `Transaction.type` filters. |
| Admin payroll page class-scope contract | `REWIRED_READ_WRITE` | `admin_payroll.html` no longer exposes block-shaped template filters or reads `Seat.block`; history and manual-credit selection use canonical `class_id` view rows while Run Payroll and manual credit remain wired through `FEAT-PROD-*`. |
| Student payroll page class-scope contract | `REWIRED_READ` | `student_payroll.html` no longer receives block-keyed maps; it renders the active canonical class through `class_label`, `payroll_state`, `unpaid_seconds`, `projected_pay`, and canonical `attendance_events`. |
| Analytics participation PROD read | `REWIRED_READ` | `AnalyticsEngine.calculate_participation_rate` now reads canonical `AttendanceSession.target_seat_id` and `timestamp`; legacy `seat_id`, `started_at`, and `is_deleted` assumptions were removed. |
| Student removal PROD cleanup | `REWIRED_DELETE` | Teacher-scoped student removal deletes PROD rows by target `seat_id` constrained to the seat's `class_id`; whole-class deletion remains scoped by `class_id` only. Cleanup targets `attendance_sessions.target_seat_id`, `hall_pass_logs.requested_by_seat_id`, and `payroll_event.target_seat_id`. |
| Class destruction PROD cleanup | `REWIRED_DELETE` | Whole-class deletion deletes the full PROD table set by `class_id`: `attendance_sessions`, `hall_pass_logs`, and `payroll_event`. Stale `TapEvent` cleanup is removed from the class-collapse path. |
| Hall-pass model transition hook | `REMOVED` | The obsolete `HallPassLog` listener that tried to populate legacy `student_id`/`seat_id` transition fields was removed; v2 writes must provide `requested_by_seat_id`, `approved_by_seat_id`, `class_id`, and `correlation_id` directly through `FEAT-PROD-002`. |
| API FEAT boundary labels for hall-pass/productivity surfaces | `REWIRED` | Live API surfaces no longer expose `FEAT-ATTN-*` wrappers or `student_tap` idempotency prefixes. Hall-pass settings mutation is explicitly labeled as Class Configuration through `FEAT-SETTINGS-001`; PROD attendance and hall-pass writes continue through `FEAT-PROD-*` command helpers. |

---

## IV. Removed / Collapsed This Checkpoint

- Deleted `hall_pass_verification.html` after public verification collapsed to `hall_pass_verify.html`.
- Deleted the historical temporal rebuild plan after replacing it with `SPEC-TIME-001`.
- Removed old hall-pass lifecycle helpers from `app/feats/attendance.py`.
- Removed the stale `/api/hall-pass/cancel/<id>` endpoint.
- Removed route-level `FEAT-ATTN-002` wrappers from hall-pass checkout/checkin.
- Removed remaining route-level `FEAT-ATTN-*` wrappers from hall-pass settings/token API surfaces; those are Class Configuration settings writes, not PROD writes.
- Removed the legacy `student_tap` idempotency prefix from the student dashboard attendance command surface.
- Removed legacy auto tap-out wording from the scheduled daily-limit enforcement job.
- Removed direct UTC day-boundary construction from `app/attendance.py`; period attendance now derives day boundaries through `canonical_temporal_resolver`.
- Removed the legacy Ledger `Transaction.type` payroll-anchor dependency from `app/attendance.py`; attendance helper anchors now read `payroll_event`.
- Removed deleted `get_all_block_statuses` / `SeatAttendanceState` assumptions from `tests/dom/attendance/test_attendance.py`.
- Removed old direct attendance writer helpers, soft-delete helper, and state-table helper paths from `app/feats/attendance.py`.
- Removed obsolete `batch_auto_tapout_students(...)` from `app/attendance.py`.
- Removed `Seat.block` fallback from `/api/tap`; class section is the only display-period source in that route.
- Removed legacy seat-level tap settings and attendance-row delete/edit UI from audited templates.
- Removed the obsolete `HallPassLog` transition listener that attempted to infer old `seat_id`/`student_id` fields instead of requiring the canonical PROD hall-pass contract.

---

## V. Remaining PROD Gaps

| Gap | Status | Required Disposition |
|---|---|---|
| Student support attendance issue naming | `REWIRED` | Route/template now expose `attendance_session`; legacy `tap_event` URL/endpoint terminology was removed rather than aliased. |
| Live schema proof | `VERIFIED` | Local PostgreSQL at Alembic head `f6a7b8c9d0e2` exposes only `attendance_sessions`, `hall_pass_logs`, and `payroll_event` for the PROD table set; `seat_attendance_state` and `tap_events` are absent. |
| PROD FEAT targeted test proof | `VERIFIED` | `pytest -q tests/dom/prod/test_feat_prod.py` passed 3 tests on 2026-07-22 after fresh migration-chain blockers were removed. |
| Journey/render verification | `PARTIAL_BLOCKED_BY_STALE_TEST_AUTH` | Existing `student_detail` identity render tests currently redirect at auth setup before template render; add route render checks and journeys for start work, hall-pass request/approve/leave/return, run payroll, payroll history, student detail, and public verification. |
| Tests still encoding old shapes | `KNOWN_RESIDUE` | Modernize direct `AttendanceSession` and `HallPassLog` test setup under the current DOM-PROD schema. `tests/dom/attendance/test_hall_pass_checkout.py` still constructs legacy `HallPassLog(seat_id, status, request_time, decision_time, period)` rows and fails before exercising the route. |
| Residual non-template cleanup | `REWIRED` | Class destruction no longer references `SeatAttendanceState` or stale `TapEvent` cleanup; dropped PROD predecessor tables are not part of live runtime cleanup. |
| Route-local view assembly | `ACCEPTED_TEMPORARILY` | Several canonical read models are still assembled in routes; extract page view builders after checklist stability. |
| Rent / obligation surfaces | `OUT_OF_SCOPE_FOR_PROD` | Rent payment and obligation satisfaction are OBL-owned. Entitlement grants produced by obligation satisfaction are entitlement-domain business; PROD reads only approved hall-pass consumption via `hall_pass_logs` and related attendance changes. Approved hall-pass consumption reuses the consumed entitlement grant's `correlation_id`. |

---

## VI. Validation Evidence

Focused checks run for this checkpoint:

```bash
python3 -m py_compile app/attendance.py app/feats/attendance.py app/feats/base.py app/feats/prod.py app/routes/api.py app/routes/admin.py app/services/attendance_service.py app/services/hall_pass_request_queue.py app/scheduled_tasks.py
git diff --check
```

Targeted PROD FEAT proof added on 2026-07-22:

```bash
pytest -q tests/dom/prod/test_feat_prod.py
# 3 passed in 21.17s
```

This run also proved that the fresh migration chain reaches Alembic head `f6a7b8c9d0e2` after removing stale migration dependencies on the retired `TapEventReasonCode` enum and already-deleted `student_blocks` table.

Student-detail targeted check added on 2026-07-22:

```bash
python3 -c "import pathlib; compile(pathlib.Path('app/routes/admin.py').read_text(), 'app/routes/admin.py', 'exec')"
rg -n "student\\.block|Block \\{\\{|transactions\\|selectattr\\('type', 'equalto', 'payroll'|transactions\\|selectattr\\('type', 'equalto', 'bonus'|student_blocks_settings|tap-entries|block-tap-settings|student-block-settings" templates/student_detail.html -S
rg -n "payroll_event_history|PayrollEvent.query|join_codes\\[class_display_label\\]" app/routes/admin.py templates/student_detail.html -S
```

The template-specific scan no longer finds `student.block`, block-labelled join-code rendering, legacy payroll/bonus transaction filters, or deleted tap-management endpoint references in `templates/student_detail.html`. The positive scan shows `student_detail_public` now supplies `payroll_event_history` from `PayrollEvent` and current-class join-code display from `ClassEconomy`; the route no longer supplies a `blocks` variable to this template. Existing `tests/dom/identity/test_admin_tenancy.py` student-detail render checks were run but failed with `302` before template rendering because their auth/session setup is stale; no template error was reached.

Admin-payroll template contract check added on 2026-07-22:

```bash
rg -n "\\bblocks\\b|data-block|student\\.block|historyBlockFilter|studentBlockFilter|total_blocks|join_codes_by_block|student-period-label|Block Filter" templates/admin_payroll.html -S
rg -n "payroll_class_options|total_classes|data-class-id|student\\.class_id|student\\.class_label|student\\.public_id|student\\.full_name" app/routes/admin.py templates/admin_payroll.html -S
```

The negative template scan no longer finds block-shaped filter variables, `Seat.block` template access, or `data-block` attributes in `admin_payroll.html`. The positive scan shows canonical `class_id` filters and student stat view rows. `PayrollSettings.block` remains a lower-level settings persistence detail to collapse in the class-configuration/settings pass, not a surviving template scope contract.

Student-payroll template contract check added on 2026-07-22:

```bash
rg -n "student_blocks|period_states|unpaid_seconds_per_block|projected_pay_per_block|attendance_events_by_block|block_events|Block \\{\\{|No blocks assigned|Breakdown by Block|Per-Block|Active Blocks|loop\\.last" templates/student_payroll.html -S
rg -n "class_label|payroll_state|unpaid_seconds|projected_pay|attendance_events\\[:20\\]|last_payroll_event|days_since_last_payroll" templates/student_payroll.html app/routes/student.py -S
```

The negative template scan no longer finds block-keyed payroll variables or block-labelled payroll UI in `student_payroll.html`. The positive scan shows a class-scoped view contract backed by canonical `attendance_sessions` and `payroll_event` reads.

Student-dashboard attendance contract check added on 2026-07-22:

```bash
rg -n "get_all_block_statuses|student_blocks|period_states|period_states_json|unpaid_seconds_per_block|projected_pay_per_block|data-period|data-block-row|block-status|block-duration|block-pay|updateBlockUI|periodStateCache|selectedBreakPeriod|data\\.periods|\\\"periods\\\"" app/routes/student.py app/routes/api.py app/services/attendance_service.py templates/student_dashboard.html static/js/attendance.js app/attendance.py
rg -n "attendance_state|attendance_state_json|data-action|student-status|api/tap" app/routes/student.py app/routes/api.py templates/student_dashboard.html static/js/attendance.js
```

The dashboard-specific negative scan no longer finds block/period-shaped attendance state in `student.dashboard`, `/api/tap`, `/api/student-status`, `templates/student_dashboard.html`, `static/js/attendance.js`, or the PROD attendance service. The same broad scan still reports `student_blocks` in the separate student-rent route; that is a different template-audit row and remains outside this dashboard disposition. The positive scan shows the dashboard now receives one `attendance_state` object for the active canonical class; `/api/tap` no longer accepts a client-supplied period; `/api/student-status` returns `attendance_state`; and `get_all_block_statuses` was removed from live PROD service code in favor of `get_class_attendance_status`.

PROD runtime cleanup proof added on 2026-07-22:

```bash
rg -n "AttendanceSession\\.seat_id|HallPassLog\\.seat_id|PayrollEvent\\.seat_id|AttendanceSession\\.started_at|AttendanceSession\\.ended_at|AttendanceSession\\.is_deleted" app/attendance.py app/utils/analytics_engine.py app/utils/student_deletion.py app/payroll.py app/routes/admin.py app/routes/api.py app/routes/student.py
# no matches

rg -n "from app\\.utils\\.time|utc_now\\(|datetime\\.now|datetime\\.utcnow|total_seconds\\(" app/attendance.py
# no matches

rg -n "TapEvent|tap_events|SeatAttendanceState|seat_attendance_state|DOM-ATT" app/routes/admin.py app/utils/deletion.py app/utils/student_deletion.py
# no matches

rg -n "HallPassLog.*before_insert|HallPassLog.*before_update|_sync_hall_pass_seat|hall_pass_logs\\.seat_id|target\\.student_id|target\\.requested_by_seat_id|target\\.approved_by_seat_id" app/models.py app/feats/prod.py app/routes/api.py app/routes/admin.py
# no matches

python3 -m py_compile app/attendance.py app/utils/analytics_engine.py app/utils/student_deletion.py
python3 -m py_compile app/routes/admin.py app/utils/deletion.py app/utils/student_deletion.py

pytest -q tests/dom/prod/test_feat_prod.py
# 3 passed in 15.62s

pytest -q tests/dom/attendance/test_hall_pass_checkout.py
# known stale-test residue: fixture constructs legacy HallPassLog(seat_id/status/request_time/decision_time/period)
```

The older attendance-domain test module still imports deleted legacy helpers and
fails during collection before exercising these paths. That stale test residue
is tracked separately from the PROD runtime cleanup.

Admin-payroll-history template contract check added on 2026-07-22:

```bash
rg -n "admin_payroll_history|payroll-history|_build_payroll_event_display_rows|PayrollEvent.query.filter\\(PayrollEvent.class_id == ctx.class_id\\)|Transaction\\.type == ['\\\"]payroll|manual_payment|bonus" tests app/routes/admin.py templates/admin_payroll_history.html
```

The route reads canonical `payroll_event` rows scoped by active `ctx.class_id`, applies class-local date filters through `canonical_temporal_resolver`, and builds display rows through `_build_payroll_event_display_rows`, which resolves Ledger amounts by `correlation_id + target_seat_id`. `admin_payroll_history.html` now guards student-detail links so missing historical seat references render as text instead of generating an ambiguous roster fallback link.

Temporal resolver and PROD FEAT proof refreshed on 2026-07-22 after confirming
the scheduled daily-limit job depends on `shift_timestamp`:

```bash
pytest -q tests/dom/temporal/test_SPEC_TIME_001__canonical_temporal_resolver.py
# 26 passed in 0.55s
# summary: pytest_result/20260722_pytest_test_SPEC_TIME_001__canonical_temporal_resolver_summary.md

pytest -q tests/dom/prod/test_feat_prod.py
# 3 passed in 13.59s
# summary: pytest_result/20260722_pytest_test_feat_prod_summary_15.md

git diff --check
```

This proof includes `shift_timestamp`, the resolver primitive used by the
scheduled daily-limit job to write the exact `inactive/done_for_day`
`AttendanceSession` timestamp through `FEAT-PROD-001` once the class limit is
reached.

Live schema proof added on 2026-07-22:

```bash
flask db current
# f6a7b8c9d0e2 (head)

psql postgresql://postgres:postgres@localhost:5432/classroom_economy -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('attendance_sessions','hall_pass_logs','payroll_event','seat_attendance_state','tap_events') ORDER BY table_name;"
# attendance_sessions
# hall_pass_logs
# payroll_event

psql postgresql://postgres:postgres@localhost:5432/classroom_economy -c "SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('attendance_sessions','hall_pass_logs','payroll_event','seat_attendance_state') ORDER BY table_name, ordinal_position;"
# verified DOM-PROD columns and nullability for attendance_sessions, hall_pass_logs, and payroll_event

psql postgresql://postgres:postgres@localhost:5432/classroom_economy -c "SELECT tablename, indexname FROM pg_indexes WHERE schemaname='public' AND tablename IN ('attendance_sessions','hall_pass_logs','payroll_event') ORDER BY tablename, indexname;"
# verified ORM-declared PROD indexes, including payroll_event policy/version and replay-guard indexes

psql postgresql://postgres:postgres@localhost:5432/classroom_economy -c "SELECT conname, confdeltype FROM pg_constraint WHERE conrelid = 'payroll_event'::regclass AND contype = 'f' AND conkey = ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid = 'payroll_event'::regclass AND attname = 'policy_version_id')]::smallint[];"
# fk_payroll_event_policy_version_id | r
```

Stale-pattern scans were also run for the touched surfaces. They no longer find:

- legacy pending hall-pass status helpers;
- `FEAT-ATTN-002`;
- `student_tap`;
- attendance soft-delete helper;
- `seat_attendance_state` usage in the touched template-facing PROD surfaces.

Current runtime scans are also clean for `FEAT-ATTN-*` and `student_tap`; remaining mentions in this document are historical evidence from this checkpoint.

The former `SeatAttendanceState` class-destruction cleanup reference has been removed from live runtime code.
Class destruction now explicitly deletes `attendance_sessions`, `hall_pass_logs`,
and `payroll_event` by `class_id`; teacher-scoped student removal remains
target-seat scoped inside the relevant class.

---

## VII. Definition of Done for PROD

Productivity and Payroll is complete only when:

- `DOM-PROD-001` tables and ORM agree with the live migrated database;
- `FEAT-PROD-001` is the only writer for `attendance_sessions`;
- `FEAT-PROD-002` is the only writer for `hall_pass_logs`;
- `FEAT-PROD-003` is the only writer for `payroll_event`;
- payroll monetary facts are posted through Ledger with shared correlation and no payroll amount stored on `payroll_event`;
- every PROD row in the template audits has a final disposition;
- every `MAP-UI-001` Productivity/Payroll row has a final disposition;
- student/admin payroll, attendance, and hall-pass templates render from canonical page contracts;
- targeted domain, read model, route, render, and journey tests pass;
- obsolete attendance/payroll compatibility paths are deleted rather than preserved.
