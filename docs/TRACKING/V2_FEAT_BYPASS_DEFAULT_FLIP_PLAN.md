# V2 FEATBypass Default-Flip Plan

**Status:** Phase 1 complete (2026-06-09). Phase 2 next.
**Owner:** V2 architecture
**Related:** [V2_Full_compliance_migration_plan.md](./V2_Full_compliance_migration_plan.md), [V2_FEAT_BYPASS_DEPENDENCY_REPORT.md](./V2_FEAT_BYPASS_DEPENDENCY_REPORT.md) (Phase 1 output), [FEAT-CORE-000](../FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md), [INV-ARC-006](../INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md)

---

## Context

The FEAT constitutional directive (FEAT-CORE-000, INV-ARC-006) requires every
state mutation to occur inside a registered FEAT context. Runtime enforcement
lives in `app/feats/base.py` via `init_feat_enforcement(app)`, which attaches
a `before_flush` listener that raises `FEATContextError` on any unscoped
mutation.

In tests, `tests/conftest.py:268-285` declares an `autouse=True` fixture that
wraps **every test** in `FEATBypass()` unless the test opts out with
`@pytest.mark.enforce_feat`. The constitutional model is therefore inverted in
CI: enforcement is opt-in rather than the default.

This inversion was discovered during the FEAT-STOR-006 audit (2026-06-08), when
two production routes (`/api/approve-redemption`, `/api/reject-redemption`)
were found to be **dead in production** — they raised `FEATContextError →
HTTP 500` for any real request, but the test suite passed because every test
ran under bypass. CI could not surface the breakage. The redemption fix
landed under a `@pytest.mark.enforce_feat`-marked test suite that explicitly
runs the routes with enforcement live; that pattern is the template this
plan rolls out everywhere else.

A second architectural bug surfaced in the same audit: the cross-FEAT
correlation guard in `app/models.py:932` was firing on UPDATE as well as
INSERT, making it impossible for any FEAT to mutate a `Transaction` row
created by a previous FEAT (refunds, voids, `reversal_transaction_id`
linkage). Hidden because each test ran under a single FEATBypass
correlation. Fixed alongside the redemption work.

The pattern is consistent: **the test default is masking real production
breakage**. The default must invert.

---

## Audit findings (2026-06-09 reconnaissance)

| Metric | Value | What it tells us |
|---|---|---|
| Test files | 137 | Surface area |
| Test functions | 872 | Triage workload |
| Test files using `db.session.add`/`commit` directly | 117 | ~85% of tests depend on the autouse bypass for fixture seeding |
| Mutating route calls in tests (`client.post/put/delete/patch`) | 371 | Each is a potential dead-route observation |
| `@feat_shell`-decorated routes/functions in `app/` | 65 across 17 files | The known-safe surface |
| Mutating route declarations in `app/routes/` | 143 | Ceiling on dead-route candidates: ~78 |
| Tests using `@pytest.mark.enforce_feat` today | 7 (in 2 files) | The marker is rarely used; the default is doing 99.2% of the work |
| Inline `with FEATBypass():` in tests | 5 occurrences across 2 files | Fixture-level bypass is the exception, not the norm |
| `FEATBypass()` calls in `app/` (production code) | **0** | Bypass is structurally test-only; flip carries no production risk |
| Bypass-aware checks in `app/` | 16 (all in `models.py` / `feats/base.py`) | Production knows about bypass but never instantiates it |

### Headline findings

**A. The load-bearing default.** With 872 tests and 7 opt-outs, 99.2% of the
suite runs with enforcement disabled. The constitution is inverted.

**B. Estimated dead-route surface.** With 143 mutating route declarations and
65 `@feat_shell` decorators, the upper bound on dead routes is ~78. Actual
will be smaller (some routes delegate to FEAT-wrapped service functions, some
POSTs are read-projections), but the magnitude warrants empirical
instrumentation before guessing. Phase 1 produces the real number.

**C. Cross-FEAT correlation bug (already fixed in the redemption PR).** The
`Transaction.before_insert/before_update` listener's "Mixed correlation in
flush" check fired on UPDATE as well as INSERT, preventing valid cross-FEAT
mutations. Fixed by gating the check on `_target_state.transient or pending`.
This is the canonical example of what Phase 1 should look for: a real
production bug invisible to CI.

**D. No production bypass calls.** Zero `FEATBypass()` calls in `app/`. The
flip is purely a test-suite change.

**E. Fixture-seeding centralization gap.** 117 test files do their own
`db.session.add` for fixture rows. There is no shared canonical fixture
catalog. Phase 2 builds one.

---

## Risk shape

- **Reversibility:** Each phase below is reversible by a single `git revert`.
  No DB or production state involved.
- **Production risk:** Zero. Bypass is test-only.
- **Blast radius if Phase 4 ships without Phases 1–3:** ~100+ failing tests
  with mixed root causes (real dead routes, fixture issues, architectural
  bugs). Impossible to triage cleanly.
- **Blast radius if Phase 1 ships alone:** Zero. Pure read instrumentation.

---

## Staged plan

### Phase 1 — Instrumentation (✅ complete 2026-06-09)

**Goal:** Empirical evidence of the actual dead-route surface before any
default change.

**Deliverables (shipped):**
- `tests/_feat_bypass_audit.py` — pytest plugin (opt-in via
  `FEAT_BYPASS_AUDIT=1`) that hooks SQLAlchemy `before_flush`. For each
  test running under `FEATBypass`, the plugin records:
  - Whether the flush would have raised `FEATContextError` under enforcement
  - Whether the flush is inside a real Flask route dispatch (using the call
    stack — `has_request_context()` is unreliable because pytest-flask leaves
    a dangling context around fixture code)
  - The originating endpoint + HTTP method if in dispatch
  - A trimmed call stack for fixture-code attribution
- `scripts/regenerate_feat_bypass_report.py` — re-emits the markdown from
  the raw JSON without a fresh suite run. Decouples report-format iteration
  from the 11-minute audit run.
- `docs/TRACKING/V2_FEAT_BYPASS_DEPENDENCY_REPORT.md` — four
  buckets:
  1. `passes_under_enforcement` (no bypass-hidden flushes observed)
  2. `fixture_only_bypass` (seeding-only bypass dependency)
  3. `get_side_effect` (INV-ARC-007 candidate — bonus discriminator added
     during Phase 1 because the data warranted separating it from the dead-
     route bucket)
  4. `dead_route_dependent` (route mutates in a non-FEAT context — dead in
     production)

**Findings (2026-06-09 run, 816 tests collected, 590 produced flushes):**

| Bucket | Count |
|---|---:|
| `passes_under_enforcement` | 0 |
| `fixture_only_bypass` | 585 |
| `get_side_effect` | **0** |
| `dead_route_dependent` | **5 tests across 4 endpoints** |

**Dead-route endpoints:**
- `POST admin.process_claim` — insurance claim approval (10 flushes)
- `POST sysadmin.resolve_escalated_issue` — sysadmin issue resolution (5)
- `POST admin.rent_settings` — rent settings update (2)
- `POST admin.passkey_auth_finish` — passkey auth finish (1)

**Key surprises vs the pre-instrumentation estimate:**
- Dead-route surface is **4 endpoints, not ~78.** The earlier ceiling
  (`143 − 65`) overcounted by ~20×. Most undecorated routes delegate to
  FEAT-wrapped service functions; the gap is concentrated, not pervasive.
- **Zero GET-side-effect bypass-hidden flushes.** INV-ARC-007 is largely
  respected in runtime.
- **Fixture seeding is the dominant work.** 585 tests have fixture-only
  bypass dependency; the top hotspot is
  `tests/helpers/class_scope.py:create_class_scope` (587 flushes across
  five line numbers in the same function). Phase 2 fixture consolidation
  should target it first.

The full table including method, flush counts, and first-observed test is
in [V2_FEAT_BYPASS_DEPENDENCY_REPORT.md](./V2_FEAT_BYPASS_DEPENDENCY_REPORT.md).

**Implication for downstream phases:**
- Phase 2 (fixture consolidation) is the bulk of the migration work, not
  Phase 4 (the flip).
- Phase 4's triage workload is bounded: 4 routes to fix, each a small
  targeted change.
- Phase 5's dead-route inventory starts at 4 entries; achievable to drain
  before Wave 12.

---

### Phase 2 — Fixture consolidation (3–5 days)

**Goal:** Move bypass dependency from "wraps every test body" to "wraps
explicit fixture helpers."

**Deliverables:**
- Extend `tests/helpers/v2_fixtures.py` (or a new
  `tests/helpers/fixtures.py`) with bypass-scoped seed helpers:
  - `seed_canonical_admin(username) -> ids` — creates `User` + `Admin` shadow
    with proper credential hashes, all under one `with FEATBypass():`
  - `seed_class_with_seat(admin_id, ...) -> ids`
  - `seed_store_item(class_id, ...) -> ids`
  - `seed_purchase(seat_id, item_id, ...) -> ids` — creates the canonical
    `Transaction` + `StudentItem` pair
  - Similar for rent, insurance, attendance
- Each helper returns ID snapshots (not detached ORM objects) so post-commit
  reads work cleanly. Template:
  `tests/test_redemption_disposition_feat.py::_seed_redemption_scenario`.
- At least three example tests demonstrating "uses Phase-2 fixtures,
  needs no autouse bypass."

**Progress update (2026-07-12):**
- `tests/helpers/v2_fixtures.py` now includes the shared canonical seed
  helpers (`seed_canonical_admin`, `seed_class_with_seat`,
  `seed_store_item`, `seed_purchase`).
- Representative tests have been migrated onto the shared helpers:
  `tests/test_canonical_auth_session.py` and
  `tests/test_sysadmin_issue_rewards.py`.

**Constraint:** Phase 2 is additive. Existing tests continue to inherit the
conftest autouse bypass. The migration of legacy tests onto these helpers
happens during Phase 4 triage.

**Exit criterion:** Helper catalog exists; three example tests run cleanly
under `@pytest.mark.enforce_feat`.

---

### Phase 3 — Pilot enforcement on clean route families (~1 week)

**Goal:** Validate the migration pattern on routes that already have
`@feat_shell` coverage before tackling the long tail.

**Selected families:**
- Hall pass (`FEAT-ATTN-*`) — small, well-bounded
- Transfer (`FEAT-LED-*`) — financial, high-value to prove
- Redemption (`FEAT-STOR-006`) — just landed; already enforces

**Procedure for each family:**
1. Add `@pytest.mark.enforce_feat` to every test touching the family
2. Migrate those tests onto Phase 2 fixture helpers
3. Run them. Each failure is classified into one of four buckets, tagged in
   the commit message:
   - `(arch)` — architectural bug like Finding C
   - `(route)` — route missing `@feat_shell` (dead route)
   - `(test)` — test infrastructure issue (e.g., session setup)
   - `(fixture)` — fixture leaks bypass dependency
4. Fix each, with the bucket label visible in the diff

**Exit criterion:** Three families run cleanly under enforcement. Bucket
distribution from the pilot documented; used as the input estimate for Phase
4 triage cost.

---

### Phase 4 — Flag day: invert the marker (1 day to flip; 1–2 weeks of triage)

**Goal:** Enforcement is the default; opt-out is explicit and traceable.

**Change to `tests/conftest.py`:**

```python
@pytest.fixture(autouse=True)
def _feat_enforcement_default(request, app):
    """
    FEAT enforcement is the default. Tests that must seed legacy state
    or test legacy paths can opt out with @pytest.mark.legacy_bypass.

    The old `enforce_feat` marker is preserved as a no-op alias for one
    release cycle so existing marked tests don't need to be touched.
    """
    if "legacy_bypass" in request.keywords:
        from app.feats.base import FEATBypass
        with FEATBypass():
            yield
        return
    yield
```

**Triage procedure for each failing test:**
1. **Fixture-setup failure on flush** → add `@pytest.mark.legacy_bypass` with
   a one-line comment naming the reason. Tracked for Phase 5.
2. **Route call failure because the route is dead** → DO NOT add the bypass.
   Add `@pytest.mark.xfail(reason="...", strict=True)` referencing the issue
   number. This becomes the dead-route inventory.
3. **Architectural bug (like Finding C)** → fix as part of this PR if small;
   otherwise file an issue and xfail with reference.
4. **Test infrastructure bug (session keys, etc.)** → fix as part of this PR.

**Deliverables:**
- One PR that ships the conftest flip + all marker/xfail additions
- `docs/TRACKING/V2_DEAD_ROUTE_INVENTORY.md` — every `xfail` from
  category 2, with route, FEAT-code-needed, and assigned wave

**Exit criterion:**
- Default-on enforcement is live in `main`
- Every `legacy_bypass` marker has a one-line reason comment
- Dead-route inventory exists with a count and per-route disposition

---

### Phase 5 — Drain `legacy_bypass` and the dead-route inventory (ongoing)

**Goal:** Reduce both markers to zero.

**Per-marker disposition:**
- `(fixture-only)` markers → refactor to use Phase-2 fixture helpers; remove
  the test-level marker
- Dead-route xfails → fix the route (add `@feat_shell`, register a FEAT code
  if needed); remove the xfail
- Architectural-bug xfails → architecture PRs; remove the xfail

**Tracked metrics:**
- `legacy_bypass` marker count
- `xfail(reason=dead-route)` count

Both metrics are surfaced in
`V2_Full_compliance_migration_plan.md`. **Wave 12 (final validation) gates on
both metrics being zero.**

---

## Open questions to resolve before Phase 4

- Should the `enforce_feat` marker remain as a no-op alias for one release
  cycle, or be removed immediately? (Current preference: preserve for one
  cycle to avoid churn on the 7 existing marked tests.)
- Should the conftest change include a transition log line ("running under
  legacy_bypass: <reason>") on every bypass-marked test, to make accidental
  regression visible? (Probably yes; cheap and informative.)
- Should the Phase 1 report be machine-readable (JSON/CSV) as well as
  markdown? (Probably yes; helps Phase 4 triage automation.)

---

## Methodology note (recorded for future audits)

The original FEATBypass audit asserted "428 `session.get('admin_id')`
references bypass canonical authority" based on a grep count, without
authority-path validation. Live probe showed the resolver gate was active
and the references were cosmetic. Lesson: **authority-path reasoning is
the finding step; grep is the reconnaissance step.** Phase 1's
instrumentation respects this: it observes actual flush behavior under
enforcement, not source patterns.
