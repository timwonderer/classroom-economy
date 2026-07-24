# STORE Domain End-to-End Audit Report

| Reference | Version | Date | Authority | Reviewer |
|-----------|---------|------|-----------|----------|
| AUDIT-STORE-001 | 2.0 | 2026-07-23 | QA/Review | Claude Opus 4.6 |

---

## Result

**AUDIT FAIL**

Re-audit conducted after partial remediation. 5 of 20 original findings were remediated. 15 remain open, including 6 critical findings. The MAP checklist marks all STORE rows as `REWIRED`, but the underlying code does not yet satisfy the contracts declared in those MAP rows.

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

Status: **PASS with concerns**

### A1: Canonical Store/Entitlement Tables

- [x] `entitlements` — PASS. Append-only grant history at `models.py:948`. No mutable balance columns.
- [x] `entitlement_consumptions` — PASS. Append-only terminal lifecycle at `models.py:981`. Unique constraint enforces one terminal event per entitlement per disposition.
- [x] `insurance_claims` — PASS. Mutable claim workflow at `models.py:1013`.
- [x] No `uses_remaining` / `bundle_remaining` anywhere — PASS.
- [x] No purchase quantity as entitlement truth — PASS.
- [x] No direct Store ownership of class configuration — PASS.
- [x] No direct Ledger ownership leaks — PASS. `InsuranceClaim.transaction_id` is nullable cross-domain correlation (acceptable per INV-ARC-021).

### A2: Insurance Policy Configuration Tables

- [x] `policy_versions` — PASS. At `models.py:1722`.
- [x] `policy_transitions` — PASS. At `models.py:1753`.
- [x] Versioned terms in `policy_payload_json` — PASS.

### A-CONCERNS (open)

| # | Finding | Location | Severity |
|---|---------|----------|----------|
| F12 | `PolicyTransition.created_by` bare integer, no FK to `users` or `seats` | `models.py:1771` | Medium |
| F19 | `RedemptionEvent` keys off `purchase_id` (FK→`store_purchases`) not `entitlement_id` | `models.py:905` | Low |
| F20 | `PolicyVersion.is_active` mutable boolean on immutable version row | `models.py:1740` | Low |

---

## Part B: FEAT Layer

Status: **FAIL**

### B1: FEAT-STOR-001 (Store Purchase) — PASS

- [x] One entitlement row per unit via loop — PASS.
- [x] Quantity not persisted as balance — PASS.
- [x] Ledger through lawful boundary — PASS.

### B2: FEAT-STOR-002 (Entitlement Terminal Lifecycle) — FAIL

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| F5 | EXPIRED and REVOKED have FEAT gate | **STILL OPEN** | `expire_entitlement` and `revoke_entitlement` in `store_entitlement_service.py:176,195` are plain service functions with no `@requires_feat_context` |
| F6 | Insurance non-revocability guard | **STILL OPEN** | `revoke_entitlement` has no check for insurance grant type |

### B3: FEAT-STOR-003 (Insurance Claim Lifecycle) — FAIL

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| F1 | Transaction claim approval posts Ledger credit | **STILL OPEN** | `execute_claim_approval` (`insurance_claim_feat.py:90-92`) branches on claim type but only changes message string — no ledger credit call |
| F2 | Productivity claim routes MANUAL_CREDIT via Payroll | **STILL OPEN** | `_resolve_claim_type` (line 42) rejects productivity type with `InsuranceClaimError("INVALID_CLAIM_TYPE")` — the type doesn't even reach approval |

### B4: FEAT-CLASS-003 (Insurance Policy Management) — PARTIAL

- [x] Store item CRUD correctly uses `FEATContext("FEAT-CLASS-003")` — PASS.
- [x] Policy changes emit persistent student-visible banners — **REMEDIATED** (F15). `create_class_announcement()` called at `admin.py:6713-6724, 6767-6774`.
- [ ] Insurance policy routes use FEAT-CLASS-003 — **STILL OPEN** (F4). See Part C.

---

## Part C: Route Wiring

Status: **FAIL**

### C1: Store Dashboard Read Model — PASS

- [x] Canonical read model, entitlement lineage, no GET side effects — all PASS.

### C2: Store Item Management — PASS

- [x] Create/edit/deactivate use FEAT-CLASS-003 — PASS.
- [x] Dead orphan constructor removed — **REMEDIATED** (F16).

### C3: Store Purchase and Redemption — PARTIAL FAIL

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| — | Purchase calls FEAT-STOR-001 | PASS | `@feat_shell("FEAT-STOR-001")` on `api.purchase_item` |
| — | Approval writes terminal consumption | PASS | `execute_redemption_approval` → `consume_entitlement` |
| — | Rejection preserves entitlement | PASS | No terminal event on rejection |
| F13 | Hall-pass early-exit bypasses `consume_entitlement` | **STILL OPEN** | `api.py:714-718` sets `student_item.status = 'redeemed'` directly without writing `EntitlementConsumption` |

### C4: Insurance Marketplace and Purchase — FAIL

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| F3 | Insurance purchase has FEAT boundary | **STILL OPEN** | `student.purchase_insurance` has no `@feat_shell`; `execute_insurance_purchase` has no `@requires_feat_context` |

### C5: Insurance Claim and Policy Views — PARTIAL FAIL

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| — | Student claim submission uses FEAT-STOR-003 | PASS | Via `@requires_feat_context` on function |
| F14 | Teacher claim decision has bare `db.session.commit()` | **STILL OPEN** | `admin.py:6935, 6943` commit outside FEAT boundary |

### C6: Insurance Policy Management — PARTIAL

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| F4 | Insurance policy routes use FEAT-CLASS-003 | **STILL OPEN** | `edit_insurance_policy` (6657), `deactivate_insurance_policy` (6750), `delete_insurance_policy` (6783) all bypass FEAT — bare `db.session.commit()` |
| — | Edit creates new prospective version | PASS | Calls `create_policy_version()` |
| — | Deactivate hides from new enrollment | PASS | |
| — | Delete schedules at entitlement boundary | PASS | `schedule_policy_deletion()` with coverage boundary |
| F15 | Persistent student-visible banners | **REMEDIATED** | `create_class_announcement()` now called |

---

## Part D: Template Audit

Status: **FAIL**

| Template | Result | Evidence |
|----------|--------|----------|
| `admin_store.html` | **PASS** | F10 REMEDIATED — `is_from_bundle`/`bundle_remaining` removed |
| `admin_insurance.html` | PASS | No retired fields |
| `admin_edit_insurance_policy.html` | **FAIL** (F7) | Line 46: `item.title` — `StoreItem` has `name` not `title`. Silently renders blank |
| `student_shop.html` | **PASS** | F17 REMEDIATED — `uses_remaining`/`bundle_remaining` stubs removed |
| `student_insurance_marketplace.html` | **FAIL** (F8) | Lines 472, 519: `claim.incident_date.strftime()` — field doesn't exist on `InsuranceClaim`; crashes when claims exist |
| `student_file_claim.html` | **FAIL** (F9) | Lines 51-52: `form.transaction_id.label()` on stub `SimpleNamespace` — GET render crashes |
| `student_view_policy.html` | **FAIL** (F8) | Lines 119, 157: `claim.incident_date.strftime()` / `claim.filed_date.strftime()` — crashes when claims exist |
| `admin_process_claim.html` | **FAIL** (F18) | Line 32: `claim.student.full_name` renders seat `public_id` (UUID) instead of display name |
| `admin_view_student_policy.html` | **FAIL** (F8) | Line 117: `claim.incident_date.strftime()` — crashes when claims exist |

---

## Part E: Completion Criteria

- [x] MAP checklist rows for STORE/insurance are all `REWIRED` — PASS (map-level).
- [ ] Current code matches authority and persistence model — **FAIL**. 15 open findings.
- [ ] No stale template row shapes — **FAIL**. 5 of 9 templates fail.
- [ ] No domain boundary violations — **FAIL**. Insurance routes bypass FEAT; claim compensation not wired.
- [x] All findings documented with file/route/template references — PASS.

---

## Remediation Tracker

### Remediated since v1.0 audit (5)

| # | Finding | Status |
|---|---------|--------|
| F10 | `admin_store.html` `is_from_bundle`/`bundle_remaining` on `StorePurchase` | REMEDIATED |
| F11 | `entitlement_item_id` not on policy tables (was misidentified — belongs on `Entitlement`, not policy) | REMEDIATED |
| F15 | Policy changes emit only `flash()` — no persistent banners | REMEDIATED |
| F16 | Dead orphan `StoreItem()` constructor | REMEDIATED |
| F17 | `student_shop.html` stubbed `uses_remaining`/`bundle_remaining` | REMEDIATED |

### Still open (15)

#### Critical (6) — domain contract violations

| # | Finding | Location | Contract |
|---|---------|----------|----------|
| F1 | Claim approval posts no compensatory Ledger credit | `insurance_claim_feat.py:90-92` | FEAT-STOR-003 §IV.B |
| F2 | Productivity claim type rejected before reaching approval | `insurance_claim_feat.py:42` | FEAT-STOR-003 §IV.C |
| F3 | Insurance purchase has no FEAT boundary | `student.py:1597`, `insurance_purchase_feat.py:24` | FEAT-STOR-001 |
| F4 | Insurance policy routes bypass FEAT-CLASS-003 | `admin.py:6657, 6750, 6783` | FEAT-CLASS-003 |
| F5 | EXPIRED/REVOKED dispositions have no FEAT gate | `store_entitlement_service.py:176, 195` | FEAT-STOR-002 |
| F6 | No insurance non-revocability guard | `store_entitlement_service.py:176` | DOM-STORE-001 §VII.D |

#### High (4) — template crashes

| # | Finding | Location |
|---|---------|----------|
| F7 | `item.title` on `StoreItem` (has `name`) — blank render | `admin_edit_insurance_policy.html:46` |
| F8 | `claim.incident_date.strftime()` — crashes when claims exist | `student_insurance_marketplace.html:472`, `student_view_policy.html:119`, `admin_view_student_policy.html:117` |
| F9 | `form.transaction_id` on stub SimpleNamespace — GET crashes | `student_file_claim.html:51` |
| F18 | `claim.student.full_name` renders UUID instead of name | `admin_process_claim.html:32` |

#### Medium (3) — contract gaps

| # | Finding | Location |
|---|---------|----------|
| F12 | `PolicyTransition.created_by` bare integer, no FK | `models.py:1771` |
| F13 | Hall-pass early-exit bypasses `consume_entitlement` | `api.py:714-718` |
| F14 | Bare `db.session.commit()` in `process_claim` outside FEAT | `admin.py:6935, 6943` |

#### Low (2) — structural debt

| # | Finding | Location |
|---|---------|----------|
| F19 | `RedemptionEvent` keys off `purchase_id` not `entitlement_id` | `models.py:905` |
| F20 | `PolicyVersion.is_active` mutable on immutable row | `models.py:1740` |

---

## Conclusion

The audit does not pass. While 5 findings were remediated (store template cleanup, persistent banners, dead code removal), the 6 critical findings (F1–F6) and 4 high-severity template crashes (F7–F9, F18) remain open.

The MAP rows report `REWIRED` status, but the code behind those rows does not yet implement the contracts the MAP rows describe. The MAP should either be corrected to reflect the actual implementation state, or the code should be brought to match the declared contracts.

### Required for AUDIT PASS

1. Remediate F1–F6 (critical FEAT/domain contract violations)
2. Remediate F7–F9, F18 (template crashes on existing model shapes)
3. Re-run this audit checklist
