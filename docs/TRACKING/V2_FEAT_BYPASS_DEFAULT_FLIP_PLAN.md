# V2 FEATBypass Default-Flip Plan

**Status:** Enforcement is default in tree; Phase 2 fixture consolidation continues.
**Owner:** V2 architecture
**Related:** [V2_Full_compliance_migration_plan.md](./V2_Full_compliance_migration_plan.md), [V2_FEAT_BYPASS_DEPENDENCY_REPORT.md](./V2_FEAT_BYPASS_DEPENDENCY_REPORT.md) (Phase 1 output), [FEAT-CORE-000](../FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md), [INV-ARC-006](../INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md)

---

## Context

The FEAT constitutional directive (FEAT-CORE-000, INV-ARC-006) requires every
state mutation to occur inside a registered FEAT context. Runtime enforcement
lives in `app/feats/base.py` via `init_feat_enforcement(app)`, which attaches
a `before_flush` listener that raises `FEATContextError` on any unscoped
mutation.

The test harness previously inverted the constitutional model by wrapping
tests in `FEATBypass()` by default. That state has now been removed from the
tree; enforcement is the default execution model and bypass is restricted to
explicit fixture seeding or audit scaffolding.

The inversion was discovered during the FEAT-STOR-006 audit (2026-06-08),
when two production routes (`/api/approve-redemption`,
`/api/reject-redemption`) were found to be dead in production. The current
tree has since moved those tests onto live enforcement, and that pattern is
now the reference point for the remaining migration work.

A second architectural bug surfaced in the same audit: the cross-FEAT
correlation guard in `app/models.py:932` was firing on UPDATE as well as
INSERT, making it impossible for any FEAT to mutate a `Transaction` row
created by a previous FEAT (refunds, voids, `reversal_transaction_id`
linkage). Hidden because each test ran under a single FEATBypass
correlation. Fixed alongside the redemption work.

The pattern is consistent: **the test default used to mask real production
breakage**. The tree has now inverted that default; remaining work is to
finish the fixture migration and drain the explicit exceptions.

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
| Tests using `@pytest.mark.enforce_feat` today | 7 (in 2 files) | The enforcement marker is present and green on the current pilot slices |
| Inline `with FEATBypass():` in tests | 5 occurrences across 2 files | Explicit bypass is now confined to fixture seeding / audit scaffolding |
| `FEATBypass()` calls in `app/` (production code) | **0** | Bypass is structurally test-only; flip carries no production risk |
| Bypass-aware checks in `app/` | 16 (all in `models.py` / `feats/base.py`) | Production knows about bypass but never instantiates it |

### Headline findings

**A. The load-bearing default is fixed.** The autouse bypass wrapper is gone
from `tests/conftest.py`; enforcement now runs by default in-tree.

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
- The 4-route dead-route list above is now a historical snapshot, not the
  current live surface; the routes have since been verified FEAT-owned in
  the tree.
- Phase 5's dead-route inventory should be regenerated from the current
  codebase before using it as launch-readiness evidence.

---

### Phase 2 — Fixture consolidation (3–5 days)

**Goal:** Move bypass dependency from "wraps every test body" to "wraps
explicit fixture helpers."

**Done so far:**
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

**Still remaining:**
- At least three example tests demonstrating "uses Phase-2 fixtures,
  needs no autouse bypass."
- Migrate any remaining fixture helpers that still construct canonical
  rows with v1-tainted assumptions rather than explicit `class_id`/`seat_id`
  inputs.
- Drain the audit-only implied-authority gaps tracked in
  [`AUDIT_IMPLIED_AUTHORITY_TODO.md`](./AUDIT_IMPLIED_AUTHORITY_TODO.md).

**Progress update (2026-07-12):**
- `tests/helpers/v2_fixtures.py` now includes the shared canonical seed
  helpers (`seed_canonical_admin`, `seed_class_with_seat`,
  `seed_store_item`, `seed_purchase`, `seed_student_identity`,
  `seed_student_membership`,
  `seed_class_feature`,
  `clear_class_feature`).
- `tests/test_collective_goal_expiration.py` and
  `tests/test_economy_policy_mode.py` now keep students and class-owned
  records on one explicit canonical class scope per scenario instead of
  re-deriving class ownership from teacher lookup or join-code shims.
- The remaining audit-only implied-authority gaps for the policy-mode and
  collective-goal fixture reshapes are tracked in
  [`AUDIT_IMPLIED_AUTHORITY_TODO.md`](./AUDIT_IMPLIED_AUTHORITY_TODO.md).
- Representative tests have been migrated onto the shared helpers:
  `tests/test_canonical_auth_session.py` and
  `tests/test_sysadmin_issue_rewards.py`, plus
  `tests/test_feature_flag_enforcement.py` for class-feature setup and
  `tests/test_api_tenancy.py` and `tests/test_admin_multi_tenancy.py` for
  shared student/class seeding, plus
  `tests/test_core_invariants_smoke.py` for shared class-feature seeding,
  plus `tests/test_shared_student_payroll.py` for multi-class student
  membership and payroll scoping.
- `tests/test_feature_flag_enforcement.py` had a latent banking fixture bug
  (`join_code` undefined) that was corrected while moving it onto the shared
  helper path.
- `tests/helpers/class_scope.py` now accepts `feature_names` so class setup
  can seed canonical `ClassFeature` rows inline instead of open-coding the
  loop in each test.
- `tests/helpers/context_factory.py` now also supports `feature_names` so
  higher-level classroom context builders can seed canonical feature flags
  without bespoke helper code.
- `tests/test_feature_settings.py` now uses FEAT-scoped feature-row writes
  for its class-feature assertions instead of unscoped commits.
- `tests/test_attendance_seat_scope.py` now seeds and mutates attendance
  records inside FEAT contexts rather than relying on raw commits.
- `tests/test_payroll_settings_class_scope.py` and
  `tests/test_banking_settings_class_scope.py` now use FEAT-scoped class
  creation and canonical session setup for their class-scope assertions.
- `app/routes/admin.py:rent_settings` now resolves scope from canonical
  `class_id` and treats `settings_block` as display-only, matching DOM-IDEN
  authority rules.
- `tests/test_rent_settings_class_scope.py` now uses the shared feature-seed
  helper instead of hand-rolling the `ClassFeature` row.
- `tests/test_economy_api.py` now seeds its canonical admin/class/session
  state through the shared helpers and canonical session context instead of
  committing ad hoc session mirrors outside FEAT contexts.
- The economy API verification slice that exercises payroll-hours defaults
  and frozen analysis snapshots is passing again under the canonical setup.
- The global autouse `FEATBypass()` wrapper is gone from the test harness.
  Enforcement is now the default execution model; bypass remains limited to
  explicit fixture seeding helpers and the audit plugin.
- Enforcement-marked suites currently pass:
  `tests/test_feat_enforcement.py` and
  `tests/test_redemption_disposition_feat.py`.

**Constraint:** Phase 2 is additive. Legacy tests may still need explicit
fixture-helper migration, but the harness no longer relies on a global
autouse bypass.

**Exit criteria:**
- Helper catalog exists.
- Three example tests run cleanly under `@pytest.mark.enforce_feat`.
- Remaining fixtures no longer invent class ownership by teacher lookup or
  join-code shims.

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

### Phase 4 — Flag day completed in tree (evidence-driven state)

**Goal:** Enforcement is the default; the old autouse bypass wrapper is no
longer present in `tests/conftest.py`.

**Current state:**
- `tests/conftest.py` no longer wraps every test in `FEATBypass()`.
- Enforcement-marked suites run under live FEAT enforcement.
- Explicit bypass remains only as a test-only fixture helper primitive and
  audit/instrumentation concept.

**Current triage focus:**
1. Remove or rewrite any test that still assumes v1-tainted bypass behavior.
2. Continue migrating remaining fixture helpers to canonical FEAT ownership.
3. Keep dead-route validation on enforcement-marked slices, and only add new
   route coverage when a real route-level bug is proven.

### Phase 5 — Drain remaining exceptions (ongoing)

**Goal:** Reduce bypass-dependent fixture code and any remaining dead-route
inventory to zero.

**Tracked metrics:**
- explicit `with FEATBypass():` helper count
- `xfail(reason=dead-route)` count
- bypass-hidden fixture helper count

Wave 12 (final validation) still gates on those metrics reaching zero.

## Open questions

- Which remaining fixture helpers still need canonicalization under the shared
  FEAT-scoped helper catalog?
- Are there any lingering dead-route xfails that should be converted back into
  live enforcement tests or removed entirely?
- Should the bypass audit report continue to emphasize fixture-only dependency
  now that the global autouse wrapper is gone?

---

## Methodology note (recorded for future audits)

The original FEATBypass audit asserted "428 `session.get('admin_id')`
references bypass canonical authority" based on a grep count, without
authority-path validation. Live probe showed the resolver gate was active
and the references were cosmetic. Lesson: **authority-path reasoning is
the finding step; grep is the reconnaissance step.** Phase 1's
instrumentation respects this: it observes actual flush behavior under
enforcement, not source patterns.
