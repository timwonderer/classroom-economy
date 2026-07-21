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
| Student views current productivity state and projected pay | `student_dashboard.html`; `student.dashboard` (`GET /student/`) | `OUTPUT` | Student `CanonicalContext`; `class_id`; `seat_id`; class-local day | Read-only `DOM-PROD`; wage policy from Class Configuration; balance from Ledger | Reads `attendance_sessions`, payroll settings, ledger balances, entitlement balance | `period_states`, `student_blocks`, `unpaid_seconds_per_block`, `projected_pay_per_block`, `unique_days_tapped`, `hall_pass_balance`, display metadata | Resolved 2026-07-21: template no longer dereferences `student.display_first_name` or `student.hall_passes`; route calls canonical attendance read service with `CanonicalContext`; display metadata supplies student name | `REWIRED_READ` |
| Student views payroll history, attendance events, and projected pay | `student_payroll.html`; `student.payroll` (`GET /student/payroll`) | `OUTPUT` | Student `CanonicalContext`; `class_id`; `seat_id`; class-local payroll window | Read-only `DOM-PROD`; `FEAT-PROD-003` lineage for payroll events | Reads `attendance_sessions`, `payroll_event`, payroll policy, ledger display data as secondary monetary facts | `student_blocks`, `unpaid_seconds_per_block`, `projected_pay_per_block`, `all_tap_events`, `tap_events_by_block`, `pay_rate_per_minute` | Resolved 2026-07-21: route groups canonical `AttendanceSession` rows by class section, uses `PayrollEvent` for last payroll, and calls canonical temporal resolver for elapsed-time display | `REWIRED_READ` |
| Teacher views payroll dashboard and estimates | `admin_payroll.html`; `admin.payroll` (`GET /admin/payroll`) | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local payroll window | Read-only `DOM-PROD`; Class Configuration for wage policy; Ledger for balances only | Reads `attendance_sessions`, `payroll_event`, payroll settings, balances | `recent_payrolls`, `next_payroll_by_block`, `total_payroll_estimate`, `student_stats`, `payroll_history`, `all_students` | Resolved 2026-07-21 for GET read: recent activity, history tab, last-payroll stats, and total earned now derive from `PayrollEvent` rows with Ledger amount lookup by `correlation_id`; legacy payroll void controls removed from this template surface | `REWIRED_READ` |
| Teacher runs attendance-based payroll | `admin_payroll.html`; `admin.run_payroll` (`POST /admin/run_payroll`) | `ACTION` | Teacher `CanonicalContext`; selected `class_id`; actor teacher seat; class-local payroll evaluation | `FEAT-PROD-003` with `payroll_event_type = payroll`; Ledger posting through `FEAT-LED-000` / `FEAT-LED-001` | Writes `payroll_event`; writes Ledger monetary facts with shared `correlation_id` | Redirect or JSON success; subsequent GET must show payroll event lineage and updated monetary facts | Resolved 2026-07-21: teacher clicking "Run Payroll" records `payroll` events, not `manual_credit`; route no longer uses `FEAT-LED-004` or `execute_admin_adjustments`; it records one payroll event per student through `record_payroll_event` using a shared canonical run timestamp | `REWIRED` |
| Teacher records manual payroll credit | `admin_payroll.html`; `admin.payroll_manual_payment` (`POST /admin/payroll/manual-payment`) | `ACTION` | Teacher `CanonicalContext`; selected `class_id`; actor teacher seat; target student seat | `FEAT-PROD-003` with `payroll_event_type = manual_credit`; Ledger through canonical monetary resolution | Writes `payroll_event`; writes Ledger credit; no payroll amount stored on domain row | Redirect back to payroll; display in payroll history/read model | Resolved 2026-07-21: any direct teacher-to-student money send is `manual_credit`; route calls `record_payroll_event(... payroll_event_type="manual_credit")`; template no longer exposes deduction or account-type controls because manual debits/fines belong to Obligations | `REWIRED` |
| Teacher views payroll history | `admin_payroll_history.html`; `admin.payroll_history` (`GET /admin/payroll-history`) | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local timestamp display | Read-only `DOM-PROD` payroll event lineage; Ledger amount display by correlation | Reads `payroll_event`; joins Ledger facts by `correlation_id` for amount display only | `payroll_history` entries with timestamp, class label, actor/target identity, amount, notes | Resolved 2026-07-21: route reads `PayrollEvent`, derives class-local date filters through `canonical_temporal_resolver`, and template uses dict `student_name` directly | `REWIRED` |
| Teacher views hall-pass queue and out-of-class state | `admin_hall_pass.html`; `admin.hall_pass` (`GET /admin/hall-pass`) | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local current day | Read-only `DOM-PROD`; entitlement balance from Obligations/Entitlement | Pending requests from ephemeral operational queue; issued passes from `hall_pass_logs`; out/returned state from `attendance_sessions`; entitlement state for balance | `pending_requests`, `issued_passes`, `out_of_class`, `verify_url`, `available_periods` | Resolved 2026-07-21: pending requests now come from ephemeral operational queue, not `hall_pass_logs`; issued/out state derives from canonical `hall_pass_logs` plus latest `attendance_sessions` | `REWIRED_READ` |
| Teacher marks approved hall pass leave/return | `admin_hall_pass.html`; `/api/hall-pass/<id>/leave`, `/api/hall-pass/<id>/return` | `ACTION` | Teacher `CanonicalContext`; `class_id`; approving teacher seat; requested student seat; class-local request time | `FEAT-PROD-001` | Writes append-only `attendance_sessions` rows for `inactive/hall_pass` and `active/start_work`; does not mutate `hall_pass_logs` lifecycle state | Reloads hall-pass page; subsequent GET derives approved/out state from latest attendance event | Resolved 2026-07-21: endpoint no longer uses `FEAT-ATTN-001` or legacy hall-pass mutation helpers for leave/return; it appends canonical attendance facts through `record_attendance_session` | `REWIRED` |
| Teacher approves or rejects pending hall-pass request | Hall-pass request/approval controls routed through admin/API hall-pass endpoints | `ACTION` | Teacher `CanonicalContext`; `class_id`; approving teacher seat; requested student seat; class-local request time; Class Configuration hall-pass settings | `FEAT-PROD-002`; entitlement consumption in Obligations/Entitlement; hall-pass settings read from Class Configuration | Pending request is ephemeral operational state; reject discards without writing PROD truth; approve writes `hall_pass_logs` and entitlement consumption with shared `correlation_id`; attendance exit/return stays in `attendance_sessions` | Pending request disappears; approved instruction appears in issued-pass read model | Resolved 2026-07-21: `admin_hall_pass.html` now approves/rejects ephemeral pending requests; approve is the commit point into `FEAT-PROD-002`, reject performs no PROD write, and legacy `HallPassLog.status` mutation helpers were removed from the touched implementation path | `REWIRED` |
| Student or teacher records productivity session state | Student dashboard attendance controls; student hall-pass controls; admin tap-in/tap-out routes | `ACTION` | Live `CanonicalContext`; actor seat; target seat; `class_id`; `CLE` temporal evaluation | `FEAT-PROD-001` | Writes append-only `attendance_sessions`; no current-state, elapsed-time, or payroll amount stored on row | Dashboard button set is contextual: `Start Work`, `Break`, `Leave`, and `Return`; Student dashboard/payroll and admin attendance views update from append-only timeline | Resolved 2026-07-21: student dashboard controls use v2 command surfaces (`/api/tap` for Start Work/Done for day, hall-pass checkout/checkin for Leave/Return); admin bulk tap-in/tap-out routes call `record_attendance_session`; legacy `app.feats.attendance` attendance writers, soft-delete helper, and `seat_attendance_state` status helper path were removed from the touched route surface | `REWIRED` |
| Teacher views attendance log | `admin_attendance_log.html`; `admin.attendance_log` (`GET /admin/attendance-log`); `/api/attendance/history` | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local display | Read-only `DOM-PROD` productivity timeline | Reads `attendance_sessions`; derives display rows from `target_seat_id`, `timestamp`, `status`, `reason_code` | `blocks`, `class_labels_by_block`; JS history payload with `student_name`, `student_class_label`, `period`, `timestamp`, `status`, `reason` | Resolved 2026-07-21: history API now reads canonical append-only `AttendanceSession` fields and uses `canonical_temporal_resolver` for date filters; legacy tap-enable toggle removed from this template surface | `REWIRED_READ` |
| Student reports attendance event issue | `student_submit_issue.html`; `student.report_tap_event_issue` (`GET, POST /student/help-support/tap-event/<id>/report`) | `ACTION` | Student `CanonicalContext`; `class_id`; `seat_id`; target attendance row belongs to same seat/class | Support FEAT/domain owns issue filing; `DOM-PROD` owns referenced attendance fact | Reads `attendance_sessions`; writes Support issue with `related_record_type` pointing at attendance fact | Issue form with `tap_event`; redirect to help/support on success | Route still names the related record `tap_event`; should be renamed or aliased to canonical productivity/attendance session terminology | `NEEDS_REWIRE` |
| Public hall-pass verification page | `hall_pass_verify.html`; public verify route | `OUTPUT` | Public capability token linked to teacher `user_id`; no live actor `CanonicalContext`; token resolves teacher-scoped verification authority across that teacher's classes | Read-only `DOM-PROD`; no mutation | Reads teacher-scoped `hall_pass_logs` and current-day attendance facts without exposing unrelated teacher/class data; student query matches `Seat.claim_first_name_hash` + `Seat.claim_last_name_hash` | Verification form/result page | Resolved 2026-07-21: class dropdown displays section + class display name while submitting `class_id`; route derives left/returned state from `attendance_sessions`; `IdentityProfile` is used only after unique match for display | `REWIRED_READ` |

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

## VI. Resolved Decisions

1. Student dashboard attendance controls must not be a generic tap-in/tap-out pair. The canonical contextual button set is `Start Work`, `Break`, `Leave`, and `Return`, derived from current productivity and hall-pass state.
2. Public hall-pass verification remains outside live actor `CanonicalContext`. It uses a public capability token linked to the teacher's `user_id`; resolving that token grants read-only teacher-scoped hall-pass verification authority because a teacher may have one physical hall-pass verification surface shared among classes.
3. Direct teacher-to-student money send is `manual_credit` under `FEAT-PROD-003`. Teacher clicking `Run Payroll` is `payroll`, even if manually triggered by the teacher.

---

## VII. Amendment

Revisions to this map must update the version, preserve the row contract, and cite any newly audited template-route source documents used to add rows.
