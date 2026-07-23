# STORE Domain End-to-End Audit Report

| Reference | Version | Date | Authority | Reviewer |
|-----------|---------|------|-----------|----------|
| AUDIT-STORE-001 | 1.0 | 2026-07-23 | QA/Review | Claude Opus 4.6 |

---

## Verdict: AUDIT FAIL

22 of 45 checklist items pass. 15 items fail. 8 items are partial pass or conditional.

---

## Pre-Audit Setup

- [x] Checked out branch `entitlement-domain-rework`
- [x] Working tree clean before audit
- [x] All 12 authoritative documents read

---

## Part A: Schema and Data Model Audit

### A1: Canonical Store/Entitlement Tables

- [x] `entitlements` — PASS. Append-only grant history at `models.py:948`. Columns: `entitlement_id` (UUID), `entitlement_item_id` (FK→store_items), `target_seat_id`, `actor_seat_id`, `class_id`, `grant_type` (PURCHASE/MANUAL_GRANT/OBLIGATION), `correlation_id`, `granted_at`. No mutable balance columns.
- [x] `entitlement_consumptions` — PASS. Append-only terminal lifecycle at `models.py:981`. Columns: `consumption_id` (UUID), `entitlement_id` (FK), `class_id`, `target_seat_id`, `actor_seat_id`, `disposition` (CONSUMED/EXPIRED/REVOKED), `correlation_id`, `timestamp`. Unique constraint `uq_entitlement_terminal_event` on `(entitlement_id, disposition)`.
- [x] `insurance_claims` — PASS. Mutable claim workflow at `models.py:1013`. Columns: `claim_id` (UUID), `class_id`, `entitlement_id` (FK), `target_seat_id`, `actor_seat_id`, `transaction_id` (FK→ledger, nullable), `claimed_dates` (JSON), `status` (SUBMITTED/APPROVED/REJECTED), `submitted_at`, `decided_at`, `decided_by_seat_id`, `correlation_id`.

Forbidden patterns:
- [x] No mutable entitlement balance columns — PASS. No `uses_remaining` or `bundle_remaining` anywhere in models.
- [x] No purchase quantity as entitlement truth — PASS. `StorePurchase.quantity` exists on legacy table but `Entitlement` has no quantity field.
- [x] No direct Store ownership of class configuration — PASS.
- [x] No direct Ledger ownership leaks into Store rows — PASS. `Entitlement` and `EntitlementConsumption` carry no ledger FKs. `InsuranceClaim.transaction_id` is a nullable cross-domain correlation reference (acceptable per INV-ARC-021).

### A2: Insurance Policy Configuration Tables

- [x] `policy_versions` — PASS. At `models.py:1722`. Columns: `class_id`, `domain`, `version_number`, `policy_payload_json`, `created_at`, `activated_at`, `created_by_transition_id`, `is_active`.
- [x] `policy_transitions` — PASS. At `models.py:1753`. Columns: `class_id`, `domain`, `source_policy_version_id`, `target_policy_version_id`, `activation_mode`, `status`, `created_at`, `created_by` (bare integer — no FK constraint, data integrity gap), `applied_at`, `correlation_id`, `superseded_by_transition_id`, `cancelled_at`.
- [ ] `entitlement_item_id` on policy lineage — **FAIL**. Neither `PolicyVersion` nor `PolicyTransition` has an `entitlement_item_id` column. The mapping exists only in `policy_payload_json` content, not as a schema-level FK.
- [x] Versioned terms in policy payload — PASS. `PolicyVersion.policy_payload_json` carries versioned terms.

### A3: Required Table Checks

- [x] `entitlements` is append-only grant history — PASS.
- [x] `entitlement_consumptions` is append-only terminal lifecycle — PASS.
- [x] `insurance_claims` is mutable claim workflow, not entitlement store — PASS.
- [x] `policy_versions`/`policy_transitions` are the only class-side insurance lineage tables — PASS.

### A-CONCERNS

1. **`PolicyTransition.created_by`** (`models.py:1771`) is a bare integer with no FK constraint to `users` or `seats`.
2. **`PolicyVersion.is_active`** is a mutable boolean on what should be an immutable version row — active status should derive from `PolicyTransition` state.
3. **`RedemptionEvent`** (`models.py:902`) keys off `purchase_id` (FK→`StorePurchase`) rather than `entitlement_id` (FK→`Entitlement`), anchoring audit lineage to the legacy model.

---

## Part B: FEAT Layer Audit

### B1: FEAT-STOR-001 (Store Purchase)

File: `app/feats/store_purchase_feat.py`

- [x] `FEAT-STOR-001` is the only lawful writer for `grant_type = PURCHASE` — PASS. `execute_store_purchase` decorated `@requires_feat_context("FEAT-STOR-001")`.
- [x] Purchase creates one entitlement row per unit — PASS. Lines 171–181 loop `for _ in range(quantity)`, calling `grant_entitlement()` once per unit.
- [x] Quantity does not become entitlement balance authority — PASS. Balance derived via `get_entitlement_balance` counting non-terminated rows.
- [x] Insurance purchase uses configured entitlement mapping — PASS (with caveat). `insurance_purchase_feat.py:51–59` checks `entitlement_item_id` from policy. However `execute_insurance_purchase` has NO `@requires_feat_context` decorator — structural gap.
- [x] Ledger posting through lawful Ledger boundary — PASS. Calls `ledger_service.create_pending_transaction()`.

### B2: FEAT-STOR-002 (Entitlement Terminal Lifecycle)

File: `app/feats/redemption_disposition_feat.py`

- [ ] FEAT covers CONSUMED, EXPIRED, REVOKED — **PARTIAL FAIL**. Only CONSUMED has a FEAT-gated path. `expire_entitlement` and `revoke_entitlement` exist only as raw service primitives in `store_entitlement_service.py` with no FEAT wrapper.
- [x] Writes to `entitlement_consumptions` — PASS. `consume_entitlement` → `_write_terminal_event` writes `EntitlementConsumption` rows.
- [x] Insurance claims do not create entitlement terminal events — PASS. No `consume_entitlement` calls in claim feat.
- [x] Hall-pass consumption owned elsewhere — PASS. Hall-pass consumption in `app/feats/prod.py:314`.
- [ ] Insurance entitlements non-revocable after purchase — **UNVERIFIABLE**. No guard exists on `revoke_entitlement` to reject insurance-typed entitlements, and there is no FEAT gate on the revocation path.

### B3: FEAT-STOR-003 (Insurance Claim Lifecycle)

File: `app/feats/insurance_claim_feat.py`

- [x] Claim submission creates SUBMITTED — PASS. `execute_claim_submission` → `submit_insurance_claim()` sets `status=SUBMITTED`.
- [x] Transitions forward-only — PASS. Guards: `if claim.status != SUBMITTED: raise ValueError`.
- [ ] Transaction claims route compensatory credit through Ledger — **FAIL**. `execute_claim_approval` only mutates claim status. No ledger credit is posted on approval. No type-specific routing exists.
- [ ] Productivity claims route MANUAL_CREDIT through Payroll → Ledger — **FAIL**. Resolved claim type is used only for message formatting, not for Payroll FEAT invocation.
- [x] Claim submission does not consume entitlement — PASS.
- [x] Cancellation of offering does not invalidate existing coverage — PASS (by design — deactivation only hides from new enrollment).

### B4: FEAT-CLASS-003 (Insurance Policy Management)

Files: `app/routes/admin.py` (inline only — no dedicated feat file)

- [ ] Policy operations are class-configuration operations — **PARTIAL FAIL**. Store item CRUD uses `FEATContext("FEAT-CLASS-003")` correctly, but insurance policy routes (`edit_insurance_policy`, `deactivate_insurance_policy`, `delete_insurance_policy`) bypass FEAT-CLASS-003 entirely with bare `db.session.commit()`.
- [ ] Policy edits create new prospective version — **SPLIT**. Insurance policy edit DOES create a new `PolicyVersion` via `create_policy_version()` (PASS). Store item edit mutates in place via `form.populate_obj(item)` (FAIL for store items).
- [ ] Switching limited to same tier group — **NOT ENFORCED** in FEAT layer.
- [ ] Bundle eligibility honors grouped tiers — **NOT ENFORCED** in FEAT layer.
- [ ] Deletion scheduled from last enforced entitlement boundary — **SPLIT**. Insurance `delete_insurance_policy` correctly schedules via `schedule_policy_deletion()` with entitlement boundary (PASS). Store item `delete_store_item` deactivates immediately (acceptable — store items are not versioned policies).
- [ ] Policy changes emit persistent student-visible banners — **FAIL**. Only `flash()` messages for teacher UI. No persistent student-visible banners.
- [x] Class-config changes do not mutate entitlement/obligation/ledger tables — PASS.

---

## Part C: Route Wiring Audit

### C1: Store Dashboard Read Model

File: `app/routes/admin.py:5157`

- [x] Uses canonical store read model data — PASS. Items via `StoreItem.query.filter_by(class_id=...)`.
- [x] Pending redemptions from canonical redemption workflow rows — PASS. Derived from `RedemptionEvent` filtered to `REQUEST`.
- [x] Recent purchases from entitlement lineage — PASS. Queries `Entitlement` with `grant_type == PURCHASE`.
- [x] GET path has no side effects — PASS. No `db.session.add/commit/flush` in GET branch.

### C2: Store Item Management

- [x] Create/edit/deactivate use FEAT-CLASS-003 — PASS. All three use `FEATContext("FEAT-CLASS-003")`.
- [x] Deactivation hides without mutating unrelated records — PASS.
- [ ] Dead orphan `StoreItem()` constructor — **FAIL** (code hygiene). `admin.py:5201–5238` constructs a `StoreItem` that is immediately overwritten by `create_store_item()` at line 5239.

### C3: Store Purchase and Redemption

- [x] Purchase route calls FEAT-STOR-001 — PASS. `api.purchase_item` decorated `@feat_shell("FEAT-STOR-001")`.
- [ ] Item use route calls FEAT-STOR-002 — **PARTIAL FAIL**. General path correct, but hall-pass early-exit at `api.py:715–719` sets `student_item.status = 'redeemed'` without calling `consume_entitlement`. No `EntitlementConsumption` record written for hall-pass items.
- [x] Approval writes authoritative terminal consumption — PASS. `execute_redemption_approval` calls `consume_entitlement`.
- [x] Rejection preserves entitlement — PASS. No `consume_entitlement` call on rejection.

### C4: Insurance Marketplace and Purchase

- [x] Marketplace renders class-scoped offerings — PASS. Uses `list_insurance_policy_versions(context.class_id)`.
- [ ] Insurance purchase uses canonical purchase orchestration — **FAIL**. `student.purchase_insurance` at `student.py:1599` has NO `@feat_shell` decorator. `execute_insurance_purchase` has no `@requires_feat_context`. No FEAT transaction boundary, no rollback guarantee, no audit correlation.

### C5: Insurance Claim and Policy Views

- [x] Student claim submission uses canonical claim lifecycle — PASS (via function-level `@requires_feat_context`).
- [ ] Teacher claim decision matches FEAT-STOR-003 — **PARTIAL FAIL**. Bare `db.session.commit()` at `admin.py:6943, 6951` outside FEAT boundary. Commit ownership should belong to the FEAT shell.

### C6: Insurance Policy Management

- [ ] Insurance editor uses FEAT-CLASS-003 — **FAIL**. Routes at `admin.py:6657, 6750, 6783` all bypass FEAT layer with bare `db.session.commit()`.
- [x] Edit creates new prospective version — PASS. Calls `create_policy_version()`.
- [x] Deactivate makes policy unavailable for new enrollment — PASS.
- [x] Delete schedules hard deletion using entitlement end boundary — PASS. Uses `schedule_policy_deletion()` with `coverage_end_time` boundary.
- [ ] Notification banners are persistent until dismissed — **FAIL**. Only teacher-facing `flash()` messages.

---

## Part D: Template Audit

### admin_store.html — FAIL

- [ ] **Lines 724–729**: Purchase History tab iterates `item.purchases` (raw `StorePurchase` rows) and accesses `student_item.is_from_bundle` and `student_item.bundle_remaining` — retired `StudentItem` fields that do not exist on `StorePurchase`. Will raise `AttributeError` at runtime when the history tab is rendered.

### admin_insurance.html — PASS

- [x] No retired fields. View model matches template. Form actions point at current routes.

### admin_edit_insurance_policy.html — FAIL

- [ ] **Line 46**: Accesses `item.title` on `StoreItem` ORM rows — `StoreItem` has `name`, not `title`. Route also uses `StoreItem.title.asc()` for ordering at `admin.py:6668`, which will raise `InvalidRequestError` at query time (HTTP 500).

### student_shop.html — CONDITIONAL PASS

- [x] `uses_remaining`, `bundle_remaining`, `is_from_bundle` are present but stubbed as `None`/`False` by the route. No runtime crash. Dead display branches remain as structural residue.

### student_insurance_marketplace.html — FAIL

- [ ] **Lines 471–505**: Claims History tab accesses `claim.policy`, `claim.incident_date`, `claim.filed_date`, `claim.approved_amount`, `claim.claim_amount`, `claim.rejection_reason` on raw `InsuranceClaim` rows. None of these fields exist on the canonical model. `.strftime()` calls on `None` will crash when claims exist.
- [ ] **Lines 324–326**: `policy.no_repurchase_after_cancel` and `policy.repurchase_wait_days` not set on route's `SimpleNamespace` — silently suppressed.

### student_file_claim.html — FAIL

- [ ] **Lines 51–52**: `form.transaction_id.label()` and `form.transaction_id()` on a `SimpleNamespace(hidden_tag=lambda: "")` stub — WTForms field attributes missing. GET render will crash.
- [ ] Missing effective CSRF token (stub returns empty string).

### student_view_policy.html — FAIL

- [ ] **Lines 119–120**: `claim.incident_date.strftime()` and `claim.filed_date.strftime()` on raw `InsuranceClaim` rows — fields don't exist. Crashes when claims exist.
- [ ] **Lines 238–256**: `enrollment.policy.no_repurchase_after_cancel` and `enrollment.policy.repurchase_wait_days` not set on route's `SimpleNamespace` — repurchase warning silently suppressed.

### admin_process_claim.html — FAIL

- [ ] **Line 147**: `claim.policy.waiting_period_days` — `claim_view` SimpleNamespace has no `.policy` attribute. Renders empty.
- [ ] **Line 32**: `claim.student.full_name` renders seat `public_id` (UUID) instead of display name.
- [ ] Claim narrative fields (`description`, `comments`, `rejection_reason`, `teacher_notes`) are stubbed as empty strings — canonical `InsuranceClaim` has no such columns.

### admin_view_student_policy.html — FAIL

- [ ] **Lines 120–121**: `claim.incident_date.strftime()` and `claim.filed_date.strftime()` on raw `InsuranceClaim` rows — crashes when claims exist.
- [ ] **Line 8**: `student.full_name` renders as empty string.

---

## Part E: Completion Criteria

- [x] MAP checklist rows for STORE and insurance surfaces are all marked `REWIRED` — PASS.
- [ ] Current code matches authority and persistence model in canonical docs — **FAIL**. See findings below.
- [ ] No stale template row shapes remain on audited surfaces — **FAIL**. 7 of 9 templates have stale field references.
- [ ] No direct domain boundary violations in audited paths — **FAIL**. Insurance policy routes bypass FEAT layer; claim approval has no compensatory credit path; insurance purchase has no FEAT boundary.
- [x] All findings documented with exact file, route, and template references — PASS.

---

## Findings Summary

### Critical (domain contract violations)

| # | Finding | Location | Contract |
|---|---------|----------|----------|
| F1 | Insurance claim approval posts no compensatory Ledger credit | `insurance_claim_feat.py:78–92` | FEAT-STOR-003 §IV.B |
| F2 | Productivity claim approval does not route MANUAL_CREDIT through Payroll | `insurance_claim_feat.py:78–92` | FEAT-STOR-003 §IV.C |
| F3 | Insurance purchase has no FEAT boundary (no `@feat_shell`, no `@requires_feat_context`) | `student.py:1599`, `insurance_purchase_feat.py` | FEAT-STOR-001 |
| F4 | Insurance policy management routes bypass FEAT-CLASS-003 | `admin.py:6657, 6750, 6783` | FEAT-CLASS-003 |
| F5 | EXPIRED and REVOKED terminal dispositions have no FEAT gate | `store_entitlement_service.py` only | FEAT-STOR-002 |
| F6 | No insurance non-revocability guard on revoke path | `store_entitlement_service.py` | DOM-STORE-001 §VII.D |

### High (template crashes)

| # | Finding | Location |
|---|---------|----------|
| F7 | `admin_edit_insurance_policy.html` uses `item.title` — `StoreItem` has `name`; route `order_by(StoreItem.title)` will 500 | `admin.py:6668`, template line 46 |
| F8 | Insurance claim templates access `claim.incident_date.strftime()` — field doesn't exist; crashes when claims exist | `student_insurance_marketplace.html:472`, `student_view_policy.html:119`, `admin_view_student_policy.html:120` |
| F9 | `student_file_claim.html` accesses `form.transaction_id` on stub SimpleNamespace — GET crashes | template line 51 |
| F10 | `admin_store.html` purchase history tab reads `is_from_bundle`/`bundle_remaining` on `StorePurchase` rows — `AttributeError` | template lines 724–729 |

### Medium (contract gaps)

| # | Finding | Location |
|---|---------|----------|
| F11 | `entitlement_item_id` not a schema-level column on `PolicyVersion`/`PolicyTransition` | `models.py` |
| F12 | `PolicyTransition.created_by` is bare integer with no FK | `models.py:1771` |
| F13 | Hall-pass early-exit in `use_item` bypasses `consume_entitlement` | `api.py:715–719` |
| F14 | Bare `db.session.commit()` in `process_claim` route outside FEAT boundary | `admin.py:6943, 6951` |
| F15 | Policy changes emit only `flash()` — no persistent student-visible banners | `admin.py:6657–6821` |

### Low (code hygiene / display)

| # | Finding | Location |
|---|---------|----------|
| F16 | Dead orphan `StoreItem()` constructor before `create_store_item()` | `admin.py:5201–5238` |
| F17 | `student_shop.html` retains stubbed `uses_remaining`/`bundle_remaining` dead branches | template lines 228–239 |
| F18 | `admin_process_claim.html` renders seat `public_id` as student name | template line 32 |
| F19 | `RedemptionEvent` keys off `purchase_id` not `entitlement_id` | `models.py:905` |
| F20 | `PolicyVersion.is_active` mutable flag on immutable version row | `models.py:1740` |

---

## Conclusion

The Store domain schema (Part A) is substantially compliant — canonical tables exist with correct shapes and no forbidden mutable counters. The FEAT layer (Part B) has correct purchase and consumption orchestration but is missing critical claim compensation paths and FEAT gates for EXPIRED/REVOKED dispositions. Route wiring (Part C) is correct for core store purchase/redemption but insurance routes lack FEAT boundaries. Templates (Part D) are the weakest surface — 7 of 9 audited templates reference fields that do not exist on the canonical models, with several paths that will crash at runtime when insurance claims exist.

**Next steps:** Remediate F1–F10 (critical and high findings) before this audit can pass.
