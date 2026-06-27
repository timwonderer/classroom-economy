# Production Deployment Instructions

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DEP-001| 1.2 | 2026-03-08 | 1.1 |Normative|

**Branch:** `codex/v2.0`
**Status:** Base production deployment instructions for the current v2 line

## I. Purpose

This document is the baseline production deployment reference. For v2.0 live testing and eventual production transition, operators must use it together with:

- `SOP-DEP-022_V2_Live_Test_Runbook.md`
- `SOP-DEP-023_V2_Production_Transition_Runbook.md`

## II. Scope

TBD
## III. Authority Level
Normative. Subordinate to CORE invariant definitions.
## IV. Dependencies
None specified.
## V. Pre-Deployment Baseline

1. Confirm working branch is `codex/v2.0`.
2. Confirm backup plan and rollback contacts.
3. Confirm maintenance-mode plan.
4. Confirm migration head state.
5. Confirm the latest PostgreSQL test-suite result is green.

## VI. Required Commands

```bash
flask db heads
flask db current
flask db upgrade
```

## VII. Post-Deploy Minimum Checks

1. Teacher login page loads.
2. Student login page loads.
3. Docs page loads.
4. Teacher current-class switching works.
5. Student class switching works.
6. Hall-pass verification route responds for a known teacher public ID.

## VIII. v2-Specific Warning

Do not treat older branch-specific deployment notes as current production instructions. The only active v2 integration branch is `codex/v2.0`.
## IX. Amendment
Revisions to this document require incrementing the version number, updating the Effective Date, and populating the Supersedes field. Subordinate to CORE changes.
