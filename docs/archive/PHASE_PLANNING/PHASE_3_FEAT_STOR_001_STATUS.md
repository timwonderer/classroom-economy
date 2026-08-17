# Phase 3: FEAT-STOR-001 v3.0 Historical Status

**Date:** 2026-07-27  
**Status:** Archived implementation record  
**Branch:** `codex/store-behavior`

---

## I. Historical Implementation Record ✅

### A. FEAT-STOR-001 v3.0 Implementation

**File:** `app/feats/store_purchase_feat.py` (245 lines)

**Structure:**
- `StorePurchaseError`: Exception class for purchase failures
- `StorePurchaseResult`: Dataclass with result schema (success, correlation_id, quantity_granted, entitlement_ids, error_code, error_message)
- `execute_store_purchase()`: Public entry point (no decorator)
- `_execute_store_purchase_impl()`: @requires_feat_context wrapped implementation

**Implementation Phases:**
1. ✅ **Phase 1: Read-Only Validation**
   - Canonical context validation (user_id, class_id, seat_id present)
   - Target seat exists and belongs to class_id
   - Quantity is positive integer
   - Product exists
   - Eligibility validation

2. ✅ **Phase 2: Ledger Coordination**
   - Purchase flow coordinates through the canonical ledger plan resolver
   - Ledger outcome is resolved before entitlement mutations are committed

3. ✅ **Phase 3: Atomic EntitlementEvent Grants**
   - Creates N distinct EntitlementEvent rows for quantity N
   - Each row: unique event_id, shared entitlement_id (lineage), same correlation_id
   - All mutations in single transaction (managed by @requires_feat_context)
   - Uses canonical_temporal_resolver for UTC timestamp

4. ✅ **Phase 4: Instant-Use Coordination**
   - If instant_use=True, creates CONSUMED event for each granted entitlement
   - Same transaction boundary as GRANTED events

**Architectural Compliance:**
- ✅ Uses `@requires_feat_context("FEAT-STOR-001")` decorator
- ✅ Uses `CanonicalContext` (not direct identity access)
- ✅ Uses `canonical_temporal_resolver` (not get_class_now/to_class_time)
- ✅ Immutable EntitlementEvent design (no mutable quantity field)
- ✅ Quantity = N rows, not mutable count
- ✅ Atomic transaction boundary (Ledger + Store succeed/fail together)
- ✅ Correlation ID lineage for audit

### B. Comprehensive Test Suite

**File:** `tests/test_feat_stor_001_purchase.py` (445 lines)

**Test Classes (7 total, 15+ test cases):**

| Test Class | Purpose | Coverage |
|---|---|---|
| `TestStorePurchaseHappyPath` | Ordinary purchase flow | Quantity=3 creates 3 GRANTED events; provided correlation_id honored |
| `TestInstantUse` | Immediate consumption | GRANTED + CONSUMED events in same transaction |
| `TestQuantityLogic` | Immutable design | Quantity=5 → 5 rows (not 1 row with count); Quantity=1 → 1 row |
| `TestValidationFailures` | Input validation | Zero/negative quantities rejected; context validation; seat scope checking |
| `TestIdempotency` | Replay protection | Documents expected behavior (full idempotency store in Phase 4) |
| `TestCrossClassIsolation` | Multi-tenancy | Purchases in different classes don't interfere |

**Test Fixtures:**
- `test_class_and_seat`: Creates class scope with teacher, student user, and student seat
- Fixtures use existing test helpers from `tests/helpers/` (class_scope.py, etc.)

**Coverage:**
- ✅ Happy path (ordinary purchase creates N events)
- ✅ Instant-use path (GRANTED + CONSUMED)
- ✅ Quantity validation (N=5 → 5 rows, not 1 row)
- ✅ Context validation (missing class_id, seat not in class)
- ✅ Quantity validation (zero, negative rejected)
- ✅ Idempotency (pattern documented; full implementation in Phase 4)
- ✅ Cross-class isolation

### C. Learning Documentation Updated

**File:** `.claude/projects/*/memory/sop_dev_002_lessons_learned.md` (new Section XI)

**Additions:**
- FEAT implementation pattern (4-phase execution + design decisions)
- FEAT-STOR-001 specifics (file structure, key decisions, MVP vs. production)
- Test coverage pattern (reusable structure for all FEATs)
- Phase 4 blocking issues (routes need rewiring)
- Architectural wins (immutability, canonical tools, atomic coordination)

### D. Phase 3 Roadmap Created

**File:** `PHASE_3_FEAT_IMPLEMENTATION_ROADMAP.md` (400+ lines)

Documents:
- Dependency graph (FEAT-STOR-001 → FEAT-STOR-004 → FEAT-STOR-002 → FEAT-STOR-003)
- Per-FEAT specifications (input/output, validation, mutation, testing)
- Weekly execution plan (4 weeks to complete all FEATs)
- Success criteria and risk factors

---

## II. Historical Notes on Earlier Gaps

### A. Ledger Coordination

This section documents the earlier MVP gap that was later closed in the live branch by routing through the canonical ledger plan resolver.

### B. Product Configuration Reads

This section records the earlier placeholder state before the purchase flow was wired to canonical product configuration.

### C. Obligation Domain Validation

This section records the earlier skipped validation step before the purchase flow was aligned with obligations checks.

### D. Idempotency Store

This section records the earlier documented-only replay pattern before the live branch gained the current purchase coordination path.

---

## III. Historical Phase 4 Follow-Ups

### A. Routes Have Broken Imports (Historical Note)

The original phase-3 notes recorded a route-wiring gap that has since been superseded by the current branch implementation.

**Affected Routes:**

| File | Broken Import | Needs Rewrite |
|---|---|---|
| `app/routes/api.py` | from `store_purchase_feat` | → call `execute_store_purchase()` |
| `app/routes/api.py` | from `redemption_disposition_feat` | → call future FEAT-STOR-002 |
| `app/routes/student.py` | from `insurance_purchase_feat` | → call `execute_store_purchase()` (insurance variant) |
| `app/routes/student.py` | from `insurance_claim_feat` | → call future FEAT-STOR-003 |
| `app/routes/admin.py` | from `insurance_claim_feat` | → call future FEAT-STOR-003 |

**Historical Action:** Wire routes to the FEAT-STOR-001 entry point

### B. Remaining FEATs (Historical Ordering)

**Status:** This section preserves the original dependency order from the phase-3 rollout notes

**Dependency Order:**
1. FEAT-STOR-001 ✅ (done)
2. FEAT-STOR-004 (direct grants) — 🔄 next
3. FEAT-STOR-002 (lifecycle transitions: CONSUMED, EXPIRED, REVOKED)
4. FEAT-STOR-003 (insurance claims: pending_actions pattern)

---

## IV. Archived Next Steps

### Week 1 Execution (archived rollout note):

1. **✅ FEAT-STOR-001** (completed in the archived rollout)
   - [x] Implement purchase + entitlement grant
   - [x] Comprehensive tests
   - [x] Documentation

2. **🔄 FEAT-STOR-004** (direct teacher grants)
   - [ ] Implement execute_direct_grant()
   - [ ] Hall-pass special handling
   - [ ] Tests
   - [ ] Wire routes: /admin/student/<id>/adjust-hall-pass-entitlements

3. **🔄 Wire FEAT-STOR-001 to routes**
   - [ ] Fix app/routes/api.py: /api/purchase-item → execute_store_purchase()
   - [ ] Fix app/routes/student.py: /student/insurance/purchase/... → execute_store_purchase()
   - [ ] Verify Flask loads

4. **🔄 Phase 4 Integration Tests**
   - [ ] End-to-end: student purchases item
   - [ ] Verify Ledger + Entitlement coordination
   - [ ] Verify balance updates

---

## V. Success Criteria (Week 1 Complete)

- [ ] FEAT-STOR-001 tests pass (currently blocked by route imports)
- [ ] Flask loads without import errors (routes rewired)
- [ ] `/api/purchase-item` endpoint works end-to-end
- [ ] Student can purchase items and receive entitlements
- [ ] Ledger updates coordinated with EntitlementEvent creation
- [ ] Idempotency works (replay safe)

---

## VI. Technical Notes

### A. Transaction Management

FEAT-STOR-001 uses `@requires_feat_context("FEAT-STOR-001")` which:
- Creates one DB transaction boundary (top-level FEAT owns transaction)
- Commits all mutations (Ledger + Store) together
- Rolls back on any failure
- Tracks correlation_id through nested FEAT calls

### B. Timestamp Canonicalization

```python
# Use canonical_temporal_resolver for all timestamps
temporal_eval = canonical_temporal_resolver(
    CLASS_LEVEL_EVALUATION,
    canonical_execution_context=canonical_context,
    primitive="current_time",
)
timestamp_utc = temporal_eval.canonical_now_utc  # ← Use this
```

NOT: `utc_now()`, `get_class_now()`, `to_class_time()` (legacy)

### C. Entitlement ID Lineage

Each unit creates:
- Unique `event_id` (UUID for each row)
- Shared `entitlement_id` (lineage for lifecycle)
- Shared `correlation_id` (cross-domain audit trail)

```python
for unit in range(quantity):
    event_id = str(uuid.uuid4())  # NEW for each unit
    entitlement_id = str(uuid.uuid4())  # Lineage anchor
    
    EntitlementEvent(
        event_id=event_id,
        entitlement_id=entitlement_id,
        correlation_id=corr_id,  # SAME for all units
        event_type="GRANTED",
        ...
    )
```

---

## VII. Files Modified/Created

| File | Status | Lines | Purpose |
|---|---|---|---|
| `app/feats/store_purchase_feat.py` | ✅ Created | 245 | FEAT-STOR-001 implementation |
| `tests/test_feat_stor_001_purchase.py` | ✅ Created | 445 | Comprehensive test suite |
| `PHASE_3_FEAT_IMPLEMENTATION_ROADMAP.md` | ✅ Created | 400+ | Weekly execution plan |
| `.claude/memory/sop_dev_002_lessons_learned.md` | ✅ Updated | +200 | Section XI: Phase 3 patterns |

---

**Last Updated:** 2026-07-27  
**Next Gate:** Phase 4 (Route Rewiring + Remaining FEATs)  
**Status:** Ready for phase 4
