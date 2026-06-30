# DOM-IDEN-005: Identity Binding and Lifecycle
| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-005   | 2.0     | 2026-06-29    | 1.1 | Constitutional   |

---
## I. Purpose

This document defines how Classroom Token Hub binds canonical identity objects into valid classroom participation and governs their lifecycle from provisioning through destruction.

This document governs the constitutional lifecycle of identity after identity information has been consumed.

This document SHALL NOT prescribe how identity information is obtained. Teacher self-registration, roster uploads, district identity providers, SSO, SIS synchronization, or any future provisioning mechanism are implementation concerns. Regardless of origin, all provisioning workflows SHALL converge to the canonical identity model defined by **DOM-IDEN-001** before the lifecycle defined in this document applies.

## II. Scope
This domain governs:
* Identity lifecycle
* Identity participation
* Identity binding
* Identity recovery
* Identity destruction
* Teacher participation lifecycle
* Student participation lifecycle

This domain does **not** govern:
- Human identity (`users`)
- Classroom universes (`classes`)
- Classroom participation (`seats`)
- Human-facing identity (`identity_profiles`)
- All business logics

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000`, `INV-CORE-001`, and `INV-ARC-008`.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`

## V. Membership by Existence
Classroom Token Hub manages multitenancy by strictly isolating each classroom economy instance by `Class`. A `User` SHALL occupy at most one `Seat` within a single `Class`. When a `class` is destroyed, all records scoped to it are also destroyed, including any orphaned `users`. A `User` that exists without a valid `seat` assigned is an invariant violation.

The **Membership-by-Existence** principle can be summarized as:
1. The existence of `class` and therefore `class_id` signifies that a particular economic universe exists.
2. The existence of `seat` within the scope of a `class` signifies that a particular actor exists.
3. The existence of `user` signifies that a particular `seat` exists and has been successfully bound to an authenticated participant.
4. The removal of a `class` signifies the destruction of `class_id`
5. The destruction of `class_id` signifies the destruction of all records scoped to that `class_id` including `seats`
6. The destruction of a `seat` signifies the destruction of `user` if there are no other `class_ids` that `user` is part of

Existence within Classroom Token Hub is binary. An identity either exists as an active participant or it does not exist. Intermediate states, soft deletes, archived identities, historical shadows, or dormant participants are constitutionally prohibited. Destruction of a `class` or `user` SHALL mean complete destruction.

# VI. Teacher Identity Lifecycle

Teacher participation SHALL originate through lawful teacher provisioning. A lawful teacher lifecycle SHALL satisfy the following sequence:

1. Provision a canonical `User`
2. Provision an initial `Class`.
3. Provision one administrative `Seat`.
4. Bind the administrative `Seat` to the newly provisioned `User`.
5. Initialize the active class and seat pointers.
6. Permit runtime participation through DOM-IDEN-006.

> [!CAUTION]
>
> A teacher User SHALL NOT exist without at least one administrative Seat. Failure to successfully provision the initial Class SHALL invalidate the entire teacher provisioning transaction. The transaction SHALL be rolled back atomically, and no partially initialized User SHALL remain.

Creation of additional classrooms SHALL provision additional administrative Seats bound to the same `User`. Creation of additional classrooms SHALL occur outside an existing class scope and SHALL provision an additional administrative Seat bound to the same User.

Removal of the final classroom SHALL result in destruction of the final administrative `Seat`.

If no remaining Seats exist, the corresponding `User` SHALL be destroyed. 

> [!WARNING]
>
> This must be gated behind the timed, multilayer deletion workflow to prevent accidental deletion. User must be informed of the consequences prior to performing deletion.

Teachers SHALL follow the same identity lifecycle and Membership-by-Existence laws as every other participant. No constitutional exceptions exist for teacher identities.

---

# VII. Student Identity Lifecycle

Student participation originates through classroom provisioning.

Roster provisioning SHALL create classroom participation opportunities rather than authenticated principals.

Roster provisioning SHALL:

- provision a `Seat`;
- provision an `IdentityProfile`;
- provision claim artifacts.

Roster provisioning SHALL NOT:

- provision authentication credentials;
- activate runtime participation;
- construct authenticated principals.

Student participation SHALL become active through either unauthenticated claim or authenticated class binding. Both workflows SHALL terminate in a lawful Seat-to-User binding.

> [!IMPORTANT]
>
> Classroom Token Hub does not infer identity by design. Identity resolution is scoped to a specific Class, and unauthenticated claim SHALL NOT search for or infer existing User identities outside the current claim transaction. If a human entity with existing `user` row used an unauthenticated claim path to claim a new seat, the workflow SHALL provision a new User because no authenticated principal exists and the system SHALL NOT infer or merge existing identities.

Following successful binding:

- a canonical User exists or has been reused;
- the `Seat` becomes bound;
- runtime participation becomes lawful.

Students may participate in multiple Classes through multiple Seats.

Removal of the final Seat SHALL destroy the corresponding `User`.

---

# VIII. Identity Binding

Identity binding is the constitutional act of associating one authenticated `User` with one previously unclaimed `Seat`.

Binding SHALL satisfy the following invariants:

- One `Seat` SHALL bind to exactly one `User`.
- One `User` MAY bind to multiple `Seats`.
- One `User` SHALL own at most one `Seat` within the same `Class`.
- Binding SHALL occur atomically.
- Binding SHALL preserve referential integrity.
- Binding SHALL NOT migrate between Users.

Successful binding establishes lawful classroom participation.

Binding SHALL be the sole constitutional mechanism through which a `User` acquires classroom participation.

---

# IX. Identity Recovery

Identity recovery restores authentication capability without altering participation.

Recovery MAY:

- restore credentials;
- restore authentication capability.

Recovery SHALL NOT:

- create Users;
- destroy Users;
- create Seats;
- destroy Seats;
- modify participation;
- modify ownership;
- modify identity bindings.

Recovery preserves identity.

Recovery never reconstructs identity.

---

# X. Cross-Domain Authority

Canonical identity objects are governed exclusively by **DOM-IDEN-001**.

Runtime identity construction is governed exclusively by **DOM-IDEN-006**.

Business domains SHALL consume canonical identity but SHALL NOT construct, bind, or destroy canonical identities.

Provisioning workflows SHALL terminate in the canonical identity model before runtime participation becomes lawful.

---

# XI. Amendment

Revisions to this document SHALL:

1. Increment the version.
2. Update the effective date.
3. Maintain consistency with INV-CORE-000.
4. Maintain consistency with DOM-IDEN-001.
5. Maintain consistency with DOM-IDEN-006.