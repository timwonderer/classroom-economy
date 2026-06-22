# INV-ARC-017: General Testing Invariants

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-017      | 1.2     | 2026-06-13     | V2-TEST-000 v1.0 | Constitutional |

## I. Purpose

This document defines the canonical testing invariants for the `codex/v2.0` rebuild. It standardizes what testing must prove, when testing is required, and which reporting behaviors are mandatory before a change can be represented as validated.

Execution details, command sequences, and PR-operational gates belong in SOP documents, not here.

## II. Scope

This invariant applies to all repository changes that can affect runtime behavior, migration behavior, documentation claims about runtime behavior, or release readiness.

It governs:

- local development validation expectations
- feature and bug-fix verification expectations
- migration and schema validation expectations
- cross-domain and regression validation expectations
- tracker and documentation claims about test status
- release and deployment readiness claims

## III. Authority Level

Constitutional within `INV-ARC`. Derived from `INV-CORE-000` Section III.7, `No Unnecessary Barriers to Supported Use`, and governed within the hierarchy described by `INV-CORE-001`. It standardizes repository-wide testing expectations and is subordinate to foundational invariants and may not weaken them.

## IV. Dependencies

- `docs/STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md`
- `docs/TRACKING/V2_Full_compliance_migration_plan.md`
- `docs/TRACKING/V2_REBUILD_VALIDATION_REPORT.md`
- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`
- `docs/TESTING/SOP-TEST-001_Validation_Execution_And_Reporting.md`
- `docs/TESTING/SOP-TEST-002_Accessibility_Validation_And_PR_Gate.md`
- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`

## V. Testing Invariants

1. Testing must be proportional to the change.
2. Tests must prove the changed behavior and the most likely adjacent regressions.
3. Tests must be scoped to the affected contract, domain, or subsystem before broader suites are considered.
4. The full suite must not be treated as the default action for every change.
5. A test result may only be reported as passing when the exact command and scope are recorded.
6. A claim of coverage must be tied to concrete execution evidence, not inference.
7. Testing is required before any claim of completion, merge readiness, release readiness, or tracker advancement when the change can affect runtime behavior, migration behavior, or a validation-backed documentation claim.
8. Documentation may not assert runtime behavior, migration state, or validation status without supporting test evidence that already exists or is rerun for the claim.
9. When a change affects scoping, authority, tenancy, migration safety, temporal boundaries, or template accessibility, the validation set must explicitly include that boundary.
10. A partial run must not be represented as whole-scope validation.

## VI. Required Coverage Categories

Every change set must validate the following as applicable:

1. Changed path success behavior.
2. Changed path failure and denial behavior.
3. Relevant authorization and scoping behavior.
4. Relevant migration upgrade and downgrade behavior.
5. Relevant invariant behavior.
6. Adjacent regression surfaces.
7. Any contract explicitly mentioned in tracker, spec, or issue text.

When a change touches one of the following, the corresponding category must be included:

- `class_id` or `join_code` logic: cross-class scoping, fail-closed lookup, and public/private boundary behavior
- FEAT code: mutation ownership, idempotency, and commit behavior
- GET handlers: no-write behavior and side-effect suppression
- migrations: upgrade, downgrade, re-upgrade, and head validation
- time-sensitive logic: class-local temporal boundaries and UTC storage behavior
- documentation claims: supporting runtime or test evidence must exist
- template or UI accessibility surfaces: semantic structure, user-perceivable state, and relevant accessibility guards

## VII. Reporting Invariants

All validation reporting must be concise, concrete, and evidence-based.

Every validation claim must preserve:

- exact command disclosure
- truthful scope disclosure
- accurate result labeling
- explicit acknowledgment of remaining untested or blocked surface when present

Do not claim broader coverage than the executed evidence supports.

## VIII. Amendment

Revisions to this document must increment the version number, update the effective date, preserve compatibility with `INV-CORE-000` and `INV-CORE-001`, and update any dependent SOP or tracker references that rely on this invariant.
