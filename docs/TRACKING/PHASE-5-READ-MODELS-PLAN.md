# Phase 5: Read Models and Projections — Store/Entitlements Domain

**Date**: 2026-07-28  
**Status**: 🔜 PHASE 5 READY TO BEGIN  
**Authority**: SOP-DEV-002 Phase 5 + DOM-STORE-001 v3.0  
**Prior Phase**: Phase 4 (Legal Mutation Boundary) ✅ COMPLETE

---

## I. Purpose

Phase 5 defines the lawful read surfaces needed by the application.

This phase classifies and implements:
- Authoritative domain reads (single source of truth from canonical tables)
- Derived projections (computed from entitlement events)
- View models (aggregates for display)
- Cross-domain aggregates (coordinated reads with Ledger, Obligations, etc.)
- Display-only formatting (rendering, localization, etc.)

---

## Important Note on Pending Actions

**Pending Actions workflows are NOT part of Phase 5 read models** (see PENDING_ACTIONS_AUDIT_2026-07-28.md).

The `pending_actions` table is canonical persistence with documented workflows (insurance claims, delayed-use redemptions, hall-pass requests), but the FEATs that would write to it are not yet implemented. 

**Phase 5 should NOT**:
- Implement read projections for pending_actions workflows
- Assume or infer workflow semantics
- Build view models that depend on unimplemented FEATs

**Phase 5 can proceed with**: Read models for entitlements, purchases, and statuses that do not depend on pending_actions.

---

## II. Read Surface Inventory

### Category A: Authoritative Domain Reads

These query `entitlement_events` table directly, retrieving immutable facts.

#### Read 1: Get Entitlement by ID

**Purpose**: Look up single entitlement's full event history  
**Source Table**: `entitlement_events`  
**Scope**: Class-scoped (cannot cross classes)  
**Query Pattern**:
```python
def get_entitlement_history(entitlement_id: str, class_id: str) -> List[EntitlementEvent]:
    """Return all events (GRANTED, CONSUMED, EXPIRED, REVOKED) for one entitlement lineage."""
    return db.session.query(EntitlementEvent).filter_by(
        entitlement_id=entitlement_id,
        class_id=class_id
    ).order_by(EntitlementEvent.timestamp.asc()).all()
```

**Used By**: 
- Entitlement detail view (audit trail)
- Cross-domain consumers (Insurance, Obligations, Hall Pass)
- Ledger reconciliation

**Purity**: ✅ Read-only (queries only)

---

#### Read 2: Get Granted Entitlements for Seat+Product

**Purpose**: Find all active (GRANTED, not CONSUMED/EXPIRED/REVOKED) entitlements for student+product  
**Source Table**: `entitlement_events`  
**Scope**: Class-scoped  
**Query Pattern**:
```python
def get_active_entitlements(
    seat_id: int,
    class_id: str,
    product_id: int | None = None
) -> List[EntitlementEvent]:
    """Return all non-terminal GRANTED events for seat+product (optionally filtered)."""
    query = db.session.query(EntitlementEvent).filter_by(
        target_seat_id=seat_id,
        class_id=class_id,
        event_type='GRANTED'
    )
    if product_id:
        query = query.filter_by(product_id=product_id)
    return query.all()
```

**Used By**:
- Balance calculations (how many hall passes available)
- Purchase limit checks (existing count)
- Entitlement status displays

**Purity**: ✅ Read-only

---

#### Read 3: Get Policy by UUID

**Purpose**: Resolve policy configuration (already in Phase 3 via StorePolicyResolver)  
**Source**: `StorePolicyResolver.resolve_store_item(policy_uuid)`  
**Scope**: Returns resolved policy; validation includes class scope check  
**Purity**: ✅ Read-only (+ validation)

---

### Category B: Derived Projections

These compute state from entitlement events without persisting.

#### Projection 1: Entitlement Consumption Status

**Purpose**: Determine if entitlement is GRANTED, CONSUMED, EXPIRED, REVOKED, or IN-PROGRESS  
**Source**: Query `entitlement_events` for all events of one entitlement_id, examine terminal events  
**Formula**:
```python
def get_entitlement_status(entitlement_id: str, class_id: str) -> str:
    """Derive canonical status from event history."""
    history = get_entitlement_history(entitlement_id, class_id)
    
    # Check for terminal events in order of precedence
    for event in history:
        if event.event_type == 'CONSUMED':
            return 'CONSUMED'
        elif event.event_type == 'EXPIRED':
            return 'EXPIRED'
        elif event.event_type == 'REVOKED':
            return 'REVOKED'
    
    # If no terminal event, must be GRANTED
    granted_events = [e for e in history if e.event_type == 'GRANTED']
    if granted_events:
        return 'GRANTED'
    
    return 'UNKNOWN'  # Should not reach if data is well-formed
```

**Used By**: 
- UI display (show entitlement as available/used)
- Availability checks (can this be consumed?)
- Reports (how many in each status)

**Purity**: ✅ Pure (deterministic from immutable events)

---

#### Projection 2: Hall Pass Balance for Seat+Class

**Purpose**: Derive how many hall passes are available for a student  
**Source**: Count GRANTED events for product_id=hall_pass, subtract CONSUMED/EXPIRED  
**Formula**:
```python
def get_hall_pass_balance(seat_id: int, class_id: str) -> int:
    """Derive available hall passes from granted - consumed."""
    # Count active (GRANTED only) hall pass entitlements
    active = db.session.query(sa.func.count(EntitlementEvent.event_id)).filter_by(
        target_seat_id=seat_id,
        class_id=class_id,
        product_id=HALL_PASS_PRODUCT_ID,  # From policy config
        event_type='GRANTED'
    ).scalar()
    return active or 0
```

**Used By**:
- Dashboard display (show balance)
- Hall pass request validation (have enough available?)

**Purity**: ✅ Pure (deterministic from immutable events)

---

#### Projection 3: Purchase Count for Seat+Product

**Purpose**: Count how many times a student has purchased a product (for limits)  
**Source**: Count GRANTED events with acquisition_type='PURCHASE'  
**Formula**:
```python
def get_purchase_count(
    seat_id: int,
    class_id: str,
    product_id: int
) -> int:
    """Count acquisitions via PURCHASE for this seat+product."""
    return db.session.query(sa.func.count(EntitlementEvent.event_id)).filter_by(
        target_seat_id=seat_id,
        class_id=class_id,
        product_id=product_id,
        acquisition_type='PURCHASE',
        event_type='GRANTED'
    ).scalar() or 0
```

**Used By**:
- Purchase limit enforcement (can't buy more than X per semester)
- Student analytics (how many have they bought)

**Purity**: ✅ Pure

---

### Category C: View Models

Aggregates combining multiple reads for UI rendering.

#### View Model 1: EntitlementListView

**Purpose**: Show student all their entitlements in a list/table  
**Structure**:
```python
@dataclass
class EntitlementListView:
    entitlement_id: str
    product_id: int
    product_name: str  # From policy
    entitlement_type: str  # INSURANCE, PRIVILEGE, etc.
    acquisition_type: str  # PURCHASE, GRANT, PERK
    status: str  # GRANTED, CONSUMED, EXPIRED, REVOKED
    granted_at: datetime
    consumed_at: datetime | None
    granted_by_seat_id: int  # For attribution
```

**Source**:
1. Query EntitlementEvent (GRANTED events only)
2. For each, derive status (Projection 1)
3. Resolve product_name from StorePolicyResolver
4. Format dates and names

**Used By**: Student entitlements dashboard, student profile

**Purity**: ✅ Pure aggregation (no writes)

---

#### View Model 2: PolicyListView (Discoverable Policies)

**Purpose**: Show the canonical store policies defined for a class  
**Status**: ✅ UNBLOCKED — pure discovery is already authorized

**Primitive**: `StorePolicyResolver.list_store_policies(class_id)` returns canonical policy definitions for the class

**View Contract**:
- Use canonical policy definitions from the resolver
- Apply presentation ordering only in the view model
- Do not evaluate student eligibility, affordability, entitlement ownership, or class feature state

**Authority Needed**: None beyond `DOM-STORE-001` plus the pure discovery primitive

**Do Not Stub**: Keep business filtering out of the resolver primitive

---

#### View Model 3: PurchaseHistoryView

**Purpose**: Show student their purchase history with status  
**Structure**:
```python
@dataclass
class PurchaseHistoryView:
    purchase_date: datetime
    policy_uuid: str
    product_name: str
    quantity: int
    price_per_unit: Decimal
    total_price: Decimal
    entitlement_status: str  # GRANTED, CONSUMED, EXPIRED
    correlation_id: str  # For audit trail
```

**Source**:
1. Query EntitlementEvent filtered by acquisition_type='PURCHASE'
2. Group by correlation_id (linked events from one purchase)
3. Resolve policy and pricing from StorePolicyResolver
4. Derive statuses

**Used By**: Student purchase history page, receipts

**Purity**: ✅ Pure

---

### Category D: Cross-Domain Aggregates

Reads coordinated with other domains.

#### Aggregate 1: EntitlementWithLedgerContext

**Purpose**: Show entitlement status along with related Ledger transaction  
**Status**: 🔴 BLOCKED — Requires undefined cross-domain contract

**Blocker**: Ledger domain read API not yet defined

**Contract Gap**:
- Does Ledger expose query API for transactions by correlation_id?
- What's the exact schema for Ledger transactions?
- How to handle case where Ledger transaction is pending (async)?
- Who owns timeout/reconciliation when entries don't match?

**Resolution**: Requires Ledger domain API specification (outside Store scope)  
**Authority Needed**: Ledger domain read contract (Phase 5+ of Ledger reconstruction)

**Do Not Stub**: This aggregate cannot be built until Ledger coordination is implemented in FEAT-STOR-001 and Ledger exposes its read API.

---

#### Aggregate 2: StudentObligationWithEntitlements

**Purpose**: Show what obligations student has, plus any entitlements toward them  
**Domains**: Obligations + Store  
**Structure**:
```python
@dataclass
class StudentObligationWithEntitlements:
    obligation: ObligationView  # From Obligations domain
    entitlement_count: int  # How many entitlements toward this obligation
    remaining_needed: int  # obligation.target - entitlement_count
```

**Source**:
1. Get student obligations from Obligations domain
2. For each, query EntitlementEvent where product maps to obligation type
3. Calculate remaining

**Used By**: Student progress view, obligation dashboard

**Purity**: ✅ Pure (coordinated reads only)

---

### Category E: Display-Only Formatting

These format read results for rendering without adding logic.

#### Format 1: Entitlement Status Badge

**Purpose**: Render color-coded status badge  
**Logic**: Map status string to CSS class/icon
```python
def format_status_badge(status: str) -> dict:
    """Return badge styling for status."""
    styles = {
        'GRANTED': {'class': 'badge-success', 'label': 'Available'},
        'CONSUMED': {'class': 'badge-secondary', 'label': 'Used'},
        'EXPIRED': {'class': 'badge-warning', 'label': 'Expired'},
        'REVOKED': {'class': 'badge-danger', 'label': 'Revoked'},
    }
    return styles.get(status, {'class': 'badge-light', 'label': 'Unknown'})
```

**Purity**: ✅ Pure (no state)

---

## III. Phase 5 Deliverables

**Scope**: Build and test canonical read models and projections ONLY. Do NOT update routes.

### Deliverable 1: Entitlement Read Service

**File**: `app/services/entitlement_read_service.py` (verify/complete)

Must provide:
- ✅ `get_entitlement_history(entitlement_id, class_id)` (verify existing)
- ✅ `get_active_entitlements(seat_id, class_id, product_id=None)` (verify existing)
- ✅ `get_entitlement_status(entitlement_id, class_id)` (verify existing)
- 🔜 `get_hall_pass_balance(seat_id, class_id)` (implement)
- ✅ `get_purchase_count(seat_id, class_id, product_id)` (verify existing)
- 🔜 `get_active_rent_grant(seat_id, class_id)` (implement if needed)

**Testing**: Unit tests for each projection; verify purity and correctness

---

### Deliverable 2: View Model Builders

**Files**: `app/services/view_model_builders.py` (new or extend)

Must provide (implement only unblocked ones):
- ✅ `build_entitlement_list_view(seat_id, class_id)` → List[EntitlementListView]
- ✅ `build_policy_list_view(class_id)` — pure discovery + presentation ordering
- ✅ `build_purchase_history_view(seat_id, class_id)` → List[PurchaseHistoryView]
- 🔴 BLOCKED: `build_entitlement_with_ledger_context(entitlement_id, class_id)` — Requires Ledger read API

**Unblocked builders**: Must have unit tests verifying structure and data accuracy

**Blocked builders**: Report contract gap; do not stub or infer semantics

---

### Deliverable 3: Test Suite

**Files**: `tests/test_entitlement_read_service.py`, `tests/test_view_model_builders.py` (new)

Must test:
- Read service correctness (each projection with known data)
- View model builder structure and data extraction
- Purity of all reads (no side effects)
- Cross-domain reference handling (when applicable)

**No route/template tests in Phase 5** — Save for Phase 7 (rewiring)

---

## IV. Phase 5 Sequencing

**Important**: Phase 5 builds read models ONLY. Do NOT rewire routes or update templates. Routes are rewired in Phase 7 after Phase 6 application surface inventory.

### Stage 1: Read Service Completion

1. Audit existing `entitlement_read_service.py`
2. Verify all projections (status, balance, count) are correct and pure
3. Document each read's source, preconditions, and data freshness
4. Implement missing reads (hall_pass_balance, etc.)
5. Unit test all reads with known data

**Effort**: 2-4 hours  
**Blocking**: Nothing

**Do Not**: Update any routes or templates

---

### Stage 2: View Model Builders (Unblocked Only)

1. Define data classes for EntitlementListView, PurchaseHistoryView
2. Implement builders using read service (unblocked ones only)
3. Add comprehensive unit tests for each builder
4. Document builder contract (inputs, outputs, temporal semantics)
5. Report blocked builders with their contract gaps

**Unblocked Builders**:
- EntitlementListView
- PurchaseHistoryView
- StudentObligationWithEntitlements
- PolicyListView

**Blocked Builders** (do not implement):
- PolicyListView — awaiting get_applicable_policies() contract
- EntitlementWithLedgerContext — awaiting Ledger read API

**Effort**: 3-5 hours  
**Blocking**: Nothing (blocked builders stay blocked)

**Do Not**: Create route endpoints, update context processors, or touch templates

---

### Stage 3: Phase 5 Documentation & Handoff

1. Document all implemented reads and view models in service contracts
2. Document all blocked projections with their contract gaps
3. Add deliverable checklist showing what's complete vs blocked
4. Hand off to Phase 6

**Effort**: 1-2 hours

**Do Not**: Begin Phase 6 surface inventory until Phase 5 is complete

---

## V. Contract Gaps (Blocked Projections)

Do NOT stub these. Leave them blocked until authority exists.

### Contract Gap 1: list_store_policies() Semantics

**Status**: Resolved for Phase 5

**Current Contract**:
- Returns canonical, validated `StorePolicyConfig` objects for the class
- Does not evaluate student eligibility, affordability, entitlement ownership, or class feature state
- View models own presentation ordering and labeling only

**Do Not**: Add business filtering to the resolver primitive.

---

### Contract Gap 2: Ledger Cross-Domain Read

**Blocks**: EntitlementWithLedgerContext  
**Issue**: No Ledger domain read API defined for transaction lookup  
**Scope**: How to query Ledger for transaction matching EntitlementEvent correlation_id?  
**Open Questions**:
- Does Ledger expose query API for transactions by correlation_id?
- What's the exact schema and access contract?
- How to handle async mismatch (transaction pending, not yet posted)?
- Who owns reconciliation/retry logic?

**Authority Needed**: 
- Ledger domain Phase 5+ read models (outside Store scope)
- Cross-domain coordination contract (INV-ARC-021)

**Resolution Path**: After Ledger domain completion and FEAT-STOR-001 real coordination (Phase 4 follow-up)

**Do Not**: Stub a Ledger query. Leave EntitlementWithLedgerContext unimplemented until Ledger API exists.

---

## VI. Implementation Notes

### Consistency with Prior Work

- `entitlement_read_service.py` already exists; verify it matches Phase 5 contract
- `StudentObligationView` pattern from Obligations domain is reference model
- Follow canonical read service patterns (pure, class-scoped, documented preconditions)

### Testing Strategy

**Unit Tests**:
- Each projection with known input data
- Verify purity (no side effects)
- Verify class scoping (cannot cross class_id)
- Verify temporal semantics (if applicable)

**View Model Tests**:
- Data extraction and aggregation correctness
- Structure and field types match declaration
- Edge cases (empty data, missing related records)

**Do Not**:
- Create route-level tests in Phase 5
- Test template rendering (Phase 7)
- Test authorization logic (belongs in routes, not read models)

### Documentation Requirements

- Each read service method: preconditions, purity statement, temporal freshness
- Each view model builder: input contract, output structure, data sources
- Blocked projections: explicit contract gap and blocker statement
- Temporal semantics: whether read is point-in-time, snapshot, or eventual-consistent

---

## VII. Phase 5 Completion Checklist

Phase 5 is complete when:

- ✅ Read service fully documented (all methods have preconditions, purity statement, tests)
- ✅ Unblocked view model builders implemented and tested
- ✅ Blocked projections explicitly documented only where authority is still missing (EntitlementWithLedgerContext)
- ✅ Blocked projections explicitly documented only where authority is still missing (EntitlementWithLedgerContext)
- ✅ All unit tests pass
- ✅ No routes or templates updated
- ✅ Contract gaps filed for Phase 6+ action

**Do Not Complete Phase 5 if**:
- Any read service lacks purity documentation or tests
- Any view model was stubbed/inferred to sidestep a contract gap
- Routes were updated during this phase
- Blocked projections were implemented without authority

---

## VIII. Next Phase: Phase 6 (Application Surface Inventory)

Phase 6 begins after Phase 5 is complete.

Phase 6 will:
1. Inventory every surface touching Store/Entitlements (routes, templates, APIs, jobs, CLI)
2. Classify each as REWIRE, REMOVE, COLLAPSE, or VERIFY
3. Identify which surfaces need blocked projections
4. Prepare disposition list for Phase 7

**Gate**: Phase 5 completion checklist ✅

---

**Ready to Begin**: Yes (Phase 5 implementation can start immediately)  
**Estimated Effort**: 
- Stage 1 (Read Service): 2-4 hours
- Stage 2 (View Models): 3-5 hours  
- Stage 3 (Documentation): 1-2 hours
- **Total**: 6-11 hours (Phase 5 only)

**Critical Path**: 
1. Verify existing read service 
2. Implement unblocked view model builders
3. Document contract gaps for Phase 6 triage
4. Hand off to Phase 6

**Start Date**: Immediately after Phase 4 ✅
