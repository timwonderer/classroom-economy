# Phases 5–8 Handoff — Extinct Runtime Identity Elimination

**Date:** 2026-06-27
**Branch:** `codex/v2.0`
**Plan doc:** `docs/TRACKING/V2_CLASS_A_REMEDIATION_PLAN.md`
**Audit reference:** `docs/TRACKING/V2_CONTEXT_RESOLUTION_AUDIT.md`

---

## Plan Context

The remediation plan has 9 phases eliminating extinct runtime identity (`admin_id`, `teacher_id`, `student_id`, `sysadmin_id`) from all authority/scoping paths. Each request resolves identity once at the decorator boundary via `resolve_canonical_context()`, stored in `g.canonical_context`.

**Phases 1–4** are complete (context resolver, `@admin_required` rewrite, admin login key cleanup, 89 admin handler rewrites).

**Phase 9** (operational telemetry) is complete.

**Phases 5–8** are the current scope. This handoff covers their status.

---

## Phase 5: Delete auth bridge functions — COMPLETE

Bridge helpers were removed from runtime code and remaining references were reduced to historical documentation only.

---

## Phase 6: Rewrite `@login_required` (student decorator) — NOT STARTED

**Goal:** Replace `@login_required` in `app/auth.py` (lines ~120-190) to use `resolve_canonical_context()` directly.

**Current decorator flow (extinct):**
1. Checks `session['student_id']` exists
2. Resolves the student from canonical context via the route-local helper
3. Uses the onboarding flow to hydrate user/seat state
4. Fails closed if the canonical seat is missing

**Target flow:**
1. Call `resolve_canonical_context()`
2. Verify `actor_role == 'student'`
3. Check 10-minute timeout
4. Store in `g.canonical_context`
5. No `session['student_id']`, no bridge functions

**Callers that need migration (~30 in student.py):**
Lines: 222, 449, 793, 953, 1282, 1284, 1369, 1599, 1601, 1712, 1834, 1855, 2158, 2197, 2952, 3162, 3355, 3736, 3770, 3805, 3849, 3915, 3927, 3959, 4012, 4075, 4141, 4210

These handlers now resolve the current student from canonical context where needed.

**Other callers:**
- `app/auth.py:164` — inside `@student_required` decorator itself
- `app/access/scope_factory.py:198` — historical reference
- `app/routes/student.py:42,3660` — historical reference

**Design decision needed:** View-as-student mode. Currently uses `session['view_as_student']` + `session['student_id']` (both extinct). The `is_viewing_as_student()` function in auth.py was already updated to check `user_role` instead of `session["is_admin"]`, but the underlying mechanism still assumes student identity is in the session.

---

## Phase 7: Rewrite `@system_admin_required` — ✅ COMPLETE

All work done:

| Site | Change |
|------|--------|
| `app/auth.py` `@system_admin_required` | Rewrote to use `resolve_canonical_context(require_class=False)` + `BoundaryContext` check |
| `app/services/context_resolver.py` | Removed `session.get("is_system_admin")` dependency; checks `user.user_role` |
| `app/routes/system_admin.py` | All handlers use `g.canonical_context`; login flows write only canonical keys; stale imports removed |
| `app/routes/main.py` `home()` | Uses `user.user_role` from `get_current_user()` |
| `app/routes/main.py` hall pass verify | Fixed Admin→User resolution via `username_lookup_hash` |
| `app/routes/docs.py` (2 sites) | `g.canonical_context.actor_role == 'sysadmin'` |
| `app/utils/helpers.py` | `g.canonical_context.actor_role` check |
| `app/services/operational_event_service.py` | `g.canonical_context.user_id` |
| `app/routes/analytics.py` | `g.canonical_context.user_id` |
| `app/routes/recovery.py` | `g.canonical_context.user_id` |
| `app/routes/api.py` | Inline canonical context check |
| `app/__init__.py` maintenance bypass | `get_current_user()` + role check |
| `app/__init__.py` `inject_current_sysadmin` | Now injects `User` object |

---

## Phase 8: Eliminate extinct session keys from login flows — PARTIALLY COMPLETE

| Login flow | File | Status | Notes |
|---|---|---|---|
| Admin password login | `admin.py` | ✅ | `session["is_admin"]` and `session["admin_id"]` writes removed |
| Admin passkey login | `admin.py` | ⬜ CHECK | Verify lines ~12714 — may already be done in Phase 4 |
| Sysadmin password login | `system_admin.py` | ✅ | Writes only `user_id`, `current_session_nonce`, `sysadmin_auth_username` |
| Sysadmin passkey login | `system_admin.py` | ✅ | Same |
| Student login | `student.py` | 🔴 BLOCKED by Phase 6 | `session['student_id']` still written |
| Admin logout | `admin.py:4080` | ✅ | Removed `is_admin`/`admin_id` pops |
| Admin account_delete | `admin.py:11296` | ✅ | Removed `is_admin`/`admin_id` pops |
| Sysadmin logout | `system_admin.py` | ✅ | Removed extinct key pops |

### Remaining `session.pop("student_id")` sites (8)

- `app/auth.py` lines 136, 150, 166, 179 — inside `@student_required` session cleanup
- `app/routes/student.py` lines 141, 767, 3686
- `app/routes/recovery.py` lines 163, 204

These will be cleaned up when Phase 6 rewrites the student decorator and login flow.

---

## Model FK Changes (Done in code, migration needed)

Three FK targets in `app/models.py` were changed from `system_admins.id` → `users.id`:

| Column | Model | Line |
|--------|-------|------|
| `reviewed_by_sysadmin_id` | `UserReport` | ~2520 |
| `sysadmin_id` | `Issue` | ~2632 |
| `system_admin_id` | `Announcement` | ~3323 |

**Migration not yet created.** The migration needs to:
1. For each row, look up `SystemAdmin.username_lookup_hash` → find matching `User.id`
2. Update FK value from `system_admins.id` to `users.id`
3. Drop old FK constraint, add new one pointing to `users.id`

Also: `Announcement` relationship backref was renamed from `announcements` to `sysadmin_announcements` to avoid conflict with the teacher-facing `user_id` relationship.

---

## Other Completed Changes (Cross-Phase)

| File | Change |
|------|--------|
| `app/routes/admin.py` `_scoped_students` | Replaced `session.get("is_system_admin")` with canonical context check |
| `app/routes/admin.py` | Fixed 4 stale `ClassEconomy.filter_by(teacher_id=...)` → `user_id=...` |
| `app/access/scope_factory.py` | Fixed `ClassEconomy.filter_by(teacher_id=...)` → `user_id=...` |
| `app/utils/student_deletion.py` | Fixed `ClassEconomy.filter_by(teacher_id=...)` → `user_id=...` |
| `app/auth.py` `is_viewing_as_student()` | Replaced `session.get("is_admin")` with `user_role` / canonical context check |

---

## Execution Priority for Next Agent

1. **Phase 6** (student decorator rewrite) — the biggest remaining chunk (~30 callers). Read the current `@login_required` decorator at `app/auth.py:120-190` and the plan's Phase 6 section.
2. **Phase 8 student login** — after Phase 6, remove `session['student_id']` writes from student login flow
3. **Phase 5 remaining deletions** — historical note; the helper surface has already been removed
4. **Database migration** — FK target changes for sysadmin columns

---

## Files to Read First

1. **`docs/TRACKING/V2_CLASS_A_REMEDIATION_PLAN.md`** — the authoritative plan (all 9 phases)
2. **`app/services/context_resolver.py`** — `CanonicalContext`, `BoundaryContext`, `resolve_canonical_context()`
3. **`app/auth.py:120-190`** — current `@login_required` (student) decorator
4. **`app/auth.py:220-300`** — current `@admin_required` decorator (already rewritten — reference for pattern)
5. **`app/auth.py:273-300`** — current `@system_admin_required` (already rewritten — reference for pattern)
6. **`app/models.py:85-200`** — `UserRole` enum and `User` model

## Key Invariants

- **`g.canonical_context`** is set by auth decorators — sole identity authority post-boundary
- **Routes MUST NOT write** `session["admin_id"]`, `session["student_id"]`, `session["sysadmin_id"]`, `session["is_system_admin"]`, or `session["is_admin"]`
- **FK targets for sysadmin columns** now point to `users.id` in code — migration pending
- **`class_id`** is the canonical class boundary; `join_code` is its public alias
- **All state mutations** go through `app/feats/` — never `db.session.add/commit` in routes
- **Base branch is `codex/v2.0`**, not `main`
- **`block`/`period`** is display metadata only, never a scoping key
- **`ClassMembership`** is deprecated; `ClassEconomy`/`classes` is the canonical teacher-to-class linkage
