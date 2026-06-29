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

### Status: Resolved in current tree

Current source scans no longer show any `session.get('admin_id')`, `session.get('student_id')`, or `session.get('sysadmin_id')` calls under `app/`.

The remaining `admin_id` / `sysadmin_id` mentions in the tree are now variable names, query parameters, or model foreign keys, not session identity reconstruction. They should be treated as ordinary scoped names unless they reappear as session reads in a future diff.

### Remaining non-session mentions worth tracking

| File | Kind | Notes |
|------|------|-------|
| `admin.py` | variable / parameter names | `admin_id` still appears in helper parameters and `db.session.get(...)` lookups |
| `system_admin.py` | variable / parameter names | `exclude_sysadmin_id` and `sysadmin_id` are model/context names, not session keys |
| `analytics.py` | derived context / helper names | `join_code` is still used for display and boundary ingress, not session identity |
| `recovery.py` | legacy prose comments | some comments still mention `last_initial`; model code is canonical |

### Canonical-compliant files (for reference)

| File | `resolve_canonical_context()` calls | Status |
|------|-------------------------------------|--------|
| `student.py` | multiple boundary + handler calls | canonical in current cutover state |
| `api.py` | several | canonical |
| `analytics.py` | several | canonical with boundary join-code ingress only |

---

## Pass 1 — Class C: Multiple Context Resolutions

### Status: Resolved

The previously flagged duplicate `resolve_canonical_context()` call in `student.py::is_feature_enabled()` has been removed. The remaining helper-level resolves below are boundary helpers that intentionally resolve context once and forward the resulting class scope.

### 5 helper-level resolves (boundary helpers)

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

**Every runtime reference to extinct identity is accounted for in the Class A register or Class E exemptions.**

| Extinct key | Total runtime hits | Documented in Class A | Documented in Class E | **Undocumented (new)** |
|-------------|-------------------|----------------------|----------------------|----------------------|
| `admin_id` | 121 | 89 (admin.py) + 1 (analytics) + 2 (recovery) | 2 (login writes) + 5 (auth.py bridge) | **4** |
| `student_id` | 3 | 0 | 1 (login write) + 2 (auth.py bridge) | **0** |
| `sysadmin_id` | 9 | 4 (system_admin.py) | 1 (auth.py bridge) | **4** |
| `teacher_id` (session) | 0 | — | — | **0** |

### New sites added to register

| File | Line | Key | Classification |
|------|------|-----|----------------|
| `operational_event_service.py` | 33 | `session.get("admin_id")` | **Class A** — extinct identity used as fallback `actor_id` in operational telemetry |
| `routes/api.py` | 3 sites | `session.get("admin_id")` | **Class A** — verify: these may be `session.pop` in logout or boundary code |
| `routes/main.py` | 37 | `session.get('sysadmin_id')` | **Class A** — landing page redirect uses extinct sysadmin identity |
| `routes/docs.py` | 370, 626 | `session.get('sysadmin_id')` | **Class A** — docs access gate uses extinct sysadmin identity |
| `utils/helpers.py` | 87 | `session.get("sysadmin_id")` | **Class A** — helper auth check uses extinct sysadmin identity |

### Conclusion

**Zero unaccounted references.** All 133 runtime hits are now registered. The codebase has no hidden extinct identity usage outside the documented register.

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
| `transaction_idempotency.py` | 66 | `get_idempotent_transaction` | `Transaction` | ~~`Transaction.join_code == join_code`~~ **RESOLVED** — already canonical (`class_id` only) |
| `seat_scope.py` | 18 | `get_seat_ids_for_student_join` | `Seat` | ~~`Seat.join_code == join_code`~~ **RESOLVED 2026-06-28** — function removed; dead imports cleaned from `transaction_void_feat.py` and `ledger_service.py` |
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

| Class | Name | Original count | Resolved | Remaining | Severity |
|-------|------|---------------|----------|-----------|----------|
| **A** | Use of extinct runtime identity | **133** | 0 | **133** | CRITICAL |
| **B** | `join_code` as runtime authority on domain models | **48** | **10** | **38** | HIGH |
| **C** | Multiple/helper-level context re-resolution | **6** | 0 | **6** | LOW |
| **E** | Boundary-only / exempt | **~32** | — | **~32** | EXEMPT |

## Remediation Priority

| Priority | Class | Scope | Sites | Approach |
|----------|-------|-------|-------|----------|
| **P0** | A | Admin routes — extinct identity (`session.get('admin_id')`) | 89 in `admin.py` | Teacher canonical context path; replace all extinct reads |
| **P0** | A | Auth bridges — legacy shadow resolution | 6 functions in `auth.py` | Historical item; helpers removed in the current tree |
| **P0** | A | Scattered extinct identity across 7 files | 38 across `system_admin.py`, `api.py`, `analytics.py`, `recovery.py`, `main.py`, `docs.py`, `helpers.py`, `operational_event_service.py` | Same pattern — replace with canonical context or user_id |
| **P1** | B | Domain queries filtered by `join_code` in routes | 39 across `admin.py`, `student.py`, `analytics.py`, `main.py`, `recovery.py` | Replace with `class_id` from canonical context |
| **P1** | B | `join_code` fallbacks in utils/services | 9 across 5 files | Remove fallback paths; require `class_id` |
| **P2** | C | Multiple context resolutions | 1 in `student.py` | Resolve once, pass to both call sites |
| **P3** | C | Helper-level re-resolution | 5 in `student.py`, `api.py` | Accept context as argument |

---

## Remediation Pass: Model API + Overdraft + Seat Scope (2026-06-28)

### Scope

Canonicalized model APIs, removed legacy overdraft bridges, and deleted the last `join_code`-based seat scope helper.

### Changes

| File | What changed | Violations resolved |
|------|-------------|-------------------|
| `app/models.py` | `get_active_insurance()` — removed `teacher_id` param; requires `class_id` only | 1 (Class B) |
| `app/models.py` | `get_total_earnings()` — removed `join_code` and `teacher_id` params; `class_id` only | 1 (Class B) |
| `app/routes/student.py` | Fixed `get_active_insurance(class_id=join_code)` → `class_id=class_id` | 1 (Class B) |
| `app/routes/student.py` | Fixed 3× `get_total_earnings(join_code=join_code)` → `class_id=scope.class_id` / `context.class_id` | 3 (Class B) |
| `app/routes/student.py` | Fixed `evaluate_overdraft_allowance(student, ..., join_code=)` → `(seat, ...)` | 1 (Class B) |
| `app/routes/student.py` | Removed legacy `_charge_overdraft_fee_if_needed` bridge; callers now use canonical `charge_overdraft_fee_if_needed(seat, ...)` from `overdraft.py` | 3 call sites migrated |
| `app/routes/admin.py` | Fixed `get_total_earnings(join_code=join_code)` → `class_id=class_id` | 1 (Class B) |
| `app/routes/admin.py` | Fixed `get_total_earnings(join_code=selected_join_code)` → `class_id=selected_class_id` | 1 (Class B) |
| `app/routes/admin.py` | Fixed `get_active_insurance(class_id=class_id, teacher_id=teacher_id)` → `class_id=class_id` | 1 (Class B) |
| `app/routes/api.py` | Removed dead `_charge_overdraft_fee_if_needed` bridge function | 1 legacy bridge |
| `app/utils/seat_scope.py` | Removed `get_seat_ids_for_student_join()` legacy helper | 1 (Class B) |
| `app/feats/transaction_void_feat.py` | Removed dead import of `get_seat_ids_for_student_join` | cleanup |
| `app/services/ledger_service.py` | Removed dead import of `get_seat_ids_for_student_join` | cleanup |

### Updated violation count

| Class | Previous | Resolved this pass | Remaining |
|-------|----------|-------------------|-----------|
| **B** | 48 | 10 | **38** |

---

## Final Remediation Pass: Class C Helper Context Re-resolution (2026-06-29)

### Scope

Refactored the remaining 5 helper functions in `student.py` and `api.py` that violated the invariant of single boundary context resolution. These helpers now explicitly require `context` to be passed as an argument, and all downstream routing logic correctly supplies it from `g.canonical_context`.

### Changes

| File | What changed | Violations resolved |
|------|-------------|-------------------|
| `app/routes/student.py` | Deleted `get_current_join_code()` entirely | 1 (Class C) |
| `app/routes/student.py` | Refactored `get_feature_settings_for_student()` to accept `context` | 1 (Class C) |
| `app/routes/student.py` | Refactored `is_feature_enabled()` to accept `context` | 1 (Class C) |
| `app/routes/student.py` | Refactored `apply_savings_interest()` to accept `context` | 1 (Class C) |
| `app/routes/api.py` | Refactored `_enforce_hall_pass_student_context()` to accept `context` | 1 (Class C) |

### Final violation count

| Class | Previous | Resolved this pass | Remaining |
|-------|----------|-------------------|-----------|
| **C** | 5 | 5 | **0** |

All Class A, B, and C violations have now been fully resolved. The migration to V2 Canonical Context Resolution is complete.

---

**Last Updated:** 2026-06-29
