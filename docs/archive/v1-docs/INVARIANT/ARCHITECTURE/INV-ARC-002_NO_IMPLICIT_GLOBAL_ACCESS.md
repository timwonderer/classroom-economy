# INV-ARC-002: No Implicit Global Access

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-002      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Prevent global or unscoped data access from becoming execution truth.

## II. Scope

Applies to all domain and feature logic.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`

## V. Core Rule

No domain or feature logic may access global or unscoped data.

All data access MUST be explicitly scoped using `join_code` or `class_id`.

## VI. Rebuild Intent

This rule exists to eliminate teacher-global shortcuts, unscoped balance use, and other
mixed-scope execution paths identified in the v2 rebuild audit.

## VII. Downstream Consequence

`DOM` and `FEAT` must treat any unscoped read used for runtime truth as invalid, even if
the underlying field or helper still exists in the repository.

## VIII. Amendment

Revisions must preserve explicit scoping requirements.
