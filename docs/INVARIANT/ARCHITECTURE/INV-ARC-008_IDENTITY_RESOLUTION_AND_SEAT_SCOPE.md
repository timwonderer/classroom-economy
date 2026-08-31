# INV-ARC-008: Identity Resolution and Seat Scope

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-008      | 1.2     | 2026-08-30     | 1.1        | Foundational    |

## I. Purpose

Define the execution-layer rules for resolving authenticated identity into active class
scope without fallback, leakage, or alias-based participant access.

## II. Scope

Applies to authentication resolution, session restoration, scoped participant routing,
and all request paths that derive `seat_id` or `class_id` from user-facing identity
inputs.

## III. Authority Level

Foundational within `INV-ARC`. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and Section III.4, `Principal and Actor Authority`, and governed within the hierarchy described by `INV-CORE-001`.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`
- `INV-ARC-010_EXPLICIT_CONTEXT_SWITCHING.md`
- `INV-ARC-011_NO_PHANTOM_SCOPE_ACCESS.md`

## V. Core Rule

Identity resolution MUST stop at one authenticated, active class context.

Requests MUST establish exactly one `seat_id` within exactly one active `class_id`, or
fail closed. Public actor references may only be emitted or compared after that
canonical context has already been established.

## VI. Execution Constraints

- **Authentication Resolution Pipeline**: The only authorized identity resolution chain
  during authentication is `users.id` -> active class context -> `seats.id` ->
  `identity_profile`.
- **Domain Execution Boundary**: Domain code MUST NOT reconstruct or infer `seat_id` or
  `class_id`. Those anchors must be supplied by the routing and authentication layer.
- **Student ID Quarantine**: Legacy `student_id` is transitional and load-bearing for
  legacy records only. It MUST NOT be introduced into new V2 domains, routes, or FEATs
  except inside explicitly approved bridge code.
- **Seat Public-ID Boundary**: `seats.public_id` is an outward-facing, UUID-encoded,
  deidentified representation of an already-resolved operational actor. It MUST NOT
  be used as an ingress identifier to discover, resolve, or reconstruct `seats.id`,
  `classes.class_id`, `users.id`, or canonical execution context. Canonical actor and
  class context MUST be established independently before `seats.public_id` is emitted
  or compared as presentation/reference data.
- **No Alias Substitution**: Legacy numeric student IDs and role-specific public IDs MUST
  NOT be accepted as substitutes for `seats.public_id` on class-scoped participant
  routes.
- **No Seat Fallback**: If a participant is not present in the active class, the
  request must fail. Resolution MUST NOT fall back to another seat owned by the same
  user or visible to the same teacher.

## VII. Rebuild Intent

This rule exists to prevent transitional identity bridges from becoming durable
authority shortcuts. The rebuild must treat active class scope as authoritative and
reject any attempt to recover meaning from alternate seats, legacy numeric IDs, or
global identity aliases.

## VIII. Downstream Consequence

`DOM-IDEN` owns the truth of users, seats, and class bindings, while request handlers
and auth helpers must enforce this invariant before any domain interaction occurs.

Teacher-facing participant navigation, class restoration, and claim-adjacent flows must
all fail closed on scope mismatch.

## IX. Amendment

Revisions must preserve fail-closed active-class resolution and the prohibition on
alias-based participant lookup. Public actor identity remains outward-only and must
not become a reverse-resolution authority.
