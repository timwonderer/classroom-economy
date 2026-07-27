# Store and Entitlements Domain Correctness Audit
## SOP-DEV-002 Compliance Verification

| Reference | Value |
|-----------|-------|
| **Domain** | Store and Entitlements (DOM-STORE-001 v3.0) |
| **Audit Date** | 2026-07-26 |
| **Authority** | DOM-STORE-001 v3.0 Effective 2026-07-22 |
| **SOP** | SOP-DEV-002 v1.0 (10-phase reconstruction audit) |
| **Auditor** | Correctness verification against canonical spec |

---

## I. Executive Summary

The Store and Entitlements domain contains **4 critical canonical violations** and **1 warning** when compared against DOM-STORE-001 v3.0. The core mutation FEAT (FEAT-STOR-001) and service primitives are correctly implemented, but legacy persistence and support tables violate immutable facts principles.

**Status: BLOCKED PENDING REMEDIATION**

---

## II. Violations Summary

### VIOLATION 1: Mutable Balance Tracking via EntitlementEvent (CRITICAL)

**Authority:** DOM-STORE-001 §IV Consumer Rules + §V.C Derived State

**Specification:**
> "Consumers SHALL NOT persist `uses_remaining`, `bundle_remaining`, or equivalent mutable entitlement balances."
> "The following SHALL be derived and SHALL NOT be persisted as canonical entitlement truth: entitlement quantity, remaining uses, entitlement balance..."

**Actual Implementation:**

File: `app/services/entitlement_service.py`

```python
def get_hall_pass_balance(seat_id: int, class_id: str) -> int:
    """Return the derived hall pass balance for a seat in a class."""
    return max(
        0,
        db.session.query(sa.func.sum(EntitlementEvent.quantity_delta))  # ← MUTABLE COUNTER
        .filter_by(seat_id=seat_id, class_id=class_id)
        .scalar()
        or 0,
    )
```

**Problem:**
- The `EntitlementEvent` table has a `quantity_delta` field used to track aggregate balances
- Balance is derived by summing `quantity_delta` values (line 33-36)
- This pattern is equivalent to persisting `uses_remaining` — exactly what the spec forbids
- Mutat side effects: `grant_hall_passes()` creates events with `quantity_delta=1`, `remove_hall_passes()` with `quantity_delta=-1`

**Correct Pattern (Per Spec §XI.A):**
- Entitlements grants are atomic rows (one row = one pass)
- Availability derived from: grant exists + no terminal event in entitlement_consumptions
- Cross-domain consumption (hall_pass_logs) references exact entitlement_id

**Evidence of Bypass:**
- `grant_hall_passes()` (line 44-73) creates EntitlementEvent rows, not Entitlement rows
- Hall pass supply is managed through quantity_delta arithmetic, not atomic rows

**Severity:** CRITICAL — Violates foundational immutable facts model

**Remediation Required:** Replace EntitlementEvent with canonical Entitlement + EntitlementConsumption pattern

---

### VIOLATION 2: Legacy RedemptionEvent Table (CRITICAL)

**Authority:** DOM-STORE-001 §VI Canonical Schema Declaration

**Specification:**
> "The following legacy or superseded persistence concepts are not part of the v3 canonical Store and Entitlements contract: `redemption_events`"
> "Disposition: replace with `entitlement_consumptions` for Store-and-Entitlements-owned terminal events."

**Actual Implementation:**

File: `app/models.py` (lines 902-937)

```python
class RedemptionEvent(db.Model):
    __tablename__ = 'redemption_events'
    id = db.Column(db.String(36), primary_key=True, ...)
    entitlement_id = db.Column(db.String(36), db.ForeignKey('entitlements.entitlement_id'), ...)
    action = db.Column(db.Enum(RedemptionEventAction, ...), ...)  # REQUEST, APPROVED, REJECTED
```

**Still In Use:**

File: `app/services/store_entitlement_service.py` (lines 516-536)

```python
def derive_display_status(entitlement_id: str) -> str:
    """Derive a human-readable display status for an entitlement."""
    # ...checks for RedemptionEvent.REQUEST without APPROVED/REJECTED
    has_request = db.session.query(
        RedemptionEvent.query.filter(
            RedemptionEvent.entitlement_id == entitlement_id,
            RedemptionEvent.action == RedemptionEventAction.REQUEST,
        ).exists()
    ).scalar()
```

**Problem:**
- RedemptionEvent is explicitly listed as "legacy or superseded" in the canonical spec
- Still persisted in database and queried in derive_display_status()
- Used to track REQUEST/APPROVED/REJECTED workflow
- Creates a second workflow table alongside canonical InsuranceClaim (which has same semantics)

**Correct Pattern (Per Spec §VII.B):**
- Terminal lifecycle recorded in EntitlementConsumption with disposition CONSUMED/EXPIRED/REVOKED
- Mutable workflow (REQUEST→APPROVED/REJECTED) uses InsuranceClaim (for insurance) or immediate CONSUMED (for store items)

**Severity:** CRITICAL — Persists unauthorized table that should be deleted per Phase 9

---

### VIOLATION 3: StorePurchase Table (CRITICAL)

**Authority:** DOM-STORE-001 §VI Canonical Schema Declaration + §XIX Reconstruction Disposition

**Specification:**
> "The following legacy or superseded persistence concepts are not part of the v3 canonical Store and Entitlements contract: `store_purchases`"
> "Disposition: collapse into atomic `entitlements` plus lawful Ledger purchase history."

**Actual Implementation:**

File: `app/models.py` (lines 867-889)

```python
class StorePurchase(db.Model):
    __tablename__ = 'store_purchases'
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, ...)
    quantity = db.Column(db.Integer, nullable=False, default=1)  # QUANTITY PERSISTED
    price_at_purchase = db.Column(db.Numeric(...), ...)
    total_price = db.Column(db.Numeric(...), ...)
    status = db.Column(db.String(20), nullable=False, default='purchased')  # MUTABLE STATUS
    ledger_tx_id = db.Column(db.Integer, ...)
    expiry_date = db.Column(db.DateTime(...), ...)
```

**Still In Use:**

- `app/routes/admin.py` — multiple queries for StorePurchase
- `app/routes/api.py` — bridge_purchase lookups
- `app/utils/deletion.py` — class deletion cascade
- `app/utils/student_deletion.py` — student cascade deletion

**Problem:**
- StorePurchase persists `quantity`, `status`, `expiry_date` — information that should be derived
- Quantity should be represented by Entitlement row count, not a single field
- Status transitions (PURCHASED → REDEEMED) are mutable state persisted as purchase authority
- Creates a second purchase/grant authority parallel to canonical Entitlements

**Correct Pattern (Per Spec §IX.A):**
- Five late-work passes purchase = five distinct Entitlement rows
- Quantity is row cardinality
- Expired status is derived from class configuration + canonical temporal resolver
- Ledger transaction is the purchase authority

**Severity:** CRITICAL — Forbidden persistence explicitly called out in Phase 9 remediation

---

### VIOLATION 4: StoreItem/StoreItemVisibility Ownership (CRITICAL)

**Authority:** DOM-STORE-001 §VI Canonical Schema Declaration + §XII.A Cross-Domain Contracts

**Specification:**
> "Store item and insurance definitions belong to the Class Configuration domain. Store and Entitlements SHALL treat these values as configuration inputs, not domain-owned state."

**Actual Implementation:**

File: `app/models.py` (lines 730-821)

```python
class StoreItem(db.Model):
    __tablename__ = 'store_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, ...)  # teacher
    class_id = db.Column(db.String(36), ...)
    name = db.Column(db.String(100), ...)
    price = db.Column(db.Numeric(...), ...)
    tier = db.Column(db.String(20), ...)
    item_type = db.Column(db.String(20), ...)  # immediate, delayed, collective
    inventory = db.Column(db.Integer, ...)
    # ... more than 20 columns of configuration
```

File: `app/models.py` (lines 843-854)

```python
class StoreItemVisibility(db.Model):
    __tablename__ = 'store_item_visibility'
    id = db.Column(db.Integer, primary_key=True)
    store_item_id = db.Column(db.Integer, db.ForeignKey('store_items.id'), ...)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'), ...)
```

**In Store/Entitlements Service:**

File: `app/services/store_service.py` (lines 78-87)

```python
def create_store_item(*, user_id: int, class_id: str, **fields) -> StoreItem:
    """Create and flush a canonical store item row."""
    item = StoreItem(user_id=user_id, class_id=class_id, **fields)
    db.session.add(item)
    db.session.flush()
    return item
```

**Problem:**
- StoreItem is created/mutated/configured within Store/Entitlements domain (create_store_item, deactivate_store_item)
- But canonical spec says Class Configuration owns definitions
- Store/Entitlements should receive item definitions as read-only configuration input
- No evidence of a separate Class Configuration domain owning these

**Severity:** CRITICAL — Boundary violation; ownership is domain-scoped

---

### WARNING 1: Historical Hall-Pass Implementation Bypasses Canonical Patterns

**Authority:** DOM-STORE-001 §XI Consumption Authority + §XII.C Cross-Domain Contracts

**Description:**

The hall pass entitlement uses EntitlementEvent tracking instead of canonical Entitlement + EntitlementConsumption + cross-domain hall_pass_logs reference pattern.

File: `app/services/entitlement_service.py` (lines 149-173)

```python
def consume_hall_pass(
    seat_id: int,
    class_id: str,
    *,
    trigger_id: str,
) -> tuple[EntitlementEvent, int]:
    """Consume one hall pass from an existing grant and return (event, balance)."""
    grant = _available_hall_pass_grant(seat_id, class_id)
    if grant is None:
        raise ValueError("No available hall-pass entitlement grant to consume")
    
    event = EntitlementEvent(
        seat_id=seat_id,
        class_id=class_id,
        quantity_delta=-1,  # ← MUTABLE COUNTER UPDATE
        event_type="CONSUME",
        trigger_id=trigger_id,
    )
```

**Correct Pattern (Per Spec §XI.B, §XII.C):**
- Hall-pass entitlement is created in Store/Entitlements
- When exercised (consumed), authoritative record is in Productivity domain's `hall_pass_logs` table
- hall_pass_logs references exact `entitlement_id`
- Store/Entitlements derives availability by checking: (entitlement exists) AND (no hall_pass_logs entry)

**Severity:** WARNING — System works but violates architectural pattern

---

## III. Audit Findings by SOP-DEV-002 Phase

### Phase 0: Boundary Definition ✅ PASS

**Scope:** Store/Entitlements owns atomic entitlement grants, consumptions, and insurance workflows.

- ✅ Entitlements table correctly defined
- ✅ EntitlementConsumption table correctly defined
- ✅ InsuranceClaim table correctly defined
- ❌ StoreItem ownership unclear (should be Class Configuration)
- ❌ Extra tables (StorePurchase, RedemptionEvent, EntitlementEvent) outside canonical scope

### Phase 1: Truth Definition ❌ FAIL

**Authority:** Immutable facts must be persisted exactly as spec defines.

- ✅ Entitlements records grants (immutable, append-only)
- ✅ EntitlementConsumption records terminal facts (immutable)
- ✅ InsuranceClaim records workflow (mutable workflow table — correct)
- ❌ EntitlementEvent persists mutable quantity_delta (forbidden)
- ❌ StorePurchase persists quantity, status (forbidden)
- ❌ RedemptionEvent persists REQUEST/APPROVED/REJECTED (forbidden)

### Phase 2: Persistence ❌ FAIL

**Authority:** Only canonical tables and proper foreign keys.

**Current Migrations Status:**

```bash
grep -l "entitlement\|store_purchase\|redemption_event" migrations/versions/*.py
```

- Migrations for entitlements table: exist and proper
- Migrations for entitlement_consumptions table: exist and proper
- Migrations for insurance_claims table: exist and proper
- ❌ Migrations for StorePurchase: exist but should be deleted
- ❌ Migrations for RedemptionEvent: exist but should be deleted
- ❌ Migrations for EntitlementEvent: exist but should be deleted

**Idempotency:** All migrations appear to have idempotency checks (need full review)

### Phase 3: Primitives ✅ PASS

**File:** `app/services/store_entitlement_service.py`

- ✅ `grant_entitlement()` — creates single atomic row per call
- ✅ `grant_entitlements_bulk()` — creates N rows for N units (correct)
- ✅ `consume_entitlement()` — writes CONSUMED disposition
- ✅ `expire_entitlement()` — writes EXPIRED disposition
- ✅ `revoke_entitlement()` — writes REVOKED disposition (with provenance checks)
- ✅ `list_available_entitlements()` — derives from grants minus terminations
- ✅ `get_entitlement_balance()` — pure projection, never persisted
- ✅ Insurance claim primitives (submit, approve, reject)
- ✅ All primitives use canonical_temporal_resolver
- ⚠️ `derive_display_status()` references RedemptionEvent (legacy)

### Phase 4: Mutation Boundary ✅ PASS

**File:** `app/feats/store_purchase_feat.py`

- ✅ FEAT-STOR-001 wraps all mutations
- ✅ Phase-based execution (validation → ledger → grants → consumption)
- ✅ Idempotency support via correlation_id
- ✅ Proper FEAT context via @requires_feat_context decorator
- ✅ Coordinates with Ledger domain for financial authority
- ✅ Calls canonical primitives (grant_entitlement, consume_entitlement)
- ✅ Creates atomic entitlements for each unit (correct per §IX.A)
- ✅ No direct db.session.add of StorePurchase (good)

**But:**
- ⚠️ Still has reference to StorePurchase in bridge idempotency check (line 118)

### Phase 5: Read Models ✅ PASS

**Status:** No view models used; raw queries are pure reads per spec

- ✅ store_entitlement_service primitives are read-only
- ✅ get_entitlement_balance() is pure projection
- ✅ list_available_entitlements() derives from canonical facts
- ✅ No mutable view models persisted

### Phase 6: Surface Inventory ⚠️ INCOMPLETE

**Routes using Store/Entitlements:**

Identified files:
- `app/routes/admin.py` — store management, purchase approvals
- `app/routes/student.py` — student store browsing (assumed)
- `app/routes/api.py` — API endpoints for purchases/claims

**Status:** Need full inventory of which routes reference StorePurchase/RedemptionEvent vs canonical tables

### Phase 7: Rewire ❌ FAIL

**Status:** Routes not fully rewired to canonical FEAT/primitive boundaries

**Evidence:**
- StorePurchase direct queries in routes (not fully wrapped in FEAT calls)
- RedemptionEvent still queried in derive_display_status()
- EntitlementEvent still mutated by entitlement_service functions

### Phase 8: Verify ⚠️ INCOMPLETE

**Test Status:** Need full test suite run to assess

Early findings:
- `tests/dom/entitlement/test_store.py` — Schema tests PASS
- `tests/dom/entitlement/test_collective_goal_progress.py` — Multiple FAILED
- `tests/dom/entitlement/test_redemption_disposition.py` — MIXED (some pass, some fail)

### Phase 9: Legacy Deletion ❌ FAIL

**Status:** No legacy tables have been deleted

**Required Deletions (Per Spec §VI, §XIX):**
- [ ] `store_purchases` table and all references
- [ ] `redemption_events` table and all references
- [ ] `entitlement_events` table (if truly only for hall passes; move to Productivity domain)
- [ ] `StorePurchase` model and ORM relationships
- [ ] `RedemptionEvent` model and ORM relationships
- [ ] Helper functions that bypass canonical primitives

### Phase 10: Audit ❌ INCOMPLETE

**Status:** This audit is incomplete pending remediation of violations 1-4

---

## IV. Critical Remediation Required

### Must Do Before Production Readiness

1. **ELIMINATE EntitlementEvent for hall-pass balance**
   - Move hall-pass entitlements to canonical Entitlement + EntitlementConsumption
   - OR move to Productivity domain if hall passes are productivity-domain-owned
   - Update `entitlement_service.py` to use canonical patterns

2. **DELETE RedemptionEvent table**
   - Remove from models.py
   - Remove all queries from store_entitlement_service.py
   - Delete associated migration
   - Replace flow with canonical terminal events (EntitlementConsumption)

3. **DELETE StorePurchase table**
   - Remove from models.py
   - Remove all route references
   - Remove from deletion utilities
   - Delete associated migrations
   - Verify FEAT-STOR-001 uses only Entitlement + Ledger

4. **Clarify StoreItem ownership**
   - Either move to Class Configuration domain
   - OR create explicit contract defining Store/Entitlements as configuration authority
   - Document in cross-domain contract (DOM-STORE-001 §XII.A)

---

## V. What's Working Correctly

The following DO comply with DOM-STORE-001 v3.0:

1. **Canonical Schema Tables**
   - entitlements — atomic grants ✅
   - entitlement_consumptions — terminal facts ✅
   - insurance_claims — mutable workflow ✅

2. **Mutation Layer**
   - FEAT-STOR-001 correctly coordinates grants ✅
   - Idempotency enforcement ✅
   - Ledger coordination ✅

3. **Query Primitives**
   - Pure reads derive from canonical facts ✅
   - No persisted balances in core primitives ✅
   - get_entitlement_balance() is projection ✅

4. **Multi-Tenancy**
   - class_id scoping enforced on all canonical tables ✅
   - Foreign key constraints proper ✅

5. **Insurance Workflow**
   - InsuranceClaim table structure correct ✅
   - Mutable workflow state appropriate ✅
   - submit_insurance_claim/approve/reject primitives correct ✅

---

## VI. Dependency on Other Domain Completion

**Blocked by:**
1. Class Configuration domain specification and implementation (owns StoreItem definitions)
2. Productivity and Payroll domain for hall-pass consumption cross-domain reference

**Blocking:**
- Student routes that display store/entitlements
- Admin routes that manage store configuration
- Tests that validate store/insurance functionality

---

## VII. Conclusion

**Status: REJECTION — CRITICAL VIOLATIONS PRESENT**

The Store and Entitlements domain has correct canonical primitives and FEAT layer, but is undermined by three legacy tables (EntitlementEvent, RedemptionEvent, StorePurchase) that violate DOM-STORE-001 v3.0's immutable-facts model and forbidden-persistence rules.

**Next Steps:**
1. Delete EntitlementEvent (move hall-pass to canonical or Productivity domain)
2. Delete RedemptionEvent (use EntitlementConsumption instead)
3. Delete StorePurchase (collapse into Entitlement + Ledger)
4. Clarify StoreItem/StoreItemVisibility ownership
5. Rerun full test suite
6. Resubmit for Phase 10 audit

**Estimated Remediation Effort:** 2-3 hours (mostly deletions and route rewiring)

---

**Audit Report Generated:** 2026-07-26  
**Authority:** DOM-STORE-001 v3.0 Canonical Spec  
**Next Review:** Post-remediation Phase 10 Certification Audit
