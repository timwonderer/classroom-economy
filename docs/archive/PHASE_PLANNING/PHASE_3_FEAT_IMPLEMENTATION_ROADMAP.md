# Phase 3: FEAT Implementation Roadmap
## Store and Entitlements Canonical FEATs

**Status:** Implemented in the live tree; retained as historical roadmap  
**Authority:** DOM-STORE-001 v4.0, FEAT-STOR-001/002/003/004 v3.0-1.0  
**Checkpoint:** Demolition complete (STORE_ENTITLEMENTS_DEMOLITION_REPORT_2026-07-27.md)

---

## I. Dependency Graph and Build Order

```
FEAT-STOR-001 (Purchase)     <- Foundational; used by purchase routes
       ↓
FEAT-STOR-004 (Direct Grant)  <- Uses same EntitlementEvent write pattern
       ↓
FEAT-STOR-002 (Lifecycle)     <- Consumes/expires/revokes; depends on GRANTED events existing
       ↓
FEAT-STOR-003 (Insurance)     <- Uses pending_actions + EntitlementEvent; depends on 002
       ↓
Entitlement Read Services     <- Derives balances from EntitlementEvent history
       ↓
Route Rewiring                <- Can begin once FEATs are ready
```

### Blocking Relationships

| FEAT | Blocks These Routes | Must Wait For |
|------|---|---|
| FEAT-STOR-001 | `/api/purchase-item` (student), `/student/insurance/purchase` (insurance purchase) | Nothing |
| FEAT-STOR-004 | `/admin/student/<id>/adjust-hall-pass-entitlements`, bulk adjust | Nothing |
| FEAT-STOR-002 | `/api/use-item`, `/api/approve-redemption`, `/api/reject-redemption` | FEAT-STOR-001 (need GRANTED events to consume) |
| FEAT-STOR-003 | `/student/insurance/claim`, `/admin/insurance/claim` | FEAT-STOR-002 (pending action resolution writes terminal events) |

---

## II. FEAT-STOR-001: Store Purchase and Entitlement Grant (v3.0)

**Authority:** `docs/FEATURE-EXECUTION/FEAT-STOR-001_STORE_PURCHASE.md` (v3.0)

### Specification Highlights

**Input:**
- `CanonicalContext` (user_id, class_id, seat_id, actor_role)
- `product_id` — configured product identifier
- `quantity` — positive integer (for quantity-5 purchases, creates 5 EntitlementEvent rows)
- `idempotency_key` — replay guard

**Execution Path:**
1. **Validation phase (read-only):**
   - Verify product exists and is purchasable for class
   - Verify eligibility (policies, per-seat limits, obligations if applicable)
   - Verify financial plan (Ledger integration)

2. **Ledger execution:**
   - Call lawful Ledger FEAT with coordinated transaction
   - Get confirmation that purchase succeeded

3. **Entitlement grant (atomic):**
   - For each unit (quantity N = N rows):
     ```
     EntitlementEvent(
       event_id=uuid(),
       entitlement_id=<stable-lineage-uuid>,
       class_id=ctx.class_id,
       target_seat_id=ctx.seat_id,
       actor_seat_id=ctx.seat_id,
       product_id=product_id,
       acquisition_type="PURCHASE",
       event_type="GRANTED",
       entitlement_type=<from-policy>,
       correlation_id=<purchase-uuid>,
       payload={...type-specific facts...},
       timestamp=canonical-now
     )
     ```

4. **Instant-use coordination (if applicable):**
   - For immediate-use products: also create CONSUMED event for same entitlement_id in same transaction

### File Structure

```
app/feats/store_purchase_feat.py  (NEW)
├── StorePurchaseResult (dataclass)
├── StorePurchaseError (exception)
├── execute_store_purchase() (main entry)
│   ├── Phase 1: Validation (read-only)
│   ├── Phase 2: Ledger execution
│   ├── Phase 3: Entitlement grants
│   └── Phase 4: Instant-use coordination (if needed)
└── Helper functions (TBD based on implementation)
```

### Testing Requirements

- Happy path: ordinary purchase creates N EntitlementEvent rows with shared correlation_id
- Instant-use: purchase + immediate CONSUMED in same transaction
- Idempotency: replay with same idempotency_key returns same result, no duplicate events
- Ledger failure: if Ledger rejects plan, no entitlements created
- Quantity validation: quantity=5 creates exactly 5 rows (not 1 row with quantity field)
- Perk handling: purchase doesn't decide if perk earned; upstream authority grants it

### Unblocked Routes (3)

- `/api/purchase-item` (POST) — student store purchase
- `/student/insurance/purchase/<policy_id>` (POST) — insurance initial purchase (routes through FEAT-STOR-001)

---

## III. FEAT-STOR-004: Direct Entitlement Grant (v1.0)

**Authority:** `docs/FEATURE-EXECUTION/FEAT-STOR-004_DIRECT_ENTITLEMENT_GRANT.md` (v1.0)

### Specification Highlights

**Input:**
- `CanonicalContext` with `actor_role="teacher"`
- `product_id` — policy-owned product
- `target_seat_id` — seat receiving grant
- `idempotency_key` — replay guard

**Execution Path:**
1. Validate teacher authority for class_id
2. Validate product supports direct grants
3. Create one EntitlementEvent per granted unit:
   ```
   EntitlementEvent(
     acquisition_type="GRANT",  # ← Different from PURCHASE
     event_type="GRANTED",
     ...same schema as STOR-001...
   )
   ```

### Special Cases

**Hall-pass grants:**
- Don't create balance row (balance is derived from EntitlementEvent count)
- Don't use productivity records as source of truth (this FEAT creates the truth)

**Privilege grants:**
- Direct teach grants for non-counted privileges (seat choice, etc.)

### File Structure

```
app/feats/direct_entitlement_grant_feat.py  (NEW)
├── DirectGrantResult (dataclass)
├── DirectGrantError (exception)
├── execute_direct_grant() (main entry)
│   ├── Validation phase
│   └── Entitlement grant (one row per unit)
└── Helpers for hall-pass/privilege handling
```

### Testing Requirements

- Teacher grant creates EntitlementEvent with acquisition_type="GRANT"
- Idempotency: replay returns same result
- Hall-pass grants don't create mutable balance counters
- Bulk grants: one row per unit, all same correlation_id

### Unblocked Routes (2)

- `/admin/student/<seat_id>/adjust-hall-pass-entitlements` (POST)
- `/admin/students/bulk-adjust-hall-pass-entitlements` (POST)

---

## IV. FEAT-STOR-002: Entitlement Lifecycle Transition (v2.0)

**Authority:** `docs/FEATURE-EXECUTION/FEAT-STOR-002_ENTITLEMENT_LIFECYCLE_TRANSITION.md` (v2.0)

### Specification Highlights

**Handles terminal events:**
- `CONSUMED` — entitlement exercised (Store-owned or cross-domain)
- `EXPIRED` — validity period ended
- `REVOKED` — lawfully withdrawn

**Key Rules:**
1. Never mutate original grant row (immutable history)
2. Cross-domain consumption: don't duplicate (e.g., hall-pass consumed by Productivity domain, don't create Store CONSUMED)
3. Rejection of delayed-use: writes REVOKED (not CONSUMED), entitlement returned
4. Revocation rules by acquisition_type:
   - `PURCHASE`: requires lawful Ledger reversal/refund
   - `GRANT`: teacher can revoke if unused
   - `PERK`: policy-dependent, generally non-revocable

### Consumption Paths

#### A. Store-Owned Consumption
```python
consume_entitlement(
  entitlement_id=<uuid>,
  class_id=ctx.class_id,
  actor_seat_id=ctx.seat_id,
  # Creates CONSUMED event
)
```

#### B. Cross-Domain Consumption
```python
# FEAT-STOR-002 detects:
# - Hall-pass consumed by HallPassLog (Productivity domain creates truth)
# - Insurance claim consumed by InsuranceClaim (Store creates terminal event but doesn't duplicate)
# 
# Read-only projection: entitlement no longer available because cross-domain event exists
```

#### C. Expiration
```python
expire_entitlements(
  class_id=...,
  product_id=...,  # Optional: expire all of this product
  reference_time_utc=canonical_temporal_resolver(),
)
```

### File Structure

```
app/feats/entitlement_lifecycle_feat.py  (NEW)
├── LifecycleResult (dataclass)
├── LifecycleError (exception)
├── consume_entitlement()
├── expire_entitlements()
├── revoke_entitlement()
├── validate_entitlement_state()
└── Helpers for cross-domain detection
```

### Testing Requirements

- Consume: creates CONSUMED event, no grant mutation
- Revoke: requires authority validation (teacher can revoke GRANT, but PURCHASE needs Ledger reversal)
- Insurance non-revocable: cannot revoke INSURANCE entitlements
- Cross-domain: detect hall-pass in HallPassLog, don't create duplicate CONSUMED
- Expiration: calendar-based boundary (use canonical_temporal_resolver)
- Idempotency: replay doesn't create duplicate terminal events

### Unblocked Routes (3)

- `/api/use-item` (POST) — delayed-use item redemption request
- `/api/approve-redemption` (POST) — consume on approval
- `/api/reject-redemption` (POST) — revoke on rejection (entitlement returned)

---

## V. FEAT-STOR-003: Insurance Claim Lifecycle (v2.0)

**Authority:** `docs/FEATURE-EXECUTION/FEAT-STOR-003_INSURANCE_CLAIM_LIFECYCLE.md` (v2.0)

### Specification Highlights

**Two-phase lifecycle:**

**Phase 1: Submission**
```
Student submits claim → 
  Structural validation (reject if malformed) →
  Policy evaluation (record ineligibility on pending action, don't reject) →
  Create pending_actions row
```

**Phase 2: Adjudication (Teacher)**
```
Teacher reviews pending_actions →
  Revalidate entitlement + claim subject →
  Approve: write CONSUMED event + coordinate Ledger/Payroll compensation →
  Reject: write CONSUMED event (payload shows rejection) + delete pending_actions (no compensation)
```

### Key Rules

1. **Submission creates pending_actions**, not a terminal event
2. **Both approved and rejected claims write CONSUMED** (payload distinguishes outcome)
3. **Rejection preserves entitlement** (no refund unless policy requires)
4. **Coverage cancellation is prospective** (doesn't expire existing coverage early)
5. **Claim allowance is derived** (never persisted as `claims_remaining`)

### Claim Subjects

- **Transaction insurance**: claimed `transaction_id` for reimbursement
- **Productivity insurance**: claimed class-local `date[]` for payroll credit
- **Non-monetary insurance**: policy-defined subject

### File Structure

```
app/feats/insurance_claim_feat.py  (NEW)
├── ClaimSubmissionResult (dataclass)
├── ClaimDecisionResult (dataclass)
├── ClaimError (exception)
├── submit_insurance_claim()  # Phase 1: Creates pending_actions
├── adjudicate_insurance_claim()  # Phase 2: Resolves pending action
├── validate_claim_subject()
├── validate_claim_eligibility()
└── Helpers for policy validation
```

### Testing Requirements

- Submission: creates pending_actions with typed payload
- Policy ineligibility: recorded on pending action, doesn't prevent submission
- Approval: writes CONSUMED, coordinates Ledger/Payroll, deletes pending action
- Rejection: writes CONSUMED (rejected outcome), no Ledger effect, deletes pending action
- Idempotency: retry submission gets same pending action; retry decision is idempotent
- Coverage window: active entitlement permits claim even if coverage would expire before review

### Unblocked Routes (2)

- `/student/insurance/claim/<policy_id>` (GET/POST) — claim submission
- `/admin/insurance/claim/<claim_id>` (GET/POST) — claim adjudication

---

## VI. Read Services (Entitlement Queries)

**Authority:** DOM-STORE-001 v4.0 §XI (Projection Rules)

### Required Read Services

```python
# app/services/entitlement_read_service.py (NEW)

def get_entitlement_balance(
  seat_id: int,
  class_id: str,
  entitlement_type: str,  # HALL_PASS, INSURANCE, etc.
  product_id: int | None = None,
  reference_time_utc: datetime | None = None,
) -> int:
  """Derive available entitlements from EntitlementEvent history."""
  # Count GRANTED events minus terminal events (CONSUMED, EXPIRED, REVOKED)
  # Filter by reference_time_utc for expiration windows

def is_entitlement_exercisable(
  entitlement_id: str,
  class_id: str,
  reference_time_utc: datetime | None = None,
) -> bool:
  """Check if entitlement has no terminal event yet."""

def get_entitlement_history(
  seat_id: int,
  class_id: str,
  product_id: int | None = None,
  limit: int = 100,
) -> list[dict]:
  """Return EntitlementEvent rows for audit/display."""

def derive_claim_allowance(
  entitlement_id: str,
  class_id: str,
  policy_config: dict,
  reference_time_utc: datetime,
) -> int:
  """Derive remaining claims from policy + history."""
  # Never query claims_remaining counter (doesn't exist)
  # Derive from policy rules + CONSUMED events
```

### Testing Requirements

- Balance derivation: sum(GRANTED) - sum(CONSUMED, EXPIRED, REVOKED)
- Exercisable: no terminal event + not expired (per policy window)
- History: returns all events in order (for audit trails)
- Claim allowance: policy-specific derivation (e.g., max 3 per month)

---

## VII. Phase 3 Execution Plan

### Week 1: FEAT-STOR-001 + FEAT-STOR-004

**Goal:** Get purchase and direct grant paths working; unblock 5 routes

**Tasks:**
1. Implement FEAT-STOR-001 v3.0 (`execute_store_purchase()`)
   - Validation → Ledger → EntitlementEvent writes (N rows for quantity N)
   - Instant-use coordination
   - Write comprehensive tests

2. Implement FEAT-STOR-004 v1.0 (`execute_direct_grant()`)
   - Teacher validation → EntitlementEvent writes
   - Hall-pass special handling
   - Write tests

3. Wire routes:
   - `/api/purchase-item` → FEAT-STOR-001
   - `/student/insurance/purchase/<policy_id>` → FEAT-STOR-001
   - `/admin/student/<id>/adjust-hall-pass-entitlements` → FEAT-STOR-004
   - `/admin/students/bulk-adjust-hall-pass-entitlements` → FEAT-STOR-004

4. Run smoke tests; verify Flask loads

**Success criteria:**
- `pytest -k "stor_001 or stor_004"` passes
- Routes load without import errors
- Purchase creates N EntitlementEvent rows with shared correlation_id

---

### Week 2: FEAT-STOR-002

**Goal:** Enable redemption and lifecycle management; unblock 3 routes

**Tasks:**
1. Implement FEAT-STOR-002 v2.0
   - `consume_entitlement()` — Store-owned consumption
   - `expire_entitlements()` — calendar-based expiration
   - `revoke_entitlement()` — revocation with authority checks
   - Cross-domain detection (hall-pass in HallPassLog)
   - Write comprehensive tests

2. Wire routes:
   - `/api/use-item` → FEAT-STOR-002 (consume)
   - `/api/approve-redemption` → FEAT-STOR-002 (consume)
   - `/api/reject-redemption` → FEAT-STOR-002 (revoke)

3. Implement entitlement read services
   - `get_entitlement_balance()`
   - `is_entitlement_exercisable()`
   - Tests

4. Update dashboard/view models to use new read services

**Success criteria:**
- `pytest -k "stor_002"` passes
- Redemption flows work (approve consumes, reject revokes)
- Hall-pass cross-domain detection works

---

### Week 3: FEAT-STOR-003 + Insurance Routes

**Goal:** Enable insurance claim workflow; unblock 2 routes

**Tasks:**
1. Implement FEAT-STOR-003 v2.0
   - `submit_insurance_claim()` — creates pending_actions
   - `adjudicate_insurance_claim()` — approval/rejection path
   - Claim subject validation (transaction vs. productivity)
   - Ledger/Payroll coordination
   - Write comprehensive tests

2. Implement insurance eligibility validation with **canonical tools**:
   - Replace deleted `insurance_eligibility.py` with new validation using `canonical_temporal_resolver`
   - Waiting period check (canonical time)
   - Claim window validation
   - Delay-use rule (query EntitlementEvent.event_type == CONSUMED)

3. Wire routes:
   - `/student/insurance/claim/<policy_id>` → FEAT-STOR-003 (submit)
   - `/admin/insurance/claim/<claim_id>` → FEAT-STOR-003 (adjudicate)

4. Fix `transaction_void_feat.py`
   - Query EntitlementEvent instead of deleted service
   - Use canonical_temporal_resolver for timestamps

5. Update insurance view templates
   - Read EntitlementEvent for coverage status
   - Derive claim allowance using new read services

**Success criteria:**
- `pytest -k "stor_003"` passes
- Insurance claim submission creates pending_actions
- Approval writes CONSUMED + coordinates compensation
- Rejection writes CONSUMED (rejected outcome)
- All eligibility checks use canonical tools

---

### Week 4: Integration + Cleanup

**Goal:** All routes load; full integration testing

**Tasks:**
1. Verify all 12 broken imports are resolved
2. Fix `app/scheduled_tasks.py` (insurance renewal task)
3. Fix `app/services/store_service.py` (strip dead imports)
4. Run full Flask app test: `pytest tests/`
5. Spot-check view models (dashboard, insurance view, store catalog)
6. Document any edge cases discovered

**Success criteria:**
- Flask loads without import errors
- Full test suite runs
- All 4 FEATs have passing tests
- Routes don't throw 500 errors on load

---

## VIII. Success Criteria (Phase 3 Complete)

✓ All 4 FEATs implemented and tested  
✓ All 12 broken imports resolved  
✓ All 9 unblocked routes wired and functional  
✓ Read services queryable and correct  
✓ New canonical tool usage enforced (no non-canonical temporal/identity utilities)  
✓ Schema writes to EntitlementEvent + PendingAction only  
✓ Database clean, no legacy model references  
✓ Flask app loads without errors  
✓ Tests demonstrate new schema working end-to-end  

---

## IX. Risk Factors

### High Risk
- **Ledger coordination (FEAT-STOR-001)**: Purchase FEAT coordinates with the canonical ledger path; tight coupling remains
- **Cross-domain detection (FEAT-STOR-002)**: Hall-pass consumption by other domain; must not duplicate
- **Canonical tool adoption**: All temporal/identity code must use canonical resolvers (not optional)

### Medium Risk
- **Insurance eligibility rewrite**: Complex policy validation; must not introduce bugs during rewrite
- **Idempotency**: All FEATs must handle replay correctly; needs careful testing

### Mitigation
- Start with unit tests for each FEAT before wiring routes
- Test cross-domain scenarios explicitly (e.g., hall-pass consumed by Productivity)
- Code review for canonical tool usage (mandatory gate)
- Integration tests covering happy path + edge cases

---

## X. Next Immediate Steps

1. **Historical note:** the FEAT files now exist in the live tree
   - `app/feats/store_purchase_feat.py`
   - `app/feats/direct_entitlement_grant_feat.py`
   - `app/feats/entitlement_lifecycle_feat.py`
   - `app/feats/insurance_claim_feat.py`

2. **Create read service file** (empty stubs)
   - `app/services/entitlement_read_service.py`

3. **Verification checkpoint**
   - Validation phase implemented
   - Ledger coordination implemented
   - EntitlementEvent writes implemented
   - Tests in place

---

**Status:** Historical roadmap; current implementation proceeds from this baseline

Manifest: STORE_ENTITLEMENTS_DEMOLITION_MANIFEST_2026-07-27.md  
Report: STORE_ENTITLEMENTS_DEMOLITION_REPORT_2026-07-27.md  
Authority: DOM-STORE-001 v4.0, FEAT-STOR-001/002/003/004
