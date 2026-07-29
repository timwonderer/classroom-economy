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

**Purpose**: Show student what policies are available to purchase in this class  
**Structure**:
```python
@dataclass
class PolicyListView:
    policy_uuid: str
    product_id: int
    product_name: str
    description: str
    price: Decimal
    available: bool  # Whether can purchase (limit not exceeded, etc.)
    current_balance: int  # For hall passes
    purchase_count: int  # How many already purchased
    limit_per_student: int | None
```

**Source**:
1. Call `StorePolicyResolver.get_applicable_policies(class_id)` (deferred to Phase 5)
2. For each policy, derive `available` and `purchase_count` (Projection 3)
3. Derive current_balance (Projection 2) for hall pass products
4. Format for UI

**Used By**: Student store browse, purchase interface

**Purity**: ⚠️ Requires `get_applicable_policies()` semantics (deferred)

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
**Domains**: Store + Ledger  
**Structure**:
```python
@dataclass
class EntitlementWithLedgerContext:
    entitlement: EntitlementListView  # From Store
    ledger_transaction_id: int | None  # From Ledger
    posted_to_ledger: bool
    ledger_amount: Decimal | None
```

**Source**:
1. Get EntitlementListView (Store read)
2. Query Ledger for transaction matching correlation_id
3. Combine

**Used By**: Admin transaction audit, reconciliation

**Purity**: ⚠️ Requires coordination but still deterministic

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

### Deliverable 1: Entitlement Read Service

**File**: `app/services/entitlement_read_service.py` (refactor/complete)

Must provide:
- ✅ `get_entitlement_history(entitlement_id, class_id)` (exists, verify)
- ✅ `get_active_entitlements(seat_id, class_id, product_id=None)` (exists, verify)
- ✅ `get_entitlement_status(entitlement_id, class_id)` (exists, verify)
- 🔜 `get_hall_pass_balance(seat_id, class_id)` (TODO)
- ✅ `get_purchase_count(seat_id, class_id, product_id)` (exists)
- 🔜 `get_active_rent_grant(seat_id, class_id)` (TODO)

**Status**: Mostly complete; verify consistency

---

### Deliverable 2: View Model Builders

**Files**: `app/services/view_model_builders.py` (new or refactor)

Must provide:
- 🔜 `build_entitlement_list_view(seat_id, class_id)` → List[EntitlementListView]
- 🔜 `build_policy_list_view(class_id)` → List[PolicyListView] (blocks on get_applicable_policies)
- 🔜 `build_purchase_history_view(seat_id, class_id)` → List[PurchaseHistoryView]
- 🔜 `build_entitlement_with_ledger_context(entitlement_id, class_id)` → EntitlementWithLedgerContext

---

### Deliverable 3: Request Context Processors

**File**: `app/context_processors.py` (update for Store/Entitlements)

Must provide:
- 🔜 `load_entitlement_context(canonical_context)` → EntitlementContext dict

Following `MAP-UI-002` patterns

---

### Deliverable 4: Route GET Handlers

**Files**: Various route files

Must implement:
- 🔜 Student entitlements list page
- 🔜 Student store browse page (with policy discovery)
- 🔜 Student purchase history page
- 🔜 Admin entitlement audit page

All using canonical read services, not direct table queries

---

## IV. Phase 5 Sequencing

### Stage 1: Read Service Completion

1. Audit existing `entitlement_read_service.py`
2. Verify all projections (status, balance, count) are correct
3. Document each read's source and purity
4. Add missing reads (if any)
5. Test all reads for correctness

**Effort**: 2-4 hours  
**Blocking**: Nothing; can proceed in parallel with other work

---

### Stage 2: View Model Builders

1. Design EntitlementListView, PolicyListView, PurchaseHistoryView
2. Implement builders using read service
3. Add tests
4. Verify compatibility with existing templates

**Effort**: 4-6 hours  
**Blocking**: get_applicable_policies() semantics (Phase 5 blocker)

---

### Stage 3: Request Context & Route Handlers

1. Update context processors per MAP-UI-002
2. Rewrite GET route handlers to use view models
3. Update templates to use view models instead of raw queries
4. Test rendering

**Effort**: 6-8 hours  
**Blocking**: View model builders

---

## V. Blocking Issues for Phase 5

### BLOCKER 1: get_applicable_policies() Semantics

**Issue**: StorePolicyResolver has stub but no implementation  
**Scope**: Which policies should be shown to student?  
**Questions**:
- Show all non-retired policies?
- Show only currently-active policies (by rent cycle)?
- Show only policies student can afford?
- Show only policies they haven't hit limit on?

**Resolution**: Requires DOM-STORE-001 refinement or view-model-specific decision  
**Impact**: PolicyListView cannot be completed until this is decided  
**Workaround**: Stub implementation for Phase 5, full semantics in Phase 6

---

### BLOCKER 2: Ledger Cross-Domain Read

**Issue**: EntitlementWithLedgerContext requires Ledger read  
**Scope**: How to query Ledger for transaction matching EntitlementEvent?  
**Questions**:
- Does Ledger expose query API for transactions by correlation_id?
- What's the schema for Ledger transactions?
- How to handle Ledger not having transaction yet (async)?

**Resolution**: Requires Ledger domain API clarification  
**Impact**: Can defer to Phase 5 Stage 3; other views don't need it  
**Workaround**: Skip EntitlementWithLedgerContext for initial Phase 5

---

## VI. Implementation Notes

### Consistency with Prior Work

- `entitlement_read_service.py` already exists (verify it matches Phase 5 spec)
- `StudentObligationView` pattern from Obligations domain should be replicated
- Follow `MAP-UI-002` request context patterns

### Testing Strategy

- Unit tests for each projection (deterministic, pure)
- Integration tests for view model builders
- Route tests for GET handlers
- Template render tests

### Documentation

- Record each read's source and temporal freshness
- Mark which reads require Ledger/Obligations coordination
- Note any display-only formatting outside domain logic

---

## VII. Next Phase: Phase 6 (Application Surface Inventory)

Phase 6 will:
1. Inventory every surface touching Store/Entitlements (routes, templates, APIs, jobs, CLI)
2. Classify as REWIRE, REMOVE, COLLAPSE, or VERIFY
3. Prepare for Phase 7 rewiring

**Gate**: Phase 5 (Read Models) must be complete

---

**Ready to Begin**: Yes  
**Estimated Effort**: 12-18 hours total  
**Critical Path Items**: 
1. Verify existing read service 
2. Design/implement view models
3. Resolve get_applicable_policies() scope
4. Rewire route handlers

**Start Date**: Immediately after Phase 4 ✅
