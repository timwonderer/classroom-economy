# INV-ARC-018: PII Storage and Retention Enforcement

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-018      | 1.0     | 2026-06-13     | None       | Constitutional |

---

## I. Purpose

This document defines the architectural enforcement rules for storing, encoding, and retaining personally identifiable information (PII) at rest. It governs which storage forms are permitted, which columns must exist, and when PII must be destroyed.

INV-ARC-005 governs PII leakage in the execution layer (request context, logs, telemetry). This document governs PII in the persistence layer (database columns, caches, files).

---

## II. Scope

This document applies to:

- All database columns that store PII (names, display identity, claim verification artifacts)
- All domain services that read or write PII fields
- All FEAT executors that create, update, or delete records containing PII
- Schema migrations that add, rename, or remove PII columns
- Caching layers that may hold decrypted PII in memory

---

## III. Authority Level

Constitutional (Tier 1). This document derives from `INV-CORE-000` Section III.2, `Minimal Use and Storage of PII`, and is governed within the `INV` hierarchy described by `INV-CORE-001`. It is subordinate to those foundational invariants.

---

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-005_NO_PII_LEAKAGE_IN_EXECUTION_LAYER.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-019_IDENTITY_AND_OWNERSHIP_MODEL.md`

---

## V. Permitted Storage Forms

Every PII field at rest must use exactly one of two storage forms. No other form is permitted.

### 1. HMAC-Hashed (Lookup/Matching)

- Purpose: enable deterministic matching without exposing the original value.
- Implementation: keyed HMAC using the application's pepper/HMAC key.
- The original value MUST NOT be recoverable from the stored form.
- Use for: roster claim name-matching hashes on `seats`, username lookup hashes.

### 2. Symmetrically Encrypted (Recoverable Display)

- Purpose: store a value that must be decrypted for in-app display.
- Implementation: Fernet symmetric encryption using the application's encryption key.
- Plaintext MUST NOT be written to the database, even transiently.
- Use for: first name and last name in `identity_profiles`, any display-purpose PII.

### Dual-Column Rule

When a single PII value serves both lookup and display purposes, it MUST be stored in two separate columns — one hashed, one encrypted. A single column MUST NOT serve both purposes.

---

## VI. Permitted PII Fields

Only the following PII fields are permitted in the v2 schema. Any PII column not listed here requires an amendment to this document before it may be added.

| Field | Table | Storage Form | Purpose |
|-------|-------|-------------|---------|
| First name (encrypted) | `identity_profiles` | Encrypted | In-app display |
| Last name (encrypted) | `identity_profiles` | Encrypted | In-app display |
| First name hash | `seats` | HMAC-hashed | Roster claim verification |
| Last name hash | `seats` | HMAC-hashed | Roster claim verification |
| Username hash | `users` | HMAC-hashed | Login lookup |

---

## VII. Prohibited Storage Patterns

1. **Plaintext PII at rest** — no column, row, file, or cache entry may contain PII in plaintext form on disk or in the database.
2. **PII in non-governed columns** — PII must not appear in `description`, `notes`, `metadata`, JSON blobs, or any free-text column.
3. **PII in indexed plaintext** — database indexes must not expose plaintext PII. Indexes on hashed columns are permitted.
4. **PII in backup-only retention** — PII must not survive in database backups beyond the retention window of the owning record. Backup retention policy must align with class lifecycle deletion (INV-CORE-000 §III.5).
5. **Redundant PII** — the same PII value must not be stored in multiple tables unless each instance serves a distinct invariant-defined purpose with a distinct storage form.

---

## VIII. Retention and Deletion Rules

PII retention is governed by the lifecycle of its owning identity record:

1. **Seat deletion** — when a seat is deleted, all PII on that seat (claim hashes) and its associated `identity_profiles` row (encrypted names) MUST be deleted in the same transaction.
2. **User deletion** — when a user is deleted (no remaining seats in any class, per INV-CORE-000 §III.5), all PII on the `users` row (username hash) MUST be deleted.
3. **Class deletion** — class deletion cascades seat deletion, which cascades PII deletion per rule 1 above.
4. **No orphaned PII** — no PII column may reference a deleted seat, user, or class. Foreign key cascades or explicit FEAT-managed deletion must enforce this.

---

## IX. Domain Responsibilities

### Identity Domain (DOM-IDEN)

- Owns `identity_profiles` and the encrypted display-name columns.
- Owns the encryption/decryption boundary: decryption happens at read time within the identity service, not in templates or routes.
- Must not expose decrypted values beyond the service return boundary except as display-ready strings.

### Seat Claim (FEAT-IDEN-001)

- Owns the creation of HMAC-hashed claim verification columns on `seats`.
- Must hash incoming roster names at write time; plaintext must not persist beyond the FEAT transaction.

### Operations Domain (DOM-OPS)

- Audit records MUST NOT contain PII. Actor attribution in audit logs uses `seat_id` or `seats.public_id`, never names.

---

## X. Migration Requirements

Any migration that adds, renames, or removes a PII column must:

1. Identify the column as PII in the migration description.
2. Specify the storage form (encrypted or HMAC-hashed).
3. Include a data migration step if converting existing plaintext to an encoded form.
4. Verify that no plaintext residue remains after the migration completes.

---

## XI. Relationship to INV-ARC-005

INV-ARC-005 and INV-ARC-018 are complementary:

| Concern | Governing Document |
|---------|-------------------|
| PII in request context, logs, telemetry | INV-ARC-005 |
| PII in database columns, caches, files | INV-ARC-018 |
| PII in error messages, URLs, query params | Both (INV-ARC-005 at runtime, INV-ARC-018 at storage) |

Together they enforce INV-CORE-000 §III.2 across both the execution layer and the persistence layer.

---

## XII. Amendment

Revisions to this document must increment the version number, update the effective date, and remain consistent with INV-CORE-000 §III.2 and the foundational documentation standard (SOP-DOC-000).
