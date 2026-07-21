# MAP-UI-001: Template to FEAT Wiring Map

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| MAP-UI-001 | 0.1 | 2026-07-20 | N/A | Informative |

---

## I. Purpose

This map connects audited template surfaces to their route, context, FEAT, domain, persistence, and read-model obligations.

It is the canonical planning artifact for turning template audit findings into executable rewiring work. GitHub issues and project boards may track execution, but this document preserves the architectural evidence.

This map is produced under `SOP-DEV-002_CANONICAL_DOMAIN_RECONSTRUCTION_WORKFLOW.md`.

---

## II. Authority and Inputs

Authority order:

1. `INV-CORE-000_CORE_INVARIANTS.md`
2. `INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`
3. `DOM-PROD-001_PRODUCTIVITY_AND_PAYROLL_DOMAIN.md`
4. `FEAT-PROD-001_RECORD_ATTENDANCE_SESSION.md`
5. `FEAT-PROD-002_RECORD_HALL_PASS_LOG.md`
6. `FEAT-PROD-003_RECORD_PAYROLL_EVENT.md`
7. `SOP-DEV-002_CANONICAL_DOMAIN_RECONSTRUCTION_WORKFLOW.md`

Audit inputs:

- `docs/TRACKING/TEMPLATE_AUDIT_ADMIN_E-P.md`
- `docs/TRACKING/TEMPLATE_AUDIT_STUDENT.md`
- `docs/TRACKING/TEMPLATE_INTERFACE_AUDIT_2026-07-19.md`
- `docs/TRACKING/TEMPLATE_ROUTE_AUDIT_ADMIN_AND_ANALYTICS.md`
- `docs/TRACKING/TEMPLATE_ROUTE_AUDIT_ADMIN_AND_SHARED.md`

---

## III. Row Contract

Each row describes one user-visible capability, not one variable or one template file.

| Field | Meaning |
|---|---|
| Capability | User-visible action, output, navigation, or client interaction |
| Surface | Template and route endpoint where the user sees or triggers the capability |
| Type | `ACTION`, `OUTPUT`, `NAVIGATION`, `CLIENT_JS`, or `HOUSEKEEPING` |
| Context | Required canonical context and temporal context |
| FEAT / Domain | Owning FEAT for mutation, plus owning domain for business truth |
| Persistence | Canonical table writes and reads |
| View Contract | Template variables or view-model shape that must be supplied |
| Current State | What the current branch appears to do |
| Rewire Status | `READY`, `NEEDS_REWIRE`, `NEEDS_FEAT_DECISION`, `DELETE_OR_RESTORE`, or `VERIFY_ONLY` |

---

## IV. Productivity and Payroll Slice

### Summary

| Status | Count | Meaning |
|---|---:|---|
| `NEEDS_REWIRE` | 7 | Existing route/template path disagrees with `DOM-PROD` or audited template contract |
| `NEEDS_FEAT_DECISION` | 1 | Product surface exists but exact FEAT/read responsibility needs a named decision |
| `DELETE_OR_RESTORE` | 1 | Template audit found a dead surface |
| `VERIFY_ONLY` | 1 | Surface is mostly a read/navigation view but needs route/template proof after rewiring |

### Capability Rows

| Capability | Surface | Type | Context | FEAT / Domain | Persistence | View Contract | Current State | Rewire Status |
|---|---|---|---|---|---|---|---|---|
| Student views current productivity state and projected pay | `student_dashboard.html`; `student.dashboard` (`GET /student/`) | `OUTPUT` | Student `CanonicalContext`; `class_id`; `seat_id`; class-local day | Read-only `DOM-PROD`; wage policy from Class Configuration; balance from Ledger | Reads `attendance_sessions`, `seat_attendance_state`, payroll settings, ledger balances | `period_states`, `student_blocks`, `unpaid_seconds_per_block`, `projected_pay_per_block`, `unique_days_tapped`, `student.hall_passes` replacement | Route uses `get_all_block_statuses(...)`, but audit flags `student.hall_passes` as legacy template access | `NEEDS_REWIRE` |
| Student views payroll history, attendance events, and projected pay | `student_payroll.html`; `student.payroll` (`GET /student/payroll`) | `OUTPUT` | Student `CanonicalContext`; `class_id`; `seat_id`; class-local payroll window | Read-only `DOM-PROD`; `FEAT-PROD-003` lineage for payroll events | Reads `attendance_sessions`, `payroll_event`, payroll policy, ledger display data as secondary monetary facts | `student_blocks`, `unpaid_seconds_per_block`, `projected_pay_per_block`, `all_tap_events`, `tap_events_by_block`, `pay_rate_per_minute` | Audit records route crash on `sess.period`; route currently reads old `started_at` / `ended_at` style fields and groups by `period` | `NEEDS_REWIRE` |
| Teacher views payroll dashboard and estimates | `admin_payroll.html`; `admin.payroll` (`GET /admin/payroll`) | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local payroll window | Read-only `DOM-PROD`; Class Configuration for wage policy; Ledger for balances only | Reads `attendance_sessions`, `payroll_event`, payroll settings, balances | `recent_payrolls`, `next_payroll_by_block`, `total_payroll_estimate`, `student_stats`, `payroll_history`, `all_students` | Route still derives recent payrolls/history primarily from `Transaction` rows; needs payroll event read model | `NEEDS_REWIRE` |
| Teacher runs attendance-based payroll | `admin_payroll.html`; `admin.run_payroll` (`POST /admin/run_payroll`) | `ACTION` | Teacher `CanonicalContext`; selected `class_id`; actor teacher seat; class-local payroll evaluation | `FEAT-PROD-003`; Ledger posting through `FEAT-LED-000` / `FEAT-LED-001` | Writes `payroll_event`; writes Ledger monetary facts with shared `correlation_id` | Redirect or JSON success; subsequent GET must show payroll event lineage and updated monetary facts | Route is wrapped as `FEAT-LED-004` and calls `execute_admin_adjustments(...)`; it does not write `payroll_event` | `NEEDS_REWIRE` |
| Teacher records manual payroll credit | `admin_payroll.html`; `admin.manual_payment` (`POST /admin/payroll/manual-payment`) | `ACTION` | Teacher `CanonicalContext`; selected `class_id`; actor teacher seat; target student seat | `FEAT-PROD-003` with `payroll_event_type = manual_credit`; Ledger through canonical monetary resolution | Writes `payroll_event`; writes Ledger credit; no payroll amount stored on domain row | Redirect back to payroll; display in payroll history/read model | Route exists in admin payroll surface; audit treats manual payment as payroll surface, but runtime path must be confirmed against `FEAT-PROD-003` | `NEEDS_REWIRE` |
| Teacher views payroll history | `admin_payroll_history.html`; `admin.payroll_history` (`GET /admin/payroll-history`) | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local timestamp display | Read-only `DOM-PROD` payroll event lineage; Ledger amount display by correlation | Reads `payroll_event`; joins Ledger facts by `correlation_id` for amount display only | `payroll_history` entries with timestamp, class label, actor/target identity, amount, notes | Audit flags dead `entry.student` branch; route currently builds from payroll `Transaction` rows, not `payroll_event` lineage | `NEEDS_REWIRE` |
| Teacher views hall-pass queue and out-of-class state | `admin_hall_pass.html`; `admin.hall_pass` (`GET /admin/hall-pass`) | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local current day | Read-only `DOM-PROD`; entitlement balance from Obligations/Entitlement | Reads `hall_pass_logs`, `attendance_sessions`, entitlement state | `pending_requests`, `approved_queue`, `out_of_class`, `verify_url`, `available_periods` | Audit flags `req.student.full_name`; route reads status-style fields that must be checked against canonical `hall_pass_logs` contract | `NEEDS_REWIRE` |
| Teacher approves or issues hall pass | Hall-pass controls routed through admin/API hall-pass endpoints | `ACTION` | Teacher `CanonicalContext`; `class_id`; approving teacher seat; requested student seat; class-local request time | `FEAT-PROD-002`; entitlement consumption in Obligations/Entitlement | Writes `hall_pass_logs`; writes entitlement consumption with shared `correlation_id`; attendance exit/return stays in `attendance_sessions` | Queue updates on redirect/JSON response; approved instruction appears in hall-pass read model | Exact active endpoint set needs a focused route trace from current hall-pass controls and JS | `NEEDS_FEAT_DECISION` |
| Student or teacher records tap in/out productivity session | Student/API tap controls; admin tap-in/tap-out routes | `ACTION` | Live `CanonicalContext`; actor seat; target seat; `class_id`; `CLE` temporal evaluation | `FEAT-PROD-001` | Writes append-only `attendance_sessions`; no current-state, elapsed-time, or payroll amount stored on row | Student dashboard/payroll and admin attendance views update from append-only timeline | Runtime still imports/calls `app.feats.attendance.student_tap`; branch has `app.feats.prod.record_attendance_session` but route adoption needs verification | `NEEDS_REWIRE` |
| Teacher views attendance log | `admin_attendance_log.html`; `admin.attendance_log` (`GET /admin/attendance-log`) | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local display | Read-only `DOM-PROD` productivity timeline | Reads `attendance_sessions`; derives counts/rates by class/section | `periods`, `blocks`, `class_labels_by_block` | Route currently returns block metadata only; audit expects period attendance counts and rates | `NEEDS_REWIRE` |
| Student reports attendance event issue | `student_submit_issue.html`; `student.report_tap_event_issue` (`GET, POST /student/help-support/tap-event/<id>/report`) | `ACTION` | Student `CanonicalContext`; `class_id`; `seat_id`; target attendance row belongs to same seat/class | Support FEAT/domain owns issue filing; `DOM-PROD` owns referenced attendance fact | Reads `attendance_sessions`; writes Support issue with `related_record_type` pointing at attendance fact | Issue form with `tap_event`; redirect to help/support on success | Route still names the related record `tap_event`; should be renamed or aliased to canonical productivity/attendance session terminology | `NEEDS_REWIRE` |
| Public hall-pass verification page | `hall_pass_verification.html` / `hall_pass_verify.html`; public verify route | `OUTPUT` | Public verifier token; no class actor context; must resolve allowed class scope without exposing cross-class data | Read-only `DOM-PROD`; no mutation | Reads `hall_pass_logs` and current-day attendance facts | Verification form/result page | Template audit marks `hall_pass_verification.html` dead; runtime renders `hall_pass_verify.html` | `DELETE_OR_RESTORE` |

---

## V. Issue and Project Shape

GitHub issues should be generated from this map by capability group, not by template variable.

Recommended issue groups for this slice:

1. Student productivity read model: dashboard plus `student_payroll.html`
2. Admin payroll read model: payroll dashboard plus history
3. Payroll command path: run payroll and manual credit through `FEAT-PROD-003`
4. Hall-pass read and command path: queue, approval, verification
5. Attendance session command path: student/API/admin tap routes through `FEAT-PROD-001`
6. Attendance support issue terminology: replace `tap_event` surface with canonical attendance-session reference

Each issue should include:

- map row(s)
- audited template(s)
- route endpoint(s)
- required context
- FEAT/domain authority
- canonical writes
- read/view-model contract
- targeted validation command

---

## VI. Open Questions

1. Should the user-facing wording remain "tap" while the internal canonical reference becomes `attendance_session`, or should the template language also shift to "attendance event"?
2. Should public hall-pass verification remain outside live actor `CanonicalContext`, or should it receive a separate documented public verification authority contract?
3. Should manual payroll credit remain inside Productivity/Payroll as `manual_credit`, or should non-productivity rewards be split to another domain before launch?

---

## VII. Amendment

Revisions to this map must update the version, preserve the row contract, and cite any newly audited template-route source documents used to add rows.
