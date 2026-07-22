# Jinja Template Interface Audit

**Date:** 2026-07-19
**Scope:** All ~110 Jinja templates in `templates/`
**Audit Type:** Template-layer interface verification (not domain/route correctness)
**Branch:** `codex/v2.0`

---

## Summary

| Status | Count | Description |
|--------|-------|-------------|
| **BROKEN** | 51 | Will crash or produce wrong output at runtime |
| **SUSPECT** | 6 | May silently produce wrong results |
| **DEAD** | 24 | Never rendered / orphaned templates |
| **LEGACY** | 1 | Still wired to v1 interface (cosmetic) |

**Root cause:** The v1-to-v2 identity migration changed routes to pass `Seat`/`User` objects, but templates still access legacy `Student`/`Admin` model attributes.

---

## BROKEN -- Will crash or produce wrong output at runtime

### Seat/Student attribute mismatch (student_detail.html)

| # | Line(s) | Jinja Code | Root Cause |
|---|---------|-----------|------------|
| 1 | 2,3,37,190,290,804 | `student.full_name` | Resolved 2026-07-22: route now supplies `student_full_name` from `IdentityProfile.full_name` |
| 2 | 804 | `student.display_first_name` | Resolved 2026-07-22: route now supplies `student_first_name` from `IdentityProfile.first_name` |
| 3 | 810 | `student.display_last_name` | Resolved 2026-07-22: route now supplies `student_last_name` from `IdentityProfile.last_name` |
| 4 | 38 | `student.is_teacher_shadow` | Resolved 2026-07-22: teacher-shadow badge removed from this v2 student-detail contract |
| 5 | 91,748 | `student.hall_passes` | Resolved 2026-07-21: student detail now receives route-supplied `hall_pass_balance` from entitlement projection |
| 6 | 195 | `student.has_completed_setup` | Resolved 2026-07-22: route now supplies `student_has_completed_setup` from the bound `User` |
| 7 | 280 | `student.recovery_status` | Resolved 2026-07-22: stale recovery-status branch removed from this v2 student-detail contract |
| 8 | 251 | `student.reset_code` | Resolved 2026-07-22: route now supplies `reset_code` from the bound `User` |
| 9 | 266-267 | `student.reset_code_expires_at` | Resolved 2026-07-22: route now supplies `reset_code_expires_at` from the bound `User` |
| 10 | 567 | `student.tap_events` | Resolved 2026-07-22: template consumes route-supplied canonical `attendance_events`; no `tap_events` relationship remains |

### Seat/Student attribute mismatch (other student templates)

| # | Template | Line(s) | Jinja Code | Root Cause |
|---|----------|---------|-----------|------------|
| 11 | `student_dashboard.html` | 11 | `student.display_first_name` | Resolved 2026-07-21: `display_metadata` context now supplies `student_display_first_name` from `IdentityProfile` |
| 12 | `student_dashboard.html` | 157 | `student.hall_passes` | Resolved 2026-07-21: route now supplies `hall_pass_balance` from entitlement service |
| 13 | `layout_student.html` | 108 | `student.display_first_name\|upper` | Resolved 2026-07-21: fallback now uses `student_display_first_name` from `display_metadata` |

### User/Admin attribute mismatch (admin_settings.html)

| # | Line(s) | Jinja Code | Root Cause |
|---|---------|-----------|------------|
| 14 | 38,42,102 | `admin.teacher_public_id` | Not on User model |
| 15 | 38,42 | `admin.get_display_name()` | User has `get_display_username()`, not `get_display_name()` |
| 16 | 111 | `admin.last_login` | Not on User model |
| 17 | 60-77 | `block_data.block`, `block_data.class_label` | Route passes tuples, not objects. `AttributeError` on every iteration |
| 18 | 37 | `admin.display_name` | Not on User (it is on ClassEconomy). Renders empty silently |

### DOM ID mismatch (admin_account_delete.html)

| # | Line(s) | Jinja Code | Root Cause |
|---|---------|-----------|------------|
| 19 | 26/91 | JS `getElementById('deletion-request-form')` | Form id is `account-delete-form`. Timed-delete safety gate is non-functional |

### HallPassLog relationship mismatch (admin_hall_pass.html)

| # | Line(s) | Jinja Code | Root Cause |
|---|---------|-----------|------------|
| 20 | 206,235,259 | `req.student.full_name` | Resolved 2026-07-21: template now uses `req.student_name`; route supplies canonical display rows from `HallPassLog.requested_by_seat.identity_profile` |

### StorePurchase attribute mismatch (admin_store.html)

| # | Line(s) | Jinja Code | Root Cause |
|---|---------|-----------|------------|
| 21 | 245 | `student_item.redemption_date` | StorePurchase has `purchased_at`, not `redemption_date` |
| 22 | 247 | `student_item.redemption_details` | Not on StorePurchase |
| 23 | 306 | `student_item.purchase_date` | StorePurchase has `purchased_at`, not `purchase_date` |

### Variable name mismatches (admin routes)

| # | Template | Jinja Code | Root Cause |
|---|----------|-----------|------------|
| 24 | `admin_username_migration.html` | `legacy_username` | Route passes `current_username` |
| 25 | `admin_support_tickets.html` | `class_scope_options` | Never supplied by route or context processor. `UndefinedError` |
| 26 | `admin_support_tickets.html` | `entry.scope_join_code` | Route supplies `scope_class_id` instead |

### Missing Issue model attributes

| # | Template | Jinja Code | Root Cause |
|---|----------|-----------|------------|
| 27 | `admin_issues_queue.html` | `issue.class_label`, `issue.student_display_name` | Not on Issue model |
| 28 | `admin_view_issue.html` | `issue.class_label`, `issue.student_display_name` | Not on Issue model |

### Announcement form edit path

| # | Template | Jinja Code | Root Cause |
|---|----------|-----------|------------|
| 29 | `admin_announcement_form.html` | `teacher_block.block`, `.get_class_label()` | Route passes string, not object |
| 30 | `admin_announcement_form.html` | `active_join_code`, `active_class_label` | Not passed by edit route |

### Analytics AuditEvent mismatch

| # | Template | Jinja Code | Root Cause |
|---|----------|-----------|------------|
| 31 | `admin_analytics_dashboard.html` | `event.event_date`, `.event_type`, `.description`, `.old_value`, `.new_value` | AuditEvent has different column names (`created_at_utc`, `operation`, `table_name`) |
| 32 | `admin_analytics_events.html` | `class_option.block`, `.label` | Route dicts only have `class_id`/`join_code` |
| 33 | `admin_analytics_events.html` | `event.event_type`, `.description`, `.event_date` etc. | Same AuditEvent mismatch |
| 34 | `admin_analytics_student_detail.html` | `student.name` | Resolved 2026-07-22: route now supplies explicit `student_name` from the selected seat's `IdentityProfile` |
| 35 | `admin_analytics_student_detail.html` | `txn.balance_after_transaction` | Resolved 2026-07-22: route now supplies recent-transaction view rows with derived `balance_after_transaction` |

### System admin dashboard variable mismatch

| # | Template | Line(s) | Jinja Code | Root Cause |
|---|----------|---------|-----------|------------|
| 36 | `system_admin_dashboard.html` | 17 | `total_teachers` | Route passes `total_admins`. Always shows 0 |
| 37 | `system_admin_dashboard.html` | 116-118 | `recent_teachers` | Route passes `recent_admins`. "No teachers" always displayed |
| 38 | `system_admin_dashboard.html` | 128 | `teacher.get_sysadmin_display_name()` | Method does not exist on User. Latent -- blocked by #37 |
| 39 | `system_admin_dashboard.html` | 167-186 | `error.error_type`, `.error_message`, `.request_method`, `.request_path`, `.timestamp` | Route passes `operational_events` with different schema. All render empty |

### Sysadmin Issue/report attribute mismatches

| # | Template | Line(s) | Jinja Code | Root Cause |
|---|----------|---------|-----------|------------|
| 40 | `sysadmin_support_tickets.html` | 293 | `issue.teacher.get_sysadmin_display_name()` | Issue has no `teacher` relationship; User has no `get_sysadmin_display_name()` |
| 41 | `sysadmin_support_tickets.html` | 297 | `issue.class_label` | Not on Issue model |
| 42 | `sysadmin_support_tickets.html` | 146-149 | `report.report_type == 'bug'` | Route passes integer `category_id`, not string. Comparison always false |
| 43 | `sysadmin_view_escalated_issue.html` | 35 | `issue.teacher.get_sysadmin_display_name()` | Same as #40 |
| 44 | `sysadmin_view_escalated_issue.html` | 36-37 | `issue.class_label` | Not on Issue model |
| 45 | `sysadmin_user_report_detail.html` | 58 | `report.anonymous_code[:16]` | Not on Issue. `UndefinedError` crash |
| 46 | `sysadmin_user_report_detail.html` | 24-27 | `report.report_type` | Not on Issue. Comparisons always false |
| 47 | `sysadmin_user_report_detail.html` | 81,86 | `report.title`, `report.description` | Issue has `student_expected_outcome`, `student_explanation` |
| 48 | `sysadmin_user_report_detail.html` | 108,112 | `report.admin_notes` | Issue has `sysadmin_notes` |
| 49 | `sysadmin_user_report_detail.html` | 117,119 | `report.reviewed_at` | Issue has `teacher_reviewed_at` |
| 50 | `sysadmin_user_report_detail.html` | 182 | ORM query on `anonymous_code` | Column does not exist. **SQLAlchemy crash** |

### Route crash preventing render

| # | Template | Jinja Code | Root Cause |
|---|----------|-----------|------------|
| 51 | `student_payroll.html` (route) | Route L1214: `sess.period` | Resolved 2026-07-21: route groups canonical `AttendanceSession` rows by current class block instead of `sess.period` |

---

## SUSPECT -- May silently produce wrong results

| # | Template | Line(s) | Jinja Code | Finding |
|---|----------|---------|-----------|---------|
| S1 | `admin_store.html` | 486 | `payroll_settings.expected_weekly_hours` | Not passed by store route; silently defaults to 5.0 |
| S2 | `admin_payroll_history.html` | 50 | `entry.student` | Resolved 2026-07-21: template now reads `entry.student_name`; route now builds detailed history from `PayrollEvent` business records with Ledger amount lookup by `correlation_id` |
| S3 | `admin_issues_queue.html` | -- | `issue.category.name` | Lazy load may fail if no eager load configured |
| S4 | `admin_view_issue.html` | -- | `issue.context_snapshot.transaction` | Depends on JSON shape at creation time |
| S5 | `admin_analytics_dashboard.html` | -- | `snapshot.*` attributes | Unverified AnalyticsSnapshot schema |
| S6 | `student_detail.html` | 567 | `student.tap_events` | Injected as empty list only when table missing |

---

## DEAD -- Never rendered / orphaned templates

| # | Template | Reason |
|---|----------|--------|
| D1 | `admin_shadow_onboard.html` | No route renders it; `url_for('admin.shadow_student_onboard')` does not exist |
| D2 | `admin_nav.html` | Never included by any template |
| D3 | `admin_transactions.html` | Route redirects to `admin.banking` before rendering |
| D4 | `admin_insurance.html` | Route aborts 404 before render |
| D5 | `admin_edit_insurance_policy.html` | Route aborts 404 |
| D6 | `admin_process_claim.html` | Route aborts 404 |
| D7 | `admin_view_student_policy.html` | Route aborts 404 |
| D8 | `admin_claim_students.html` | No route renders it |
| D9 | `admin_backfill_join_codes.html` | No route renders it |
| D10 | `admin_help_support.html` | Superseded by `admin_support_tickets.html` |
| D11 | `student_complete_profile.html` | No route renders it |
| D12 | `student_help_support.html` | Superseded by `student_help_support_new.html` |
| D13 | `student_insurance_marketplace.html` | Route aborts 404 |
| D14 | `student_file_claim.html` | Route aborts 404 |
| D15 | `student_view_policy.html` | Route aborts 404 |
| D16 | `student/recovery/reset_form.html` | Recovery flow redirects elsewhere |
| D17 | `student/recovery/identity_update.html` | No route renders it |
| D18 | `system_admin_username_migration.html` | No route exists |
| D19 | `hall_pass_verification.html` | No route renders it |
| D20 | `error_400.html` | No `errorhandler(400)` registered |
| D21 | `error_401.html` | No `errorhandler(401)` registered |
| D22 | `error_403.html` | No `errorhandler(403)` registered |
| D23 | `error_404.html` | No `errorhandler(404)` registered |
| D24 | `error_503.html` | No `errorhandler(503)` registered |

---

## LEGACY -- Still wired to v1 interface

| # | Template | Finding |
|---|----------|---------|
| L1 | `system_admin_manage_teachers.html` | `teacher.teacher_public_id` -- dead code branch, falls through to `teacher.username` via Jinja `or` chain |

---

## Templates Likely to Crash

These templates will raise exceptions during rendering:

| Template | Crash Trigger | Exception Type |
|----------|--------------|----------------|
| `student_detail.html` | Any render -- `student.full_name` on line 2 | `AttributeError` on Seat |
| `admin_settings.html` | Any render -- `admin.teacher_public_id` on line 38 | `AttributeError` on User |
| `admin_hall_pass.html` | When pending/approved requests exist -- `req.student.full_name` | Resolved 2026-07-21: canonical hall-pass rows now expose `student_name`; no template relationship dereference |
| `admin_store.html` | Viewing redeemed items -- `student_item.redemption_date` | `AttributeError` on StorePurchase |
| `admin_support_tickets.html` | Any render -- `class_scope_options` undefined | `UndefinedError` |
| `admin_issues_queue.html` | When issues exist -- `issue.class_label` | `AttributeError` on Issue |
| `admin_view_issue.html` | Any render -- `issue.class_label` | `AttributeError` on Issue |
| `admin_analytics_dashboard.html` | When audit events exist -- `event.event_date` | `AttributeError` on AuditEvent |
| `admin_analytics_events.html` | When events exist -- same AuditEvent attrs | `AttributeError` |
| `admin_analytics_student_detail.html` | Any render -- `student.name` on Seat | Resolved 2026-07-22: template reads route-supplied `student_name` |
| `sysadmin_view_escalated_issue.html` | Any render -- `issue.teacher.get_sysadmin_display_name()` | `AttributeError` |
| `sysadmin_user_report_detail.html` | Any render -- `report.anonymous_code[:16]` | `UndefinedError` |
| `admin_announcement_form.html` | Edit path -- `teacher_block.block` on string | `AttributeError` |

---

## Broken Navigation and Actions

| Template | Element | Target | Problem |
|----------|---------|--------|---------|
| `admin_account_delete.html` | JS delete gate | `getElementById('deletion-request-form')` | ID mismatch -- form is `account-delete-form`; safety timer never activates |
| `admin_shadow_onboard.html` | Form action | `url_for('admin.shadow_student_onboard')` | Endpoint does not exist -- `BuildError` |
| `admin_support_tickets.html` | Class filter dropdown | `class_scope_options` loop | Variable never supplied -- dropdown empty |
| `admin_username_migration.html` | Display field | `legacy_username` | Route passes `current_username` -- field blank |
| `admin_announcement_form.html` | Edit path | `active_join_code`, `active_class_label` | Not passed -- renders empty |
| `sysadmin_support_tickets.html` | Report type badges | `report.report_type == 'bug'` | Integer vs string comparison -- always wrong badge |
| `sysadmin_user_report_detail.html` | Related reports link | ORM query on `anonymous_code` | Column does not exist -- `InvalidRequestError` |

---

## Remaining v1 Template Interfaces

The dominant pattern: routes now pass `Seat` objects where templates still expect `Student` model attributes.

| Legacy Interface | Templates Affected | v1 Expectation | Current Reality |
|------------------|--------------------|----------------|-----------------|
| `student.full_name` | student_detail, student_dashboard | `Student.full_name` property | Seat has no `full_name`; use `seat.identity_profile.full_name` |
| `student.display_first_name` | student_detail, student_dashboard, layout_student | `Student.display_first_name` | Not on Seat; use `seat.identity_profile.first_name` |
| `student.display_last_name` | student_detail | `Student.display_last_name` | Not on Seat |
| `student.hall_passes` | student_detail, student_dashboard, admin_students | `Student.hall_passes` column | Resolved 2026-07-21: affected templates now use route-supplied entitlement projections (`hall_pass_balance` or `student_hall_pass_balances_by_seat_id`) |
| `student.has_completed_setup` | student_detail | `Student.has_completed_setup` | Not on Seat |
| `student.is_teacher_shadow` | student_detail | `Student.is_teacher_shadow` | Not on Seat |
| `student.recovery_status` | student_detail | `Student.recovery_status` | Not on Seat |
| `student.reset_code` / `.reset_code_expires_at` | student_detail | `Student.reset_code` | On `User`, not `Seat` |
| `req.student.full_name` | admin_hall_pass | `HallPassLog.student` relationship | Resolved 2026-07-21: replaced by route-supplied `student_name` from requested seat IdentityProfile |
| `student_item.redemption_date` / `.purchase_date` | admin_store | `StudentItem` columns | `StorePurchase` has `purchased_at` |
| `admin.get_display_name()` / `.teacher_public_id` / `.last_login` | admin_settings | Legacy `Admin` model methods | `User` model has different interface |
| `teacher.get_sysadmin_display_name()` | sysadmin_dashboard, sysadmin_support_tickets, sysadmin_view_escalated_issue | Legacy method | `User` has `get_display_username()` |
| `report.anonymous_code` / `.title` / `.description` / `.admin_notes` / `.reviewed_at` | sysadmin_user_report_detail | Legacy report model | `Issue` model has different column names |
| `issue.teacher` | sysadmin_support_tickets, sysadmin_view_escalated_issue | Legacy relationship | `Issue` has no `teacher` relationship |

---

## Template Migration Checklist

### Critical -- will crash; fix first

- [x] **`student_detail.html`** -- Resolved 2026-07-22: route supplies explicit Seat/IdentityProfile/User display/account fields (`student_full_name`, `student_first_name`, `student_last_name`, `student_notes`, `student_has_completed_setup`, `reset_code`, `reset_code_expires_at`); template no longer dereferences legacy Student full/display/setup/recovery/tap-event attributes; hall-pass balance remains route-supplied from entitlement projection
- [x] **`student_dashboard.html`** -- Replace `student.display_first_name`, `student.hall_passes` with Seat-compatible accessors
- [x] **`student_dashboard.html`** (`/api/tap` standard start/done path) -- Resolved 2026-07-21: student Start Work and Done for the Day path now writes append-only `AttendanceSession` rows through `FEAT-PROD-001`; hall-pass request flow remains a separate PROD command surface
- [x] **`layout_student.html`** -- Replace `student.display_first_name` fallback path
- [ ] **`admin_settings.html`** -- Replace `admin.teacher_public_id`, `admin.get_display_name()`, `admin.last_login`, `admin.display_name` with User equivalents; fix `blocks` iteration to unpack tuples instead of accessing `.block`/`.class_label`
- [ ] **`admin_account_delete.html`** -- Fix JS `getElementById` to match actual form id `account-delete-form`
- [x] **`admin_hall_pass.html`** -- Replace `req.student.full_name` with route-supplied canonical `student_name`
- [ ] **`admin_store.html`** -- Replace `student_item.redemption_date` with `purchased_at`, remove `redemption_details`, replace `purchase_date` with `purchased_at`
- [ ] **`admin_support_tickets.html`** -- Supply `class_scope_options` from route OR remove filter; fix `entry.scope_join_code` to `scope_class_id`
- [ ] **`admin_issues_queue.html`** -- Add `class_label`/`student_display_name` to route context or template
- [ ] **`admin_view_issue.html`** -- Same as issues_queue
- [ ] **`admin_analytics_dashboard.html`** -- Map AuditEvent columns to template expectations
- [ ] **`admin_analytics_events.html`** -- Same AuditEvent fix plus fix `class_option` dict keys
- [x] **`admin_analytics_student_detail.html`** -- Resolved 2026-07-22: template reads explicit `student_name`; route supplies transaction view rows with derived `balance_after_transaction`
- [ ] **`admin_announcement_form.html`** (edit path) -- Fix `teacher_block` to be an object or restructure template; pass `active_join_code`/`active_class_label`
- [ ] **`system_admin_dashboard.html`** -- Rename `total_admins` to `total_teachers`, `recent_admins` to `recent_teachers` (or vice versa); fix error card attributes
- [ ] **`sysadmin_view_escalated_issue.html`** -- Replace `issue.teacher.get_sysadmin_display_name()`, `issue.class_label`
- [ ] **`sysadmin_support_tickets.html`** -- Replace `issue.teacher`, `issue.class_label`; fix `report_type` integer-vs-string
- [ ] **`sysadmin_user_report_detail.html`** -- Wholesale rewrite: `anonymous_code` to `actor_public_id`, `title` to `student_expected_outcome`, `description` to `student_explanation`, `admin_notes` to `sysadmin_notes`, `reviewed_at` to `teacher_reviewed_at`, remove `ip_address`/`user_agent`
- [ ] **`admin_username_migration.html`** -- Replace `legacy_username` with `current_username`
- [x] **`student_payroll.html`** (route) -- Fix `sess.period` in route code before template can render
- [x] **`admin_payroll.html`** (GET read model) -- Resolved 2026-07-21: recent activity, history tab, last-payroll stats, and total earned now derive from `PayrollEvent` with Ledger amount lookup by `correlation_id`; legacy payroll void controls removed from this template surface
- [x] **`admin_payroll.html`** (`admin.run_payroll`) -- Resolved 2026-07-21: attendance-based payroll action now records `payroll` rows through `FEAT-PROD-003`; route no longer uses `FEAT-LED-004`, ledger adjustment batching, or legacy payroll transaction history as the payroll boundary
- [x] **`admin_payroll.html`** (`admin.payroll_manual_payment`) -- Resolved 2026-07-21: manual credit action now calls `FEAT-PROD-003`; template no longer exposes deduction or account-type controls because manual debits/fines belong to Obligations

### Housekeeping -- dead templates to remove

- [ ] Delete `admin_shadow_onboard.html`
- [ ] Delete `admin_nav.html`
- [ ] Delete `admin_transactions.html`
- [ ] Delete `admin_claim_students.html`
- [ ] Delete `admin_backfill_join_codes.html`
- [ ] Delete `admin_help_support.html`
- [ ] Delete `student_complete_profile.html`
- [ ] Delete `student_help_support.html`
- [ ] Delete `student/recovery/reset_form.html`
- [ ] Delete `student/recovery/identity_update.html`
- [x] Delete `hall_pass_verification.html` -- Resolved 2026-07-22: legacy orphan template is absent; public verification is consolidated on `hall_pass_verify.html`
- [ ] Delete `system_admin_username_migration.html`
- [ ] Register error handlers for `error_400.html`, `error_401.html`, `error_403.html`, `error_404.html`, `error_503.html` -- or delete them
- [ ] Evaluate insurance templates behind abort(404): `admin_insurance.html`, `admin_edit_insurance_policy.html`, `admin_process_claim.html`, `admin_view_student_policy.html`, `student_insurance_marketplace.html`, `student_file_claim.html`, `student_view_policy.html` -- delete or restore

### Low priority -- suspect / cosmetic

- [ ] **`admin_store.html`** -- Pass `payroll_settings` from store route (currently defaults to 5.0)
- [x] **`admin_payroll_history.html`** -- Remove dead `entry.student` branch
- [ ] **`system_admin_manage_teachers.html`** -- Remove dead `teacher.teacher_public_id` branch
