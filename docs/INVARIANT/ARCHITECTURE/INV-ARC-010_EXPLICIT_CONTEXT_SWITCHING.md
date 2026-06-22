# INV-ARC-010: Explicit Context Switching

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-010      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Ensure context changes are explicit and observable.

## II. Scope

Applies to all request or actor context switching.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` Section III.4, `Principal and Actor Authority`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`

## V. Core Rule

All context changes MUST be explicit.

Implicit reuse of prior request state is forbidden.

## VI. Rebuild Intent

This rule exists to prevent convenience reuse of prior class, actor, or session state
from becoming hidden authority.

## VII. Downstream Consequence

`FEAT` flows must represent context changes explicitly, and `DOM` must not assume that a
previous request established valid scope for the current one.

## VIII. Amendment

Revisions must preserve explicit context switching.
