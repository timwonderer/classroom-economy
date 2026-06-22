# SOP-TEST-001: Validation Execution and Reporting

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-TEST-001     | 1.0     | 2026-06-13     | None       | Standard Operating Procedure |

## I. Purpose

This SOP defines how repository validation is executed and reported after the testing invariants in `INV-ARC-017` determine that testing is required.

## II. Dependencies

- `docs/INVARIANT/ARCHITECTURE/INV-ARC-017_GENERAL_TESTING_INVARIANTS.md`
- `docs/TESTING/SOP-TEST-003_Test_Creation.md`
- `docs/TRACKING/V2_Full_compliance_migration_plan.md`

## III. Canonical Test Scope Sets

The repository standardizes the following execution sets:

### A. Micro Set

- one test file, one test function, or one narrow `-k` expression

### B. Slice Set

- the changed feature slice and nearest regressions
- usually 2 to 6 related files

### C. Domain Set

- an entire domain contract plus adjacent boundary tests

### D. Gate Set

- a milestone, migration, or cross-cutting checkpoint

### E. Full Suite

- `pytest` without narrowing

## IV. Default Event Mapping

### 1. Small Code Fix

- Micro Set
- one adjacent regression test when needed

### 2. Route Change

- Slice Set
- authorization or scoping tests for affected class or seat boundaries

### 3. FEAT Change

- Slice Set
- mutation ownership and idempotency validation

### 4. Service Change

- Slice Set
- domain-contract and adjacent invariant tests

### 5. Model Change

- model-specific tests
- migration validation if schema changed

### 6. Migration Change

- migration lint when available
- upgrade, downgrade, re-upgrade, and head verification

### 7. Tenancy or Authority Change

- class-scoped tests
- cross-class rejection tests
- fail-closed lookup tests

### 8. Temporal or Scheduled Behavior Change

- class-local time tests
- deterministic boundary tests
- scheduler or idempotency tests if applicable

### 9. Documentation-Only Change

- no runtime test execution unless the doc changes a runtime, migration, protocol, or validation claim

### 10. Wave or Release Validation

- the wave-specific gate set from the tracker
- any migration or invariant gate referenced by the wave

## V. Execution Procedure

1. Identify the changed contract.
2. Select the smallest test set that proves it.
3. Run the narrowest proving set first.
4. Expand only when the change crosses more boundaries or an earlier run exposes broader risk.
5. Escalate to the full suite only when a gate, milestone, or evidence gap requires it.

## VI. Reporting Requirements

Every validation report must include:

- exact command
- scope class
- result
- relevant failures, skips, deselections, or xfails
- what changed since the last validated run, when that context matters

Permitted outcome labels:

- pass
- fail
- partial
- skipped
- blocked

## VII. Preferred Execution Patterns

- single file: `pytest -q tests/test_example.py`
- explicit subset: `pytest -q tests/test_a.py tests/test_b.py`
- scoped expression: `pytest -q tests/test_domain.py -k "keyword"`
- migration gate: `flask db upgrade`, `flask db downgrade`, `flask db upgrade`
- syntax smoke: `python3 -m py_compile <files>`
