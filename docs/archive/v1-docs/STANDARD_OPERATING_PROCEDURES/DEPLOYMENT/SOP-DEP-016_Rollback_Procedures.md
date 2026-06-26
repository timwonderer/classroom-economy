# Rollback Procedures

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DEP-016| 1.1 | 2026-03-08 | 1.0 |Normative|

## I. Purpose
Establish a repeatable workflow for rolling back non-functional or severely bugged deployments to a prior stable state across staging and production environments.

## II. Scope
All environments managed via automated CI/CD pipelines and manual server deployments. Must be used when P0 incidents are identified during or immediately post-deployment.

## III. Authority Level
SOP Tier.

## IV. Dependencies
- SOP-DEP-015: CI/CD Pipeline Documentation
- SOP-DB-013: Database Migration Rollback

## V. Rollback Criteria
A rollback must be initiated if:
- Core operations (Login, Attendance, Banking) fail immediately for a significant subset of users.
- Migrations cause catastrophic data formatting errors that are detected in staging.
- Security bypass endpoints are mistakenly deployed.

## VI. Step-by-Step Rollback Workflow
1. **Identify the Last Known Good Commit:**
   Using GitHub, locate the SHA of the last commit prior to deployment.
2. **Revert DB (if needed):**
   Before reverting code, execute `flask db downgrade <target_revision>` according to `SOP-DB-013`.
3. **Revert Code:**
   Execute `git revert <failed_commit_sha>` or push a direct undo commit.
4. **Trigger Deployment:**
   Push to main to trigger the deployment workflow, or manually execute the deployment script.

## VII. Verification Post-Rollback
- Verify the system health dashboards.
- Execute validation smoke tests.
## VIII. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.
