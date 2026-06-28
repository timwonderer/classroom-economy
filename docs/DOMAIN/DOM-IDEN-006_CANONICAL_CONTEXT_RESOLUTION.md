# DOM-IDEN-006: Canonical Context Resolution

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-IDEN-006 | 1.0     | 2026-06-28 | - | Constitutional |

## I. Purpose
This document defines the **Canonical Context Resolution** within Classroom Token Hub. It governs how the system determines the active class context for a given user, ensuring that all actions are performed within the correct classroom boundaries. It also defines how missing or malformed context is handled.

## II. Scope
This document applies to all codes that requires authenticated user context. All business logic and page load requests MUST validate and resolve a canonical class context. It serves as the authoritative reference for this critical cross-cutting capability.

This document is about how the backend constructs the canonicalContext object and how the program consumes the object. It does not govern user account lifecycle, authentication, or identity display aliases.

## III. Authority Level
Tier 1 - Constitutional. This document defines the sole valid method for constructing canonicalContext objects and when those objects are constructed and consumed. All other documents that reference canonicalContext objects MUST defer to this document. It is subordinate to `INV-CORE-000`, `INV-CORE-001`, and `INV-ARC-008`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`

## V. Schema Authority Declaration

Canonical Context Resolution SHALL NOT own or mutate any table. It scope is limited to how canonicalContext objects are constructed and consumed.

## VI. Owned Tables

Canonical Context Resolution are prohibited from owning any table.  