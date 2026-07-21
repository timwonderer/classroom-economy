# Productivity and Payroll Reconstruction Stocktake

| Reference Number | Version | Date | Scope |
|---|---:|---|---|
| PROD-PAYROLL-STOCKTAKE-2026-07-20 | 0.1 | 2026-07-20 | Productivity and Payroll only |

---

## I. Purpose

This stocktake freezes the current state before route/template wiring begins for the Productivity and Payroll domain.

The goal is to distinguish:

- what is already built and can be reused;
- what is partially built but not ready to wire;
- what still needs to be built before any template or route is reconnected;
- what legacy surface must be deleted, collapsed, or rewritten.

This document follows `SOP-DEV-002_CANONICAL_DOMAIN_RECONSTRUCTION_WORKFLOW.md` and uses `MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md` as the UI surface checklist.

---

## II. Authoritative Inputs

### Domain and FEAT Authority

- `docs/DOMAIN/DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-001_RECORD_ATTENDANCE_SESSION.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-002_RECORD_HALL_PASS_LOG.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-003_RECORD_PAYROLL_EVENT.md`

### Reconstruction and Wiring Authority

- `docs/STANDARD_OPERATING_PROCEDURES/DEVOPS/SOP-DEV-002_CANONICAL_DOMAIN_RECONSTRUCTION_WORKFLOW.md`
- `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md`
- `docs/MAP/MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE.md`

### Template Audit Inputs

- `docs/TRACKING/TEMPLATE_AUDIT_ADMIN_E-P.md`
- `docs/TRACKING/TEMPLATE_AUDIT_STUDENT.md`
- `docs/TRACKING/TEMPLATE_INTERFACE_AUDIT_2026-07-19.md`
- `docs/TRACKING/TEMPLATE_ROUTE_AUDIT_ADMIN_AND_ANALYTICS.md`
- `docs/TRACKING/TEMPLATE_ROUTE_AUDIT_ADMIN_AND_SHARED.md`

---

## III. Built

These pieces exist in the current branch and are valid inputs for the reconstruction.

| Area | Current Artifact | Status | Notes |
|---|---|---|---|
| Domain authority | `DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md` | Built | Defines Productivity and Payroll as the authority over productivity session facts, hall-pass execution facts, and payroll event records. |
| FEAT specs | `FEAT-PROD-001`, `FEAT-PROD-002`, `FEAT-PROD-003` | Built | Defines exclusive write paths for `attendance_sessions`, `hall_pass_logs`, and `payroll_event`. |
| UI wiring map | `MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md` | Built | Captures the Productivity and Payroll template/route surfaces that must be rewired, removed, collapsed, or verified. |
| Reconstruction workflow | `SOP-DEV-002_CANONICAL_DOMAIN_RECONSTRUCTION_WORKFLOW.md` | Built | Defines the repeatable domain reconstruction process. |
| Request/view pipeline | `MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE.md` | Built | Defines Canonical Context, Temporal Context, Identity Display Context, and Page View Model responsibilities. |
| ORM table shapes | `app/models.py` | Built but unverified | Contains `AttendanceSession`, `HallPassLog`, and `PayrollEvent` with v2-shaped fields. |
| Schema migrations | `b2c3d4e5f8a` and `c3d4e5f8a9b` | Built but needs head/schema verification | Migrations align PROD tables and drop `seat_attendance_state`; live DB verification is still required before wiring. |
| PROD FEAT module | `app/feats/prod.py` | Partially built | Contains `record_attendance_session`, `record_hall_pass_log`, `record_payroll_event`, and `record_payroll_reversal`. |
| PROD unit tests | `tests/dom/prod/test_feat_prod.py` | Built but stale/failing | Tests exist, but current assertions and setup still reference removed fields or blocked FEAT behavior. |
| Temporal resolver tests/artifacts | `pytest_result/20260719_pytest_test_canonical_temporal_resolver_summary_2.md` | Evidence exists | Latest artifact shows temporal/PROD tests were not green. |

---

## IV. Partially Built

These pieces exist, but are not ready to treat as wiring targets.

### 1. Temporal Resolver Contract Is Not Import-Safe

`app/feats/prod.py` imports:

```python
from app.utils.temporal import (
    CLASS_LEVEL_EVALUATION,
    SYSTEM_LEVEL_EVALUATION,
    resolve_canonical_temporal_evaluation,
)
```

But the current checkout has no `app/utils/temporal.py`.

Current implication:

- `FEAT-PROD-*` cannot be considered import-safe.
- Route wiring into `app.feats.prod` would likely crash before execution.
- The temporal contract must be reconciled before any route calls PROD FEATs.

Required disposition:

- Either restore/build `app/utils/temporal.py` as the canonical runtime module; or
- intentionally amend the FEAT docs and FEAT implementation to use the actual canonical temporal module.

Do not paper over this with a compatibility shim.

### 2. ORM and Tests Disagree

The current `AttendanceSession` model uses:

- `target_seat_id`
- `target_user_id`
- `actor_seat_id`
- `status`
- `reason_code`
- `timestamp`

But `tests/dom/prod/test_feat_prod.py` still asserts or creates:

- `session.seat_id`
- `session.ended_at`
- `session.end_reason_code`
- `started_at`
- `ended_at`
- `duration_seconds`
- `start_reason`
- `end_reason`

Current implication:

- The tests do not prove the canonical schema.
- Test failures here are expected until the tests are rewritten around the append-only timeline.

Required disposition:

- Rewrite PROD tests to assert canonical row shape and derived timeline behavior.
- Remove old session-duration assumptions from PROD test setup.

### 3. PROD FEAT Implementation Is Incomplete Against Its Own Specs

Observed gaps:

- `record_attendance_session(...)` currently targets `ctx.seat_id`; `FEAT-PROD-001` requires explicit actor and target semantics, including teacher/system initiated writes.
- `record_attendance_session(...)` maps `daily_limit`; current memory and recent architecture notes indicate `daily_limit` should not be preserved unless a current doc explicitly still requires it.
- `record_hall_pass_log(...)` writes an approved hall-pass fact and consumes entitlement, but the current `HallPassLog` model no longer has `status`; stale tests still expect `log.status`.
- `record_payroll_event(...)` accepts `policy_version_id=None`; `DOM-PROD-001` and `FEAT-PROD-003` require policy lineage for payroll events.
- Payroll reversal lookup depends on ledger transaction correlation behavior that is not yet proven by current PROD tests.
- `SYSTEM_LEVEL_EVALUATION` is imported but not used.

Current implication:

- The FEAT module is a useful starting point, not a ready-to-wire implementation.

Required disposition:

- Bring FEAT signatures and behavior into exact agreement with `FEAT-PROD-001/002/003`.
- Then prove with focused PROD tests before route adoption.

### 4. Route Layer Still Enters Legacy Attendance and Payroll Paths

Current live references include:

- `app/routes/admin.py` imports `student_tap` from `app.feats.attendance`.
- `app/routes/admin.py` still wraps payroll execution in `FEAT-LED-004`.
- `app/routes/api.py` still contains `FEAT-ATTN-*` tap and attendance endpoints.
- `app/attendance.py`, `app/feats/attendance.py`, and `app/payroll.py` still contain old attendance/payroll business logic.
- Tests under `tests/dom/attendance` and `tests/dom/obligations` still seed or assert old attendance/payroll shapes.

Current implication:

- The application surface is not wired to `FEAT-PROD-*`.
- `FEAT-PROD-001` is not yet the exclusive writer in runtime.
- `FEAT-PROD-003` is not yet the payroll command path.

Required disposition:

- Do not start template rewiring first.
- Rebuild the command/read boundary, then rewire routes, then update templates/view models.

### 5. Read Models Do Not Exist Yet

`MAP-UI-001` requires read/view contracts for:

- student productivity state;
- student payroll page;
- admin payroll dashboard;
- admin payroll history;
- hall-pass queue and out-of-class state;
- admin attendance log;
- public hall-pass verification.

Current implementation still derives many of these from legacy helpers, `Transaction` rows, status-style hall-pass fields, or old attendance duration columns.

Current implication:

- Templates cannot be cleanly wired until page-specific view models exist.
- Route rewiring without read models will likely produce render crashes.

Required disposition:

- Build canonical read model builders before updating templates.

---

## V. Not Built Yet

These are required before the domain can be considered complete.

| Required Piece | Why It Is Needed | Owner |
|---|---|---|
| Import-safe canonical temporal module | `FEAT-PROD-*` depends on it; current file is missing | Temporal architecture / PROD FEAT prerequisite |
| Passing PROD primitive tests | Proves `FEAT-PROD-001/002/003` against canonical schema | PROD |
| Writer audit enforcement | Proves no route/service/job writes `attendance_sessions`, `hall_pass_logs`, or `payroll_event` outside PROD FEATs | PROD / FEAT guardrails |
| Attendance timeline read service | Derives active/inactive state, unpaid seconds, current work status, and daily/class-local summaries | PROD read model |
| Payroll projection service | Derives payroll estimates/history from `attendance_sessions`, `payroll_event`, policy, and ledger by correlation | PROD read model |
| Hall-pass queue/read service | Derives approved queue, current out-of-class state, and verification view from `hall_pass_logs` plus attendance timeline | PROD read model |
| Student productivity view model | Supplies dashboard contract without legacy `student` object assumptions | View model |
| Student payroll view model | Supplies payroll history, attendance events, and projected pay without `sess.period` or old duration fields | View model |
| Admin payroll dashboard view model | Supplies estimates, recent payrolls, student stats, and history from canonical projections | View model |
| Admin attendance log view model | Supplies attendance counts/rates and section/class display from canonical timeline | View model |
| Hall-pass admin/public view models | Supplies queue, verification, and display metadata from canonical state | View model |
| Route rewires | Connects audited surfaces to new FEAT/read model interfaces | Route layer |
| Template contract rewires | Updates Jinja to receive canonical view models and identifiers | Template layer |
| Journey tests | Proves real workflows from UI action to DB write to rendered result | Verification |
| Legacy deletion pass | Removes `FEAT-ATTN-*`, `FEAT-LED-004` payroll usage, dead templates, stale tests, and obsolete helpers once unreachable | Cleanup |

---

## VI. Pre-Wiring Gates

Do not begin broad route/template wiring until these gates are satisfied.

1. `app.feats.prod` imports successfully.
2. PROD primitive tests pass against the current ORM schema.
3. The live migration head and inspected DB schema match `DOM-PROD-001`.
4. A writer scan identifies every current writer to `attendance_sessions`, `hall_pass_logs`, and `payroll_event`.
5. The first read model boundary is selected and implemented before its templates are touched.

Recommended first targeted tests:

```bash
pytest tests/dom/prod/test_feat_prod.py
pytest tests/test_canonical_temporal_resolver.py
```

Do not run the full suite for this phase unless a targeted pass exposes global collection/import failures.

---

## VII. Recommended Completion Order

### Phase 1: Make the Domain Core Import-Safe and Testable

1. Reconcile `app.utils.temporal` versus the actual temporal implementation.
2. Fix any mapper issues for `AttendanceSession`, `HallPassLog`, and `PayrollEvent`.
3. Rewrite `tests/dom/prod/test_feat_prod.py` around canonical fields.
4. Make `FEAT-PROD-001/002/003` pass targeted primitive tests.

Exit criteria:

- `pytest tests/dom/prod/test_feat_prod.py` passes.
- `pytest tests/test_canonical_temporal_resolver.py` passes or has only non-PROD failures explicitly tracked.

### Phase 2: Build Canonical Read Models

1. Build attendance timeline projections.
2. Build payroll projection/history projections.
3. Build hall-pass queue/public verification projections.
4. Define page view model contracts using `MAP-UI-002`.

Exit criteria:

- Read model tests prove state is derived from canonical PROD tables and Ledger correlation only where monetary display is needed.

### Phase 3: Rewire Command Routes

1. Student/API/admin tap routes call `FEAT-PROD-001`.
2. Hall-pass approve/issue routes call `FEAT-PROD-002`.
3. Payroll run/manual credit/reversal routes call `FEAT-PROD-003`.
4. Remove runtime mutation authority from `app.feats.attendance`, `app.attendance`, and `app.payroll` where replaced.

Exit criteria:

- Writer scan shows no direct route/service/job writes to PROD tables outside `app.feats.prod`.

### Phase 4: Rewire GET Routes and Templates

1. Student dashboard and student payroll.
2. Admin payroll dashboard and payroll history.
3. Admin attendance log.
4. Admin hall-pass queue and public verification.
5. Support issue reference naming from `tap_event` to canonical attendance-session terminology.

Exit criteria:

- Each `MAP-UI-001` row is marked `REWIRED`, `REMOVED`, `COLLAPSED`, or `VERIFY_ONLY`.
- No template depends on stale fields such as `sess.period`, `student.hall_passes`, `req.student.full_name`, or old attendance duration columns.

### Phase 5: Journey Verification and Legacy Deletion

1. Student starts work.
2. Student leaves/returns by hall pass.
3. Teacher runs payroll.
4. Ledger balance updates from payroll settlement.
5. Student payroll and admin payroll history render from `payroll_event`.
6. Attendance log renders from `attendance_sessions`.
7. Delete unreachable legacy attendance/payroll paths.

Exit criteria:

- Journey tests pass.
- Legacy writer paths are deleted, not shimmed.
- Docs and maps are updated with final row dispositions.

---

## VIII. Current Blocking Findings

| Severity | Finding | Impact |
|---|---|---|
| P0 | `app/utils/temporal.py` is missing while `app/feats/prod.py` imports it | PROD FEAT module is not import-safe. |
| P0 | Latest pytest artifacts show PROD/temporal tests failing | Domain core is not ready to wire. |
| P0 | Tests and some runtime paths still reference removed `AttendanceSession` fields | Schema/test/route contract is inconsistent. |
| P0 | Routes still call `FEAT-ATTN-*` and `FEAT-LED-004` for Productivity/Payroll surfaces | Exclusive PROD write authority is not enforced. |
| P1 | Read model/view model layer is not built | Templates will remain fragile and likely crash if wired directly. |
| P1 | Migrations require live schema/head verification | Cannot claim schema completion until DB proof exists. |
| P2 | `MAP-UI-001` has open product decisions for hall-pass verification and terminology | Needs decision during the hall-pass slice, not before core FEAT work. |

---

## IX. Definition of Done for This Domain

Productivity and Payroll is complete only when:

- `DOM-PROD-001` tables and ORM agree with the live migrated database;
- `FEAT-PROD-001` is the only writer for `attendance_sessions`;
- `FEAT-PROD-002` is the only writer for `hall_pass_logs`;
- `FEAT-PROD-003` is the only writer for `payroll_event`;
- payroll monetary facts are posted through Ledger with shared correlation and no payroll amount stored on `payroll_event`;
- every `MAP-UI-001` Productivity/Payroll row has a final disposition;
- student/admin payroll, attendance, and hall-pass templates render from canonical page view models;
- targeted domain, read model, route, render, and journey tests pass;
- obsolete attendance/payroll compatibility paths are deleted rather than preserved.
