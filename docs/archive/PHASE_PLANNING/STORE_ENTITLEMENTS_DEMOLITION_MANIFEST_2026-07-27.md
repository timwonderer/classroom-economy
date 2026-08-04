# Store and Entitlements Phase 2 Demolition Manifest
## Re-Audited Against Current Constitutional Authority (2026-07-27)

**Authority:** DOM-STORE-001 v4.0, FEAT-STOR-001 v3.0, FEAT-STOR-002 v2.0, FEAT-STOR-003 v2.0, FEAT-STOR-004 v1.0, SPEC-TIME-001

**Key Audit Finding:** This re-audit discovered that **mandatory canonical tool requirement** (context resolver, temporal resolver, display metadata resolver) supersedes prior demolition classifications. Any code using non-canonical temporal, identity, or display utilities must be deleted and rewritten, regardless of whether it appears "functional" in isolation.

**Current Schema State (Phase 2 Complete):**
- ✓ `entitlement_events` table created (append-only canonical)
- ✓ `pending_actions` table created (unresolved entitlement actions)
- ✓ Old models deleted: Entitlement, EntitlementConsumption, StorePurchase, RedemptionEvent, InsuranceClaim, etc.
- ✓ Imports cleaned in routes and most services

**Demolition Scope:**
- Keep: canonical schema, constitutional docs, Class Configuration domain routes
- Rewrite: all old FEATs and service entry points to use new schema per v4.0 specifications AND canonical tools (temporal resolver, context resolver, display metadata)
- Delete: old FEAT implementations that reference deleted models; old test files already skipped; utility files using non-canonical tools
- Stub: routes until corresponding Phase 3 FEATs are ready
- **Enforce:** New implementations MUST use canonical temporal, identity, and display tools exclusively (non-negotiable architectural requirement)

---

## I. FEAT-Layer Rewrite Inventory

### A. FEAT-STOR-001: Store Purchase and Entitlement Grant

**Current File:** `app/feats/store_purchase_feat.py` (v2.0, broken bridge)

**Current State:**
- Calls deleted `grant_entitlement()` from `store_entitlement_service`
- Calls deleted `consume_entitlement()` for instant-use
- Uses old `grant_type="PURCHASE"` terminology (should be `acquisition_type`)
- Still imports deleted models (commented in imports)
- Has TODO comments for Phase 3-4 migration

**Constitutional Requirement (v3.0):**
- Must write `EntitlementEvent` rows directly with canonical schema
- Must create one row per unit with `acquisition_type=PURCHASE`, `event_type=GRANTED`
- Must use new `entitlement_type`, `event_type`, `acquisition_type` enums
- Must write `payload` JSON with type-specific canonical facts only (no monetary truth)
- For instant-use products: create `GRANTED` and immediately create `CONSUMED` in same transaction
- Must never persist quantity, remaining_uses, or mutable status

**Classification:** **COMPLETE REWRITE REQUIRED**

**Action:** Delete old file; create new `FEAT-STOR-001` v3.0 implementation that:
1. Validates canonical context and product eligibility
2. Resolves Ledger purchase through `FEAT-LED-*` 
3. Writes `EntitlementEvent` rows (one per unit) via direct schema access
4. Coordinates instant-use consumption if applicable
5. Handles perk grants when upstream authority established it

---

### B. FEAT-STOR-002: Entitlement Lifecycle Transition

**Current File:** `app/feats/redemption_disposition_feat.py` (version unknown, broken bridge)

**Current State:**
- References deleted `RedemptionEvent`, `EntitlementConsumption`, `Entitlement` models
- Unclear lifecycle handling (approval/rejection logic)
- May implement old "reject refunds" pattern (prohibited by v4.0)

**Constitutional Requirement (v2.0):**
- Must handle Store-owned `CONSUMED`, `EXPIRED`, `REVOKED` events only
- Must NOT create duplicate entries when cross-domain event exists (e.g., hall-pass)
- Rejection of delayed-use item: write `REVOKED` (not `CONSUMED`), preserve entitlement unless refund path exists
- Revocation rules: direct grants revocable by teacher while unused; purchased items require Ledger reversal; insurance non-revocable
- Must write immutable `EntitlementEvent` rows only, never mutate grant row
- Cross-domain consumption: other domain writes authoritative event; Store derives entitlement no longer available

**Classification:** **COMPLETE REWRITE REQUIRED**

**Action:** Delete old file; create new `FEAT-STOR-002` v2.0 implementation that:
1. Validates entitlement state and authorization
2. Writes terminal events (`CONSUMED`, `EXPIRED`, `REVOKED`) via direct schema
3. Handles cross-domain consumption (e.g., hall-pass no duplicate)
4. Enforces revocation rules by acquisition_type
5. Never mutates original grant row

---

### C. FEAT-STOR-003: Insurance Claim Lifecycle

**Current File:** `app/feats/insurance_claim_feat.py` (version unknown, broken bridge)

**Current State:**
- References deleted `InsuranceClaim`, `EntitlementConsumption` models
- Unclear if implements `pending_actions` pattern
- Likely missing proper separation of submission vs. decision phases

**Constitutional Requirement (v2.0):**
- Submission phase: create `PendingAction` row, `authoritative_feat=FEAT-STOR-003`, payload with claim subject (transaction_id or dates)
- Submission: structural validation prevents `PendingAction` creation; policy ineligibility recorded on pending action
- Decision phase: revalidate, calculate compensation, coordinate Ledger credit via `FEAT-LED-*`, write `EntitlementEvent` with `event_type=CONSUMED` and claim outcome in payload, delete `PendingAction`
- Both accepted and rejected claims write `CONSUMED` events (payload distinguishes outcome)
- Rejection: no Ledger/Payroll effect unless policy requires refund
- Claim allowance: derived from policy + history, never persisted as `claims_remaining`
- Coverage expiration: FEAT-STOR-002 handles (not this FEAT)

**Classification:** **COMPLETE REWRITE REQUIRED**

**Action:** Delete old file; create new `FEAT-STOR-003` v2.0 implementation that:
1. Submission: validate entitlement + claim subject, create `PendingAction`
2. Adjudication: read `PendingAction`, make decision, write `EntitlementEvent`, coordinate compensation (Ledger/Payroll), delete `PendingAction`
3. Write `CONSUMED` events for both accepted and rejected claims
4. Never persist claim allowance counters

---

### D. FEAT-STOR-004: Direct Entitlement Grant (NOT YET WRITTEN)

**Current File:** None exists; old insurance_purchase_feat.py is incomplete bridge

**Constitutional Requirement (v1.0):**
- Teacher direct grants of entitlements (hall-passes, privileges, etc.)
- Write `EntitlementEvent` with `acquisition_type=GRANT`, `event_type=GRANTED`
- One row per unit granted
- Validate teacher authority and product direct-grantability
- For hall-pass grants: don't create balance row, don't use productivity records as source

**Classification:** **MUST CREATE NEW**

**Action:** Create new `app/feats/direct_entitlement_grant_feat.py` implementing FEAT-STOR-004 v1.0:
1. Validate teacher context and product policy
2. Write `EntitlementEvent` rows (one per unit) via direct schema
3. Handle hall-pass and privilege types specifically
4. Implement idempotency via idempotency_key

---

## II. Service-Layer Rewrite Inventory

### A. `app/services/store_entitlement_service.py`

**Current State:**
- Likely contains obsolete `grant_entitlement()`, `consume_entitlement()` entry points
- Likely mixes Store and Entitlements orchestration (per name)
- Not used after Phase 2 (FEATs had import errors)

**Constitutional Authority:** Do not own this domain service; FEATs own mutation

**Classification:** **DELETE ENTIRE FILE**

**Action:** Delete; all orchestration moves to rewritten FEATs

---

### B. `app/services/entitlement_service.py`

**Current State:**
- Imports partially cleaned in Phase 2 (removed old model imports)
- Likely contains `grant_hall_passes()`, `remove_hall_passes()` entry points
- These entry points call deleted model queries (need rewrite)

**Constitutional Authority:** Can provide read utilities (e.g., derive hall-pass balance); cannot own mutation

**Classification:** **STRIP AND REWRITE SELECTIVE FUNCTIONS**

**Action:**
1. Delete functions: `grant_hall_passes()`, `remove_hall_passes()` (move to FEAT-STOR-004)
2. Keep/rewrite: `get_hall_pass_balance()` to read from `entitlement_events` instead of old model
3. Add read-only utilities: `get_entitlement_balance()`, `is_entitlement_exercisable()`, `has_unconsumed_entitlements()` (derive from EntitlementEvent history)

---

### C. `app/services/store_service.py`

**Current State:**
- Contains catalog read logic: `get_store_items()`, `get_visibility_for_student()`
- Imports cleaned in Phase 2 (removed old model imports)
- Also contains `decrement_inventory()` (likely Class Configuration concern)

**Constitutional Authority:** Store doesn't own class configuration; Store may read catalog definitions

**Classification:** **KEEP CATALOG READS; MOVE INVENTORY LOGIC TO CLASS CONFIGURATION**

**Action:**
1. Keep: `get_store_items()`, `get_visibility_for_student()` and other read-only catalog queries
2. Delete: `decrement_inventory()`, any mutable catalog operations (they're Class Configuration, not Store)
3. No rewrite needed for read paths

---

### D. `app/services/insurance_policy_service.py`

**Current State:**
- Manages insurance policy definitions (Class Configuration concern)
- Not directly related to Store/Entitlements canonical schema

**Constitutional Authority:** Class Configuration owns policy definitions

**Classification:** **KEEP AS-IS; MOVE TO CLASS CONFIGURATION SERVICE LAYER EVENTUALLY**

**Action:** No action needed for Phase 2 demolition; this is Class Configuration not Store

---

## III. Utility-Layer Deletion Inventory

### A. `app/utils/store.py`

**Current State:**
- Legacy store-specific utilities
- Likely references deleted models or obsolete patterns

**Constitutional Authority:** Store doesn't need domain-specific utilities; use canonical schema directly

**Classification:** **DELETE ENTIRE FILE**

**Action:** Delete; FEATs and services access `EntitlementEvent` schema directly

---

### B. `app/utils/insurance_eligibility.py`

**Current State:**
- Live insurance claim eligibility checker; NOT legacy code
- Comprehensive transaction-based claim validation (waiting period, time limits, reimbursement tracking, delayed-use rules)
- **VIOLATES MANDATORY ARCHITECTURAL REQUIREMENT**: Uses non-canonical temporal utilities (`get_class_now()`, `to_class_time()`, `ensure_utc()`) instead of `canonical_temporal_resolver`
- **VIOLATES MANDATORY ARCHITECTURAL REQUIREMENT**: Calls deleted `list_entitlement_history()` from deleted service
- **VIOLATES MANDATORY ARCHITECTURAL REQUIREMENT**: Direct attribute access (`getattr(enrollment, "class_id")`) instead of canonical context resolution

**Constitutional Authority:** Claim eligibility validation belongs in insurance domain; but implementation must use canonical tools

**Classification:** **DELETE ENTIRE FILE** (must be rewritten using mandatory canonical tools)

**Action:** 
1. Delete entire file
2. Move canonical eligibility logic into `FEAT-STOR-003` submission validation phase:
   - Rewrite waiting-period check using `canonical_temporal_resolver` with `CanonicalTemporalEvaluation`
   - Rewrite transaction eligibility using canonical context resolver
   - Rewrite delayed-use rule to query `EntitlementEvent` directly (not service function)
   - Return policy violations as part of pending_action payload (not hard-reject)
3. Move reimbursement tracking to Ledger domain (it owns transaction history)
4. Move claim-type resolution into policy service or FEAT-STOR-003

---

### C. `app/utils/insurance_billing.py`

**Current State:**
- Insurance billing/premium calculation utility
- Likely based on old schema or Obligations patterns

**Constitutional Authority:** Obligations owns premium assessment and satisfaction; Ledger owns monetary truth

**Classification:** **DELETE ENTIRE FILE**

**Action:** Delete; billing logic remains in Obligations domain

---

## IV. Route-Layer Rewrite Inventory

### A. Routes Owned by Class Configuration Domain (Keep, may need view-model updates)

| Route | Endpoint | Current Path | Ownership | Action |
|-------|----------|--------------|-----------|--------|
| `admin.store_management` (GET) | `/admin/store` | `app/routes/admin.py:5175` | Class Cfg → display catalog | Keep; may need view-model for new schema |
| `admin.store_management` (POST) | `/admin/store` | `app/routes/admin.py:5175` | Class Cfg → create item | Keep; `store_items` write is correct |
| `admin.edit_store_item` | `/admin/store/edit/<item_id>` | `app/routes/admin.py:5540` | Class Cfg → edit catalog | Keep; `store_items` write is correct |
| `admin.delete_store_item` | `/admin/store/delete/<item_id>` | `app/routes/admin.py:5614` | Class Cfg → soft-delete item | Keep; `store_items` write is correct |
| `admin.hard_delete_store_item` | `/admin/store/hard-delete/<item_id>` | `app/routes/admin.py:5640` | Class Cfg → hard-delete item | Keep; `store_items` write is correct |
| `admin.insurance_management` (GET) | `/admin/insurance` | `app/routes/admin.py:6379` | Class Cfg → display policies | Keep; aborted, restore with Class Cfg authority |
| `admin.insurance_management` (POST) | `/admin/insurance` | `app/routes/admin.py:6379` | Class Cfg → create policy | Keep; create insurance policy (Class Cfg) |
| `admin.edit_insurance_policy` | `/admin/insurance/edit/<policy_id>` | `app/routes/admin.py:6424` | Class Cfg → edit policy | Keep; edit policy (Class Cfg) |
| `admin.deactivate_insurance_policy` | `/admin/insurance/deactivate/<policy_id>` | `app/routes/admin.py:6518` | Class Cfg → deactivate | Keep; deactivate policy (Class Cfg) |
| `admin.delete_insurance_policy` | `/admin/insurance/delete/<policy_id>` | `app/routes/admin.py:6552` | Class Cfg → delete policy | Keep; delete policy (Class Cfg) |
| `student.shop` (GET) | `/student/shop` | `app/routes/student.py:?` | Read → catalog browse | Keep; read-only, update view model |
| `student.insurance_marketplace` (GET) | `/student/insurance` | `app/routes/student.py:1522` | Read → marketplace browse | Keep; read-only, update view model |

**Action:** No breaking changes; these routes own Class Configuration domain, not Store/Entitlements. View models may need updates to reference `entitlement_events` instead of old purchase models.

---

### B. Routes Owned by Store and Entitlements Domain (REWRITE REQUIRED)

| Route | Endpoint | Current FEAT | v3.0+ FEAT | Authority | Status |
|-------|----------|--------------|------------|-----------|--------|
| `api.purchase_item` | `/api/purchase-item` | store_purchase_feat | FEAT-STOR-001 v3.0 | Student purchase | **REWRITE** |
| `api.use_item` | `/api/use-item` | redemption_disposition_feat | FEAT-STOR-002 v2.0 | Delayed-use consumption | **REWRITE** |
| `api.approve_redemption` | `/api/approve-redemption` | redemption_disposition_feat | FEAT-STOR-002 v2.0 | Approve redemption | **REWRITE** |
| `api.reject_redemption` | `/api/reject-redemption` | redemption_disposition_feat | FEAT-STOR-002 v2.0 | Reject redemption | **REWRITE** |
| `admin.adjust_hall_pass_entitlements` | `/admin/student/<seat_id>/adjust-hall-pass-entitlements` | (old) | FEAT-STOR-004 v1.0 | Teacher grant/revoke | **REWRITE** |
| `admin.bulk_adjust_hall_pass_entitlements` | `/admin/students/bulk-adjust-hall-pass-entitlements` | (old) | FEAT-STOR-004 v1.0 | Bulk teacher grant/revoke | **REWRITE** |
| `admin.process_claim` | `/admin/insurance/claim/<claim_id>` | insurance_claim_feat | FEAT-STOR-003 v2.0 | Insurance adjudication | **REWRITE** |
| `admin.view_student_policy` | `/admin/insurance/student-policy/<enrollment_id>` | (aborted) | Read-only | Insurance policy review | **NEEDS IMPLEMENTATION** |
| `student.purchase_insurance` | `/student/insurance/purchase/<policy_id>` | insurance_purchase_feat | FEAT-STOR-001 v3.0 | Insurance initial purchase | **REWRITE** |
| `student.file_claim` | `/student/insurance/claim/<policy_id>` | insurance_claim_feat | FEAT-STOR-003 v2.0 | Insurance claim submission | **REWRITE** |
| `student.view_policy` | `/student/insurance/policy/<enrollment_id>` | (aborted) | Read-only | Insurance coverage view | **NEEDS IMPLEMENTATION** |

**Action Summary:**
- Rewrite mutation paths (purchase, redemption, claim) to call new FEATs with `EntitlementEvent` schema
- Implement read paths for insurance/policy views using `EntitlementEvent` history
- Update view models to consume canonical data instead of deleted models

---

## V. Test-Layer Deletion Inventory (Already Skipped in Phase 2)

| Test File | Reason | Action |
|-----------|--------|--------|
| `tests/dom/entitlement/test_store.py` | Tests old StorePurchase model | Delete |
| `tests/dom/entitlement/test_redemption_disposition.py` | Tests old RedemptionEvent | Delete |
| `tests/dom/entitlement/test_redemption_rejection.py` | Tests old RedemptionEvent | Delete |
| `tests/dom/entitlement/test_collective_goal_progress.py` | Tests old Entitlement model | Delete |
| `tests/dom/attendance/test_hall_pass_checkout.py` | Tests old EntitlementEvent schema (v1) | Delete |
| `tests/dom/prod/test_feat_prod.py` | Tests old EntitlementEvent schema (v1) | Delete |
| `tests/dom/ledger/test_join_code_deletion_semantics.py` | Tests deleted StorePurchase | Delete |

**Action:** Delete all identified test files; they test superseded schema and broken FEATs.

---

## VI. Execution Roadmap (Phase 3-4)

### Phase 3: Primitives (New FEAT implementations)

**Priority 1:**
1. `FEAT-STOR-001` v3.0 — Purchase + entitlement grant (enables `api.purchase_item`)
2. `FEAT-STOR-002` v2.0 — Lifecycle transitions (enables `api.use_item/approve_redemption/reject_redemption`)
3. `FEAT-STOR-004` v1.0 — Direct teacher grants (enables `admin.adjust_hall_pass_entitlements`)

**Priority 2:**
4. `FEAT-STOR-003` v2.0 — Insurance claim lifecycle (enables insurance submission/approval)
5. Read services: `get_entitlement_balance()`, `is_entitlement_exercisable()`, etc.

### Phase 4: Routes and Integration

**Priority 1:** Wire routes to new FEATs
1. `/api/purchase-item` → FEAT-STOR-001
2. `/api/use_item`, `/api/approve_redemption`, `/api/reject_redemption` → FEAT-STOR-002
3. `/admin/student/<seat_id>/adjust-hall-pass-entitlements` → FEAT-STOR-004

**Priority 2:** Implement insurance routes
4. `/student/insurance/claim/<policy_id>` → FEAT-STOR-003
5. `/admin/insurance/claim/<claim_id>` → FEAT-STOR-003 decision path
6. `/student/insurance/policy/<enrollment_id>` → Read-only EntitlementEvent history
7. `/admin/insurance/student-policy/<enrollment_id>` → Read-only EntitlementEvent history

**Priority 3:** Implement read-only catalog updates
8. Update `student.shop` view model
9. Update `admin.store_management` view model (if references deleted models)

### Phase 5: Cleanup

**After all routes wired:**
1. Delete old FEAT files (after confirmed no route references)
2. Delete old service files
3. Delete old utility files
4. Delete test files
5. Update MAP-UI-001 to reflect new FEAT wiring

---

## VII. Classification Summary

| Category | Count | Action | Phase |
|----------|-------|--------|-------|
| **FEATs** | 4 | Complete rewrite to new schema (3 existing + 1 new) | 3 |
| **Services** | 4 | Delete 1, rewrite selective functions in 1, keep 2 as-is | 3 |
| **Utilities** | 3 | Delete all 3 (store.py, insurance_eligibility.py, insurance_billing.py) | 5 |
| **Routes (Class Cfg)** | 11 | Keep as-is, may update view models | 4 |
| **Routes (Store/Ent)** | 11 | Rewrite to call new FEATs | 4 |
| **Test Files** | 7 | Delete all (already skipped) | 5 |

**Total Phase 3-5 Effort:**
- Write 4 new/rewritten FEATs (~4 weeks)
- Rewrite 4 routes to new FEATs (~2 weeks)
- Implement 7 read-only routes (~2 weeks)
- Cleanup and verification (~1 week)

---

## VIII. Mandatory Canonical Tool Requirement

**CRITICAL ARCHITECTURAL ENFORCEMENT:** Any code that uses non-canonical temporal or identity tools must be deleted and rewritten.

Mandatory canonical tools for Phase 3 rewrites:

| Tool | Authority | Usage |
|------|-----------|-------|
| `canonical_temporal_resolver` | SPEC-TIME-001 | All temporal evaluation (waiting periods, time limits, date boundaries) |
| `CanonicalContext` | INV-CORE, INV-ARC-019 | All identity and class-scope resolution |
| `context_resolver.resolve_canonical_context()` | INV-ARC-020 | Entry point for route context resolution |
| `display_metadata` / `display_name_session` | INV-ARC-020 | All display-only rendering (names, labels, titles) |

**Non-Canonical Anti-Patterns Found in Store/Entitlements Code:**

- ❌ `app.utils.time.get_class_now()` — use `canonical_temporal_resolver.resolve("CLE", ctx)`
- ❌ `app.utils.time.to_class_time()` — use `canonical_temporal_resolver` evaluation
- ❌ `app.utils.time.ensure_utc()` — use `canonical_temporal_resolver` which enforces UTC normalization
- ❌ Direct `getattr(obj, "class_id")` for identity — use `CanonicalContext` from context resolver
- ❌ `app.services.store_entitlement_service` functions — deleted models; use direct schema queries only

**Consequence:** Any new FEAT, service, utility, or route rewrite MUST use canonical tools exclusively. Code review will reject implementations using custom temporal or identity utilities.

---

## IX. Constitutional Anchors

This manifest is subordinate to and SHALL be reaudited against:
- DOM-STORE-001 v4.0 (2026-07-27)
- FEAT-STOR-001 v3.0 (2026-07-27)
- FEAT-STOR-002 v2.0 (2026-07-27)
- FEAT-STOR-003 v2.0 (2026-07-27)
- FEAT-STOR-004 v1.0 (2026-07-27)
- MAP-UI-001 v0.2 (2026-07-22)
- SPEC-TIME-001 (Canonical Temporal Resolver)
- INV-CORE, INV-ARC-019, INV-ARC-020 (Identity and Temporal Model)
- SOP-DEV-002 (Canonical Domain Reconstruction Workflow)

Any future amendment to these documents renders prior demolition classifications void; re-audit required.

---

**Document Version:** 1.0 (Re-audit from Phase 2 bridge state)
**Last Updated:** 2026-07-27
**Status:** Ready for Phase 3-4 execution planning
