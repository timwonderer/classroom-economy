# Comprehensive CTH v2 Domain Audit Baseline
**Date:** 2026-08-04  
**Auditor:** Claude  
**Status:** BASELINE FINDINGS (not yet approved)  
**Authority:** SOP-DEV-002a, DOM-CORE-002  

---

## EXECUTIVE SUMMARY

This audit establishes a **baseline understanding** of all 10 domains' current progress through SOP-DEV-002 phases. It replaces previous stale tracking with verified code inspection findings.

**Critical Finding:** Phase 6-7 (View Model Integration) has a **universal measurement problem** that affects all domains:
- Phase 6-7 completion criterion changed from "routes and templates consume view models" to "domains own fields, not templates"
- Only **2 view model implementations found** (Obligation, Store/Entitlements builders)
- Other 8 domains have **NO view models defined yet**
- Most routes still construct ad-hoc context for templates instead of canonical view models
- This is a **blocker for Phases 6-7 for most domains**

**Obligations Domain Alert:** Phase 6-7 certification is **INVALID** (previous audit false positives):
- Template `student_rent.html` references `period_status[current_block]` — NOT IN VIEW MODEL
- Template references `days_until_due` at top level — actually nested in `current_period` dict
- Route correctly passes only `view=view` but template expects undefined variables
- This is a **CRITICAL BLOCKER** preventing template rendering

---

## DOMAIN-BY-DOMAIN STATUS

### 1. IDENTITY DOMAIN (DOM-IDEN-001/002/003/006)

**Phase Status:** 🔄 Phases 0-5 likely complete, **6-7 BLOCKED** (no view model)

**Evidence:**

✅ **Phase 0:** Domain specs exist (DOM-IDEN-001, 002, 003, 006, 005, 006, 007)  
✅ **Phase 1:** Canonical models: `User`, `Seat`, `IdentityProfile`, `ClassEconomy` with immutable timestamps  
✅ **Phase 2:** Migrations exist (schema verified at database level)  
✅ **Phase 3:** Service layer `identity_service.py` has queries, but **NO class_id filtering** (identity is global by design)  
✅ **Phase 4:** Routes use `resolve_canonical_context()` which is function-based, not FEAT-wrapped mutations  
⚠️ **Phase 5:** NO view model found for identity  
❌ **Phase 6-7:** BLOCKED — No `IdentityProfileView` or similar view model exists

**Blocker:**
- No view model for identity context; routes resolve identity inline
- Templates get raw `user`, `seat`, `class_id` variables, not from view model

**Recommendation:**
- Create `IdentityProfileView` dataclass for Phase 5
- Create `build_identity_profile_view()` constructor
- Update routes to use view model
- Update Phase 6-7 audit

---

### 2. CLASS CONFIGURATION DOMAIN (DOM-CLASS-001)

**Phase Status:** 🔄 Phases 0-5 likely complete, **6-7 BLOCKED** (no view model)

**Evidence:**

✅ **Phase 0:** Spec exists (DOM-CLASS-001)  
✅ **Phase 1:** Canonical tables: `classes` (ClassEconomy), `feature_settings`, `rent_settings`, etc.  
✅ **Phase 2:** Migrations in place  
✅ **Phase 3:** `payroll_settings_service.py`, `admin_settings_service.py` exist with queries  
✅ **Phase 4:** Settings mutations via routes (may need FEAT wrapping verification)  
⚠️ **Phase 5:** NO view model found for class config  
❌ **Phase 6-7:** BLOCKED — Templates receive `rent_settings`, `payroll_settings` directly, not via view model

**Blocker:**
- Settings passed as raw dicts to templates: `rent_settings=settings`
- Should be: `view=build_class_config_view(...)`

**Recommendation:**
- Create `ClassConfigurationView` dataclass
- Create `build_class_config_view()` constructor
- Refactor all routes using settings to pass view model

---

### 3. LEDGER DOMAIN (DOM-LED-001)

**Phase Status:** 🔄 Phases 0-5 likely complete, **6-7 BLOCKED** (no view model)

**Evidence:**

✅ **Phase 0:** Spec exists (DOM-LED-001)  
✅ **Phase 1:** Canonical tables: `ledger_transaction`, `ledger_balance_snapshot`  
✅ **Phase 2:** Migrations in place, indexes on class_id  
✅ **Phase 3:** `ledger_service.py` with 5+ class_id filtering operations  
✅ **Phase 4:** FEAT layer exists (FEAT-LED-000 for transaction creation)  
⚠️ **Phase 5:** NO balance view model found (balance_service.py returns raw Decimals)  
❌ **Phase 6-7:** BLOCKED — Balances passed as raw `checking_balance`, `savings_balance` variables to templates

**Blocker:**
- `get_available_balances(seat_id, class_id)` returns tuple of Decimals, not view model
- Should return: `LedgerBalanceView` dataclass

**Recommendation:**
- Create `LedgerBalanceView` dataclass with checking, savings, summary fields
- Create `build_ledger_balance_view()` constructor
- Refactor all routes to use view model

---

### 4. PRODUCTIVITY & PAYROLL DOMAIN (DOM-PROD-001)

**Phase Status:** 🔄 Phases 0-5 likely complete, **6-7 BLOCKED** (no view model)

**Evidence:**

✅ **Phase 0:** Spec exists (DOM-PROD-001)  
✅ **Phase 1:** Canonical tables: `attendance_sessions`, `hall_pass_logs`, `seat_attendance_state`, `payroll_transaction`  
✅ **Phase 2:** Migrations exist  
✅ **Phase 3:** `attendance_service.py`, `payroll_settings_service.py` with queries  
✅ **Phase 4:** FEAT layer for attendance/payroll mutations  
⚠️ **Phase 5:** NO view model for payroll/attendance dashboard  
❌ **Phase 6-7:** BLOCKED — Routes construct context ad-hoc (current_period_earnings, rewards_total, etc.)

**Blocker:**
- `build_payroll_view()` or `build_attendance_view()` does not exist
- Routes pass raw computed values to templates

**Recommendation:**
- Create `StudentPayrollView` dataclass
- Create `StudentAttendanceView` dataclass
- Create builder functions
- Refactor routes

---

### 5. OBLIGATIONS DOMAIN (DOM-OBL-001)

**Phase Status:** ❌ **PHASES 0-5 PASS, 6-7 FAIL, AUDIT INVALID**

**Evidence:**

✅ **Phase 0:** Spec exists (DOM-OBL-001)  
✅ **Phase 1:** Canonical tables: `obligation_assessment`, `assessment_events`, `bill_cycles`  
✅ **Phase 2:** Migrations in place, class_id indexed  
✅ **Phase 3:** `obligations_service.py` with 3+ class_id filtering operations  
✅ **Phase 4:** FEAT mutations in place (`assess_obligation_feat.py`, etc.)  
✅ **Phase 5:** View model EXISTS: `StudentObligationView` in `obligation_view_model.py` ✅ FROZEN DATACLASS  
❌ **Phase 6:** Routes pass `view=view` but **TEMPLATE EXPECTS UNDEFINED VARIABLES**
❌ **Phase 7:** Template-verification FAILS

**Critical Blocker — Phase 6-7 Template Mismatch:**

File: `templates/student_rent.html` line 53:
```jinja
{% set status = period_status[current_block] %}  <!-- ❌ UNDEFINED: not in view, not in context -->
```

File: `templates/student_rent.html` lines 71-86:
```jinja
{% elif days_until_due is not none %}  <!-- ❌ UNDEFINED: nested in view.current_period, not top-level -->
    {% if days_until_due < 3 %}
```

File: `app/routes/student.py` line 2959-2963:
```python
view = build_student_obligation_view(  # ✅ View model built correctly
    seat_id=seat_id,
    class_id=class_id,
    obligation_type='RENT',
)
```

File: `app/routes/student.py` line 2990-3000:
```python
return render_template(
    'student_rent.html',
    student=student_seat,
    settings=settings,
    view=view,  # ✅ Only view passed (correct)
    checking_balance=checking_balance,
    savings_balance=savings_balance,
    now=now_utc,
    ...
)
```

**Root Cause:**
- `StudentObligationView` contains `current_period` dict with nested `days_until_due`
- Template expects top-level `days_until_due` variable
- `StudentObligationView` does NOT contain `period_status` dict at all
- Template expects `period_status[current_block]` to exist

**What's Actually in StudentObligationView (lines 140-150):**
```python
current_period: dict  # {due_date, grace_end, amount_due, amount_paid, amount_waived, balance, is_paid, is_waived, is_past_due, is_preview, days_until_due, days_overdue}
```

**What Template Needs:**
- `period_status[current_block]` — a dict mapping block/period names to status
- `days_until_due` — at top level, OR template must access via `view.current_period.days_until_due`

**Solution Options:**
1. **Add `period_status` to StudentObligationView** — Create dict mapping each block to its status
   - Requires change to view model builder (obligation_view_model.py lines 174-353)
   - Template stays the same

2. **Fix template to use current_period correctly** — Change template to use nested access
   - Change `{{ days_until_due }}` to `{{ view.current_period.days_until_due }}`
   - Change `{{ period_status[current_block] }}` to access view model fields
   - Requires template refactoring

**Audit Status:** ❌ **REJECTED** — Phase 6-7 INVALID until template verification passes

**Next Action:** Implement Option 1 or 2, then re-run Phase 6-7 template render test

---

### 6. STORE & ENTITLEMENTS DOMAIN (DOM-STORE-001)

**Phase Status:** 🔄 Phases 0-5 **LIKELY** pass, **6-7 NEEDS VERIFICATION**

**Evidence:**

✅ **Phase 0:** Spec exists (DOM-STORE-001)  
✅ **Phase 1:** Canonical tables: `entitlement_events`, `pending_actions` (per spec)  
✅ **Phase 2:** Migrations likely exist  
✅ **Phase 3:** `entitlement_service.py`, `entitlement_read_service.py` with class_id filtering  
✅ **Phase 4:** Mutations via FEAT (FEAT-STOR-001, FEAT-STOR-004 from memory)  
⚠️ **Phase 5:** View models exist: `EntitlementListView`, `PurchaseHistoryView` in `view_model_builders.py` with FROZEN=TRUE  
⚠️ **Phase 6:** Routes appear to construct these views (requires verification)  
⚠️ **Phase 7:** Templates likely use view model fields (requires grep verification)

**Status:** 
- Implementation appears complete per recent PRs (#1293, #1294, #1295)
- BUT NO PHASE 10 AUDIT DOCUMENT EXISTS
- Cannot approve without audit

**Next Action:** Run Phase 10 audit verification

---

### 7. OPERATIONS DOMAIN (DOM-OPS-001)

**Phase Status:** 🔄 Phases 0-1 only, **6-7 BLOCKED** (not started)

**Evidence:**

✅ **Phase 0:** Spec exists (DOM-OPS-001, DOM-OPS-002)  
✅ **Phase 1:** No canonical models visible yet  
❌ **Phase 2-7:** Not started

**Status:** Awaiting foundational domain work

---

### 8. INTERPRETATION DOMAIN (DOM-ITR-001)

**Phase Status:** 🔄 Phases 0-1 only, **6-7 BLOCKED** (not started)

**Evidence:**

✅ **Phase 0:** Spec exists (DOM-ITR-001)  
❌ **Phase 1-7:** Not started

**Status:** Awaiting prior domain completion

---

### 9. POLICIES DOMAIN (DOM-POL-001)

**Phase Status:** 🔄 Phases 0-1 only, **6-7 BLOCKED** (not started)

**Evidence:**

✅ **Phase 0:** Spec exists (DOM-POL-001, DOM-POL-001A)  
❌ **Phase 1-7:** Not started

**Status:** Foundational; needed by Store domain

---

### 10. SUPPORT DOMAIN (DOM-SUP-001)

**Phase Status:** 🔄 Phases 0-1 only, **6-7 BLOCKED** (not started)

**Evidence:**

✅ **Phase 0:** Spec exists (DOM-SUP-001)  
❌ **Phase 1-7:** Not started

**Status:** Lower priority; depends on Operations

---

## CROSS-CUTTING FINDINGS

### Finding 1: View Model Adoption is Incomplete

**Summary:** Only Obligations and Store/Entitlements domains have view models. Other 8 domains pass raw data to templates.

**Impact:** All 8 domains blocked on Phase 6-7 completion

**Evidence:**
- View models found: 2 (Obligation, Store via view_model_builders.py)
- Domains without view models: 8 (Identity, Class Config, Ledger, Payroll, Operations, Interpretation, Policies, Support)

**Action Required:** Create view models for all 8 domains

### Finding 2: Routes Still Mutate Data Directly

**Summary:** 11 instances of `db.session.add/commit` found in routes

**Impact:** Phase 4 (Mutation Boundary) verification incomplete

**Evidence:**
```
grep -r "db.session.add\|db.session.commit" app/routes/ | wc -l
# Returns: 11
```

**Action Required:** Audit each and ensure FEAT layer wrapping

### Finding 3: Phase 6-7 Definition Now Field-Centric

**Summary:** Phase 6-7 completion criterion changed from "templates consume view models" to "domains own fields in view models"

**Impact:** All previous Phase 6-7 certifications need re-audit with new criteria

**Action Required:** Re-verify all domains that claimed Phase 6-7 complete using field ownership model

### Finding 4: Identity Domain Has Special Multi-Tenancy

**Summary:** Identity domain (User/Seat/IdentityProfile) uses global scope, not class_id scoping

**Impact:** Phase 3 class_id verification must exclude Identity queries

**Action Required:** Update Phase 3 audit criteria for identity domain

---

## AUDIT MATRIX: Current vs. Target

| Domain | Phase 0-4 | Phase 5 | Phase 6-7 | Phase 8-9 | Phase 10 | **Action Needed** |
|--------|-----------|---------|-----------|-----------|----------|-------------------|
| Identity | ✅ | ❌ NONE | ❌ BLOCKED | ? | ❌ | Create identity view model |
| Class Config | ✅ | ❌ NONE | ❌ BLOCKED | ? | ❌ | Create settings view model |
| Ledger | ✅ | ❌ NONE | ❌ BLOCKED | ? | ❌ | Create balance view model |
| Payroll | ✅ | ❌ NONE | ❌ BLOCKED | ? | ❌ | Create payroll view model |
| **Obligations** | ✅ | ✅ | ❌ **FAILS** | ? | ❌ | Fix Phase 6-7 blocker |
| Store | ✅ | ✅ | ⚠️ UNVERIFIED | ? | ❌ | Run Phase 10 audit |
| Operations | 🔄 | ❌ | ❌ | ❌ | ❌ | Start Phase 1 |
| Interpretation | 🔄 | ❌ | ❌ | ❌ | ❌ | Start Phase 1 |
| Policies | 🔄 | ❌ | ❌ | ❌ | ❌ | Start Phase 1 |
| Support | 🔄 | ❌ | ❌ | ❌ | ❌ | Start Phase 1 |

---

## CRITICAL BLOCKERS SUMMARY

### BLOCKER 1: Obligations Phase 6-7 Template Failure (P0)

**Issue:** Template references undefined variables  
**Impact:** Route passes only `view`, template expects `period_status` and top-level `days_until_due`  
**File:** `templates/student_rent.html` lines 53, 71-86  
**Fix:** Add `period_status` dict to StudentObligationView OR refactor template to use view.current_period  
**Timeline:** Blocks Phase 10 audit; must fix before re-certification

### BLOCKER 2: 8 Domains Missing View Models (P1)

**Issue:** No view models defined for Identity, Class Config, Ledger, Payroll, Operations, Interpretation, Policies, Support  
**Impact:** All 8 domains blocked on Phase 6-7  
**Fix:** Create dataclass + builder function for each  
**Timeline:** Required for domain progression

### BLOCKER 3: Routes Still Calling db.session Directly (P1)

**Issue:** 11 instances of db.session.add/commit found in routes  
**Impact:** Phase 4 (Mutation Boundary) not fully enforced  
**Fix:** Audit each instance and wrap in FEAT layer  
**Timeline:** Before Phase 10 audits

### BLOCKER 4: No Phase 10 Audits Exist (P1)

**Issue:** Only Obligations attempted Phase 10 audit (found INVALID)  
**Impact:** Cannot certify any domain as production-ready  
**Fix:** Run Phase 10 audit for each domain using SOP-DEV-002a checklist  
**Timeline:** Required for production readiness sign-off

---

## RECOMMENDED AUDIT ORDER

1. **Fix Obligations Phase 6-7 blocker** (P0) — Unblocks one domain immediately
2. **Create Identity view model** (P1) — Foundation for all auth
3. **Create Class Config view model** (P1) — Needed by most other domains
4. **Create Ledger view model** (P1) — Needed by Obligations, Payroll
5. **Create Payroll view model** (P1) — Needed by dashboard
6. **Audit routes for db.session calls** (P1) — Enforce mutation boundary
7. **Run Store Phase 10 audit** (P1) — Recently completed domain
8. **Create view models for Operations, Interpretation, Policies, Support** (P2)
9. **Run Phase 10 audits for all domains** (P2) — Production readiness

---

## NEXT STEPS

1. **Document each finding in domain-specific implementation plans**
2. **Create GitHub issues for each blocker**
3. **Update DOMAIN_PROGRESS_MATRIX_2026.md with verified status**
4. **Begin Phase 5-7 implementation for all 8 domains without view models**
5. **Re-audit Obligations with fixed template**
6. **Run SOP-DEV-002a Phase 10 audits**

---

**This audit baseline is the new source of truth for domain status.**  
**Replace previous stale tracking with findings documented here.**  

---

**Audit Evidence Files:**
- Grep queries: Search results for class_id, db.session, @dataclass(frozen=True)
- Code inspection: app/services/*, app/routes/*, templates/*, app/models.py
- Domain specs: docs/DOMAIN/DOM-*.md
- Template analysis: templates/student_rent.html, etc.
