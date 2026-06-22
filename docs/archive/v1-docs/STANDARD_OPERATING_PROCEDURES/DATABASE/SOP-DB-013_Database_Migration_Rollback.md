# Database Migration Rollback Procedures

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DB-013       | 1.0     | 2026-03-01     | N/A        | Normative                 |

## I. Purpose
To define the strict protocols governing the downgrade of Alembic database migrations.

## II. Scope
All Postgres database instances storing application data, specifically when using `flask db downgrade`.

## III. Authority Level
SOP Tier.

## IV. Dependencies
- SOP-DB-011: Migration Specifications
- SOP-DEP-016: Rollback Procedures

## V. Pre-Migration Backups
Prior to any downgrade in production, a fresh pg_dump backup must be captured from the database:
`pg_dump classroom_economy > backup_$(date +%Y%m%d_%H%M%S).sql`

## VI. Downgrade Procedure
1. Identify the intended target revision using `flask db history`.
2. Downgrade using: `flask db downgrade <target_revision>`.
3. Do not manually `DROP TABLE` or `ALTER COLUMN` outside of Alembic to perform rollbacks.

## VII. Data Validation
- Post-downgrade, cross-check total user counts to ensure no orphaned rows were inadvertently wiped (unless such drop was intended).
- Re-run `flask db current` to verify successful reversion.

## VIII. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field.
