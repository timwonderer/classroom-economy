# MAP-UI-001: Template to FEAT Wiring Map

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| MAP-UI-001 | 0.2 | 2026-07-22 | 0.1 | Informative |

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
7. `DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
8. `FEAT-STOR-001_STORE_PURCHASE.md`
9. `FEAT-STOR-002_ENTITLEMENT_TERMINAL_LIFECYCLE.md`
10. `FEAT-STOR-003_INSURANCE_CLAIM_LIFECYCLE.md`
11. `SOP-DEV-002_CANONICAL_DOMAIN_RECONSTRUCTION_WORKFLOW.md`
12. `MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE.md`

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
| `REWIRED` | 7 | Template-triggered PROD action routes now call the canonical v2 interface or were intentionally collapsed |
| `REWIRED_READ` | 6 | Template-rendered PROD read surfaces now use canonical v2 read contracts |
| `NEEDS_REWIRE` | 0 | No unresolved PROD row remains in this map; template audits remain the final checklist |

### Capability Rows

| Capability | Surface | Type | Context | FEAT / Domain | Persistence | View Contract | Current State | Rewire Status |
|---|---|---|---|---|---|---|---|---|
| Student views current productivity state and projected pay | `student_dashboard.html`; `student.dashboard` (`GET /student/`) | `OUTPUT` | Student `CanonicalContext`; `class_id`; `seat_id`; class-local day | Read-only `DOM-PROD`; wage policy from Class Configuration; balance from Ledger | Reads `attendance_sessions`, payroll settings, ledger balances, entitlement balance | `period_states`, `student_blocks`, `unpaid_seconds_per_block`, `projected_pay_per_block`, `unique_days_tapped`, `hall_pass_balance`, display metadata | Resolved 2026-07-21: template no longer dereferences `student.display_first_name` or `student.hall_passes`; route calls canonical attendance read service with `CanonicalContext`; display metadata supplies student name | `REWIRED_READ` |
| Student views payroll history, attendance events, and projected pay | `student_payroll.html`; `student.payroll` (`GET /student/payroll`) | `OUTPUT` | Student `CanonicalContext`; `class_id`; `seat_id`; class-local payroll window | Read-only `DOM-PROD`; `FEAT-PROD-003` lineage for payroll events | Reads `attendance_sessions`, `payroll_event`, payroll policy, ledger display data as secondary monetary facts | `student_blocks`, `unpaid_seconds_per_block`, `projected_pay_per_block`, `attendance_events`, `attendance_events_by_block`, `pay_rate_per_minute` | Resolved 2026-07-21: route groups canonical `AttendanceSession` rows by class section, uses `PayrollEvent` for last payroll, and calls canonical temporal resolver for elapsed-time display | `REWIRED_READ` |
| Teacher views payroll dashboard and estimates | `admin_payroll.html`; `admin.payroll` (`GET /admin/payroll`) | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local payroll window | Read-only `DOM-PROD`; Class Configuration for wage policy; Ledger for balances only | Reads `attendance_sessions`, `payroll_event`, payroll settings, balances | `recent_payrolls`, `next_payroll_by_block`, `total_payroll_estimate`, `student_stats`, `payroll_history`, `all_students` | Resolved 2026-07-21 for GET read: recent activity, history tab, last-payroll stats, and total earned now derive from `PayrollEvent` rows with Ledger amount lookup by `correlation_id`; legacy payroll void controls removed from this template surface | `REWIRED_READ` |
| Teacher runs attendance-based payroll | `admin_payroll.html`; `admin.run_payroll` (`POST /admin/run_payroll`) | `ACTION` | Teacher `CanonicalContext`; selected `class_id`; actor teacher seat; class-local payroll evaluation | `FEAT-PROD-003` with `payroll_event_type = payroll`; Ledger posting through `FEAT-LED-000` / `FEAT-LED-001` | Writes `payroll_event`; writes Ledger monetary facts with shared `correlation_id` | Redirect or JSON success; subsequent GET must show payroll event lineage and updated monetary facts | Resolved 2026-07-21: teacher clicking "Run Payroll" records `payroll` events, not `manual_credit`; route no longer uses `FEAT-LED-004` or `execute_admin_adjustments`; it records one payroll event per student through `record_payroll_event` using a shared canonical run timestamp | `REWIRED` |
| Teacher records manual payroll credit | `admin_payroll.html`; `admin.payroll_manual_payment` (`POST /admin/payroll/manual-payment`) | `ACTION` | Teacher `CanonicalContext`; selected `class_id`; actor teacher seat; target student seat | `FEAT-PROD-003` with `payroll_event_type = manual_credit`; Ledger through canonical monetary resolution | Writes `payroll_event`; writes Ledger credit; no payroll amount stored on domain row | Redirect back to payroll; display in payroll history/read model | Resolved 2026-07-21: any direct teacher-to-student money send is `manual_credit`; route calls `record_payroll_event(... payroll_event_type="manual_credit")`; template no longer exposes deduction or account-type controls because manual debits/fines belong to Obligations | `REWIRED` |
| Teacher views payroll history | `admin_payroll_history.html`; `admin.payroll_history` (`GET /admin/payroll-history`) | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local timestamp display | Read-only `DOM-PROD` payroll event lineage; Ledger amount display by correlation | Reads `payroll_event`; joins Ledger facts by `correlation_id` for amount display only | `payroll_history` entries with timestamp, class label, actor/target identity, amount, notes | Resolved 2026-07-21: route reads `PayrollEvent`, derives class-local date filters through `canonical_temporal_resolver`, and template uses dict `student_name` directly | `REWIRED` |
| Teacher views hall-pass queue and out-of-class state | `admin_hall_pass.html`; `admin.hall_pass` (`GET /admin/hall-pass`) | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local current day | Read-only `DOM-PROD`; entitlement balance from Obligations/Entitlement | Pending requests from ephemeral operational queue; issued passes from `hall_pass_logs`; out/returned state from `attendance_sessions`; entitlement state for balance | `pending_requests`, `issued_passes`, `out_of_class`, `verify_url`, `available_periods` | Resolved 2026-07-21: pending requests now come from ephemeral operational queue, not `hall_pass_logs`; issued/out state derives from canonical `hall_pass_logs` plus latest `attendance_sessions` | `REWIRED_READ` |
| Teacher marks approved hall pass leave/return | `admin_hall_pass.html`; `/api/hall-pass/<id>/leave`, `/api/hall-pass/<id>/return` | `ACTION` | Teacher `CanonicalContext`; `class_id`; approving teacher seat; requested student seat; class-local request time | `FEAT-PROD-001` | Writes append-only `attendance_sessions` rows for `inactive/hall_pass` and `active/start_work`; does not mutate `hall_pass_logs` lifecycle state | Reloads hall-pass page; subsequent GET derives approved/out state from latest attendance event | Resolved 2026-07-21: endpoint no longer uses `FEAT-ATTN-001` or legacy hall-pass mutation helpers for leave/return; it appends canonical attendance facts through `record_attendance_session` | `REWIRED` |
| Teacher approves or rejects pending hall-pass request | Hall-pass request/approval controls routed through admin/API hall-pass endpoints | `ACTION` | Teacher `CanonicalContext`; `class_id`; approving teacher seat; requested student seat; class-local request time; Class Configuration hall-pass settings | `FEAT-PROD-002`; entitlement consumption in Obligations/Entitlement; hall-pass settings read from Class Configuration | Pending request is ephemeral operational state; reject discards without writing PROD truth; approve writes `hall_pass_logs` and entitlement consumption with shared `correlation_id`; attendance exit/return stays in `attendance_sessions` | Pending request disappears; approved instruction appears in issued-pass read model | Resolved 2026-07-21: `admin_hall_pass.html` now approves/rejects ephemeral pending requests; approve is the commit point into `FEAT-PROD-002`, reject performs no PROD write, and legacy `HallPassLog.status` mutation helpers were removed from the touched implementation path | `REWIRED` |
| Student or teacher records productivity session state | Student dashboard attendance controls; student hall-pass controls; admin tap-in/tap-out routes | `ACTION` | Live `CanonicalContext`; actor seat; target seat; `class_id`; `CLE` temporal evaluation | `FEAT-PROD-001` | Writes append-only `attendance_sessions`; no current-state, elapsed-time, or payroll amount stored on row | Dashboard button set is contextual: `Start Work`, `Break`, `Leave`, and `Return`; Student dashboard/payroll and admin attendance views update from append-only timeline | Resolved 2026-07-21: student dashboard controls use v2 command surfaces (`/api/tap` for Start Work/Done for day, hall-pass checkout/checkin for Leave/Return); admin bulk tap-in/tap-out routes call `record_attendance_session`; legacy `app.feats.attendance` attendance writers, soft-delete helper, and `seat_attendance_state` status helper path were removed from the touched route surface | `REWIRED` |
| Teacher views attendance log | `admin_attendance_log.html`; `admin.attendance_log` (`GET /admin/attendance-log`); `/api/attendance/history` | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id`; class-local display | Read-only `DOM-PROD` productivity timeline | Reads `attendance_sessions`; derives display rows from `target_seat_id`, `timestamp`, `status`, `reason_code` | `blocks`, `class_labels_by_block`; JS history payload with `student_name`, `student_class_label`, `period`, `timestamp`, `status`, `reason` | Resolved 2026-07-21: history API now reads canonical append-only `AttendanceSession` fields and uses `canonical_temporal_resolver` for date filters; legacy tap-enable toggle removed from this template surface | `REWIRED_READ` |
| Student reports attendance event issue | `student_submit_issue.html`; `student.report_attendance_session_issue` (`GET, POST /student/help-support/attendance-session/<id>/report`) | `ACTION` | Student `CanonicalContext`; `class_id`; `seat_id`; target attendance row belongs to same seat/class | Support FEAT/domain owns issue filing; `DOM-PROD` owns referenced attendance fact | Reads `attendance_sessions`; writes Support issue with `related_record_type = attendance_session` pointing at attendance fact | Issue form with `attendance_session`; redirect to help/support on success | Resolved 2026-07-22: route, endpoint, parameter, template `url_for`, and submitted related-record type use canonical attendance-session terminology; legacy `tap_event` URL/endpoint is not preserved | `REWIRED` |
| Public hall-pass verification page | `hall_pass_verify.html`; public verify route | `OUTPUT` | Public capability token linked to teacher `user_id`; no live actor `CanonicalContext`; token resolves teacher-scoped verification authority across that teacher's classes | Read-only `DOM-PROD`; no mutation | Reads teacher-scoped `hall_pass_logs` and current-day attendance facts without exposing unrelated teacher/class data; student query matches `Seat.claim_first_name_hash` + `Seat.claim_last_name_hash` | Verification form/result page | Resolved 2026-07-21: class dropdown displays section + class display name while submitting `class_id`; route derives left/returned state from `attendance_sessions`; `IdentityProfile` is used only after unique match for display | `REWIRED_READ` |

---

## V. Store and Entitlements Slice

### Summary

| Status | Count | Meaning |
|---|---:|---|
| `NEEDS_REWIRE` | 16 | Route and/or template must be rewritten to match canonical FEAT, DOM-STORE-001 persistence, and cross-domain boundaries |

### Capability Rows

| Capability | Surface | Type | Context | FEAT / Domain | Persistence | View Contract | Current State | Rewire Status |
|---|---|---|---|---|---|---|---|---|
| Teacher views store dashboard: items, pending redemptions, recent purchases, audit log | `admin_store.html`; `admin.store_management` (`GET /admin/store`) | `OUTPUT` | Teacher `CanonicalContext`; selected `class_id` | Read-only `DOM-STORE`; Class Configuration for item catalog; Ledger for price display | Reads `store_items`, `store_purchases`, `redemption_events`, `store_item_visibility`; entitlement balance from `entitlement_events` | `items`, `pending_redemptions`, `recent_purchases`, `collective_progress_by_item`, `audit_rows`, `rent_managed_item_ids`, display metadata | Code reads correct canonical tables but template dereferences `student_item.redemption_date`, `student_item.purchase_date`, `student_item.redemption_details` which are not `StorePurchase` attributes per DOM-STORE-001; `student_hall_pass_balances_by_seat_id` read path already canonical; route uses legacy `FEATContext("FEAT-STOR-001")` for a GET which violates INV-ARC-007 (no GET side effects) | `NEEDS_REWIRE` |
| Teacher creates store item | `admin_store.html`; `admin.store_management` (`POST /admin/store`) | `ACTION` | Teacher `CanonicalContext`; selected `class_id`; actor teacher seat | Class Configuration domain; `store_items` and `store_item_visibility` are catalog definition, not Store purchase or entitlement mutation | Writes `store_items`, `store_item_visibility` | Redirect to store dashboard; subsequent GET shows new item | Route calls `create_store_item()` service and `item.set_blocks()` for visibility under wrong FEAT label `FEATContext("FEAT-STOR-001")`; must be rewired to Class Configuration FEAT | `NEEDS_REWIRE` |
| Teacher edits store item | `admin_edit_item.html`; `admin.edit_store_item` (`GET, POST /admin/store/edit/<item_id>`) | `ACTION` | Teacher `CanonicalContext`; selected `class_id`; actor teacher seat | Class Configuration domain; same as item creation | Writes `store_items`, `store_item_visibility` | `form`, `item`, `payroll_settings` | Route mutates `StoreItem` fields and visibility under wrong FEAT label `FEATContext("FEAT-STOR-001")`; must be rewired to Class Configuration FEAT | `NEEDS_REWIRE` |
| Teacher deactivates store item | `admin_store.html`; `admin.delete_store_item` (`POST /admin/store/delete/<item_id>`, `/admin/item/deactivate/<item_id>`) | `ACTION` | Teacher `CanonicalContext`; selected `class_id`; actor teacher seat | Class Configuration domain for catalog mutation; refund of pending collective purchases requires coordinated Ledger FEAT for monetary reversal | Writes `store_items` (soft-delete); refunds pending collective `store_purchases` via `refund_pending_collective_purchases()` | Redirect to store dashboard | Route uses wrong FEAT label `FEATContext("FEAT-STOR-003")`; refund path writes `StorePurchase.status` and `Transaction` directly which crosses Ledger domain boundary — monetary reversal must go through lawful Ledger FEAT | `NEEDS_REWIRE` |
| Student browses store catalog and views owned items | `student_shop.html`; `student.shop` (`GET /student/shop`) | `OUTPUT` | Student `CanonicalContext`; `class_id`; `seat_id` | Read-only `DOM-STORE`; Class Configuration for catalog; Ledger for balance display | Reads `store_items`, `store_purchases`, `store_item_visibility`, `rent_settings`; entitlement balance from `entitlement_events` | `items`, `student_items`, `has_paid_rent`, `per_period_rent_item_ids`, `rent_free_uses`, `class_size`, `collective_progress` | Template var `student_items` references legacy `StudentItem` naming convention; actual query reads `StorePurchase` but view contract uses wrong name; visibility check calls canonical `store_service.is_item_visible_to_seat()`; route passes `student` (Seat object) directly to template instead of identity display context per MAP-UI-002 | `NEEDS_REWIRE` |
| Student purchases store item | `student_shop.html` (inline JS); `api.purchase_item` (`POST /api/purchase-item`) | `ACTION` | Student `CanonicalContext`; `class_id`; `seat_id`; passphrase verification | `FEAT-STOR-001` (`grant_type = PURCHASE`); Ledger posting through lawful Ledger FEAT | Writes `store_purchases`; writes one entitlement grant row per purchased unit with shared `correlation_id` (quantity 5 = 5 entitlement rows, per FEAT-STOR-001); Ledger `Transaction` with shared `correlation_id` | JSON `{status, message}`; subsequent GET reflects purchase in owned-items list | Code uses `@feat_shell("FEAT-STOR-002")` — wrong label, must be `FEAT-STOR-001`; `execute_store_purchase()` does not create per-unit entitlement grant rows; `StorePurchase.uses_remaining` and `bundle_remaining` are mutable counters that DOM-STORE-001 says must be derived; idempotency uses `client_purchase_id` mapped to `idempotency_key` — mechanism exists but contract needs verification against FEAT-STOR-001 replay semantics | `NEEDS_REWIRE` |
| Student requests item redemption | `student_shop.html` (inline JS); `api.use_item` (`POST /api/use-item`) | `ACTION` | Student `CanonicalContext`; `class_id`; `seat_id`; passphrase verification | `FEAT-STOR-002` for instant-use items (`consume_entitlement` writes terminal `entitlement_consumptions`); `DOM-STORE` for delayed items (redemption request only, no terminal event yet) | Writes `redemption_events` (`action = REQUEST`) for delayed items; for instant-use writes `entitlement_consumptions` as authoritative terminal event; for hall-pass items writes `entitlement_events` | JSON `{status, message}`; subsequent GET shows item status change | Code uses `@feat_shell("FEAT-STOR-005")` — wrong label, must be `FEAT-STOR-002`; `_append_redemption_audit_log()` writes `RedemptionEvent` with lowercase `action` values (`request`) instead of canonical `REQUEST`; route creates pending `Transaction` directly which crosses Ledger domain boundary; `StorePurchase.uses_remaining` decremented as mutable counter instead of deriving from `entitlement_consumptions` | `NEEDS_REWIRE` |
| Teacher approves redemption request | `admin_store.html` (inline JS); `api.approve_redemption` (`POST /api/approve-redemption`) | `ACTION` | Teacher `CanonicalContext`; `class_id`; actor teacher seat; target student seat | `FEAT-STOR-002` (`consume_entitlement`); approval writes authoritative terminal event to `entitlement_consumptions` | Writes `redemption_events` (`action = APPROVED`) as audit; writes `entitlement_consumptions` (`CONSUMED`) as authoritative terminal event | JSON `{status, message}`; subsequent GET removes item from pending list | Code uses `@feat_shell("FEAT-STOR-006")` — wrong label, must be `FEAT-STOR-002`; `execute_redemption_approval()` mutates `StorePurchase.status` directly as canonical state instead of writing `entitlement_consumptions` terminal event; no `entitlement_consumptions` row written at all | `NEEDS_REWIRE` |
| Teacher rejects redemption request | `admin_store.html` (inline JS); `api.reject_redemption` (`POST /api/reject-redemption`) | `ACTION` | Teacher `CanonicalContext`; `class_id`; actor teacher seat; target student seat | `FEAT-STOR-002` for redemption workflow only; rejection does NOT terminate the entitlement — the student retains the entitlement and may request redemption again | Writes `redemption_events` (`action = REJECTED`) as audit; does NOT write `entitlement_consumptions`; no Ledger refund because the entitlement is still held | JSON `{status, message}`; subsequent GET returns item to redeemable state, not consumed or refunded | Code uses `@feat_shell("FEAT-STOR-006")` — wrong label, must be `FEAT-STOR-002`; `execute_redemption_rejection()` mutates `StorePurchase.status` to `rejected` as if terminal and issues a Ledger refund — both are wrong because rejection preserves the entitlement; refund creates `Transaction` directly in Store FEAT which crosses Ledger domain boundary | `NEEDS_REWIRE` |
| Teacher adjusts hall-pass entitlements for a seat | `student_detail.html`; `admin.adjust_hall_pass_entitlements` (`POST /admin/student/<seat_id>/adjust-hall-pass-entitlements`) | `ACTION` | Teacher `CanonicalContext`; `class_id`; actor teacher seat; target student seat | `FEAT-STOR-001` (`grant_type = MANUAL_GRANT` for grants); `FEAT-STOR-002` (`revoke_entitlement` for removals) | Writes `entitlement_events` with signed `quantity_delta`; balance derived as `SUM(quantity_delta)` | Redirect to student detail page | Code uses `@feat_shell("FEAT-ENT-001")` — wrong label; `grant_hall_passes()` and `remove_hall_passes()` in `entitlement_service.py` write correct append-only events; no mutable counter; balance derivation is canonical | `NEEDS_REWIRE` |
| Teacher bulk adjusts hall-pass entitlements | `admin_students.html` (inline JS); `admin.bulk_adjust_hall_pass_entitlements` (`POST /admin/students/bulk-adjust-hall-pass-entitlements`) | `ACTION` | Teacher `CanonicalContext`; `class_id`; actor teacher seat; multiple target student seats | `FEAT-STOR-001` (`grant_type = MANUAL_GRANT` for grants); `FEAT-STOR-002` (`revoke_entitlement` for removals) | Writes `entitlement_events` per seat with signed `quantity_delta` | JSON `{status, message, updated, errors}` | Code uses `@feat_shell("FEAT-ENT-001")` — wrong label; same canonical append-only mechanism as single-seat adjust; iteration over seat list is correct | `NEEDS_REWIRE` |
| Teacher manages insurance catalog and policy configuration | `admin_insurance.html`, `admin_edit_insurance_policy.html`; `admin.insurance_management`, `admin.edit_insurance_policy`, `admin.deactivate_insurance_policy`, `admin.delete_insurance_policy`, `admin.mass_remove_policy` | `ACTION` | Teacher `CanonicalContext`; selected `class_id` | `FEAT-CLASS-003` for class-side insurance policy management; `DOM-CLASS-001` for policy lineage and deletion scheduling | Class-owned policy lineage via `policy_versions` / `policy_transitions`; downstream entitlement, obligation, and ledger tables remain unchanged | Policy editor contract, policy banner notifications, same-group switching, bundle eligibility across grouped tiers, and scheduled deletion boundary | Historical v1 behavior used a large `InsurancePolicyForm` and direct CRUD mutation of `InsurancePolicy`; the canonical v2 contract now requires class-configuration lineage, persistent student notifications, same-group switching, and deferred deletion until the last entitlement boundary | `NEEDS_REWIRE` |
| Teacher processes insurance claim | `admin_process_claim.html`, `admin_view_student_policy.html`; `admin.process_claim`, `admin.view_student_policy` | `ACTION` | Teacher `CanonicalContext`; selected `class_id`; `actor_role = teacher` per FEAT-STOR-003 | `FEAT-STOR-003` for claim approval/rejection; transaction-insurance compensation through lawful Ledger FEAT; productivity-insurance compensation through `DOM-PROD` → `payroll_event` with `payroll_type = MANUAL_CREDIT` | Templates exist on disk; routes abort 404 | Routes abort 404; templates reference `InsuranceClaim`/`InsuranceEnrollment`/`InsurancePolicy` which are not in canonical `models.py`; FEAT-STOR-003 defines the complete target claim lifecycle (submit → approve/reject with type-specific compensation) but no implementation surface exists; must be built from FEAT-STOR-003 specification | `NEEDS_REWIRE` |
| Student browses insurance marketplace and purchases initial coverage | `student_insurance_marketplace.html`; `student.insurance_marketplace`, `student.purchase_insurance` | `ACTION` | Student `CanonicalContext`; `class_id`; `seat_id` | `FEAT-STOR-001` for initial insurance acquisition (`grant_type = PURCHASE` with insurance capability); Obligations domain creates renewal assessment schedule upon purchase; obligation satisfaction causes `OBLIGATION` entitlement grant for ongoing coverage | Templates exist on disk; routes abort 404 | Routes abort 404; `insurance_purchase_feat.py` exists but writes `ObligationAssessment` for the purchase itself — initial acquisition must go through `FEAT-STOR-001` as a Store purchase; Obligations takes over only for renewal assessment/satisfaction after initial purchase | `NEEDS_REWIRE` |
| Student files insurance claim | `student_file_claim.html`; `student.file_claim` | `ACTION` | Student `CanonicalContext`; `class_id`; `seat_id`; `actor_role = student` per FEAT-STOR-003 | `FEAT-STOR-003` for claim submission (`submit_insurance_claim()` → `status = SUBMITTED`); claim does not consume the insurance entitlement | `insurance_claims` | `policy`, `enrollment`, `claims_this_period`, `eligible_transactions`, `form`, `errors` | Route now resolves the active insurance entitlement from the purchased policy item and calls `execute_claim_submission()` on POST; claim rows are created against `insurance_claims.entitlement_id`, and submission does not consume the entitlement | `REWIRED` |
| Student views insurance coverage and claim history | `student_view_policy.html`; `student.view_policy` | `OUTPUT` | Student `CanonicalContext`; `class_id`; `seat_id` | Read-only `DOM-STORE` for entitlement and coverage state; read-only Obligations for renewal status | `insurance_claims`, `entitlements`, `obligation_assessments` | `enrollment`, `policy`, `claims`, `now` | Route now resolves the active insurance entitlement from the policy item, derives claim history from `insurance_claims.entitlement_id`, and builds the coverage view from canonical entitlement + obligation rows | `REWIRED` |

---

## VI. Issue and Project Shape

GitHub issues should be generated from this map by capability group, not by template variable.

Recommended issue groups for the Productivity and Payroll slice:

1. Student productivity read model: dashboard plus `student_payroll.html`
2. Admin payroll read model: payroll dashboard plus history
3. Payroll command path: run payroll and manual credit through `FEAT-PROD-003`
4. Hall-pass read and command path: queue, approval, verification
5. Attendance session command path: student/API/admin tap routes through `FEAT-PROD-001`
6. Attendance support issue terminology: resolved to canonical attendance-session route and related-record reference

Recommended issue groups for the Store and Entitlements slice:

1. Item catalog CRUD: rewire `admin.store_management` POST, `admin.edit_store_item`, `admin.delete_store_item` to Class Configuration domain FEAT; fix current wrong FEAT labels
2. Store dashboard read model: `admin_store.html` GET — fix attribute mismatches on `StorePurchase`, remove GET-path FEAT wrapper, align view contract to MAP-UI-002 pipeline
3. Student store read model: `student_shop.html` GET — rename `student_items` to canonical view contract, replace raw `Seat` object with identity display context
4. Purchase command path: `api.purchase_item` through `FEAT-STOR-001` — fix FEAT label, create per-unit entitlement grant rows, eliminate `uses_remaining`/`bundle_remaining` mutable counters, verify idempotency replay
5. Redemption command path: `api.use_item`, `api.approve_redemption`, `api.reject_redemption` through `FEAT-STOR-002` — fix FEAT labels, write `entitlement_consumptions` terminal events on approval only, fix rejection to preserve entitlement (no refund, no terminal event), resolve Ledger domain boundary
6. Entitlement adjust command path: `adjust_hall_pass_entitlements` and `bulk_adjust_hall_pass_entitlements` — fix FEAT labels to `FEAT-STOR-001`/`FEAT-STOR-002`
7. Insurance acquisition: restore `student.insurance_marketplace` and `student.purchase_insurance` against `FEAT-STOR-001` for initial purchase; wire Obligations for renewal assessment/satisfaction → `OBLIGATION` entitlement grant
8. Insurance claims: restore `student.file_claim` against `FEAT-STOR-003` for submission; restore `admin.process_claim` and `admin.view_student_policy` for teacher approval/rejection with type-specific compensation (Ledger for transaction-insurance, `DOM-PROD` for productivity-insurance)
9. Insurance catalog and policy read: restore `admin.insurance_management` and `admin.edit_insurance_policy` for Class Configuration catalog definition and Obligations renewal schedule; restore `student.view_policy` for entitlement/coverage read model

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

## VII. Resolved Decisions

### Productivity and Payroll

1. Student dashboard attendance controls must not be a generic tap-in/tap-out pair. The canonical contextual button set is `Start Work`, `Break`, `Leave`, and `Return`, derived from current productivity and hall-pass state.
2. Public hall-pass verification remains outside live actor `CanonicalContext`. It uses a public capability token linked to the teacher's `user_id`; resolving that token grants read-only teacher-scoped hall-pass verification authority because a teacher may have one physical hall-pass verification surface shared among classes.
3. Direct teacher-to-student money send is `manual_credit` under `FEAT-PROD-003`. Teacher clicking `Run Payroll` is `payroll`, even if manually triggered by the teacher.

### Store and Entitlements

4. Entitlement terminal truth lives in `entitlement_consumptions`, not in `redemption_events` or `StorePurchase.status`. `redemption_events` is an append-only audit log of the redemption workflow (`REQUEST`, `APPROVED`, `REJECTED`); `entitlement_consumptions` holds the authoritative terminal events (`CONSUMED`, `EXPIRED`, `REVOKED`). `StorePurchase.status` may remain as a denormalized read cache only after the canonical derivation from `entitlement_consumptions` is proven.
5. Rejected redemption does not terminate the entitlement. A teacher rejecting a redemption request means "I will not fulfill this now" — the student retains the entitlement and may request redemption again. Only approval writes a `CONSUMED` terminal event to `entitlement_consumptions`. The current code's behavior of marking `StorePurchase.status = rejected` and issuing a Ledger refund on rejection is wrong on both counts.
6. FEAT-STOR-001 atomicity applies to entitlement grants, not `StorePurchase` rows. A quantity-5 purchase creates one `StorePurchase` record but five distinct entitlement grant rows with a shared `correlation_id`. The current code does not create per-unit entitlement grants.
7. `StorePurchase.uses_remaining` and `bundle_remaining` are mutable counters prohibited by DOM-STORE-001. Remaining uses must be derived from entitlement grant count minus `entitlement_consumptions` terminal event count. These columns must be removed or deprecated.
8. `RedemptionEvent.action` values must use uppercase enum values (`REQUEST`, `APPROVED`, `REJECTED`) matching DOM-STORE-001, not lowercase.
9. Store FEATs must not create `Transaction` records directly. Ledger writes must go through lawful Ledger FEAT with a shared `correlation_id`. The current redemption rejection refund path in `redemption_disposition_feat.py` crosses this boundary — and is additionally wrong because rejection should not trigger a refund at all (see decision 5).
10. Hall-pass entitlement grants by teacher are `MANUAL_GRANT` under `FEAT-STOR-001`; removals are `revoke_entitlement()` under `FEAT-STOR-002`. The current `FEAT-ENT-001` label does not exist in the canonical FEAT set and must be replaced.
11. Store item catalog CRUD (create, edit, deactivate) is Class Configuration, not a Store FEAT. `store_items` and `store_item_visibility` are catalog definition tables. The current code's `FEATContext("FEAT-STOR-001")` and `FEATContext("FEAT-STOR-003")` labels on these routes are wrong.
12. Insurance initial acquisition is a Store purchase through `FEAT-STOR-001`. Renewal assessment and satisfaction belong to the Obligations domain. When an obligation is satisfied (e.g., recurring premium paid), Obligations creates an `OBLIGATION` entitlement grant — Store does not own the renewal cycle. Insurance capabilities are surviving surfaces that must be rewired, not deleted.
13. Insurance claim lifecycle is governed by `FEAT-STOR-003`. Claim activity does not consume the insurance entitlement. Transaction-insurance compensation goes through lawful Ledger FEAT; productivity-insurance compensation goes through `DOM-PROD` as a `payroll_event` with `payroll_type = MANUAL_CREDIT`. Store must not directly create payroll events or Ledger transactions for insurance compensation.

---

## VIII. Amendment

Revisions to this map must update the version, preserve the row contract, and cite any newly audited template-route source documents used to add rows.
