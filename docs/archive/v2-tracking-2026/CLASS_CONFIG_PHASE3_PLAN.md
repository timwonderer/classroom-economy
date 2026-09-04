# Class Configuration Phase 3 Implementation Plan

**Domain:** DOM-CLASS-001  
**Phase:** 3 (Primitives — Core queries in service layer)  
**Status:** PLANNING (2026-08-08)  
**Authority:** SOP-DEV-002a, SPEC-ECON-003, DOM-CLASS-001  

---

## Overview

Phase 3 ("Primitives") requires centralizing all core queries into a dedicated service layer. Routes must NOT make direct database queries; instead, they call service functions.

This document defines the **complete set of Phase 3 primitives** for the Class Configuration domain. Once these are implemented, Phase 4 (FEAT Mutation Boundary) can begin.

---

## Phase 3 Success Criteria

✅ All class configuration queries centralized in `app/services/class_configuration_query_service.py`  
✅ Every route that reads class data calls service functions (no direct `db.session.query()`)  
✅ All service functions documented with docstrings  
✅ Service functions tested (Phase 8 coverage)  
✅ No schema coupling in routes (all queries live in service layer)

---

## Class Configuration Query Service Functions

### Module: `app/services/class_configuration_query_service.py`

All functions are read-only (no mutations) and class-scoped.

#### 1. Class Entity Queries

```python
def get_class_economy(class_id: str) -> ClassEconomy | None:
    """Get the ClassEconomy entity for a class.
    
    Args:
        class_id: The class to retrieve
        
    Returns:
        ClassEconomy instance or None if not found
    """
```

```python
def get_class_by_join_code(join_code: str) -> ClassEconomy | None:
    """Get the ClassEconomy entity by public join_code alias.
    
    Args:
        join_code: Public class alias (e.g., "CHEM101")
        
    Returns:
        ClassEconomy instance or None if not found
    """
```

#### 2. Economic Engine Queries

```python
def get_current_economic_engine(class_id: str) -> EconomicEngine | None:
    """Get the current (active) EconomicEngine for a class.
    
    The current version is determined from the latest effective ClassFeature state.
    Query the EconomicEngine linked by the most recent ClassFeature record.
    
    Args:
        class_id: The class to retrieve
        
    Returns:
        EconomicEngine instance linked to current feature state, or None if no engine exists
    """
```

```python
def get_economic_engine_history(class_id: str) -> list[EconomicEngine]:
    """Get all EconomicEngine versions for a class in chronological order.
    
    Ordered by created_at DESC (most recent first).
    Use created_at (not effective_at, which does not exist on EconomicEngine).
    
    Args:
        class_id: The class to retrieve history for
        
    Returns:
        List of EconomicEngine instances, ordered by creation time (may be empty)
    """
```

#### 3. Class Feature Queries

```python
def get_class_features(class_id: str, effective_at: datetime | None = None) -> dict[str, ClassFeature]:
    """Get all class features for a class, keyed by feature name.
    
    Returns the state of features as of effective_at (default: now).
    
    Args:
        class_id: The class to retrieve features for
        effective_at: Timestamp to query feature state at (default: canonical now)
        
    Returns:
        Dict mapping feature name -> ClassFeature instance
        Empty dict if class has no features
    """
```

```python
def get_class_feature(class_id: str, feature: str, effective_at: datetime | None = None) -> ClassFeature | None:
    """Get a specific class feature by name.
    
    Args:
        class_id: The class
        feature: Feature name (e.g., 'payroll', 'hall_pass', 'rent')
        effective_at: Timestamp to query at (default: canonical now)
        
    Returns:
        ClassFeature instance or None if not found/disabled
    """
```

```python
def get_class_feature_history(class_id: str, feature: str) -> list[ClassFeature]:
    """Get all versions of a specific class feature in chronological order.
    
    Ordered by effective_at DESC (most recent first).
    
    Args:
        class_id: The class
        feature: Feature name
        
    Returns:
        List of ClassFeature instances (may be empty)
    """
```

#### 4. Settings Queries (Payroll, Rent, Banking, Hall Pass)

```python
def get_payroll_settings(class_id: str) -> PayrollSettings | None:
    """Get payroll configuration for a class.
    
    Includes hourly_pay_rate, expected_weekly_hours, CWI, policy mode.
    
    Args:
        class_id: The class
        
    Returns:
        PayrollSettings instance or None
    """
```

```python
def get_rent_settings(class_id: str) -> RentSettings | None:
    """Get rent configuration for a class.
    
    Includes rent_amount, rent_frequency, rent_payday, grace period.
    
    Args:
        class_id: The class
        
    Returns:
        RentSettings instance or None
    """
```

```python
def get_banking_settings(class_id: str) -> BankingSettings | None:
    """Get banking configuration for a class.
    
    Includes interest_rate, interest_frequency, savings_threshold.
    
    Args:
        class_id: The class
        
    Returns:
        BankingSettings instance or None
    """
```

```python
def get_hall_pass_settings(class_id: str) -> HallPassSettings | None:
    """Get hall pass configuration for a class.
    
    Includes grant_frequency, grant_amount, expiration_days.
    
    Args:
        class_id: The class
        
    Returns:
        HallPassSettings instance or None
    """
```

#### 5. CWI and Economic Derived Values

```python
def calculate_cwi(class_id: str) -> float | None:
    """Calculate the current Classroom Wage Index (CWI) for a class.
    
    CWI = hourly_pay_rate × expected_weekly_hours
    
    Args:
        class_id: The class
        
    Returns:
        CWI as a float, or None if payroll settings not found
    """
```

```python
def get_policy_mode(class_id: str) -> str | None:
    """Get the current economic policy mode for a class.
    
    Returns the policy_mode from current EconomicEngine.
    Examples: 'tight', 'default', 'comfortable'
    
    Args:
        class_id: The class
        
    Returns:
        Policy mode string or None
    """
```

#### 6. Configuration State Queries

```python
def is_feature_enabled(class_id: str, feature: str) -> bool:
    """Check if a specific feature is enabled for a class.
    
    Returns True if feature exists, is not deleted, and 
    effective_at <= canonical_now.
    
    Args:
        class_id: The class
        feature: Feature name
        
    Returns:
        True if enabled, False otherwise
    """
```

```python
def get_all_classes_by_teacher(teacher_user_id: int) -> list[ClassEconomy]:
    """Get all classes owned by a teacher.
    
    Ordered by created_at DESC (most recent first).
    
    Args:
        teacher_user_id: The teacher's User.id
        
    Returns:
        List of ClassEconomy instances (may be empty)
    """
```

#### 7. Teacher-Facing Configuration Guidance

```python
def suggest_economic_mode(class_size: int, weekly_hours: float) -> str:
    """Suggest a policy mode based on class context.
    
    Returns advisory suggestion ("tight", "default", or "comfortable").
    Teachers can override the suggestion.
    
    Args:
        class_size: Number of students in class
        weekly_hours: Expected earning hours per week
        
    Returns:
        Suggested policy mode
    """
```

```python
def validate_payroll_rate(hourly_pay_rate: float, policy_mode: str) -> tuple[bool, str | None]:
    """Validate a proposed hourly pay rate for reasonableness.
    
    Returns (is_valid, warning_message).
    - is_valid=True: rate accepted (may still have advisory warning)
    - is_valid=False: rate violates hard constraint
    
    Args:
        hourly_pay_rate: Proposed rate
        policy_mode: Class policy mode
        
    Returns:
        (is_valid: bool, warning: str | None)
    """
```

---

## Refactoring Scope (Routes Using These Queries)

### Routes that need Phase 3 refactoring

**Admin Routes (`app/routes/admin.py`):**

- `/admin/<join_code>/settings` - class configuration page
- `/admin/<join_code>/settings/payroll` - payroll settings page
- `/admin/<join_code>/settings/rent` - rent settings page
- `/admin/<join_code>/settings/banking` - banking settings page
- Any route that reads ClassEconomy, PayrollSettings, RentSettings, etc.

**Analytics Routes (`app/routes/analytics.py`):**

- `/admin/analytics/class/<join_code>` - class analytics (uses CWI, policy mode)

**Main Routes (`app/routes/main.py`):**

- Any route that lists classes or checks configuration

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

## Testing Requirements (Phase 8)

Each service function requires:

1. **Happy path test** — Function returns expected data
2. **Empty state test** — Function handles missing data gracefully
3. **Multi-tenancy test** — Query respects class_id scope (if applicable)

Example test structure:

```python
def test_get_payroll_settings_returns_class_scoped_data(app):
    """Verify payroll settings query respects class scope."""
    classroom = initialize("chemistry_p1", app)
    
    payroll = get_payroll_settings(classroom.class_id)
    
    assert payroll is not None
    assert payroll.class_id == classroom.class_id
    assert payroll.hourly_pay_rate is not None
```

---

## Dependencies (What blocks Phase 3)

**Blocked by:** Nothing — Phase 2 is complete  
**Blocks:** Phase 4 (FEAT Mutation Boundary)

Phase 3 is pure read-side, so it can proceed immediately after Phase 2.

---

## Implementation Order

**Step 1:** Create `app/services/class_configuration_query_service.py` with all functions above  
**Step 2:** Add comprehensive docstrings and type hints  
**Step 3:** Test each function (Phase 8 coverage)  
**Step 4:** Refactor routes to use service layer (one route at a time)  
**Step 5:** Verify no direct db.session.query() in routes  
**Step 6:** Document query coverage in this plan

---

## Success Checklist for Phase 3 Completion

- [ ] `class_configuration_query_service.py` created with all 15+ functions
- [ ] Every function has docstring with Args and Returns
- [ ] Type hints complete for all parameters and returns
- [ ] All service functions tested (happy path, empty state, multi-tenancy)
- [ ] Admin routes refactored to use service functions (not direct queries)
- [ ] Analytics routes refactored to use service functions
- [ ] Main routes refactored to use service functions
- [ ] Zero direct `ClassEconomy.query` in routes
- [ ] Zero direct `PayrollSettings.query` in routes
- [ ] Zero direct `RentSettings.query` in routes
- [ ] Zero direct `BankingSettings.query` in routes
- [ ] Zero direct `HallPassSettings.query` in routes
- [ ] Phase 3 audit passes (grep confirms all queries in service layer)

---

## Phase 4 Prerequisites

Phase 3 completion unblocks Phase 4 (FEAT Mutation Boundary), which requires:

1. **FEAT-ECON-001:** Create class and economy
2. **FEAT-ECON-002:** Update economic settings (payroll, rent, banking, hall pass, features)
3. **FEAT-ECON-003:** Change economic policy mode
4. Mutations for each settings type

Once Phase 3 is complete, Phase 4 can begin defining these FEATs.

---

## Links

- Authority: `docs/DOMAIN/DOM-CLASS-001.md`, `SPEC-ECON-003.md`
- Phase 2 Status: `docs/TRACKING/DOMAIN_PROGRESS_MATRIX_2026.md`
- Phase 3 Concepts: `docs/STANDARD_OPERATING_PROCEDURES/DEVOPS/SOP-DEV-002a_DOMAIN_RECONSTRUCTION_QA_AUDIT.md` (Phase 3 section)

---

**Created:** 2026-08-08  
**Status:** Ready for implementation  
**Next:** Begin Step 1 (create query service)
