# Obligations Domain Rewire Status Summary
**As of 2026-07-25** — Branch: `obligatin-domain-rewire`

---

## Executive Summary

The branch has **5 remaining items** to close:

1. ✅ **Student rent surface rewiring** — PARTIALLY DONE (using obligations_service but may lack full DOM-OBL-001 compliance)
2. ✅ **Admin rent settings rewiring** — PARTIALLY DONE (using obligations_service but may lack full FEAT boundaries)
3. ⚠️ **FEAT boundary validation** — B1/B2/B3 checkboxes unchecked; specs need explicit verification against implementation
4. ⚠️ **Insurance read verification** — Renewal status dependency on obligations needs explicit scope documentation
5. ⚠️ **Canonical inputs checkboxes** — All 12 doc inputs unchecked in checklist

---

## Authority Conflict: Checklist vs. MAP

| Document | Status | Date | Authority Level |
|----------|--------|------|-----------------|
| Checklist Part A | Phase 7 REWIRED ✅ | 2026-07-XX (historical) | Audit snapshot |
| MAP-UI-001 lines 141–142 | NEEDS_REWIRE | 2026-07-22 (current) | Informative |
| Implementation | Partial (using obligations_service) | 2026-07-25 | Code truth |

**Interpretation:** The Phase 7 audit verified that routes call canonical obligations_service functions. The MAP's "NEEDS_REWIRE" tag reflects that full FEAT-level boundary compliance and view-model normalization haven't been verified yet.

---

## Detailed Remaining Work

### 1. Student Rent Surface (`student.rent`)

**Current State:**
- Route calls `get_rent_assessments_for_cycle()`, `get_total_paid_for_assessment()`, `get_rent_payment_history()`
- Builds `period_status` dict with `is_paid`, `is_waived`, `is_late`, `assessments`, `total_paid`, `total_due`, `remaining_amount`
- Template variables pass all required fields

**To verify compliance:**
- [ ] Does the view model fully reflect `ASSESSMENT`, `PAYMENT`, `WAIVED` event types per DOM-OBL-001?
- [ ] Are all legacy rent-payment table accesses removed from the render path?
- [ ] Does grace-period logic derive correctly from assessment `due_at` timestamps?
- [ ] Are late fees calculated only from derived state, not stored amounts?

**Action:** Read the obligations FEAT spec to identify any gaps in the current view model.

---

### 2. Admin Rent Settings Surface (`admin.rent_settings`)

**Current State:**
- Route updates `RentSettings` policy fields
- Renders `admin_rent_settings.html` with status counts, waivers, and payment logs

**To verify compliance:**
- [ ] Does the waiver form use `FEAT-OBL-003` (`satisfy_obligation` with `satisfaction_type = WAIVER`)?
- [ ] Does the bill-cycle progression UI use `FEAT-OBL-002` (advance bill cycles)?
- [ ] Are rent assessments created only through `FEAT-OBLI-001`, not admin form submission?
- [ ] Is the payment log truly read-only (GET) vs. write (POST)?

**Action:** Clarify which admin operations mutate obligation events and which only configure policy.

---

### 3. FEAT Boundary Validation (Part B1–B3)

**Unchecked items:**

**B1: `FEAT-OBLI-001` (Assessment)**
- [ ] creates immutable obligation assessments
- [ ] does not write amount onto obligations tables
- [ ] coordinates satisfaction only through FEAT-OBL-003 when needed
- [ ] records `internal_ref` and `correlation_id`

**B2: `FEAT-OBL-002` (Bill Cycle Advancement)**
- [ ] advances recurring bill cycles
- [ ] only records identity-blind reminder state
- [ ] does not infer business meaning from the reference
- [ ] terminates cleanly when upstream relationship ends

**B3: `FEAT-OBL-003` (Satisfaction)**
- [ ] records payment satisfaction with lawful Ledger reference
- [ ] records rent waiver satisfaction without Ledger movement
- [ ] supports multiple partial payments for one assessment
- [ ] keeps satisfaction immutable
- [ ] writes to shared `assessment_events` table, not a separate satisfaction table

**Action:** Read FEAT specs and verify implementation against each checkbox.

---

### 4. Insurance Read Verification

**Current state in MAP:**
- `student.view_policy` — `REWIRED_READ`; reads entitlements + obligation renewal lineage
- `student.file_claim` — `REWIRED`; claim submission does NOT create obligation events
- `admin.process_claim` — `REWIRED`; claim decision does NOT mutate obligations

**Remaining verification:**
- [ ] When an insurance entitlement is created through `FEAT-STOR-001`, does it immediately create a rent obligation assessment via `FEAT-OBLI-001`?
- [ ] Does the insurance renewal flow read `assessment_events` (ASSESSMENT rows) to determine next due date?
- [ ] Are claim approvals isolated from rent obligation mutation?

**Action:** Trace the insurance purchase → rent obligation creation boundary in the code.

---

### 5. Canonical Inputs Checklist (Part A, lines 40–51)

All document inputs are unchecked. These are the authority specs that govern the rewiring:

- [ ] `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md` — defines obligation lifecycle and event model
- [ ] `docs/FEATURE-EXECUTION/FEAT-OBLI-001_ASSESS_OBLIGATION.md` — defines assessment creation
- [ ] `docs/FEATURE-EXECUTION/FEAT-OBL-002_ADVANCE_BILL_CYCLE.md` — defines cycle progression
- [ ] `docs/FEATURE-EXECUTION/FEAT-OBL-003_SATISFY_OBLIGATION.md` — defines payment/waiver satisfaction
- [ ] `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md` — defines entitlement lifecycle
- [ ] `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md` — defines rent policy configuration
- [ ] `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md` — defines rewiring plan
- [ ] `docs/MAP/MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE.md` — defines view model contract
- [ ] `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

**Action:** Mark these as reviewed to close the audit.

---

## Recommended Next Steps

### Option A: Close the Branch (If Compliant)
If the routes are already calling obligations_service correctly and the template audits passed, then:
1. Read the FEAT specs (DOM-OBL-001, FEAT-OBLI/OBL/STOR-001–003) to verify the current code matches
2. Check boxes B1–B3 as verified
3. Check boxes Part A as reviewed
4. Update MAP rows from `NEEDS_REWIRE` → `VERIFIED`
5. Commit the checklist updates

### Option B: Complete Remaining Rewiring (If Gaps Found)
If verification finds gaps:
1. Document the specific gap in the checklist
2. Create a focused PR to close each gap (e.g., "Fix admin rent waiver FEAT boundary")
3. Re-verify after each change
4. Then proceed to Option A

---

## Checklist Path Forward

### To close immediately:

1. **Read the 4 key FEAT specs:**
   - `FEAT-OBLI-001`, `FEAT-OBL-002`, `FEAT-OBL-003` (assessment, cycle, satisfaction)
   - `FEAT-STOR-001` (insurance purchase → obligation creation boundary)

2. **Validate Part B (FEAT boundaries):**
   - [ ] For each FEAT, read the spec and confirm the code matches each checkbox in B1/B2/B3

3. **Validate Part A (surfaces):**
   - Spot-check `student.rent` and `admin.rent_settings` routes against the FEAT specs

4. **Update Part A (canonical inputs):**
   - Mark all 12 docs as reviewed

5. **Update the checklist:**
   - Mark Part C completion items with evidence
   - Close Part D (completion criteria)

6. **Update the MAP:**
   - If verified, change obligations rows from `NEEDS_REWIRE` → `VERIFIED`

---

**Decision point:** Should we do a verification pass now, or focus on targeted rewiring first?
