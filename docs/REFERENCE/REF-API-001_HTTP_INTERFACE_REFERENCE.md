# REF-API-001: HTTP Interface Reference

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| REF-API-001      | 1.0     | 2026-09-05     | `ARC-OPS-005_Api_Reference` (v1, archived) | Informative |

## I. Purpose

Describe every JSON-returning HTTP endpoint the application exposes, identify which client calls it, and record the disposition of each one — live, operational, stale, broken, or prohibited. The v1 predecessor (`ARC-OPS-005_Api_Reference`) documented a route table that no longer matches the running application and is quarantined with the rest of the v1 archive.

## II. Scope

Covers the 63 endpoints that return `application/json`, out of 198 registered rules. It does not cover HTML page routes, static assets, or the `/docs` site.

This document is **descriptive, not normative**. It records what the application currently exposes. It does not grant authority to any endpoint; authority flows from `INV-CORE-*` → `INV-ARC-*` → `DOM-*` → `FEAT-*` as always. Where this document and a domain contract disagree, the domain contract wins and this document is the thing that is wrong.

## III. Authority Level

Informative. Subordinate to `INV-ARC-000`, `INV-ARC-006`, and `INV-ARC-007`.

## III-A. Dependencies

- `docs/INVARIANT/ARCHITECTURE/INV-ARC-000_EXECUTION_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-004_CROSS_TENANT_ISOLATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md`
- `docs/DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md`

---

## IV. Interface Model

**There is no public API.** Every endpoint below is a same-origin XHR endpoint serving the application's own front end. This has consequences that a reader arriving from the v1 document may not expect:

- **No versioning, no deprecation window, no stability contract.** The client ships in the same deploy as the server. An endpoint may change shape in any release, because the only caller changes with it.
- **Authentication is the session cookie**, not a bearer token or API key. There is no token-issuing endpoint and no machine-to-machine credential.
- **Mutating requests require a CSRF token.** Same-origin XHR carries `X-CSRFToken`; a caller outside the browser session has no way to obtain one.
- **The `/api` prefix is not a boundary.** JSON endpoints exist under `/admin`, `/student`, `/sysadmin`, and `/` as well. Sixteen of the 63 live outside `/api`. Treat the prefix as historical, not architectural.

Consequently, "the API" is not an integration surface anyone outside the application may build against. Requests for an integration surface are a product decision, not a documentation gap.

### IV-A. Response shape

The dominant convention is `{"status": "success"|"error", ...}` with the HTTP status carrying the real signal. It is not universal — some endpoints return a bare object or a bare array (`/api/tips/<user_type>`). Do not write a client that assumes the envelope without checking the endpoint.

---

## V. Authentication and Authorization

| Guard | Meaning |
|-------|---------|
| `@admin_required` | Teacher session. |
| `@login_required` | Student session. |
| `@system_admin_required` | Operator session. |
| *(none)* | Reachable without a session. Twelve endpoints; each is justified in §VII or flagged as a defect. |

Authorization beyond the session — that a teacher owns *this* class, that a student holds *this* entitlement — is enforced inside the view via `resolve_canonical_context()` and class scoping, never by the decorator. A decorator tells you the actor is *some* teacher; it never tells you they may touch the record named in the URL.

Rate limiting defaults to `500/day, 200/hour` globally (`app/extensions.py`). Endpoints that override it are noted below.

---

## VI. Endpoint Inventory

Auth column: **A** = `@admin_required`, **S** = `@login_required` (student), **O** = `@system_admin_required`, **—** = none.

### VI-A. Attendance and tap

| Method | Path | Auth | Client |
|--------|------|------|--------|
| POST | `/api/tap` | — † | `attendance.js` |
| GET | `/api/student-status` | S | `attendance.js` |
| GET | `/api/attendance/history` | A | `admin_attendance_log.html` |
| POST | `/admin/tap-in-students` | A | `admin_students.html` |
| POST | `/admin/tap-out-students` | A | `admin_students.html` |

† `/api/tap` carries no auth decorator but is **not** unauthenticated: it resolves `g.canonical_context` and returns 401 when absent, then requires a PIN check against `User.pin_hash` before doing anything. Rate limited to 100/min. The risk is not present-tense exposure but that the guarantee is imperative — there is no decorator whose removal a reviewer would notice. See §VIII-D.

### VI-B. Hall passes

The largest cluster, and the only one with a sanctioned cross-class exception.

| Method | Path | Auth | Client |
|--------|------|------|--------|
| POST | `/api/hall-pass/request` | S | `attendance.js`, `admin_hall_pass.html` |
| POST | `/api/hall-pass/request/<request_id>/cancel` | S | `attendance.js`, `admin_hall_pass.html` |
| POST | `/api/hall-pass/request/<request_id>/<action>` | A | `attendance.js`, `admin_hall_pass.html` |
| POST | `/api/hall-pass/<int:pass_id>/<action>` | A | `attendance.js`, `admin_hall_pass.html`, `hall_pass_setup.html` |
| POST | `/api/hall-pass/checkout` | S | `attendance.js` |
| POST | `/api/hall-pass/checkin` | S | `attendance.js` |
| GET | `/api/hall-pass/available-types` | S | `attendance.js` |
| GET | `/api/hall-pass/history` | A | `admin_hall_pass.html` |
| GET · POST | `/api/hall-pass/settings` | A | `admin_hall_pass.html` |
| GET · POST | `/api/hall-pass/setup` | A | `hall_pass_setup.html` |
| POST | `/api/hall-pass/verify-token/rotate` | A | `admin_hall_pass.html` |
| POST | `/admin/students/bulk-adjust-hall-pass-entitlements` | A | `admin_students.html` |
| GET | `/api/hall-pass/verification/active` | — | **none — see §VII-C** |

The public hall-pass verification capability that office staff actually use is **not** in this table: it is the server-rendered `POST /verify/hallpass/<teacher_public_token>` in `main.py`, rate limited to 60/min. `/api/hall-pass/verification/active` is a JSON reimplementation of the same capability with no caller.

### VI-C. Store and entitlements

| Method | Path | Auth | Client |
|--------|------|------|--------|
| POST | `/api/purchase-item` | S | `student_shop.html` |
| POST | `/api/use-item` | S | `student_shop.html` |
| POST | `/api/approve-redemption` | A | `admin_dashboard.html`, `admin_store.html` |
| POST | `/api/reject-redemption` | A | `admin_dashboard.html`, `admin_store.html` |

### VI-D. Economy balance checker

Driven entirely by `static/js/economy-balance.js`, which builds request URLs from `apiBaseUrl = '/admin/api/economy'`. The script is loaded by `admin_store.html`, `admin_rent_settings.html`, `admin_edit_item.html`, and `admin_payroll.html`.

| Method | Path | Auth | Client |
|--------|------|------|--------|
| POST | `/admin/api/economy/calculate-cwi` | A | `economy-balance.js` |
| POST | `/admin/api/economy/analyze` | A | `economy-balance.js` |
| POST | `/admin/api/economy/validate/<feature>` | A | `economy-balance.js` |

### VI-E. Roster and class administration

| Method | Path | Auth | Client |
|--------|------|------|--------|
| POST | `/admin/current-class` | A | `layout_admin.html` |
| POST | `/admin/feature-settings/update` | A | `admin_feature_settings.html` |
| POST | `/admin/upload-students` | A | `admin_students.html` |
| POST | `/admin/students/bulk-delete` | A | `admin_students.html` |
| POST | `/admin/pending-students/delete` | A | `admin_students.html` |
| POST | `/admin/void-transaction/<int:transaction_id>` | A | `admin_banking.html`, `student_detail.html` |
| POST | `/admin/announcements/toggle/<int:announcement_id>` | A | `admin_announcements.html` |
| POST · DELETE | `/admin/join-code/delete` · `/admin/join-code` | A | `admin_account_delete.html` |

### VI-F. Onboarding

| Method | Path | Auth | Client |
|--------|------|------|--------|
| GET | `/admin/onboarding/status` | A | `components/getting_started_widget.html` |
| POST | `/admin/onboarding/skip` | A | `components/getting_started_widget.html` |
| POST | `/admin/onboarding/skip-task` | A | `components/getting_started_widget.html` |

### VI-G. Passkeys (WebAuthn)

Teacher and operator ceremonies are structurally identical and separately registered.

| Method | Path | Auth | Client |
|--------|------|------|--------|
| POST | `/admin/passkey/auth/start` · `/finish` | — ‡ | `admin_login.html` |
| POST | `/admin/passkey/register/start` · `/finish` | A | `admin_passkey_settings.html` |
| DELETE | `/admin/passkey/<int:passkey_id>/delete` | A | `admin_passkey_settings.html` |
| POST | `/sysadmin/passkey/auth/start` · `/finish` | — ‡ | `system_admin_login.html` |
| POST | `/sysadmin/passkey/register/start` · `/finish` | O | `system_admin_passkey_settings.html` |
| POST | `/sysadmin/passkey/<int:credential_id>/delete` | O | `system_admin_passkey_settings.html` |
| GET | `/admin/passkey/list` | A | **none — see §VII-C** |
| GET | `/sysadmin/passkey/list` | O | **none — see §VII-C** |

‡ The `auth/start` and `auth/finish` ceremonies are unauthenticated by definition — they *are* the login. Both are rate limited to 20/min; registration and deletion to 10/min.

### VI-H. Hybrid page routes

These are HTML page routes that return JSON only on their XHR branch (`student.py` contains 21 such content-negotiation checks). They appear in a `jsonify` scan but are not API endpoints, and should not be treated as a stable JSON surface.

| Path | Notes |
|------|-------|
| `/student/login` | Rate limited 60/min; JSON on the XHR failure branch. |
| `/student/transfer` | Page; JSON validation errors. |
| `/student/switch-class/<class_id>` | POST returns JSON. |

### VI-I. Platform and operations

| Method | Path | Auth | Disposition |
|--------|------|------|-------------|
| GET | `/health` | — | Live. Liveness probe, returns `ok`. No in-app caller by design. |
| GET | `/health/deep` | — | Live. Dependency probe. No in-app caller by design. |

`/debug/filters` and `/debug/admin-db-test` were registered here at the time of the
audit and have since been removed — see §VIII-A.

---

## VII. Disposition Summary

Counts are as-of this revision, after the §VIII-A and §VIII-B removals landed.

| Disposition | Count | Meaning |
|-------------|-------|---------|
| Live | 52 | Reachable from a shipped client. |
| Operational | 2 | No in-app caller by design (`/health`, `/health/deep`). |
| Stale | 6 | Registered, functional, zero callers. §VII-C |
| Broken | 0 | Was 1 before §VIII-B was resolved. |
| Prohibited | 0 | Was 2 before §VIII-A was resolved. |

### VII-C. Stale endpoints

Each is registered and reachable, has an intact auth guard, and has no caller in `templates/`, `static/`, or any other application code.

| Path | Assessment |
|------|-----------|
| `/admin/payroll/transactions/<int:transaction_id>/void` | A payroll-specific void, parallel to the live `/admin/void-transaction/<id>` used by `admin_banking.html`. Two implementations of one capability; this is the unused one. |
| `/admin/payroll/transactions/void-bulk` | Bulk form of the same dead path. |
| `/admin/pending-students/bulk-delete` | Referenced only by a test. The live UI calls the singular `/admin/pending-students/delete`. |
| `/admin/passkey/list` | Both settings pages render the credential list server-side; nothing fetches it. |
| `/sysadmin/passkey/list` | As above. |
| `/api/hall-pass/verification/active` | Superseded by the server-rendered `/verify/hallpass/<token>`. Carries the highest residual risk of the six — see §VIII-C. |

---

## VIII. Findings

### VIII-A. `/debug/*` endpoints were unauthenticated and registered in every environment (prohibited — resolved)

Both routes are declared on `main_bp` with no auth decorator, no rate limit beyond the global default, and no environment gate. Verified against a running instance with credentials omitted:

- `GET /debug/filters` → **200**, returns the complete Jinja filter list. A framework- and version-fingerprinting aid, including the application's custom filters.
- `GET /debug/admin-db-test` → executes a `User` query filtered to `UserRole.TEACHER` and returns the row count. Its own docstring calls it a "Temporary route."

Neither has a caller. `debug_admin_db_test` in particular is an unauthenticated endpoint whose entire function is to report on the users table.

**Resolution:** both were deleted from `app/routes/main.py`. `tests/test_route_registration_contract.py::test_debug_routes_are_not_registered` now asserts neither path can reappear in the URL map. If a Jinja-filter dump is wanted for local work, it belongs behind `@system_admin_required` or a `FLASK_DEBUG` guard, not on the public router.

Removing `debug_admin_db_test` exposed a second latent defect it had been sharing with `/health/deep`: both referenced `UserRole`, which `main.py` never imported. The deep health probe's teachers-table check therefore raised `NameError` rather than reporting status — which is also why `/debug/admin-db-test` answered 500 rather than leaking the count. The import was added.

### VIII-B. `/admin/payroll/rewards/add` was a dangling decorator that always 500s (resolved)

`app/routes/admin.py:7868` carries a route decorator whose function body was removed. The decorator now binds to the *next* function in the file:

```python
@admin_bp.route('/payroll/rewards/add', methods=['POST'])      # ← body deleted; binds below


@admin_bp.route('/payroll/transactions/<int:transaction_id>/void', methods=['POST'])
@admin_required
def void_payroll_transaction(transaction_id):
```

The rule supplies no `transaction_id`, but the view requires one, so every request raises `TypeError` before reaching any application logic. Proven by comparing `Rule.arguments` against the view signature across all 198 rules — this is the only structural mismatch in the application:

```
/admin/payroll/rewards/add   url_args=[]   view_requires=['transaction_id']   MISSING=['transaction_id']
```

Authorization is *not* bypassed — decorators apply bottom-up, so `@admin_required` still wraps the function. The defect is a guaranteed 500, plus a route table that advertises a capability ("add payroll reward") the application does not implement.

**Resolution:** the orphaned decorator line was deleted. The signature check is now `tests/test_route_registration_contract.py::test_every_rule_supplies_the_arguments_its_view_requires`, with a companion asserting no rule passes an argument its view cannot accept. Together they cover the whole route table, so a future body deletion fails at test time instead of at request time.

### VIII-C. `/api/hall-pass/verification/active` is dead code holding a live PII surface

The endpoint is token-authorized rather than session-authorized, and carries an explicit sanctioned-exception comment citing `INV-ARC-004 §V.3` — it is the one runtime path permitted to span a teacher's classes. That justification is sound for the *capability*. It is not sound for a *second, unused copy* of the capability:

- It returns student first names and last initials, destinations, and timestamps across every class the token's teacher owns.
- Its only credential is the `hall_pass_verify_token` in a query string.
- The server-rendered page implementing the same capability is rate limited to **60/min**; this endpoint inherits only the global default of **200/hour**, and query-string credentials are the kind that end up in proxy and referrer logs.

Nothing calls it. It is an unmonitored, more permissive twin of a surface that was deliberately hardened.

**Recommendation:** delete it. If a JSON verification surface is wanted later, it should be re-derived from the hardened page's guards rather than resurrected from this one.

### VIII-D. `/api/tap` enforces authentication imperatively

`handle_tap` is correct today — it 401s without a canonical context and 403s on a bad PIN. But it is the only mutating endpoint whose authentication lives entirely in the body, with no decorator. A refactor that reorders the early returns silently removes the check, and no reviewer scanning decorators would see it.

**Recommendation:** no behavioural change; add a regression test asserting 401 without a session and 403 on a wrong PIN, so the guarantee is pinned by something other than reading order.

---

## IX. Rules for Adding an Endpoint

1. **Justify the JSON.** If the page can render the state server-side, render it server-side. Every JSON endpoint is a second surface to authorize, scope, and keep alive.
2. **Carry an explicit auth decorator.** Enforce authentication declaratively even when the view re-checks it. §VIII-D is what the alternative costs.
3. **Scope by `class_id`.** The decorator authorizes the actor, never the record. Resolve canonical context and scope the query.
4. **Mutate through a FEAT** (`INV-ARC-006`). No `db.session.commit()` in a view.
5. **Keep GET pure** (`INV-ARC-007`). No writes, no lazy reconciliation, no expiry sweeps.
6. **Ship the caller in the same change.** An endpoint with no caller is how every entry in §VII-C started.
7. **Delete rather than deprecate.** There is no external consumer, so there is nothing to deprecate for.

---

## X. Regenerating This Inventory

The tables above are derived, not hand-maintained. Rebuild them from `app.url_map` rather than by grepping route decorators — the decorator scan cannot see stacked or dynamically-built routes, and produced two false results during the initial audit:

- `/admin/api/economy/*` looked orphaned because `economy-balance.js` composes its URLs from a base constant (`apiBaseUrl = '/admin/api/economy'`), so the full path never appears in any file.
- `/admin/payroll/rewards/add` looked like an ordinary route because a decorator scan attributes it to the function beneath it, which is exactly the bug.

Cross-reference callers against `templates/**/*.html` and `static/js/**/*.js`, and treat a zero-caller result as a question rather than a verdict.

---

**Last verified:** 2026-09-05 against 198 registered rules (63 JSON).
