# Obligations Domain Phase 10 Certification Audit
## Independent Verification Post-Phase-9 Legacy Deletion

| Reference | Version | Date | Auditor | Authority |
|-----------|---------|------|---------|-----------|
| AUDIT-OBL-002 | 1.0 | 2026-07-24 | Certification Review | Phase 10 |

---

## Executive Summary

**Status: AUDIT FAIL — Blocking Finding**

The Obligations domain implementation has been substantially corrected in Phase 9 (REVERSED events removed, ObligationLifecycle writes eliminated from services). However, a **schema migration gap** persists: the database still contains `reason` and `reversed_by_seat_id` columns that violate DOM-OBL-001 §VI (Canonical Schema Authority).

**Action Required:** Create a migration to drop these forbidden columns from `assessment_events` before certification can pass.

---

## I. Audit Scope

This audit independently verifies the Obligations domain against:
- **DOM-OBL-001**: Canonical authority document
- **FEAT-OBLI-001, OBL-002, OBL-003**: Primitive operation contracts
- **SOP-DEV-002 §VIII**: Domain completion gate criteria
- **Test evidence**: Phase 8 verification tests (14/14 passing)

---

## II. Audit Categories

### A. Canonical Domain Authority

**Claim:** Obligations is the sole business authority for obligation lifecycle.

**Finding: ✅ PASS**

Evidence:
- ✅ No direct `db.session.add/commit` on ObligationAssessment in routes
- ✅ All writes routed through `obligations_service` functions (`record_rent_payment`, `record_rent_waiver`, etc.)
- ✅ `_set_assessment_lifecycle()` removed from services (no lifecycle mutations)
- ✅ `record_insurance_reversal()` function removed (no REVERSED events)
- ✅ DOM-OBL-001 §IV-V clearly states domain authority and boundaries

---

### B. Persistence Correctness

**Claim:** Schema matches DOM-OBL-001 §VI-VII canonical persistence.

**Finding: ❌ FAIL — Schema Migration Gap**

Evidence:

**Required Canonical Tables per DOM-OBL-001 §VI:**
- ✅ `assessment_events` exists
- ✅ `bill_cycles` exists

**Required Fields in `assessment_events` per DOM-OBL-001 §VII:**
- ✅ `id`, `seat_id`, `class_id` (identity anchors)
- ✅ `internal_ref`, `correlation_id` (lineage)
- ✅ `event_type` (discriminator: ASSESSMENT | PAYMENT | WAIVED)
- ✅ `obligation_type`, `policy_version_id`
- ✅ `ledger_transaction_id` (Ledger backing)
- ✅ `due_at`, `viewable_at`, `assessed_at`, `created_at` (temporal)

**Forbidden Fields per DOM-OBL-001 §VI ("does not own"):**
- ✅ `paid_amount` — NOT present
- ✅ `satisfied` — NOT present
- ✅ `lifecycle_status` — NOT present
- ❌ `reason` — **STILL PRESENT** (forbidden)
- ❌ `reversed_by_seat_id` — **STILL PRESENT** (forbidden)
- ❌ `ix_assessment_events_reversed_by_seat_id` index — **STILL PRESENT**

**Blocking Issue:**
The ORM model (`app/models.py` ObligationAssessment) correctly removed `reason` and `reversed_by_seat_id` fields, but the database schema still contains these columns. This is a **migration gap**: a prior migration added these columns for reversal support, but Phase 9 legacy deletion did not include a migration to drop them.

**Bill Cycles Identity-Blind Requirement per DOM-OBL-001 §VII:**
- ✅ No `seat_id` on bill_cycles (correct)
- ✅ No `class_id` on bill_cycles (correct)
- ✅ No `amount` on bill_cycles (correct)

**Event-Type Discriminator per DOM-OBL-001 §VII:**
- ✅ Only authorized types in code: ASSESSMENT, PAYMENT, WAIVED
- ✅ No REVERSED events in test data (test database is clean)
- Note: Production database may contain legacy REVERSED rows; audit does not have access to production

---

### C. Lawful FEAT Mutation Boundaries

**Claim:** All obligation mutations occur through designated FEATs only.

**Finding: ✅ PASS**

Evidence:
- ✅ FEAT-OBLI-001 documented and implemented (assessment creation)
- ✅ FEAT-OBL-002 documented and implemented (bill cycle advancement)
- ✅ FEAT-OBL-003 documented and implemented (satisfaction: payment + waiver)
- ✅ No direct mutation paths exist outside these FEATs
- ✅ Tests verify FEAT context enforcement (14 tests passing)

Specific removals completed in Phase 9:
- ✅ Removed `_set_assessment_lifecycle()` (was bypassing canonical state)
- ✅ Removed `record_insurance_reversal()` (illegal operation)
- ✅ Removed ObligationLifecycle writes from all `record_*` functions
- ✅ Removed `reversed_by_seat_id` parameter passing in routes

---

### D. Read Model Correctness

**Claim:** All read models derive from canonical sources only.

**Finding: ✅ PASS**

Evidence:
- ✅ Six canonical query helpers defined and tested:
  - `get_rent_assessments_for_cycle()` (ASSESSMENT events)
  - `get_payment_events_for_assessment()` (PAYMENT events)
  - `get_total_paid_for_assessment()` (Ledger-backed amounts, NOT obligation fields)
  - `get_waived_event_for_assessment()` (WAIVED events)
  - `get_rent_payment_history()` (paired ASSESSMENT + state events)
  - `get_rent_waivers_for_seat()` (WAIVED events)
- ✅ No route-level state reconstruction except for derived display properties
- ✅ GET routes remain pure (no mutations)
- ✅ Amounts always read from Ledger via `ledger_transaction_id`

Tests passing:
- ✅ `test_a1_amounts_come_from_ledger_not_obligations` (Phase 8)
- ✅ `test_a1_query_helpers_work_with_event_discriminator` (Phase 8)
- ✅ All A1-A2 query paths verified in tests

---

### E. Application Surface Rewiring

**Claim:** All 8 obligation-facing surfaces (A1-A8) are wired to canonical paths.

**Finding: ✅ PASS**

Evidence:
- ✅ A1 (Student Rent) — REWIRED: calls canonical query helpers
- ✅ A2 (Admin Rent Settings) — REWIRED: uses `get_rent_payment_history()`
- ✅ A3-A8 (Insurance + Dashboards) — VERIFIED: read-only, no schema violations
- ✅ All 8 surfaces tested in Phase 8 (8/8 passing)
- ✅ No dead routes remain that access removed schema fields

Routes audited:
- ✅ `student.rent` (GET /student/rent) — uses canonical helpers
- ✅ `admin.rent_settings` (GET|POST /admin/rent-settings) — uses canonical helpers
- ✅ `admin.dashboard`, `admin.economy_health` — use canonical read paths

---

### F. Template Contract Compliance

**Claim:** Templates receive only canonical view models; no deprecated field access.

**Finding: ✅ PASS**

Evidence:
- ✅ `student_rent.html` — no access to `.satisfactions`, `.reversal`, `.reason`
- ✅ `admin_rent_settings.html` — no access to removed fields
- ✅ `admin_dashboard.html`, `admin_economy_health.html` — canonical reads only
- ✅ All templates pass render tests (Phase 8)

Specific removals:
- ✅ Removed `waiver.reversal.reason` access from `student.py` (line 2720)
- ✅ Removed `waiver.reversal.reason` access from `admin.py` (line 6097)
- ✅ Removed `reversed_events` processing from rent payment history (student.py)

---

### G. Accessibility Requirements

**Claim:** Changed templates meet INV-ARC-020 accessibility requirements.

**Finding: ✅ PASS**

Evidence:
- ✅ A1 and A2 templates maintain existing accessibility structures
- ✅ No semantic HTML changes; only data flow rewiring
- ✅ Aria labels and table headers preserved
- ✅ No new interactive elements requiring new accessibility features

---

### H. Journey Workflows

**Claim:** Complete obligation workflows still function end-to-end.

**Finding: ✅ PASS**

Evidence:
- ✅ Rent assessment → payment journey works (test_a1_amounts_come_from_ledger_not_obligations passes)
- ✅ Rent waiver journey works (test_a2_settings_integrate_with_obligations passes)
- ✅ Insurance premium assessment works (A3-A7 verified as read-only, entitlement-driven)
- ✅ No workflows require REVERSED or reversal metadata

---

### I. Legacy Implementation Leakage

**Claim:** All legacy/forbidden code has been removed or disabled.

**Finding: ✅ PASS (Code), ❌ SCHEMA MIGRATION GAP**

**Code Evidence:**
- ✅ `record_insurance_reversal()` removed entirely
- ✅ `_set_assessment_lifecycle()` removed entirely
- ✅ No ObligationLifecycle writes in service layer
- ✅ No references to `REVERSED` events in code
- ✅ No `waiver.reversal` access in routes

**ORM Model:**
- ✅ ObligationAssessment model has no `reason` or `reversed_by_seat_id` fields
- ✅ No `reversed_by` relationship defined
- ✅ REVERSED removed from event_type docstring

**Schema Gap:**
- ❌ Database columns still exist: `reason`, `reversed_by_seat_id`
- ❌ Index still exists: `ix_assessment_events_reversed_by_seat_id`
- ❌ Foreign key still exists: `assessment_events.reversed_by_seat_id` → `seats.id`

This is a **migration gap**, not a code issue. The code is correct; the database needs a cleanup migration.

---

### J. Documentation Synchronization

**Claim:** Implementation correctly reflects documented behavior.

**Finding: ✅ PASS**

Evidence:
- ✅ DOM-OBL-001 §IX (Canonical Business Operations) matches implemented `record_*` functions
- ✅ DOM-OBL-001 §VIII (Derived State) correctly computed in queries
- ✅ FEAT-OBLI-001/002/003 document actual implementations
- ✅ Immutability rule (§X.5) enforced: no REVERSED, no deletions
- ✅ Phase 8 audit instruction correctly specified two-table model and three event types

---

### K. Cross-Domain Coordination

**Claim:** Obligations correctly interfaces with Class Configuration, Ledger, and Entitlements.

**Finding: ✅ PASS**

Evidence:
- ✅ **Class Configuration**: Obligations reads `RentSettings` for contract terms (does not mutate)
- ✅ **Ledger**: Obligations stores `ledger_transaction_id` reference; reads amounts from Transaction (does not store amount)
- ✅ **Entitlements/Store**: Insurance flows through Entitlements ownership; Obligations records premium/claim events without owning entitlements

Coordination correct:
- ✅ `get_total_paid_for_assessment()` reads from Ledger via FK
- ✅ rent_settings mutations routed to Class Configuration domain (admin.rent_settings, not obligations_service)
- ✅ Insurance policy mutations routed to Store/Entitlements domain

---

### L. Targeted Regression Evidence

**Claim:** No regressions in Phase 9 changes.

**Finding: ✅ PASS**

Evidence:
- ✅ All 14 Phase 8 tests still passing after Phase 9 deletions
  - 8 A1-A8 tests ✅
  - 6 Phase 7 verification tests ✅
- ✅ No new test failures introduced
- ✅ Key test: `test_all_obligation_assessment_events_schema_compliant` verifies event_type in [ASSESSMENT, PAYMENT, WAIVED]
- ✅ Key test: `test_a1_amounts_come_from_ledger_not_obligations` verifies Ledger-backed amounts

---

## III. Blocking Findings

| Finding | Severity | Category | Resolution |
|---------|----------|----------|------------|
| Schema migration gap: `reason` and `reversed_by_seat_id` columns still exist in assessment_events | **BLOCKING** | Persistence | Create migration to drop forbidden columns |
| `ix_assessment_events_reversed_by_seat_id` index still present | **BLOCKING** | Persistence | Dropped automatically when column is dropped |
| FK constraint `assessment_events.reversed_by_seat_id` → `seats.id` still exists | **BLOCKING** | Persistence | Dropped automatically when column is dropped |

---

## IV. Recommended Action

**Before certification can pass:**

1. **Create migration:** Drop `reason` and `reversed_by_seat_id` columns from `assessment_events`
   ```bash
   flask db migrate -m "Drop forbidden reversal columns from assessment_events per DOM-OBL-001"
   ```
2. **Manually edit migration** to include idempotency helpers (check existence before drop)
3. **Test:** `flask db upgrade && flask db downgrade && flask db upgrade`
4. **Run regression tests:** `pytest tests/test_phase8_a1_a2_surfaces.py tests/test_obligations_phase7_verification.py`
5. **Re-run audit** to verify schema compliance

---

## V. Completion Criteria (SOP-DEV-002 §VIII)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Canonical domain authority fully documented | ✅ PASS | DOM-OBL-001 §IV-XI |
| Persistence contract complete | ❌ FAIL | Schema migration gap (columns exist but not in model) |
| Primitive operations defined | ✅ PASS | DOM-OBL-001 §IX (three operations) |
| Every lawful mutation enters through FEAT | ✅ PASS | FEAT-OBLI-001/002/003, no bypasses |
| Read models documented | ✅ PASS | obligations_service.py (six helpers) |
| Every inventoried surface marked REWIRED or VERIFIED | ✅ PASS | A1-A8 complete (2 REWIRED, 6 VERIFIED) |
| Targeted validation passed | ✅ PASS | 14/14 Phase 8 tests passing |
| Documentation reflects implementation | ✅ PASS | DOM-OBL-001 matches code |
| Certification audit completed | ⏳ CONDITIONAL | Awaiting schema migration |
| Remaining issues explicitly tracked | ✅ PASS | This report documents blocking finding |

---

## VI. Audit Sign-Off

**Audit Date:** 2026-07-24  
**Auditor:** Independent Verification (Phase 10)  
**Result:** ❌ **CONDITIONAL PASS** — Blocking Finding  
**Blocking Findings:** 1 (Schema migration gap)  
**Non-Blocking Findings:** 0  

**Next Steps:**
1. Apply schema migration to drop forbidden columns
2. Re-run tests to verify no regression
3. Re-run Phase 10 audit to confirm all findings resolved
4. Proceed to Phase 11 (if in workflow) or mark domain CERTIFIED

**Certification Status:** **PENDING SCHEMA MIGRATION**

---

## VII. Appendix: Code Quality Summary

### Phase 9 Deletions Verified
- ✅ Removed: `record_insurance_reversal()` function
- ✅ Removed: `_set_assessment_lifecycle()` function
- ✅ Removed: ObligationLifecycle imports and writes
- ✅ Removed: REVERSED from event_type filters and docstrings
- ✅ Removed: `reason` parameter from `record_rent_waiver()`
- ✅ Removed: `waiver.reversal.reason` template access (2 locations)
- ✅ Removed: `reversed_events` processing from payment history (student.py)

### ORM Model Compliance
- ✅ ObligationAssessment: Correct schema definition
- ✅ BillCycle: Identity-blind (no seat_id, class_id, amount)
- ✅ ObligationLifecycle: Exists but not written to by domain services ⚠️

### Routes Compliance
- ✅ Student rent route: Uses canonical helpers
- ✅ Admin rent settings: Uses canonical helpers
- ✅ All admin/student routes: No direct obligation mutations

### Tests Compliance
- ✅ 14/14 Phase 8 verification tests passing
- ✅ Event type assertions updated: only [ASSESSMENT, PAYMENT, WAIVED]
- ✅ No test failures introduced in Phase 9

