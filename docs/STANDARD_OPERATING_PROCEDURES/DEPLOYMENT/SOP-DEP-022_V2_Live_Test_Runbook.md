# v2 Live-Test Runbook

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEP-022      | 1.2     | 2026-03-31     | 1.1      | Normative       |

## I. Purpose
Provide the exact operator workflow for preparing the current v2 branch for live testing.

## II. Scope
All testing deployments from the current branch running against v2 operational databases.

## III. Authority Level
Normative (SOP Tier). Subordinate to INV-CORE-000.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`
- `SOP-DB-009_Migration_Compliance_Review.md`
- `SOP-DB-011_Migration_Specifications.md`

## V. Environment Truth

- Branch: `codex/v2.0`
- Dev/migration DB: the team-configured v2 dev database for migration rehearsal
- Test DB: the team-configured PostgreSQL test database used for v2 validation

## VI. Pre-Live-Test Checklist

1. Confirm branch and clean worktree.
2. Confirm migration head state:

```bash
flask db heads
flask db current
bash scripts/check-migrations.sh
```

3. Rehearse migration upgrade on the team-configured dev/migration DB:

```bash
DATABASE_URL=<team-dev-migration-db-url> flask db upgrade
DATABASE_URL=<team-dev-migration-db-url> flask db current
```

4. Run the full PostgreSQL test suite:

```bash
DATABASE_URL=<team-test-db-url> pytest -q
```

5. Record the result and confirm it matches or exceeds the latest validated baseline:
   - `664 passed, 1 skipped`

## VII. Smoke-Route Ownership Model

The live-test smoke pass must be owned and recorded with named humans, not left as an implied team task.

Required named roles for each rehearsal or go-live smoke pass:

- primary operator: runs upgrade and captures command output
- independent verifier: executes or witnesses the smoke routes and confirms behavior was checked by someone other than the branch author
- engineering escalation owner: approves hold/fix-forward/rollback if the smoke pass fails

The primary operator and engineering escalation owner may be the same person if staffing requires it. The independent verifier must be a different person from the branch author.

### Solo-Operator Exception

In single-operator environments where an independent verifier is not available, the operator MAY assume all roles (primary operator, independent verifier, and engineering escalation owner), provided that all of the following are satisfied:

- the full PostgreSQL-backed test suite passes with no failures
- all defined smoke routes in Section VIII are executed and recorded
- results are fully documented in the Rehearsal Record (Section X)
- any known risks, anomalies, or deviations are explicitly noted prior to go/no-go decision

Optional augmentation (solo mode only):
- AI-assisted review MAY be used to identify potential defects or invariant violations
- AI output is advisory only and MUST NOT be treated as independent verification authority

## VIII. Smoke Routes

Verify these paths manually after upgrade:

- `/admin/login`
- `/student/login`
- `/docs`
- teacher current-class switching via `POST /admin/current-class`
- student add-class flow via `/student/add-class`
- student switch-class flow via `POST /student/switch-class/<join_code>`
- admin selected-class export via `/admin/export-students?join_code=<owned-join-code>`
- hall-pass verification via `/verify/hallpass/<teacher_public_token>`

For each route, record:

- owner
- execution timestamp
- pass/fail/blocked
- notes or defect link

## IX. Seed and Fixture Expectations

- Use canonical v2 class scope: `ClassEconomy`, admin `ClassMembership`, student `ClassMembership`.
- Do not assume TeacherBlock-only authority for class access.
- Use at least two teacher-owned classes for the rehearsal so current-class switching, selected-class export, and student switch-class checks are meaningful.

## X. Rehearsal Record Template

Use this template for the rehearsal artifact or ticket comment:

```text
Live-Test Rehearsal Record
Date:
Branch:
Commit SHA: (populate after commit using `git rev-parse HEAD`)
Primary operator:
Independent verifier:
Engineering escalation owner:
Database target:

Pre-upgrade checks
- flask db heads:
- flask db current:
- bash scripts/check-migrations.sh:

Upgrade
- DATABASE_URL=<team-dev-migration-db-url> flask db upgrade:
- DATABASE_URL=<team-dev-migration-db-url> flask db current:

Test suite
- DATABASE_URL=<team-test-db-url> pytest -q:

Smoke routes
- /admin/login:
- /student/login:
- /docs:
- POST /admin/current-class:
- /student/add-class:
- POST /student/switch-class/<join_code>:
- /admin/export-students?join_code=<owned-join-code>:
- /verify/hallpass/<teacher_public_token>:

Decision
- Live-test go/no-go:
- Follow-up issues:
- Operator confirmation:
- Independent verifier confirmation:
```

---
## XI. Rehearsal Record Storage and Finalization

The rehearsal record is completed in two phases:

### Phase 1 — Pre-Commit Rehearsal
- Execute all steps in Sections VI–VIII.
- Fill out the rehearsal record with all available information.
- Leave `Commit SHA` as pending.

### Phase 2 — Commit and Finalization
- Commit the validated changes.
- Retrieve the commit SHA:

```bash
git rev-parse HEAD
```

- Update the rehearsal record with the actual commit SHA.
- Store the finalized record in one of the following:
  - a LOGS-AUD-* artifact file in the repository, or
  - a linked ticket / PR comment that is retained as an audit record

Recommended repo-tracked artifact:

- `docs/LOGS/AUDITS/LOG-DEP-024_V2_Live_Test_Rehearsal_Checklist.md`

The stored record MUST be immutable after finalization and must correspond exactly to the deployed commit.

---

## XII. Backup and Rollback Decision

Before live testing:

1. Confirm a recoverable snapshot or backup of the live-test target database exists.
2. If migration rehearsal fails, stop and rollback before exposing testers.
3. If smoke checks fail after upgrade, revert to backup or hold the environment in maintenance mode until resolved.

## XIII. Required Output Record

Capture and store:

- migration head state before upgrade
- migration head state after upgrade
- pytest summary
- smoke-check status
- final go/no-go decision for live testing

## XIV. Deferral Boundary

- This runbook intentionally avoids a broader route-taxonomy rewrite or operations-document restructure.
- Any deeper cleanup driven by route renames, class-scope normalization, or cross-SOP reorganization is deferred until after `../../SPECS/V2_ADMIN_ROUTE_REFACTOR.md` and `../../MAP/MAP-CLASS-002_CLASS_SCOPE_NORMALIZATION_TARGET.md`.

## XV. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
