# Phase 4: Route Rewiring & Complete FEAT Implementation

**Status:** Starting  
**Authority:** STORE_ENTITLEMENTS_DEMOLITION_REPORT_2026-07-27.md, PHASE_3_FEAT_IMPLEMENTATION_ROADMAP.md  
**Goal:** Get app loading + routes wired to new FEATs + Phase 2-3 FEATs fully implemented

---

## I. Immediate Blockers (App Won't Load)

### Broken Imports Summary

| File | Broken Imports | Impact | Fix Strategy |
|---|---|---|---|
| `app/routes/api.py` | 3 imports | POST `/api/purchase-item`, `/api/use-item`, `/api/approve-redemption`, `/api/reject-redemption` fail | Remove old, wire to new FEATs |
| `app/routes/student.py` | 5 imports | GET/POST `/student/shop`, `/student/insurance/*`, claim submission fail | Remove old, wire to new FEATs |
| `app/routes/admin.py` | 4 imports | GET/POST admin insurance/claim routes fail | Remove old, wire to new FEATs |
| `app/services/store_service.py` | 1 import | Service loads but functions unavailable | Remove dead import |
| `app/feats/transaction_void_feat.py` | 1 import | Cross-domain void path broken | Rewrite to query EntitlementEvent directly |
| `app/scheduled_tasks.py` | 1 import | Insurance renewal tasks blocked | TODO: Audit what task exists |

**App Load Status:** 🔴 BLOCKED (ModuleNotFoundError on import)

---

## II. Phase 4 Execution Order

### Stage 1: Unblock App Loading (1-2 hours)

**Goal:** Flask can start without import errors

**Tasks:**
1. Remove all broken imports from routes (comment out, don't delete logic yet)
2. Create stub implementations for immediate endpoints (or return 503 Service Unavailable)
3. Verify `flask run` works

**Affected Files (in order):**
- [ ] `app/services/store_service.py` — Remove line 16 (dead import)
- [ ] `app/routes/api.py` — Comment out lines 59-63 (store_purchase_feat, store_entitlement_service, redemption_disposition_feat)
- [ ] `app/routes/student.py` — Comment out lines 74-130 (all store-related imports)
- [ ] `app/routes/admin.py` — Comment out lines 135-250 (all store-related imports)
- [ ] `app/scheduled_tasks.py` — Comment out line 11 (insurance_billing)
- [ ] `app/feats/transaction_void_feat.py` — Comment out line 10; add TODO for EntitlementEvent rewrite

**Commit:** "Stage 1: Remove broken imports (app loads, routes return 503)"

---

### Stage 2: Implement FEAT-STOR-004 (1-2 hours)

**Goal:** Direct teacher grant FEAT ready for route wiring

**File:** `app/feats/direct_entitlement_grant_feat.py` (new, ~200 lines)

**Implementation:**
1. Copy FEAT-STOR-001 pattern
2. Validation: Teacher authority for class, product supports direct grants
3. Mutation: Create one EntitlementEvent per granted unit
4. Special handling: Hall-pass grants (don't create mutable balance)
5. Tests: Teacher grant creates GRANTED event, idempotency, bulk grants

**Tests:** `tests/test_feat_stor_004_direct_grant.py` (~300 lines)

**Commit:** "Phase 4: Implement FEAT-STOR-004 v1.0 (Direct Entitlement Grant)"

---

### Stage 3: Wire Routes to FEAT-STOR-001 & FEAT-STOR-004 (2-3 hours)

**Goal:** Purchase and direct grant routes working end-to-end

**Critical Routes (highest priority):**

| Route | Method | Current Import | Action | Unblocks |
|---|---|---|---|---|
| `/api/purchase-item` | POST | `store_purchase_feat` | Wire to `execute_store_purchase()` | Student purchases |
| `/admin/.../adjust-hall-pass` | POST | `None yet` | Wire to `execute_direct_grant()` | Teacher adjustments |

**Secondary Routes (after critical):**

| Route | Method | Current Import | Action | Unblocks |
|---|---|---|---|---|
| `/api/use-item` | POST | `redemption_disposition_feat` | TODO (Phase 5: FEAT-STOR-002) | Item use/redemption |
| `/api/approve-redemption` | POST | `redemption_disposition_feat` | TODO (Phase 5: FEAT-STOR-002) | Approve item use |
| `/api/reject-redemption` | POST | `redemption_disposition_feat` | TODO (Phase 5: FEAT-STOR-002) | Reject item use |
| `/student/insurance/purchase/` | POST | `insurance_purchase_feat` | Wire to `execute_store_purchase()` | Insurance purchase |
| `/student/insurance/claim/` | POST | `insurance_claim_feat` | TODO (Phase 5: FEAT-STOR-003) | Claim submission |
| `/admin/insurance/claim/` | POST | `insurance_claim_feat` | TODO (Phase 5: FEAT-STOR-003) | Claim adjudication |

**Implementation Strategy:**
1. Fix `app/routes/api.py`: Wire `/api/purchase-item` to new FEAT
2. Fix `app/routes/student.py`: Wire `/student/insurance/purchase/` to new FEAT
3. Add `/admin/.../adjust-hall-pass` endpoint (new, wire to FEAT-STOR-004)
4. Leave other routes returning 503 Service Unavailable (FEAT-STOR-002/003 coming in Phase 5)

**Commit:** "Phase 4: Wire purchase routes to FEAT-STOR-001 + FEAT-STOR-004"

---

### Stage 4: Smoke Tests & Integration (1-2 hours)

**Goal:** Flask loads, basic purchase flow works

**Tests:**
1. Flask loads without import errors ✅
2. Student can purchase item end-to-end ✅
3. EntitlementEvent rows created ✅
4. Ledger coordination MVP (assumes success) ✅
5. Teacher can adjust entitlements ✅

**Run Full Test Suite:**
```bash
pytest tests/test_feat_stor_001_purchase.py -xvs
pytest tests/test_feat_stor_004_direct_grant.py -xvs
# Routes can't test yet (Ledger integration needed)
```

**Commit:** "Phase 4: Smoke tests passing, purchase flow works"

---

### Stage 5: Phase 2 Integration Improvements (2-3 hours, optional)

**Goal:** Add production-ready features to FEAT-STOR-001 (optional if time permits)

**Optional Enhancements:**
1. Actual Ledger coordination (integrate `resolve_intended_ledger_plan()`)
2. Product config reads (validate entitlement_type, pricing)
3. Idempotency store (track idempotency_key → correlation_id)
4. Obligation validation (check blocking rents)

**If completed:**
- Routes can actually charge students
- Purchases fail when insufficient funds
- Purchases blocked by outstanding obligations

**If skipped:** Document as Phase 5 work

---

## III. Critical Decisions

### Decision 1: Stub Routes or Remove Them?

**Options:**
A. Comment out broken imports, leave route handlers (they'll error at runtime)
B. Comment out entire route handlers, return 503 Service Unavailable
C. Delete route handlers completely

**Decision:** Option B — Return 503 Service Unavailable with message "FEAT-STOR-002/003 not yet implemented"

**Rationale:** Routes are discoverable; users see clear message instead of runtime error

### Decision 2: Fix Routes Before or After FEAT-STOR-004?

**Options:**
A. Fix routes first (can't test without FEAT-STOR-004 for direct grants)
B. Implement FEAT-STOR-004 first (can then test direct grant route)

**Decision:** Option B — FEAT-STOR-004 first, then wire both purchase + grant routes together

**Rationale:** Parallel work is more efficient; both routes ready in Stage 3

### Decision 3: Implement All Production Integrations in Phase 4?

**Options:**
A. MVP only (Ledger assumes success, no product config, no Obligations)
B. Full production (all integrations complete)
C. Partial (Ledger integration done, product config in Phase 5)

**Decision:** Option A → B (MVP first, upgrade if time permits)

**Rationale:** MVP unblocks testing today; Phase 5 can iterate on integrations if needed

---

## IV. Files to Modify

### 1. Route Files (Remove broken imports, comment out logic)

```
app/routes/api.py                  # Lines 59-63
app/routes/student.py              # Lines 74-130
app/routes/admin.py                # Lines 135-250
app/scheduled_tasks.py             # Line 11
```

### 2. New FEAT Implementation

```
app/feats/direct_entitlement_grant_feat.py  # NEW (FEAT-STOR-004)
tests/test_feat_stor_004_direct_grant.py    # NEW
```

### 3. Existing FEAT Fixes

```
app/feats/transaction_void_feat.py  # Comment out line 10; rewrite query
```

### 4. Service Cleanup

```
app/services/store_service.py  # Remove line 16
```

---

## V. Success Criteria (End of Phase 4)

- [ ] Flask app loads without import errors
- [ ] `/api/purchase-item` wired to FEAT-STOR-001 ✓
- [ ] `/admin/.../adjust-hall-pass` wired to FEAT-STOR-004 ✓
- [ ] Student can purchase items (end-to-end) ✓
- [ ] Teacher can adjust entitlements ✓
- [ ] EntitlementEvent rows created correctly ✓
- [ ] Correlation ID lineage working ✓
- [ ] All uncommitted Stage tests pass ✓
- [ ] No import errors in route files ✓

**Status if complete:** Ready for Phase 5 (FEAT-STOR-002/003 + remaining routes)

---

## VI. Phase 5 Preview (Not Executing Now)

**Still TODO:**
- FEAT-STOR-002 (lifecycle: CONSUMED, EXPIRED, REVOKED)
- FEAT-STOR-003 (insurance claims: pending_actions pattern)
- Route wiring for lifecycle/insurance operations
- Cross-domain coordination tests
- Full integration testing

**Estimated:** 2-3 weeks additional work

---

**Created:** 2026-07-27 (Start of Phase 4)  
**Status:** Ready to Execute  
**Estimated Duration:** 5-10 hours for full Phase 4 completion
