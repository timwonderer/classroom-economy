# Class B Remediation Plan: Eliminating `join_code` Domain Query Filters

**Status:** Approved plan
**Date:** 2026-06-28
**Audit reference:** `docs/TRACKING/V2_CONTEXT_RESOLUTION_AUDIT.md`
**Violation count:** 48 sites across 10 files

---

## Target State

Every domain-model query that scopes data to a class filters by `class_id`, never by `join_code`. The `join_code` column remains on models (it is the user-facing class identifier for login/recovery flows) but is never used as a query discriminator for data access. Helper functions that accept `join_code` parameters are refactored to accept `class_id`.

Two accepted deviations: invariant-integrity checks in `deletion.py` and `admin.py` that intentionally query by `join_code` to find rows missing `class_id` (data integrity assertions, not data access).

---

## Phase 1: Utils and Services (5 sites)

**Files:** `app/utils/seat_scope.py`, `app/utils/transaction_idempotency.py`, `app/utils/issue_helpers.py`, `app/services/identity_service.py`

Foundational changes — route code depends on these helpers.

### 1A. `app/utils/seat_scope.py` line 18

Remove `join_code` fallback in `get_seat_ids_for_student_join()`. If `class_row` is None, return `[]`. The function is already marked "legacy compatibility shim" in its own docstring.

```python
# Before
if class_row:
    query = query.filter(Seat.class_id == class_row.class_id)
else:
    query = query.filter(Seat.join_code == join_code)

# After
if not class_row:
    return []
query = query.filter(Seat.class_id == class_row.class_id)
```

### 1B. `app/utils/transaction_idempotency.py` lines 65-66

Remove `elif join_code:` fallback branch in `get_idempotent_transaction()`:

```python
# Before
if class_id:
    query = query.filter(Transaction.class_id == class_id)
elif join_code:
    query = query.filter(Transaction.join_code == join_code)

# After
if class_id:
    query = query.filter(Transaction.class_id == class_id)
```

Remove `join_code` parameter from `get_idempotent_transaction()` signature. Update `purchase_transaction_key()` to use `class_id` instead of `join_code` in key construction. Update all callers.

### 1C. `app/utils/issue_helpers.py` line 87

`create_context_snapshot()` already resolves `class_id` on line 52-53, but queries `Transaction` by `join_code` on line 87.

```python
# Before (line 87)
Transaction.query.filter_by(student_id=student.id, join_code=join_code)

# After
Transaction.query.filter_by(student_id=student.id, class_id=class_id)
```

Change function signature from `join_code` to `class_id`, remove the `ClassEconomy` lookup (lines 52-55). Update `create_issue()` signature similarly. Update all callers in `student.py`.

### 1D. `app/services/identity_service.py` line 93

```python
# Before
StudentBlock.join_code == (seat.join_code if seat else None),

# After
StudentBlock.class_id == (seat.class_id if seat else None),
```

### 1E. Accepted deviations (NOT changed)

- `app/utils/deletion.py` line 44-45: intentionally finds rows with `join_code` but missing `class_id`
- `app/routes/admin.py` ~line 1285: same invariant check inlined

**Validation:**
```bash
grep -n "\.join_code ==" app/utils/seat_scope.py app/utils/transaction_idempotency.py app/utils/issue_helpers.py app/services/identity_service.py
# Expected: zero hits
```

---

## Phase 2: `app/routes/analytics.py` (5 sites)

All follow identical pattern: handler resolves `class_id` via canonical context, looks up `join_code` from `ClassEconomy`, filters domain model by `join_code`. Fix: filter by `class_id` directly.

| Line | Model | Fix |
|------|-------|-----|
| 252 | `AnalyticsAlert` | `.class_id == class_id` |
| 266 | `AnalyticsEvent` | `.class_id == class_id` |
| 389 | `AnalyticsAlert` | `.class_id == class_id` |
| 438 | `AnalyticsAlert` | `.class_id == class_id` |
| 479 | `AnalyticsEvent` | `.class_id == class_id` |

Remove intermediate `join_code = class_row.join_code` assignments that exist solely to feed these filters.

**Validation:**
```bash
grep -n "\.join_code ==" app/routes/analytics.py
# Expected: zero hits
```

---

## Phase 3: `app/routes/student.py` (8 sites)

All handlers have `class_id` from `g.canonical_context.class_id` or seat context.

| Line | Model | Source of `class_id` |
|------|-------|---------------------|
| 1244 | `Announcement` | `context.class_id` |
| 1639 | `InsuranceEnrollment` | `context.class_id` |
| 1645 | `InsurancePolicy` | `context.class_id` |
| 1687 | `InsuranceClaim` | `context.class_id` |
| 1791 | `InsuranceEnrollment` | `context.class_id` |
| 1993 | `Transaction` | `enrollment.class_id` |
| 2245 | `StoreItem` | `context.class_id` |
| 2812 | `Transaction` | refactor `_filter_valid_rent_payments` to take `class_id` |

**Validation:**
```bash
grep -n "\.join_code ==" app/routes/student.py | grep -v ClassEconomy
# Expected: zero hits
```

---

## Phase 4: `app/routes/admin.py` (25 sites)

Largest batch. All handlers have `class_id` via `_resolve_admin_class_context()` or `require_admin_feature_scope()`.

### Group 4A — Seat queries (6 sites)

| Line | Handler |
|------|---------|
| 1096 | `_student_scope_subquery_for_join_code` |
| 1118 | `_get_claimed_teacher_block_for_join_code` |
| 4944 | seat transfer |
| 4955 | seat transfer |
| 8744 | hall pass |
| 10425 | CSV export |

Rename `_student_scope_subquery_for_join_code(join_code)` → `_student_scope_subquery_for_class(class_id)`. Rename `_get_claimed_teacher_block_for_join_code(...)` similarly. All: `Seat.join_code ==` → `Seat.class_id ==`. Update all callers.

### Group 4B — Transaction + TapEvent (3 sites)

Lines 4707, 4732, 4733 in student detail view. Swap to `class_id`.

### Group 4C — InsuranceEnrollment + InsuranceClaim (5+1 sites)

Lines 7517, 7527, 7540, 7551, 10409. `selected_class_id` already resolved; swap all.

### Group 4D — HallPassLog (3 sites)

Lines 8217, 8227, 8237. Swap to `HallPassLog.class_id == selected_class_id`.

### Group 4E — Other models (6 sites)

| Line | Model | Change |
|------|-------|--------|
| 6048 | `RedemptionAuditLog` | `.class_id == selected_class_id` |
| 1664 | `ClassMembership` | `.class_id == class_id`, rename `_admin_owns_join_code` → `_admin_owns_class` |
| 10345 | `ClassMembership` | `.class_id == selected_class_id` |
| 8649 | `PayrollSettings` | `.class_id == class_id` |

**Validation:**
```bash
grep -c "\.join_code ==" app/routes/admin.py
# Expected: only the 2 accepted invariant-check deviations
```

---

## Phase 5: `app/routes/main.py` (1) + `app/routes/recovery.py` (1)

### 5A. `main.py` line 336

`HallPassLog.join_code == selected_join_code` is redundant — line 337 already filters by `class_id`. Remove the `join_code` filter.

### 5B. `recovery.py` line 139

`Seat.join_code == join_code` where `join_code` is user input. Resolve to `class_id` first:

```python
# Before
Seat.join_code == join_code,

# After
class_row = ClassEconomy.query.filter_by(join_code=join_code).first()
if not class_row:
    flash("Invalid code.", "error")
    return redirect(url_for('recovery.account_lookup'))
# Then:
Seat.class_id == class_row.class_id,
```

**Validation:**
```bash
grep -n "\.join_code ==" app/routes/main.py app/routes/recovery.py
# Expected: zero hits
```

---

## Execution Order and Dependencies

```
Phase 1 (utils/services)  ← no dependencies
  ├→ Phase 2 (analytics.py)     ← independent
  ├→ Phase 3 (student.py)       ← depends on 1C (issue_helpers signature)
  ├→ Phase 4 (admin.py)         ← depends on 1A, 1B (seat_scope, idempotency signatures)
  └→ Phase 5 (main.py + recovery.py) ← independent
```

Phases 2, 4, 5 are independent of each other. Phase 3 depends on Phase 1C. All phases can be merged individually.

---

## Accepted Deviations (2 sites, not counted in 48)

1. **`app/utils/deletion.py` line 45** — `model.join_code == join_code` in `_assert_class_scope_integrity()`. Intentional: finds rows tagged with `join_code` that lack `class_id` (data integrity assertion).
2. **`app/routes/admin.py` ~line 1285** — Same invariant check inlined in the deletion handler.

These queries must use `join_code` because their purpose is to detect rows where `class_id` was never backfilled. Swapping to `class_id` would defeat the check.

---

## Final Validation Script (CI gate after all phases)

```bash
# Zero join_code query filters in route/service/util code
grep -rn "\.join_code ==" app/routes/ app/utils/ app/services/ --include='*.py' \
  | grep -v 'deletion.py.*class_id.is_(None)' \
  | grep -v 'admin.py.*class_id.is_(None)' \
  && echo "FAIL: join_code query filters remain" && exit 1 \
  || echo "PASS: zero join_code query filters"
```

---

## Testing Requirements

### Per-phase tests

| Phase | Tests |
|-------|-------|
| 1 | `get_seat_ids_for_student_join` returns `[]` when class not found; `get_idempotent_transaction` works without `join_code` param; `create_context_snapshot` accepts `class_id` |
| 2 | Analytics alert/event queries return correct results filtered by `class_id` |
| 3 | Student insurance, store, rent, announcement views all scope by `class_id` |
| 4 | Admin student detail, insurance management, hall pass, CSV export, store management all scope by `class_id` |
| 5 | Hall pass verification works without redundant filter; recovery resolves `join_code` → `class_id` before querying |

### Regression gate

Existing test suite pass count must not decrease from current baseline after each phase.

---

**Last Updated:** 2026-06-28
