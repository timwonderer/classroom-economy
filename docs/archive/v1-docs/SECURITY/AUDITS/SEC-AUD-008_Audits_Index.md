# Audit Reports Directory

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
|SEC-AUD-008| 1.1 | 2026-03-08 | 1.0 |Normative|

This directory contains all formal audit reports for the Classroom Economy codebase.

Audits are structured, read-only reviews of the system intended to identify risks, architectural weaknesses, economic invariant violations, and technical debt. Audit PRs must use the `audit` label and follow the governance rules enforced by CI.

---

## Purpose of Audits

Audits are designed to:

- Detect structural or logical risks before they become production issues
- Protect financial invariants and ledger integrity
- Identify high-risk schema or migration patterns
- Surface security boundary concerns
- Highlight fragile or under-tested logic
- Document system state at specific points in time

Audits are observational. They do not modify source code.

---

## Audit Stages

Each audit report must clearly indicate which stage it represents:

1. **Stage 1 – Static Structural Audit**  
   Code structure, complexity, dead code, and maintainability analysis.

2. **Stage 2 – Economic Invariant Risk Audit**  
   Ledger integrity, financial mutation risks, precision issues, and transactional safety.

3. **Stage 3 – Security & Boundary Scan**  
   Authentication, authorization, multi-tenant boundaries, and injection surfaces.

4. **Stage 4 – Test Coverage & Fragility Audit**  
   Coverage gaps, brittle tests, state bleed, and invariant protection.

5. **Stage 5 – Refactor Proposal (Plan Only)**  
   Structured refactor plan derived from prior audit findings.

---

## Naming Convention

Audit files should follow this format:

```
YYYY-MM-DD_stage-<number>_<short-description>.md
```

Examples:

- `2026-02-15_stage-1_static-structure.md`
- `2026-02-15_stage-2_economic-invariants.md`

This ensures chronological traceability and consistent organization.

---

## Governance Rules

All audit PRs must:

- Use the `audit` label (lowercase)
- Modify documentation only (i.e., no changes to source code, migrations, or schema files)
- Include at least one new or modified file under `docs/audits/`

CI will enforce these rules automatically.

---

## Historical Record

Audit reports serve as institutional memory. They document architectural state and risk posture over time. Reports should not be rewritten after merge. If new findings arise, create a new audit report.

Append-only documentation is preferred.
