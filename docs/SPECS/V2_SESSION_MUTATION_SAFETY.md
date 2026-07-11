# V2 Session Mutation Safety

**Status:** Draft target-state policy

## Purpose

This document defines session invalidation and mutation-safety behavior for v2.

It exists to answer questions that do not belong in the identity model itself:

- what happens when a session expires
- what happens when a newer login replaces an older one
- how stale tabs behave
- whether a rejected mutation may be retried automatically after reauth

## Core Policy

CTH supports one active session per user identity.

A new successful sign-in replaces the prior active session for that user.

Session validity is enforced at the request boundary before any authenticated business
logic or mutation runs.

## Session Model

The current target model uses session authority stored on `users`:

- `current_session_started_at`
- `current_session_expires_at`
- `current_session_nonce`

Rules:

- `current_session_started_at` is written at sign-in.
- `current_session_expires_at` is written once at sign-in as 10 minutes after session
  start.
- `current_session_nonce` is regenerated at sign-in.
- These values do not slide forward on activity.
- A new sign-in replaces all three values.

## Session Context

The Flask session may carry:

- `user_id` — canonical authenticated principal
- `current_class_id` / `current_join_code` — active class context mirrors
- `current_seat_id` — class-local actor context where available

Only `user_id` authenticates the principal. Role-specific IDs may be used to load
existing templates or route helpers only during transitional compatibility work, but
they must be resolved from the canonical user and must not drive credential
verification, recovery authority, class scope, or money-affecting authorization.

Credential verification must read from `users`:

- teacher/sysadmin username and TOTP
- student username and PIN
- student passphrase gates
- user-owned passkey metadata

Any route that accepts a non-canonical session key without resolving the canonical
`users.id` first is not an acceptable v2 authority pattern.

## Request Validation Rule

Every authenticated request must validate session authority before performing any
protected read or write.

Validation checks:

1. request session nonce matches `users.current_session_nonce`
2. current time is before `users.current_session_expires_at`

If either check fails:

- the request is rejected immediately
- no mutation is committed
- the session is treated as expired or replaced

## Stale Tab Behavior

A stale browser tab may continue to look logged in until it makes another request.

That is acceptable.

The browser UI is not the authority. The server-side session validation check is the
authority.

So if a user:

1. signs in on Device A
2. signs in later on Device B
3. returns to the still-open page on Device A

then Device A must fail on its next authenticated request because its nonce is stale.

## Mutation Safety Rule

Rejected mutation requests must die completely.

If a mutation request is rejected due to session expiry or session replacement:

- no business mutation may be applied
- no partial side effect may be committed
- no hidden retry may occur server-side
- no automatic replay may occur after reauth

This is especially strict for money-affecting actions.

Examples:

- pay rent
- transfer funds
- purchase item
- approve insurance claim
- void transaction

## Reauthentication Rule

After session expiry or session replacement:

- the user may be redirected to sign-in
- after successful sign-in, the app returns to a safe page or safe state
- the user must explicitly re-initiate any prior mutation

The application must not automatically resubmit a previously rejected POST, PATCH,
PUT, or DELETE request after reauth.

## Retry Policy

Allowed after reauth:

- reload page state
- reload safe GET requests
- restore non-authoritative UI context if useful

Not allowed after reauth:

- silent replay of a financial mutation
- automatic form submission of a previously rejected action
- resuming a partially processed money action from browser memory alone

## Financial Action Standard

For money-affecting actions, the safe default is:

1. validate session authority
2. validate action authority
3. execute mutation once
4. require explicit user intent for any later retry

Financial actions should also use idempotency or duplicate-submission protection where
appropriate, but idempotency does not justify automatic replay after forced reauth.

Idempotency protects against duplicate submission.
It does not authorize hidden resubmission.

## Why This Policy Exists

This policy is intentionally strict because the product does not need concurrent session
management complexity.

The chosen design optimizes for:

- clear single source of truth
- deterministic invalidation behavior
- fewer session edge cases
- safer mutation handling
- easier debugging of stale-session failures

If concurrent sessions are not a product feature, the system should not behave as if
they are.

## Relationship To Other Docs

- `docs/SPECS/V2_STUDENT_IDENTITY_ARCHITECTURE.md` defines who `users`, `seats`, and `classes` are.
- `docs/SPECS/V2_AUTHORITY_EXTRACTION_PLAN.md` defines where mutation and authority logic belongs.
- This document defines what must happen when session validity and mutation safety meet
  at request time.
