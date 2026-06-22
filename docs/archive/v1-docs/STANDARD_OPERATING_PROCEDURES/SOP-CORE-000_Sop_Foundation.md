# SOP-CORE-000: Standard Operating Procedures Foundation

| Reference Number | Version | Effective Date | Supersedes | Authority Level  |
|------------------|---------|----------------|------------|------------------|
|SOP-CORE-000| 1.1 | 2026-03-08 | 1.0 |Constitutional|

---

## I. Purpose

This document defines the scope, structure, subdivisions, and authoring rules for the `STANDARD_OPERATING_PROCEDURES` namespace in the Classroom Token Hub documentation.

## II. Scope

The `STANDARD_OPERATING_PROCEDURES` (SOP) namespace governs **human procedures** and governance outside of application runtime behavior. It dictates how developers, administrators, and contributors interact with the repository, deployments, and databases.

SOP documents are binding rules for humans, not for application code.

## III. Authority Level

Constitutional (Tier 1) within the context of human procedure, but explicitly subordinate to `INV-CORE-000` and `ARC/DOM` structures. SOP documents cannot dictate architectural behavior.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`

## V. Subdivisions

The `STANDARD_OPERATING_PROCEDURES` namespace is organized into the following subdivisions:

- `DOCUMENTATION/` (SOP-DOC-*): Rules for writing, structuring, and maintaining documentation.
- `DEPLOYMENT/` (SOP-DEP-*): Procedures for releasing code, scaling environments, and managing hosting.
- `DATABASE/` (SOP-DB-*): Procedures for running migrations, backfilling data, and managing state.
- `WORKFLOW/` (SOP-WORK-*): CI/CD procedures, Git discipline, and PR guidelines.

## VI. Standard Document Template

All documents within the `STANDARD_OPERATING_PROCEDURES` namespace must follow the standard normative template defined in `SOP-DOC-000`:

1. **I. Purpose**
2. **II. Scope**
3. **III. Authority Level**
4. **IV. Dependencies**
5. **[V+] Content Sections**
6. **[Last] Amendment** (Must specify procedure for altering the SOP)

## VII. Amendment

Revisions to this document require a version increment, an update to the Effective Date, and must maintain consistency with `INV-CORE-000`.
