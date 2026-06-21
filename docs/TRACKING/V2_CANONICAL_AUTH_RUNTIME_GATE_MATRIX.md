# V2 Canonical Auth Runtime Gate Matrix

## Status

- **Gate type:** hard stop
- **Applies to:** runtime request context, class/seat authority, and any request-time identity or scope resolution
- **Authority:** `INV-CORE-000`, `INV-CORE-001`, `INV-ARC-001`, `INV-ARC-002`, `INV-ARC-006`, `INV-ARC-007`, `INV-ARC-008`, `INV-ARC-010`, `INV-ARC-011`, `INV-ARC-014`, `INV-ARC-019`

This matrix is the active compliance gate for the canonical-auth runtime cutover. A row marked `Remove` blocks merge until it is eliminated. A row marked `Rewrite` may remain temporarily only if the new implementation is on the approved canonical path and the old behavior is fully retired from request-time authority. A row marked `Allowed` is permitted only if it stays within the canonical boundary described below.

Canonical context is immutable for the lifetime of a request.

## Canonical Rule Summary

- `join_code` is user-facing and must resolve to `class_id` before authority-sensitive behavior.
- `user_id`, `class_id`, and `seat_id` must come from canonical request context, not from route-local inference.
- No request may recover authority from prior session state if the current request context is missing or invalid.
- All context switching must be explicit and observable.
- GET routes must remain pure.

## Matrix

| Area | Current Pattern | Classification | Why | Required Action |
|---|---|---:|---|---|
| Request context construction | `g.canonical_context` resolved at request boundary | Allowed | Matches explicit request context and request-time authority requirements. | Preserve only if it remains the sole runtime authority object. |
| Canonical resolution inputs | `user_id` + persisted active class selection + seat lookup under boundary | Rewrite | Transitional use of persisted selection is acceptable only if it is treated as an explicit, prior confirmed context and not as hidden fallback. | Ensure the request boundary fails closed when selection is missing or invalid. |
| Authority propagation | Reconstructing `CanonicalContext` or copying authority fields after boundary | Remove | Authority must originate exactly once per request. Multiple constructors create divergent runtime state and hidden authority sources. | Pass the canonical context object by reference; do not rebuild it downstream. |
| Session-backed class anchor | `session["current_class_id"]` / `get_current_class_id()` as authority | Remove | Violates no-implicit-global-access and explicit-context-switching rules. | Keep removed from all request-time authority paths. |
| Session-backed seat anchor | `session["current_seat_id"]` / `seat_id` session writes | Remove | Creates a second runtime anchor and enables implicit reuse of prior scope. | Do not restore seat/class authority from session. |
| Join-code display in templates | `join_code` shown to users and used in labels/forms | Allowed | `join_code` is a human-facing alias and is permitted for display and user input. | Keep UI-facing only; never treat as authority without boundary resolution. |
| Join-code request inputs | `join_code` submitted in selector/import flows | Rewrite | Allowed only as ingress; must resolve to `class_id` before authority-sensitive actions. | Resolve once at boundary and discard as control key. |
| Admin class selection page | Explicit selection gate before dashboard access | Allowed | Satisfies explicit switching. | Preserve as the only class-selection entrypoint for teacher runtime context. |
| Teacher onboarding/create-class gate | User-only onboarding or create-class page before any class exists | Allowed | The docs permit a user-only exception only for pre-class onboarding. | Keep fail-closed for all class-scoped actions until a class exists. |
| Runtime fallback to prior request state | Any helper that recovers class/seat from previous request/session state | Remove | Explicitly forbidden by scoped context, no phantom scope access, and explicit context switching. | Delete or rewrite to require canonical context input. |
| GET route writes | Any GET that mutates scope or repairs context | Remove | Violates GET purity. | Move mutation to command path or remove repair behavior. |
| Label-based control keys | `block`, `section`, `period` used as scope authority | Remove | Labels are metadata only and may not drive identity or routing. | Replace with canonical identifiers or derived display-only labels. |
| Participant URL resolution | `seats.public_id` under active `class_id` | Allowed | Matches the canonical public actor boundary. | Keep fail-closed on mismatch or missing scope. |
| Legacy actor/table bridges | `StudentTeacher`, `created_by_teacher_id`, `created_by_admin_id`, `student_id` authority use | Remove | Transitional residue may exist, but must not be used as runtime authority. | Delete from runtime logic; test-only compatibility must be isolated. |
| Canonical trace logging | `TLCP` correlation using canonical context | Allowed | Trace logging may use canonical request context. | Preserve fail-closed logging behavior, but do not invent authority from missing context. |

## Hard-Gate Rules

The following conditions fail the gate immediately:

1. Any request-time authority depends on session state instead of canonical context.
2. Any route reconstructs `class_id` or `seat_id` outside the canonical boundary.
3. Any GET route performs a write to repair or restore context.
4. Any label is used as an identity or scope key.
5. Any fallback recovers scope from an alternate seat, prior request, or hidden compatibility bridge.

## Evaluation Notes

- This matrix is evaluated as part of the canonical-auth runtime cutover.
- A `Rewrite` row is not merge-ready until the replacement path exists and the old path is removed from runtime authority.
- A `Remove` row is not merge-ready until the code path is deleted or hard-disabled.
- A `Remove` row blocks merge until it is eliminated.
- The matrix should be refreshed whenever a new runtime path touches `user_id`, `class_id`, `seat_id`, `join_code`, or scope restoration.

## References

- [`docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)
- [`docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`](../INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md)
- [`docs/INVARIANT/ARCHITECTURE/INV-ARC-001_SCOPED_REQUEST_CONTEXT.md`](../INVARIANT/ARCHITECTURE/INV-ARC-001_SCOPED_REQUEST_CONTEXT.md)
- [`docs/INVARIANT/ARCHITECTURE/INV-ARC-002_NO_IMPLICIT_GLOBAL_ACCESS.md`](../INVARIANT/ARCHITECTURE/INV-ARC-002_NO_IMPLICIT_GLOBAL_ACCESS.md)
- [`docs/INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`](../INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md)
- [`docs/INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md`](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md)
- [`docs/INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`](../INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md)
- [`docs/INVARIANT/ARCHITECTURE/INV-ARC-010_EXPLICIT_CONTEXT_SWITCHING.md`](../INVARIANT/ARCHITECTURE/INV-ARC-010_EXPLICIT_CONTEXT_SWITCHING.md)
- [`docs/INVARIANT/ARCHITECTURE/INV-ARC-011_NO_PHANTOM_SCOPE_ACCESS.md`](../INVARIANT/ARCHITECTURE/INV-ARC-011_NO_PHANTOM_SCOPE_ACCESS.md)
- [`docs/INVARIANT/ARCHITECTURE/INV-ARC-014_NO_LABEL_BASED_LOGIC.md`](../INVARIANT/ARCHITECTURE/INV-ARC-014_NO_LABEL_BASED_LOGIC.md)
- [`docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`](../INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md)

## Amendment

Any change to this matrix must:

1. preserve the hard-gate status,
2. keep `join_code` user-facing only,
3. keep canonical request context as the sole runtime authority source,
4. update the classification of any affected row from `Allowed` / `Rewrite` / `Remove`.
