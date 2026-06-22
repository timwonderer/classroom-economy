# INV-ARC-007: GET Must Be Pure

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-007      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Preserve read purity in HTTP GET execution.

## II. Scope

Applies to all GET requests.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` Section III.3, `Deterministic and Traceable Financial Logic`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`

## V. Core Rule

GET requests MUST be side-effect free.

GET requests MUST NOT:

- commit
- flush
- trigger domain mutations

## VI. Rebuild Intent

This rule exists to remove the specific class of bugs where viewing a page changes
financial state, expires goals, settles balances, or repairs runtime data.

## VII. Downstream Consequence

Any rebuild design that requires mutation during `GET` is invalid and must be moved to a
command or job path instead.

## VIII. Amendment

Revisions must preserve read purity.
