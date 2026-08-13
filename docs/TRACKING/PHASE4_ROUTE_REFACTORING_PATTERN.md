# Phase 4 Route Refactoring Pattern

| Reference | Version | Effective Date | Status |
|---|---|---|---|
| Phase 4 Pattern | 1.0 | 2026-08-10 | DOCUMENTED |

---

## Overview

Phase 4 (Legal Mutation Boundary) requires all routes to call canonical FEATs for mutations and service functions for reads. This document defines the refactoring pattern applied to the first route and serves as a template for refactoring the remaining 53 routes.

---

## Completed Refactoring Example

### Route: `/feature-settings/period/<period>` (POST)

**File:** `app/routes/admin.py` line 9976

**What Changed:**
- **BEFORE:** Used legacy `replace_enabled_class_features()` function with `FEATContext("FEAT-ADMN-001")`
- **AFTER:** Calls `execute_enable_feature()` and `execute_disable_feature()` from FEAT-CLASS-004 for each feature that changed state

**Key Differences:**

#### Before (Legacy Pattern)
```python
with FEATContext("FEAT-ADMN-001", idempotency_key=idempotency_key):
    replace_enabled_class_features(class_id, enabled_features)
```

#### After (Phase 4 Pattern)
```python
# Get initial economic engine (required by FEAT-CLASS-004)
initial_engine = get_initial_economic_engine(class_id)

# For each feature, call the appropriate FEAT
for feature_name in features_to_process:
    requested_state = bool(data.get(feature_name))
    current_state = is_feature_enabled(class_id, feature_name)
    
    if requested_state == current_state:
        continue  # No change needed
    
    if requested_state:
        result = execute_enable_feature(
            canonical_context=canonical_context,
            class_id=class_id,
            feature=feature_name,
            economic_version_id=initial_engine.economic_version_id,
            correlation_id=f"admin:feature-settings:{class_id}:{feature_name}",
        )
    else:
        result = execute_disable_feature(
            canonical_context=canonical_context,
            class_id=class_id,
            feature=feature_name,
            correlation_id=f"admin:feature-settings:{class_id}:{feature_name}",
        )
```

---

## Refactoring Checklist

When refactoring a route, follow this checklist:

### 1. Identify the Mutation Type

- [ ] **Feature Enable/Disable** → Use FEAT-CLASS-004 (`execute_enable_feature` / `execute_disable_feature`)
- [ ] **Economic Policy Transition** → Use FEAT-CLASS-005 (`execute_transition_economic_policy`)
- [ ] **Class Creation** → Use FEAT-CLASS-001 (`execute_create_class_boundary`)
- [ ] **Read-Only** → Use service functions from `class_configuration_query_service`

### 2. Get Required Context

For mutation routes:
- [ ] Get `canonical_context` from `g.canonical_context`
- [ ] Get initial `EconomicEngine` via `get_initial_economic_engine(class_id)`
- [ ] Get current state via service functions (`is_feature_enabled()`, etc.)

### 3. Replace Direct Queries

- [ ] Remove `ClassEconomy.query.filter_by(...)`
- [ ] Remove `ClassFeature.query.filter_by(...)`
- [ ] Replace with service function calls (readonly) or FEAT calls (mutations)

### 4. Call Appropriate FEAT

For mutations:
- [ ] Pass `canonical_context` with validated `user_id`, `class_id`, `seat_id`, `actor_role`
- [ ] Pass `correlation_id` for audit trail
- [ ] Handle error responses from FEAT (check `result.success` and `result.error_code`)

### 5. Test the Route

- [ ] Route still accepts same request format
- [ ] Route returns same response format
- [ ] FEAT is called with correct parameters
- [ ] Error handling matches original behavior

---

## Service Functions by Capability

### Feature Management
- `is_feature_enabled(class_id: str, feature: str) -> bool`
- `get_class_feature_settings(join_code, class_id) -> dict`
- **FEAT:** `execute_enable_feature()`, `execute_disable_feature()`

### Economic State
- `get_initial_economic_engine(class_id: str) -> EconomicEngine | None`
- `get_class_economy(class_id: str) -> ClassEconomy | None`
- **FEAT:** `execute_transition_economic_policy()`

### Class Management
- `get_all_classes_by_teacher(user_id: int) -> list[ClassEconomy]`
- **FEAT:** `execute_create_class_boundary()`

### Settings Queries
- `get_payroll_settings(class_id: str) -> PayrollSettings | None`
- `get_rent_settings(class_id: str) -> RentSettings | None`
- `get_banking_settings(class_id: str) -> BankingSettings | None`
- `get_hall_pass_settings(class_id: str) -> HallPassSettings | None`

---

## Correlation ID Naming Convention

Correlation IDs should follow the pattern:
```
<domain>:<operation>:<identifier>
```

Examples:
- `admin:feature-settings:abc123:payroll` - Feature toggle by admin for class abc123
- `api:policy-transition:def456:comfortable` - Policy transition via API for class def456
- `system:onboarding:ghi789:default` - System setup for class ghi789

---

## Error Handling Pattern

All FEAT calls return result objects with success/error fields:

```python
result = execute_enable_feature(...)

if not result.success:
    return jsonify({
        'status': 'error',
        'message': 'Feature enablement failed',
        'error_code': result.error_code,
        'details': result.error_message,
    }), 400 or 500  # Depends on error type
```

Common FEAT-CLASS error codes:
- `FEATURE_NOT_ENABLED` - Feature is not currently enabled
- `INVALID_POLICY_MODE` - Unknown policy mode
- `INVALID_TEMPORAL_ORDER` - Timestamp is in the past
- `CLASS_SCOPE_MISMATCH` - Teacher doesn't own this class
- `TEACHER_NOT_AUTHORIZED` - Actor is not a teacher

---

## Routes Remaining (53 total)

Priority order for refactoring:

### CRITICAL (Route-level FEAT mutations)
- [ ] `settings` POST - May call multiple FEATs
- [ ] `rent_settings` POST - Complex (CLASS + Obligations domain)
- [ ] `apply_economy_rebalance` POST - FEAT-CLASS-005
- [ ] `update_expected_weekly_hours` POST - FEAT-CLASS-001/005

### HIGH (Feature/Config mutations)
- [ ] `set_class_timezone` POST - FEAT-CLASS-001
- [ ] `delete_join_code` POST - FEAT-CLASS-001
- [ ] `banking_settings_update` POST - CLASS config
- [ ] `feature_settings` GET - Verify service calls

### MEDIUM (Student roster operations)
- [ ] `add_individual_student` POST - FEAT-CLASS-001 + IDEN
- [ ] `add_manual_student` POST - FEAT-CLASS-001 + IDEN
- [ ] `upload_students` POST - FEAT-CLASS-001 + IDEN
- [ ] `edit_student` POST - IDEN domain read
- [ ] `delete_student` POST - IDEN domain
- [ ] (10 more student-related routes)

### LOW (Display/Analytics - Read-Only)
- [ ] `dashboard` GET - Use `get_all_classes_by_teacher()`
- [ ] `students` GET - Use `get_class_economy()`
- [ ] `payroll` GET - Use service functions
- [ ] (11 more read-only routes in admin.py, analytics.py, api.py, student.py)

---

## Testing Strategy for Phase 4

**Unit Tests (Per Route):**
- Verify route calls correct FEAT or service function
- Verify route returns same HTTP response format
- Verify error handling for FEAT errors

**Integration Tests (Cross-Route):**
- Verify no direct model queries in routes
- Verify all mutations go through FEATs
- Verify all reads use service functions

**Regression Tests:**
- Run full test suite to ensure backward compatibility
- Verify existing route tests still pass
- Check for any breaking changes in API contracts

---

## Progress Tracking

| File | Routes | CRITICAL | HIGH | MEDIUM | LOW | Status |
|------|--------|----------|------|--------|-----|--------|
| admin.py | 36 | 4 | 5 | 10 | 17 | 1 DONE* |
| analytics.py | 3 | 0 | 0 | 0 | 3 | 🔴 PENDING |
| api.py | 8 | 0 | 1 | 2 | 5 | 🔴 PENDING |
| student.py | 6 | 1 | 1 | 2 | 2 | 🔴 PENDING |
| main.py | 1 | 0 | 0 | 0 | 1 | 🔴 PENDING |
| **TOTAL** | **54** | **5** | **7** | **14** | **28** | **1 DONE** |

*`update_period_feature_settings` - refactored to use FEAT-CLASS-004

---

## Next Steps

1. **Verify the refactored route** - Manual testing or integration test
2. **Apply pattern to CRITICAL routes** - 5 routes with core CLASS mutations
3. **Apply pattern to HIGH routes** - 7 routes with feature/config changes
4. **Batch apply to MEDIUM routes** - Student roster operations
5. **Verify read-only routes** - Ensure they use service functions
6. **Run Phase 4 audit** - Confirm all 54 routes follow pattern

---

**Last Updated:** 2026-08-10  
**Authority:** SOP-DEV-002 Phase 4 (Legal Mutation Boundary)  
**Status:** Initial pattern documented, 1/54 routes refactored
