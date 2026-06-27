# Class A Remediation Plan: Eliminating Extinct Runtime Identity

**Status:** Approved plan
**Date:** 2026-06-27
**Audit reference:** `docs/TRACKING/V2_CONTEXT_RESOLUTION_AUDIT.md`
**Violation count:** 133 sites across 14 files

---

## Target State

Every request resolves identity exactly once at the decorator boundary via `resolve_canonical_context()`. The result — an immutable `CanonicalContext` or `BoundaryContext` — is stored in `g.canonical_context` and used for the duration of the request. No handler, service, FEAT, or utility reads `session.get('admin_id')`, `session.get('student_id')`, or `session.get('sysadmin_id')`. No bridge function converts canonical identity to extinct identity.

---

## Phase 1: Extend context resolver — `BoundaryContext` + `require_class` parameter

**Files:** `app/services/context_resolver.py`

Add a `BoundaryContext` — a restricted frozen dataclass for authenticated actors without class scope:

```python
@dataclass(frozen=True)
class BoundaryContext:
    user_id: int
    actor_role: str  # "teacher" or "sysadmin"

    def __getattr__(self, name):
        if name in {"class_id", "seat_id"}:
            raise AttributeError(
                "BoundaryContext has no class scope — resolve class selection first"
            )
        forbidden = {"join_code", "teacher_id", "block", "section", "student_id", "admin_id"}
        if name in forbidden:
            raise AttributeError(f"Strict context invariant violation: cannot access {name}")
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
```

Add `require_class=True` parameter to `resolve_canonical_context()`:
- `require_class=True` (default): current behavior — full `CanonicalContext` or exception
- `require_class=False`: when `class_id` is missing, return `BoundaryContext(user_id, actor_role)` for teachers/sysadmins instead of raising. Sysadmins always get `BoundaryContext` (they are forbidden from class context).

**Tests:**
- `BoundaryContext.class_id` raises `AttributeError` with "no class scope"
- `BoundaryContext.admin_id` raises `AttributeError` with "invariant violation"
- `resolve_canonical_context(require_class=False)` returns `BoundaryContext` for teacher with no `last_active_class_id`
- `resolve_canonical_context(require_class=False)` returns `BoundaryContext` for sysadmin
- `resolve_canonical_context(require_class=False)` returns `CanonicalContext` for teacher with valid class+seat

---

## Phase 2: Rewrite `@admin_required` to resolve at boundary

**Files:** `app/auth.py`

Replace the current decorator (which checks `session.get("is_admin")` and calls `get_current_admin()`) with:

1. Call `resolve_canonical_context(require_class=False)`
2. On `ContextNotEstablished` / `ContextMismatch` → redirect to login
3. On `CanonicalContext` with `actor_role == 'teacher'` → store in `g.canonical_context`, proceed
4. On `BoundaryContext` with `actor_role == 'teacher'` → redirect to `admin.create_class` for all endpoints except the classless allowlist
5. Check timeout via `session['last_activity']` (unchanged)
6. No reference to `session.get("admin_id")`, `session.get("is_admin")`, or `get_current_admin()`

Classless endpoint allowlist — teacher without a class can only reach these. There is no class selector for a classless teacher because there is nothing to select. The teacher remains at `create_class` until `class_id` is established.

```python
_CLASSLESS_ADMIN_ENDPOINTS = frozenset({
    'admin.create_class',
    'admin.onboarding',
    'admin.login',
    'admin.logout',
    'admin.username_migration',
    'admin.account_delete',
    'admin.passkey_login_start',
    'admin.passkey_login_finish',
})
```

**Tests:**
- Teacher with valid class → `g.canonical_context` is `CanonicalContext(actor_role='teacher')`
- Teacher with no classes → any class-requiring endpoint redirects to `create_class`
- Teacher with no classes → `create_class` endpoint returns 200
- Expired session → redirects to login
- Student session → admin route → redirects to login
- Sysadmin session → admin route → redirects to sysadmin login

---

## Phase 3: Admin login stops writing extinct keys

**Files:** `app/routes/admin.py` lines 3247–3253, 12714–12719

Before (password login):
```python
session["is_admin"] = True           # extinct — remove
session["admin_id"] = admin.id       # extinct — remove
session["user_id"] = user.id         # canonical — keep
session["current_session_nonce"] = ...  # canonical — keep
```

After:
```python
session["user_id"] = user.id
session["current_session_nonce"] = nonce
user.current_session_nonce = nonce
session["login_time"] = utc_now().isoformat()
session["last_activity"] = utc_now().isoformat()
```

Same change for passkey login (lines 12714–12719).

**Tests:** Integration test: admin login → `session` contains only `user_id`, `current_session_nonce`, `last_activity`, `login_time`. No `admin_id` or `is_admin` key present.

---

## Phase 4: Systematic admin handler rewrite (89 sites)

**Files:** `app/routes/admin.py`

Every handler that reads `session.get('admin_id')` is rewritten to use `g.canonical_context`. Four replacement patterns:

### Pattern A — Identity reconstruction (51 sites)

| Before | After | Rationale |
|--------|-------|-----------|
| `admin_id = session.get('admin_id')` | `ctx = g.canonical_context` | Resolved at boundary |
| `ClassEconomy.teacher_id == admin_id` | `ClassEconomy.class_id == ctx.class_id` | Scope by class, not teacher ownership |
| `filter_by(teacher_id=admin_id)` | `filter_by(class_id=ctx.class_id)` | Same |
| `admin = db.session.get(Admin, admin_id)` | Remove | Admin object extinct |
| `admin_id` passed to FEAT as `teacher_id` | `ctx.user_id` passed as `user_id` | FEATs accept canonical identity |

### Pattern B — Query scoping (10 sites)

Single-class context (most handlers):
```python
# Before
classes = ClassEconomy.query.filter(ClassEconomy.teacher_id == admin_id).all()

# After
class_economy = ClassEconomy.query.filter_by(class_id=ctx.class_id).first()
```

Multi-class listing (dashboard, class selector — runs with `BoundaryContext`):
```python
classes = ClassEconomy.query.filter(ClassEconomy.owner_user_id == ctx.user_id).all()
```

**Schema prerequisite:** `ClassEconomy` needs `owner_user_id` (FK to `users.id`) to replace extinct `teacher_id` (FK to `admins.id`). Migration must add column, backfill from Admin→User mapping, then drop `teacher_id` once callers migrate.

### Pattern C — Ownership/authorization (4 sites)

```python
# Before
if resource.teacher_id != admin_id:
    abort(403)

# After
if resource.class_id != ctx.class_id:
    abort(403)
```

Teacher authority over the class is already proven by the context resolver (seat with `role='teacher'` in that class).

### Pattern D — Display/logging (22 sites)

```python
# Before
log_action(admin_id=session.get('admin_id'), ...)

# After
log_action(user_id=ctx.user_id, class_id=ctx.class_id, seat_id=ctx.seat_id, ...)
```

### Execution order

Rewrite handlers in dependency order:
1. `create_class`, `onboarding` — produce class context, must work with `BoundaryContext`
2. `dashboard` — entry point after class creation/selection
3. Remaining handlers alphabetically

### Per-handler validation

- `grep` handler body for `admin_id`, `teacher_id`, `session.get('admin_id')` → zero hits
- Existing test (if present) still passes
- New test: handler returns 200 with canonical session containing no `admin_id`

---

## Phase 5: Delete auth bridge functions

**Files:** `app/auth.py`

Once Phases 4, 6, 7 eliminate all callers, delete:

| Function | Reason |
|----------|--------|
| `get_current_admin()` | Returns extinct `Admin` object from `session.get("admin_id")` |
| `resolve_admin_shadow_for_user()` | Bridges `User` → extinct `Admin` |
| `get_logged_in_student()` | Returns extinct `Student` from `session.get("student_id")` |
| `resolve_student_shadow_for_user()` | Bridges `User` → extinct `Student` |
| `get_current_system_admin()` | Returns extinct `SystemAdmin` from `session.get("sysadmin_id")` |
| `resolve_system_admin_shadow_for_user()` | Bridges `User` → extinct `SystemAdmin` |
| `sync_student_session_context()` | Backfills extinct session keys |
| `set_canonical_user_session()` | Login flow writes `user_id` directly |
| `get_admin_student_query()` | Scopes by extinct `Admin.id` via `ClassEconomy.teacher_id` |

**Validation:** `grep -rn` for each deleted function name across `app/` returns zero hits.

---

## Phase 6: Rewrite `@login_required` (student decorator)

**Files:** `app/auth.py`

Replace the current decorator (which checks `session['student_id']`, calls `get_logged_in_student()`, calls `sync_student_session_context()`) with:

1. Call `resolve_canonical_context()`
2. On `ContextNotEstablished` / `ContextMismatch` → redirect to student login
3. On `ContextInvariantViolation` (no class) → redirect to `student.select_class`
4. Verify `actor_role == 'student'`
5. Check timeout (strict 10-minute from login time — unchanged)
6. Store in `g.canonical_context`
7. No reference to `session['student_id']`, `get_logged_in_student()`, or `sync_student_session_context()`

**View-as-student:** Teacher assuming student perspective currently checks `session['view_as_student']` and `session['student_id']` — both extinct. Requires a dedicated design decision: teacher temporarily holds a student-role context within their active class. Tracked as a separate design item, not blocked by this phase.

**Tests:**
- Valid student session → `g.canonical_context` with `actor_role='student'`
- Expired session → redirect to login
- Unclaimed seat → redirect to login
- No class selected → redirect to class selector

---

## Phase 7: Rewrite `@system_admin_required`

**Files:** `app/auth.py`, `app/routes/system_admin.py`, `app/routes/main.py`, `app/routes/docs.py`, `app/utils/helpers.py`

Sysadmins are forbidden from class context. `resolve_canonical_context(require_class=False)` returns `BoundaryContext(user_id, actor_role='sysadmin')`.

Rewrite decorator:
1. Call `resolve_canonical_context(require_class=False)`
2. Verify `actor_role == 'sysadmin'`
3. Timeout check (60-minute sliding — unchanged)
4. Store in `g.canonical_context`

4 handler sites in `system_admin.py` → replace `session.get('sysadmin_id')` with `g.canonical_context.user_id`.

5 scattered sites (`main.py:37`, `docs.py:370,626`, `helpers.py:87`, `operational_event_service.py:33`) → replace `session.get('sysadmin_id')` checks with:
```python
ctx = getattr(g, 'canonical_context', None)
is_sysadmin = ctx and ctx.actor_role == 'sysadmin'
```

---

## Phase 8: Eliminate extinct session keys from all login flows

**Files:** `app/routes/admin.py`, `app/routes/student.py`, `app/routes/system_admin.py`

After all decorators and handlers are rewritten, login flows stop writing extinct keys:

| Login flow | File | Keys removed |
|---|---|---|
| Admin password login | `admin.py:3247–3253` | `session["is_admin"]`, `session["admin_id"]` |
| Admin passkey login | `admin.py:12714–12719` | `session['admin_id']`, `session['is_admin']` |
| Student login | `student.py:3693` | `session['student_id']` |
| Sysadmin password login | `system_admin.py:261` | `session["sysadmin_id"]`, `session["is_system_admin"]` |
| Sysadmin passkey login | `system_admin.py:472` | `session["sysadmin_id"]`, `session["is_system_admin"]` |

Each login retains only: `user_id`, `current_session_nonce`, `login_time`, `last_activity`.

---

## Phase 9: Operational telemetry fix

**Files:** `app/services/operational_event_service.py`

```python
# Before (line 33)
"actor_id": actor_id if actor_id is not None else (session.get("admin_id") if has_request_context() else None),

# After
"actor_id": actor_id if actor_id is not None else (
    getattr(getattr(g, 'canonical_context', None), 'user_id', None)
    if has_request_context() else None
),
```

---

## Execution Order and Dependencies

```
Phase 1  ← no dependencies (BoundaryContext + require_class)
  ├→ Phase 2  (rewrite @admin_required)
  ├→ Phase 6  (rewrite @login_required)
  ├→ Phase 7  (rewrite @system_admin_required)
  └→ Phase 9  (operational telemetry — independent)
       ↓
Phase 3  ← depends on Phase 2 (admin login keys)
Phase 8  ← depends on Phases 2, 6, 7 (all login flows)
       ↓
Phase 4  ← depends on Phases 2, 3 (89 admin handlers — long pole)
       ↓
Phase 5  ← depends on Phases 4, 6, 7 (delete bridges — runs last)
```

Phases 1, 9 run in parallel.
Phases 2, 6, 7 run in parallel after Phase 1.
Phase 4 is the long pole (89 sites in 13K lines).
Phase 5 is cleanup — runs only after all callers are eliminated.

---

## Schema Prerequisite

Phase 4 Pattern B requires `ClassEconomy.owner_user_id` (FK to `users.id`) to replace extinct `ClassEconomy.teacher_id` (FK to `admins.id`). This migration must land before Phase 4 Pattern B rewrites.

---

## Validation Script (CI gate after all phases)

```bash
# Zero extinct identity reads in runtime code
grep -rn "session\.get.*admin_id\|session\[.*admin_id\|session\.get.*student_id\|session\[.*student_id\|session\.get.*sysadmin_id\|session\[.*sysadmin_id" \
  app/ --include='*.py' | grep -v 'app/models.py' | grep -v '^\s*#' | grep -v 'db\.session' \
  && echo "FAIL: extinct identity references found" && exit 1 \
  || echo "PASS: zero extinct identity references"

# Zero bridge function references
grep -rn "get_current_admin\|resolve_admin_shadow\|get_logged_in_student\|resolve_student_shadow\|get_current_system_admin\|resolve_system_admin_shadow" \
  app/ --include='*.py' | grep -v 'app/models.py' | grep -v '^\s*#' \
  && echo "FAIL: bridge function references found" && exit 1 \
  || echo "PASS: zero bridge function references"

# Zero is_admin / is_system_admin session flags
grep -rn "session.*is_admin\|session.*is_system_admin" \
  app/ --include='*.py' | grep -v 'app/models.py' | grep -v '^\s*#' \
  && echo "FAIL: extinct session flags found" && exit 1 \
  || echo "PASS: zero extinct session flags"
```

---

## Testing Requirements

### Unit tests per phase

| Phase | Tests |
|-------|-------|
| 1 | `BoundaryContext` attribute guards; `require_class=False` return types for teacher/sysadmin/student |
| 2 | Decorator redirect matrix (6 cases: valid class, no classes, expired, student→admin, sysadmin→admin, classless→create_class) |
| 3 | Login writes only canonical keys; no extinct keys in session post-login |
| 4 | Per-handler: zero extinct refs in body + returns 200 with canonical session |
| 5 | Grep for deleted function names = zero hits |
| 6 | Decorator redirect matrix (4 cases: valid, expired, unclaimed, no class) |
| 7 | Decorator returns `BoundaryContext(actor_role='sysadmin')` |
| 8 | All login flows write only canonical keys |

### Integration tests

1. **Teacher full cycle:** login → no classes → create class → dashboard → action (BoundaryContext → CanonicalContext transition)
2. **Teacher class switch:** two classes → switch → verify `g.canonical_context.class_id` changes
3. **Student full cycle:** login → dashboard → action with canonical context
4. **Session expiry:** login → wait → next request → redirected to login
5. **Cross-role rejection:** student→admin route, admin→sysadmin route, sysadmin→admin route

### Regression gate

Existing test suite must pass after each phase. Fail count must not increase from current baseline (619 passed, 123 failed).

---

**Last Updated:** 2026-06-27
