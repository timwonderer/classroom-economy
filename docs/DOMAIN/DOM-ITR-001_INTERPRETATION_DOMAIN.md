# DOM-ITR-001: Interpretation Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-ITR-001      | 1.2     | 2026-08-16     | 1.1        | Normative       |

## I-A. Authority Level and Dependencies

Normative. Subordinate to `INV-CORE-000` and `INV-ARC-009`.

### Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`

---

## I. Purpose

The Interpretation Domain is a read-only meaning layer over authoritative system truth. It produces two kinds of output:

- **Descriptive observations** — statements of what the persisted facts show.
- **Interpretive signals** — conclusions that combine descriptive observations with an explicit reference or model to answer a class-economy question.

Interpretation does not mutate state, enforce policy, or define correctness. It does not itself constitute policy authority, nor does it produce facts that source domains are obligated to accept.

---

## II. Domain Authority

### Interpretation OWNS Authority Over:

- **Descriptive observations** over authoritative domain facts, per completed economic cycle windows.
- **Interpretive signals** that combine descriptive observations with an explicit, declared reference or model, subject to the reference-scope constraint below.
- **Aggregation** of per-subject observations to class-level rollups where declared.
- **Trend indicators**, when a prior-snapshot source exists. (Currently NOT IMPLEMENTED — see §VIII.)
- **Simulation outputs** — non-persistent projections. (Currently NOT IMPLEMENTED.)
- **Contextual annotations** — non-authoritative labels attached to observed events. (Currently NOT IMPLEMENTED.)

### Reference-Scope Constraint

An Interpretation-declared reference or model MAY define an analytical framing (e.g., how a descriptive observation is combined with a declared expectation to produce an interpretive signal). It SHALL NOT manufacture policy expectations, correctness standards, or behavioral expectations that properly belong to another domain. Where such an expectation exists, it must be authored by, and lawfully imported from, the owning domain's declared observational contract.

### Scope Note

The Interpretation Domain is authorized to answer questions of participation, economic activity, obligation outcomes, savings behavior, income composition, resource distribution, and resilience. These are topics addressed through the output semantics of §IV, not additional semantic categories. Every resilience-related output is either a descriptive observation or an interpretive signal, and inherits all the constraints of its declared semantic kind.

### Interpretation Explicitly DOES NOT Own:

- **Financial truth** → Ledger
- **Obligation truth** → Obligations
- **Attendance truth** → Attendance
- **Entitlement balances** → Obligations / Store
- **System correctness** → Operations
- **Policy definition or enforcement** → Class Configuration
- **Economic calculation and reference values** → `SPEC-ECON-003` under CLASS authority (CWI derivation, per-mode bands, doubling-time, compound growth, economic coherence rules).
- **Store product definitions or purchase truth** → STORE.
- **Recovery / reset eligibility, triggering, execution, or gating** → not currently owned by any documented domain. Interpretation MAY produce observations that inform such a decision but MUST NOT itself specify or gate it.
- **Overdraft / NSF assessment ownership** — currently split between LEDGER (execution) and OBLIGATIONS (semantic owner in current CTH discussion); pending domain reconciliation. Interpretation acknowledges this as an observation gap (see §XIII.c).

---

## III. Core Boundary

### Interpretation answers:

- "What does the current system state mean?"

### It does NOT answer:

| Question | Domain |
| :--- | :--- |
| Is the system correct? | **Operations** |
| Is the system enforced properly? | **Class Configuration** |
| What should happen next? | Teacher / Policy |
| What is the truth? | Source Domains |
| What is a viable economic configuration? | **Class Configuration** (`DOM-CLASS-003`, `SPEC-ECON-003`) |
| What is the correct value of X? | **Source Domain** |
| What action should the teacher take? | **Teacher / Policy** — Interpretation may surface observations but never prescribes response |
| Is this student eligible for recovery/reset? | **Not owned by Interpretation** (no current doctrine home) |

---

## IV. Output Semantics (Non-Optional)

Every Interpretation output SHALL declare three orthogonal properties.

### IV.1 Semantic Kind

Every Interpretation output declares exactly one Semantic Kind:

- **Descriptive observation** — reports a fact or aggregate derived from authoritative sources. Carries no conclusion about condition, pattern, or departure from a reference.
- **Interpretive signal** — combines descriptive observations with an explicit, declared reference or model to answer a class-economy question. Every interpretive signal traces to (a) the descriptive inputs it consumes, (b) the model or reference it applies, and (c) the source of that reference.

**Each individual output has exactly one Semantic Kind. A single Interpretation calculation MAY emit multiple outputs of different Semantic Kinds. No individual output is both.**

### IV.2 Subject Declaration

Every output declares:

- **Subject** — the entity the output describes, identified by an authoritative entity identifier exposed by the owning domain. `seat_id` and `class_id` are canonical examples. Where the subject is an entity owned by another domain, the identifier used SHALL be one that domain publishes as canonical; Interpretation does not establish another domain's identity contract.
- **Observation basis** — the entity or entities from which the underlying facts were observed, identified similarly.
- **Aggregation** — how observations were combined to produce the output at the declared subject (e.g., `per_seat` when subject and basis coincide; `class_aggregate_from_seat_observations` when a class-level output is built from per-seat observations). There is no default aggregation. Every output declares its own.

### IV.3 Reference Dependency

Every output declares one of:

- **None** — output is defined entirely by observed facts.
- **Class Configuration observational reference** — output compares observation against an expectation explicitly declared as observational by `DOM-CLASS-*` or `SPEC-ECON-003`.
- **Interpretation-declared reference** — output compares observation against a reference this domain itself owns, subject to §II's reference-scope constraint.

Configuration input ranges, permissible policy-mode bands, and configured recommendation ranges are **not** observational references. See §VI INV-ITR-014.

---

## V. State Classification

| State | Classification | Justification |
| :--- | :--- | :--- |
| **Descriptive Observations** | Derived State | Computed from authoritative domain facts. |
| **Interpretive Signals** | Derived State | Descriptive inputs combined with a declared reference/model. |
| **Trend Indicators** | Derived State | Requires prior-snapshot source (currently unavailable — see §VIII). |
| **Simulation Outputs** | Derived State | Hypothetical, non-persistent. Currently NOT IMPLEMENTED. |
| **Interpretation Snapshots** | Cache | Performance only. Currently NOT IMPLEMENTED — see §VIII, §IX. |
| **Annotation Signals** | Derived State | Non-authoritative labels. Currently NOT IMPLEMENTED. |

---

## VI. Invariants

### General Invariants

- **INV-ITR-001: Read-Only Enforcement**. No mutation of any domain state.
- **INV-ITR-002: Source-of-Truth Dependency**. All outputs must derive from authoritative domains.
- **INV-ITR-003: Deterministic Reproducibility**. Same inputs + same window → identical outputs.
- **INV-ITR-004: No Domain Logic Reimplementation**. No re-creating Ledger, Obligations, or Attendance logic.
- **INV-ITR-005: Correction Awareness**. All reversals, waivers, and corrections must be reflected.
- **INV-ITR-006: Timezone Integrity**. All time logic uses `ClassTimeZone`.
- **INV-ITR-007: Explicit Time Windows**. All outputs must define window boundaries and cycle definition.
- **INV-ITR-008: Non-Authoritative Output**. Interpretation MUST NOT enforce policy, block actions, or mutate configuration.
- **INV-ITR-009: Actor Dignity Constraint**. No rankings, no exposed identities, no hierarchy signals.
- **INV-ITR-010: No Policy Authority**. Interpretation evaluates but never enforces.
- **INV-ITR-011: Cache Integrity**. Caches must be recomputable and invalidated on change.

### Semantic Invariants

- **INV-ITR-012: Output Property Declaration**. Every Interpretation output SHALL declare its Semantic Kind (§IV.1), Subject / Observation Basis / Aggregation (§IV.2), and Reference Dependency (§IV.3). Outputs missing any of the three declarations are non-compliant.

- **INV-ITR-013: Descriptive-to-Interpretive Traceability**. Descriptive observations SHALL NOT be presented as interpretive conclusions. Every interpretive signal SHALL trace to (a) its descriptive input(s), (b) the model or reference applied, and (c) the source of that reference. Silent promotion of a descriptive count, rate, or aggregate into an interpretive claim about meaning, condition, pattern, or departure from a declared reference is prohibited.

  *Example of prohibited pattern:* reporting "N% of students are within the class configuration's rent band" as a departure-from-expectation signal without a declared observational reference authorizing that comparison.

- **INV-ITR-014: No Inferred Observational Expectation from Configuration**. Interpretation SHALL NOT construct an observational expectation from a Class Configuration input range, permissible policy-mode band, or configured recommendation range. Interpretation MAY compare observations against a reference only when that reference is explicitly declared as observational by the owning domain.

  *Example of prohibited pattern:* using a policy-mode's `savings_weekly.min` (a configuration target) as the reference for an observational "students are or aren't saving enough" signal without an owning-domain declaration authorizing that use.

- **INV-ITR-015: Provenance via Canonical Fields**. Interpretation SHALL classify Ledger event origin using `mechanism`, `feat_code`, `correlation_id`, and reversal linkage fields, plus the authoritative event tables of the owning domains (`AttendanceSession`, `AssessmentEvent`, `EntitlementEvent`, `PayrollEvent`). Interpretation SHALL NOT treat `Transaction.type` as authoritative semantic classification.

- **INV-ITR-016: Source Domain Precedence**. When an authoritative fact is persisted by a source domain, Interpretation SHALL consume that fact directly rather than reconstruct it from Ledger rows or other secondary sources. STORE establishes purchases; OBLIGATIONS establishes assessment / payment / waiver; ATTENDANCE / PRODUCTIVITY establishes labor participation; LEDGER establishes monetary movement and its provenance. Interpretation queries the owning domain first. This invariant does not itself decide domain ownership of any given fact; where ownership is unresolved, Interpretation MUST NOT infer it (see §XIII.c).

- **INV-ITR-017: Threshold Ownership**. Every threshold used in an Interpretation output SHALL have an explicitly declared semantic owner. The computation layer and the presentation layer SHALL NOT invent thresholds locally. When the owner is Interpretation, the threshold SHALL be declared in the specification that defines the containing output. When the owner is Class Configuration or another domain, the threshold's location and authority SHALL be cited.

  *Example of prohibited pattern:* a view-model layer independently declaring "green above 70%, yellow above 50%" for a metric whose SPEC does not authorize those bounds.

---

## VII. Temporal Model

### Primary Unit: Completed Economic Cycle

- Only completed cycles are evaluated.
- No rolling windows.
- No partial-cycle metrics.

### Activation

Interpretation begins only after at least one full completed economic cycle. (Enforcement of this rule against caller-supplied windows is currently not satisfied by runtime — see §XIII.b.)

### Historical Configuration Binding

Interpretation of a completed historical window SHALL be evaluated against the class configuration that was authoritative for that window. Reinterpreting historical windows under a later configuration is prohibited. When the current schema cannot represent the configuration authoritative for a given historical window with sufficient provenance, Interpretation SHALL declare the window's evaluation as **not replayable** rather than silently substituting current configuration.

### Known Noncompliance

The current runtime does not satisfy the Historical Configuration Binding requirement above. Existing implementations evaluate completed windows against the class configuration active at compute time, and no persistence or provenance surface exists that would permit lawful evaluation against the historical configuration. This is a doctrine violation, not a specification gap. Closing it requires a separately specified schema / provenance contract; until that contract lands and is implemented, callers of Interpretation SHALL be advised that historical-window outputs against changed configurations are computed noncompliantly.

---

## VIII. State Transitions

### Compute Interpretation

- **Actor**: System
- **Trigger**: produces derived output
- **Status**: IMPLEMENTED. Executes via the Compute Interpretation FEAT (canonical name `FEAT-ITR-001`, read-only). See §XIII.b for the current runtime name and rename status.

### Materialize Snapshot

- **Actor**: System
- **Trigger**: writes cache
- **Status**: NOT IMPLEMENTED. Requires a separately specified Materialize FEAT with its own schema, provenance, and lifecycle contract. See §IX.

### Invalidate Snapshot

- **Actor**: System
- **Trigger**: marks stale
- **Status**: NOT IMPLEMENTED. Depends on Materialize.

### Generate Simulation

- **Actor**: System
- **Trigger**: produces non-persistent output
- **Status**: NOT IMPLEMENTED.

---

## IX. Derived Schema

The schema declared in this section describes intended persistence for materialized Interpretation outputs. **As of v1.2, none of these tables exists in the runtime schema or in the migration chain.** All current Interpretation outputs are computed on demand and returned as in-memory dataclasses. Materializing these tables requires a separately specified Materialize Interpretation Snapshot FEAT with its own schema, provenance, and lifecycle contract, and is out of scope for the current tranche (§X.9).

### `interpretation_snapshots`

- `id`: UUID
- `class_id`: UUID
- `axis`: (behavioral | structural) — **DEPRECATED.** If materialized, this column MUST be revised to align with v1.2's Semantic Kind (§IV.1) and Subject declaration (§IV.2). The two-axis enum is retired.
- `cycle_id`: UUID
- `metric_type`: VARCHAR
- `window_start`: TIMESTAMPTZ
- `window_end`: TIMESTAMPTZ
- `computed_at`: TIMESTAMPTZ
- `value_payload`: JSONB

### `interpretation_annotations`

- `id`: UUID
- `class_id`: UUID
- `event_type`: VARCHAR
- `timestamp`: TIMESTAMPTZ
- `payload`: JSONB

---

## X. Edge Case Decisions

1. **Reversals override prior signals**: Metrics must reflect the final corrected truth.
2. **Late data triggers recomputation**: Historical snapshots must be updated.
3. **No fabricated data**: Incomplete logs result in incomplete interpretation, not guesses.
4. **Simulations never persist**: Hypothetical data must not contaminate the cache.
5. **No ranking systems**: The system produces aggregate observations and signals, not individual rankings.
6. **Interpretation never becomes policy**: The teacher remains the final authority on configuration changes.
7. **Descriptive observations do not silently become interpretive conclusions.** See INV-ITR-013.
8. **Configuration inputs are not observational references.** See INV-ITR-014.
9. **Missing implementation does not remove an authorized capability from domain scope.** State transitions and schema surfaces marked NOT IMPLEMENTED (§VIII, §IX) remain authorized as Interpretation capabilities. Implementing any such capability remains subject to the applicable SPEC, FEAT, schema, provenance, and certification requirements. Doctrine-level authorization of a capability does not pre-authorize its persistence semantics, lifecycle behavior, provenance model, invalidation rules, or simulation contract. Each of those is owned by its downstream contract, and each must be produced before that capability can lawfully be built.

---

## XI. Design North Star

A teacher should be able to answer:

- What did students do in the observed window?
- What was configured for that window?
- Where do observations depart from what a declared observational reference would predict?

Without:

- digging through logs
- comparing students to each other
- interpreting raw data
- receiving prescriptive policy recommendations from Interpretation

---

## XII. Canonical Mental Model

- **Descriptive observation** tells you what the persisted facts show.
- **Interpretive signal** tells you what those facts mean *when compared against an explicitly declared reference* — never as an inferred conclusion from configuration alone.
- **The teacher** decides what to do about either.

---

## XIII. Implementation Status

Non-normative appendix. Records the divergences between doctrine and current runtime so downstream SPEC and FEAT work has a single reference point. Split into three categories.

### XIII.a NOT IMPLEMENTED — Authorized Capabilities Absent from Runtime

| Element | Doctrine Status | Runtime Status |
|---|---|---|
| Materialize Snapshot | Authorized (§VIII) | No persistence layer; no `interpretation_snapshots` table. Requires a separately specified Materialize FEAT with its own schema / provenance / lifecycle contract. |
| Invalidate Snapshot | Authorized (§VIII) | Depends on Materialize. |
| Generate Simulation | Authorized (§VIII) | No simulation surface. |
| Trend indicators with prior-snapshot source | Authorized (§V) | No prior-snapshot source available; `compute_trends` always receives `previous_snapshot=None` and returns `stable`. |

### XIII.b KNOWN NONCOMPLIANCE — Runtime Violates v1.2 Doctrine

| Element | Doctrinal Requirement | Runtime Behavior |
|---|---|---|
| FEAT name for Compute | Compute Interpretation FEAT is `FEAT-ITR-001` under the Interpretation domain namespace. | Currently registered as `FEAT-ANLY-001` under a non-canonical `"Analytics"` domain string in `app/feats/base.py`. Rename authorized but deferred. |
| Historical Configuration Binding | §VII requires historical windows to be evaluated against their authoritative historical configuration. | Runtime evaluates historical windows against compute-time configuration. Doctrine violation, not a specification gap. |
| Completed-cycle window discipline | §VII requires completed cycles only. | Runtime accepts arbitrary caller-supplied windows without enforcement. |
| Output Property Declaration (INV-ITR-012) | Every output SHALL declare Semantic Kind, Subject / Observation Basis / Aggregation, and Reference Dependency. | Current outputs declare none of these. |
| Provenance via canonical fields (INV-ITR-015) | Classification of Ledger events uses `mechanism`, `feat_code`, `correlation_id`, reversal linkage, and authoritative source-domain event tables. `Transaction.type` is not authoritative. | `Transaction.type` is consulted in some current calculations. |
| Source Domain Precedence (INV-ITR-016) | Authoritative facts consumed directly from owning domains. | `participation_rate` derives from Ledger + Attendance without domain-fact preference; other metrics similar. |
| Threshold Ownership (INV-ITR-017) | Every threshold has an explicit semantic owner; computation and presentation layers do not invent them locally. | Thresholds duplicated across `ANALYTICS_POLICY_DEFAULTS`, `analytics_engine.py`, and `app/services/analytics/builders.py`, with six documented divergences. |

### XIII.c UNRESOLVED — Cross-Domain Ownership Questions Affecting Interpretation

Items in this section are not Interpretation-owned and cannot be resolved by amending DOM-ITR-001. They are recorded here only so downstream SPEC-ITR-001 work knows what it cannot assume.

| Element | Status |
|---|---|
| Overdraft / NSF fee assessment ownership | **Ownership unresolved between LEDGER and OBLIGATIONS.** INV-ITR-016 requires Interpretation to consume the owning domain's fact but does not itself decide which domain owns the fact. Interpretation MUST NOT infer ownership. Runtime currently: LEDGER writes `type="overdraft_fee"`; no `AssessmentEvent` produced. Cross-domain reconciliation between LEDGER and OBLIGATIONS is a precondition for obligation-outcome observations to include overdraft / NSF. |
| Current runtime `suggested_action` alert content | **Doctrinal question is resolved:** v1.2 §III, §XI, and INV-ITR-010 establish that Interpretation does not prescribe teacher action. **Runtime disposition is unresolved:** the existing prescriptive text in `analytics_engine.py::generate_alerts` violates that doctrine and requires removal or relocation. Whether that disposition happens via deletion, movement to a non-Interpretation surface, or reformulation as a purely descriptive signal is a runtime remediation choice, not a doctrinal one. |
