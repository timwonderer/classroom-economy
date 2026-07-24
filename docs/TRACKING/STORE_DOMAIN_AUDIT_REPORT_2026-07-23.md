# STORE Domain End-to-End Audit Report

| Reference | Version | Date | Authority | Reviewer |
|-----------|---------|------|-----------|----------|
| AUDIT-STORE-001 | 3.0 | 2026-07-24 | QA/Review | Claude Opus 4.6 |

---

## Result

**AUDIT FAIL** (conditional — 3 residual findings, 1 blocking)

Third audit round after two remediation passes. 17 of 20 original findings are remediated. 3 remain open: 1 blocking (F7 route query crash), 2 structural debt (F19, F20).

---

## Canonical Documents Reviewed

- `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `docs/FEATURE-EXECUTION/FEAT-CLASS-003_INSURANCE_POLICY_MANAGEMENT.md`
- `docs/FEATURE-EXECUTION/FEAT-STOR-001_STORE_PURCHASE.md`
- `docs/FEATURE-EXECUTION/FEAT-STOR-002_ENTITLEMENT_TERMINAL_LIFECYCLE.md`
- `docs/FEATURE-EXECUTION/FEAT-STOR-003_INSURANCE_CLAIM_LIFECYCLE.md`
- `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md`
- `docs/INVARIANT/ARCHITECTURE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-007_REQUEST_HANDLER_AUTHORITY_AND_SIDE_EFFECT_BOUNDARIES.md`

---

## Part A: Schema and Data Model

Status: **PASS**

### A1: Canonical Store/Entitlement Tables

- [x] `entitlements` — append-only grant history, no mutable balance columns. `models.py:948`.
- [x] `entitlement_consumptions` — append-only terminal lifecycle with unique constraint. `models.py:981`.
- [x] `insurance_claims` — mutable claim workflow, not entitlement store. `models.py:1013`.
- [x] No `uses_remaining` / `bundle_remaining` anywhere.
- [x] No purchase quantity as entitlement truth.
- [x] No direct Store ownership of class configuration.
- [x] No direct Ledger ownership leaks.

### A2: Insurance Policy Configuration Tables

- [x] `policy_versions` — versioned terms in `policy_payload_json`. `models.py:1722`.
- [x] `policy_transitions` — with FK on `created_by` → `users.id` (F12 REMEDIATED). `models.py:1753`.

### A3: Required Table Checks — all PASS.

### Residual concerns

| # | Finding | Severity |
|---|---------|----------|
| F19 | `RedemptionEvent` keys off `purchase_id` not `entitlement_id` | Low (structural debt) |
| F20 | `PolicyVersion.is_active` mutable; `economy_rebalance.py:424` mutates `target_version.is_active = True` on existing rows | Low (structural debt) |

---

## Part B: FEAT Layer

Status: **PASS**

### B1: FEAT-STOR-001 — PASS
- [x] One entitlement row per unit.
- [x] Ledger through lawful boundary.
- [x] Insurance purchase now has `@feat_shell("FEAT-STOR-001")` (F3 REMEDIATED).

### B2: FEAT-STOR-002 — PASS
- [x] `revoke_entitlement` and `expire_entitlement` now have `@feat_shell("FEAT-STOR-002")` (F5 REMEDIATED).
- [x] Insurance non-revocability guard present (F6 REMEDIATED).
- [x] Insurance claims do not create terminal events.
- [x] Hall-pass consumption owned by Productivity domain.

### B3: FEAT-STOR-003 — PASS
- [x] Transaction claim approval now posts compensatory Ledger credit via `ledger_service.create_pending_transaction()` (F1 REMEDIATED).
- [x] Productivity claim approval now coordinates `manual_credit` payroll event via `record_payroll_event()` (F2 REMEDIATED).
- [x] Forward-only transitions enforced.
- [x] Claim submission does not consume entitlement.

### B4: FEAT-CLASS-003 — PASS
- [x] Store item CRUD uses `FEATContext("FEAT-CLASS-003")`.
- [x] Insurance policy routes now use `@feat_shell("FEAT-CLASS-003")` (F4 REMEDIATED).
- [x] Persistent student-visible banners via `create_class_announcement()` (F15 REMEDIATED).
- [x] Class-config changes do not mutate entitlement/obligation/ledger tables.

---

## Part C: Route Wiring

Status: **PASS** (with 1 blocking issue in C6)

### C1: Store Dashboard Read Model — PASS
- [x] Canonical read model, entitlement lineage, no GET side effects.

### C2: Store Item Management — PASS
- [x] Create/edit/deactivate use FEAT-CLASS-003.

### C3: Store Purchase and Redemption — PASS
- [x] Purchase calls FEAT-STOR-001.
- [x] Hall-pass path now calls `consume_entitlement` (F13 REMEDIATED).
- [x] Approval writes terminal consumption.
- [x] Rejection preserves entitlement.

### C4: Insurance Marketplace and Purchase — PASS
- [x] Class-scoped offerings.
- [x] FEAT boundary present (F3 REMEDIATED).

### C5: Insurance Claim and Policy Views — PASS
- [x] Student claim submission uses FEAT-STOR-003.
- [x] Teacher claim decision: bare commits removed (F14 REMEDIATED).

### C6: Insurance Policy Management — PASS (with blocking issue)

- [x] All routes use `@feat_shell("FEAT-CLASS-003")` (F4 REMEDIATED).
- [x] Edit creates new prospective version.
- [x] Deactivate hides from new enrollment.
- [x] Delete schedules at entitlement boundary.
- [x] Persistent banners emitted (F15 REMEDIATED).

**Blocking issue:**

| # | Finding | Location | Impact |
|---|---------|----------|--------|
| F7 | Route queries `StoreItem.title.asc()` — `StoreItem` has `name`, not `title` | `admin.py:6668` | `InvalidRequestError` crash on GET for insurance policy editor whenever store items exist. Template was fixed to `item.name` but route ordering was missed. |

---

## Part D: Template Audit

Status: **PASS**

| Template | Result |
|----------|--------|
| `admin_store.html` | PASS (F10 remediated in round 1) |
| `admin_insurance.html` | PASS |
| `admin_edit_insurance_policy.html` | PASS — template uses `item.name` (F7 template side remediated) |
| `student_shop.html` | PASS (F17 remediated in round 1) |
| `student_insurance_marketplace.html` | PASS (F8 REMEDIATED — `incident_date`/`filed_date` refs removed) |
| `student_file_claim.html` | PASS (F9 REMEDIATED — `_DummyField` stubs prevent crash) |
| `student_view_policy.html` | PASS (F8 REMEDIATED) |
| `admin_process_claim.html` | PASS (F18 REMEDIATED — `IdentityProfile.full_name` resolved) |
| `admin_view_student_policy.html` | PASS (F8 REMEDIATED) |

---

## Part E: Completion Criteria

- [x] MAP checklist rows for STORE/insurance are all `REWIRED`.
- [x] Current code matches authority and persistence model in canonical docs (with residual structural debt).
- [x] No stale template row shapes remain on audited surfaces.
- [ ] No direct domain boundary violations — **1 blocking route query crash** (F7 route side).
- [x] All findings documented with exact file, route, and template references.

---

## Full Remediation Tracker

### Remediated (17 of 20)

| # | Finding | Remediated In |
|---|---------|---------------|
| F1 | Claim approval now posts compensatory Ledger credit | Round 2 |
| F2 | Productivity claim type accepted; payroll MANUAL_CREDIT coordinated | Round 2 |
| F3 | `@feat_shell("FEAT-STOR-001")` on `execute_insurance_purchase` | Round 2 |
| F4 | Insurance policy routes wrapped with `@feat_shell("FEAT-CLASS-003")` | Round 2 |
| F5 | `@feat_shell("FEAT-STOR-002")` on `revoke_entitlement` and `expire_entitlement` | Round 2 |
| F6 | Insurance non-revocability guard on revoke path | Round 2 |
| F8 | `incident_date`/`filed_date` references removed from claim templates | Round 2 |
| F9 | `_DummyField` stubs prevent GET crash on claim filing form | Round 2 |
| F10 | `is_from_bundle`/`bundle_remaining` removed from `admin_store.html` | Round 1 |
| F11 | `entitlement_item_id` correctly on `Entitlement` model | Round 1 |
| F12 | `PolicyTransition.created_by` now FK to `users.id` | Round 2 |
| F13 | Hall-pass path now calls `consume_entitlement` | Round 2 |
| F14 | Bare `db.session.commit()` removed from `process_claim` | Round 2 |
| F15 | Persistent student-visible banners via `create_class_announcement()` | Round 1 |
| F16 | Dead orphan `StoreItem()` constructor removed | Round 1 |
| F17 | `uses_remaining`/`bundle_remaining` stubs removed from `student_shop.html` | Round 1 |
| F18 | `IdentityProfile.full_name` used for student display name | Round 2 |

### Still open (3 of 20)

| # | Finding | Severity | Location | Action needed |
|---|---------|----------|----------|---------------|
| F7 | Route queries `StoreItem.title.asc()` — column is `name` | **Blocking** | `admin.py:6668` | Change `.order_by(StoreItem.title.asc(), ...)` to `.order_by(StoreItem.name.asc(), ...)` |
| F19 | `RedemptionEvent` keys off `purchase_id` not `entitlement_id` | Low | `models.py:905` | Structural debt — design decision deferred |
| F20 | `PolicyVersion.is_active` mutable; `economy_rebalance.py:424` mutates existing version rows | Low | `models.py:1740`, `economy_rebalance.py:424` | Structural debt — immutability enforcement deferred |

---

## Conclusion

The audit is conditionally failing on 1 blocking issue: `admin.py:6668` queries `StoreItem.title` which does not exist (the column is `name`), causing the insurance policy editor GET to crash with `InvalidRequestError` whenever store items exist. This is a one-line fix.

The 2 remaining low-severity findings (F19, F20) are structural debt that do not cause runtime failures and can be deferred to a future migration wave.

**To achieve AUDIT PASS:** fix `StoreItem.title` → `StoreItem.name` at `admin.py:6668`.
