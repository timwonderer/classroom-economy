# Store & Entitlements Domain Rewire — Handoff Note

**Date:** 2026-07-22  
**Branch:** `codex/v2.0`  
**Governing docs:** DOM-STORE-001 v3.0, FEAT-STOR-001 v2.0, FEAT-STOR-002 v1.0, FEAT-STOR-003 v1.0  
**Process:** SOP-DEV-002 (Canonical Domain Reconstruction Workflow)  
**Nothing is committed.** All changes are unstaged working-tree modifications.

---

## What Is This Work

A complete rewiring of the Store and Entitlements domain from v1/v2 legacy (StorePurchase/RedemptionEvent as authority, mutable counters, `uses_remaining`/`bundle_remaining`) to v3 canonical architecture (atomic `entitlements` table, `entitlement_consumptions` for Store-owned terminal events, `insurance_claims` for claim workflow). The guiding principle is: **docs are authority, code is the thing being fixed.**

---

## What Is Done

### 1. DOM-STORE-001 updated to v3.0
- File: `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md`
- Added §XII Canonical Terminology (in prior session), then full v3.0 rewrite with 3-table schema (`entitlements`, `entitlement_consumptions`, `insurance_claims`), primitive operations, 21 canonical invariants, reconstruction disposition of v2.2 tables

### 2. MAP-UI-001 updated with Store & Entitlements slice
- File: `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md`
- 16 NEEDS_REWIRE capability rows, 13 resolved decisions, 9 issue groups

### 3. Models aligned to v3.0 canonical schema
- File: `app/models.py` (lines ~940-1052)
- **`Entitlement`** (table: `entitlements`) — replaces `EntitlementGrant`/`entitlement_grants`. Fields: `entitlement_id`, `entitlement_item_id`, `target_seat_id`, `actor_seat_id`, `class_id`, `grant_type` (PURCHASE/MANUAL_GRANT/OBLIGATION), `correlation_id`, `granted_at`. No `purchase_id` (correlation is sufficient).
- **`EntitlementConsumption`** (table: `entitlement_consumptions`) — fields: `consumption_id`, `entitlement_id` (FK to `entitlements.entitlement_id`), `class_id`, `target_seat_id`, `actor_seat_id`, `disposition` (CONSUMED/EXPIRED/REVOKED), `correlation_id`, `timestamp`. No `notes`.
- **`InsuranceClaim`** (table: `insurance_claims`) — fields: `claim_id`, `class_id`, `entitlement_id` (FK to `entitlements.entitlement_id`), `target_seat_id`, `actor_seat_id`, `transaction_id`, `claimed_dates`, `status`, `submitted_at`, `decided_at`, `decided_by_seat_id`, `correlation_id`. No `claim_type` (resolvable from config chain), no `claim_basis`, no `decision_notes`.
- **Removed:** `InsuranceClaimType` enum (dropped from schema per §VII.C)
- **Dropped from StorePurchase** (in prior migration): `uses_remaining`, `bundle_remaining`, `is_from_bundle`
- **RedemptionEventAction** enum values uppercased: REQUEST, APPROVED, REJECTED

### 4. Two migrations created and tested
- **`1761e2187234`** — Creates `entitlement_grants`, `entitlement_consumptions`, `insurance_claims`; drops StorePurchase mutable columns; uppercases RedemptionEventAction enum; drops legacy tables (`student_items`, `store_item_blocks`, `redemption_audit_logs`)
- **`a3f2c8d91b47`** — Aligns to v3.0: renames `entitlement_grants` → `entitlements`, drops `purchase_id`, renames columns across all three tables, adds `target_seat_id` to consumptions, adds `actor_seat_id` to claims, adds proper FKs to `entitlements.entitlement_id`, drops `claim_type`/`claim_basis`/`decision_notes`/`notes`, drops `insurance_claim_type_enum`
- Both tested: upgrade ✅, downgrade ✅, re-upgrade ✅, single head at `a3f2c8d91b47`

### 5. Canonical domain primitives written
- **New file:** `app/services/store_entitlement_service.py`
- Grant primitives: `grant_entitlement()`, `grant_entitlements_bulk()`
- Terminal lifecycle: `consume_entitlement()`, `revoke_entitlement()`, `expire_entitlement()`
- Query primitives: `get_entitlement()`, `list_entitlements_for_seat()`, `list_available_entitlements()`, `get_entitlement_balance()`, `is_entitlement_available()`, `list_entitlement_history()`
- Insurance: `submit_insurance_claim()`, `approve_insurance_claim()`, `reject_insurance_claim()`, `get_insurance_claim()`, `list_insurance_claims()`
- All time via `canonical_temporal_resolver` — **`app/utils/time.py` is deprecated, never import from it**

### 6. FEAT_REGISTRY updated
- File: `app/feats/base.py` (lines ~102-118)
- FEAT-STOR-001: "Store Purchase and Entitlement Grant"
- FEAT-STOR-002: "Entitlement Terminal Lifecycle"
- FEAT-STOR-003: "Insurance Claim Lifecycle"
- Bridge aliases for FEAT-STOR-004/005/006 and FEAT-ENT-001 (marked `[RETIRED →]` so existing call-sites don't crash)
- Auto-key generation at line ~434 remapped from `FEAT-STOR-002` → `FEAT-STOR-001`

### 7. FEAT-STOR-001 rewritten
- File: `app/feats/store_purchase_feat.py` — **fully rewritten**
- `execute_store_purchase()` — canonical purchase: Ledger execution → N atomic `grant_entitlement()` calls → optional instant-use `consume_entitlement()` → inventory decrement
- `execute_manual_grant()` — teacher-initiated MANUAL_GRANT
- `execute_obligation_grant()` — obligation lifecycle OBLIGATION grant
- Result type: `StorePurchaseResult` with `correlation_id`, `entitlement_ids`, `ledger_transaction_id`, `success_message`
- **Breaking change:** Old `StorePurchaseResult` had `purchase_ids` and `hall_pass_balance`; new one has `entitlement_ids` and `correlation_id`. Old `execute_rent_perk_purchase()` is removed.

### 8. Enum fix propagated
- `app/feats/redemption_disposition_feat.py` — action strings uppercased (APPROVED/REJECTED)
- `app/routes/api.py` — action map uppercased (REQUEST/APPROVED/REJECTED)
- `tests/dom/entitlement/test_store.py` — schema assertion updated (removed dropped columns)

---

## What Is NOT Done (Remaining Work)

### Current Blocker: Insurance policy editing has no canonical contract

The current store/entitlement rewiring can move forward on the purchase, redemption, and claim flows, but it cannot truthfully complete the insurance policy editor surface yet.

What is missing:
- A FEAT-layer specification for the insurance policy management/editor flow
- A canonical form contract for `admin_edit_insurance_policy.html`
- A domain-approved authoritative field list for insurance policy create/update
- A route-level owner for policy editing that defines validation and persistence rules

What needs to be clarified:
- Is insurance policy editing in scope for this slice, or should it remain read-only for now?
- If it is in scope, which doc is authoritative for:
  - editable fields
  - create vs update semantics
  - activation/deactivation behavior
  - autopay, cancellation, waiting-period, and claim-limit rules
  - bundle/tier configuration
- Whether the admin insurance page should be a real CRUD surface or only a management/read-only view

Why this blocks progress:
- The template already expects a large form surface, but there is no canonical backing contract in the form layer or FEAT docs.
- Implementing the editor without that contract would invent behavior, which violates the docs-first rule for this repository.

Decision required:
1. Provide the authoritative insurance policy editor spec and form contract, then continue implementation.
2. Explicitly exclude insurance policy editing from this handoff slice and treat the admin page as read-only until a later domain spec exists.

### Current Blocker: Insurance claims still need an entitlement-backed purchase path

The student-facing insurance claim surface is now aligned to the claim FEAT contract and policy-version reads, but the current runtime still does not create a canonical insurance entitlement on purchase.

What is missing:
- A lawful insurance purchase path that produces an `entitlements` row for the purchased coverage
- A stable mapping from insurance policy lineage/version to the entitlement item that claim submission will reference
- A completed student claim submission handler that can submit against that entitlement and preserve the coverage boundary rules

Why this blocks end-to-end completion:
- `FEAT-STOR-003` requires `insurance_claims.entitlement_id`
- The current purchase path still records insurance as an `ObligationAssessment` instead of an entitlement grant
- Without that entitlement record, claim submission cannot be completed honestly without inventing a cross-domain shortcut

Decision required:
1. Authorize the insurance purchase path to create the canonical entitlement record needed for claim submission, then finish the student claim flow.
2. Or explicitly defer insurance claim submission from this rewire slice and keep the student claim page read-only until the entitlement-backed purchase contract is written.

### A. Rewrite `app/feats/redemption_disposition_feat.py` as FEAT-STOR-002

**Current state:** Still references old v1 patterns — `StorePurchase.status` mutation, `RedemptionEvent` creation, `utc_now()` from deprecated `app/utils/time.py`, refund via `store_purchase_refund_key`. Decorated as `@requires_feat_context("FEAT-STOR-006")`.

**Target:** Per FEAT-STOR-002 v1.0 (`docs/FEATURE-EXECUTION/FEAT-STOR-002_ENTITLEMENT_TERMINAL_LIFECYCLE.md`):
- Should orchestrate `consume_entitlement()`, `expire_entitlement()`, `revoke_entitlement()` from `app/services/store_entitlement_service.py`
- Provenance-aware revocation rules (§VII): MANUAL_GRANT = teacher can revoke; PURCHASE = only via coordinated Ledger reversal; OBLIGATION = prohibited; Insurance = prohibited
- Cross-domain consumption (hall passes) is NOT handled here — that's Productivity domain
- Instant-use coordination with FEAT-STOR-001 (§VIII)
- All time through `canonical_temporal_resolver`, never `app/utils/time.py`
- Decorate as `@requires_feat_context("FEAT-STOR-002")`

**Key design questions:**
- The existing `record_live_redemption_event()` function is called from `app/routes/api.py:230` for the student redemption request flow. Under v3, a "redemption request" is not a Store terminal event — it's a workflow concern. Decide whether to keep `RedemptionEvent` as a bridge workflow table or introduce a new mechanism.
- The existing approval path mutates `StorePurchase.status` to `"completed"` — under v3, `StorePurchase` is superseded (§XIX). The approval should write `CONSUMED` to `entitlement_consumptions` instead.
- The existing rejection path issues a Ledger refund and sets `StorePurchase.status = "rejected"` — under v3, rejection of a redemption request does NOT terminate the entitlement (the student keeps it). Only if the teacher is doing a coordinated revocation+refund should `REVOKED` be written.

### B. Write FEAT-STOR-003 implementation (insurance claim lifecycle)

**No file exists yet.** Needs a new file, e.g. `app/feats/insurance_claim_feat.py`.

Per FEAT-STOR-003 v1.0 (`docs/FEATURE-EXECUTION/FEAT-STOR-003_INSURANCE_CLAIM_LIFECYCLE.md`):
- `execute_claim_submission()` — validates insurance entitlement, coverage window, claim allowance, basis; calls `submit_insurance_claim()`
- `execute_claim_approval()` — type-specific downstream: TRANSACTION → Ledger compensatory credit; PRODUCTIVITY → Payroll MANUAL_CREDIT; NON_MONETARY → no downstream mutation
- `execute_claim_rejection()` — calls `reject_insurance_claim()`, no Ledger/Payroll effect
- Insurance type is resolved through `entitlement_id → entitlement_item_id → Class Configuration`, NOT stored on the claim

### C. Fix route callers (`app/routes/api.py`)

The following call-sites will break because the old function signatures changed:

1. **Line 59:** `from app.feats.store_purchase_feat import execute_rent_perk_purchase, execute_store_purchase` — `execute_rent_perk_purchase` no longer exists
2. **Line 521:** `result = execute_rent_perk_purchase(...)` — needs rewrite. Rent perk purchase under v3 is an ordinary `execute_store_purchase()` with `total_price=Decimal('0.00')`
3. **Line 651:** `result = execute_store_purchase(...)` — signature changed. Old params `uses_remaining`, `purchase_status`, `expiry_date` are gone. New params: `is_instant_use`. Result type changed: `result.purchase_ids` → `result.entitlement_ids`, `result.transaction_id` → `result.ledger_transaction_id`
4. **Lines 867, 918:** `execute_redemption_approval()`/`execute_redemption_rejection()` — still work for now but use `FEAT-STOR-006` bridge alias. Should be remapped when FEAT-STOR-002 is rewritten.
5. **Line 230:** `record_live_redemption_event()` — still works but uses deprecated `utc_now()` internally

### D. Fix other route callers

Run `grep -rn "execute_store_purchase\|execute_rent_perk_purchase\|uses_remaining\|bundle_remaining\|is_from_bundle" --include="*.py" | grep -v __pycache__ | grep -v migrations/` to find all remaining references to dropped concepts.

Key files likely affected:
- `app/routes/admin.py` — hall pass entitlement adjustment uses `FEAT-ENT-001` (retired)
- `app/routes/student.py` — shop route references `uses_remaining`
- `app/services/store_service.py` — heavy references to dropped columns

### E. Template rewiring

Use the template audit docs in `docs/TRACKING/` as source-of-truth checklists. Each Store-related template surface is classified as REWIRE, REMOVE, COLLAPSE, VERIFY, or BLOCKED in MAP-UI-001.

### F. Tests

- Update/add tests for FEAT-STOR-001 (the new `execute_store_purchase` creates entitlement rows, not StorePurchase rows)
- Add tests for FEAT-STOR-002 (consume, expire, revoke with provenance rules)
- Add tests for FEAT-STOR-003 (insurance claim lifecycle)
- Existing test at `tests/dom/entitlement/test_store.py` has schema assertions that were updated but behavioral tests still use old `store_service.record_standard_purchase_items()` — need rewrite to use FEAT-STOR-001

---

## Critical Rules for the Next Agent

1. **Docs are authority, code is the thing being fixed.** If there's a misalignment, the code is wrong.
2. **`app/utils/time.py` is deprecated.** All time resolution goes through `canonical_temporal_resolver` from `app/utils/canonical_temporal_resolver.py`.
3. **Hall passes are Productivity domain (DOM-PROD-001).** The `EntitlementEvent` table and `app/services/entitlement_service.py` are Productivity mechanisms. Store domain does NOT own hall pass consumption.
4. **All mutations go through FEATs.** No direct `db.session.add/commit` in routes. Use `app/feats/base.py` decorators.
5. **Canonical context must be resolved before FEAT entry.** Use `resolve_canonical_context()` from `app/services/context_resolver.py`. The FEAT receives `CanonicalContext` with `user_id`, `class_id`, `seat_id`, `actor_role`.
6. **`store_purchases` and `redemption_events` are superseded** (DOM-STORE-001 §XIX). They still exist in the database as bridge tables but are not canonical Store truth. Don't add new dependencies on them.
7. **Insurance claim type is NOT stored on the claim.** It's resolved through `entitlement_id → Entitlement.entitlement_item_id → StoreItem (Class Configuration)`.
8. **Rejection of a redemption request does NOT terminate the entitlement.** The student keeps it. Only coordinated revocation+refund creates a REVOKED terminal event.
9. **Branch is `codex/v2.0`.** All work merges here, never to `main`.

---

## File Inventory

### New files (untracked)
| File | Purpose |
|------|---------|
| `app/services/store_entitlement_service.py` | Canonical domain primitives for all 3 tables |
| `migrations/versions/1761e2187234_*.py` | Migration: create 3 tables, drop legacy columns/tables |
| `migrations/versions/a3f2c8d91b47_*.py` | Migration: align to v3.0 (renames, FK additions, column drops) |

### Modified files (unstaged)
| File | What changed |
|------|-------------|
| `app/models.py` | `Entitlement`, `EntitlementConsumption`, `InsuranceClaim` models (v3.0); removed `InsuranceClaimType` enum |
| `app/feats/base.py` | FEAT_REGISTRY canonical labels + bridge aliases; auto-key remap |
| `app/feats/store_purchase_feat.py` | **Fully rewritten** as FEAT-STOR-001 |
| `app/feats/redemption_disposition_feat.py` | Enum values uppercased only (still needs full rewrite as FEAT-STOR-002) |
| `app/routes/api.py` | Enum values uppercased (action map) |
| `tests/dom/entitlement/test_store.py` | Removed dropped columns from schema assertion |

### Key reference docs
| Doc | Version | Purpose |
|-----|---------|---------|
| `docs/DOMAIN/DOM-STORE-001_STORE_AND_ENTITLEMENTS_DOMAIN.md` | v3.0 | **Schema and domain authority** |
| `docs/FEATURE-EXECUTION/FEAT-STOR-001_STORE_PURCHASE.md` | v2.0 | Purchase + grant orchestration |
| `docs/FEATURE-EXECUTION/FEAT-STOR-002_ENTITLEMENT_TERMINAL_LIFECYCLE.md` | v1.0 | Consume/expire/revoke orchestration |
| `docs/FEATURE-EXECUTION/FEAT-STOR-003_INSURANCE_CLAIM_LIFECYCLE.md` | v1.0 | Insurance claim lifecycle |
| `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md` | v0.2 | Template surface inventory |

---

## Recommended Next Steps (in order)

1. **Rewrite `app/feats/redemption_disposition_feat.py`** as FEAT-STOR-002 using the primitives in `store_entitlement_service.py`. This is the most impactful remaining piece.
2. **Create `app/feats/insurance_claim_feat.py`** as FEAT-STOR-003.
3. **Fix `app/routes/api.py`** callers — the import of `execute_rent_perk_purchase` will crash at module load time.
4. **Fix remaining broken references** to dropped columns across `store_service.py`, `api.py`, `student.py`, `admin.py`.
5. **Rewrite tests** to validate the new FEAT paths.
6. **Template rewiring** using audit docs as checklist.
