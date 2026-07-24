# Obligations Domain Rewire Checklist

| Reference | Version | Date | Authority | Reviewer |
|-----------|---------|------|-----------|----------|
| AUDIT-OBL-001 | 1.0 | 2026-07-24 | QA/Review | [TBD] |

---

## Purpose

This checklist tracks the complete obligations-domain rewrite work: documentation, route/template rewiring, and the route/view-model pipeline required by `MAP-UI-001` and `MAP-UI-002`.

Use the audited template routes as the scope source. Do not invent new endpoints or surfaces beyond what is listed here.

**Target outcome:** canonical obligations surfaces are wired through `FEAT-OBLI-001`, `FEAT-OBL-002`, and `FEAT-OBL-003`, with rent and insurance read models derived from the new obligations contract.

---

## Canonical Inputs

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

## Part A: Obligations Surface Inventory

### A1: Student Rent Surface

File: `templates/student_rent.html`
Route: `student.rent` - `GET /student/rent`

**Phase 7 Audit Result: NEEDS_REWIRE (Critical)**

Issues Found:
- ❌ Route accesses removed schema fields: `amount_paid`, `was_late`, `late_fee_charged`, `satisfied_at`
- ❌ Route must derive amounts from Ledger transactions (via `ledger_transaction_id`), not from satisfaction row
- ✅ All 13 required variables are passed to template
- ✅ Route calls `obligations_service` functions (canonical read layer)

Canonical Requirements:
- [ ] Fix lines 2943, 2989-2993 to read amounts from Ledger via correlation_id
- [ ] Verify `payment_history` derives from assessments + satisfactions + ledger joins
- [ ] Ensure `period_status` reflects derived state (satisfied/outstanding) not mutable flags

Required route variables (all present):
- [x] `student` ✅
- [x] `settings` ✅
- [x] `student_blocks` ✅
- [x] `period_status` ✅
- [x] `current_block` ✅
- [x] `checking_balance` ✅
- [x] `savings_balance` ✅
- [x] `payment_due_date` ✅
- [x] `grace_end_date` ✅
- [x] `grace_end_date_for_status` ✅
- [x] `payment_history` ✅ (but needs schema fix)
- [x] `rent_items` ✅
- [x] `days_until_due` ✅

### A2: Admin Rent Settings Surface

File: `templates/admin_rent_settings.html`
Route: `admin.rent_settings` - `GET|POST /admin/rent-settings`

- [ ] rent settings render through the canonical class-config and obligations split
- [ ] view model distinguishes policy, cycle, assessment, satisfaction, and waiver facts
- [ ] template no longer treats `block`-grouped rent rows as authority
- [ ] waivers are routed through obligations satisfaction, not mutable rent state
- [ ] bill-cycle progression input is visible only through obligations-owned fields

Required route variables:

- [ ] `settings`
- [ ] `total_students`
- [ ] `active_waivers`
- [ ] `all_students`
- [ ] `payroll_warning`
- [ ] `payroll_settings`
- [ ] `settings_block`
- [ ] `teacher_blocks`
- [ ] `class_labels_by_block`
- [ ] `join_codes_by_block`
- [ ] `rent_items`
- [ ] `rent_active_for_period`
- [ ] `period_label`
- [ ] `rent_status_counts`
- [ ] `rent_status_total`
- [ ] `payment_log`
- [ ] `unpaid_rent_log`
- [ ] `current_period_start`
- [ ] `current_period_end`
- [ ] `next_due_date`
- [ ] `student_past_due_json`
- [ ] `current_coverage_due_date`
- [ ] `upcoming_coverage_due_date`
- [ ] `selected_feature_scope`

### A3: Student Insurance Marketplace

File: `templates/student_insurance_marketplace.html`
Route: `student.student_insurance` - `GET /student/insurance`

- [ ] template no longer treats insurance marketplace as a blank abort surface
- [ ] purchase view model uses canonical policy/enrollment/claim data
- [ ] obligations renewal status is read-only and derived
- [ ] template no longer assumes legacy insurance enrollment models are authoritative

Required route variables:

- [ ] `my_policies`
- [ ] `available_policies`
- [ ] `tier_groups`
- [ ] `my_claims`
- [ ] `can_purchase`
- [ ] `enrolled_tiers`
- [ ] `repurchase_blocks`
- [ ] `now`

### A4: Student Insurance Claim Submission

File: `templates/student_file_claim.html`
Route: `student.file_claim` - `GET|POST /student/insurance/claim/<int:policy_id>`

- [ ] claim form reads from canonical enrollment and claim lineage
- [ ] claim submission does not create obligation events
- [ ] eligibility and time-limit fields remain claim-local
- [ ] template only renders the current claim workflow contract

Required route variables:

- [ ] `form`
- [ ] `policy`
- [ ] `enrollment`
- [ ] `contract_title`
- [ ] `contract_description`
- [ ] `claim_type`
- [ ] `contract_claim_time_limit_days`
- [ ] `contract_max_claim_amount`
- [ ] `contract_max_claims_count`
- [ ] `contract_max_claims_period`
- [ ] `eligible_transactions`
- [ ] `claims_this_period`
- [ ] `remaining_period_cap`
- [ ] `errors`
- [ ] `now`

### A5: Student Insurance Policy View

File: `templates/student_view_policy.html`
Route: `student.view_policy` - `GET /student/insurance/policy/<int:enrollment_id>`

- [ ] policy detail page renders from canonical enrollment + claim lineage
- [ ] obligations-backed renewal status is derived, not stored on the template model
- [ ] claim history remains read-only

Required route variables:

- [ ] `student`
- [ ] `enrollment`
- [ ] `claims`
- [ ] `now`

### A6: Admin Insurance Management

Files: `templates/admin_insurance.html`, `templates/admin_edit_insurance_policy.html`
Routes: `admin.insurance_management`, `admin.edit_insurance_policy`

- [ ] insurance catalog/edit surfaces are class-config owned
- [ ] policy lineage remains versioned and prospective
- [ ] no obligations truth is mutated directly from these surfaces
- [ ] template fields match the current route view model

Required route variables for edit page:

- [ ] `policy`
- [ ] `form`
- [ ] `available_policies`
- [ ] `tier_groups`
- [ ] `payroll_settings`
- [ ] `insurance_recommendation`

### A7: Insurance Claim Decision Surfaces

Files: `templates/admin_process_claim.html`, `templates/admin_view_student_policy.html`
Routes: `admin.process_claim`, `admin.view_student_policy`

- [ ] claim decision remains a Store/Entitlements consumer of obligation-backed coverage state
- [ ] claim approval/rejection does not mutate obligations tables directly
- [ ] route/template contract renders from canonical claim and enrollment lineage

Required route variables:

- [ ] `claim`
- [ ] `policy`
- [ ] `enrollment`
- [ ] `claims`
- [ ] `decision_form`

### A8: Admin Summary Surfaces That Surface Obligations Data

Files: `templates/admin_dashboard.html`, `templates/admin_economy_health.html`

- [ ] pending insurance and rent counts are read-only projections
- [ ] dashboard and economy-health pages do not invent debt state
- [ ] these pages consume obligations read models only

---

## Part B: FEAT Boundary Checklist

### B1: `FEAT-OBLI-001`

- [ ] creates immutable obligation assessments
- [ ] does not write amount onto obligations tables
- [ ] coordinates satisfaction only through the satisfaction FEAT when needed
- [ ] records `internal_ref` and `correlation_id`

### B2: `FEAT-OBL-002`

- [ ] advances recurring bill cycles
- [ ] only records identity-blind reminder state
- [ ] does not infer business meaning from the reference
- [ ] terminates cleanly when the upstream relationship ends

### B3: `FEAT-OBL-003`

- [ ] records payment satisfaction with a lawful Ledger reference
- [ ] records rent waiver satisfaction without a Ledger movement
- [ ] supports multiple partial payments for one assessment
- [ ] keeps satisfaction immutable

---

## Part C: MAP / Pipeline Checklist

### C1: MAP-UI-001

- [ ] Obligations slice is present and detailed
- [ ] every obligations-facing template surface is listed
- [ ] each row includes route, current status, route variables, obligations role, and audit source
- [ ] insurance rows remain present where they depend on obligations-backed renewal state

### C2: MAP-UI-002

- [ ] routes assemble canonical context first
- [ ] temporal context is supplied from class-scoped authority
- [ ] identity display context remains separate from authority
- [ ] page view models are built from lawful domain reads

---

## Part D: Completion Criteria

The checklist passes only if all of the following are true:

- [ ] all obligations-facing template rows are inventoried
- [ ] the rewired surfaces match the canonical obligations FEAT contract
- [ ] no template relies on retired obligation lifecycle/reversal state
- [ ] rent read/write surfaces are canonical
- [ ] insurance read/write surfaces remain separated from obligation mutation while consuming obligations-backed renewal status
- [ ] all findings are documented with file, route, and template references

If any item cannot be proven from current evidence, mark the item pending and record the missing proof path.
