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
| Hall-pass leave/return | `REWIRED` | Leave/return append `attendance_sessions` rows through `FEAT-PROD-001`; `hall_pass_logs` are not mutated for lifecycle state. |
| Public hall-pass verification | `REWIRED_READ` | Public token resolves teacher-scoped read authority; class dropdown submits `class_id`; name lookup checks seat hashed names and displays `IdentityProfile` only after unique match. |
| Admin attendance log | `REWIRED_READ` | `/api/attendance/history` reads append-only `AttendanceSession` fields and uses `canonical_temporal_resolver` for class-local filters. |
| Admin roster bulk Start Work / Break | `REWIRED` | `admin.tap_in_students` / `admin.tap_out_students` call `record_attendance_session` and submit only `seat_ids`; no block or period scope is submitted. |
| Student detail PROD sections | `REWIRED_READ` | Attendance summary/history, hall-pass balance, join-code display, and Payroll tab are rewired; Payroll tab reads `payroll_event` rows plus Ledger amount lookup by `correlation_id`, not legacy `Transaction.type` filters. |
| Admin payroll page class-scope contract | `REWIRED_READ_WRITE` | `admin_payroll.html` no longer exposes block-shaped template filters or reads `Seat.block`; history and manual-credit selection use canonical `class_id` view rows while Run Payroll and manual credit remain wired through `FEAT-PROD-*`. |

---

## IV. Removed / Collapsed This Checkpoint

- Deleted `hall_pass_verification.html` after public verification collapsed to `hall_pass_verify.html`.
- Deleted the historical temporal rebuild plan after replacing it with `SPEC-TIME-001`.
- Removed old hall-pass lifecycle helpers from `app/feats/attendance.py`.
- Removed the stale `/api/hall-pass/cancel/<id>` endpoint.
- Removed route-level `FEAT-ATTN-002` wrappers from hall-pass checkout/checkin.
- Removed old direct attendance writer helpers, soft-delete helper, and state-table helper paths from `app/feats/attendance.py`.
- Removed obsolete `batch_auto_tapout_students(...)` from `app/attendance.py`.
- Removed `Seat.block` fallback from `/api/tap`; class section is the only display-period source in that route.
- Removed legacy seat-level tap settings and attendance-row delete/edit UI from audited templates.

---

## V. Remaining PROD Gaps

| Gap | Status | Required Disposition |
|---|---|---|
| Student support attendance issue naming | `REWIRED` | Route/template now expose `attendance_session`; legacy `tap_event` URL/endpoint terminology was removed rather than aliased. |
| Live schema proof | `VERIFIED` | Local PostgreSQL at Alembic head `f6a7b8c9d0e2` exposes only `attendance_sessions`, `hall_pass_logs`, and `payroll_event` for the PROD table set; `seat_attendance_state` and `tap_events` are absent. |
| PROD FEAT targeted test proof | `VERIFIED` | `pytest -q tests/dom/prod/test_feat_prod.py` passed 3 tests on 2026-07-22 after fresh migration-chain blockers were removed. |
| Journey/render verification | `PARTIAL_BLOCKED_BY_STALE_TEST_AUTH` | Existing `student_detail` identity render tests currently redirect at auth setup before template render; add route render checks and journeys for start work, hall-pass request/approve/leave/return, run payroll, payroll history, student detail, and public verification. |
| Tests still encoding old shapes | `KNOWN_RESIDUE` | Modernize direct `AttendanceSession` test setup under the current DOM-PROD schema. |
| Residual non-template cleanup | `REWIRED` | Class destruction no longer references `SeatAttendanceState`; the dropped state table is not part of live PROD runtime cleanup. |
| Route-local view assembly | `ACCEPTED_TEMPORARILY` | Several canonical read models are still assembled in routes; extract page view builders after checklist stability. |

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
# 3 passed in 14.51s
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

The former `SeatAttendanceState` class-destruction cleanup reference has been removed from live runtime code.

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
