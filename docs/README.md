# Classroom Token Hub — Documentation Index

This directory contains the canonical v2 documentation for the Classroom Token Hub, organized by namespace per [SOP-DOC-000](STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md).

---

## Document Tier Classification

All documents are classified into one of three tiers. See [SOP-DOC-000 Section V](STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md) for full definitions.

| Tier               | Authority                              | Namespaces / Locations                        |
|--------------------|----------------------------------------|-----------------------------------------------|
| **Constitutional** | Inviolable — cannot be overridden      | `INV-CORE-*`, `INV-ARC-*`                    |
| **Normative**      | Binding — must be followed             | `DOM`, `FEAT`, `REF`, `SOP`, `.claude/rules/`, `SEC-CONT-*` |
| **Informative**    | Descriptive — no normative authority   | `LOG`, `SEC-AUD/INC/VUL/THR-*`, root files   |

---

## Documentation Namespaces

### Constitutional & Normative (v2 canonical)

| Directory | Tier | Purpose |
|-----------|------|---------|
| **[INVARIANT/](INVARIANT/)** | Constitutional | Core invariants and architecture invariants |
| **[DOMAIN/](DOMAIN/)** | Normative | Per-domain authority specs and contracts |
| **[FEATURE-EXECUTION/](FEATURE-EXECUTION/)** | Normative | FEAT contracts for all state mutations |
| **[MAP/](MAP/)** | Normative | Domain-to-FEAT capability maps and scope normalization |
| **[TESTING/](TESTING/)** | Normative | Test creation, validation, and accessibility compliance |
| **[STANDARD_OPERATING_PROCEDURES/](STANDARD_OPERATING_PROCEDURES/)** | Normative | SOPs for database, deployment, devops, documentation |
| **[SECURITY/](SECURITY/)** | Normative (CONT) / Informative | Security controls, audits, incidents, threat models |

### Reference & Principles

| Directory | Tier | Purpose |
|-----------|------|---------|
| **[REFERENCE/](REFERENCE/)** | Normative | Authoritative vocabulary and terminology (`REF-TERM-*`) |
| **[PRINCIPLES/](PRINCIPLES/)** | Informative | Design principles (security, privacy, SSO rationale) |

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

- **[Core Invariants](INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)** — Canonical v2 core invariants
- **[Authority Model](INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md)** — Canonical capability-based authority hierarchy
- **[Domain Authority Summary](DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md)** — Per-domain authority overview
- **[FEAT Constitutional Directive](FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md)** — FEAT execution rules
- **[Canonical Schema Definition](DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md)** — Runtime schema, table ownership, and structural constraints
- **[Class Scope Normalization](MAP/MAP-CLASS-002_CLASS_SCOPE_NORMALIZATION_TARGET.md)** — Long-term class_id scoping model
- **[Documentation Standard](STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md)** — Tier classification, taxonomy, naming, authoring rules
- **[Documentation Index](STANDARD_OPERATING_PROCEDURES/SOP-DOC-002_DOCUMENTATION_INDEX.md)** — Complete list of tracked documents

---

## Archive

The `archive/` directory contains genuinely superseded v1 documentation:

| Directory | Contents |
|-----------|----------|
| `archive/v1-user-guides/` | v1 teacher manual, student guide, diagnostics, feature guides (pending v2 port) |
| `archive/v1-architecture/` | Early v1 identity and core architectural specs |
| `archive/v1-development/` | v1→v2 migration planning and legacy schema analysis |
| `archive/v1-docs/` | v1 security audits, deployment SOPs, ARC-* specs, FEATURES/*, DOMAINS/* (~55 files) |
| `archive/github-pages/` | GitHub Pages landing site assets |

> **Note (2026-06-21):** Documentation reorganized. v1 namespace directories (`ARCHITECTURE/`, `FEATURES/`, `DOMAINS/`) archived — their content is covered by v2 namespaces (`INVARIANT/ARCHITECTURE/`, `FEATURE-EXECUTION/`, `DOMAIN/`). v2 docs previously misplaced in the archive were restored to canonical namespaces.
>
> **Known content gaps:** None. Cross-domain reference semantics (formerly ARC-OPS-017) is now covered by `INV-ARC-021`. Sysadmin interface does not require a standalone spec — it follows from DOM authority and FEAT contracts like other interfaces.
