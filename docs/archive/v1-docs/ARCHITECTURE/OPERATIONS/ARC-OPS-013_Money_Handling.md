# ARC-OPS-013: Money Handling

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| ARC-OPS-013      | 2.0     | 2026-06-21     | 1.0 (stub) | Consolidated    |

## Status: Consolidated

This document was an incomplete stub (Purpose and Scope marked TBD). Its money handling rules — Decimal arithmetic, integer-cents storage, serialization boundaries — are fully covered by:

- **[DOM-ECON-003: Ledger Integrity and Determinism](../../DOMAINS/ECONOMY_DESIGN/DOM-ECON-003_Ledger_Integrity_and_Determinism.md)** — Section V (Integer Cents), canonical authority for money representation and arithmetic
- **[FEAT-LED-001: Post Ledger Transaction](../../../../FEATURE-EXECUTION/FEAT-LED-001_POST_LEDGER_TRANSACTION.md)** — `amount_cents` contract and serialization boundaries

All money handling rules are now governed by DOM-ECON-003. This file is retained as a redirect to preserve references from other documents.
