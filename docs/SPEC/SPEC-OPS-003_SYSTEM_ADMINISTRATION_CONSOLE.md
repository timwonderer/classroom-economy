# SPEC-OPS-003: System Administration Console

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-OPS-003 | 1.0 | 2026-09-04 | — | Normative |

## I. Purpose

Define the operator-facing surface of the System Administration Console: which capabilities it exposes, what each capability may read or mutate, and the boundary between platform operation and classroom domain truth.

This specification is developer and operator documentation. The console is not a user-facing product surface and is deliberately excluded from the user guide corpus (see §IX).

## II. Scope

Governs the `sysadmin` blueprint (`/sysadmin`) and its rendered pages. It does not govern teacher or student surfaces, and it does not define health evaluation, incident lifecycle, or audit lineage — those belong to `DOM-OPS-001` and `DOM-OPS-002`.

## III. Authority Level

Normative (SPEC Tier). Subordinate to `INV-CORE-000`, `INV-ARC-004`, `INV-ARC-007`, `INV-ARC-009`, and `DOM-OPS-001`.

## IV. Dependencies

- `docs/DOMAIN/DOM-OPS-001_OPERATIONS_DOMAIN.md`
- `docs/DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-004_CROSS_TENANT_ISOLATION.md`
- `docs/SPEC/SPEC-OPS-001_REVERSAL_AND_VOID.md`

## V. Access Control

Every console route is gated by `system_admin_required`. Sysadmin authentication is independent of teacher and student authentication and grants no classroom authority: a sysadmin session is not a teacher session and cannot act inside a class.

Authentication factors supported by the console:

- password with TOTP second factor;
- passkey (WebAuthn) registration and assertion.

Passkey self-service lives at `/sysadmin/passkey/settings`. Registration, listing, and deletion act only on the authenticated sysadmin's own credentials. The console exposes no surface for creating, deleting, or resetting the credentials of another operator; that provisioning is out-of-band.

## VI. Console Surface

### 6.1 Navigation

The console navigation exposes exactly four destinations plus sign-out:

| Destination | Route | Purpose |
| --- | --- | --- |
| Dashboard | `/sysadmin/dashboard` | Platform-wide counts and recent error events |
| Support | `/sysadmin/support` | Teacher issues and developer-escalated issues |
| Logs | `/sysadmin/combined-logs` | Error events and network activity |
| Passkeys | `/sysadmin/passkey/settings` | The operator's own WebAuthn credentials |

Routes outside this set are reachable by direct URL only and MUST NOT be treated as supported operator surfaces.

### 6.2 Dashboard

A pure read (`INV-ARC-007`). It reports:

- teacher account count, seat count with student role, and sysadmin count;
- open ticket count, defined as new/teacher-review issues plus issues escalated to developer review;
- the five most recent error events;
- the sysadmin roster, rendered as display view objects rather than raw models.

The dashboard is display-only. It exposes no account administration action.

### 6.3 Support

Two tabs over the single `Issue` record type:

- **Teacher issues** — issues of type `general`, filterable by status. Status counts are aggregated per status.
- **Escalated issues** — issues in a developer-review state, partitioned into pending, in review, and resolved.

Issues are addressed by opaque reference, never by primary key, in both URLs and templates. Detail, start-review, and resolve actions operate on a single issue resolved from that reference.

Issue records carry `actor_public_id` and `class_public_id`. The console reads across tenants by design — it is the one surface exempt from class scoping — and therefore MUST NOT surface identifying student or teacher data beyond those opaque references.

### 6.4 Logs

`/sysadmin/combined-logs` is the supported log surface, with error events and network activity as tabs over persisted records.

`/sysadmin/logs` reads the tail of the configured application log file (`LOG_FILE`, default `app.log`) and structures it for display. It is filesystem-dependent and therefore returns nothing meaningful on deployments without a local log file.

### 6.5 Grafana proxy

`/sysadmin/grafana/<path>` proxies an upstream Grafana instance behind sysadmin authentication. The proxy carries no CTH domain authority; it neither reads nor writes domain state.

### 6.6 Error-handler probes

`/sysadmin/test-errors/<code>` deliberately raises the named HTTP error to exercise error handlers. These are diagnostic probes, not operator features.

## VII. Mutation Boundary

The console MUST NOT mutate classroom domain truth. Specifically it does not create, modify, or delete:

- classes, class configuration, or economic policy versions;
- balances, transactions, or any ledger record;
- obligations, entitlements, attendance facts, or store catalog entries;
- teacher or student accounts.

Permitted mutations are confined to Operations-owned records: issue status and reviewer annotation, and the operator's own passkey credentials.

Any capability that would reach into class state — deleting a class period, deleting a teacher account, adjusting a student balance, broadcasting to classroom dashboards — is outside this specification and MUST NOT be added to the console without a domain-owning FEAT and an amendment here.

## VIII. Known Non-Conformance

Recorded so implementers do not mistake these for intended behavior:

1. `/sysadmin/error-logs`, `/sysadmin/logs-testing`, and `/sysadmin/network-activity` render hardcoded empty result sets. They are superseded by `/sysadmin/combined-logs` and are candidates for removal.
2. `update_user_report` assigns issue status, reviewer notes, and review metadata directly on the model without routing through a FEAT and without an explicit commit, contrary to the mutation model in `CLAUDE.md` and `app/feats/base.py`.

## IX. Documentation Placement

The console is documented here, in the developer corpus under `/docs`, and not in `docs/user-guides/`.

Rationale: the user guide corpus is audience-isolated at the docs route — a reader in the `user` audience sees only `user-guides/`, and the `devops` audience sees everything except it. Operator documentation placed under `user-guides/` was reachable by neither audience in a useful way, and mixed platform operation into a corpus whose stated separation forbids internal implementation detail (`SOP-DOC-000`).

The prior guides at `docs/user-guides/features/sysadmin/` and `docs/user-guides/sysadmin_manual.md` are superseded by this specification.
