# DOM-IDEN-006: Canonical Context Resolution

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-006 | 1.0     | 2026-06-28 | - | Constitutional |

## I. Purpose
This document defines the **Canonical Context Resolution** within Classroom Token Hub. It governs how the system determines the active class context for a given user, ensuring that all actions are performed within the correct classroom boundaries. It also defines how missing or malformed context is handled.

## II. Scope
This document applies to all code that requires authenticated runtime context. All business logic and page-load requests MUST validate and resolve a canonical class context before performing class-scoped reads or writes. It serves as the authoritative reference for this critical cross-cutting capability.

This document is about how the backend constructs the canonicalContext object and how the program consumes the object. It does not govern user account lifecycle, authentication, or identity display aliases.

## III. Authority Level
Tier 1 - Constitutional. This document defines the sole valid method for constructing canonicalContext objects and when those objects are constructed and consumed. All other documents that reference canonicalContext objects MUST defer to this document. It is subordinate to `INV-CORE-000`, `INV-CORE-001`, and `INV-ARC-008`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`

## V. Schema Authority Declaration

Canonical Context Resolution SHALL NOT own or mutate any table. Its scope is limited to how `canonicalContext` objects are constructed and consumed.

## VI. Owned Tables

Canonical Context Resolution is prohibited from owning any table.

## VII. Canonical Context Object

A `canonicalContext` object is the sole runtime authority for authenticated class-scoped execution.

A valid `canonicalContext` object MUST contain:

- `user_id`: the authenticated `users.id` principal.
- `class_id`: the active `class_economies.id` universe.
- `seat_id`: the active `seats.id` actor within the active class universe.
- `actor_role`: the resolved authority role for the selected seat in the selected class.

`canonicalContext` is request-scoped. It SHALL be constructed once at the authenticated request boundary and then passed downward to business logic, route helpers, services, and policy checks.

No downstream code may reconstruct, infer, mutate, or re-resolve `canonicalContext`.

## VIII. Resolution Algorithm

The backend SHALL construct `canonicalContext` using the following algorithm and no other algorithm.

1. Read the authenticated `user_id` from the authenticated user session.
2. Read `last_active_class_id` for the authenticated user.
3. If `last_active_class_id` is missing, route the user to the class-selection screen. No class-scoped business logic may run.
4. Use `last_active_class_id` as the candidate `class_id`.
5. Scope all seat resolution to the candidate `class_id`.
6. Read `last_active_seat_id` for the authenticated user.
7. If `last_active_seat_id` is missing, query `seats` within the candidate `class_id` where `seats.user_id == users.id`.
8. If no matching seat exists, fail closed.
9. If exactly one matching seat exists, use that seat as the candidate `seat_id`.
10. If more than one matching seat exists within the same class scope, fail closed unless an authoritative class-selection or seat-selection boundary resolves the ambiguity.
11. If `last_active_seat_id` is present, verify that the referenced seat belongs to the candidate `class_id`.
12. If the referenced seat is outside the candidate `class_id`, fail closed.
13. Verify that the selected seat's `user_id` equals the authenticated `users.id`.
14. If the selected seat's `user_id` does not equal the authenticated `users.id`, fail closed.
15. Read the actor role from the selected seat and class-scoped authority rules.
16. Construct the `canonicalContext` object containing `user_id`, `class_id`, `seat_id`, and `actor_role`.
17. Attach the constructed `canonicalContext` to the request boundary for downstream consumption.

The resolver SHALL NOT use `join_code` as runtime authority. `join_code` may only be used at explicit boundary-ingress workflows that resolve a class before authenticated class-scoped runtime begins.

## IX. Boundary Rules

`canonicalContext` resolution is a boundary concern.

The system SHALL:

- construct `canonicalContext` exactly once per authenticated request;
- construct `canonicalContext` only through the canonical context resolver;
- fail closed when class, seat, user, or role validation fails;
- treat missing active class context as a class-selection requirement, not as authorization to guess or infer context;
- treat missing or mismatched seat context as an authorization failure unless an explicit selection boundary resolves it.

The system SHALL NOT:

- construct identity from downstream route logic;
- re-resolve context inside helper functions;
- derive runtime authority from `join_code`;
- derive runtime authority from URL parameters;
- derive runtime authority from request payload fields;
- derive runtime authority from legacy identity tables;
- trust `last_active_seat_id` without checking that it belongs to `last_active_class_id`;
- trust `last_active_seat_id` without checking that the seat belongs to the authenticated `user_id`.

## X. Consumption Rules

All class-scoped business logic SHALL consume `canonicalContext` as an explicit input.

Helpers, services, and policy checks that require class-scoped authority SHALL accept `canonicalContext` or the specific fields derived from it. They SHALL NOT call the canonical context resolver themselves.

A function below the request boundary that needs class context MUST receive one of the following from its caller:

- the full `canonicalContext` object; or
- an explicit `class_id`, `seat_id`, and `user_id` derived from `canonicalContext`.

No function below the request boundary may perform independent session reads to determine class, seat, user, or role authority.

## XI. Failure Semantics

Canonical context resolution MUST fail closed.

The resolver SHALL NOT silently repair, infer, or switch context when validation fails.

The following conditions MUST fail closed:

- authenticated `user_id` is missing;
- `last_active_class_id` references a deleted or inaccessible class;
- `last_active_seat_id` references a deleted seat;
- `last_active_seat_id` references a seat outside `last_active_class_id`;
- `last_active_seat_id` references a seat whose `user_id` does not match the authenticated `users.id`;
- no seat exists for the authenticated user in the selected class;
- multiple candidate seats exist and no explicit boundary selection resolves the ambiguity;
- actor role cannot be resolved.

Missing `last_active_class_id` is not a failure condition by itself. It requires routing to class selection before class-scoped runtime proceeds.

## XII. Explicit Prohibitions

The following patterns are prohibited in authenticated runtime code:

- helper-level calls to the canonical context resolver;
- direct session reads for class, seat, or role authority below the request boundary;
- runtime authorization using `join_code`;
- runtime authorization using legacy identifiers such as `admin_id`, `student_id`, or `sysadmin_id`;
- runtime identity construction from legacy tables;
- alternate constructors for `canonicalContext`;
- compatibility bridges that reconstruct context from non-canonical state.

## XIII. Relationship to Identity Lifecycle

This document governs runtime context resolution only.

It does not govern roster provisioning, account claim, credential setup, account recovery, identity display, or class binding lifecycle. Those workflows are governed by the Identity domain documents.

Identity lifecycle documents may define how `last_active_class_id` and `last_active_seat_id` are initialized or updated. However, once an authenticated request begins, this document is the sole authority for resolving and validating runtime class context.

## XIV. Amendment

Revisions to this document must:

1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000` and `INV-CORE-001`.
4. Maintain consistency with `INV-ARC-008` for identity resolution and seat scope.
5. Preserve the rule that `canonicalContext` is resolved exactly once at the authenticated request boundary and consumed downstream without re-resolution.