# INV-ARC-003: Scoped Capability Evaluation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-003      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Define how capability checks must evaluate scope.

## II. Scope

Applies to all capability checks.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and Section III.4, `Principal and Actor Authority`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`

## V. Core Rule

All capability checks MUST accept explicit context.

Capability evaluation without explicit class scope is invalid.

## VI. Requirements

- capability checks are side-effect free
- capability checks use explicit request-scoped context only
- capability checks are evaluated at request time

## VII. Rebuild Intent

This rule exists to turn capability checks into first-class architecture rather than
route-local conditionals embedded in controllers.

## VIII. Downstream Consequence

`DOM` must expose side-effect-free capability evaluation, and `FEAT` must not replace it
with inline authorization logic.

## IX. Amendment

Revisions must preserve request-scoped capability evaluation.
