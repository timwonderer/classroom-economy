# SOP-DEV-002: Canonical Domain Reconstruction Workflow

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEV-002 | 1.0 | 2026-07-20 | N/A | Normative |

---

## I. Purpose

This SOP defines the repeatable workflow for reconstructing a domain from canonical truth, lawful primitive operations, read projections, and audited application surfaces.

The workflow is intended for v2 migration and future domain refactors where the existing implementation contains mixed v1/v2 behavior, compatibility paths, or route-level business logic.

---

## II. Scope

This SOP applies to:

- domain reconstruction
- domain-owned table replacement
- route and template rewiring
- v1 compatibility removal
- feature workflows that must be rebuilt from canonical primitives
- user-facing surfaces that must be reconnected after canonical domain work

This SOP governs development sequence and deliverables. It does not define runtime authority itself. Runtime authority remains governed by `INV`, `DOM`, and `FEAT` documents.

---

## III. Authority Level

Normative. Subordinate to:

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `SOP-DOC-000_DOCUMENTATION_STANDARD.md`
- `SOP-DEV-001_REFACTOR_BEST_PRACTICES.md`

If this workflow conflicts with governing `INV`, `DOM`, or `FEAT` authority, the governing architecture document prevails.

---

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-017_GENERAL_TESTING_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
- `docs/STANDARD_OPERATING_PROCEDURES/DEVOPS/SOP-DEV-001_REFACTOR_BEST_PRACTICES.md`
- `docs/MAP/MAP-UI-001_TEMPLATE_TO_FEAT_WIRING_MAP.md`
- `docs/MAP/MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE.md`

---

## V. Core Principle

Domain reconstruction proceeds from truth to interface, then uses audited interface demand to drive rewiring.

The old implementation is evidence, not authority.

The required direction is:

1. canonical truth
2. canonical persistence
3. lawful primitive writes
4. lawful reads and projections
5. FEAT orchestration
6. route/application interface
7. template and API surface rewiring
8. verification
9. legacy removal

The template or route surface may prove that a capability is user-facing, but it must not dictate domain authority or persistence shape.

---

## VI. Required Workflow

### Phase 0: Domain Boundary

Identify:

- the domain being reconstructed
- the owning `DOM-*` document
- the constraining `INV-*` documents
- the relevant `FEAT-*` documents or missing FEAT gaps
- adjacent domains that must be read from or coordinated with
- a cross-domain contract identifying:
  - domains this domain owns
  - domains it consumes through lawful reads
  - domains it mutates through FEAT coordination
  - interfaces this domain exposes to other domains

Deliverable:

- a short domain boundary statement naming what the domain owns and what it does not own

### Phase 1: Canonical Truth

Ask only what facts must remain permanently true.

Classify all candidate state as:

- stored truth
- derived state
- display-only projection
- cross-domain reference
- obsolete v1 residue

Rules:

- Persist only facts the domain owns.
- Do not persist state that can be deterministically derived.
- Do not preserve a v1 table, field, or cache because routes or templates still reference it.
- If a fact belongs to another domain, reference that domain through the lawful read or FEAT boundary.

Deliverable:

- canonical truth table listing stored facts, derived facts, forbidden facts, and owning documents

### Phase 2: Canonical Persistence

Define or confirm:

- owned tables
- required fields
- forbidden fields
- append-only versus mutable semantics
- `class_id` and `seat_id` anchors
- correlation and idempotency requirements
- deletion and retention semantics

Rules:

- Schema shape must follow `DOM-CORE-002`.
- Domain-owned tables must not encode another domain's authority.
- Financial meaning must not be stored outside the lawful monetary and business-authority split.

Deliverable:

- canonical table contract in the owning `DOM-*` document or a scoped schema proposal when the `DOM-*` document is not ready to change

### Phase 3: Primitive Operations

Break the domain into the smallest lawful operations.

For each primitive, define:

- command or query
- required context
- temporal resolver requirement
- inputs
- reads
- writes
- preconditions
- postconditions
- failure contract
- owning FEAT if it mutates

Rules:

- A primitive write must be explicit and named.
- A primitive read must be pure.
- A domain primitive may validate or return state, but cross-domain orchestration belongs in FEAT.

Deliverable:

- primitive operation table in `DOM-*`, `FEAT-*`, or a scoped implementation plan

### Phase 4: Legal Mutation Boundary

For every write primitive, define the single lawful FEAT path.

Rules:

- Routes, background jobs, CLI commands, tests, and helpers must not write domain tables directly.
- Mutation must resolve canonical context before domain interaction.
- Mutation must use one transaction boundary.
- Idempotency and correlation must be part of the FEAT contract where replay or linked effects are possible.

Deliverable:

- FEAT write contract naming the one legal writer for each domain-owned table

### Phase 5: Read Models and Projections

Define the lawful read surfaces needed by the application.

Classify each read as:

- authoritative domain read
- derived projection
- view model
- cross-domain aggregate
- display-only formatting

Rules:

- Do not reconstruct domain truth in routes.
- Do not derive payroll, balance, entitlement, or lifecycle authority from presentation-layer objects.
- GET routes must remain pure.
- Temporal comparisons must use the canonical temporal model when class-local or boundary-sensitive.

Deliverable:

- read/projection contract listing each view model and its source facts

Shared request context and page view model assembly should follow `MAP-UI-002_REQUEST_CONTEXT_AND_VIEW_MODEL_PIPELINE.md`.

### Phase 6: Application Surface Inventory

Inventory every surface that touches the domain.

Required sources:

- Jinja/template audits
- Flask routes
- API endpoints
- JavaScript request targets
- scheduled jobs
- CLI commands
- tests and test helpers

Rules:

- Use template audits to discover the user-facing demand surface.
- Use route/API/job/CLI scans to discover non-template callers.
- Keep template interface auditing separate from domain correctness auditing.
- Treat each surface as `rewire`, `remove`, `collapse`, or `verify`.

Deliverable:

- a map or checklist, normally under `docs/MAP/`, with one row per user-visible capability or non-template caller group

### Phase 7: Rewire, Remove, or Collapse

For each inventory row, choose exactly one disposition:

- `REWIRE`: keep the surface and connect it to canonical route, FEAT, domain, persistence, and read-model paths
- `REMOVE`: delete an obsolete, illegal, unsupported, or unreachable surface
- `COLLAPSE`: merge duplicated behavior into another canonical surface, then delete the redundant one
- `VERIFY`: prove the surface is already canonical and record evidence

Rules:

- Do not add compatibility bridges to keep an obsolete surface alive.
- Do not make the domain conform to stale template shape.
- Do not leave a surviving UI surface without a named canonical provider.

Deliverable:

- updated map status and linked patch or issue reference for each row

### Phase 8: Verification

Run targeted validation proportional to the changed surface.

Required categories as applicable:

- domain primitive tests
- FEAT transaction and idempotency tests
- route success and denial tests
- template render tests
- accessibility validation for changed templates
- journey tests for complete user workflows
- migration upgrade/downgrade checks for schema changes

Rules:

- Record exact commands and scope.
- Do not claim whole-domain completion from partial runs.
- Use the newest relevant `pytest_result` artifact before running new tests when triaging failures.

Deliverable:

- validation evidence in the map, tracker, PR, or changelog

### Phase 9: Legacy Deletion

After every legitimate surface has been rewired, removed, collapsed, or verified, delete unreachable legacy code.

Targets may include:

- dead routes
- compatibility helpers
- dead templates
- unused context processors
- obsolete tests
- unused models
- retired tables and migrations, when schema rules allow

Rules:

- Delete after the replacement surface is proven.
- If deletion exposes a caller, add it to the surface inventory rather than restoring the old path.
- Do not keep legacy code because it might be needed without a mapped surviving surface.

Deliverable:

- deletion patch with targeted regression evidence and updated tracking docs

### Phase 10: Certification Audit

Perform an independent audit of the reconstructed domain.

The audit should attempt to falsify the claim that the domain has been successfully reconstructed.

Required audit categories include, as applicable:

- canonical domain authority
- persistence correctness
- lawful FEAT mutation boundaries
- read model correctness
- application surface rewiring
- template contract compliance
- accessibility requirements
- journey workflows
- legacy implementation leakage
- documentation synchronization
- cross-domain coordination
- targeted regression evidence

Rules:

- The audit should independently verify the implementation rather than relying on implementation assumptions.
- Documentation must accurately describe the implemented behavior.
- False positives discovered during audit should result in refinement of the audit methodology rather than unnecessary code changes.
- Findings must either be resolved or explicitly tracked before certification.

Deliverable:

- completed domain audit report
- disposition of all findings
- certification evidence

---

## VII. Required Status Vocabulary

Domain reconstruction maps must use these dispositions:

| Status | Meaning |
|---|---|
| `REWIRE` | Surviving behavior must be connected to canonical v2 paths |
| `REMOVE` | Surface or code path should be deleted |
| `COLLAPSE` | Behavior should be consolidated into another canonical surface |
| `VERIFY` | Current implementation appears canonical and needs proof |
| `BLOCKED` | Canonical authority is missing or contradictory |

When a row is complete, record the completed disposition:

| Completed Status | Meaning |
|---|---|
| `REWIRED` | Surviving surface now uses canonical v2 paths |
| `REMOVED` | Surface or code path was deleted |
| `COLLAPSED` | Surface was merged into another canonical workflow |
| `VERIFIED` | Surface was proven already canonical |

---

## VIII. Stage Gates

Do not begin route/template rewiring until:

- canonical truth is defined
- owned persistence is defined
- primitive writes and reads are named
- write FEAT ownership is known or explicitly blocked
- the relevant surface inventory exists

Do not mark a surface complete until:

- route and template contracts agree
- the route calls the canonical provider
- mutation, if any, enters the single lawful FEAT path
- reads come from canonical domain projections or documented cross-domain reads
- targeted tests or render evidence exist
- dead compatibility paths exposed by that surface have been removed or tracked

Do not delete a legacy path until:

- every known surviving caller has been rewired, removed, collapsed, or verified
- targeted validation covers the replacement surface
- the deletion itself is included in the verification scope

---

### Domain Completion Gate

A domain reconstruction is considered complete only when:

- canonical domain authority is fully documented
- persistence contract is complete
- primitive operations are defined
- every lawful mutation enters through FEAT
- read models are documented
- every inventoried application surface is marked:
  - REWIRED
  - REMOVED
  - COLLAPSED
  - VERIFIED
- targeted validation has passed
- documentation reflects the implemented architecture
- certification audit has completed with no unresolved blocking findings
- remaining issues, if any, are explicitly tracked and do not violate governing INV, DOM, or FEAT authority

Completion represents architectural certification of the reconstructed domain rather than implementation progress alone.

---

## IX. Productivity and Payroll Reference Pattern

The Productivity and Payroll reconstruction is the reference example for this SOP.

It followed this sequence:

1. Define productivity and payroll business truth.
2. Define the canonical tables: `attendance_sessions`, `hall_pass_logs`, and `payroll_event`.
3. Classify derived state such as current attendance status, elapsed productivity time, payroll windows, and remaining hall-pass count.
4. Define single write FEATs: `FEAT-PROD-001`, `FEAT-PROD-002`, and `FEAT-PROD-003`.
5. Map template and route surfaces in `MAP-UI-001`.
6. Use the map as the checklist for rewiring, removing, collapsing, verifying, and deleting legacy paths.

---

## X. Prohibited Patterns

The following are prohibited:

- starting from v1 helper shape instead of canonical truth
- treating a template variable as proof that a domain must store a field
- retaining compatibility shims without a mapped surviving surface
- letting routes compute authoritative state that belongs to a domain
- allowing multiple write paths to the same domain-owned table
- marking a surface complete because it renders while it still calls legacy authority
- marking a domain complete without deleting or tracking reachable legacy paths
- using full-suite tests as a substitute for targeted proof of the reconstructed surface

---

## XI. Required Deliverables

Every domain reconstruction must produce or update:

1. governing `DOM-*` authority or schema proposal
2. primitive operation table
3. legal FEAT write contract
4. read/projection contract
5. application surface inventory or map
6. cutover checklist with `REWIRE`, `REMOVE`, `COLLAPSE`, `VERIFY`, or `BLOCKED`
7. targeted validation evidence
8. tracker/changelog/doc updates when runtime behavior changes

---

## XII. Amendment

Revisions to this SOP must:

1. increment the version number
2. update the Effective Date
3. update the Supersedes field
4. preserve consistency with `INV-CORE-000`, `INV-CORE-001`, `INV-ARC-009`, and `SOP-DEV-001`
5. update `SOP-DOC-002` if the document is renamed or superseded
