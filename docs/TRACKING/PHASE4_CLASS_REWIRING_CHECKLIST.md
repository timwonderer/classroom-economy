# Phase 4: CLASS Domain Rewiring Checklist

| Reference Number | Version | Effective Date | Status |
|---|---|---|---|
| SOP-DEV-002 Phase 4 | 1.0 | 2026-08-09 | IN PROGRESS |

**Objective:** Verify every route that accesses CLASS domain tables calls canonical providers (FEATs for mutations, services for reads). Ensure route-template field contracts match.

**Scope:** ~48 routes identified across 5 route files (CLASS domain only; Store item CRUD belongs to Store/Entitlements domain per MAP-UI-001 decision 6)

---

## Summary

| File | Total Routes | Mutations | Reads | Status |
|------|---|---|---|---|
| admin.py | 36 | 22 | 14 | 🔴 NEEDS_REWIRE |
| analytics.py | 3 | 0 | 3 | 🟡 VERIFY_ONLY |
| api.py | 8 | 1 | 7 | 🟡 VERIFY_ONLY |
| student.py | 6 | 3 | 3 | 🟡 VERIFY_ONLY |
| main.py | 1 | 1 | 0 | 🟡 VERIFY_ONLY |
| **TOTAL** | **54** | **27** | **27** | |

**Note:** 3 Store item CRUD routes removed (store_management POST, edit_store_item POST, delete_store_item POST) — these belong to Store/Entitlements domain per MAP-UI-001 decision 6, not CLASS Configuration.

---

## admin.py (39 routes)

### MUTATIONS (25 routes) — Must call FEAT-CLASS-001/004/005

| Route | Path | HTTP | Tables | Current State | Required FEAT | View Model Needed | Status |
|---|---|---|---|---|---|---|---|
| `set_class_timezone` | `/classes/<class_id>/timezone` | POST | ClassEconomy | Direct `.query` | FEAT-CLASS-001 (create boundary has timezone) | ClassConfigurationView | 🔴 NEEDS_REWIRE |
| `settings` | `/settings` | GET,POST | ClassEconomy | Direct query + mutation | FEAT-CLASS-001/004/005 (depends on which setting) | ClassConfigurationView | 🔴 NEEDS_REWIRE |
| `feature_settings` | `/feature-settings` | GET,POST | ClassFeature | Direct mutation | FEAT-CLASS-004 (enable/disable) | FeatureConfigurationView | 🔴 NEEDS_REWIRE |
| `rent_settings` | `/rent-settings` | GET,POST | ClassEconomy, PayrollSettings, RentSettings | Direct mutation + query | CLASS config + Obligations domain | RentConfigurationView | 🔴 NEEDS_REWIRE |
| `banking_settings_update` | `/banking/settings` | POST | BankingSettings | Direct mutation | CLASS config | BankingConfigurationView | 🔴 NEEDS_REWIRE |
| `add_individual_student` | `/student/add-individual` | POST | ClassEconomy | Direct mutation + query | FEAT-CLASS-001 (class boundary) + IDEN for seat | StudentAdditionView | 🔴 NEEDS_REWIRE |
| `add_manual_student` | `/student/add-manual` | POST | ClassEconomy | Direct mutation + query | FEAT-CLASS-001 + IDEN for seat | StudentRosterUploadView | 🔴 NEEDS_REWIRE |
| `upload_students` | `/upload-students` | POST | ClassEconomy | Direct mutation + CSV parsing | FEAT-CLASS-001 (bulk class linkage) + IDEN | StudentRosterUploadView | 🔴 NEEDS_REWIRE |
| `edit_student` | `/student/edit` | POST | ClassEconomy | Direct query for student seat class linkage | Read: class_configuration_query_service, Mutation: IDEN domain | StudentEditView | 🔴 NEEDS_REWIRE |
| `delete_student` | `/student/archive` | GET,POST | ClassEconomy | Direct mutation + query | IDEN domain (seat deletion), CLASS config for class scope | StudentDeleteView | 🔴 NEEDS_REWIRE |
| `delete_pending_student` | `/pending-students/delete` | POST | ClassEconomy | Direct mutation | IDEN domain + CLASS config | StudentDeleteView | 🔴 NEEDS_REWIRE |
| `bulk_delete_pending_students` | `/pending-students/bulk-delete` | POST | ClassEconomy | Direct mutation | IDEN domain + CLASS config | StudentBulkDeleteView | 🔴 NEEDS_REWIRE |
| `delete_block` | `/students/delete-block` | POST | ClassEconomy | Direct mutation | FEAT-CLASS-005? (economic versioning?) | ClassManagementView | ⚠️ UNCLEAR_SCOPE |
| `delete_join_code` | `/join-code/delete` | POST | ClassEconomy | Direct mutation | FEAT-CLASS-001 (class boundary deletion) | ClassManagementView | 🔴 NEEDS_REWIRE |
| `set_current_class` | `/current-class` | POST | ClassEconomy | Direct mutation (session state only) | No FEAT needed (session management) | N/A | 🟢 VERIFY_ONLY |
| `apply_economy_rebalance` | `/economy-policy/rebalance` | POST | ClassEconomy, PayrollSettings | Direct mutation + query | FEAT-CLASS-005 (economic engine evolution) | EconomyRebalanceView | 🔴 NEEDS_REWIRE |
| `update_expected_weekly_hours` | `/payroll/update-expected-hours` | POST | PayrollSettings | Direct mutation | FEAT-CLASS-001 (initial engine) or FEAT-CLASS-005 (evolution) | PayrollConfigurationView | 🔴 NEEDS_REWIRE |
| `adjust_hall_pass_entitlements` | `/student/<seat_id>/adjust-hall-pass-entitlements` | POST | ClassEconomy | Direct query for class scope | **WRONG FEAT** currently (STOR-004), read from class_configuration_query_service | EntitlementAdjustmentView | 🔴 NEEDS_REWIRE |
| `bulk_adjust_hall_pass_entitlements` | `/students/bulk-adjust-hall-pass-entitlements` | POST | ClassEconomy | Direct query for class scope | Read from class_configuration_query_service | EntitlementAdjustmentView | 🔴 NEEDS_REWIRE |
| `give_bonus_all` | `/bonuses` | POST | BankingSettings | Direct query for banking settings | Read from class_configuration_query_service | BonusConfigurationView | 🔴 NEEDS_REWIRE |
| `api_calculate_cwi` | `/api/economy/calculate-cwi` | POST | PayrollSettings | Direct query + calculation | Read from class_configuration_query_service (CWI calculation already there) | EconomyAnalysisView | 🔴 NEEDS_REWIRE |
| `api_economy_analyze` | `/api/economy/analyze` | POST | ClassEconomy, RentSettings | Direct query + analysis | Read from class_configuration_query_service | EconomyAnalysisView | 🔴 NEEDS_REWIRE |
| `recover` | `/recover` | GET,POST | ClassEconomy | Direct query (class scope for recovery) | Read from class_configuration_query_service | RecoveryView | 🔴 NEEDS_REWIRE |
| `help_support` | `/help-support` | GET,POST | ClassEconomy | Direct query for class scope | Read from class_configuration_query_service | SupportView | 🔴 NEEDS_REWIRE |
| `close_issue` | `/issues/<issue_ref>/close` | POST | ClassEconomy | Direct query (authorization only) | Read from class_configuration_query_service | IssueManagementView | 🔴 NEEDS_REWIRE |
| `resolve_issue` | `/issues/<issue_ref>/resolve` | POST | ClassEconomy | Direct query (authorization only) | Read from class_configuration_query_service | IssueManagementView | 🔴 NEEDS_REWIRE |
| `escalate_issue` | `/issues/<issue_ref>/escalate` | POST | ClassEconomy | Direct query (authorization only) | Read from class_configuration_query_service | IssueManagementView | 🔴 NEEDS_REWIRE |

### READS (14 routes) — Must call class_configuration_query_service

| Route | Path | HTTP | Tables | Current State | Required Service | View Model Needed | Status |
|---|---|---|---|---|---|---|---|
| `dashboard` | `/` | GET | ClassEconomy | Direct query | `get_all_classes_by_teacher()` | AdminDashboardView | 🔴 NEEDS_REWIRE |
| `students` | `/students` | GET | ClassEconomy | Direct query + joins | `get_class_economy()` | StudentRosterView | 🔴 NEEDS_REWIRE |
| `student_detail_public` | `/students/<string:actor_public_id>` | GET | ClassEconomy | Direct query | `get_class_economy()` | StudentDetailView | 🔴 NEEDS_REWIRE |
| `hall_pass` | `/hall-pass` | GET | ClassEconomy | Direct query | `get_class_economy()` | HallPassManagementView | 🔴 NEEDS_REWIRE |
| `payroll` | `/payroll` | GET | ClassEconomy, PayrollSettings | Direct query | `get_class_economy()`, `get_payroll_settings()` | PayrollDashboardView | 🔴 NEEDS_REWIRE |
| `banking` | `/banking` | GET | BankingSettings | Direct query | `get_banking_settings()` | BankingDashboardView | 🔴 NEEDS_REWIRE |
| `export_students` | `/export-students` | GET | ClassEconomy | Direct query | `get_class_economy()` | StudentRosterExportView | 🔴 NEEDS_REWIRE |
| `export_class_roster` | `/export-class-roster` | GET | ClassEconomy | Direct query | `get_class_economy()` | StudentRosterExportView | 🔴 NEEDS_REWIRE |
| `issues_queue` | `/issues` | GET | ClassEconomy | Direct query (class scope for permissions) | `get_class_economy()` | IssueQueueView | 🔴 NEEDS_REWIRE |
| `onboarding_status` | `/onboarding/status` | GET | ClassEconomy, PayrollSettings, RentSettings, BankingSettings, HallPassSettings | Direct query of all settings | Service functions for each | OnboardingStatusView | 🔴 NEEDS_REWIRE |

---

## analytics.py (3 routes)

### READS — Verify calling service layer

| Route | Path | HTTP | Tables | Current State | Required Service | View Model Needed | Status |
|---|---|---|---|---|---|---|---|
| `dashboard` | `/analytics/` | GET | ClassEconomy | Direct `.query.filter_by(teacher_user_id=...)` | `get_all_classes_by_teacher()` | AnalyticsDashboardView | 🟡 VERIFY_ONLY |
| `events` | `/analytics/events` | GET | ClassEconomy | Direct `.query.filter_by(class_id=...)` | `get_class_economy()` | EventsView | 🟡 VERIFY_ONLY |
| `student_drill_down` | `/analytics/student/<int:student_id>` | GET | ClassEconomy | Direct `.query.get(class_id)` | `get_class_economy()` | StudentAnalyticsView | 🟡 VERIFY_ONLY |

---

## api.py (8 routes)

### READS — Verify calling service layer

| Route | Path | HTTP | Tables | Current State | Required Service | View Model Needed | Status |
|---|---|---|---|---|---|---|---|
| `get_available_hall_pass_types` | `/api/hall-pass/available-types` | GET | ClassEconomy, HallPassSettings | Direct `.query` | `get_hall_pass_settings()` | HallPassTypesView | 🟡 VERIFY_ONLY |
| `get_hall_pass_setup` | `/api/hall-pass/setup` | GET | HallPassSettings | Direct `.query.filter_by(class_id=...)` | `get_hall_pass_settings()` | HallPassSetupView | 🟡 VERIFY_ONLY |
| `hall_pass_settings` | `/api/hall-pass/settings` | GET | HallPassSettings | Direct `.query.filter_by(class_id=...)` | `get_hall_pass_settings()` | HallPassSettingsView | 🟡 VERIFY_ONLY |
| `save_hall_pass_setup` | `/api/hall-pass/setup` | GET | HallPassSettings | Direct `.query.filter_by(class_id=...)` | `get_hall_pass_settings()` | HallPassSetupView | 🟡 VERIFY_ONLY |
| `attendance_history` | `/api/attendance/history` | GET | ClassEconomy | Direct `.query.filter_by(class_id=...)` | `get_class_economy()` | AttendanceHistoryView | 🟡 VERIFY_ONLY |
| `hall_pass_history` | `/api/hall-pass/history` | GET | ClassEconomy | Direct `.query.filter_by(class_id=...)` | `get_class_economy()` | HallPassHistoryView | 🟡 VERIFY_ONLY |
| `hall_pass_verification_active` | `/api/hall-pass/verification/active` | GET | ClassEconomy | Direct `.query.filter_by(class_id=...)` | `get_class_economy()` | HallPassVerificationView | 🟡 VERIFY_ONLY |

### MUTATIONS (1 route) — Must call FEAT

| Route | Path | HTTP | Tables | Current State | Required FEAT | View Model Needed | Status |
|---|---|---|---|---|---|---|---|
| `handle_tap` | `/api/tap` | POST | ClassEconomy | Direct query for class scope | Read from class_configuration_query_service | TapResponseView | 🔴 NEEDS_REWIRE |

---

## student.py (6 routes)

### MUTATIONS (3 routes) — Must call FEAT

| Route | Path | HTTP | Tables | Current State | Required FEAT | View Model Needed | Status |
|---|---|---|---|---|---|---|---|
| `add_class` | `/student/add-class` | GET,POST | ClassEconomy | Direct `.query.filter_by(join_code=...)` | Identity domain (join-code ingress → DOM-IDEN-001) | ClassSelectionView | 🔴 NEEDS_REWIRE (Identity domain) |
| `claim_account` | `/student/claim-account` | GET,POST | ClassEconomy | Direct `.query` (join_code resolution) | Identity domain (join-code ingress → DOM-IDEN-001) | AccountClaimView | 🔴 NEEDS_REWIRE (Identity domain) |
| `purchase_insurance` | `/student/insurance/purchase/<int:policy_id>` | POST | BankingSettings | Direct query for banking settings | Read from class_configuration_query_service | InsurancePurchaseView | 🔴 NEEDS_REWIRE |

### READS (3 routes) — Verify calling service layer

| Route | Path | HTTP | Tables | Current State | Required Service | View Model Needed | Status |
|---|---|---|---|---|---|---|---|
| `payroll` | `/student/payroll` | GET | PayrollSettings | Direct `.query.filter_by(class_id=...)` | `get_payroll_settings()` | StudentPayrollView | 🟡 VERIFY_ONLY |
| `shop` | `/student/shop` | GET | RentSettings | Direct `.query.filter_by(class_id=...)` | `get_rent_settings()` | StudentShopView | 🟡 VERIFY_ONLY |
| `help_support` | `/student/help-support` | GET | ClassEconomy | Direct query for class scope | `get_class_economy()` | StudentSupportView | 🟡 VERIFY_ONLY |

---

## main.py (1 route)

### MUTATIONS (1 route) — Must call FEAT

| Route | Path | HTTP | Tables | Current State | Required FEAT | View Model Needed | Status |
|---|---|---|---|---|---|---|---|
| `verify_hall_pass` | `/verify/hallpass/<teacher_public_token>` | GET,POST | ClassEconomy | Direct query for class scope (teacher token resolution) | Read from class_configuration_query_service (public teacher token lookup) | HallPassVerificationView | 🔴 NEEDS_REWIRE |

---

## Phase 4 Stage Gates (Per SOP-DEV-002 VIII)

✅ **Preconditions Met:**
- Canonical truth defined (Phase 0-2 ✅)
- Owned persistence defined (Phase 2 ✅)
- Primitive writes named (Phase 3 ✅ — FEAT-CLASS-001/004/005)
- Write FEAT ownership known (Phase 4 ✅ — Created above)

❌ **Stage Gate — Route Verification:**

For EACH route in the NEEDS_REWIRE category:
- [ ] Route calls canonical provider (FEAT or service, not `.query()`)
- [ ] Route passes ALL required fields to template (no missing fields)
- [ ] Template field names match route variable names (contract verification)
- [ ] Mutation routes call exactly ONE FEAT (no direct db.session)
- [ ] Read routes use class_configuration_query_service (or domain-specific service)
- [ ] View model defined for complex templates (Phase 5 deliverable)

---

## Next Steps

### Phase 4 Completion
1. **Route Rewiring** (30 mutations + 27 reads)
   - Rewrite each NEEDS_REWIRE route to call canonical provider
   - Remove all direct `.query()` calls on CLASS tables
   - Verify route → template field contracts match
   
2. **Verification Tests**
   - Unit test for each rewired route (SPEC-TEST-001 patterns)
   - Ensure FEAT mutations are called (not db.session bypassed)
   - Ensure template renders without missing fields

### Phase 5 Preparation (deferred)
- Create view models for 57 routes (list in column 7)
- Follow MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE.md
- Ensure view models are canonical (no legacy denormalized state)

---

## Known Issues / Blockers

| Issue | Impact | Resolution |
|---|---|---|
| `delete_block` scope unclear | Not sure if CLASS or Obligations owns block deletion | Need architecture clarification before rewiring |
| Many routes do class_id validation via direct query | Repetitive pattern across 20+ routes | Refactor to helper that calls class_configuration_query_service |

**Note on Store Item CRUD:** Routes `store_management` POST, `edit_store_item` POST, and `delete_store_item` POST belong to **Store/Entitlements domain**, not CLASS Configuration. They have been removed from this checklist per MAP-UI-001 decision 6. These routes should be tracked in the Store domain Phase 4 rewiring work.

---

## Statistics

- **Total Phase 4 Routes:** 57
- **Mutations Requiring FEAT:** 30
- **Reads Requiring Service:** 27
- **Verification-Only:** ~14 (already using services)
- **Estimated Rewiring Effort:** ~30-40 hours (1-2 weeks)
- **Phase 5 View Models Needed:** 57 (one per route interaction pattern)

