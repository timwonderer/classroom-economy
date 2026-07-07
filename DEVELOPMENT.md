# Classroom Token Hub - Development Priorities

**Last Updated:** 2026-03-30
**Current Released Version:** 1.9.0
**Engineering State:** v2.0 live-test candidate
**Active Integration Branch:** `codex/v2.0`

## Quick Links

- **[Architecture Guide](docs/ARCHITECTURE/ARC-CORE-000_Architecture_Foundation.md)** - System design and patterns
- **[Database Schema](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md)** - Current data models and transitional compatibility notes
- **[Class Scope Normalization Target](docs/MAP/MAP-CLASS-002_CLASS_SCOPE_NORMALIZATION_TARGET.md)** - Deferred post-port target for `class_id`-first internal scoping
- **[V2 Banking Ledger Settlement Plan](docs/SPECS/V2_BANKING_LEDGER_SETTLEMENT_PLAN.md)** - Deferred rebuild plan for per-account balances, settlement checkpoints, and reconciliation
- **[API Reference](docs/ARCHITECTURE/OPERATIONS/ARC-OPS-005_Api_Reference.md)** - Runtime contract for public, student, and admin APIs
- **[v2 Main Reconciliation Tracker](docs/archive/v1-development/tracking/V2_MAIN_RECONCILIATION_TRACKER.md)** - `origin/main` features not yet reconciled into `codex/v2.0`
- **[v2 Launch Readiness Matrix](docs/archive/v1-development/tracking/V2_LAUNCH_READINESS_MATRIX.md)** - Current launch blockers and readiness status
- **[v2 Documentation Compliance Sweep](docs/archive/v1-development/tracking/V2_DOCUMENTATION_COMPLIANCE_SWEEP.md)** - Active-doc compliance status for v2
- **[v2 Parallel Workstreams](docs/archive/v1-development/tracking/V2_PARALLEL_WORKSTREAMS.md)** - Parallel execution map for multi-threaded v2 work
- **[v2 Class ID Invariant Backlog](docs/SPECS/V2_CLASS_ID_INVARIANT_BACKLOG.md)** - Deferred cleanup for class lifecycle and membership semantics that violate the `class_id` model
- **[v2 Live-Test Runbook](docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-022_V2_Live_Test_Runbook.md)** - Internal validation workflow before live testing

## Branch and Database Truth

- Only `codex/v2.0` is an active protected v2 branch.
- Dev and migration work must use the team-configured v2 dev database.
- Test runs must use the team-configured PostgreSQL test database.
- The validated v2 branch state passed:
  - `DATABASE_URL=<team-test-db-url> pytest -q`
  - Result: `708 passed, 1 skipped`

## Git Hooks

Run once after clone:

```bash
./scripts/setup-hooks.sh
```


## Current v2.0 State

### Ready Now

- `classes.class_id` is the canonical class boundary; `join_code` is a public alias.
- `Seat + Class` is the runtime class-scoped authority for student/admin/API flows.
- Legacy `ClassMembership`, `student_teachers`, and principal columns may still support compatibility paths, but they are not the identity or class-boundary authority.
- Branch consolidation is complete: prior merge-prep branches were folded into `codex/v2.0` and pruned.
- Migration heads are resolved in repo with `e8f1a2b3c4d5_merge_remaining_v2_heads.py`.
- Full-suite validation succeeded on the PostgreSQL test database.
- Economy policy scheduling, rebalance timing, rent-cycle locking, penalty-reversal corrections, transaction idempotency, frozen economy snapshots, waiver scope, settlement safety, and related sysadmin auth/logging fixes have landed on `codex/v2.0`.
- Wave 7 rent-waiver actor attribution is now seat-scoped, and rent-waiver add/remove flows no longer emit legacy analytics rows; the analytics schema still needs its own seat-scoped cutover before those annotations return.
- Pricing recommendation logic is now centralized in `app/utils/economy_policy.py`, with the checker, rebalance preview, economy APIs, and insurance setup/edit pages consuming that shared source instead of duplicating pricing math.
- Main-branch feature divergence is now tracked in `docs/archive/v1-development/tracking/V2_MAIN_RECONCILIATION_TRACKER.md`.

### Required Before Live Testing

- Publish and review the v2 live-test runbook with operator ownership.
- Refresh migration-compliance status so current exceptions are explicit and not buried in historical audit language.
- Rehearse migration upgrade flow on the v2 dev database with operator-facing verification steps.
- Complete smoke-route checklist and confirm it can be executed by someone who did not author the branch.
- Remove or supersede stale docs that still imply deleted branches or legacy TeacherBlock fallback plans.
- Confirm whether the remaining adjacent economy-health delta from `main` (CWI warning bypass controls) is needed before live testing or can move to the post-live-test/production lane.
- Port launch-critical `origin/main` deltas called out in the v2 reconciliation tracker.
- Close active-doc issues still marked open in `docs/archive/v1-development/tracking/V2_DOCUMENTATION_COMPLIANCE_SWEEP.md`.

### Required Before Production

- Complete the v2 production transition runbook and sign-off workflow.
- Re-audit rollback expectations for migrations that are forward-safe but not business-safe to downgrade after live data changes.
- Finish operator backup/restore rehearsal on the intended production topology.
- Confirm monitoring, maintenance-mode usage, and post-deploy verification steps are current.
- Port production-required `origin/main` deltas still marked open in the reconciliation tracker.

## Operations Doc Boundaries

- This branch now carries only launch-critical v2 runbook fixes needed for live testing and production transition.
- Deeper operations-document restructuring, route-taxonomy cleanup, and architecture-driven SOP rewrites are intentionally deferred until after `docs/SPECS/V2_ADMIN_ROUTE_REFACTOR.md` and `docs/MAP/MAP-CLASS-002_CLASS_SCOPE_NORMALIZATION_TARGET.md` are ready to land.
- Until those refactors land, prefer targeted supersession notes, explicit operator record templates, and current-command verification over broad documentation reorganization.

### Post-Live-Test Cleanup

- Broader historical audit cleanup and supersession notes.
- Lower-priority guide refreshes where wording is stale but not dangerous.
- Compatibility shim reduction for legacy aliases that still exist only to ease migration or testing.
- Class-scope normalization project to move internal scoping from `join_code` to `class_id`.
- Banking ledger rebuild project to move financial authority to `class_id + seat_id + account_type` with explicit available/current balance semantics.
- Class-identity invariant cleanup that removes pseudo-lifecycle semantics from class and membership layers.

## v2.0 Technical Direction

- `users.id` is the authentication principal; legacy role-specific session keys are route compatibility shadows only.
- `seats.id` plus `classes.class_id` is the class-scoped runtime authority.
- `join_code` is a public class alias and must resolve to `class_id` before authority-sensitive work.
- Class-scoped reads and writes are seat/class-gated, not `teacher_id`-, `student_id`-, block-, or `TeacherBlock`-gated.
- Public actor identity uses UUID-encoded `Seat.public_id`, not role-specific public-ID families.
- Roster upload provisions an inactive `User`, class-local `Seat`, seat-bound `IdentityProfile`, and seat-owned claim artifacts; it does not create an authenticated student.
- v2 documentation should not describe TeacherBlock fallback as intended runtime behavior.
- Use `db.session.get(Model, id)`, not `Model.query.get(id)`. Treat `Query.get()` as banned in new development.

## Focus Areas

### High Priority

#### 1. Live-Test Operational Readiness

- Finalize runbooks for v2 live testing and production transition.
- Document migration rehearsal, verification queries, and rollback decision points.
- Confirm maintenance-mode and operator sign-off procedures.

#### 2. Migration and Schema Safety

- Keep migration-head hygiene explicit in docs and deployment instructions.
- Track remaining migration-policy exceptions separately from current v2 merge readiness.
- Publish current migration validation expectations for local, test, and production-like databases.

#### 3. Residual v2 Hardening

- Continue removing compatibility-only assumptions that are no longer part of the v2 runtime contract.
- Audit lower-priority read paths and sysadmin paths for contract clarity and documentation parity.
- Keep “all sections” semantics explicit anywhere teacher-wide fan-out still exists.

### Medium Priority

#### 1. Documentation Consistency

- Keep architecture, SOP, and user guides aligned with `codex/v2.0`.
- Prefer superseding notes on historical audits over rewriting release-history records.

#### 2. Live-Test Feedback Loop

- Capture findings from live testing in the v2 checklist and runbooks.
- Convert any repeated operator questions into permanent SOP updates.

## Release Framing

- Public docs site remains on the current released product line: **1.9.0**.
- Internal engineering docs describe the repo as a **v2.0 live-test candidate**.
- Do not label v2.0 as released until live-test and production transition gates are complete.
