# SOP-DOC-000: Documentation Standard

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DOC-000      | 3.0     | 2026-06-08     | SOP-DOC-000 v2.0, SOP-DOC-003 v1.2, SOP-DOC-005 v2.1, SOP-DOC-006 v1.0 | Foundational |

---

## I. Purpose

This document defines the unified documentation standard, namespace taxonomy, repository organization, and authoring guidelines for the Classroom Token Hub repository under the V2 restructure architecture.

---

## II. Scope

This standard governs all documentation in the repository, including core invariants, architectural specifications, domain definitions, feature execution files, standard operating procedures, logs, user guides, and root repository files.

---

## III. Authority Level

Foundational (Tier 0). Subordinate only to `INV-CORE-000` and `INV-CORE-001`.

---

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`

---

## V. Document Tier Classification

All documents are classified into four tiers representing their normative authority:

### Tier 0 — Foundational
- **Definition**: Defines non-negotiable laws and identity of the system.
- **Location**: `docs/INVARIANT/CORE/`
- **Prefix**: `INV-CORE-*`

### Tier 1 — Constitutional
- **Definition**: Structural enforcement mechanisms and bounded domain rules that operationalize Tier 0 laws.
- **Location**: 
  - `docs/INVARIANT/ARCHITECTURE/` (Prefix: `INV-ARC-*`)
  - `docs/DOMAIN/` (Prefix: `DOM-*`)

### Tier 2 — Normative
- **Definition**: Governs concrete implementation flows, transactions, and operational standard procedures.
- **Location**: 
  - `docs/FEATURE-EXECUTION/` (Prefix: `FEAT-*`)
  - `docs/STANDARD_OPERATING_PROCEDURES/` (Prefix: `SOP-*`)

### Tier 3 — Informative
- **Definition**: Preserves institutional memory, timelines, target plans, releases, and user guides. Must not define runtime rules.
- **Location**:
  - `docs/MAP/` (Prefix: `MAP-*`)
  - `docs/user-guides/` (User guides)
  - `docs/LOGS/` (Prefix: `LOG-*`)
  - Root directory files (`README.md`, `CHANGELOG.md`, `DEVELOPMENT.md`, etc.)

---

## VI. Restructure Directory Taxonomy

The target structure under `docs/` consists of:

1. **`INVARIANT/CORE/`**: Foundational invariants and system properties.
2. **`INVARIANT/ARCHITECTURE/`**: Architectural invariants, cross-domain safety boundaries, and gating rules.
3. **`DOMAIN/`**: Authoritative domain specifications defining vocabulary, schema authority, owned database tables, and capability checks.
4. **`FEATURE-EXECUTION/`**: Specs defining user interactions, FEAT orchestration, and transaction safety.
5. **`MAP/`**: Technical maps, launch tracking checklists, and target-state documentation.

---

## VII. Naming Convention

All formal document identifiers must follow the format:

```
[NAMESPACE]-[FUNCTIONAL-AREA]-[NUMERIC-IDENTIFIER]_[Descriptive_Title].md
```

- `000` is reserved for namespace-area definitions or foundations (e.g. `DOM-CORE-000`).
- Subsequent numbers represent derived documents.
- Title must use snake_case or descriptive words separated by underscores.

---

## VIII. Authoring Guidelines

### Required Sections for Normative and Constitutional Documents

Formal specifications (INV, DOM, FEAT, SOP) must include the following sections in this exact order:

1. **I. Purpose** — Single paragraph explaining the document's goal.
2. **II. Scope** — Details on what is governed and where constraints apply.
3. **III. Authority Level** — Tier classification and subordination mappings.
4. **IV. Dependencies** — References to preceding documents or models.
5. **[V+] Content Sections** — Document-specific rules (e.g., capability definitions).
6. **[Last] Amendment** — Standard revision procedure.

### Crucial Architectural Rules to Document

- **Class Isolation Scoping**: Documents must scope student/seat queries by `class_id` (canonical boundary) rather than teacher ownership or label.
- **Identity Context**: Roster and activity anchors must be bound to `seat_id`.
- **Pure Reads**: Read pathways (GET) must not trigger state modification or session commits.
- **PII Encryption**: Specifications must ensure PII is encrypted at rest using standard hash/encryption helpers.

---

## IX. Codebase Organization Playbook

### Clean Separation Rules
- **No Documentation in `/app/`**: Runtime directories must contain only execution code, tests, and configuration.
- **No Runtime Code in `/docs/`**: The documentation tree must not contain executable modules or active scripts.
- **User-Facing Separation**: Public guides belong in `docs/user-guides/` and must focus on high-level guarantees and walkthroughs. No internal implementation details, ORM schemas, or system keys may be published in user-facing guides.

### File Operations Workflow
1. **Use Git Move**: Always run `git mv` to relocate files to preserve commit history.
2. **Verify References**: After moving, use `rg` to locate and update all inbound markdown links and reference pointers.
3. **Audit heads**: Ensure Alembic migration heads and Git HEAD remain clean and unified.

---

## X. Link Integrity Verification Procedure

Every file relocation or renaming must be immediately verified with:

```bash
# Search for occurrences of the old filename or path across the repository
rg "old_filename_or_path" docs/
```

All references must be updated in the same commit to guarantee a zero-broken-link state.

---

## XI. Amendment

Revisions to this standard require:
1. Incrementing the version number.
2. Updating the Effective Date.
3. Updating the Supersedes list.
4. Ensuring compatibility with core invariants in `INV-CORE-000`.
