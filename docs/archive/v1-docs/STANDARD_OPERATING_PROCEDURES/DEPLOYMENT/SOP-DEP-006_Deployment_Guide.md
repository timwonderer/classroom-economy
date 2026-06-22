---
title: Deployment Guide
category: operations
roles: [developer, teacher]
---

# Deployment Guide

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DEP-006| 1.2 | 2026-03-08 | 1.1 |Normative|

This guide provides the current top-level deployment contract for v2.0 live-test readiness. Use it with:

- `SOP-DEP-022_V2_Live_Test_Runbook.md`
- `SOP-DEP-023_V2_Production_Transition_Runbook.md`

## I. Purpose

TBD
## II. Scope

TBD
## III. Authority Level
Normative. Subordinate to CORE invariant definitions.
## IV. Dependencies
None specified.
## V. Environment Variables

Required:

- `SECRET_KEY`
- `DATABASE_URL`
- `FLASK_ENV`
- `ENCRYPTION_KEY`
- `PEPPER_KEY`
- `CSRF_SECRET_KEY`

## VI. Database Truth

- Dev and migration rehearsal DB:
  - use the team-configured v2 dev database
- Test DB:
  - use the team-configured PostgreSQL test database

## VII. Standard Deploy Flow

1. Install dependencies.
2. Confirm branch and database target.
3. Run migration rehearsal or production transition checklist as appropriate.
4. Apply migrations with `flask db upgrade`.
5. Start the application server.
6. Run smoke checks.

## VIII. Maintenance Mode

Maintenance mode is persistent across code deploys and must be turned on and off intentionally. Use it during production transition and any migration that needs a protected validation window.

## IX. Reset Warning

Do not use schema-drop reset instructions for live-test or production-like environments. Database reset remains a local-development escape hatch only.

## X. CI/CD

The deployment workflows are defined in the repo workflows. For v2.0 readiness, operator-owned runbooks take precedence over generic deployment steps.
## XI. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.
