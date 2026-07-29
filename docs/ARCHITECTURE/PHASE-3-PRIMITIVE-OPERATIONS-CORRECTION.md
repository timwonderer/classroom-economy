# Phase 3: Primitive Operations — Exact Resolution Contract (Correction)

**Date**: 2026-07-28  
**Revision**: 1.0  
**Context**: Corrects inference-based policy selection in FEAT-STOR-004 to enforce exact UUID resolution

---

## Problem Statement

Initial Phase 3 implementation (commit 7be90ade) accepted `product_id` as FEAT input and inferred which policy to use via:
```
Query store_products WHERE class_id=X AND is_retired=False AND payload.product_id=product_id
Take first match (arbitrary if multiple exist)
Resolve that policy_uuid
```

This violates the architectural requirement: **Execution must accept and resolve exact policy_uuid without inference.**

---

## Correction (Commit 7539f300)

### FEAT-STOR-004 Contract Revision

**Before:**
```python
def execute_direct_grant(
    canonical_context,
    target_seat_id,
    product_id,  # ❌ Inference: which policy for this product?
    quantity
)
```

**After:**
```python
def execute_direct_grant(
    canonical_context,
    target_seat_id,
    policy_uuid,  # ✅ Exact: caller supplies exact policy to execute
    quantity
)
```

### Execution Flow (After Correction)

1. **Caller discovers policy** (outside FEAT scope — deferred to `get_applicable_policies()`)
   - Resolves "which policy applies for product_id X in class Y?"
   - Returns policy_uuid

2. **Caller invokes FEAT with exact UUID**
   ```python
   execute_direct_grant(
       canonical_context=ctx,
       target_seat_id=student_id,
       policy_uuid="550e8400-e29b-41d4-a716-446655440000",  # Exact input
       quantity=1
   )
   ```

3. **FEAT-STOR-004 executes with exact resolution** (no inference)
   ```python
   # Exact resolution — no inference
   policy_config = StorePolicyResolver.resolve_store_item(policy_uuid)
   
   # Verify scope
   if policy_config.class_id != canonical_context.class_id:
       raise POLICY_SCOPE_MISMATCH
   
   # Validate constraints (FEAT-specific)
   if not policy_config.supports_direct_grants:
       raise GRANT_NOT_SUPPORTED
   
   # Extract product_id from resolved policy (not from caller)
   product_id = policy_config.product_id
   
   # Check per-student limits
   existing = count_grants(class_id, target_seat_id, product_id)
   if existing + quantity > policy_config.limit_per_student:
       raise LIMIT_EXCEEDED
   
   # Create entitlements
   for i in range(quantity):
       create_entitlement_event(
           product_id=policy_config.product_id,
           entitlement_type=policy_config.entitlement_type,
           policy_uuid=policy_config.policy_uuid,
           ...
       )
   ```

---

## Architectural Consequences

### 1. No Ambiguity with Multiple Policies per Product

**Scenario**: Multiple non-retired policies exist for same product_id:
```
store_products (class_id="C1", product_id=101, supports_direct_grants=true)   → UUID-1
store_products (class_id="C1", product_id=101, supports_direct_grants=false)  → UUID-2
```

**Before (Inference)**: ❌ Arbitrary selection of first matching row
```python
# Which UUID? Depends on database sort order (undefined)
policy = query_store_products(class_id="C1", is_retired=False, product_id=101)
# Might resolve UUID-1 or UUID-2 non-deterministically
```

**After (Exact)**: ✅ Caller chooses exact UUID, FEAT resolves it
```python
# Caller: "Grant policy UUID-1 to student"
execute_direct_grant(policy_uuid="UUID-1", ...)  # → UUID-1 resolved, guarantees supports_direct_grants=true

# OR

# Caller: "Grant policy UUID-2 to student"
execute_direct_grant(policy_uuid="UUID-2", ...)  # → UUID-2 resolved, guarantees supports_direct_grants=false
```

### 2. Clear Domain Boundaries

**Policies Domain (POL)**
- Owns `store_products` table
- Owns immutable UUID locator
- Responsible for "which policies exist"

**Discovery/Applicability** (deferred, separate concern)
- `get_applicable_policies(class_id)` — semantics TBD in DOM-STORE-001
- Responsible for "which policy applies now"
- Returns list of applicable policies with UUIDs
- Caller chooses from list

**Store & Entitlements Domain (STORE)**
- Owns FEAT-STOR-004 and FEAT-STOR-001
- Accepts exact policy_uuid from caller
- Resolves and validates per SPEC-STORE-001
- Creates immutable entitlement events
- No inference; no hidden dependencies

### 3. Prevents Policy Selection Races

**Scenario**: Concurrent requests while policies are transitioning
```
Time T0: PolicyA (product_id=101, price=$50) is active
Time T1: PolicyB (product_id=101, price=$100) replaces PolicyA
Time T2: Grant request arrives

❌ Inference-based: "Which price was intended? $50 or $100?"
✅ Exact UUID: "Execute PolicyA-UUID if caller supplied it; PolicyB-UUID if caller supplied that"
```

---

## FEAT-STOR-001 (Purchase) — Apply Same Contract

When implementing FEAT-STOR-001, apply identical contract principle:

```python
def execute_purchase(
    canonical_context,
    target_seat_id,
    policy_uuid,  # ✅ Exact policy, not product_id
    quantity
)
```

Same flow:
1. Caller discovers applicable policies via separate mechanism (TBD)
2. Caller supplies exact policy_uuid
3. FEAT resolves exactly, validates, executes

---

## Test Coverage (Commit 7539f300)

Created `tests/test_store_policy_resolver.py` with comprehensive coverage:

**Parser Validation** (SPEC-STORE-001 rules)
- Unknown fields rejected fail-fast
- Type checking (int, bool, decimal, datetime, enum)
- Range validation (price ≥ 0, limits > 0, percentages in [0-100])
- Type-specific rules (IMMEDIATE_USE ≠ auto_expiry_days, HALL_PASS = supports_direct_grants, etc.)
- Mutual exclusion (bundle XOR collective_goal)

**Exact Resolution**
- Single UUID resolves to exact policy
- Multiple UUIDs (same product_id) coexist without ambiguity
- Deleted policy UUID no longer resolves (expected)
- Other policies unaffected by deletion

**FEAT Contract**
- Signature requires `policy_uuid`, not `product_id`
- No inference logic
- Class scope verification
- Constraint validation (supports_direct_grants, per-student limits)

---

## Future Work

1. **Get Applicable Policies**: Define semantics in DOM-STORE-001 or SPEC-STORE-001
   - What makes a policy "applicable" for a class/product?
   - How do concurrent policy transitions interact with discovery?
   - Should return non-retired policies? Most recent? All versions?

2. **Routes and API**: Update endpoints to:
   - Call discovery layer (get_applicable_policies)
   - Let caller/UI select policy
   - Supply exact policy_uuid to FEAT

3. **FEAT-STOR-001**: Apply same exact-resolution contract for purchases

---

## Summary

| Concern | Before | After | Owns |
|---------|--------|-------|------|
| Discovery | (Missing) | `get_applicable_policies()` | Not FEAT (TBD) |
| Execution | FEAT (inference) | FEAT (exact UUID) | FEAT-STOR-004 |
| Policy Selection | Implicit, ambiguous | Explicit, unambiguous | Caller |
| Multiple Policies/Product | Undefined behavior | No conflict | Design, not bug |

The corrected contract establishes:
- **No inference in execution** — FEAT always resolves exact UUID supplied by caller
- **No ambiguity** — multiple policies coexist; caller chooses which one to execute
- **Clear domain boundary** — discovery (deferred) and execution (FEAT) are separate concerns
