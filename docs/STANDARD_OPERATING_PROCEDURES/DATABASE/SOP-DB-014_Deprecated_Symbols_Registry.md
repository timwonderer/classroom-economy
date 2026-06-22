# SOP-DB-014: Deprecated Symbols Registry

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SOP-DB-014| 1.1 | 2026-03-08 | 1.0 |Normative|

## I. Purpose

Deprecated symbols represent schema or model elements that have entered the **Contract phase** of the Expand / Contract lifecycle.

Their presence in application code indicates:
- Hidden runtime coupling
- Incomplete schema contraction
- High risk of production regression

This registry exists to convert past incidents into permanent guardrails.

## II. Scope

Symbols that are explicitly prohibited from appearing in application code.

## III. Authority Level

Normative (SOP Tier). Subordinate to INV-CORE-000.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`

## V. Rules

- Symbols must be listed as **literal strings**, exactly as they would appear in code
- One symbol per line in `deprecated_symbols.txt`
- No regex, wildcards, or glob patterns
- Symbols may be removed **only after** full database contraction has been completed

## VI. Current Deprecated Symbols

| Symbol | Reason | Status |
|------|--------|--------|
| `teacher_id` | Legacy single-tenant coupling replaced by StudentTeacher association | Active |

## VII. Relationship to Schema Policy

This registry derives its authority from:

- **Schema Contraction & Destructive Migration Policy**
- **Schema Change Gate (PR-Blocking Checklist)**

Violation of this registry constitutes a schema gate failure.

## VIII. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
