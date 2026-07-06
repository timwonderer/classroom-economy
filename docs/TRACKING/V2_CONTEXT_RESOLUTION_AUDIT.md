# V2 Context Resolution Audit

**Status:** In Progress
**Started:** 2026-06-27
**Scope:** Waves 1–8 (all code landed through Store domain)
**Auditor:** Claude + Timothy

---

## Audit Invariant

> Context is resolved **once** at boundary via `context_resolver.resolve_canonical_context()`, producing an immutable `CanonicalContext(user_id, class_id, seat_id, actor_role)`. This object is used for the duration of all business logic until session expiry or transaction completion. **No downstream code may reconstruct, infer, or bridge identity past boundary. No extinct runtime identity (`admin_id`, `teacher_id`, `student_id`, `sysadmin_id`) may appear in any authority, scoping, or resolution path.**

---

## Violation Classes

| Class | Name | Description | Severity |
|-------|------|-------------|----------|
| **A** | Use of extinct runtime identity | Code reads `session.get('admin_id')`, `session.get('student_id')`, `session.get('sysadmin_id')`, or uses `teacher_id` / `admin_id` / `student_id` as identity — all extinct under v2 | CRITICAL |
| **B** | `join_code` used as runtime authority | Code uses `join_code` as a scoping or authority key downstream of boundary instead of `class_id` from canonical context | HIGH |
| **C** | Multiple context resolutions per request | Same handler or helper calls `resolve_canonical_context()` more than once | LOW |
| **D** | Mixed resolution patterns | Route uses both `resolve_canonical_context()` and `get_current_seat()`/`get_current_class_id()` redundantly | LOW |
| **E** | Boundary-only / false positive | Login flows writing session keys, auth decorators enforcing session gates, `context_resolver.py` itself | EXEMPT |

---

## Pass 1: Use of Extinct Runtime Identity (Class A)

### Summary

**Current runtime status:** zero extinct-session-identity reads remain in `app/` request paths. The startup-critical identity cleanup is complete; the remaining legacy identity hits are now concentrated in tests, model/backfill residue, and non-session FK naming.
Bridge-service imports were also removed from the active admin/recovery paths I touched during the latest cleanup pass; the app still starts cleanly after that checkpoint.

### Breakdown by File

| File | Occurrences | `resolve_canonical_context()` calls | Status |
|------|-------------|-------------------------------------|--------|
| `admin.py` | 0 | 0 | Canonical runtime path; no startup-blocking legacy identity reads remain |
| `system_admin.py` | 0 | 0 | Canonical runtime path; no startup-blocking legacy identity reads remain |
| `analytics.py` | 0 | 5 (separate handlers) | Canonical runtime path |
| `recovery.py` | 0 | 0 | Canonical runtime path |

### Canonical-compliant files (for reference)

| File | `resolve_canonical_context()` calls | Extinct identity reads | Status |
|------|-------------------------------------|------------------------|--------|
| `student.py` | 19 handlers + 4 helpers | 1 (login write — Class E) | Largely canonical |
| `api.py` | 7 | 0 | Canonical |
| `analytics.py` | 5 | 1 | Mostly canonical |

### admin.py — Historical Violation Register

This register is retained for traceability only. The `app/routes/admin.py` request path no longer reads extinct session identity in the current tree.

#### Identity reconstruction in route handlers (51 sites)

These handlers read `session.get('admin_id')` past the `@admin_required` boundary to determine "who am I":

| Line | Handler |
|------|---------|
| 347 | `_get_admin_owned_join_codes` |
| 511 | `dashboard` |
| 642 | `select_class` |
| 655 | `select_class` |
| 705 | `create_class` |
| 730 | `create_class` |
| 841 | `handle_admin_login_success` |
| 857 | `handle_admin_login_success` |
| 1074 | `manage_students` |
| 1754 | `add_student` |
| 2938 | `delete_student` |
| 4015 | `admin_store` |
| 4381 | `add_store_item` |
| 4588 | `edit_store_item` |
| 4648 | `delete_store_item` |
| 4846 | `inventory_management` |
| 5212 | `payroll` |
| 5277 | `run_payroll` |
| 5333 | `payroll_settings` |
| 5391 | `update_payroll_settings` |
| 5462 | `payroll_settings_copy` |
| 5793 | `rent_settings_update` |
| 6128 | `view_student` |
| 6204 | `edit_student` |
| 6245 | `student_transactions` |
| 6481 | `admin_adjustment` |
| 7407 | `insurance_settings` |
| 7845 | `view_insurance_claims` |
| 8201 | `hall_pass` |
| 8279 | `hall_pass_setup` |
| 8298 | `update_economy_policy` |
| 8334 | `apply_economy_rebalance` |
| 8452 | `economy_health` |
| 9737 | `attendance_log` |
| 9771 | `upload_students` |
| 10285 | `export_class_roster` |
| 10335 | `export_students` |
| 10517 | `check_tapped_out_daily_limit` |
| 10628 | `tap_out_all` |
| 10767 | `tap_in_all` |
| 10940 | `banking` |
| 11152 | `banking_settings_update` |
| 11267 | `account_delete` |
| 11332 | `help_support` |
| 11524 | `feature_settings` |
| 11568 | `update_period_feature_settings` |
| 11617 | `copy_feature_settings` |
| 11934 | `onboarding_status` |
| 12200 | `calculate_cwi` |
| 12305 | `economy_analyze` |
| 12441 | `update_feature_price` |

#### Query scoping via extinct identity (10 sites)

These use `admin_id` as `teacher_id` to scope database queries:

| Line | Handler | Query pattern |
|------|---------|---------------|
| 857 | `handle_admin_login_success` | `filter_by(teacher_id=admin_id)` |
| 1074 | `manage_students` | `filter_by(teacher_id=admin_id)` |
| 3177 | `view_student_detail` | `filter_by(teacher_id=admin_id)` |
| 4565 | `edit_store_item` | `filter_by(teacher_id=admin_id)` |
| 7473 | `insurance_settings` | scope check |
| 7592 | `update_insurance_settings` | scope check |
| 7644 | `update_insurance_settings` | scope check |
| 7646 | `update_insurance_settings` | scope check |
| 8628 | `payroll_history` | `_get_admin_owned_join_codes(admin_id)` |
| 10988 | `banking_transaction_log` | `_get_admin_owned_join_codes(admin_id)` |
| 9722 | `attendance_log` | `filter_by(teacher_id=admin_id)` |
| 11332 | `help_support` | scope resolution |

#### Ownership/authorization via extinct identity (4 sites)

| Line | Handler | Pattern |
|------|---------|---------|
| 7671 | `update_insurance_settings` | `enrollment.teacher_id != admin_id` |
| 7691 | `update_insurance_settings` | ownership guard |
| 7779 | `process_insurance_claim` | ownership guard |
| 12563 | `start_passkey_registration` | ownership verification |

#### Display/logging/audit (22 sites)

| Line | Handler |
|------|---------|
| 1714 | `add_student` |
| 5152 | `payroll` |
| 5187 | `payroll` |
| 5536 | `run_payroll` |
| 5650 | `rent_management` |
| 5688 | `rent_management` |
| 7156 | `insurance_management` |
| 7265 | `insurance_management` |
| 8083 | `process_claim` |
| 8730 | `run_payroll_legacy` |
| 11697 | `announcements` |
| 11736 | `announcement_create` |
| 11795 | `announcement_edit` |
| 11857 | `announcement_delete` |
| 11896 | `announcement_toggle` |
| 12596 | `finish_passkey_registration` |
| 12744 | `passkey_list` |
| 12767 | `passkey_delete` |
| 12789 | `passkey_settings` |
| 12815 | `issues_queue` |
| 12873 | `view_issue` |
| 12901 | `resolve_issue` |
| 13031 | `escalate_issue` |
| 13093 | `close_issue` |

#### Boundary establishment (Class E — exempt, 2 sites)

| Line | Handler | Context |
|------|---------|---------|
| 3248 | `login` | `session["admin_id"] = admin.id` — login write |
| 12714 | `passkey_login_finish` | `session['admin_id'] = admin.id` — login write |

### system_admin.py — Historical Violation Register

| Line | Handler | Pattern |
|------|---------|---------|
| 1373 | `manage_admins` | `session.get('sysadmin_id')` — identity reconstruction |
| 1667 | `system_settings` | `session.get('sysadmin_id')` — identity reconstruction |
| 1717 | `update_system_settings` | `session.get('sysadmin_id')` — identity reconstruction |
| 1924 | `audit_log` | `session.get('sysadmin_id')` — identity reconstruction |

### analytics.py — Historical Violation Register

| Line | Handler | Pattern |
|------|---------|---------|
| 514 | `api_economy_health` | `session.get('admin_id')` as `teacher_id` — identity reconstruction |

### recovery.py — Historical Violation Register

| Line | Handler | Pattern |
|------|---------|---------|
| 82 | `initiate_recovery` | `session.get('admin_id')` — audit logging |
| 88 | `initiate_recovery` | `session.get("admin_id")` — audit logging |

### auth.py — Legacy bridge functions (Class A)

These are **not exempt**. Bridge functions between extinct and canonical identity are themselves violations:

| Function | Line(s) | Pattern |
|----------|---------|---------|
| `get_current_admin()` | 619–641 | Historical legacy helper (removed) |
| `get_current_system_admin()` | 644–666 | Historical legacy helper (removed) |
| `get_logged_in_student()` | 591–616 | Historical legacy helper (removed) |
| `resolve_admin_shadow_for_user()` | 310–316 | Historical legacy helper (removed) |
| `resolve_student_shadow_for_user()` | 329–354 | Historical legacy helper (removed) |
| `resolve_system_admin_shadow_for_user()` | 319–325 | Bridges `User` → `SystemAdmin` |

---

## Pass 1 — Class C: Multiple Context Resolutions

### 1 violation found

| File | Function | Lines | Issue |
|------|----------|-------|-------|
| `student.py` | `is_feature_enabled()` | 481, 485 | Calls `resolve_canonical_context()` twice in same function body |

### 5 helper-level resolves (borderline)

These helpers resolve context internally rather than receiving it as an argument:

| File | Function | Line |
|------|----------|------|
| `student.py` | `get_current_join_code()` | 436 |
| `student.py` | `get_feature_settings_for_student()` | 454 |
| `student.py` | `apply_savings_interest()` | 1574 |
| `student.py` | `is_feature_enabled()` | 481 |
| `api.py` | `_enforce_hall_pass_student_context()` | 1126 |

---

## Verification Sweep 1: Extinct Identity — Exhaustive Proof

**Status:** Complete
**Date:** 2026-06-27

### Method

Grepped all `.py` files under `app/` and `wsgi.py` for every pattern: `session.get('admin_id')`, `session['admin_id']`, `session.pop('admin_id')`, and equivalents for `student_id`, `sysadmin_id`. Also searched `teacher_id` as session key. Excluded `app/models.py`, migrations, tests, comments, imports, and `db.session.*` (SQLAlchemy session).

### Result

**Every runtime reference to extinct identity is accounted for in the Class A register or Class E exemptions, and the live `app/` request surface no longer reads extinct session identity.**

| Extinct key | Total runtime hits | Documented in Class A | Documented in Class E | **Undocumented (new)** |
|-------------|-------------------|----------------------|----------------------|----------------------|
| `admin_id` | 121 | 89 (admin.py) + 1 (analytics) + 2 (recovery) | 2 (login writes) + 5 (auth.py bridge) | **4** |
| `student_id` | 3 | 0 | 1 (login write) + 2 (auth.py bridge) | **0** |
| `sysadmin_id` | 9 | 4 (system_admin.py) | 1 (auth.py bridge) | **4** |
| `teacher_id` (session) | 0 | — | — | **0** |

### New sites added to register

| File | Line | Key | Classification |
|------|------|-----|----------------|
| `operational_event_service.py` | 33 | `session.get("admin_id")` | **Historical Class A** — no longer present in the live runtime path, retained here only as prior audit evidence |
| `routes/api.py` | 3 sites | `session.get("admin_id")` | **Historical Class A** — verify against current tree before reclassifying |
| `routes/main.py` | 37 | `session.get('sysadmin_id')` | **Historical Class A** — verify against current tree before reclassifying |
| `routes/docs.py` | 370, 626 | `session.get('sysadmin_id')` | **Historical Class A** — verify against current tree before reclassifying |
| `utils/helpers.py` | 87 | `session.get("sysadmin_id")` | **Historical Class A** — verify against current tree before reclassifying |

### Conclusion

**Current tree summary:** runtime extinct identity reads are gone from `app/` request handlers, but legacy identity residue still exists in tests, model names, and compatibility helpers. Re-run the audit before claiming any further reduction in the residue surface.

---

## Verification Sweep 2: Domain Query Scoping — Exhaustive Proof

**Status:** Complete
**Date:** 2026-06-27

### Method

Grepped all `.py` files under `app/` (excluding models, migrations, tests) for every `.filter`, `.filter_by`, and `==` expression on `join_code` against domain models. Separately counted `class_id` scoping on the same models to measure canonical adoption.

### Result

**Not all domain queries scope by `class_id`. 48 confirmed violations remain where domain models are queried by `join_code`.**

The Pass 2 register undercounted by 8 sites. Corrected inventory below.

### Corrected violation count by model

| Domain Model | `join_code` violations | Files |
|--------------|----------------------|-------|
| `Seat` | **7** | admin.py (5), recovery.py (1), seat_scope.py (1) |
| `Transaction` | **5** | admin.py (2), student.py (2), transaction_idempotency.py (1) |
| `InsuranceEnrollment` | **7** | admin.py (5), student.py (2) |
| `HallPassLog` | **6** | admin.py (5), main.py (1) |
| `AnalyticsAlert` | **3** | analytics.py (3) |
| `AnalyticsEvent` | **2** | analytics.py (2) |
| `TapEvent` | **1** | admin.py (1) |
| `InsurancePolicy` | **1** | student.py (1) |
| `InsuranceClaim` | **1** | student.py (1) |
| `StoreItem` | **1** | student.py (1) |
| `Announcement` | **1** | student.py (1) |
| `StudentBlock` | **1** | identity_service.py (1) |
| `RedemptionAuditLog` | **1** | admin.py (1) |
| `ClassMembership` | **2** | admin.py (2) |
| Multi-model loop (`deletion.py`) | **1** | deletion.py (1) |
| **TOTAL** | **48** | |

### New sites not in original Pass 2 register

| File | Line | Model | Expression |
|------|------|-------|------------|
| `admin.py` | 1085 | `Seat` | `Seat.join_code == join_code` |
| `admin.py` | 1107 | `Seat` | `Seat.join_code == join_code` |
| `admin.py` | 4933 | `Seat` | `Seat.join_code == target_join_code` |
| `admin.py` | 4944 | `Seat` | `Seat.join_code == old_join_code` |
| `admin.py` | 8757 | `Seat` | `Seat.join_code == selected_join_code` |
| `admin.py` | 10444 | `Seat` | `Seat.join_code == selected_join_code` |
| `admin.py` | 3002 | `HallPassLog` | `HallPassLog.join_code.in_(teacher_join_codes)` |
| `admin.py` | 3032 | `HallPassLog` | `HallPassLog.join_code.in_(teacher_join_codes)` |
| `admin.py` | 6037 | `RedemptionAuditLog` | `RedemptionAuditLog.join_code == selected_join_code` |
| `admin.py` | 1653 | `ClassMembership` | `ClassMembership.join_code == join_code` |
| `admin.py` | 10364 | `ClassMembership` | `ClassMembership.join_code == selected_join_code` |
| `main.py` | 319 | `HallPassLog` | `HallPassLog.join_code == selected_join_code` |
| `recovery.py` | 138 | `Seat` | `Seat.join_code == join_code` |
| `student.py` | 2345 | `Seat` | `Seat.join_code == join_code` (if present) |

### Canonical `class_id` adoption (correct usage)

~151 domain-model queries correctly scope by `class_id` across the codebase, indicating the migration is majority-complete but the tail of violations is systematic.

### Conclusion

**The proof fails.** 48 domain-model queries use `join_code` instead of `class_id`. All are now registered. The violation surface is concentrated in `admin.py` (25 sites), `student.py` (8), `analytics.py` (5), with the remainder in utils and services.

---

## Pass 2: `join_code` as Runtime Authority (Class B)

**Status:** Complete — superseded by Verification Sweep 2 above
**Date:** 2026-06-27

### Invariant

> `join_code` may only appear in a `.filter` / `.filter_by` on the `ClassEconomy` table to resolve the boundary (`join_code` → `class_id`). All downstream domain queries must use `class_id`. Any domain-model query filtered by `join_code` is a Class B violation.

### Summary

**43 violation sites** across routes, services, and utils. FEATs are clean (zero join_code filters). The violations cluster in three patterns:

| Pattern | Count | Description |
|---------|-------|-------------|
| Domain model queried by `join_code` instead of `class_id` | 28 | `Transaction`, `InsuranceEnrollment`, `HallPassLog`, `Announcement`, `StoreItem`, `AnalyticsAlert`, etc. filtered by `join_code` |
| Fallback from `class_id` to `join_code` | 3 | Code tries `class_id` first, falls back to `join_code` when missing — dual-key ambiguity |
| Legacy shim that accepts `join_code` parameter | 4 | Functions with `join_code` in their signature that should accept `class_id` |

### Legal uses (Class E — not violations)

These filter `ClassEconomy` itself to resolve the boundary — this IS the resolution:

| File | Line | Context |
|------|------|---------|
| `admin.py` | 628, 646, 1011, 1204, 1956, 2011, 2460, 3579, 4301, 4736, 5063, 5238, 5298, 8378, 9825, 10111, 10532, 10644, 10680, 10789 | `ClassEconomy.query.filter_by(join_code=...)` — boundary resolution |
| `student.py` | 501, 541, 859, 1423, 2412, 2679, 3114 | `ClassEconomy.query.filter_by(join_code=...)` — boundary resolution |
| `api.py` | 209 | `ClassEconomy.query.filter_by(join_code=...)` — boundary resolution |
| `analytics.py` | 86, 522 | `ClassEconomy.query.filter_by(join_code=...)` — boundary resolution |
| `utils/banking.py` | 136 | `ClassEconomy.query.filter_by(join_code=...)` — boundary resolution |
| `utils/issue_helpers.py` | 52, 133 | `ClassEconomy.query.filter_by(join_code=...)` — boundary resolution |
| `utils/seat_scope.py` | 13 | `ClassEconomy.query.filter_by(join_code=...)` — boundary resolution |
| `utils/analytics_engine.py` | 86 | `ClassEconomy.query.filter_by(join_code=...)` — boundary resolution |
| `utils/economy_policy.py` | 457, 468 | `ClassEconomy.query.filter(join_code=...)` — boundary resolution |

### Violations — Routes

#### admin.py (15 violation sites)

| Line | Handler | Table | Source of join_code | Issue |
|------|---------|-------|---------------------|-------|
| 1239 | `_delete_transactions_for_join_code` | `Transaction` | function parameter | `Transaction.query.filter_by(join_code=join_code).delete()` — destructive operation using non-canonical key |
| 1274 | `_hard_delete_class_scope` | 11+ domain models | `class_row.join_code` | Loop queries domain models with `model.join_code == join_code` |
| 4696 | `_get_student_detail_view` | `Transaction` | local variable | `Transaction.join_code == join_code` — redundant after canonical seat/class scope |
| 4721 | `_get_student_detail_view` | `Transaction` | local variable | Adds `join_code` filter after canonical scope |
| 4722 | `_get_student_detail_view` | `TapEvent` | local variable | Adds `join_code` filter after canonical scope |
| 7506 | `_get_student_insurance_data` | `InsuranceEnrollment` | `selected_join_code` | `.filter(InsuranceEnrollment.join_code == selected_join_code)` |
| 7516 | `_get_student_insurance_data` | `InsuranceEnrollment` | `selected_join_code` | Filters enrollment count by join_code |
| 7529 | `_get_student_insurance_data` | `InsuranceEnrollment` | `selected_join_code` | Filters active enrollments by join_code |
| 7540 | `_get_student_insurance_data` | `InsuranceClaim` | `selected_join_code` | `.filter(InsuranceClaim.join_code == selected_join_code)` |
| 8215 | `hall_pass` | `HallPassLog` | `selected_join_code` | `.filter(HallPassLog.join_code == selected_join_code)` |
| 8225 | `hall_pass` | `HallPassLog` | `selected_join_code` | Filters approved passes by join_code |
| 8235 | `hall_pass` | `HallPassLog` | `selected_join_code` | Filters pending passes by join_code |
| 8649 | `payroll_history` | `PayrollSettings` | `join_code_tuple[0]` | `.filter_by(join_code=join_code_tuple[0])` |
| 10428 | `_export_roster_data` | `InsuranceEnrollment` | `selected_join_code` | `.filter(InsuranceEnrollment.join_code == selected_join_code)` |
| 9953 | `_resolve_student_import` | `ClassEconomy` | `file_join_code` | `.filter(ClassEconomy.join_code == file_join_code)` — this one is boundary resolution but inside import logic |

#### student.py (8 violation sites)

| Line | Handler | Table | Issue |
|------|---------|-------|-------|
| 1621 | `_get_insurance_enrollment_page` | `InsuranceEnrollment` | Filters by `join_code` after seat already provides class context |
| 1627 | `_get_insurance_enrollment_page` | `InsurancePolicy` | Filters by `join_code`; should use class_id from seat |
| 1669 | `_get_insurance_enrollment_page` | `InsuranceClaim` | Filters by `join_code`; should use class_id from seat |
| 1773 | `_get_insurance_enrollment_page` | `InsuranceEnrollment` | Tier check by `join_code`; seat provides canonical scope |
| 1975 | `_resolve_eligible_claim_transactions` | `Transaction` | `Transaction.join_code == enrollment.join_code` — should use class_id |
| 2215 | `_get_student_store_page` | `StoreItem` | Filters by `join_code`; should use class_id from seat |
| 2782 | `_filter_valid_rent_payments` | `Transaction` | Filters by `join_code` parameter; should use class_id |
| 1221 | `_get_student_announcements_list` | `Announcement` | Filters by `join_code`; should use class_id |

#### analytics.py (5 violation sites)

| Line | Handler | Table | Issue |
|------|---------|-------|-------|
| 252 | `dashboard` | `AnalyticsAlert` | `.filter(AnalyticsAlert.join_code == join_code)` |
| 266 | `dashboard` | `AnalyticsEvent` | `.filter(AnalyticsEvent.join_code == join_code)` |
| 389 | `api_alerts` | `AnalyticsAlert` | `.filter(AnalyticsAlert.join_code == join_code)` |
| 438 | `acknowledge_alert` | `AnalyticsAlert` | `.filter(AnalyticsAlert.join_code == join_code)` |
| 479 | `events` | `AnalyticsEvent` | `.filter(AnalyticsEvent.join_code == join_code)` |

### Violations — Services

| File | Line | Function | Table | Issue |
|------|------|----------|-------|-------|
| `identity_service.py` | 93 | `sync_student_block_rent_passes` | `StudentBlock` | `StudentBlock.join_code == (seat.join_code)` — fallback after seat_id lookup fails |

### Violations — Utils

| File | Line | Function | Table | Issue |
|------|------|----------|-------|-------|
| `transaction_idempotency.py` | 66 | `get_idempotent_transaction` | `Transaction` | `Transaction.join_code == join_code` — fallback when `class_id` not provided |
| `seat_scope.py` | 18 | `get_seat_ids_for_student_join` | `Seat` | `Seat.join_code == join_code` — fallback when ClassEconomy lookup fails |
| `issue_helpers.py` | 87 | `create_context_snapshot` | `Transaction` | `Transaction.join_code == join_code` — domain query by non-canonical key |
| `deletion.py` | 45 | `sanity_check_class_invariants` | 11+ models | `model.join_code == join_code` — invariant checks using non-canonical key |

### Violations — FEATs

**None.** All FEAT files are clean — zero `join_code` filters.

---

## Pass 3: FEAT/Service Boundary Integrity

**Status:** Complete
**Date:** 2026-06-27

FEATs: **Clean.** Zero session reads, zero `join_code` filters, zero direct identity reconstruction. All FEATs receive context as arguments.

Services: **1 violation** in `identity_service.py:93` (Class B — `join_code` fallback filter on `StudentBlock`). All other services are clean.

---

## Final Totals

| Class | Name | Proven count | Severity |
|-------|------|-------------|----------|
| **A** | Use of extinct runtime identity | **0 in live `app/` request paths; historical hits retained below** | CRITICAL |
| **B** | `join_code` as runtime authority on domain models | **48** | HIGH |
| **C** | Multiple/helper-level context re-resolution | **6** | LOW |
| **E** | Boundary-only / exempt | **~32** | EXEMPT |

## Remediation Priority

| Priority | Class | Scope | Sites | Approach |
|----------|-------|-------|-------|----------|
| **P0** | A | Admin routes — extinct identity (`session.get('admin_id')`) | historical only | Completed in the live runtime path; keep residue cleanup out of the runtime audit |
| **P0** | A | Auth bridges — legacy shadow resolution | 6 functions in `auth.py` | Historical item; helpers removed in the current tree |
| **P0** | A | Scattered extinct identity across 7 files | historical only | Same pattern is now useful only as historical evidence; keep current work focused on residue and tests |
| **P1** | B | Domain queries filtered by `join_code` in routes | 39 across `admin.py`, `student.py`, `analytics.py`, `main.py`, `recovery.py` | Replace with `class_id` from canonical context |
| **P1** | B | `join_code` fallbacks in utils/services | 9 across 5 files | Remove fallback paths; require `class_id` |
| **P2** | C | Multiple context resolutions | 1 in `student.py` | Resolve once, pass to both call sites |
| **P3** | C | Helper-level re-resolution | 5 in `student.py`, `api.py` | Accept context as argument |

---

**Last Updated:** 2026-06-27

### Status Update (2026-07-05): Runtime Helper Naming Cleanup

- `app/services/admin_identity_bridge_service.py` has been renamed to `app/services/admin_identity_service.py`
- `app/services/recovery_bridge_service.py` has been renamed to `app/services/recovery_service.py`
- the live `app/` import graph no longer references `bridge_service`
- `app --app wsgi routes` still starts cleanly after the identity cleanup
- startup verification still passes after the rename (`venv/bin/flask --app wsgi routes >/dev/null`)
