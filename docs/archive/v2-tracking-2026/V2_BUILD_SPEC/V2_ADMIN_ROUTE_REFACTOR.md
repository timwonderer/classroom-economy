

# V2 Admin Route Refactor Plan

**Status:** In progress, with authority-critical money routes extracted (updated 2026-04-18)
**Scope:** `app/routes/admin.py`

---

## I. Purpose

This document defines the structural refactor plan for the `admin.py` route layer.

The goal is to transition from a monolithic route file containing mixed concerns
into a clean separation of:

- Routes (HTTP interface only)
- Services (business logic)
- Models (data layer)

This refactor does NOT change intended system behavior. Its purpose is to move authority out of routes and into enforceable service and FEAT layers.

## II. Current Completed State

The highest-risk admin money flows are no longer route-owned:

- transaction void delegates to `transaction_void_feat`
- insurance claim approval delegates to `insurance_claim_feat`
- payroll run, manual payment, reward, and fine flows delegate to `admin_adjustment_feat`
- route handlers no longer construct `Transaction` rows inline for these flows

This means the most dangerous admin exceptions are already closed even though `admin.py` remains large.

---

## III. Current State

`admin.py` currently contains:

- Route handlers
- Business logic
- Multi-table database operations
- Destructive workflows (deletion)
- Scope resolution (join_code / class_id)
- Analytics and economy calculations
- Payroll and attendance aggregation

This results in:

- High cognitive load
- Difficult debugging
- Increased risk for destructive operations
- Tight coupling between HTTP and domain logic

---

## IV. Target State

### Architecture

```
routes/   → HTTP interface (thin)
services/ → business logic (heavy)
models/   → data definitions
```

### Route Responsibilities

Routes MUST:

- parse request input
- call appropriate service functions
- return responses

Routes MUST NOT:

- perform multi-table DB logic
- contain business rules
- implement destructive workflows
- compute analytics or financial logic

---

## V. Extraction Plan

Refactoring will be performed incrementally by domain.

---

### 1. Deletion Service (Highest Priority)

**Target:** `services/deletion_service.py`

Move:

- `_hard_delete_join_code_scope`
- `_hard_delete_teacher_account_scope`
- `_delete_*`
- `_assert_transaction_deletion_allowed`

Rationale:

- These represent system invariants
- High risk operations must be isolated

---

### 2. Economy Service

**Target:** `services/economy_service.py`

Move:

- `_build_economy_snapshot_from_analysis`
- `_get_frozen_economy_analysis_payload`
- `_build_policy_summary`
- `_build_rebalance_preview`
- `_build_insurance_recommendation_context`
- `_load_economy_rebalance_context`
- `_apply_rebalance_plan`

Rationale:

- Complex computation logic
- Cross-cutting domain behavior

---

### 3. Payroll Service

**Target:** `services/payroll_service.py`

Move:

- `_build_payroll_preview_state`
- `_resolve_payroll_settings_for_block`
- `auto_tapout_all_over_limit`

Rationale:

- Aggregation-heavy logic
- Independent domain concern

---

### 4. Scope Service (Critical for v2)

**Target:** `services/scope_service.py`

Move:

- `_resolve_class_id`
- `_resolve_join_code_for_block`
- `require_admin_feature_scope`
- `get_admin_feature_settings_for_join_code`
- `is_admin_feature_enabled`

Rationale:

- Centralizes class scoping logic
- Prepares for strict `class_id` enforcement

---

### 5. Roster Service

**Target:** `services/roster_service.py`

Move:

- `_link_student_to_admin`
- `_ensure_teacher_student_seat`

---

## VI. Post-Refactor Route Pattern

### Before

```
@admin_bp.route('/example')
def example():
    # large block of logic
    scope = require_admin_feature_scope(...)
    data = _build_economy_snapshot_from_analysis(...)
    db.session.commit()
```

### After

```
@admin_bp.route('/example')
def example():
    scope = scope_service.resolve_scope_from_request(...)
    data = economy_service.get_snapshot(scope)
    return jsonify(data)
```

---

## VII. Naming Conventions

Service functions MUST follow consistent naming:

- `resolve_*` → identity/scope
- `get_*` → read-only
- `build_*` → computed structures
- `apply_*` → state changes
- `delete_*` → destructive operations

---

## VIII. Guardrails

- No new business logic may be added to `admin.py`
- All new domain logic MUST be implemented in services
- No new money-affecting write path may construct `Transaction` outside `ledger_service`
- Routes exceeding ~50–100 lines SHOULD be refactored

---

## IX. Migration Strategy

Refactor will be performed incrementally:

1. Extract deletion service
2. Extract economy service
3. Extract scope service
4. Extract remaining domains

Each step must:

- preserve behavior
- pass all tests
- avoid schema changes

---

## X. Outcome

After completion:

- `admin.py` becomes a thin orchestration layer
- business logic is modular and testable
- system invariants are isolated
- future architecture enforcement (class_id-only) becomes straightforward

---

## XI. Notes

This refactor aligns with:

- docs/MAP/MAP-CLASS-002_CLASS_SCOPE_NORMALIZATION_TARGET.md
- CI enforcement of join_code boundary

It is a prerequisite for strict enforcement of class-scoped invariants.
