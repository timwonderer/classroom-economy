# CTH Domain Reconstruction Progress Matrix

**Status:** Active Canonical Tracker  
**Last Updated:** 2026-08-04 (CORRECTED — requires audit verification)  
**Authority:** SOP-DEV-002a, INV-CORE-000, DOM-CORE-002  

**⚠️ CRITICAL NOTE:** This matrix is being rebuilt with actual audit verification. "Complete" now means Phase 10 audit certification with all checkmarks. Domains without audit documentation are marked "likely complete but unaudited" pending verification.

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
| **Identity** | DOM-IDEN-001/002/003/006 | ✅ | ❌ NO VM | ❌ BLOCKED | ? | ❌ | ❌ BLOCKED on Phase 5 | 2026-08-04 baseline |
| **Class Configuration** | DOM-CLASS-001 | ✅ | ❌ NO VM | ❌ BLOCKED | ? | ❌ | ❌ BLOCKED on Phase 5 | 2026-08-04 baseline |
| **Ledger** | DOM-LED-001 | ✅ | ❌ NO VM | ❌ BLOCKED | ? | ❌ | ❌ BLOCKED on Phase 5 | 2026-08-04 baseline |
| **Productivity & Payroll** | DOM-PROD-001 | ✅ | ❌ NO VM | ❌ BLOCKED | ? | ❌ | ❌ BLOCKED on Phase 5 | 2026-08-04 baseline |
| **Obligations** | DOM-OBL-001 | ✅ | ✅ | ❌ TEMPLATE FAILS | ? | ❌ | ❌ AUDIT INVALID | 2026-08-04 (Phase 6-7 undefined vars) |
| **Store & Entitlements** | DOM-STORE-001 | ✅ | ✅ | ✅ VERIFIED | ✅ | ✅ | ✅ AUDITED (Phase 10 certified) | 2026-08-04 (PASS) |
| **Operations** | DOM-OPS-001 | 🔄 | ❌ | — | — | ❌ | 🔄 NOT STARTED | N/A |
| **Interpretation** | DOM-ITR-001 | 🔄 | ❌ | — | — | ❌ | 🔄 NOT STARTED | N/A |
| **Policies** | DOM-POL-001 | 🔄 | ❌ | — | — | ❌ | 🔄 NOT STARTED | N/A |
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

**AUDIT STATUS UPDATE (2026-08-04):**

- **Identity:** Phases 0-4 complete, Phase 5 **BLOCKED** (no view model), Phase 6-7 **BLOCKED**
- **Class Config:** Phases 0-4 complete, Phase 5 **BLOCKED** (no view model), Phase 6-7 **BLOCKED**
- **Ledger:** Phases 0-4 complete, Phase 5 **BLOCKED** (no view model), Phase 6-7 **BLOCKED**
- **Payroll:** Phases 0-4 complete, Phase 5 **BLOCKED** (no view model), Phase 6-7 **BLOCKED**
- **Obligations:** Phases 0-5 complete, Phase 6-7 **INVALID** (template uses undefined variables: `period_status`, `days_until_due`)
- **Store:** Phases 0-10 complete ✅ **PRODUCTION READY** (Phase 6-7 wiring completed 2026-08-04, Phase 10 audit passed)
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
| **Obligations** | StudentObligationView | ❌ INVALID | Templates use undefined variables; must add `period_status` dict |
| **Store & Entitlements** | EntitlementListView, PurchaseHistoryView, PolicyListView | ⚠️ UNVERIFIED | Exists but Phase 10 audit pending |

**Domains WITHOUT view models (Phase 5 blocked):**

| Domain | Why Blocked | Action Needed |
| -------- | ------------ | --------------- |
| **Identity** | No IdentityProfileView | Create dataclass + builder function |
| **Class Configuration** | No ClassConfigurationView | Create dataclass + builder function |
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

## Detailed Domain Status

### The 10 Domains (CTH v2)

#### Identity Domain (DOM-IDEN-001, 002, 003, 006)

**Canonical Tables:** `users`, `seats`, `classes`, `identity_profiles`, `user_invite_tokens`, `user_recovery_tokens`  
**Phase:** 🔄 0-? (Unaudited)  
**Status:** Commits exist, likely complete but needs Phase 10 audit  
**Key Achievement:** User/Seat canonical identity active; legacy Admin/Student tables dropped from runtime auth  
**Notes:** Remaining bridge tables `Admin`, `Student`, `StudentTeacher` exist for backward compat; will be deleted in final cleanup  
**Next Action:** Create Phase 10 audit document with template verification

---

#### Class Configuration Domain (DOM-CLASS-001)

**Scope:** class_id (canonical), join_code (public alias), display name, section, timezone, CWI settings (policy mode, interest rate, pricing ratios based on CWI and policy)  
**Canonical Tables:** `classes`, `class_features`, `feature_settings`, `hall_pass_settings`, `rent_settings`, `payroll_settings`, `payroll_rewards`, `payroll_fines`, `banking_settings`  
**Phase:** 🔄 0-? (Unaudited)  
**Status:** Commits exist, likely complete but needs Phase 10 audit  
**Key Achievement:** Settings migrated to canonical; `class_id` canonical scope enforcement with timezone and CWI configuration  
**Notes:** `join_code` is public alias for class_id; block/period is display-only metadata  
**Next Action:** Create Phase 10 audit document with template verification

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
**Phase:** ✅ 0-5 | ⚠️ 6-7 INVALID | ✅ 8-9 | ❌ 10 INVALID  
**Status:** BLOCKED — Phase 10 audit invalid (templates access undefined variables)  
**Last Audit:** 2026-07-26 (FALSE CHECKMARKS — templates not actually verified)  
**Blocking Issue:** Templates (`student_rent.html`) access `period_status[current_block]` and `days_until_due` which are NOT:

- Passed from routes
- Defined in StudentObligationView
- Set in templates

**Key Achievement:** Canonical schema and FEAT mutations complete; Phase 6-7 templates need refactoring  
**Next Action:** Fix templates to use ONLY view model fields; re-run Phase 6-7 verification

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

**Scope:** Settings and versioning storage for each domain (NOT business logic, just persistence of configuration and version history)  
**Canonical Tables:** Per-domain settings tables and versioning logs (structure determined by each domain's needs)  
**Phase:** 🔄 0-1 (Spec review)  
**Status:** NOT STARTED (blocked on prior domain audits)  
**Dependency Chain:** All domains (each domain owns its settings, Policies just stores them) → **BLOCKED UNTIL PRIOR DOMAINS AUDITED**  
**Notes:** This is a utility/persistence domain, not a business logic domain

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

- ❌ **0 domains AUDITED:** Obligations audit is INVALID (templates access undefined variables, Phase 6-7 failed)
- 🔄 **6 domains UNAUDITED AND UNTRUSTED:** Identity, Class Config, Ledger, Productivity & Payroll, Obligations, Store & Entitlements
  - No valid Phase 10 audit documents
  - No Phase 6-7 template verification
- 🔄 **4 domains NOT STARTED:** Operations, Interpretation, Policies, Support

**CRITICAL BLOCKER:** The only existing Phase 10 audit (Obligations) has false checkmarks. Templates were NOT actually verified. **No domain is known to be end-to-end complete.**

**Minimum Path Forward (Priority Order):**

1. **URGENT (P0):** Fix Obligations Phase 6-7 blocker (templates must ONLY access view model fields)
   - Audit template code (`templates/student_rent.html`, `templates/admin_rent_settings.html`)
   - Add `period_status` dict to StudentObligationView
   - Refactor templates to access `view.current_period.days_until_due` instead of bare `days_until_due`
   - Re-verify Phase 6-7 manually before re-running audit
2. **HIGH (P1):** Create missing view models for 5 domains (Identity, Class Config, Ledger, Payroll x2)
   - Estimated 20-30 hours
3. **HIGH (P1):** Refactor routes and templates to use view models (Phase 6-7)
   - Estimated 15-20 hours
4. **HIGH (P1):** Audit 11 direct db.session mutations in routes (Phase 4 enforcement)
   - Estimated 10-15 hours
5. **MEDIUM (P2):** Run Phase 10 audit for all 10 domains using SOP-DEV-002a checklist
   - Estimated 100-150 hours (10-15 per domain)
   - Focus on template field verification (what failed with Obligations)
6. **MEDIUM (P2):** Start Operations, Interpretation, Policies, Support domains (Phase 0-1)
   - Only after Ledger, Productivity & Payroll, Obligations, Store are audited
7. **FINAL:** Production readiness validation gate (all domains Phase 10 certified)

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

**Last Updated:** 2026-08-04  
**Maintained By:** Development Team  
**Canonical:** YES (This matrix is the single source of truth for domain progress)
