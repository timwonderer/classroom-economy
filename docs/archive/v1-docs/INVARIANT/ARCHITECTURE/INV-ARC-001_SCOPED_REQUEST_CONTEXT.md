# INV-ARC-001: Scoped Request Context

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-001      | 1.0     | 2026-04-13     | N/A        | Foundational    |

## I. Purpose

Define the required request context for all request-time decision making.

## II. Scope

Applies to all runtime actions that evaluate capability or execute domain commands.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and Section III.4, `Principal and Actor Authority`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-000_EXECUTION_MODEL.md`

## V. Core Rule

All requests MUST construct explicit request context containing:

- `user_id`
- `class_id`
- `seat_id`
- `actor_type`
- `request_id`
- `timestamp`

> [!IMPORTANT]
>
> Although `user_id` is included in every context construction, `user_id` should only be used for the following cases:
> 1. `seat_id` look up within the `class_id` boundary provided
> 2. Verifying session validity 
> 2. user credential recovery
> 4. account deletion

Requests missing required scope MUST fail immediately.

## VI. Rebuild Intent

This rule exists to prevent the rebuild from falling back to route-local assumptions,
implicit session carryover, or actor-only access patterns that bypass tenant scope.

## VII. Downstream Consequence

`DOM` and `FEAT` must assume that missing request context is a hard failure, not a cue to
infer or repair scope implicitly.

## VIII. Amendment

Revisions must preserve explicit scope requirements and alignment with `INV-ARC-000`.
