# INV-ARC-004: Cross Tenant Isolation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-004      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Define the one-tenant-per-request rule.

## II. Scope

Applies to all runtime requests and background execution paths.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`

## V. Core Rule

A single request MUST NOT:

- read across multiple `join_code` boundaries
- write across multiple `join_code` boundaries

All execution is constrained to a single tenant boundary.

## VI. Rebuild Intent

This rule exists to prevent fan-out reads, cross-tenant writes, and mixed-scope
capability decisions from reappearing in the rebuild.

## VII. Downstream Consequence

Any `DOM` or `FEAT` design that requires more than one tenant boundary inside one
request is invalid at this level.

## VIII. Amendment

Revisions must preserve one-tenant-per-request execution.
