# SOP-DB-015: Schema Change Gate

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DB-015| 1.1 | 2026-03-08 | 1.0 |Normative|

## I. Purpose

This document defines the **Schema Change Gate** — a mandatory checklist that determines whether a pull request involving schema changes may be merged.

## II. Scope

All pull requests that modify the database schema, including columns, tables, foreign keys, or model attributes.

## III. Authority Level

Normative (SOP Tier). Subordinate to INV-CORE-000.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `SOP-DB-011_Migration_Specifications.md`

## V. When This Gate Applies

This gate is REQUIRED if a pull request includes **any** of the following:

- Dropping or renaming a column
- Dropping or renaming a table
- Removing or changing foreign keys
- Replacing one-to-one or one-to-many relations with association tables
- Removing model attributes that map to existing database columns

If none of the above apply, this gate does not apply.

## VI. PR Classification (Required)

Every schema-affecting PR MUST declare **exactly one** classification at the top of the PR description:

- [ ] **EXPAND** – Additive, backward-compatible (no removals)
- [ ] **CONTRACT (CODE ONLY)** – Model attribute removal, DB schema unchanged
- [ ] **CONTRACT (DATABASE)** – Destructive migration only

If no classification is selected, the PR is invalid.

## VII. Mandatory Checklist (PR-Blocking)

All items below MUST be checked before merge.

### 1. Expand / Contract Compliance

- [ ] This PR represents **only one phase** of Expand / Contract
- [ ] No destructive DB changes are included in EXPAND or CONTRACT (CODE ONLY)
- [ ] CONTRACT (DATABASE) PR contains **no unrelated code changes**

### 2. Model & Runtime Safety

- [ ] Legacy attributes removed from models (if applicable)
- [ ] Application boots and runs without legacy attributes
- [ ] No runtime access to deprecated attributes remains

### 3. Deprecated Symbol Audit

- [ ] All deprecated attributes/columns are listed explicitly
- [ ] No deprecated symbols appear in application code
- [ ] Any allowlisted exceptions (tests/migrations) are documented

### 4. Migration Robustness

- [ ] No constraint names are hardcoded
- [ ] Constraints are discovered dynamically via inspection
- [ ] Migrations are idempotent where feasible

### 5. Migration Rehearsal

- [ ] Migration rehearsed on production-like clone
- [ ] `upgrade` succeeds
- [ ] `downgrade` succeeds **or** migration declared irreversible

**If rehearsal not performed:**

- [ ] PR labeled **UNSAFE: NO MIGRATION REHEARSAL**
- [ ] Elevated risk explicitly acknowledged

### 6. Testing Requirements

- [ ] No tests were fixed mechanically
- [ ] Tests affected by schema change were re-evaluated for intent

**Mandatory workflows verified:**

- [ ] Account claiming
- [ ] Money transfer
- [ ] Student creation / association
- [ ] Admin / teacher-scoped operations

### 7. Smoke Testing

- [ ] Critical workflows smoke-tested (manual or automated)
- [ ] ORM/DB boundary verified under real execution

## VIII. Enforcement Mechanism (How This Becomes PR-Blocking)

This gate is enforced through **process and automation**:

### 1. Process Enforcement

- PRs modifying schema **must** include this checklist in the PR description
- Missing or unchecked items = automatic request for changes
- Reviewers are empowered to block merge solely on gate violation

### 2. Automation Enforcement (Recommended)

At minimum, CI SHOULD:

- Detect schema-affecting files (models, migrations)
- Fail if PR classification is missing
- Fail if deprecated symbols appear in application code

Optional advanced enforcement:

- Require successful migration rehearsal job
- Require explicit approval for UNSAFE-labeled PRs

## IX. Decision Authority

- Passing the Schema Change Gate is **required but not sufficient** for merge
- Failing the gate is **sufficient** to block merge
- Exceptions require explicit acknowledgment of production risk

## X. Summary

> **If it changes the schema, it changes the risk profile.**  
> This gate exists to make that risk visible, reviewable, and intentional.

## XI. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.

