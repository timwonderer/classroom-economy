# ARC-CORE-000: Architecture Foundation

| Reference Number | Version | Effective Date | Supersedes | Authority Level  |
|------------------|---------|----------------|------------|------------------|
|ARC-CORE-000| 1.1 | 2026-03-08 | 1.0 |Constitutional|

---

## I. Purpose

This document defines the scope, structure, subdivisions, and authoring rules for the `ARCHITECTURE` namespace in the Classroom Token Hub documentation.

## II. Scope

The `ARCHITECTURE` namespace is strictly for architectural rules, mechanisms, and systems that span **multiple domains**. 

If a system, logic flow, or rule is isolated to a single functional area (e.g., only RENT or only BANK), it does not belong in ARCHITECTURE. It belongs in `DOMAINS`.

Examples of cross-domain architecture:
- Identity handling (used by authentication, roles, every domain route)
- Join-code scoping (used to isolate tenant boundaries globally)
- Ledger entry system (used by payroll, banking, rent, store, etc.)

## III. Authority Level

Constitutional (Tier 1). No other ARCHITECTURE document may override the rules defined herein, and other namespaces must conform to ARC. Subordinate only to `INV-CORE-000_CORE_INVARIANTS.md`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`

## V. Subdivisions

The `ARCHITECTURE` namespace is organized into the following subdivisions:

- `OPERATIONS/` (ARC-OPS-*): Application-level operational constraints, environments, and deployment architecture.
- `IDENTITY/` (ARC-IDEN-*): Cross-domain identity, roles, and authorization mechanisms.
- `SYSADMIN/` (ARC-SYS-*): Global administrative architecture spanning multiple boundaries.

## VI. Standard Document Template

All documents within the `ARCHITECTURE` namespace must follow the standard normative template defined in `SOP-DOC-000`:

1. **I. Purpose**
2. **II. Scope**
3. **III. Authority Level**
4. **IV. Dependencies**
5. **[V+] Content Sections**
6. **[Last] Amendment**

## VII. Amendment

Revisions to this document require explicit architectural deliberation, a version increment, an update to the Effective Date, and must maintain consistency with `INV-CORE-000`.
