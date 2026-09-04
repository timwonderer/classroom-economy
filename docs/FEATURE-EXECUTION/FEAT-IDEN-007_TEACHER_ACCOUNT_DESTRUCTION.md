# FEAT-IDEN-007 — Teacher Account Destruction

## Contract

Terminal destruction of a teacher principal. The command destroys the `users`
row together with everything that principal owns: every class universe it holds
(`ClassEconomy` and all class-scoped records), the teacher-scoped settings,
activity, audit, rent, insurance, issue, store, and recovery/credential rows,
and any student seats left orphaned by those class teardowns.

Blast radius: **HIGH**. The operation is irreversible and removes otherwise
immutable economic history, which is lawful only under the terminal-destruction
lifecycle exception (INV-CORE-000 §III.5). The class-scope teardown sets
`cth.class_universe_destroying` for exactly that reason.

The command requires a canonical context and explicit `correlation_id` /
`idempotency_key` metadata. The principal destroyed is `canonical_context.user_id`
and nothing else.

## Authority resolution

Deletion authority comes from the canonical context alone (INV-CORE-000 §III.4).
No display name, username, join code, public identifier, or any other
form-supplied value participates in resolving the destruction target. Display
values reaching this surface exist only to render the human-readable
confirmation phrase; they never select, switch, or authorize a target.

## Composition

One FEAT executes per request (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2). This FEAT
therefore composes **domain commands**, never other FEATs:

- per-class teardown calls the plain `_destroy_class_scope_rows` command, not the
  `FEAT-CLASS-001` wrapper `_hard_delete_class_scope`;
- account-level teardown calls the `_delete_teacher_*` commands and
  `delete_admin_account_rows` directly.

A single envelope covers the whole sequence, which is what makes account
destruction atomic: a failure anywhere — including inside a class teardown —
rolls back the entire account deletion rather than leaving a half-destroyed
principal.

`FEAT-CLASS-001` remains the entry point for destroying **one** class while the
owning account survives (`POST /admin/join-code/delete`). The two entry points
are not interchangeable; a caller already holding a context must use the domain
command.

## Boundary

Routes own the destruction gate (30-second countdown, exact typed phrase,
10-second press-and-hold) and the confirmation presentation. They must not
delete identity or class rows inline. Post-destruction session teardown and the
clearing of canonical pointers (`User.last_active_class_id` /
`last_active_seat_id`, INV-ARC-012 §V) are route concerns for the surviving
actor; a destroyed principal has no pointers left to clear.

Authority: INV-CORE-000 §III.4, §III.5; INV-ARC-012 §V; INV-ARC-021 §V.2;
DOM-IDEN-001.
