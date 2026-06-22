# SOP-TEST-003: Test Creation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-TEST-003     | 1.0     | 2026-06-13     | V2-TEST-001 v1.0 | Standard Operating Procedure |

## I. Purpose

This SOP defines the canonical procedure for creating tests in the `codex/v2.0` codebase. It standardizes when tests must be added, what the test should prove, how to scope the test, how to structure the test, and how to validate that the test itself is fit for use.

## II. Scope

This SOP applies whenever a contributor introduces new behavior, changes existing behavior, fixes a bug, modifies a migration, alters a contract, or updates a documentation claim that depends on runtime behavior.

It governs:

- new test design
- regression test creation
- test file organization
- selection of assertions and fixtures
- test naming and scope
- validation of new or changed tests before they are relied upon

It complements `INV-ARC-017` and the testing execution SOPs. This document answers how to create the test; the companion SOPs answer how to run and report it.

## III. Dependencies

- `docs/INVARIANT/ARCHITECTURE/INV-ARC-017_GENERAL_TESTING_INVARIANTS.md`
- `docs/STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md`
- `docs/TRACKING/V2_Full_compliance_migration_plan.md`
- `docs/TRACKING/V2_REBUILD_VALIDATION_REPORT.md`
- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`
- `docs/TESTING/SOP-TEST-002_Accessibility_Validation_And_PR_Gate.md`
- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`

## IV. Test Creation Principles

1. A test must prove one meaningful contract, not several unrelated behaviors.
2. Every test must have a clear reason to exist.
3. A test must be narrow enough to diagnose failures quickly.
4. A new test should be written against the smallest stable surface that expresses the contract.
5. A test must not encode implementation details unless the implementation detail is the contract being protected.
6. A test must not rely on broad fixtures when a focused fixture can prove the same behavior.
7. A test must reflect the current canonical architecture, not the legacy path unless the legacy path itself is the subject of the test.

## V. When To Create Tests

Create or update tests whenever any of the following happen:

1. New runtime behavior is introduced.
2. Existing behavior changes.
3. A bug is fixed.
4. A migration changes schema behavior.
5. A FEAT changes mutation ownership or idempotency.
6. A route changes authorization, scoping, or side-effect behavior.
7. A service or model changes its public contract.
8. A tracked bug, wave, or refactor mentions a required regression.
9. A documentation claim depends on runtime evidence and no test currently proves it.
10. A template or UI accessibility fix changes rendered semantics, contrast behavior, naming, focus, or disclosure state.

Do not wait until the end of a large change to invent tests retroactively if the contract can be stated earlier.

## VI. What A Created Test Must Cover

Every newly created test must establish the following, as applicable:

1. The expected success path.
2. The relevant failure or denial path.
3. The boundary or scope rule that matters.
4. The regression the test is preventing.
5. The observable outcome that proves the contract.

If the change touches one of these areas, the test must cover the corresponding contract:

- tenancy or class scoping: same-class allowance and cross-class rejection
- FEAT mutation: ownership, commit boundary, and idempotency
- GET handlers: no write side effects
- migrations: upgrade, downgrade, and head consistency
- time-sensitive logic: class-local boundaries and deterministic timestamps
- authentication or recovery: fail-closed behavior and session integrity
- documentation claims: runtime evidence must be available or newly produced
- template accessibility: rendered structure, semantic linkage, and browser-visible contrast or ARIA behavior

## VII. Test Design Workflow

1. Identify the contract.
2. Identify the smallest reliable execution path that proves it.
3. Decide whether the test belongs in a helper, feature, domain, or integration-style file.
4. Choose fixtures that model the real state boundary as closely as possible.
5. Add only the assertions needed to prove the contract and the adjacent regression risk.
6. Prefer explicit state setup over hidden fixture magic.
7. Keep negative-path tests fail-closed and direct.
8. Ensure the test name describes the contract, not the implementation trick.

## VIII. Test Construction Rules

### A. File Placement

- Put the test in the closest file or domain folder that already owns the contract.
- Add a new file when the contract spans a distinct feature or domain boundary.
- Do not create a generic catch-all test file for unrelated behaviors.

### B. Naming

- Test names must describe the contract in plain terms.
- Prefer names that encode outcome and scope.
- Avoid names that describe only implementation internals.

### C. Fixtures

- Use the smallest fixture set that reproduces the contract.
- Seed only the rows, session values, and context needed for the test.
- Preserve class and seat scoping in every fixture that touches multi-tenant data.
- Model the canonical identity path when the test concerns current runtime behavior.

### D. Assertions

- Assert outcomes, not incidental implementation details, unless the implementation detail is the invariant.
- Include explicit denial assertions for fail-closed behavior.
- Include cross-scope rejection assertions for tenancy-sensitive behavior.
- Include downgrade or rollback assertions when a migration or schema claim is involved.

### E. Negative Tests

- Every bug fix test set must include at least one regression test that fails on the prior broken behavior.
- Every authorization or scope test set must include at least one rejection case.
- Every mutation path test set must include at least one guard or denial case.

## IX. Required Validation For New Tests

Before a new test is treated as authoritative, the contributor must validate that:

1. The test runs in the intended scope.
2. The test fails for the prior broken behavior when that behavior is still present.
3. The test passes against the patched behavior.
4. The test is not overfitted to an incidental fixture artifact.
5. The test does not duplicate an existing test without adding a stricter contract.

Minimum validation evidence for a newly added test:

- the exact test command
- the intended scope
- the passing result
- if relevant, the prior failure mode that the test would have caught

## X. Standard Test Shapes

### 1. Regression Test

Use when a bug has been fixed and the exact broken behavior should never return.

Must include:

- a setup that reproduces the broken condition
- an assertion that fails against the broken behavior
- an assertion that passes on the fixed behavior

### 2. Boundary Test

Use when a contract depends on class, seat, user, tenant, or temporal boundaries.

Must include:

- an in-scope case
- an out-of-scope case
- explicit proof that the boundary is enforced

### 3. Contract Test

Use when a service, FEAT, or helper exposes a stable public behavior.

Must include:

- the input contract
- the expected output or side effect
- the error path if the input is invalid

### 4. Migration Test

Use when schema, head state, or downgrade safety changes.

Must include:

- upgrade validation
- downgrade validation
- re-upgrade validation when relevant

### 5. Route Test

Use when a route changes authorization, response shape, or side-effect behavior.

Must include:

- the route entrypoint
- the scoped request context
- the expected status or redirect
- the expected no-write or write behavior

## XI. Quality Bar

A newly created test is acceptable only if it is:

1. focused
2. readable
3. deterministic
4. scoped to the changed contract
5. able to fail for the relevant regression
6. able to distinguish correct from incorrect behavior

If a test requires excessive setup to prove a small contract, the test design is too broad and should be simplified.

## XII. Anti-Patterns

The following are prohibited as test creation patterns:

1. Writing broad tests that only prove the app starts.
2. Using giant fixtures when a small fixture proves the same contract.
3. Testing implementation details that are not part of the contract.
4. Mixing unrelated behaviors into one test.
5. Writing only happy-path tests for a bug fix.
6. Creating tests that merely mirror the code instead of validating behavior.
7. Adding tests that can never fail because they assert trivial truths.
8. Treating documentation claims as sufficient without runtime evidence.
