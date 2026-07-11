# Identity Marker Inventory

**Date:** 2026-06-01  
**Branch:** `codex/v2.0`  
**Purpose:** Enumerate every meaningful actor-identifying marker in the current tree so we can distinguish canonical v2 anchors from historical residue, temporary bridge code, and ambiguous references.

This inventory audits current implementation residue against a clean v2 build. It is
not a historical-data migration plan. Invalid marker families should be removed rather
than preserved as compatibility contracts. In the live `app/` request paths, extinct
session identity and startup-blocking bridge wiring are now gone; the remaining work
is mostly model, test, and broader legacy residue.

## Summary

The codebase currently mixes four identity layers:

1. **Canonical scoped v2 markers**
   - `class_id`
   - `seat_id`
   - `Seat.public_id`
   - `User.id`

2. **Legacy route compatibility principals retained after authentication**
   - `Admin.id`
   - `Student.id`
   - `SystemAdmin.id`

3. **Transitional bridge markers**
   - `join_code`
   - `Seat.student_id`
   - `Seat.join_code`
   - `Seat.block`
   - `ClassMembership.admin_id` / `ClassMembership.student_id`
   - `StudentTeacher.teacher_id` / `StudentTeacher.student_id`
   - `TeacherBlock.teacher_id` / `TeacherBlock.student_id`

4. **Opaque or alternate public references**
   - `Admin.teacher_public_id`
   - `Admin.public_id`
   - `Admin.hall_pass_verify_token`
   - `Student.opaque_reference`
   - `Student.internal_reference`

The most important conclusion is that **seat-scoped runtime authority is now the live request-time dialect**, but the codebase still carries multiple role-specific ID families, plus some ambiguous markers that are not cleanly canonical or purely presentation-only.

## High-Frequency Marker Families

Quick grep counts across `app/` show the dominant identifiers still in live code:

- `block` is still the most common marker in routes, especially `admin.py`.
- `join_code` remains heavily used as a runtime alias and transitional scope key.
- `class_id` is widespread and is the cleanest class boundary marker.
- `admin_id`, `teacher_id`, and `student_id` are retained in auth, routes, and bridge tables as compatibility residue.
- `seat_id` is present across canonical domains, but still less pervasive than legacy human IDs.

This means the repository is **not yet speaking one identity dialect**. Runtime request paths are much closer to canonical, but tests, schema names, and compatibility helpers still speak at least three dialects: teacher/student/sysadmin principal IDs, seat/class IDs, and join-code/block-era roster markers.

## Inventory By Marker

### Canonical v2 actor markers

These are the markers that most closely match the intended v2 authority model.

| Marker | Meaning | Current role |
|---|---|---|
| `Seat.id` / `seat_id` | Canonical class-local actor anchor | Primary scoped activity identity |
| `ClassEconomy.class_id` / `class_id` | Canonical class boundary | Primary class scope identity |
| `Seat.public_id` | UUID-encoded deidentified public actor identity | Canonical public marker for teacher and student seats |
| `User.id` / `user_id` | Global human identity | Canonical TOTP/PIN authentication principal and session anchor |
| `IdentityProfile.id` / `identity_id` | Display-identity record | Human-facing display binding, not activity scope |
| `Seat.claim_first_name_hash` / `claim_last_name_hash` | Seat claim verification artifacts | Prove entitlement to one unclaimed seat inside one class |

Notes:

- `Seat.public_id` is the single canonical deidentified public actor identifier. It is
  a UUID encoded as a 36-character string.
- `User.id` is authoritative for teacher TOTP, student PIN, system-admin TOTP,
  and passkey credential verification. Live runtime compatibility is now mostly
  removed; remaining legacy-principal removal is concentrated in tests and data
  residue.
- `identity_id` is identity-display linkage, not an activity anchor.
- `IdentityProfile` is one-to-one with `Seat`; it must not own authentication,
  claim verification, or authority state.
- Claim name lookup hashes belong to `Seat`, not `User`, because they verify
  entitlement to a class-local participant position and should disappear with it.

## Public or externally exposed identity markers

These are public-facing or opaque identifiers that can represent an actor without exposing raw primary keys.

| Marker | Owner | Meaning | Status |
|---|---|---|---|
| `Seat.public_id` | `Seat` | UUID-encoded deidentified public identity for both teacher and student seats | Canonical |
| `Admin.teacher_public_id` | `Admin` | Legacy teacher public ID | Invalid v2 residue; remove |
| `Admin.public_id` | `Admin` | Second legacy teacher public ID family | Invalid v2 residue; remove |
| `Admin.hall_pass_verify_token` | `Admin` | Capability token for hall-pass verification URL | Valid capability token, not general actor ID |
| `Student.opaque_reference` | `Student` | Legacy student public reference | Invalid v2 residue; remove |
| `Student.internal_reference` | `Student` | Legacy internal student reference | Invalid internal-locator residue; remove |
| `actor_public_id` | TLCP / observability | Runtime and schema name for trace, error-event, and ticket-pack actor references | Canonical `Seat.public_id` value |

Key weirdness:

- Teachers previously had **two separate public IDs**: `teacher_public_id` and `public_id`. Neither belongs in clean v2; teacher seats use `Seat.public_id`.
- Students currently have **two separate references**: `opaque_reference` and `internal_reference`. Neither belongs in clean v2; student seats use `Seat.public_id` publicly and `seat_id` internally.
- TLCP runtime and schema now use `actor_public_id`, backed by the class-scoped
  `Seat.public_id` value.

## Legacy route compatibility human principal IDs

These are still load-bearing in route logic after canonical authentication.

| Marker | Owner | Meaning | Status |
|---|---|---|---|
| `Admin.id` / `admin_id` | Teacher compatibility shadow | Historical route/session compatibility ID | Not a TOTP authentication decision |
| `Student.id` / `student_id` | Student compatibility shadow | Route/session compatibility ID | Not a PIN authentication decision |
| `SystemAdmin.id` / `sysadmin_id` | Sysadmin compatibility shadow | Route/session compatibility ID | Not a TOTP authentication decision |
| `teacher_id` | Many models | Usually teacher owner FK | Legacy naming still widespread |

Important distinction:

- `admin_id` remains historical compatibility language in tests and helper surfaces, but not in live `app/` request handlers.
- `teacher_id` is the **model/ownership language** for teachers.
- That split is semantically understandable, but still increases identity-surface complexity.

## Transitional bridge markers

These markers connect current implementation residue to v2 seat/class identities.
They are temporary implementation bridges, not compatibility promises.

| Marker | Meaning | Why it exists |
|---|---|---|
| `Seat.student_id` | Back-reference from seat to legacy student row | Bridges old student-owned tables into seat scope |
| `Seat.join_code` | Transitional class alias on seat | Needed while class rewiring is incomplete |
| `Seat.block` | Transitional block mirror on seat | Legacy compatibility and UI glue |
| `Student.class_id` / `Student.join_code` / `Student.block` | Legacy student-local scope hints | Transitional compatibility only |
| `StudentTeacher.student_id` + `teacher_id` | Legacy teacher-student ownership link | Still source of truth for some teacher visibility |
| `ClassMembership.admin_id` + `student_id` | Membership bridge by human principal | Transitional class membership layer |
| `TeacherBlock.teacher_id` + `student_id` + `join_code` + `block` | Legacy roster seat record | Claim flow and roster migration glue |
| `created_by_admin_id` / `created_by_teacher_id` | Provenance actor fields | Historical ownership/provenance |
| `processed_by_teacher_id` | Audit/action attribution | Historical teacher action marker |

These are not harmless metadata. Several of them still participate in resolution logic, ownership logic, or write-time backfills.

## Session identity markers

### Student session keys

| Session key | Meaning | Status |
|---|---|---|
| `student_id` | Logged-in legacy student principal | Historical compatibility |
| `user_id` | Logged-in canonical `User.id` | Canonical auth session anchor |
| `current_seat_id` | Current seat context | Canonical session scope |
| `seat_id` | Alternate seat context key | Legacy alias still accepted |
| `current_class_id` | Current class context | Canonical session scope |
| `class_id` | Alternate class context key | Legacy alias still accepted |
| `current_join_code` | Current public class alias | Transitional alias |
| `join_code` | Alternate join-code key | Legacy alias still accepted |
| `onboarding_student_ref` / `onboarding_seat_ref` / `onboarding_user_ref` | Recovery/claim flow handoff keys | Transitional flow-specific |
| `recovery_student_id` | Recovery flow marker | Transitional |

### Teacher session keys

| Session key | Meaning | Status |
|---|---|---|
| `admin_id` | Logged-in teacher principal | Historical compatibility |
| `user_id` | Logged-in canonical `User.id` | Canonical auth session anchor |
| `current_class_id` | Current teacher class context | Canonical class scope |
| `current_join_code` | Current class alias | Transitional/public alias |
| `is_admin` | Teacher auth role flag | Historical compatibility |
| `view_as_student` | Teacher impersonation mode flag | Current special-case behavior |

### Sysadmin session keys

| Session key | Meaning | Status |
|---|---|---|
| `sysadmin_id` | Logged-in sysadmin principal | Historical compatibility |
| `user_id` | Logged-in canonical `User.id` | Canonical auth session anchor |
| `is_system_admin` | Sysadmin role flag | Historical compatibility |

Session alias acceptance remains documented:

- `get_current_seat()` accepts both `seat_id` and `current_seat_id`.
- `get_current_class_id()` accepts both `class_id` and `current_class_id`.
- `get_current_user()` accepts canonical `user_id` and may resolve the same user
  from an already validated owned seat.

That means the session model still has **alias acceptance**, not one canonical key per concept.

## Observability and correlation actor markers

These markers represent actors for logging, tracing, and support workflows.

| Marker | Meaning | Status |
|---|---|---|
| `actor_type` | Role label such as `student`, `teacher`, `sysadmin` | Current logging metadata |
| `actor_id` | Raw actor integer ID chosen by context resolver | Current role-dependent support marker |
| `actor_public_id` | Runtime support/log actor identity | Current; value is `Seat.public_id` |
| `request_id` | Request correlation token | Not actor identity, but part of trace identity |

Important caveat:

- `app/services/tlcp.py` resolves runtime actor identity to `Seat.public_id` for
  student and teacher class-scoped contexts.
- `actor_id` still carries a role-dependent legacy integer for diagnostics; it is not
  the support-ticket actor identity.

## Ambiguous or overloaded markers

These are the markers most likely to cause confusion or authority bugs.

### `block`

- Appears everywhere as roster label, UI grouping label, period identifier, and in some scope resolution paths.
- Exists on `Seat`, `Student`, `TeacherBlock`, `StudentBlock`, and multiple settings surfaces.
- This is still the highest-frequency non-canonical identity-adjacent marker in the app.
- Formalization target: class-period metadata should live on `classes.section`.
  `block` is legacy naming and should be retired in favor of `section`.

### `join_code`

- Public class alias in the target architecture.
- Still used widely as runtime scope, bridge lookup key, settings lookup key, and route context key.
- Legitimate alias, but still too load-bearing in several legacy paths.

### `teacher_id` versus `admin_id`

- `admin_id` was the authenticated teacher principal in session/auth code.
- `teacher_id` means teacher ownership FK in tables and business logic.
- The split is coherent but easy to misread during audits or refactors.

### `student_id`

- Still active in tests, bridge tables, recovery flows, analytics drilldowns, observability, and many domain tables.
- The codebase often treats it as “person identity,” but the live runtime increasingly translates it into seat scope only at the boundary.

### `actor_id`

- In `Scope`, this means “the acting principal ID,” but the numeric space depends on role.
- For students, `actor_id` is usually `Student.id`, not `Seat.id`.
- This is a useful abstraction for capability code, but not a canonical actor anchor.

### `system_admin_id` versus `sysadmin_id`

- Runtime auth uses `sysadmin_id`.
- Some models and routes still expose `system_admin_id`.
- This is a small but real naming fork.

## Explicit weird markers worth follow-up

### 1. Auto-created legacy seats

Several model hooks still synthesize `Seat` rows from legacy `student_id` writes, using synthetic join codes like `LEGACY_<student_id>`.

This appears in dual-write bridge paths for:

- ledger transactions
- rent payments
- insurance-linked records

This is one of the clearest signs that legacy student identity can still create new scoped actor artifacts indirectly.

### 2. Two teacher public-ID families

`Admin` currently has both:

- `teacher_public_id`
- `public_id`

Both are invalid v2 residue. Teacher seats use UUID-encoded `Seat.public_id`.

Runtime reduction completed on 2026-06-02:

- new class-anchor flows provision a teacher `Seat`
- `/api/hall-pass/verification/active` resolves a teacher-seat `Seat.public_id`
  under one explicit `class_id`
- `/api/hall-pass/available-types` rejects `teacher_public_id`
- `/student/switch-teacher/<teacher_public_id>` returns `404`; student class switching
  uses the existing class-context route

Remaining `Admin.teacher_public_id` and `Admin.public_id` usages are account/display
residue, not class-scoped lookup authority.

Runtime helper cleanup completed on 2026-07-05:

- `app/services/admin_identity_bridge_service.py` renamed to `app/services/admin_identity_service.py`
- `app/services/recovery_bridge_service.py` renamed to `app/services/recovery_service.py`
- The remaining active callers now use the canonical service names directly; bridge filenames are no longer part of the runtime code path in the cleaned admin/recovery slice.
- route imports now reference the canonical service names, with no `bridge_service` imports left in `app/`
- startup verification passed after the rename: `venv/bin/flask --app wsgi routes >/dev/null`

### 3. Two student opaque/reference families

`Student` currently has both:

- `opaque_reference`
- `internal_reference`

These are invalid v2 residue. The canonical references are:

- `opaque_reference` -> `Seat.public_id`
- `internal_reference` -> `seat_id`

### 4. TLCP actor resolution runtime cutover

`resolve_actor_context()` now emits `actor_public_id` from the active class-scoped
`Seat.public_id` for student and teacher contexts.

Request traces, error events, student recent-error prompts, and ticket correlation
packs now use that seat UUID through the `actor_public_id` schema/API name.

Because ticket packs are already bound to `class_id`, the actor identity recorded with
the ticket is now class-scoped rather than person-global.

### 5. Hall-pass verify token ownership is still teacher-table-scoped

`hall_pass_verify_token` is currently stored on `Admin` and the public verify route resolves the teacher with:

- `Admin.query.filter_by(hall_pass_verify_token=teacher_public_token).first()`

This is not a general actor identity marker; it is a capability token. The open question is not whether it should become `Seat.public_id` directly, but whether the capability should be owned by:

- the teacher seat
- the class
- a dedicated hall-pass capability object

Right now it is still anchored to the legacy teacher principal.

### 6. Canonical `user_id` session support

`get_current_user()` now accepts only canonical `user_id`, with an owned-seat
resolution path for already validated class context. Deprecated user-principal
session aliases are no longer read or written.

Teacher TOTP, student PIN, and system-admin TOTP login now authenticate `User`
first. Legacy principal IDs are populated only after a unique route shadow is
resolved. Passkey registration and authentication now use `user_<User.id>` as
the Passwordless external identity and reject legacy `admin_<id>` /
`sysadmin_<id>` external principals.

## Current classification

### Keep as canonical

- `class_id`
- `seat_id`
- `Seat.public_id`
- `User.id`
- `IdentityProfile.id`

### Runtime residue still load-bearing until removed

- `admin_id`
- `student_id`
- `sysadmin_id`

### Keep as public alias or capability token

- `join_code`
- `hall_pass_verify_token`

### Temporary bridges to remove from the clean v2 implementation

- `Seat.student_id`
- `Seat.join_code`
- `Seat.block`
- `StudentTeacher.*`
- `TeacherBlock.*` — runtime cleared; remaining surface is test and data-shape residue
- `ClassMembership.admin_id`
- `ClassMembership.student_id`
- `seat_id` session alias
- `class_id` session alias
- `join_code` session alias

### Highest-risk ambiguous markers

- `block`
- `teacher_id`
- `student_id`
- `actor_id`
- `Admin.teacher_public_id` plus `Admin.public_id`
- `Student.opaque_reference` plus `Student.internal_reference`
- `hall_pass_verify_token` ownership on `Admin`

## Suggested cleanup order

1. **Remove role-specific teacher public identity**
   - Class-scoped lookup removal is complete.
   - Remove remaining account/display `Admin.public_id` and `teacher_public_id`
     residue; teacher seats use UUID-encoded `Seat.public_id`.

2. **Remove student alternate reference markers**
   - Remove `opaque_reference` and `internal_reference`; student seats use `Seat.public_id` publicly and `seat_id` internally.

3. **Reduce session key aliases**
   - Standardize on one key each for current user, seat, class, and join-code context. Runtime request handlers are already on the canonical path; this is now alias cleanup, not emergency cutover work.

4. **Remove legacy seat synthesis from `student_id` writes**
   - Stop auto-creating seats with synthetic `LEGACY_<student_id>` aliases as the affected write paths are rewritten.

5. **Continue support schema cleanup outside actor identity**
   - `issues.actor_public_id` is now the canonical support actor reference.
   - remaining support cleanup should focus on non-actor opaque route helpers and
     legacy `Student.opaque_reference` residue.
   - analytics drilldown
   - access `Scope.actor_id`

6. **Decide hall-pass capability ownership**
   - Move `hall_pass_verify_token` off `Admin` if teacher principal is no longer the right owner.

7. **Continue eliminating `block` as an authority-adjacent marker**
   - Keep it presentation-only.

## Source surfaces inspected

- `app/models.py`
- `app/auth.py`
- `app/access/scope.py`
- `app/access/scope_factory.py`
- `app/services/tlcp.py`
- `app/routes/admin.py`
- `app/routes/student.py`
- `app/routes/api.py`
- `app/routes/system_admin.py`
- `app/routes/recovery.py`
- `app/routes/analytics.py`
