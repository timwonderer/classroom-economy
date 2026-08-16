# CTH Domain Reconstruction Progress Matrix

**Status:** Active Canonical Tracker
**Last Updated:** 2026-08-16 (Obligation Phase 10 audit GAP surfaced: cross-layer template sweep missed; emergency template fix + `rent_settings` dead-schema drop landed; Policies-domain doctrine substantially advanced — `policy_uuid` promoted to first-class in DOM-POL-001 §VI.0, all `*_settings` tables (rent/payroll/hall_pass/store/insurance) routed to DOM-POL-001; `banking_settings` routed to Class Config / economic-engine; no Banking domain. See `OBLIGATION_POLICIES_FOLLOWUP_2026-08-16.md`.)
**Authority:** SOP-DEV-002a, INV-CORE-000, DOM-CORE-002

**DOMAIN READINESS SNAPSHOT:**
- ✅ **2 domains** Phase 10 certified (production-ready): Identity, Store
- ⚠️ **1 domain** Phase 10 certified with known audit gap: Obligations (2026-07-26 audit missed cross-layer template sweep; templates + `rent_settings` mutation pattern flagged 2026-08-16)
- 🔄 **1 domain** Phase 5 complete, Phase 6-7 partial: Class Config (view models defined; 4 of 12 MAP-UI-001 rows rewired; EconomicView stub still incomplete; 5 constitutional issues open)
- 🔄 **2 domains** Phase 1 complete but blocked on Phase 2 (schema migrations pending): Ledger, Payroll
- 🔄 **1 domain** Phase 0-1, doctrine substantially advanced 2026-08-16: Policies
- 🔄 **3 domains** Phase 0-1 only, not started: Operations, Interpretation, Support

---

## Overview

This matrix consolidates the progress of all CTH domains through the 10-phase SOP-DEV-002 reconstruction workflow. Each domain progresses independently but follows the same phase sequence:

| Phase | Name | Purpose |
| ------- | ------ | --------- |
| **0** | Boundary | Domain scope defined and authorized |
| **1** | Truth | Canonical facts immutable and audit-traceable |
| **2** | Persistence | Schema, migrations, indexes in place |
| **3** | Primitives | Core queries centralized in service layer |
| **4** | Mutation Boundary | All writes through FEAT layer |
| **5** | Read Models | View models immutable, generic, scoped |
| **6** | View Model Wiring | Routes construct view models; all owned fields exist in models |
| **7** | Surface Integration | Templates consume only owned fields; legacy sources removed |
| **8** | Verify | Tests prove correctness and multi-tenancy |
| **9** | Legacy Deletion | Dead code removed |
| **10** | Audit | Production readiness certified |

---

## Domain Status Matrix

| Domain | Spec | Phase 0-4 | Phase 5 | Phase 6-7 | Phase 8-9 | Phase 10 | Status | Audit Doc |
| -------- | ------ | ----------- | --------- | ----------- | ----------- | ---------- | -------- | ----------- |
| **Identity** | DOM-IDEN-001/002/003/006 | ✅ | ✅ | ✅ VERIFIED | ✅ VERIFIED | ✅ CERTIFIED | ✅ PRODUCTION READY (Phase 10 certified 2026-08-06) | 2026-08-06 (PASS) |
| **Class Configuration** | DOM-CLASS-001 | ✅ Phase 0-4 | ⚠️ Phase 5 (EconomicView stub) | 🔄 Phase 6-7 partial (4/12 rows) | ❌ | ❌ | 🔄 Phase 7 IN PROGRESS — settings routes (rent/banking/payroll/economic_engine) class_id-authoritative; CWI-unconfigured path fully handled; blocks-as-scope eliminated from class-config surface. 5 constitutional issues open. | 2026-08-16 update |
| **Ledger** | DOM-LED-001 | ✅ | ❌ NO VM | ❌ BLOCKED | ? | ❌ | ❌ BLOCKED on Phase 5 | 2026-08-04 baseline |
| **Productivity & Payroll** | DOM-PROD-001 | ✅ | ❌ NO VM | ❌ BLOCKED | ? | ❌ | ❌ BLOCKED on Phase 5 | 2026-08-04 baseline |
| **Obligations** | DOM-OBL-001 | ✅ | ✅ | ⚠️ REVERIFY | ✅ | ⚠️ AUDIT GAP | ⚠️ PRODUCTION READY with known Phase 10 audit gap (2026-08-16): cross-layer template sweep missed — orphan `url_for` targets crashed rent/insurance/fines pages, fixed emergency in `053c20f4`. `rent_settings` mutation-pattern violation of DOM-POL-001 §VI documented (Scope B remediation pending). See `OBLIGATION_POLICIES_FOLLOWUP_2026-08-16.md`. | 2026-08-04 (ACCEPTED) + 2026-08-16 (gap surfaced) |
| **Store & Entitlements** | DOM-STORE-001 | ✅ | ✅ | ✅ VERIFIED | ✅ | ✅ | ✅ AUDITED (Phase 10 certified) | 2026-08-04 (PASS) |
| **Operations** | DOM-OPS-001 | 🔄 | ❌ | — | — | ❌ | 🔄 NOT STARTED | N/A |
| **Interpretation** | DOM-ITR-001 | 🔄 | ❌ | — | — | ❌ | 🔄 NOT STARTED | N/A |
| **Policies** | DOM-POL-001 | 🔄 (doctrine advanced 2026-08-16) | ❌ | — | — | ❌ | 🔄 PHASE 0-1 — doctrine substantially advanced (`policy_uuid` = version §VI.0; Insert & Availability Contract §VI; all `*_settings` scope §X). Phase 2+ still blocked on prior-domain sequencing. | 2026-08-16 (`OBLIGATION_POLICIES_FOLLOWUP_2026-08-16.md`) |
| **Support** | DOM-SUP-001 | 🔄 | ❌ | — | — | ❌ | 🔄 NOT STARTED | N/A |

**Legend:**

- ✅ = Passed/Complete with audit verification
- 🔄 = In progress, likely complete but NOT YET audited, or not started
- ❌ = Blocked (cannot proceed to next phase)
- ? = Unknown status (requires audit)

**What "Actually Complete" Means:**

- ✅ Phase 10 SOP-DEV-002a certification audit document exists with all checkmarks
- ✅ All 10 phases 0-10 have [x] marks in audit
- ✅ Tests pass (Phase 8)
- ✅ Routes use view models, templates use only view model fields (Phase 6-7)
- ✅ No legacy code remains (Phase 9)
- ✅ Domain is production-ready

**Unaudited domains:** Commits exist, code likely works, but require formal Phase 10 audit to confirm all phases are complete.

**AUDIT STATUS UPDATE (2026-08-08 REVISED):**

- **Identity:** Phases 0-10 complete ✅ **PRODUCTION READY** (Phase 10 certified 2026-08-06)
- **Class Config:** Phases 0-5 complete ✅ (Phase 5 with EconomicView stub caveat) | Phase 6-7 **PARTIAL** — 4 of 12 MAP-UI-001 rows rewired (2026-08-16)
- **Ledger:** Phases 0-1 complete | Phase 2 **PENDING** (schema migrations needed)
- **Payroll:** Phases 0-1 complete | Phase 2 **PENDING** (schema migrations needed)
- **Obligations:** Phases 0-10 complete ✅ **PRODUCTION READY** (Phase 10 audit ACCEPTED 2026-08-04)
- **Store:** Phases 0-10 complete ✅ **PRODUCTION READY** (Phase 10 audit passed 2026-08-04)
- **Operations, Interpretation, Policies, Support:** Phases 0-1 only, not started

---

## Phase 6-7 Verification: View Model Field Ownership

Phase 6-7 completion is now measured via **field ownership**, not template structure. A domain reaches Phase 7 when:

1. **Phase 6: View Model Wiring**
   - Every field owned by this domain is defined in its canonical view model(s)
   - Routes construct the view model and pass it to templates
   - No owned field is computed inline in routes or templates

2. **Phase 7: Surface Integration**
   - Every template that uses an owned field accesses it via the view model
   - Legacy field sources (old route variables, old model methods) are removed
   - Cross-domain field dependencies are explicitly tracked (see below)

### View Model Status by Domain

**Domains with view models (Phase 5 complete):**

| Domain | View Model(s) | Phase 6-7 Status | Audit Notes |
| -------- | --------------- | ----------------- | ------------- |
| **Obligations** | StudentObligationView | ✅ COMPLETE | Phase 6-7 validated: `period_status` dict properly implemented; templates use view.current_period namespace only; all 5 tests pass |
| **Store & Entitlements** | EntitlementListView, PurchaseHistoryView, PolicyListView, StoreManagementView | ✅ COMPLETE | Phase 10 audit passed; all fields wired via view.* namespace |
| **Identity** | IdentityProfileView | ✅ COMPLETE | Phase 10 certified (2026-08-06); all 10 phases verified |

**Domains WITHOUT view models (Phase 5 blocked):**

| Domain | Why Blocked | Action Needed |
| -------- | ------------ | --------------- |
| **Class Configuration** | 🔄 Phase 6-7 PARTIAL (2026-08-16) | 4/12 MAP-UI-001 rows rewired (rent/banking/payroll/economic_engine settings surfaces). EconomicView still stub. 6 rows still `NEEDS_REWIRE` (dashboard, create_class, settings, feature_settings, delete_join_code, students). 2 rows `VERIFY_ONLY` (set_current_class, feature settings read). |
| **Ledger** | No LedgerBalanceView | Create dataclass + builder function |
| **Payroll/Attendance** | No PayrollView or AttendanceView | Create 2 dataclasses + builder functions |
| **Operations** | Phase 0-1 only; not yet at Phase 5 | Start Phase 0-5 implementation |
| **Interpretation** | Phase 0-1 only; not yet at Phase 5 | Start Phase 0-5 implementation |
| **Policies** | Utility domain; no user-facing view | N/A (stores settings for other domains) |
| **Support** | Phase 0-1 only; not yet at Phase 5 | Start Phase 0-5 implementation |

**How to audit Phase 6-7:**

1. For each field owned by the domain, grep for template usage: `grep -r "view_model.field_name" templates/`
2. Verify the field is defined in the view model constructor
3. Verify the field is computed from a canonical service (Phase 3)
4. Verify no template uses legacy sources (e.g., `{{ legacy_variable }}` or `{{ computed_inline }}`)
5. Verify cross-domain dependencies are documented

---

## Misclassified FEATs and Docs

**Authority:** SOP-DEV-002 Phase 0 (Domain Boundary) requires clear ownership. These documents are currently in the wrong domain and must be reclassified.

| Document | Current Classification | Actual Owner | Issue | Status | Notes |
|----------|----------------------|--------------|-------|--------|-------|
| FEAT-CLASS-002 | DOM-CLASS (Class Configuration) | DOM-IDEN (Identity) | Modifying roster (student seats and identity profiles) is Identity domain concern, not class configuration | ⏳ TO BE RECLASSIFIED | Should be FEAT-IDEN-002 or similar |
| FEAT-CLASS-003 | DOM-CLASS (Class Configuration) | DOM-STORE (Store & Entitlements) | Insurance policy definitions and entitlements belong to Store/Entitlements domain; only the class-level feature toggle belongs in CLASS | ⏳ TO BE SPLIT | CLASS domain: enable/disable insurance feature only. Store domain: policy definitions, entitlement management |

**Reclassification Plan:**
- Phase 3 conformance audit identified these misclassifications (2026-08-09)
- Will be corrected in future domain boundary cleanup
- Does NOT block Phase 3 (Class Configuration) completion
- Recorded here for transparency and future reference

---

## Detailed Domain Status

### The 10 Domains (CTH v2)

#### Identity Domain (DOM-IDEN-001, 002, 003, 006)

**Canonical Tables:** `users`, `seats`, `classes`, `identity_profiles`, `user_invite_tokens`, `user_recovery_tokens`  
**Phase:** ✅ 0-10 (COMPLETE & CERTIFIED)  
**Status:** ✅ **PRODUCTION READY** (Phase 10 certified 2026-08-06)  
**Last Audit:** 2026-08-06 (PASS) — `docs/TRACKING/SOP-DEV-002a_IDENTITY_20260806_AUDIT.md`  
**Key Achievement:** User/Seat canonical identity active; IdentityProfileView wired to student_detail surface; full Phase 9 legacy sweep confirmed no dead code  
**Notes:** Remaining bridge tables `Admin`, `Student`, `StudentTeacher` exist for backward compat; will be deleted in final cleanup  
**Next Action:** None — domain is production-ready

---

#### Class Configuration Domain (DOM-CLASS-001)

**Scope:** class_id (canonical), join_code (public alias), display name, section, timezone, CWI settings (policy mode, expected_weekly_hours on EconomicEngine, pricing ratios based on CWI and policy)  
**Canonical Tables:** `classes`, `class_features`, `economic_engine`, `feature_settings`, `hall_pass_settings`, `rent_settings`, `payroll_settings`, `payroll_rewards`, `payroll_fines`, `banking_settings`  
**Phase:** ✅ Phase 0-4 COMPLETE | ⚠️ Phase 5 (EconomicView stub) | 🔄 Phase 6-7 PARTIAL | ❌ Phase 8-10  
**Status:** Phase 7 in progress. Settings surfaces (rent, banking, payroll, economic_engine) rewired class_id-authoritative. `expected_weekly_hours` migrated from PayrollSettings to canonical EconomicEngine. `block`-as-scope pattern eliminated from all class-config-owned routes/services. CWI-unconfigured state renders warning path (no fallback). Test suite: 96/96 passing.  

**Phase 2 Achievements (COMPLETED):**
- ✅ Class economy immutability: EconomicEngine model with before_update event listener prevents post-commit modifications
- ✅ Append-only features timeline: ClassFeature composite PK (class_id, feature, effective_at); version_chain with previous_version_id FK
- ✅ Schema migrations: Phase 2a (immutable versioning), 2b (composite PK enforcement), 2c (consumer migrations), 2d (test infrastructure updates)
- ✅ Consumer migrations: 22 references across 7 files (routes, services, tests, templates) updated from ClassEconomy.user_id → teacher_user_id
- ✅ Test infrastructure: Migrated to SPEC-TEST-001 (canonical initializer) and SPEC-TIME-001 (canonical temporal resolver) patterns

**Phase 3 Achievements (COMPLETED 2026-08-11):**
- ✅ 17 read-only query functions in `class_configuration_query_service.py`
- ✅ 55 tests passing (happy path, empty state, multi-tenancy per function)
- ✅ CWI calculation, policy mode, feature enablement, temporal queries
- ✅ Teacher-facing guidance functions (suggest_economic_mode, validate_payroll_rate)

**Phase 4 Achievements (COMPLETED 2026-08-12):**
- ✅ Core reads centralized: 21 direct ClassEconomy.query calls replaced with service layer functions (1 mutation-only call remains inside @feat_shell)
- ✅ Mutations through FEAT boundaries: all class-config writes use @feat_shell or FEATContext
- ✅ 4 new service helpers: get_teacher_classes_by_ids, get_class_by_public_id, get_classes_by_public_ids (get_teacher_class_by_section removed 2026-08-16 as dead v1 helper)
- ✅ Fixed stale ClassEconomy.user_id → teacher_user_id references
- ✅ Fixed full-table-scan anti-pattern in recovery route

**Phase 6-7 Achievements (PARTIAL, 2026-08-16 session):**
- ✅ FEAT-CLASS-005 generalized from policy-mode-only to arbitrary EconomicEngine field updates (`execute_evolve_economic_engine(updates={...})`); carry-forward semantics; `execute_transition_economic_policy()` retained as backward-compat wrapper
- ✅ FEAT-CLASS-001 accepts optional initial `expected_weekly_hours`
- ✅ `PayrollSettings.expected_weekly_hours` column DROPPED (migration `a4e8f19d7c31`); canonical location is `EconomicEngine.expected_weekly_hours` per DOM-CLASS-002
- ✅ `calculate_cwi()` refactored to read from `EconomicEngine` via `get_effective_economic_engine('payroll')`; returns `None` when unconfigured (no fallback)
- ✅ `analyze_economy()` returns empty analysis with WARNING when CWI unconfigured; economic_engine page shows "configure expected weekly hours" alert
- ✅ New route `/admin/economy/update-expected-hours` → `FEAT-CLASS-005` (was `/admin/payroll/update-expected-hours` writing to PayrollSettings)
- ✅ `update_economy_policy` route now writes via `FEAT-CLASS-005` (was writing directly to `FeatureSettings.economy_policy_mode`); reads via `get_active_policy_mode_for_class()` (EconomicEngine-backed)
- ✅ `upsert_payroll_settings` auto-creates active `PolicyVersion` snapshot for payroll domain (was blocking `/admin/run_payroll` with "No active payroll policy version")
- ✅ Rewired settings routes to class_id-only (removed `blocks_to_update` pattern, `for block in blocks_to_update:` loops, `selected_scope['block']` usage): `rent_settings`, `banking_settings_update`, `payroll_settings`, `update_expected_weekly_hours`
- ✅ Rewired `EconomyBalanceChecker(user_id, block=..., class_id=...)` → `(user_id, class_id=...)`. Deleted `self.block` mode switch — rent validation always uses policy-mode weekly bands. Updated 7 call sites.
- ✅ Rewired `_load_economy_rebalance_context(ctx, class_id, selected_block)` → `(ctx, class_id)`. Removed cross-class `all_payroll_settings` aggregation.
- ✅ Rewired `_build_rebalance_preview` and `_filter_economy_health_warnings` — removed `selected_block` params
- ✅ Rewired `_build_payroll_preview_state(students, class_ids_by_block)` → `(students)` — dead parameter removed
- ✅ Cleaned `economic_engine`, `payroll`, `banking`, `rent_settings` routes: removed `teacher_blocks`, `settings_block`, `class_labels_by_block`, `join_codes_by_block`, `dashboard_blocks`, `class_ids_by_block`, `selected_block`, `cwi_block` local variables and template kwargs
- ✅ Removed `PayrollSettings.block.is_(None).desc()` and `BankingSettings.block.is_(None).desc()` orderings (v1 artifacts)
- ✅ Rent recommendation display bug fixed: template was using `recommendations.rent` (monthly) with "per week" label; corrected to `recommendations.rent_weekly`
- ✅ Removed 5.0 fallback for `expected_weekly_hours` — CWI now returns None, pricing recommendations disabled with warning, features still work

**MAP-UI-001 Row Status (12 rows):**
| # | Row | Status | Notes |
|---|---|---|---|
| 153 | Create class (`admin.create_class`) | ❌ NEEDS_REWIRE | Not touched 2026-08-16 |
| 154 | View class list (`admin.dashboard`) | ❌ NEEDS_REWIRE | Not touched |
| 155 | Select current class (`admin.set_current_class`) | ⏳ VERIFY_ONLY | Not verified |
| 156 | Enable feature (`admin.feature_settings` POST) | ❌ NEEDS_REWIRE | Not touched |
| 157 | Disable feature (`admin.feature_settings` POST) | ❌ NEEDS_REWIRE | Not touched |
| 158 | Transition economic policy (`admin.apply_economy_rebalance`) | ✅ REWIRED (2026-08-16) | Now via `execute_evolve_economic_engine` w/ CWI guard |
| 159 | Update timezone (`admin.set_class_timezone`) | ⚠️ CONFLICT | DOM-CLASS-001 §V says timezone is immutable; row must be reconciled |
| 160 | View class configuration (`admin.customizations` / renamed from `admin.settings`) | ❌ NEEDS_REWIRE | Route renamed 2026-08-15; view model wiring pending |
| 161 | View feature configuration status | ⏳ VERIFY_ONLY | Not verified |
| 162 | View class economy dashboard (`admin.economic_engine`) | ✅ REWIRED (2026-08-16) | Fully class_id-authoritative; CWI-unconfigured state handled |
| 163 | View enrollment/students (`admin.students`) | ❌ NEEDS_REWIRE | Not touched |
| 164 | Delete class / join code (`admin.delete_join_code`) | ❌ NEEDS_REWIRE | Not touched; retention policy unpinned |
| (bonus) | Update `expected_weekly_hours` (`admin.update_expected_weekly_hours`) | ✅ REWIRED (2026-08-16) | Via FEAT-CLASS-005 |
| (bonus) | Update economic policy mode (`admin.update_economy_policy`) | ✅ REWIRED (2026-08-16) | Via FEAT-CLASS-005 |

**Pending View Models:**
- ⏳ **EconomicView** — Full pricing/CWI/economy-health calculator still pending. Current impl in `class_configuration_economic_service.py` populates `display_context` with `expected_weekly_hours` (from EconomicEngine), `hourly_rate`, `policy_mode`; suggests low/medium/high pricing tiers; has warning strings. Consumers (Store) partially wired but need broader adoption verification.
- ✅ **ClassConfigurationView**, **ClassSummaryView**, **FeatureConfigurationView** — Implemented Phase 5

**Constitutional Issues Surfaced (must reconcile before Phase 10 audit):**
1. **Timezone mutation contradiction** — DOM-CLASS-001 §V says `timezone` "MUST NOT be mutated afterward"; MAP-UI-001 row 159 lists `admin.set_class_timezone` action. Resolve: remove the route, or amend DOM-CLASS-001, or restrict to controlled engine-evolution decision.
2. **Class deletion semantics** — DOM-CLASS-001 §VII.1 says class deletion removes class + all class-owned config rows; MAP-UI-001 §IX.7 defers hard vs soft delete to DOM-CLASS-002 retention + INV-ARC-016. Retention policy must be pinned.
3. **`FEAT-CLASS-002` namespace collision** — MAP-UI-001 row 159 references TBD `FEAT-CLASS-002` for class-boundary work; Matrix "Misclassified FEATs" uses same identifier for the identity-domain reclassification. Pick one.
4. **`FEAT-CLASS-003` split incomplete** — insurance feature toggle stays in CLASS; policy definitions/entitlements move to Store per DOM-STORE-001. Confirm class-level toggle FEAT scope.
5. **`EconomicView` stub completion** — flagged as blocker for Store consumer certification. Current implementation is partial.

**Legacy v1 Helpers Still Present (Phase 9 deletion targets, out-of-scope for class-config domain):**
`_get_teacher_blocks`, `_resolve_block_class_ids`, `_get_class_labels_for_blocks`, `_get_join_codes_by_block`, `_get_class_ids_by_block` remain in `admin.py`. Still consumed by dashboard, hall_pass, insurance, attendance_log, and transfer routes (each is a different domain). Removal requires domain-specific rewrites and is not blocking class-config Phase 7 completion.

**Notes:** `join_code` is public alias for class_id; block/period is display-only metadata; timezone is class-immutable per constitutional spec (row 159 conflict noted above).  

**Next Actions (in order):**
1. Complete `EconomicView` full implementation (Phase 5 residual)
2. Reconcile 5 constitutional issues above (either amend specs or align code)
3. Rewire remaining 6 MAP-UI-001 rows: `create_class`, `dashboard`, `customizations`, `feature_settings` (enable/disable), `students`, `delete_join_code`
4. Verify 2 `VERIFY_ONLY` rows: `set_current_class`, feature settings read
5. Record Phase 8 verification commands per row (12 rows × command evidence)
6. Phase 9 legacy deletion (direct `ClassEconomy.query`, legacy template variables, dead `blocks` helpers where feasible per neighboring domains)
7. Run SOP-DEV-002a Phase 10 certification audit → produce `SOP-DEV-002a_CLASS_CONFIG_YYYYMMDD_AUDIT.md`

---

#### Ledger Domain (DOM-LED-001)

**Canonical Tables:** `ledger_transaction`, `ledger_balance_snapshot`  
**Phase:** 🔄 0-? (Unaudited)  
**Status:** Commits exist, likely complete but needs Phase 10 audit  
**Key Achievement:** `transaction` → `ledger_transaction` migration complete; FEAT-LED-000 canonical monetary resolution active  
**Notes:** `BalanceCache` dropped; all balance reads flow through canonical ledger queries  
**Next Action:** Create Phase 10 audit document with template verification

---

#### Productivity & Payroll Domain (DOM-PROD-001)

**Scope:** Attendance tracking, payroll execution, rewards, fines (includes attendance sessions, hall pass logs, payroll state, reward/fine definitions and application)  
**Canonical Tables:** `attendance_sessions`, `hall_pass_logs`, `seat_attendance_state`, `payroll_settings`, `payroll_rewards`, `payroll_fines`  
**Phase:** 🔄 0-? (Unaudited)  
**Status:** Commits exist, likely complete but needs Phase 10 audit  
**Key Achievement:** Attendance and payroll calculations in service layer; routes thin; view models canonical  
**Notes:** Early work; completed before structured SOP-DEV-002a audits were formalized. Attendance domain merged into this domain.  
**Next Action:** Create Phase 10 audit document with template verification

---

### IN PROGRESS (Failing Tests, Must Fix Before Merge)

#### Obligations Domain (DOM-OBL-001)

**Scope:** Rent, insurance premiums, fines (assessment events, lifecycle, satisfaction, reversal; obligation tracking and settlement)  
**Canonical Tables:** `assessment_events`, `obligation_lifecycle`, `obligation_satisfaction`, `obligation_reversal`, `entitlement_events`  
**Phase:** ⚠️ 0-10 (CERTIFIED with known gap — reverify recommended)  
**Status:** ⚠️ **PRODUCTION READY with known Phase 10 audit gap** (2026-07-26 audit ACCEPTED; 2026-08-16 gap surfaced)  
**Last Audit:** 2026-08-04 (ACCEPTED) — `docs/TRACKING/OBLIGATION_DOMAIN_QA_AUDIT_AUG_2026.md`  
**Follow-up findings:** 2026-08-16 — `docs/TRACKING/OBLIGATION_POLICIES_FOLLOWUP_2026-08-16.md`

**Known audit gaps (2026-08-16):**

1. **Cross-layer template sweep missed.** Backend routes `admin.reverse_cycle_penalties` (deleted `6c9c3857`) and `admin.remove_rent_waiver` (deleted `eeef3de7`) were removed for FEAT-OBL-003 immutability compliance, but corresponding UI in `templates/admin_rent_settings.html` was left behind. Every teacher-facing template touching the domain crashed on load with `werkzeug.routing.exceptions.BuildError`. Emergency-fixed in commit `053c20f4`.

2. **`rent_settings` mutation-pattern violation of `DOM-POL-001 §VI`.** `rent_settings` is designed as a mutable singleton (`class_id` `unique=True`, `updated_at` `onupdate=utc_now`); all writers mutate the existing row in place. Under the now-clarified doctrine, `rent_settings` is a Policies-repository table and each teacher submission must produce a new immutable row with a new `policy_uuid`. Scope B remediation documented in follow-up doc; **not remediated in current branch**.

3. **Dead schema removed (Scope A).** `rent_settings.active_version_id` and `rent_settings.next_version_id` (orphans of an abandoned rent-specific versioning attempt) dropped by migration `2978fdba914a`.

4. **Removed-column landmines across obligation code paths.** Static audit surfaced references to columns DOM-OBL-001 v2.5 removed from `ObligationAssessment` (`.assessed_at`, `.due_at`) across `app/routes/student.py`, `app/services/obligation_view_model.py`, and one route in `app/routes/admin.py`. All were pre-existing on the certified branch — the Phase 10 audit did not catch them because happy-path testing didn't exercise the crashing code paths. Missing helper `obligations_service.get_active_rent_waivers_for_class` (same class of bug — the prior fix `bf40e23e` on `claude/vigilant-tesla-758abf` orphaned) was ported. Two new resolvers (`resolve_assessment_amount`, `resolve_assessment_due_at`) added per DOM-OBL-001 §V.1 + §VII (amount from upstream policy via `policy_uuid`; due_at from `bill_cycle.assessment_at`). Fixed in commits `3e31acb2` and `29321eb3`.

5. **Initial Playwright verification was a false positive.** The subagent-run harness reported PASS for all obligation teacher routes but was actually recording final-URL-after-redirect status, not requested-URL status. Silent auth redirects passed as PASS. See `OBLIGATION_POLICIES_FOLLOWUP_2026-08-16.md` §VI for full post-mortem and §VII for the mandatory harness contract going forward.

**Next Action:** re-run Phase 10 for Obligations after Scope B remediation, with the revised Phase 10 gate (see follow-up doc §VII.3): mandatory cross-layer template sweep meeting harness contract §VII.1, mandatory view-model attribute-exercise test §VII.2, mandatory co-audit with Policies §VII.3, mandatory field-removal grep §VII.4.

---

#### Store & Entitlements Domain (DOM-STORE-001)

**Scope:** Classroom store items, student purchases, redemptions, entitlements (store catalog and student entitlement tracking)  
**Canonical Tables:** `entitlement_events`, `pending_actions`, `store_items` (via policy resolver), `store_item_visibility`  
**Phase:** ✅ 0-10 (COMPLETE & CERTIFIED)  
**Status:** ✅ **PRODUCTION READY** (Phase 10 audit passed 2026-08-04)  
**Last Audit:** 2026-08-04 (PASS) — `docs/TRACKING/SOP-DEV-002a_STORE_20260804_AUDIT.md`  
**Key PRs:**

- #1293: Store foundation: canonical resolver and policy view boundary
- #1294: Store behavior: FEAT wiring for purchase, grant, and claims
- #1295: Store docs: surface map and archival closeout
- #1299: Organize store domain documentation after completion
- Phase 6-7 wiring: 2026-08-04 (view model consolidation, template refactoring)

**Key Achievement:** 
- Full canonical store domain with FEAT-wired mutations, immutable view models, and comprehensive docs
- Phase 6-7 completion: StoreManagementView consolidates admin dashboard; all template access via view model
- All 10 phases independently verified and certified

**Dependencies Unblocked:** Operations and Interpretation domains may now proceed (Store ✅)

---

### NOT STARTED (Awaiting Sequence)

#### Operations Domain (DOM-OPS-001)

**Scope:** Operational events, audit lineage, incident tracking, job scheduling, health checks  
**Canonical Tables:** `operational_events`, `audit_log`, `incident_events`, `incident_summary`, `alert_events`, `invariant_run_events`, `job_events`, `health_check_events`  
**Phase:** 🔄 0-1 (Spec review)  
**Status:** NOT STARTED (blocked on prior domain audits)  
**Dependency Chain:** Ledger (unaudited) → Productivity & Payroll (unaudited) → Obligations (blocked) → Store (✅ CERTIFIED) → **CAN NOW PROCEED**

---

#### Interpretation Domain (DOM-ITR-001)

**Scope:** Economic health metrics (budget survivability, money velocity), economic alerts, actionable feedback to teachers  
**Canonical Tables:** `interpretation_snapshots`, `interpretation_annotations`, `alert_events`  
**Phase:** 🔄 0-1 (Spec review)  
**Status:** NOT STARTED (blocked on prior domain audits)  
**Dependency Chain:** Ledger (unaudited) → Store (✅ CERTIFIED) → Operations (not started) → **BLOCKED UNTIL LEDGER AUDITED; STORE READY**  
**Notes:** Generates economic health alerts and recommendations for teachers; feeds from Ledger and Operations event streams

---

#### Policies Domain (DOM-POL-001)

**Scope:** Append-only immutable repository of class-scoped policy definitions. Stores what other domains submit; does not originate mutation flows. Consumers reference each row by `policy_uuid` (which **is** the version identifier — no separate version pointer permitted).
**Canonical Tables (per `DOM-POL-001 §X` boundary attribution):**

- `rent_settings` — consumed by `DOM-OBL-001`
- `payroll_settings`, `payroll_rewards`, `payroll_fines` — consumed by `DOM-PROD-001`
- `hall_pass_settings` — consumed by `DOM-PROD-001` at grant time
- `store_items`, `store_item_visibility` — consumed by `DOM-STORE-001`
- Insurance policy definitions — consumed by Insurance operational flow

**NOT in this repository:** `banking_settings` (savings APY, overdraft fees, interest formulas) is inherently Class Config → `economic-engine` per `DOM-CLASS-001` / `DOM-CLASS-002`; versioned under `DOM-CLASS-003` (`policy_versions` / `policy_transitions`), which is **economic-policy lineage only**, not domain-policy storage.

**Phase:** 🔄 0-1 (Spec review; doctrine substantially advanced 2026-08-16)  
**Status:** Doctrine now sufficient to begin Phase 2 planning; execution still blocked on prior-domain sequencing.

**Doctrine advances (2026-08-16):**

- ✅ `DOM-POL-001 §VI.0` — `policy_uuid` promoted to first-class definitional statement (**IS** the version; no separate pointer permitted).
- ✅ `DOM-POL-001 §VI` — renamed from "Mutation Contract" to "Insert and Availability Contract"; Insert/Update collapsed to single Insert action.
- ✅ `DOM-POL-001 §X` — boundary table extended to cover all policy `*_settings` tables and explicit exclusion of `banking_settings`.
- ✅ `DOM-CORE-001` / `DOM-CORE-002` — ownership contradictions corrected; all `*_settings` tables routed through `DOM-POL-001`.
- ✅ `DOM-PROD-001 §XII` — coordination bullets rewritten (payroll/hall-pass are Policies-stored, PROD-consumed).

**Follow-up doc:** `docs/TRACKING/OBLIGATION_POLICIES_FOLLOWUP_2026-08-16.md`

**Dependency Chain:** All consumer domains (Obligations, PROD, Store, Insurance) → Policies is subordinate to their audit sequencing.  
**Notes:** Utility/persistence domain; no business logic. Phase 2 (persistence audit) is the natural next step once dependency chain unblocks.

---

#### Support Domain (DOM-SUP-001)

**Scope:** Issue tracking, announcements, support ticket management, resolution actions  
**Canonical Tables:** `issues`, `issue_status_history`, `issue_resolution_actions`, `ticket_correlation_packs`, `announcements`, `issue_categories`  
**Phase:** 🔄 0-1 (Spec review)  
**Status:** NOT STARTED (blocked on prior domain audits)  
**Dependency Chain:** Operations (not started) → Support → **BLOCKED UNTIL OPERATIONS AUDITED**

---

## Domain Dependencies (Critical Path)

**Can start immediately (no dependencies):**

- Identity
- Class Config
- Ledger

**Depend on Ledger + Class Config:**

- Productivity & Payroll (depends on Ledger for payroll calculations, Class Config for settings)
- Obligations (depends on Ledger for settlement, Class Config for settings)
- Store & Entitlements (depends on Ledger for purchase transactions, Class Config for pricing)

**Depend on Ledger + Productivity & Payroll + Obligations + Store:**

- Operations (depends on all to track events, maintain audit lineage)

**Depend on Ledger + Store + Operations:**

- Interpretation (depends on Ledger for financial data, Store for transaction data, Operations for event stream; generates economic health alerts)

**Depend on all domains (utility domain):**

- Policies (stores settings and version history for each domain; each domain owns its settings config)

**Depend on Operations:**

- Support (depends on Operations for incident tracking, audit events)

---

## Critical Path to Production

**Current Status:**

- ✅ **3 domains PRODUCTION READY:** Identity (Phase 10 certified 2026-08-06), Obligations (Phase 10 ACCEPTED 2026-08-04), Store (Phase 10 certified 2026-08-04)
- 🔄 **1 domain Phase 5 COMPLETE:** Class Config (view models defined and tested; Phase 6-7 route/template wiring pending)
- 🔄 **2 domains Phase 1 COMPLETE:** Ledger, Productivity & Payroll (Phase 2 schema work needed)
- 🔄 **4 domains NOT STARTED:** Operations, Interpretation, Policies, Support

**STATUS UPDATE (2026-08-11):** Class Configuration Phase 3 (read-only query service) COMPLETE. 17 service functions, 55 tests passing. Phase 4 (FEAT mutation boundary) is next. Ledger and Payroll unblocked and ready for Phase 2 schema work.

**Minimum Path Forward (Priority Order):**

1. **HIGH (P1):** Create missing view models for 3 domains (Class Config, Ledger, Payroll)
   - Blocked at Phase 5 until complete
   - Estimated 20-30 hours
2. **HIGH (P1):** Refactor routes and templates to use view models (Phase 6-7)
   - Applies to all 3 domains once Phase 5 view models created
   - Estimated 15-20 hours
3. **HIGH (P1):** Audit 11 direct db.session mutations in routes (Phase 4 enforcement)
   - Estimated 10-15 hours
4. **MEDIUM (P2):** Run Phase 10 audits for remaining 7 domains using SOP-DEV-002a checklist
   - Estimated 70-105 hours (10-15 per domain after phases 5-9 complete)
   - Focus on template field verification (as done with Obligations and Store)
5. **MEDIUM (P2):** Start Operations, Interpretation, Policies, Support domains (Phase 0-1)
   - Only after Ledger, Productivity & Payroll audited
6. **FINAL:** Production readiness validation gate (all 10 domains Phase 10 certified)

---

## How to Use This Matrix

### For Implementation Work

1. **Find your domain** in the "Detailed Domain Status" section
2. **Identify the current phase** (see Status Table or domain detail)
3. **Read the blocking issues** and next actions
4. **Pick ONE blocker** and create a focused PR to advance it
5. **After completing, update this matrix** with the new phase status and commit with: `tracking: update domain-progress-matrix for [DOMAIN] phase [N]`

### For Cross-Domain Dependency Checks

1. **Find your domain** in the "Domain Dependencies" section above
2. **Identify dependencies** (e.g., Support requires Operations; Operations requires Ledger)
3. **Verify dependent domains** are audited and working before starting your domain

### For PR Reviews

1. **Check the domain phase matrix** for current status
2. **Verify the PR advances the phase** (e.g., should only modify routes/templates if phase 5-7)
3. **Ensure SOP-DEV-002 criteria are met** before approving
4. **Update this matrix** after merge

### For Audit Planning

1. **Check if domain is at Phase 10 candidate**
2. **Run SOP-DEV-002a audit** using the template in `docs/STANDARD_OPERATING_PROCEDURES/DEVOPS/SOP-DEV-002a_DOMAIN_RECONSTRUCTION_QA_AUDIT.md`
3. **Record results** in "Last Audit" field
4. **Update matrix with pass/fail** status

---

## Archive of Previous Tracking Docs

The following tracking documents remain for historical reference but are **superseded by this matrix**:

| File | Status | Reason |
| ------ | -------- | -------- |
| `V2_Full_compliance_migration_plan.md` | Archived | Replaced by wave/phase matrix structure |
| `OBLIGATIONS_DOMAIN_PHASE10_CERTIFICATION_AUDIT_2026-07-26.md` | Reference | Linked in Obligations section |
| `SOP-DEV-002a_STORE_20260731_AUDIT.md` | Reference | Linked in Store section |
| `TERMINOLOGY_AUDIT_V1.md` | Reference | Historical v1 audit |
| `V2_REBUILD_VALIDATION_REPORT.md` | Reference | Early validation snapshot |
| `TEMPLATE_AUDIT_FOR_REWIRING/*` | Reference | Route audit templates (use for Phase 6-7 work) |

---

## How to Update This Matrix

**When you complete a phase or domain:**

1. Find the domain row
2. Update the phase checkboxes (✅, ⚠️, ❌, 🔄)
3. Update the "Phase" cell with new status
4. Add notes about what changed
5. Update "Last Updated" timestamp
6. Commit with message: `tracking: update domain-progress-matrix for [DOMAIN] phase [N]`

**Format for blocking issues:**

```markdown
**Blocking Issues:**
1. [Issue] — [Impact]
   - Root cause or technical detail
   - Next action to resolve
```

**Example updates:**

```markdown
- Obligations: ✅ 0-4 | ✅ 5-7 | ✅ 8 | ⚠️ 9 (legacy deletion incomplete)
- Store: ✅ 0-7 | ⚠️ 8 (test coverage gap on entitlement view models)
```

---

## References

- **SOP-DEV-002a:** `docs/STANDARD_OPERATING_PROCEDURES/DEVOPS/SOP-DEV-002a_DOMAIN_RECONSTRUCTION_QA_AUDIT.md`
- **Authority Specs:**
  - `docs/INVARIANT/CORE/INV-CORE-000_FOUNDATIONAL_INVARIANTS.md`
  - `docs/DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
- **Domain Specs:** `docs/DOMAIN/DOM-*.md`
- **FEAT Registry:** `docs/FEATURE-EXECUTION/` (all FEAT-* specs)
- **Previous Tracking:** `docs/TRACKING/V2_Full_compliance_migration_plan.md` (historical reference)

---

## Cross-Cutting: SPEC-TIME-001 Browser Timezone Compliance (2026-08-14)

**Status:** ✅ COMPLETE

**Change:** Removed `static/js/timezone-utils.js` and `/api/set-timezone` endpoint. All timestamp display now uses server-side Jinja filters (`fmt_timestamp`, `fmt_date`, `fmt_compact_date`, `fmt_time`) via `app/utils/temporal_display.py`, compliant with SPEC-TIME-001 and MAP-UI-002 §VII.

**What was removed:**
- `static/js/timezone-utils.js` — browser-side timezone detection (prohibited by SPEC-TIME-001 §XII)
- `/api/set-timezone` endpoint — stored browser-detected timezone in session (violated INV-ARC-015 §VI.4)
- `window.TimezoneUtils` JS API — all callers migrated to server-formatted timestamps
- `local-timestamp` CSS class pattern — client-side timestamp conversion replaced with server-rendered output
- Service worker cache entry for `timezone-utils.js`

**What was added:**
- `app/utils/temporal_display.py` — SPEC-TIME-001 compliant formatting functions and Jinja filters
- `inject_display_timezone` context processor — resolves `ClassEconomy.class_timezone` once per request (Temporal Context layer per MAP-UI-002 §VII)
- Server-formatted `formatted_timestamp` field in attendance history and hall pass history APIs

**Affected templates:** All templates that previously used `local-timestamp` spans (60+ occurrences across admin, student, and sysadmin shells).

**Spec compliance:**
- Display timezone = `ClassEconomy.class_timezone` for CLE, `UTC` for SLE (SPEC-TIME-001 §X)
- No browser timezone detection (SPEC-TIME-001 §XII)
- No hardcoded `America/Los_Angeles` (SPEC-TIME-001 §XII)
- Temporal Context resolved once at request boundary, not queried from Jinja (MAP-UI-002 §VII, §IX)

---

**Last Updated:** 2026-08-14 (SPEC-TIME-001 browser timezone compliance; Identity Phase 10 CERTIFIED; 3 domains production-ready)
**Maintained By:** Development Team
**Canonical:** YES (This matrix is the single source of truth for domain progress)
