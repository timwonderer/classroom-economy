# INV-ARC-011: No Phantom Scope Access

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-011      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Prevent requests from succeeding against non-existent scope.

## II. Scope

Applies to all requests referencing tenant scope.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and Section III.5, `Definite Class Lifecycle`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-004_CROSS_TENANT_ISOLATION.md`

## V. Core Rule

Requests referencing non-existent `join_code` MUST fail.

No fallback or recovery logic is permitted.

## VI. Rebuild Intent

This rule exists to prevent the rebuild from papering over missing or deleted tenant
state with fallback lookups, alternate scope, or “best effort” recovery logic.

## VII. Downstream Consequence

`DOM` and `FEAT` must treat non-existent scope as terminal for that request path.

## VIII. Amendment

Revisions must preserve hard failure for phantom scope.
