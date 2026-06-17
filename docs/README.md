# Classroom Token Hub — Documentation Index

This directory contains the canonical v2 documentation for the Classroom Token Hub, organized by namespace per [SOP-DOC-000](STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md).

---

## Document Tier Classification

All documents are classified into one of three tiers. See [SOP-DOC-000 Section V](STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md) for full definitions.

| Tier               | Authority                              | Namespaces / Locations                        |
|--------------------|----------------------------------------|-----------------------------------------------|
| **Constitutional** | Inviolable — cannot be overridden      | `INV-CORE-*`, `INV-ARC-*`                    |
| **Normative**      | Binding — must be followed             | `ARC`, `DOM`, `FEAT`, `REF`, `SOP`, `.claude/rules/`, `SEC-CONT-*` |
| **Informative**    | Descriptive — no normative authority   | `LOG`, `SEC-AUD/INC/VUL/THR-*`, root files   |

---

## Documentation Namespaces

### Constitutional & Normative (v2 canonical)

| Directory | Tier | Purpose |
|-----------|------|---------|
| **[INVARIANT/](INVARIANT/)** | Constitutional | Core invariants and architecture invariants |
| **[DOMAIN/](DOMAIN/)** | Normative | Per-domain authority specs and contracts |
| **[FEATURE-EXECUTION/](FEATURE-EXECUTION/)** | Normative | FEAT contracts for all state mutations |
| **[ARCHITECTURE/](ARCHITECTURE/)** | Normative | Cross-domain architectural rules and operational constraints |
| **[DOMAINS/](DOMAINS/)** | Normative | Domain-level design specs (economy, ledger) |
| **[FEATURES/](FEATURES/)** | Normative | Feature specifications (analytics, hall pass, rent, etc.) |
| **[MAP/](MAP/)** | Normative | Domain-to-FEAT capability maps and scope normalization |
| **[TESTING/](TESTING/)** | Normative | Test creation, validation, and accessibility compliance |
| **[STANDARD_OPERATING_PROCEDURES/](STANDARD_OPERATING_PROCEDURES/)** | Normative | SOPs for database, deployment, devops, documentation |
| **[SECURITY/](SECURITY/)** | Normative (CONT) / Informative | Security controls, audits, incidents, threat models |

### Reference

| Directory | Tier | Purpose |
|-----------|------|---------|
| **[REFERENCE/](REFERENCE/)** | Normative | Authoritative vocabulary and terminology (`REF-TERM-*`) |

### Planning & Status

| Directory | Tier | Purpose |
|-----------|------|---------|
| **[SPECS/](SPECS/)** | Normative | Target-state architecture specs (V2_*) |
| **[TRACKING/](TRACKING/)** | Informative | Migration progress, compliance validation, launch readiness |

### Historical

| Directory | Tier | Purpose |
|-----------|------|---------|
| **[LOGS/](LOGS/)** | Informative | Historical audit logs and release notes |
| **[archive/](archive/)** | Informative | v1 docs (user-guides, GitHub Pages assets, old dev artifacts) |

### Other

| Location | Tier | Purpose |
|----------|------|---------|
| `.claude/rules/` | Normative | AI agent operational rules |
| `self-hosting/` | Informative | Self-hosting deployment guide |
| Root files | Informative | Project orientation and contributor reference |

---

## Quick Links

- **[Core Invariants](INV-CORE-000_Core_Invariants.md)** — Constitutional constraints (Tier 1)
- **[Authority Model](INV-CORE-001_Authority_Model.md)** — INV → DOM → FEAT hierarchy
- **[Domain Authority Summary](DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md)** — Per-domain authority overview
- **[FEAT Constitutional Directive](FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md)** — FEAT execution rules
- **[Schema Ownership Index](ARCHITECTURE/OPERATIONS/ARC-OPS-016_Schema_Ownership_Index.md)** — Table-to-domain ownership map
- **[Cross-Domain Data Relationships](ARCHITECTURE/OPERATIONS/ARC-OPS-017_Cross_Domain_Data_Relationships.md)** — Shared reference fields across domains
- **[Documentation Standard](STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md)** — Tier classification, taxonomy, naming, authoring rules
- **[Documentation Index](STANDARD_OPERATING_PROCEDURES/SOP-DOC-002_DOCUMENTATION_INDEX.md)** — Complete list of tracked documents

---

## Archive

v1 user-facing documentation (teacher manual, student guide, diagnostics, feature guides) has been moved to `archive/v1-user-guides/` pending review for v2 port. GitHub Pages landing site assets are in `archive/github-pages/`.
