# V2 FEATBypass Dependency Report

**Generated:** 2026-07-12 20:00 UTC
**Commit:** `7ae01697`
**Plan:** [V2_FEAT_BYPASS_DEFAULT_FLIP_PLAN.md](./V2_FEAT_BYPASS_DEFAULT_FLIP_PLAN.md) — historical Phase 1 output, retained for trend comparison.

---

## Executive findings

**Dead-route surface was 4 unique mutating endpoints** in the Phase 1 run, far smaller than the audit-plan ceiling of ~78 derived from `143 mutating route decls − 65 @feat_shell decorators`. Most undecorated routes delegate to FEAT-wrapped service functions.

**GET-side-effect surface was 0 unique endpoints.** INV-ARC-007 (GETs must be pure) was largely respected in runtime.

**Fixture-only bypass dependency dominated the run.** The bulk of Phase 2 migration work is fixture-seeding consolidation, not route fixing. The top callsite hotspot was `tests/helpers/class_scope.py:create_class_scope` (see Fixture callsites section).

**590 flush-producing observations were classified** in the run. The audited cohort comprised fixture-only bypass use plus four dead-route endpoints; there were no GET side effects.

---

## Methodology

For every test that ran in the suite, a SQLAlchemy `before_flush` listener (installed by `tests/_feat_bypass_audit.py`) inspected the active FEAT stack. Any flush where `FEATBypass` was the only thing in scope — and the session held new/dirty/deleted entities — would have raised `FEATContextError` under production enforcement. Those flushes are the data behind this report.

Each test is bucketed by what its bypass dependency looks like:

- **`passes_under_enforcement`** — no bypass-hidden flushes observed. Test would run cleanly with enforcement on.
- **`fixture_only_bypass`** — bypass-hidden flushes seen during setup/teardown or in test bodies that are not inside a Flask route dispatch. Fixture infrastructure needs an explicit `with FEATBypass():` wrap; the route call itself is not dead.
- **`get_side_effect`** — a bypass-hidden flush happened inside a GET handler. This is an [INV-ARC-007](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md) candidate: GETs are required to be side-effect free. Separate category from dead-route since the fix is "remove the write" rather than "add `@feat_shell`".
- **`dead_route_dependent`** — a bypass-hidden flush happened inside a mutating-method (POST/PUT/DELETE/PATCH) route handler. The route is mutating state without `@feat_shell` and would return HTTP 500 under enforcement. **These are the dead routes Phase 4 will need to fix.**

The dispatch discriminator uses the call stack (looking for Flask's `wsgi_app`, `full_dispatch_request`, `dispatch_request`, or `preprocess_request` frames), not `has_request_context()`. pytest-flask leaves a dangling request context around fixture code, so the stack check is the reliable signal for "is a real route handler running right now."

---

## Summary

| Bucket | Tests | % of recorded |
|---|---:|---:|
| Pass under enforcement     |     0 |   0.0% |
| Fixture-only bypass        |   585 |  99.2% |
| GET side-effect            |     0 |   0.0% |
| Dead-route dependent       |     5 |   0.8% |
| **Total tests observed**   |   590 | 100.0% |

_Total tests collected by pytest: 816. Difference vs observed = tests that errored before any flush ran (typically import/collect failures) or tests that produced no flushes at all._

---

## Dead-route inventory — POST/PUT/DELETE/PATCH endpoints flushed under bypass

These mutating-method endpoints performed at least one flush while only `FEATBypass` kept the session-level enforcement quiet. Each is a candidate to either (a) get a `@feat_shell` decorator or (b) confirm it routes mutation through a separately-decorated service function.

The four dead-route endpoints observed in Phase 1 were:

- `POST admin.process_claim`
- `POST sysadmin.resolve_escalated_issue`
- `POST admin.rent_settings`
- `POST admin.passkey_auth_finish`

---

## GET-side-effect inventory — INV-ARC-007 candidates

GET handlers are required to be side-effect free. These endpoints flushed mutated state during a GET. The fix is to remove the write (typically a lazy-create or reconciliation pattern), not to add `@feat_shell`.

No GET-side-effect flushes were observed.

---

## Top fixture-only flush callsites

These are the source locations where bypass-hidden flushes most frequently originate in fixture/setup code. Phase 2 fixture consolidation should target these hotspots first.

The top fixture-only flush callsites were concentrated in `tests/helpers/class_scope.py:create_class_scope`.

---

## Raw data

Machine-readable per-test data lives in `V2_FEAT_BYPASS_DEPENDENCY_REPORT_RAW.json`.
