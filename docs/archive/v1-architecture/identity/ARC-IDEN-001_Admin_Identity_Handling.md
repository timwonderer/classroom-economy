# ARC-IDEN-001: Admin Identity Handling Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-IDEN-001     | 2.0     | 2026-04-12     | 1.2        | Constitutional  |

> [!CAUTION]
> **SUPERSEDED.** This document describes the v1 teacher identity model.
> For the v2 target model, see:
> `docs/SPECS/V2_TEACHER_IDENTITY_ARCHITECTURE.md`
> and `docs/DOMAIN/DOM-IDEN-001_IDENTITY_CLASS_BINDING_DOMAIN.md`.
> This document is retained for historical reference only.

## I. Purpose
Define the hardened v2 identity model for System Admins and Teachers (Admins), emphasizing the transition to a hash-only, privacy-preserving authentication architecture and the absolute removal of legacy plaintext identifiers.

## II. Scope
Applies to identity models, login properties, and public display identifiers for System Admins and Teachers.

## III. Authority Level
Constitutional (ARC Tier). Subordinate to INV-CORE-000.

## IV. Dependencies
- `INV-CORE-000_CORE_INVARIANTS.md`

## V. Canonical Identity Fields

Teacher/admin (`teachers`):
- `username_hash` - Hashed authentication username.
- `username_lookup_hash` - Deterministic lookup hash used for initial record identification during login/recovery.
- `salt` - Per-account salt for deterministic hashing operations.
- `teacher_public_id` - Canonical public teacher identifier (UUID).
- `public_id` - ORM synonym alias for `teacher_public_id`.
- `display_name` - Optional teacher-managed application label for student-facing UI.
- App-mapped `passkey_credentials` for WebAuthn support.

System admin (`system_admins`):
- `username_hash` - Hashed authentication username.
- `username_lookup_hash` - Deterministic lookup hash.
- Passkey (WebAuthn) support available for secure, passwordless authentication.

> [!IMPORTANT]
> **Purge Status**: The legacy `username` (plaintext) column has been physically removed from the `teachers` and `system_admins` tables. Any attempt to access this attribute at the ORM level will result in an `AttributeError`.

## VI. Identity Semantics

### Authentication Identity
- **Primary Auth**: Authentication relies exclusively on the correspondence between the incoming username lookup hash and the stored `username_lookup_hash`.
- **Credential Storage**: No plaintext or reversible representation of the username exists within the system.
- **WebAuthn Integration**: Passkeys are the preferred high-security authentication mechanism, leveraging public-key cryptography to bypass shared-secret vulnerabilities.

### Public Teacher Identity
- `teacher_public_id` is the **only** canonical public teacher identifier. 
- Public-facing flows (e.g., student join, hall-pass verification) must use the `public_id` UUID. 
- Internal integer IDs are restricted to database-layer join operations and must not be exposed to endpoints.

### Display Identity
- Student-facing views must prioritize `display_name`.
- If `display_name` is absent, the application must fall back to `teacher_public_id` / `public_id`.
- Authentication identifiers (hashes) must never be used for display purposes.

## VII. v2 Identity Contract
- All authentication flows are "trapped" within the hash-only architecture.
- Public verification tokens and dynamic profile lookups rely on persistent UUIDs (`public_id`) rather than mutable usernames.

## VIII. Transitional Metadata (Hardened)
As of version 2.0, the following legacy attributes have been fully decommissioned and removed from the schema:
- Plaintext `username` fields.
- `hall_pass_verify_token` (superseded by UUID-based verification).
- Shadow-identity transition flags and original admin cross-references on student records.

## IX. Amendment
Revisions to this document require a version increment and must be consistent with the Foundational Invariants in `INV-CORE-000`.
