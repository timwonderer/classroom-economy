# v2 Production Transition Runbook

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEP-023 | 1.3 | 2026-03-30 | 1.2 | Normative |

## I. Purpose

Provide the explicit operator workflow for moving the current v2 branch from live-test candidate to production transition.

## II. Scope

Production transition work for `codex/v2.0` after successful live testing, including maintenance-mode usage, migration execution, post-deploy verification, rollback decision points, and operator sign-off.

## III. Authority Level

Normative (SOP Tier). Subordinate to `INV-CORE-000`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `SOP-DB-009_Migration_Compliance_Review.md`
- `SOP-DEP-022_V2_Live_Test_Runbook.md`
- `SOP-DEP-016_Rollback_Procedures.md`

## V. Preconditions

- `codex/v2.0` is the approved deployment branch.
- Live-test runbook has been executed successfully.
- Migration compliance status has been reviewed.
- Backup, maintenance window, and rollback contacts are confirmed.
- Team-owned production and pre-production database targets are identified before any migration step begins.
- Named production operator, independent verifier, and rollback approver are assigned before the maintenance window starts.

## VI. Pre-Production Checklist

1. Enable maintenance mode if the deployment requires a protected window.
2. Verify current production backup or snapshot and test restore instructions.
3. Confirm migration head state and target revision.
4. Confirm operator sign-off from engineering and operations.
5. Reconfirm smoke checklist and escalation path.

Current branch verification references:

- maintenance workflow: `.github/workflows/toggle-maintenance.yml`
- deployment workflow: `.github/workflows/deploy.yml`
- migration safety check: `bash scripts/check-migrations.sh`

## VII. Upgrade Flow

1. Put the environment into maintenance mode.
2. Confirm the maintenance banner is active and operator messaging is correct.
3. Confirm migration head state and run the migration safety check.
4. Apply migrations.
5. Deploy application code.
6. Run post-deploy smoke checks before reopening the app.

## VIII. Post-Migration Verification

Verify:

- app boots normally
- `/admin/login` and `/student/login` load
- `/docs` loads
- teacher current-class switching works via `POST /admin/current-class`
- student add-class and switch-class flows work
- class-scoped admin actions respect membership
- selected-class export works via `/admin/export-students?join_code=<owned-join-code>`
- hall-pass verification path works via `/verify/hallpass/<teacher_public_token>`
- no unexpected migration head drift is present

## IX. Rollback Policy

- If migration fails before app reopen, rollback to the pre-deploy backup/snapshot.
- If post-deploy smoke checks fail and cannot be corrected within the maintenance window, rollback.
- If migration is structurally successful but business behavior is incorrect, hold maintenance mode until rollback or fix-forward is approved.

## X. Transition Record Template

Use this template for the production transition record:

```text
Production Transition Record
Date:
Branch:
Commit SHA:
Production operator:
Independent verifier:
Rollback approver:
Maintenance window:

Pre-window confirmation
- Backup/snapshot reference:
- Restore procedure verified:
- flask db heads:
- flask db current:
- bash scripts/check-migrations.sh:

Maintenance mode
- Enable action:
- Banner/message verified:

Deployment
- Migration result:
- Application deploy result:

Post-deploy verification
- /admin/login:
- /student/login:
- /docs:
- POST /admin/current-class:
- /student/add-class:
- POST /student/switch-class/<join_code>:
- /admin/export-students?join_code=<owned-join-code>:
- /verify/hallpass/<teacher_public_token>:

Outcome
- Reopen time:
- Go/no-go:
- Rollback needed:
- Operator sign-off:
- Independent verifier sign-off:
- Rollback approver sign-off:
```

## XI. Sign-Off Record

Record:

- deployment time
- operator
- branch SHA
- migration result
- smoke-check status
- reopen time
- rollback decision

## XII. Deferral Boundary

- This runbook is limited to launch-critical transition steps and operator records.
- Broader operational taxonomy changes, route-family cleanup, and post-port architecture alignment are deferred until after `../../SPECS/V2_ADMIN_ROUTE_REFACTOR.md` and `../../MAP/MAP-CLASS-002_CLASS_SCOPE_NORMALIZATION_TARGET.md`.

## XIII. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.
