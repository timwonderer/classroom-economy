# CTH Domain Reconstruction Progress Matrix

**Status:** Active Canonical Tracker  
**Last Updated:** 2026-08-04 (CORRECTED — requires audit verification)  
**Authority:** SOP-DEV-002a, INV-CORE-000, DOM-CORE-002  

**⚠️ CRITICAL NOTE:** This matrix is being rebuilt with actual audit verification. "Complete" now means Phase 10 audit certification with all checkmarks. Domains without audit documentation are marked "likely complete but unaudited" pending verification.

---

## Overview

This matrix consolidates the progress of all CTH domains through the 10-phase SOP-DEV-002 reconstruction workflow. Each domain progresses independently but follows the same phase sequence:

| Phase | Name | Purpose |
|-------|------|---------|
| **0** | Boundary | Domain scope defined and authorized |
| **1** | Truth | Canonical facts immutable and audit-traceable |
| **2** | Persistence | Schema, migrations, indexes in place |
| **3** | Primitives | Core queries centralized in service layer |
| **4** | Mutation Boundary | All writes through FEAT layer |
| **5** | Read Models | View models immutable, generic, scoped |
| **6** | Surface Inventory | Routes and templates consume view models |
| **7** | Rewire | Legacy aggregation replaced; routes thin |
| **8** | Verify | Tests prove correctness and multi-tenancy |
| **9** | Legacy Deletion | Dead code removed |
| **10** | Audit | Production readiness certified |

---

## Domain Status Matrix

| Domain | Spec | Phase 0-4 | Phase 5-7 | Phase 8-9 | Phase 10 | Status | Audit Doc |
|--------|------|-----------|-----------|-----------|----------|--------|-----------|
| **Identity** | DOM-IDEN-001/002/003/006 | ✅ | ✅ | ✅ | ? | 🔄 Unaudited | None |
| **Class Configuration** | DOM-CLASS-001 | ✅ | ✅ | ✅ | ? | 🔄 Unaudited | None |
| **Ledger** | DOM-LED-001 | ✅ | ✅ | ✅ | ? | 🔄 Unaudited | None |
| **Attendance** | DOM-OPS-001 (subset) | ✅ | ✅ | ✅ | ? | 🔄 Unaudited | None |
| **Obligations** | DOM-OBL-001 | ✅ | ✅ | ✅ | ❌ | ❌ AUDIT INVALID | 2026-07-26 (FAILS Phase 6-7 verification) |
| **Productivity & Payroll** | DOM-PROD-001 | ✅ | ✅ | ✅ | ? | 🔄 Unaudited | None |
| **Store & Entitlements** | DOM-STORE-001 | ✅ | ✅ | ? | ? | 🔄 Needs audit | None |
| **Operations & Audit** | DOM-OPS-001/002 | 🔄 | — | — | — | 🔄 NOT STARTED | N/A |
| **Interpretation** | DOM-ITR-001 | 🔄 | — | — | — | 🔄 NOT STARTED | N/A |
| **Policies** | DOM-POL-001 | 🔄 | — | — | — | 🔄 NOT STARTED | N/A |
| **Economy & Governance** | DOM-ECON-000/003/004 | 🔄 | — | — | — | 🔄 NOT STARTED | N/A |
| **Support** | DOM-SUP-001 | 🔄 | — | — | — | 🔄 NOT STARTED | N/A |

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

---

## Detailed Domain Status

### COMPLETE (Ready to Merge)

#### Identity Domain (DOM-IDEN-001, 002, 003, 006)
**Canonical Tables:** `users`, `seats`, `classes`, `identity_profiles`, `user_invite_tokens`, `user_recovery_tokens`  
**Phase:** ✅ 0-10 Complete  
**Status:** LIVE (Wave 3, landed)  
**Key Achievement:** User/Seat canonical identity active; legacy Admin/Student tables dropped from runtime auth  
**Notes:** Remaining bridge tables `Admin`, `Student`, `StudentTeacher` exist for backward compat; will be deleted in final cleanup

---

#### Class Configuration Domain (DOM-CLASS-001)
**Canonical Tables:** `classes`, `class_features`, `feature_settings`, `hall_pass_settings`, `rent_settings`, `payroll_settings`, `payroll_rewards`, `payroll_fines`, `banking_settings`  
**Phase:** ✅ 0-10 Complete  
**Status:** LIVE (Wave 4, landed)  
**Key Achievement:** Settings migrated to canonical; `class_id` canonical scope enforcement  
**Notes:** `join_code` remains public alias; block/period is display-only metadata

---

#### Ledger Domain (DOM-LED-001)
**Canonical Tables:** `ledger_transaction`, `ledger_balance_snapshot`  
**Phase:** ✅ 0-10 Complete  
**Status:** LIVE (Wave 5, landed)  
**Key Achievement:** `transaction` → `ledger_transaction` migration complete; FEAT-LED-000 canonical monetary resolution active  
**Notes:** `BalanceCache` dropped; all balance reads flow through canonical ledger queries

---

#### Attendance Domain (DOM-OPS-001 subset)
**Canonical Tables:** `attendance_sessions`, `hall_pass_logs`, `seat_attendance_state`  
**Phase:** ✅ 0-10 Complete  
**Status:** LIVE (Wave 6, landed)  
**Key Achievement:** `tap_events` → canonical attendance migration; automatic attendance state tracking  
**Notes:** `TapEvent` legacy table dropped; hall pass entitlements scoped to `seat_id + class_id`

---

#### Productivity & Payroll Domain (DOM-PROD-001)
**Canonical Tables:** (Integrated into Class Configuration + Ledger)  
**Phase:** ✅ 0-10 Complete  
**Status:** LIVE  
**Key Achievement:** Payroll calculations in service layer; routes thin; view models canonical  
**Notes:** Early work; completed before structured SOP-DEV-002a audits were formalized

---

### IN PROGRESS (Failing Tests, Must Fix Before Merge)

#### Obligations Domain (DOM-OBL-001)
**Canonical Tables:** `assessment_events`, `obligation_lifecycle`, `obligation_satisfaction`, `obligation_reversal`, `entitlement_events`  
**Phase:** ✅ 0-4 | ✅ 5-7 | ✅ 8-9 | ✅ 10  
**Status:** COMPLETE (Wave 7, obligatin-domain-rewire merged)  
**Last Audit:** 2026-07-26 (PASSED — all 9 tests pass; "REJECTED" was administrative only due to 1-commit branch lag)  
**Key PRs/Commits:** Multiple phases across obligatin-domain-rewire branch, final merge at af2f76d9  
**Key Achievement:** Complete canonical obligations domain with assessment_events, obligation_lifecycle, and FEAT-wired mutations  
**Documentation:** 
- `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md` (spec)
- `docs/TRACKING/OBLIGATIONS_DOMAIN_PHASE10_CERTIFICATION_AUDIT_2026-07-26.md` (audit results showing all phases passed)

---

#### Store & Entitlements Domain (DOM-STORE-001)
**Canonical Tables:** `store_items`, `store_item_visibility`, `store_purchases`, `redemption_events`  
**Phase:** ✅ 0-4 | ✅ 5-7 | ✅ 8-9 | ✅ 10  
**Status:** COMPLETE (Wave 8, landed 2026-08-03)  
**Last Audit:** PASSED (PRs #1293-1295, #1299 completed all phases)  
**Key PRs:**
- #1293: Store foundation: canonical resolver and policy view boundary
- #1294: Store behavior: FEAT wiring for purchase, grant, and claims
- #1295: Store docs: surface map and archival closeout
- #1299: Organize store domain documentation after completion

**Key Achievement:** Full canonical store domain with FEAT-wired mutations, view models, and comprehensive docs  
**Documentation:** `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`

---

### NOT STARTED (Awaiting Sequence)

#### Operations & Audit Domain (DOM-OPS-001, DOM-OPS-002)
**Scope:** Audit lineage, observability, operational event tracking  
**Canonical Tables:** `operational_events`, `audit_log`, `incident_events`, `incident_summary`, `alert_events`, `invariant_run_events`, `job_events`, `health_check_events`  
**Phase:** 🔄 0-1 (Spec review in progress)  
**Wave Assignment:** Wave 9  
**Status:** Ready to start (all dependencies complete)  
**Dependency Chain:** Ledger (Wave 5) ✅ → Attendance (Wave 6) ✅ → Obligations (Wave 7) ✅ → Store (Wave 8) ✅ → **READY**

---

#### Interpretation Domain (DOM-ITR-001)
**Scope:** Analytics snapshots, interpretation annotations for economy state  
**Canonical Tables:** `interpretation_snapshots`, `interpretation_annotations`  
**Phase:** 🔄 0-1 (Spec review)  
**Wave Assignment:** Wave 9  
**Status:** Ready to start (all dependencies complete)  
**Dependency Chain:** Ledger (Wave 5) ✅ → Store (Wave 8) ✅ → **READY**

---

#### Policies Domain (DOM-POL-001)
**Scope:** Policy definitions, policy rules, policy activation  
**Canonical Tables:** `policies`, `policy_rules`, `policy_assignments`  
**Phase:** 🔄 0-1 (Spec review)  
**Wave Assignment:** Wave 9  
**Status:** Ready to start (all dependencies complete)  
**Dependency Chain:** Class Config (Wave 4) ✅ → Obligations (Wave 7) ✅ → **READY**  
**Notes:** Overlaps with DOM-ECON-003 policy execution surfaces

---

#### Economy & Governance Domain (DOM-ECON-000, DOM-ECON-003, DOM-ECON-004)
**Scope:** Economic policy formulas, CWI calculations, solvency models, policy disclosure  
**Canonical Tables:** Distributed across Class Config, Ledger, Store (no dedicated tables)  
**Phase:** 🔄 0 (Boundary definition in progress via spec review)  
**Wave Assignment:** Integrated across Waves 4-9  
**Status:** Requires separate planning; cross-cuts multiple domains  
**Key Challenge:** Policy mode, CWI ratios, collective-goal rules must integrate with class config, ledger settlement, and store pricing  
**Next Action:** Create DOM-ECON-specific implementation plan mapping to each wave's class-config/ledger/store/interpretation touchpoints

---

#### Support Domain (DOM-SUP-001)
**Scope:** Issue tracking, announcements, support ticket management  
**Canonical Tables:** `issues`, `issue_status_history`, `issue_resolution_actions`, `ticket_correlation_packs`, `announcements`, `issue_categories`  
**Phase:** 🔄 0-1 (Spec review)  
**Wave Assignment:** Wave 10  
**Status:** Awaiting all operational domains (Operations, Interpretation, Policies)  
**Dependency Chain:** Operations (Wave 9) → Support (Wave 10)

---

## Wave Progression Timeline

| Wave | Domains | Status | Est. Completion |
|------|---------|--------|-----------------|
| 1-2 | Foundation & Bootstrap | ✅ Complete | 2026-04 |
| 3 | Identity | ✅ Complete | 2026-05 |
| 4 | Class Config | ✅ Complete | 2026-05 |
| 5 | Ledger | ✅ Complete | 2026-06 |
| 6 | Attendance | ✅ Complete | 2026-06 |
| 7 | Obligations | ✅ Complete | 2026-07-26 (merged) |
| 8 | Store & Entitlements | ✅ Complete | 2026-08-03 |
| 9 | Operations, Interpretation, Policies | 🔄 Ready to start | TBD |
| 10 | Support | 🔄 Awaiting Wave 9 | TBD |
| 11 | Post-Launch Completion | 🔄 Awaiting all domains | TBD |
| 12 | Final Validation | 🔄 Awaiting all domains | TBD |

---

## Critical Path to Production

**Current Status:** 
- ❌ **0 domains AUDITED:** Obligations audit is INVALID (templates access undefined variables, Phase 6-7 failed)
- 🔄 **7 domains UNAUDITED AND UNTRUSTED:** All domains (Identity, Class Config, Ledger, Attendance, Productivity & Payroll, Obligations, Store & Entitlements)
  - No valid Phase 10 audit documents
  - No Phase 6-7 template verification
- 🔄 **5 domains NOT STARTED:** Operations, Interpretation, Policies, Support, Economy & Governance

**CRITICAL BLOCKER:** The only existing Phase 10 audit (Obligations) has false checkmarks. Templates were NOT actually verified. **No domain is known to be end-to-end complete.**

**Minimum Path Forward:**
1. **URGENT:** Fix Obligations Phase 6-7 (templates must ONLY access view model fields)
   - Audit template code (`templates/student_rent.html`, `templates/admin_rent_settings.html`)
   - Move `period_status`, `current_block`, `days_until_due` into view model
   - Refactor templates to access `view.current_period.days_until_due` instead of bare `days_until_due`
   - Re-verify Phase 6-7 manually before re-running audit
2. **DEFINE:** What does "actually complete" mean? (Phase 10 audit template verification checklist)
3. **SELECT PILOT:** Pick one domain for proper end-to-end Phase 10 audit verification
4. **AUDIT PILOT:** Run full SOP-DEV-002a audit with manual verification of Phase 6-7 templates
5. **SYSTEMIZE:** Create re-audit process that catches template issues
6. **THEN:** Audit remaining domains before starting Wave 9
6. **After Wave 9:** Begin Wave 10 (Support)
7. **After all domains:** Wave 11 (post-launch hardening)
8. **Final:** Wave 12 validation gate (exact 44 tables, all tests passing)

---

## How to Use This Matrix

### For Implementation Work
1. **Find your domain** in the "Detailed Domain Status" section
2. **Identify the current phase** (e.g., Obligations is stuck in Phase 8)
3. **Read the blocking issues** and next actions
4. **Pick ONE action** and create a focused PR
5. **After fixing, update this matrix** with the new status

### For Cross-Domain Dependency Checks
1. **Find your domain** in the wave timeline
2. **Look for dependencies** (e.g., Support requires Operations, Interpretation, Policies to complete)
3. **Verify preceding waves are complete** before starting your domain

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
|------|--------|--------|
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
```
**Blocking Issues:**
1. [Issue] — [Impact]
   - Root cause or technical detail
   - Next action to resolve
```

**Example updates:**
```
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
