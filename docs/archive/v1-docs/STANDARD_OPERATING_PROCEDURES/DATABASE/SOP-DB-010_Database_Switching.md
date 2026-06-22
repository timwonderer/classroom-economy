# Database Configuration

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-010       | 1.1     | 2026-03-08     | 1.0        | Normative       |

## I. Purpose
To specify local developer environments regarding branch-based, automatic PostgreSQL database switching and configurations.

## II. Scope
All active contributor workstations testing against branch code.

## III. Authority Level
Normative (SOP Tier). Subordinate to INV-CORE-000.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`

## V. Automatic Branch-Based Database Switching

This repository uses branch-based database switching through the shared git hooks.

### Protected v2 Branches

- `codex/v2.0`
- `codex/v2-*`

These branches must use:

- the team-configured v2 dev database

### Test Database

Automated and manual tests for v2 must use:

- the team-configured PostgreSQL test database

This is not the same database as the protected dev/migration database.

### All Other Branches

All other branches may use:

- `postgresql://postgres:postgres@localhost:5432/production_dev`

## VI. How It Works

When you checkout a branch, the `hooks/post-checkout` hook updates `DATABASE_URL` in `.env` for the branch class it recognizes.

The hook and `./scripts/switch-db.sh` only allow the approved local dev URLs for this repo:

- `postgresql://postgres:postgres@localhost:5432/classroom_economy`
- `postgresql://postgres:postgres@localhost:5432/production_dev`

If `.env` contains a different `DATABASE_URL`, the tooling refuses to overwrite it. This is a safety guard against accidentally pointing local branch work at a deployed or otherwise non-local database.

## VII. Manual Switching

```bash
# Switch to production_dev (blocked on protected v2 branches)
./scripts/switch-db.sh production_dev

# Switch to classroom_economy
./scripts/switch-db.sh classroom_economy

# Check current database
./scripts/switch-db.sh
```

## VIII. Operator Truth

- `classroom_economy` is the v2 dev and migration rehearsal database.
- PostgreSQL test databases are branch-scoped through `TEST_DATABASE_URL`.
- `classroom_economy_v2_test` is the dedicated local PostgreSQL test database for `codex/v2-*` work.
- `classroom_economy_test` remains available for non-v2 or legacy local testing.
- `production_dev` is for non-v2 development branches.
- Any branch matching `codex/v2-*` is treated as v2 work and routes to `classroom_economy`.

## IX. Setup for Contributors

1. Run `./scripts/setup-hooks.sh`.
2. Checkout your branch.
3. Confirm `.env` contains the expected `DATABASE_URL`.
4. Confirm `.env` contains the expected `TEST_DATABASE_URL` for your branch.
5. Before running tests on v2 work, export:

```bash
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost/classroom_economy_v2_test
export DATABASE_URL="$TEST_DATABASE_URL"
```

## X. Troubleshooting

If automatic switching is not working:

1. Verify the hook exists: `ls -la hooks/post-checkout`
2. Verify hooks path config: `git config --get core.hooksPath`
3. Verify the hook is executable: `chmod +x hooks/post-checkout`
4. Use `./scripts/switch-db.sh` manually for the dev database
5. Set the test database explicitly in the shell before running pytest

## XI. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
