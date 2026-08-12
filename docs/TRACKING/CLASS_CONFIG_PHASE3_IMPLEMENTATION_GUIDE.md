# Class Configuration Domain — Phase 3 Implementation Guide

**Domain:** DOM-CLASS-001  
**Phase:** 3 (Primitives — Core queries in service layer)  
**Status:** COMPLETE (implemented 2026-08-11; guide retained as historical reference)  
**Authority:** INV-CORE-001 → INV-ARC-009/015/016 → DOM-CLASS-001/002/003 → SPEC-ECON-003 → Phase 3  
**Version:** 1.0 (Comprehensive synthesis of CLASS_CONFIG_PHASE3_PLAN.md + Governance + Testing)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Objective & Deliverables](#objective--deliverables)
3. [Success Criteria](#success-criteria)
4. [Authority Hierarchy & Governing Constraints](#authority-hierarchy--governing-constraints)
5. [Complete Service Function Specification](#complete-service-function-specification)
6. [Testing Requirements (SPEC-TEST-001 & SPEC-TIME-001)](#testing-requirements-spec-test-001--spec-time-001)
7. [Implementation Roadmap](#implementation-roadmap)
8. [Detailed Citations](#detailed-citations)
9. [Pre-Implementation Checklist](#pre-implementation-checklist)

---

## Executive Summary

Phase 3 (Primitives) requires implementing **17 read-only query service functions** in `app/services/class_configuration_query_service.py` and refactoring all routes to call these functions instead of making direct database queries. This is a **schema-abstraction phase**—no mutations, no domain logic, just pure read operations with proper scoping.

**Phase 3 Deliverables:**
- ✅ 17 service functions with complete docstrings and type hints
- ✅ 55 comprehensive tests (3+ per function: happy path, empty state, multi-tenancy)
- ✅ All routes refactored to use service layer (zero direct schema queries)
- ✅ Multi-tenancy scoping enforced via class_id parameter
- ✅ Temporal query support via canonical_temporal_resolver()

**Dependencies:**
- **Blocked by:** Nothing (Phase 2 ✅ complete)
- **Blocks:** Phase 4 (FEAT Mutation Boundary) — cannot proceed without Phase 3 read-side

**Estimated Effort:** 2–3 days (implementation + tests + route refactoring + audit)

---

## Objective & Deliverables

### Primary Objective

> Centralize all class configuration queries into a dedicated service layer, breaking the coupling between routes and the database schema.

### Detailed Objectives

**1. Schema Abstraction Layer**
- All database queries for class configuration facts (ClassEconomy, EconomicEngine, ClassFeature, PayrollSettings, RentSettings, BankingSettings, HallPassSettings) wrapped in named service functions with documented contracts
- Routes have zero knowledge of schema implementation details

**2. Route Decoupling**
- Every route that reads class data (`GET` handlers) calls service functions; zero direct `db.session.query()` in routes
- Future schema changes only require updating service layer, not routes

**3. Temporal Query Support**
- Service layer handles `effective_at` parameter for querying historical feature state (required for future-law visibility per SPEC-ECON-002)
- All temporal queries use canonical_temporal_resolver() (SPEC-TIME-001)

**4. Derived Value Calculations**
- CWI calculation, policy mode lookup, and economic state queries live in service layer (not in routes or Jinja2 templates)

**5. Configuration Guidance**
- Two helper functions (`suggest_economic_mode`, `validate_payroll_rate`) provide teacher-facing validation and UX hints

### Why This Matters

- **Phase 4 (Mutation Boundary)** requires a clean read-side to avoid query-vs-mutation inconsistencies
- **Multi-tenancy enforcement** can be centralized (all class queries check class_id scoping)
- **Testing** becomes simpler (mock service functions in tests rather than database state)
- **Future Changes** (schema refactors, query optimization) only require changing the service layer, not dozens of routes

---

## Success Criteria

### Completion Checklist

**Service Layer Implementation:**
- [ ] `app/services/class_configuration_query_service.py` created with all 17 functions
- [ ] Every function has comprehensive docstring with `Args:`, `Returns:`, and behavior notes
- [ ] Type hints complete for all parameters and return types
- [ ] Function signatures match spec exactly (see Section 5)

**Test Coverage:**
- [ ] Happy path test for every function (returns expected data)
- [ ] Empty state test for every function (handles missing data gracefully)
- [ ] Multi-tenancy test for every function that references `class_id` (verifies scoping)
- [ ] All tests use `initialize()` or `initialize_as_teacher()` from SPEC-TEST-001
- [ ] All tests use `canonical_temporal_resolver()` for time-dependent queries (SPEC-TIME-001)
- [ ] Test coverage > 80% for class_configuration_query_service module
- [ ] All ~48 tests passing

**Route Refactoring:**
- [ ] All `app/routes/admin.py` routes refactored (zero direct schema queries)
- [ ] All `app/routes/analytics.py` routes refactored
- [ ] All `app/routes/main.py` routes refactored
- [ ] Grep audit confirms zero `ClassEconomy.query`, `PayrollSettings.query`, etc. in routes

**Verification & Documentation:**
- [ ] Code review passes (all functions reviewed for correctness and type hints)
- [ ] Grep audit confirms all class configuration queries live in service layer
- [ ] Integrated test suite passes (pytest with full coverage)
- [ ] CHANGELOG.md updated
- [ ] PR created to `codex/v2.0` with clean commit history

### Definition of Done

Phase 3 is **COMPLETE** when:
1. All 17 service functions implemented and documented
2. All routes refactored to use service layer (zero direct schema queries)
3. Test coverage > 80% for class_configuration_query_service module
4. Grep verification: `grep -r "ClassEconomy.query\|PayrollSettings.query" app/routes/` returns ZERO matches
5. PR merged to `codex/v2.0` with approvals

---

## Authority Hierarchy & Governing Constraints

### A. Authority Model (INV-CORE-001)

```text
INV-CORE-001 (Foundational laws)
  ↓ governs all downstream specifications
INV-ARC-009 (Domain authority for state)
INV-ARC-015 (Temporal model)
INV-ARC-016 (Audit lineage)
  ↓ governs domain specifications
DOM-CLASS-001 (Class Configuration domain)
DOM-CLASS-002 (Class Economy governance)
DOM-CLASS-003 (Economic policy)
  ↓ governs implementation specs
SPEC-ECON-003 (Economic calculations)
  ↓ governs implementation
Phase 3 Service Functions
```

**Key Principle:** Phase 3 implements the READ-SIDE of specs established by DOM-CLASS-001/002/003. Functions are read-only queries that expose facts, not logic.

### B. Multi-Tenancy & Scoping Constraints

**Hard Rule:** All class-scoped queries must filter by `class_id` (never by `teacher_id` alone).

**Rationale:** CTH previously had a P0 multi-period data leak when queries used `teacher_id` without `class_id`. Phase 3 prevents this by design.

**Exceptions:**
- `get_all_classes_by_teacher(teacher_user_id)` — scoped by `teacher_user_id` by design (returns only classes owned by that teacher; no student data exposed)
- `get_class_economy(class_id)` may also be looked up via `join_code` in ingress contexts, but the service function requires `class_id`

**Implementation:**
- All class-scoped functions take `class_id` as first parameter (non-optional)
- All class-scoped queries include `.filter_by(class_id=class_id)` or equivalent
- `get_all_classes_by_teacher` is the sole exception, scoped by `teacher_user_id`
- All tests must verify class-scoped queries with multi-class fixture data

**Authority:** `.claude/rules/multi-tenancy.md`

### C. Schema Constraints (Phase 2 Complete)

**ClassEconomy Table:**
- `class_id` (UUID, PK) — Canonical class identifier
- `join_code` (String, unique) — Public class alias
- `teacher_user_id` (FK to User.id, renamed in Phase 2c from `user_id`)
- `display_name`, `section`, `timezone` (immutable after creation)
- `created_at`, `updated_at`

**EconomicEngine Table:**
- `id` (UUID, PK)
- `class_id` (FK to classes.class_id)
- `policy_mode` ('tight', 'default', 'comfortable')
- All economic settings (CWI-relative ratios, store pricing, etc.)
- `created_at` (immutable; use for version history)
- `previous_version_id` (FK to prior EconomicEngine, for audit lineage)
- ⚠️ **NO `effective_at`** — EconomicEngine is versioned by creation time, not effective date

**ClassFeature Table (Append-Only Timeline):**
- `class_id` (FK to classes.class_id)
- `feature` (String, e.g., 'payroll', 'hall_pass', 'rent')
- `effective_at` (DateTime; temporal anchor—when does this feature take effect?)
- `economic_version_id` (FK to economic-engine, nullable; links engine version for this feature; NULL = disabled)
- Composite PK: `(class_id, feature, effective_at)`
- **Immutable:** Rows never updated; new rows inserted for state changes

**Query Implication:**

The fundamental query model is: **class × feature × effective_time → economic_policy_version**

- `get_effective_economic_engine(class_id, feature='store')` → Query the EconomicEngine linked by the most-recent-effective ClassFeature for that specific feature (where effective_at <= now, deleted_at IS NULL), ordered by effective_at DESC
  - Honors feature-level timelines: different features can have DIFFERENT engines at different times
  - Temporal consistency: same as `get_class_feature()` temporal semantics
  
- `get_effective_economic_engine(class_id, feature='rent', effective_at=day_20)` → Query what policy governs rent on Day 20 (even if Day 20 is in the future)
  - Enables UI to preview future rebalancing effects before they occur
  
- `get_initial_economic_engine(class_id)` → Get the earliest/original engine (for analytics/baseline only, not policy authority)
  
- `get_economic_engine_history(class_id)` → Get all engine versions by creation time (for analytics/audit trail)
  
- `get_class_feature(class_id, feature, effective_at)` → Find the ClassFeature row where `(class_id=X, feature=Y, effective_at <= T, deleted_at IS NULL)`, ordered by effective_at DESC, limit 1

**Authority:** DOM-CLASS-001, SPEC-ECON-003

### D. Temporal Constraints (SPEC-TIME-001)

**Mandatory for Phase 3:**
- All queries that accept `effective_at` must use `canonical_temporal_resolver()` for determining "now"
- Never use `datetime.now()` or `datetime.utcnow()` directly in service layer
- All tests must inject `reference_time_utc` via temporal resolver (not rely on wall-clock time)

**Import Pattern:**
```python
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    CLASS_LEVEL_EVALUATION,
    SYSTEM_LEVEL_EVALUATION,
)

# For system-level (UTC) time
result = canonical_temporal_resolver(
    SYSTEM_LEVEL_EVALUATION,
    primitive="current_time"
)

# For class-level (class timezone) time
result = canonical_temporal_resolver(
    CLASS_LEVEL_EVALUATION,
    canonical_execution_context=ctx,  # CanonicalExecutionContext with class_id
    primitive="current_time"
)
```

**Authority:** INV-ARC-015 (temporal model), SPEC-TIME-001 (temporal resolver spec)

### E. Read-Only Constraint

**Phase 3 Functions Must Never:**
- ❌ Mutate database state (no `db.session.add`, `db.session.commit()`)
- ❌ Call FEAT layer functions
- ❌ Trigger ORM event listeners
- ❌ Rely on transactional semantics

**Why:** Mutations belong in Phase 4 (FEAT Mutation Boundary). Mixing read and write logic violates the SOP-DEV-002 phase progression model.

**Authority:** SOP-DEV-002 (phase workflow), INV-ARC-007 (GET handlers must be pure)

### F. Testing Constraints (SPEC-TEST-001 & SPEC-TIME-001)

**All Phase 3 tests must use SPEC-TEST-001 canonical initializer:**

```python
from tests.helpers.classroom_initializer import (
    initialize,           # For DB-only tests
    initialize_as_student,  # For student HTTP tests
    initialize_as_teacher,  # For teacher HTTP tests
)

# Entry Point 1: DB State Only
classroom = initialize("chemistry_p1", app)

# Entry Point 2: Teacher HTTP Session
classroom = initialize_as_teacher("chemistry_p1", client, app)

# Entry Point 3: Student HTTP Session
classroom, student = initialize_as_student("chemistry_p1", client, app, student_index=0)
```

**All Phase 3 tests must follow SPEC-TIME-001 temporal discipline:**

```python
# Option A: Inject reference_time_utc via canonical_temporal_resolver
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    SYSTEM_LEVEL_EVALUATION,
)

test_time = datetime(2026, 8, 9, 15, 30, 0, tzinfo=timezone.utc)
result = canonical_temporal_resolver(
    SYSTEM_LEVEL_EVALUATION,
    primitive="current_time",
    reference_time_utc=test_time  # ← Injected for test reproducibility
)

# Option B: Pass fixed timezone-aware UTC timestamps directly to effective_at
# This is acceptable when testing query functions that accept effective_at
reference_time = datetime(2099, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
engine = get_effective_economic_engine(class_id, "payroll", effective_at=reference_time)

# NEVER: datetime.now(), datetime.utcnow(), or utc_now()
```

**Authority:** SPEC-TEST-001 (canonical test initializer), SPEC-TIME-001 (canonical temporal resolver)

### G. Prohibited v1 Test Patterns

❌ **NEVER use these deprecated patterns:**

```python
# DEPRECATED v1 patterns (FORBIDDEN in Phase 3)
from tests.helpers.v2_fixtures import seed_canonical_admin, create_class_scope
from tests.helpers.context_factory import set_canonical_context

# NEVER: Manual context setup
admin = seed_canonical_admin("test_teacher")
context = create_class_scope(admin_id=admin.id)
set_canonical_context(context)

# NEVER: Direct db.session mutations in tests
with app.app_context():
    teacher = Admin(username="test")
    db.session.add(teacher)
    db.session.commit()  # WRONG! Bypasses FEAT layer
```

✅ **Always use SPEC-TEST-001 canonical initializer instead:**

```python
from tests.helpers.classroom_initializer import initialize

classroom = initialize("chemistry_p1", app)
# All setup complete, invariants verified, context ready
```

---

## Complete Service Function Specification

### Module: `app/services/class_configuration_query_service.py`

All functions are **read-only** (no mutations), **class-scoped**, and **thoroughly documented**.

---

### 1. Class Entity Queries (2 functions)

#### `get_class_economy(class_id: str) -> ClassEconomy | None`

```python
def get_class_economy(class_id: str) -> ClassEconomy | None:
    """Get the ClassEconomy entity for a class.
    
    Args:
        class_id: The class to retrieve (UUID)
        
    Returns:
        ClassEconomy instance or None if not found
        
    Raises:
        None (returns None on missing data)
        
    Example:
        economy = get_class_economy("abc123-def456")
        if economy:
            print(f"Class: {economy.display_name}, Timezone: {economy.timezone}")
    """
```

**Authority:** DOM-CLASS-001 § VII (ClassEconomy ownership)

#### `get_class_by_join_code(join_code: str) -> ClassEconomy | None`

```python
def get_class_by_join_code(join_code: str) -> ClassEconomy | None:
    """Get ClassEconomy entity by public join_code alias.
    
    Args:
        join_code: Public class alias (e.g., "CHEM101")
        
    Returns:
        ClassEconomy instance or None if not found
        
    Example:
        economy = get_class_by_join_code("CHEM101")
        if economy:
            class_id = economy.class_id  # Use canonical ID for further queries
    """
```

**Authority:** DOM-CLASS-001 § V (join_code as public alias)

---

### 2. Economic Engine Queries (3 functions)

#### `get_effective_economic_engine(class_id: str, feature: str, effective_at: datetime | None = None) -> EconomicEngine | None`

```python
def get_effective_economic_engine(
    class_id: str,
    feature: str,
    effective_at: datetime | None = None
) -> EconomicEngine | None:
    """Get the EconomicEngine that governs a specific feature at a specific time.
    
    Returns the immutable economic policy version that is effective for the given
    feature and timestamp. This enables querying current, historical, and future
    policy across feature-scoped timelines.
    
    Args:
        class_id: The class (UUID)
        feature: Feature name ('store', 'rent', 'payroll', 'hall_pass', etc.) [REQUIRED]
        effective_at: Timestamp to query at (default: canonical now via SPEC-TIME-001)
        
    Returns:
        EconomicEngine instance that governs this (class, feature, time), or None if not found
        
    Note:
        The contract is: Given class X, feature Y, and time T, which immutable
        economic policy version governs that feature?
        
        - Find the ClassFeature row where:
          (class_id=X, feature=Y, effective_at <= T, deleted_at IS NULL)
          Order by effective_at DESC, take first.
        - Return the EconomicEngine linked by that ClassFeature.
        
        Different features can have DIFFERENT engines because teacher can schedule
        transitions at different times during rebalancing.
        
    Example (Staggered rebalancing):
        # Teacher schedules: store switches to Engine B immediately (Day 5)
        #                   rent  switches to Engine B on Day 20
        
        # Current policy (Day 10):
        store_engine = get_effective_economic_engine(class_id, "store")
        # Returns Engine B (effective_at=Day5 <= now) ✅
        
        rent_engine = get_effective_economic_engine(class_id, "rent")
        # Returns Engine A (effective_at=Day20 > now, so max <= now is Day1) ✅
        
        # Historical query (Day 3, before rebalance):
        store_policy_then = get_effective_economic_engine(class_id, "store", day_3)
        # Returns Engine A ✅
        
        # Future query (Day 25, after rent switches):
        rent_policy_then = get_effective_economic_engine(class_id, "rent", day_25)
        # Returns Engine B ✅ (precomputed timeline!)
        
        # UI: Show teacher what will happen on Day 20 (before it occurs)
        future_rent_policy = get_effective_economic_engine(class_id, "rent", day_20_midnight)
        # Returns Engine B, enables UX to show "Rent will switch to Engine B on Day 20" ✅
    """
```

**Implementation Pattern:**

```python
def get_effective_economic_engine(
    class_id: str,
    feature: str,
    effective_at: datetime | None = None
) -> EconomicEngine | None:
    from app.utils.canonical_temporal_resolver import (
        canonical_temporal_resolver,
        SYSTEM_LEVEL_EVALUATION,
    )
    
    # Determine query time using canonical temporal resolver (SPEC-TIME-001)
    if effective_at is None:
        result = canonical_temporal_resolver(
            SYSTEM_LEVEL_EVALUATION,
            primitive="current_time"
        )
        query_time = result.canonical_now_utc
    else:
        query_time = effective_at
    
    # Find the most-recent-effective ClassFeature for this (class, feature) pair
    # where effective_at <= query_time and not deleted
    class_feature = ClassFeature.query.filter(
        ClassFeature.class_id == class_id,
        ClassFeature.feature == feature,
        ClassFeature.effective_at <= query_time,
        (ClassFeature.deleted_at.is_(None) | (ClassFeature.deleted_at > query_time))
    ).order_by(
        ClassFeature.effective_at.desc()  # Most recent effective_at first
    ).first()
    
    if not class_feature:
        return None
    
    return db.session.get(EconomicEngine, class_feature.economic_version_id)
```

**Authority:** DOM-CLASS-002 § III (policy mode), DOM-CLASS-003 § II (policy versioning), SPEC-ECON-002 (feature-level effective_at semantics)

#### `get_initial_economic_engine(class_id: str) -> EconomicEngine | None`

```python
def get_initial_economic_engine(class_id: str) -> EconomicEngine | None:
    """Get the original (first) EconomicEngine created for a class.
    
    Returns the immutable economic policy version that was active when the class
    was created. Useful for analytics, baseline comparisons, or understanding
    the original economy design. This engine is never authoritative over current
    policy—it's simply the earliest immutable version in the timeline.
    
    Args:
        class_id: The class (UUID)
        
    Returns:
        EconomicEngine linked by the ClassFeature with earliest effective_at,
        or None if not found
        
    Example:
        # Show teacher the original economy they designed
        initial = get_initial_economic_engine(class_id)
        if initial:
            print(f"Original mode: {initial.policy_mode}")
            print(f"Created on: {initial.created_at}")
    """
```

**Implementation Pattern:**

```python
def get_initial_economic_engine(class_id: str) -> EconomicEngine | None:
    # Find the earliest ClassFeature (first feature ever created for this class)
    class_feature = ClassFeature.query.filter(
        ClassFeature.class_id == class_id,
        ClassFeature.deleted_at.is_(None)
    ).order_by(
        ClassFeature.effective_at.asc()  # Earliest effective_at first
    ).first()
    
    if not class_feature:
        return None
    
    return db.session.get(EconomicEngine, class_feature.economic_version_id)
```

**Authority:** DOM-CLASS-003 § II (policy evolution), analytics context

#### `get_economic_engine_history(class_id: str) -> list[EconomicEngine]`

```python
def get_economic_engine_history(class_id: str) -> list[EconomicEngine]:
    """Get all EconomicEngine versions for a class in chronological order.
    
    Ordered by created_at DESC (most recent first).
    
    Args:
        class_id: The class to retrieve history for (UUID)
        
    Returns:
        List of EconomicEngine instances, ordered by creation time (may be empty)
        
    Note:
        Use created_at (not effective_at, which does not exist on EconomicEngine).
        Traverse previous_version_id for audit lineage.
        
    Example:
        history = get_economic_engine_history(classroom.class_id)
        for engine in history:
            print(f"Version created at {engine.created_at}: mode={engine.policy_mode}")
    """
```

**Authority:** INV-ARC-016 (audit lineage via previous_version_id), DOM-CLASS-003 § II (policy evolution)

---

### 3. Class Feature Queries (3 functions)

#### `get_class_features(class_id: str, effective_at: datetime | None = None) -> dict[str, ClassFeature]`

```python
def get_class_features(class_id: str, effective_at: datetime | None = None) -> dict[str, ClassFeature]:
    """Get all class features for a class, keyed by feature name.
    
    Returns the state of features as of effective_at (default: canonical now).
    
    Args:
        class_id: The class to retrieve features for (UUID)
        effective_at: Timestamp to query feature state at (default: canonical now via SPEC-TIME-001)
        
    Returns:
        Dict mapping feature name -> ClassFeature instance
        Empty dict if class has no features
        
    Note:
        - If effective_at is None, use canonical_temporal_resolver() with SYSTEM_LEVEL_EVALUATION
        - A feature is active if: effective_at <= query_time AND (deleted_at IS NULL OR deleted_at > query_time)
        - For each feature name, return the LATEST effective_at <= query_time
        - Composite PK ensures no duplicates
        
    Example:
        features = get_class_features(classroom.class_id)
        if 'payroll' in features:
            print(f"Payroll enabled since {features['payroll'].effective_at}")
    """
```

**Authority:** DOM-CLASS-001 § VI (ClassFeature schema), SPEC-ECON-002 § II (effective_at semantics)

#### `get_class_feature(class_id: str, feature: str, effective_at: datetime | None = None) -> ClassFeature | None`

```python
def get_class_feature(class_id: str, feature: str, effective_at: datetime | None = None) -> ClassFeature | None:
    """Get a specific class feature by name.
    
    Args:
        class_id: The class (UUID)
        feature: Feature name (e.g., 'payroll', 'hall_pass', 'rent')
        effective_at: Timestamp to query at (default: canonical now via SPEC-TIME-001)
        
    Returns:
        ClassFeature instance or None if not found/disabled
        
    Note:
        Convenience wrapper on get_class_features() for single-feature lookup.
        
    Example:
        payroll_feature = get_class_feature(classroom.class_id, 'payroll')
        if payroll_feature:
            print(f"Payroll effective since {payroll_feature.effective_at}")
    """
```

**Authority:** DOM-CLASS-001 § VI (feature enablement), SPEC-ECON-002 (future-law visibility)

#### `get_class_feature_history(class_id: str, feature: str) -> list[ClassFeature]`

```python
def get_class_feature_history(class_id: str, feature: str) -> list[ClassFeature]:
    """Get all versions of a specific class feature in chronological order.
    
    Ordered by effective_at DESC (most recent first).
    
    Args:
        class_id: The class (UUID)
        feature: Feature name
        
    Returns:
        List of ClassFeature instances (may be empty)
        
    Example:
        payroll_history = get_class_feature_history(classroom.class_id, 'payroll')
        for version in payroll_history:
            status = "active" if version.deleted_at is None else "deleted"
            print(f"Payroll {status} from {version.effective_at}")
    """
```

**Authority:** DOM-CLASS-003 § II (policy evolution as append-only timeline)

---

### 4. Settings Queries (4 functions)

#### `get_payroll_settings(class_id: str) -> PayrollSettings | None`

```python
def get_payroll_settings(class_id: str) -> PayrollSettings | None:
    """Get payroll configuration for a class.
    
    Includes hourly_pay_rate, expected_weekly_hours, CWI, policy mode.
    
    Args:
        class_id: The class (UUID)
        
    Returns:
        PayrollSettings instance or None
        
    Example:
        payroll = get_payroll_settings(classroom.class_id)
        if payroll:
            cwi = payroll.hourly_pay_rate * payroll.expected_weekly_hours
    """
```

**Authority:** DOM-CLASS-002 § IV (payroll governance)

#### `get_rent_settings(class_id: str) -> RentSettings | None`

```python
def get_rent_settings(class_id: str) -> RentSettings | None:
    """Get rent configuration for a class.
    
    Includes rent_amount, rent_frequency, rent_payday, grace period.
    
    Args:
        class_id: The class (UUID)
        
    Returns:
        RentSettings instance or None
        
    Example:
        rent = get_rent_settings(classroom.class_id)
        if rent:
            print(f"Students owe ${rent.rent_amount} every {rent.rent_frequency}")
    """
```

**Authority:** DOM-CLASS-002 § IV (rent governance)

#### `get_banking_settings(class_id: str) -> BankingSettings | None`

```python
def get_banking_settings(class_id: str) -> BankingSettings | None:
    """Get banking configuration for a class.
    
    Includes interest_rate, interest_frequency, savings_threshold.
    
    Args:
        class_id: The class (UUID)
        
    Returns:
        BankingSettings instance or None
        
    Example:
        banking = get_banking_settings(classroom.class_id)
        if banking:
            print(f"Savings interest: {banking.interest_rate}% {banking.interest_frequency}")
    """
```

**Authority:** DOM-CLASS-002 § IV (banking governance), SPEC-ECON-001 (interest accrual)

#### `get_hall_pass_settings(class_id: str) -> HallPassSettings | None`

```python
def get_hall_pass_settings(class_id: str) -> HallPassSettings | None:
    """Get hall pass configuration for a class.
    
    Includes grant_frequency, grant_amount, expiration_days.
    
    Args:
        class_id: The class (UUID)
        
    Returns:
        HallPassSettings instance or None
        
    Example:
        hp = get_hall_pass_settings(classroom.class_id)
        if hp:
            print(f"Students get {hp.grant_amount} passes every {hp.grant_frequency}")
    """
```

**Authority:** DOM-CLASS-002 § IV (entitlements governance)

---

### 5. CWI & Economic Derived Values (2 functions)

#### `calculate_cwi(class_id: str) -> float | None`

```python
def calculate_cwi(class_id: str) -> float | None:
    """Calculate the current Classroom Wage Index (CWI) for a class.
    
    CWI = hourly_pay_rate × expected_weekly_hours
    
    Args:
        class_id: The class (UUID)
        
    Returns:
        CWI as a float, or None if payroll settings not found
        
    Example:
        cwi = calculate_cwi(classroom.class_id)
        if cwi:
            print(f"CWI: ${cwi}/week")
    """
```

**Authority:** DOM-CLASS-002 § II (CWI definition), SPEC-ECON-003 § II (CWI calculation)

#### `get_policy_mode(class_id: str) -> str | None`

```python
def get_policy_mode(class_id: str) -> str | None:
    """Get the current economic policy mode for a class.
    
    Returns the policy_mode from current EconomicEngine.
    
    Args:
        class_id: The class (UUID)
        
    Returns:
        Policy mode string ('tight', 'default', 'comfortable') or None
        
    Example:
        mode = get_policy_mode(classroom.class_id)
        if mode == 'tight':
            print("Restricted economy")
    """
```

**Authority:** DOM-CLASS-002 § II (policy mode), SPEC-ECON-003 § III (mode ratio bands)

---

### 6. Configuration State Queries (2 functions)

#### `is_feature_enabled(class_id: str, feature: str) -> bool`

```python
def is_feature_enabled(class_id: str, feature: str) -> bool:
    """Check if a specific feature is enabled for a class.
    
    Returns True if feature exists, is not deleted, and effective_at <= canonical_now.
    
    Args:
        class_id: The class (UUID)
        feature: Feature name
        
    Returns:
        True if enabled, False otherwise
        
    Example:
        if is_feature_enabled(classroom.class_id, 'payroll'):
            print("Payroll is active")
    """
```

**Authority:** DOM-CLASS-001 § V (feature enablement), SPEC-ECON-002 (effective_at semantics)

#### `get_all_classes_by_teacher(teacher_user_id: int) -> list[ClassEconomy]`

```python
def get_all_classes_by_teacher(teacher_user_id: int) -> list[ClassEconomy]:
    """Get all classes owned by a teacher.
    
    Ordered by created_at DESC (most recent first).
    
    Args:
        teacher_user_id: The teacher's User.id
        
    Returns:
        List of ClassEconomy instances (may be empty)
        
    Example:
        classes = get_all_classes_by_teacher(teacher_user.id)
        for cls in classes:
            print(f"{cls.display_name} ({cls.join_code})")
    """
```

**Authority:** DOM-CLASS-001 § V (class ownership via teacher_user_id)

---

### 7. Teacher-Facing Configuration Guidance (2 functions)

#### `suggest_economic_mode(class_size: int, weekly_hours: float) -> str`

```python
def suggest_economic_mode(class_size: int, weekly_hours: float) -> str:
    """Suggest a policy mode based on class context.
    
    Returns advisory suggestion ("tight", "default", or "comfortable").
    Teachers can override the suggestion.
    
    Args:
        class_size: Number of students in class
        weekly_hours: Expected earning hours per week
        
    Returns:
        Suggested policy mode string
        
    Note:
        This is advisory only. Teachers retain full authority over policy selection.
        Suggestion algorithm: consider class size, weekly earning potential, and defaults.
        
    Example:
        suggested = suggest_economic_mode(class_size=25, weekly_hours=50)
        print(f"Suggested mode: {suggested}")
    """
```

**Authority:** DOM-CLASS-002 § II (policy modes), SPEC-ECON-003 § III (mode selection guidance)

#### `validate_payroll_rate(hourly_pay_rate: float, policy_mode: str) -> tuple[bool, str | None]`

```python
def validate_payroll_rate(hourly_pay_rate: float, policy_mode: str) -> tuple[bool, str | None]:
    """Validate a proposed hourly pay rate for reasonableness.
    
    Returns (is_valid, warning_message).
    - is_valid=True: rate accepted (may still have advisory warning)
    - is_valid=False: rate violates hard constraint
    
    Args:
        hourly_pay_rate: Proposed rate
        policy_mode: Class policy mode ('tight', 'default', 'comfortable')
        
    Returns:
        Tuple of (is_valid: bool, warning: str | None)
        
    Example:
        is_valid, warning = validate_payroll_rate(hourly_pay_rate=15.0, policy_mode='default')
        if not is_valid:
            print("Rate rejected")
        elif warning:
            print(f"Warning: {warning}")
    """
```

**Authority:** DOM-CLASS-002 § II (payroll governance), SPEC-ECON-003 § IV (rate validation constraints)

---

### Function Summary Table

| # | Function | Input | Output | Authority |
|---|----------|-------|--------|-----------|
| 1 | `get_class_economy()` | class_id | ClassEconomy\|None | DOM-CLASS-001 |
| 2 | `get_class_by_join_code()` | join_code | ClassEconomy\|None | DOM-CLASS-001 |
| 3 | `get_effective_economic_engine()` | class_id, feature, effective_at? | EconomicEngine\|None | DOM-CLASS-002/003, SPEC-ECON-002 |
| 4 | `get_initial_economic_engine()` | class_id | EconomicEngine\|None | DOM-CLASS-003 (analytics) |
| 5 | `get_economic_engine_history()` | class_id | list[EconomicEngine] | DOM-CLASS-003, INV-ARC-016 |
| 6 | `get_class_features()` | class_id, effective_at? | dict[str, ClassFeature] | DOM-CLASS-001, SPEC-ECON-002 |
| 7 | `get_class_feature()` | class_id, feature, effective_at? | ClassFeature\|None | DOM-CLASS-001 |
| 8 | `get_class_feature_history()` | class_id, feature | list[ClassFeature] | DOM-CLASS-003 |
| 9 | `get_payroll_settings()` | class_id | PayrollSettings\|None | DOM-CLASS-002 |
| 10 | `get_rent_settings()` | class_id | RentSettings\|None | DOM-CLASS-002 |
| 11 | `get_banking_settings()` | class_id | BankingSettings\|None | DOM-CLASS-002, SPEC-ECON-001 |
| 12 | `get_hall_pass_settings()` | class_id | HallPassSettings\|None | DOM-CLASS-002 |
| 13 | `calculate_cwi()` | class_id | float\|None | DOM-CLASS-002, SPEC-ECON-003 |
| 14 | `get_policy_mode()` | class_id | str\|None | DOM-CLASS-002, SPEC-ECON-003 |
| 15 | `is_feature_enabled()` | class_id, feature | bool | DOM-CLASS-001, SPEC-ECON-002 |
| 16 | `get_all_classes_by_teacher()` | teacher_user_id | list[ClassEconomy] | DOM-CLASS-001 |
| 17 | `suggest_economic_mode()` | class_size, weekly_hours | str | DOM-CLASS-002, SPEC-ECON-003 |
| 18 | `validate_payroll_rate()` | hourly_pay_rate, policy_mode | (bool, str\|None) | DOM-CLASS-002, SPEC-ECON-003 |

**Total:** 17 functions (spec says "15+" — we have: 2 entity + 3 engine + 3 feature + 4 settings + 2 derived + 2 state + 1 initial = 17)

---

## Testing Requirements (SPEC-TEST-001 & SPEC-TIME-001)

### A. SPEC-TEST-001: Canonical Test Initializer

**Authority:** `tests/helpers/classroom_initializer.py` (lines 1–35)  
**Purpose:** Single entry point for ALL v2 test setup. No test may construct identity, scope, or context through any other path.

#### Three Entry Points

**Entry Point 1: DB State Only (No Session)**

```python
from tests.helpers.classroom_initializer import initialize

def test_service_layer_db_only(app):
    """For unit tests on services or models that don't need HTTP."""
    classroom = initialize("chemistry_p1", app)
    
    # Returned object has:
    # - classroom.class_id (UUID)
    # - classroom.join_code (str)
    # - classroom.teacher_user (User object)
    # - classroom.teacher_seat (Seat object)
    # - classroom.students (list[ProvisionedStudent])
    # - DB self-test passed
    # - Constitutional invariants verified
    
    payroll = get_payroll_settings(classroom.class_id)
    assert payroll is not None
```

**Entry Point 2: Teacher HTTP Session**

```python
from tests.helpers.classroom_initializer import initialize_as_teacher

def test_admin_route_with_session(client, app):
    """For admin/teacher HTTP routes."""
    classroom = initialize_as_teacher("chemistry_p1", client, app)
    
    # Returned object PLUS:
    # - Teacher session is live
    # - Canonical context verified
    
    response = client.get('/admin/settings')
    assert response.status_code == 200
```

**Entry Point 3: Student HTTP Session**

```python
from tests.helpers.classroom_initializer import initialize_as_student

def test_student_route_with_session(client, app):
    """For student HTTP routes."""
    classroom, student = initialize_as_student(
        "chemistry_p1", 
        client, 
        app, 
        student_index=0
    )
    
    # Returned tuple:
    # - classroom: full provisioned classroom
    # - student: ProvisionedStudent for students[student_index]
    # - Student session is live
    # - Canonical context verified
    
    response = client.get('/student/balance')
    assert response.status_code == 200
```

#### Initialization Guarantees

```text
Step 1: provision_classroom()
├─ Calls production code (FEAT layer)
├─ Builds complete Teacher + Students + Class + Economy
└─ Returns ProvisionedClassroom object

Step 2: _assert_db_invariants()
├─ Re-queries every entity from database
├─ Verifies constitutional invariants hold
├─ Fails test immediately if anything wrong
└─ Checks:
    • ClassEconomy.teacher_user_id == Teacher.id ✅
    • Teacher.user_role == TEACHER ✅
    • All students linked to class ✅

Step 3: login_teacher() or login_student()
└─ Sets Flask session; credentials verified

Step 4: _assert_canonical_context()
├─ Calls resolve_canonical_context() inside real request context
├─ Verifies returned context matches provisioned state
└─ Validates:
    • Resolved user_id == teacher_user.id ✅
    • Resolved class_id == classroom.class_id ✅
    • Resolved seat_id == teacher_seat.id ✅
```

#### Prohibited v1 Patterns

❌ **NEVER use deprecated v1 patterns:**

```python
# FORBIDDEN
from tests.helpers.v2_fixtures import seed_canonical_admin, create_class_scope
from tests.helpers.context_factory import set_canonical_context

def test_bad(app):
    admin = seed_canonical_admin("test_teacher")  # ❌ WRONG
    context = create_class_scope(admin_id=admin.id)  # ❌ WRONG
    set_canonical_context(context)  # ❌ WRONG
```

✅ **Always use SPEC-TEST-001 canonical initializer:**

```python
from tests.helpers.classroom_initializer import initialize

def test_good(app):
    classroom = initialize("chemistry_p1", app)  # ✅ CORRECT
    # Context already set up and verified
```

---

### B. SPEC-TIME-001: Canonical Temporal Resolver

**Authority:** `app/utils/canonical_temporal_resolver.py` (lines 388–430)  
**Purpose:** Single authoritative temporal evaluation tool. No test uses `datetime.now()`.

#### Function Signature

```python
def canonical_temporal_resolver(
    evaluation_type: str,  # SYSTEM_LEVEL_EVALUATION | CLASS_LEVEL_EVALUATION
    *,
    canonical_execution_context=None,  # Required for CLASS_LEVEL_EVALUATION
    primitive: str,  # "current_time", "earlier_than", etc.
    reference_time_utc: datetime | None = None,  # Test injection point
    **primitive_inputs,  # Additional parameters
) -> CanonicalTemporalEvaluation:
    """The single authoritative temporal evaluation tool."""
```

#### Evaluation Types

**SYSTEM_LEVEL_EVALUATION (SLE) — UTC Time**

```python
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    SYSTEM_LEVEL_EVALUATION,
)
from datetime import datetime, timezone

# Get current UTC time
result = canonical_temporal_resolver(
    SYSTEM_LEVEL_EVALUATION,
    primitive="current_time"
)

# For tests: Inject specific reference time
test_time = datetime(2026, 8, 9, 15, 30, 0, tzinfo=timezone.utc)
result = canonical_temporal_resolver(
    SYSTEM_LEVEL_EVALUATION,
    primitive="current_time",
    reference_time_utc=test_time  # ← Injected for reproducibility
)

assert result.canonical_now_utc == test_time
```

**CLASS_LEVEL_EVALUATION (CLE) — Class Timezone**

```python
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    CLASS_LEVEL_EVALUATION,
)

class MockContext:
    class_id = "abc123"  # Required

result = canonical_temporal_resolver(
    CLASS_LEVEL_EVALUATION,
    canonical_execution_context=MockContext(),
    primitive="current_time"
)

# Returns time in ClassEconomy.class_timezone (e.g., "America/Los_Angeles")
print(result.display_timezone)  # "America/Los_Angeles"
```

#### Supported Primitives

| Primitive | Purpose | Use Case |
|-----------|---------|----------|
| `current_time` | Get "now" | Default `effective_at` in feature queries |
| `earlier_than` | Compare times | Policy activation checks |
| `later_than` | Compare times | Expiration checks |
| `between_boundaries` | Time range | Grace periods, windows |
| `time_since` | Elapsed time | Rental age, pass lifetime |
| `time_until` | Remaining time | Days to expiration |

---

### C. Test Pattern: Complete Example

```python
"""Phase 3 test pattern for class_configuration_query_service.py"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.services.class_configuration_query_service import (
    get_class_economy,
    get_payroll_settings,
    calculate_cwi,
    get_class_features,
    is_feature_enabled,
)
from app.utils.canonical_temporal_resolver import (
    canonical_temporal_resolver,
    SYSTEM_LEVEL_EVALUATION,
)
from tests.helpers.classroom_initializer import initialize, initialize_as_teacher


class TestClassConfigurationQueryService:
    """Test Phase 3 service layer per SPEC-TEST-001 & SPEC-TIME-001."""

    # ========== Happy Path Tests ==========

    def test_get_payroll_settings_returns_class_scoped_data(self, app):
        """Happy path: payroll settings returns correct data."""
        classroom = initialize("chemistry_p1", app)
        
        payroll = get_payroll_settings(classroom.class_id)
        
        assert payroll is not None
        assert payroll.class_id == classroom.class_id
        assert payroll.hourly_pay_rate is not None
        assert payroll.expected_weekly_hours is not None

    def test_calculate_cwi_uses_payroll_settings(self, app):
        """Happy path: CWI calculation is correct."""
        classroom = initialize("chemistry_p1", app)
        
        payroll = get_payroll_settings(classroom.class_id)
        cwi = calculate_cwi(classroom.class_id)
        
        expected_cwi = payroll.hourly_pay_rate * payroll.expected_weekly_hours
        assert cwi == expected_cwi

    # ========== Empty State Tests ==========

    def test_get_payroll_settings_returns_none_for_missing_class(self, app):
        """Empty state: non-existent class returns None."""
        payroll = get_payroll_settings("nonexistent-class-id")
        assert payroll is None

    def test_calculate_cwi_returns_none_when_no_payroll(self, app):
        """Empty state: CWI None without payroll settings."""
        # Create classroom, then remove payroll
        classroom = initialize("chemistry_p1", app)
        
        with app.app_context():
            from app.models import PayrollSettings
            from app.extensions import db
            
            PayrollSettings.query.filter_by(class_id=classroom.class_id).delete()
            db.session.commit()
        
        cwi = calculate_cwi(classroom.class_id)
        assert cwi is None

    # ========== Multi-Tenancy Tests ==========

    def test_payroll_query_scoped_by_class_id(self, app):
        """Multi-tenancy: payroll settings isolated by class."""
        classroom1 = initialize("chemistry_p1", app)
        classroom2 = initialize("biology_p2", app)
        
        payroll1 = get_payroll_settings(classroom1.class_id)
        payroll2 = get_payroll_settings(classroom2.class_id)
        
        assert payroll1 is not None
        assert payroll2 is not None
        assert payroll1.class_id != payroll2.class_id

    # ========== Temporal Tests (SPEC-TIME-001) ==========

    def test_get_class_features_with_effective_at_parameter(self, app):
        """Temporal: feature queries work with effective_at parameter."""
        classroom = initialize("chemistry_p1", app)
        
        # Current time query
        features_now = get_class_features(classroom.class_id)
        assert isinstance(features_now, dict)
        
        # Historical query (1 day in the past)
        past_time = datetime(2026, 8, 8, 12, 0, 0, tzinfo=timezone.utc)
        features_past = get_class_features(classroom.class_id, effective_at=past_time)
        assert isinstance(features_past, dict)

    def test_get_class_features_default_uses_canonical_now(self, app):
        """Temporal: default effective_at uses canonical_temporal_resolver."""
        classroom = initialize("chemistry_p1", app)
        
        features = get_class_features(classroom.class_id)
        
        # Verify non-empty (at least some defaults present)
        assert len(features) > 0

    # ========== Temporal Injection Test ==========

    def test_service_uses_injected_reference_time(self, app):
        """Temporal: tests can inject reference_time_utc for reproducibility."""
        classroom = initialize("chemistry_p1", app)
        
        injected_time = datetime(2026, 8, 9, 15, 30, 0, tzinfo=timezone.utc)
        
        features = get_class_features(
            classroom.class_id,
            effective_at=injected_time
        )
        
        # Verify stable results with same injected time
        features_again = get_class_features(
            classroom.class_id,
            effective_at=injected_time
        )
        assert features == features_again
```

---

### D. Test Coverage Requirements

**Per function: 3 tests minimum**
- Happy path test (returns expected data)
- Empty state test (handles missing data gracefully)
- Multi-tenancy test (verifies class_id scoping)

**Total:** 17 functions × 3 tests = 51+ tests

**Coverage Target:** > 80% for class_configuration_query_service module

**All tests must:**
- ✅ Use `initialize()`, `initialize_as_teacher()`, or `initialize_as_student()` from SPEC-TEST-001
- ✅ Use `canonical_temporal_resolver()` for time-dependent queries (SPEC-TIME-001)
- ✅ Inject `reference_time_utc` for reproducibility (no hardcoded times)
- ✅ Import from canonical locations (`tests.helpers.classroom_initializer`, `app.utils.canonical_temporal_resolver`)
- ✅ Include type hints and docstrings

---

## Implementation Roadmap

### Step-by-Step Execution

**Step 1: Create Service Module** (1–2 hours)
```bash
# Create file with all 17 function signatures
# Add comprehensive docstrings (copy from Section 5)
# Add type hints for all parameters and returns
touch app/services/class_configuration_query_service.py
```

**Step 2: Implement Each Function** (4–6 hours)
```python
# For each function:
# 1. Implement query logic (SQLAlchemy ORM)
# 2. Enforce class_id scoping
# 3. Handle temporal queries with canonical_temporal_resolver()
# 4. Add error handling and edge cases
# 5. Return type matches spec exactly
```

**Step 3: Write Comprehensive Tests** (6–8 hours)
```bash
# Create tests/test_class_configuration_query_service.py
# 3 tests per function (51+ tests total)
# All using SPEC-TEST-001 and SPEC-TIME-001
pytest tests/test_class_configuration_query_service.py
```

**Step 4: Refactor Routes** (4–6 hours)
```python
# For each route in app/routes/admin.py, analytics.py, main.py:
# 1. Replace direct db.session.query() with service function calls
# 2. Update imports
# 3. Test route still works (no HTTP test failures)
```

**Step 5: Audit & Verify** (1–2 hours)
```bash
# Grep audit: zero direct schema queries in routes
grep -r "ClassEconomy.query\|PayrollSettings.query\|RentSettings.query" app/routes/
# Should return ZERO matches

# Run full test suite
pytest tests/

# Check coverage
pytest --cov=app.services.class_configuration_query_service tests/
```

**Step 6: Documentation & Commit** (1 hour)
```bash
# Update CHANGELOG.md
# Create PR to codex/v2.0
# Commit message: "Phase 3: Implement class configuration query service (17 functions)"
```

**Total Estimated Time:** 16–25 hours (2–3 days with interruptions)

---

### Routes Requiring Refactoring

**Admin Routes (`app/routes/admin.py`):**
- `/admin/<join_code>/settings` — class configuration page
- `/admin/<join_code>/settings/payroll` — payroll settings page
- `/admin/<join_code>/settings/rent` — rent settings page
- `/admin/<join_code>/settings/banking` — banking settings page
- Any route reading ClassEconomy, PayrollSettings, RentSettings, etc.

**Analytics Routes (`app/routes/analytics.py`):**
- `/admin/analytics/class/<join_code>` — class analytics (uses CWI, policy mode)

**Main Routes (`app/routes/main.py`):**
- Any route listing classes or checking configuration

### Refactoring Pattern

**BEFORE (Direct DB access):**

```python
class_econ = ClassEconomy.query.filter_by(class_id=class_id).first()
payroll = PayrollSettings.query.filter_by(class_id=class_id).first()
```

**AFTER (Service layer):**

```python
from app.services.class_configuration_query_service import (
    get_class_economy,
    get_payroll_settings,
)

class_econ = get_class_economy(class_id)
payroll = get_payroll_settings(class_id)
```

---

## Detailed Citations

### A. Tracking & Planning Documents

| Document | Location | Purpose | Phase 3 Relevance |
|----------|----------|---------|-------------------|
| CLASS_CONFIG_PHASE3_PLAN.md | docs/TRACKING/ | Original Phase 3 plan | Defines 15+ functions, refactoring scope |
| CLASS_PHASE2_PERSISTENCE_DELTA.md | docs/TRACKING/ | Phase 2 completion | Schema foundation (EconomicEngine, ClassFeature) |
| DOMAIN_PROGRESS_MATRIX_2026.md | docs/TRACKING/ | Master progress tracker | Class Config Phase 2 ✅, Phase 3-4 pending |

### B. Constitutional Domain Specifications

| Document | Location | Authority | Relevance |
|----------|----------|-----------|-----------|
| DOM-CLASS-001 | docs/DOMAIN/ | Tier 1 (Constitutional) | Class Configuration domain ownership of classes, economic-engine, class_features |
| DOM-CLASS-002 | docs/DOMAIN/ | Tier 1 (Constitutional) | CWI, policy modes (tight/default/comfortable), payroll/rent/banking/hall_pass governance |
| DOM-CLASS-003 | docs/DOMAIN/ | Tier 1 (Constitutional) | Append-only policy evolution, immutable economic versioning |

### C. Constitutional Invariants

| Document | Location | Authority | Relevance |
|----------|----------|-----------|-----------|
| INV-CORE-001 | docs/INVARIANT/CORE/ | Foundational | Authority hierarchy: INV > DOM > FEAT |
| INV-ARC-009 | docs/INVARIANT/ARCHITECTURE/ | Architectural | Domain authority for state: Class Config owns schema and queries |
| INV-ARC-015 | docs/INVARIANT/ARCHITECTURE/ | Architectural | Temporal model: class_timezone immutability, effective_at semantics |
| INV-ARC-016 | docs/INVARIANT/ARCHITECTURE/ | Architectural | Audit lineage: immutable versioning via previous_version_id |
| INV-ARC-007 | docs/INVARIANT/ARCHITECTURE/ | Architectural | GET handlers must be pure (no mutations) |

### D. Specification Documents

| Document | Location | Purpose | Phase 3 Relevance |
|----------|----------|---------|-------------------|
| SPEC-ECON-001 | docs/SPEC/ | Savings interest rules | Interest rate, compound_frequency configuration |
| SPEC-ECON-002 | docs/SPEC/ | Policy visibility | Justifies effective_at parameter in feature queries |
| SPEC-ECON-003 | docs/SPEC/ | CWI & policy calculations | CWI derivation, policy-mode ratio bands, validation constraints |
| SPEC-TEST-001 | tests/helpers/classroom_initializer.py | Canonical test initializer | Mandatory for all Phase 3 tests |
| SPEC-TIME-001 | app/utils/canonical_temporal_resolver.py | Canonical temporal resolver | Mandatory for all temporal queries in Phase 3 |

### E. Operations & Procedures

| Document | Location | Purpose | Phase 3 Relevance |
|----------|----------|---------|-------------------|
| SOP-DEV-002 | docs/STANDARD_OPERATING_PROCEDURES/DEVOPS/ | 10-phase domain reconstruction | Phase 3 is step 3 (Primitives) |
| SOP-DEV-002a | docs/STANDARD_OPERATING_PROCEDURES/DEVOPS/ | Phase 3 audit procedures | Query verification, route refactoring validation, multi-tenancy tests |

### F. Project Rules

| Document | Location | Constraint | Phase 3 Impact |
|----------|----------|-----------|----------------|
| multi-tenancy.md | .claude/rules/ | Multi-tenancy scoping | All queries MUST scope by class_id; never use teacher_id alone |
| testing.md | .claude/rules/ | Testing requirements | Happy path, empty state, multi-tenancy tests for each function |
| documentation.md | .claude/rules/ | Doc standards | Update CHANGELOG.md, function docstrings |
| security.md | .claude/rules/ | Security guidelines | Phase 3 (read-only) doesn't mutate; mutation security checks belong in Phase 4 |

---

## Pre-Implementation Checklist

### Environment & Prerequisites

- [ ] Current branch: `class-config-phase3` (or feature branch off `codex/v2.0`)
- [ ] Latest from `codex/v2.0` merged in
- [ ] Phase 2 ✅ confirmed complete (EconomicEngine, ClassFeature tables created)
- [ ] pytest running and baseline tests passing
- [ ] All dependencies installed (`flask-sqlalchemy`, `pytz`, etc.)

### Understanding & Knowledge

- [ ] Read all sections of this document thoroughly
- [ ] Reviewed DOM-CLASS-001/002/003 (domain authority)
- [ ] Reviewed INV-CORE-001, INV-ARC-009/015/016 (constitutional invariants)
- [ ] Reviewed SPEC-TEST-001 usage patterns (`initialize()` function)
- [ ] Reviewed SPEC-TIME-001 usage patterns (`canonical_temporal_resolver()` function)
- [ ] Understand multi-tenancy scoping rules (class_id as canonical scope)
- [ ] Understand temporal query semantics (effective_at, deleted_at, created_at)

### Implementation Setup

- [ ] Create `app/services/class_configuration_query_service.py`
- [ ] Create `tests/test_class_configuration_query_service.py`
- [ ] Set up test fixtures using `initialize()`, `initialize_as_teacher()`, `initialize_as_student()`
- [ ] Confirm `conftest.py` provides `app` and `client` fixtures

### Quality Gates

- [ ] All 17 functions have comprehensive docstrings (Args, Returns, Note, Example)
- [ ] All functions fully type-hinted (parameter types, return types)
- [ ] All functions tested with happy path, empty state, multi-tenancy (51+ tests)
- [ ] All tests passing (pytest with 80%+ coverage)
- [ ] Zero direct schema queries in routes (grep audit passes)
- [ ] CHANGELOG.md updated
- [ ] Code review approved
- [ ] CI/CD pipeline green

---

## Summary: Phase 3 At a Glance

| Aspect | Detail |
|--------|--------|
| **Phase** | 3 (Primitives — Core queries in service layer) |
| **Domain** | Class Configuration (DOM-CLASS-001) |
| **Objective** | Centralize 17 read-only query functions; decouple routes from schema |
| **Primary File** | `app/services/class_configuration_query_service.py` |
| **Functions to Implement** | 17 (2 entity, 3 engine, 3 feature, 4 settings, 2 derived, 2 state, 1 initial) |
| **Tests Required** | 51+ (3 per function: happy path, empty state, multi-tenancy) |
| **Routes to Refactor** | 8+ in admin.py, analytics.py, main.py |
| **Authority Hierarchy** | INV-CORE-001 → INV-ARC-009/015/016 → DOM-CLASS-001/002/003 → SPEC-ECON-003 → Phase 3 |
| **Key Constraints** | Class-scoped queries only; no direct schema access in routes; temporal resolver mandatory; SPEC-TEST-001 for tests; SPEC-TIME-001 for time |
| **Estimated Effort** | 2–3 days (implementation + tests + refactoring + audit) |
| **Definition of Done** | All 17 functions implemented & tested, all routes refactored, zero direct queries in routes, grep audit passes, PR merged |
| **Blocked By** | Nothing (Phase 2 ✅ complete) |
| **Blocks** | Phase 4 (FEAT Mutation Boundary) |

---

**Created:** 2026-08-09  
**Status:** Ready for implementation  
**Version:** 1.0 (Comprehensive synthesis from CLASS_CONFIG_PHASE3_PLAN.md + governance + testing)  
**Next Step:** Begin Step 1 (create query service module)

---

## Document Navigation

- **For Objective & Deliverables:** See Section 2
- **For Success Criteria:** See Section 3
- **For Constraints:** See Section 4
- **For Service Function Specs:** See Section 5
- **For Testing Patterns:** See Section 6
- **For Implementation Steps:** See Section 7
- **For Citations:** See Section 8
- **For Pre-Impl Checklist:** See Section 9

---

**Authority Chain:**
- INV-CORE-001 (Capability-Based Architecture)
- INV-ARC-009 (Domain Authority for State)
- INV-ARC-015 (Temporal Model)
- INV-ARC-016 (Audit Lineage)
- DOM-CLASS-001/002/003 (Class Configuration Domain)
- SPEC-ECON-003 (Economic Engine Calculation)
- SPEC-TEST-001 (Canonical Test Initializer)
- SPEC-TIME-001 (Canonical Temporal Resolver)
- Phase 3 Implementation
