# Obligations Domain Rewiring — Focused Action Plan
**Branch:** `obligatin-domain-rewire` | **Date:** 2026-07-25

---

## Overview

Based on **MAP-UI-001** (canonical rewiring plan), there are **2 surfaces** that must be normalized to canonical obligation events and bill cycles:

1. **Student Rent View** (`student.rent` route)
2. **Admin Rent Settings** (`admin.rent_settings` route)

This plan defines the exact view-model contract each route must satisfy, identifies gaps, and prescribes fixes.

---

## 1. Student Rent View (`student.rent`)

### MAP Contract (Line 141 of MAP-UI-001)

**Expected View Variables:**
```
rent_items
active_waivers
current_period_start
current_period_end
current_coverage_due_date
rent_status_counts
rent_status_total
unpaid_rent_log
```

**Persistence Model:**
- Reads: `assessment_events` (PAYMENT, WAIVED event rows), `bill_cycles`, `ledger_transaction`
- Domain: Read-only `DOM-OBL`; rent terms from Class Configuration; payment truth from Ledger

**Current State (per MAP):**
> "Route and template currently expose rent status, waivers, and current period facts; this surface **must be normalized to canonical obligation events and bill cycles rather than legacy rent-payment rows**"

### Current Route Variables (line 3106 of app/routes/student.py)

```python
render_template('student_rent.html',
  student=seat,
  settings=settings,
  student_blocks=student_blocks,
  period_status=period_status,
  current_block=current_block,
  checking_balance=checking_balance,
  savings_balance=savings_balance,
  due_date=due_date,
  payment_due_date=payment_due_date,
  grace_end_date=grace_end_date,
  grace_end_date_for_status=grace_end_date_for_status,
  preview_start_date=preview_start_date,
  payment_history=payment_history_rows,
  rent_items=rent_items,
  days_until_due=days_until_due
)
```

### Gap Analysis

**Present (✅):**
- `rent_items` ✅

**Missing (❌) — Must Add:**
- `active_waivers` — List of WAIVED obligation events (currently passed but named `waiver_rows` internally; need to expose)
- `current_period_start` — Canonical start date of current obligation assessment cycle
- `current_period_end` — Canonical end date of current obligation assessment cycle
- `current_coverage_due_date` — Due date of the assessment being viewed
- `rent_status_counts` — Summary counts by status (SATISFIED, OUTSTANDING, PAST_DUE)
- `rent_status_total` — Total amount outstanding across all statuses
- `unpaid_rent_log` — List of outstanding assessments with amounts owed

**Present but Non-canonical (⚠️) — May Need to Retire:**
- `student` — Probably needed for display, but check if it violates identity boundaries
- `settings` — Rent policy; canonical from Class Configuration
- `student_blocks` — Display only; OK
- `period_status` — May be legacy; verify if `rent_status_counts` + assessment list replaces it
- `current_block` — Display only; OK
- `checking_balance`, `savings_balance` — Ledger state; OK for display
- `due_date`, `payment_due_date`, `grace_end_date`, `grace_end_date_for_status` — Assessment-derived; likely consolidated into new view
- `preview_start_date` — Canonical from bill_cycle or assessment; check if needed
- `payment_history_rows` — Currently derived from assessments; likely replaced by structured assessment + event list
- `days_until_due` — Derived; OK if kept for display

### Work Items

**1.1 Add `active_waivers`**
- Extract from the existing `waiver_rows` query (line 3037)
- Format as list of dicts: `{assessment_id, assessed_at, ...}`
- Pass to template

**1.2 Add `current_period_start` and `current_period_end`**
- These define the canonical assessment cycle boundary
- Source: Derived from assessment `due_at` or bill_cycle `cycle_boundary_at`
- Logic: Current/active rent cycle start/end dates (e.g., 2026-07-01 to 2026-07-31 for monthly rent)

**1.3 Add `current_coverage_due_date`**
- The `due_at` of the current assessment being viewed
- Source: assessment event's `due_at` field

**1.4 Add `rent_status_counts`**
- Structured as: `{SATISFIED: N, OUTSTANDING: N, PAST_DUE: N}`
- Derived by looping through assessments and checking each one's derived status
- Status derivation per DOM-OBL-001 §VIII:
  ```
  paid_amount = sum(Ledger amounts from PAYMENT events)
  has_waiver = exists(WAIVED for same correlation_id)
  
  if paid_amount >= assessed_amount:
      status = SATISFIED
  elif has_waiver:
      status = SATISFIED
  else:
      status = OUTSTANDING
  
  if status == OUTSTANDING and now > due_at:
      status = PAST_DUE
  ```

**1.5 Add `rent_status_total`**
- Total amount owed across all outstanding assessments
- Source: For each OUTSTANDING assessment, add `(assessed_amount - paid_amount)`

**1.6 Add `unpaid_rent_log`**
- List of outstanding assessments with amounts owed
- Format: `[{assessment_id, period_month, period_year, amount_owed, due_at, is_late}, ...]`
- Filter: Only assessments where status != SATISFIED

---

## 2. Admin Rent Settings (`admin.rent_settings`)

### MAP Contract (Line 142 of MAP-UI-001)

**Expected View Variables:**
```
settings
rent_items
all_students
active_waivers
current_period_start
current_period_end
current_coverage_due_date
rent_status_counts
rent_status_total
unpaid_rent_log
```

**Persistence Model:**
- Reads: `rent_settings`; reads and writes `assessment_events` (PAYMENT/WAIVED rows), `bill_cycles`
- FEAT Boundaries: **`FEAT-OBL-002`** for bill-cycle progression, **`FEAT-OBL-003`** for rent waiver actions
- Domain: Class Configuration for policy; Obligations for event recording

**Current State (per MAP):**
> "Admin rent surface is still wired to legacy waiver/payment semantics in the current checkout; it needs **explicit obligations FEAT boundaries and a canonical view model split for policy, cycle, assessment, and event history**"

### Current Route Variables (line 5796 of app/routes/admin.py)

Passed to template (need to verify exact list from render_template call):
```
settings
total_students
active_waivers
all_students
payroll_warning
payroll_settings
settings_block
teacher_blocks
class_labels_by_block
join_codes_by_block
rent_items
rent_active_for_period
period_label
rent_status_counts
rent_status_total
payment_log
unpaid_rent_log
current_period_start
current_period_end
next_due_date
student_past_due_json
current_coverage_due_date
upcoming_coverage_due_date
selected_feature_scope
```

### Gap Analysis

**Present (✅):**
- `settings` ✅
- `rent_items` ✅
- `all_students` ✅
- `active_waivers` ✅
- `current_period_start` ✅
- `current_period_end` ✅
- `current_coverage_due_date` ✅
- `rent_status_counts` ✅
- `rent_status_total` ✅
- `unpaid_rent_log` ✅

**Missing (❌):** None — admin route already has expected variables

**Issue (⚠️) — FEAT Boundaries Not Explicit:**
The route performs waiver and bill-cycle mutations, but the code flow doesn't clearly show:
1. Where `FEAT-OBL-002` is invoked (bill-cycle progression)
2. Where `FEAT-OBL-003` is invoked (waiver recording)

**Current Code Patterns:**
- Line ~5855: `with FEATContext("FEAT-ADMN-001", ...)` — This is wrong; should be FEAT-OBL-002 or FEAT-OBL-003
- Line ~6330+: Admin waiver form processing — Does this call `record_rent_waiver()` from obligations_service? Need to verify

### Work Items

**2.1 Audit Waiver Recording Flow**
- Find where admin form submits a waiver request
- Verify it calls `obligations_service.record_rent_waiver()`
- If not, wire it to do so

**2.2 Audit Bill-Cycle Advancement Flow**
- Identify if/where the admin route advances bill cycles
- If it does, verify it's using a canonical `FEAT-OBL-002` orchestration
- If not, document that bill-cycle advancement is external (e.g., scheduled task)

**2.3 Explicit FEAT Context**
- Replace `FEATContext("FEAT-ADMN-001")` with explicit `FEAT-OBL-003` when recording waivers
- Add `FEAT-OBL-002` context if bill-cycle progression happens here

**2.4 View Model Verification**
- Confirm that `rent_status_counts` and `unpaid_rent_log` are built from assessment events, not legacy tables
- Confirm `active_waivers` includes all WAIVED event rows scoped to class

---

## 3. FEAT Boundary Checklist

After rewiring the routes, verify that these FEAT contracts are honored:

### FEAT-OBL-003 (Satisfy Obligation) — Required for Waivers

When admin records a rent waiver:
- [ ] Calls `record_rent_waiver()` from obligations_service
- [ ] Creates an immutable `WAIVED` event in `assessment_events` table
- [ ] Sets `event_type = 'WAIVED'`
- [ ] Sets `obligation_type = 'RENT'`
- [ ] NO Ledger transaction created (waivers don't create Ledger movements)
- [ ] Correlation_id links the waiver to the assessment it resolves

### FEAT-OBL-002 (Advance Bill Cycle) — If Present

If admin manually advances bill cycles:
- [ ] Calls canonical bill-cycle advancement function
- [ ] Creates a successor row in `bill_cycles` table
- [ ] Does NOT store amount, business meaning, or seat/class identity in the cycle
- [ ] Idempotent: retrying with same cycle number produces no duplicate

---

## 4. Template Variable Reconciliation

Once route variables are updated, the templates must be checked:

### `student_rent.html`
- [ ] Does it reference `payment_history` or should it use `unpaid_rent_log`?
- [ ] Does `period_status` dict structure match the current template rendering?
- [ ] Does it iterate over assessments correctly using canonical event data?

### `admin_rent_settings.html`
- [ ] Does it render `payment_log` and `unpaid_rent_log` using canonical assessment events?
- [ ] Does the waiver form submission call the right endpoint/FEAT?
- [ ] Does it display bill-cycle state if applicable?

---

## 5. Canonical Inputs Checklist

Per OBLIGATIONS_DOMAIN_REWIRE_CHECKLIST.md Part A, mark as reviewed:

- [ ] `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md`
- [ ] `docs/FEATURE-EXECUTION/FEAT-OBLI-001_ASSESS_OBLIGATION.md`
- [ ] `docs/FEATURE-EXECUTION/FEAT-OBL-002_ADVANCE_BILL_CYCLE.md`
- [ ] `docs/FEATURE-EXECUTION/FEAT-OBL-003_SATISFY_OBLIGATION.md`
- [ ] `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- [ ] `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- [ ] `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md`
- [ ] `docs/MAP/MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE.md`
- [ ] `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- [ ] `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

---

## 6. Completion Criteria

The branch is complete when:

- [ ] Student rent route exposes all MAP-expected view variables
- [ ] Admin rent settings route exposes all MAP-expected view variables (already done)
- [ ] Both routes derive state from `assessment_events`, not legacy rent tables
- [ ] Waiver operations call `record_rent_waiver()` through `FEAT-OBL-003`
- [ ] Bill-cycle operations (if present) use canonical FEAT-OBL-002
- [ ] Templates render without errors and display canonical obligation state
- [ ] All canonical input docs are marked reviewed in checklist
- [ ] MAP rows updated from `NEEDS_REWIRE` → `VERIFIED` with evidence

---

## Next Steps

**Immediate:** Start with **Item 1.1–1.6** (student.rent variables)  
**Then:** Audit **Item 2.1–2.4** (admin.rent_settings FEAT boundaries)  
**Finally:** Update checklist and MAP status rows

Would you like me to start implementing any of these work items?
