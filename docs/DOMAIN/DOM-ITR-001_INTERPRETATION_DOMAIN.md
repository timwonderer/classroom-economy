# DOM-ITR-001: Interpretation Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-ITR-001      | 1.5     | 2026-08-30     | 1.4        | Normative       |

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
- **Trend indicators**, when a prior cycle-record source exists. (Available once `interpretation_cycle_record` accrues across cycles — see §VIII, §IX.)
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
- **Overdraft / NSF assessment ownership** — RESOLVED (SPEC-ECON-003 §4.6.1.1): LEDGER executes (posts the fee) and stays domain-blind; OBLIGATIONS owns the fine, recorded by the originating business FEAT as an immediate obligation. Interpretation consumes the OBLIGATIONS fact per INV-ITR-016 (see §XIII.c).

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
| **Trend Indicators** | Derived State | Requires a prior cycle record source. Available once `interpretation_cycle_record` accrues across cycles (§VIII, §IX). |
| **Simulation Outputs** | Derived State | Hypothetical, non-persistent. Currently NOT IMPLEMENTED. |
| **Cycle Interpretation Records** | Durable Authoritative Record | Immutable per-cycle materialization bound to `payroll_cycle_id`; self-describing via a versioned `reference_configuration` projection. Not a cache. Persistence surface IMPLEMENTED (`interpretation_cycle_record`, migration `b3d7f1a9c2e4`); materialization writer NOT IMPLEMENTED (§VIII, §IX). |
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
- **INV-ITR-011: Read-Cache Integrity (scoped)**. This invariant applies ONLY to optional, non-authoritative, ephemeral read caches used to accelerate on-demand Interpretation. Such caches must be recomputable and invalidated on change. It does **not** apply to the durable `interpretation_cycle_record` (§IX): a materialized cycle record is authoritative, immutable, and never recomputed or invalidated. No caching rule may be read to require rewriting a completed cycle record.

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

Interpretation of a completed historical window SHALL be evaluated against the class configuration that was authoritative for that window. Reinterpreting historical windows under a later configuration is prohibited.

This requirement is satisfied by **cycle-bound materialization** (§VIII, §IX). The economic cycle is defined by payroll completion (`DOM-PROD-001` §XV): when a class-level payroll run closes cycle N, the canonical completion FEAT (`FEAT-PROD-004`) orchestrates Interpretation to compute and materialize exactly one durable, immutable `interpretation_cycle_record` for that cycle. The record persists the **actual economic reference values in effect for cycle N** (§IX) so that the closed cycle is self-describing and never depends on reinterpreting against later configuration.

A materialized `interpretation_cycle_record` is permanently bound to its `payroll_cycle_id` and is **never recomputed**. Ordinary downstream reversals or corrections do not retroactively rewrite a completed cycle's record; they are reflected in the cycle in which they occur. Because the record captures the governing reference values at materialization time, the "not replayable" fallback of prior versions is no longer required for cycles produced under this contract.

### Pre-Contract Windows

Cycles that predate the cycle-bound materialization contract have no `interpretation_cycle_record` and no `reference_configuration` projection. For such windows Interpretation SHALL declare the evaluation as **not replayable** rather than silently substituting current configuration. This is a transitional coverage gap, tracked toward zero as cycles accrue under the new contract, not a doctrine violation of the binding rule itself.

---

## VIII. State Transitions

### Compute Interpretation

- **Actor**: System
- **Trigger**: produces derived output
- **Status**: IMPLEMENTED. Executes via the Compute Interpretation FEAT (canonical name `FEAT-ITR-001`, read-only). See §XIII.b for the current runtime name and rename status.

### Materialize Cycle Interpretation

- **Actor**: System
- **Trigger**: economic-cycle boundary — successful payroll completion for the class (`DOM-PROD-001` §XV), orchestrated by `FEAT-PROD-004`.
- **Behavior**: Computes the closed cycle's Interpretation and writes exactly one durable, immutable `interpretation_cycle_record` (§IX) bound to the run's `payroll_cycle_id`, capturing the economic reference values in effect for the cycle.
- **Status**: Persistence surface IMPLEMENTED — the `interpretation_cycle_record` table, model, and schema certification exist via migration `b3d7f1a9c2e4` (§IX). Materialization writer NOT IMPLEMENTED — no row is written yet. Materialization is invoked only as a declared side effect of `FEAT-PROD-004`; Interpretation never decides on its own that some historical cycle is "ready" to materialize. The record is immutable and never recomputed. Building the writer remains subject to the provenance and certification requirements of its downstream contract (§X.9).

### Invalidate Snapshot

- **Actor**: System
- **Trigger**: marks stale
- **Status**: NOT APPLICABLE to cycle records. A cycle-bound `interpretation_cycle_record` is immutable and never invalidated or recomputed. Cache-style invalidation applies only to any optional non-authoritative read cache, which is out of scope for this tranche.

### Generate Simulation

- **Actor**: System
- **Trigger**: produces non-persistent output
- **Status**: NOT IMPLEMENTED.

---

## IX. Derived Schema

The schema declared in this section describes persistence for materialized cycle Interpretation. **As of v1.5, the `interpretation_cycle_record` table exists in the runtime schema and the migration chain (migration `b3d7f1a9c2e4`): the persistence surface is IMPLEMENTED.** No lawful materialization writer exists yet, so no row is written: all current Interpretation outputs are still computed on demand and returned as in-memory dataclasses. Populating this table requires the separately specified materialization slice, invoked only as a declared side effect of `FEAT-PROD-004` (§VIII, §X.9), which is NOT IMPLEMENTED.

### `interpretation_cycle_record`

A **durable, immutable, self-describing** record of one completed economic cycle's Interpretation. It is not a cache: it is authoritative for "what this cycle meant, evaluated against the configuration that governed it," and is never recomputed. It persists the actual economic reference values it interpreted against, so historical review never requires reinterpretation and never reaches across domains to reconstruct configuration.

- `id`: UUID — primary key
- `class_id`: UUID — canonical isolation boundary (shared anchor)
- `payroll_cycle_id`: UUID — the economic-cycle identity produced by `FEAT-PROD-004` (`DOM-PROD-001` §XV); one `interpretation_cycle_record` per `(class_id, payroll_cycle_id)`
- `cycle_started_at`: TIMESTAMPTZ — opening boundary of the closed cycle (UTC)
- `cycle_completed_at`: TIMESTAMPTZ — closing boundary (payroll completion) of the closed cycle (UTC)
- `computed_at`: TIMESTAMPTZ — when Interpretation materialized the record (UTC)
- `reference_configuration`: JSONB — a **versioned, immutable informational projection** of the authoritative economic configuration actually consumed while interpreting the cycle (see below)
- `observations_json`: JSONB — the materialized Descriptive observations and Interpretive signals, each carrying its §IV output-property declarations

##### `reference_configuration` contract

`reference_configuration` is a **versioned snapshot** of the governing economic inputs that were in effect for the cycle, captured at materialization time. Conceptual structure:

```json
{
  "schema_version": 1,
  "economic_engine": {
    "cwi": "...",
    "expected_weekly_hours": "...",
    "hourly_pay_rate": "..."
  },
  "policy": {
    "policy_uuid": "...",
    "version": "..."
  }
}
```

It is:

- an **immutable informational projection** of the authoritative configuration actually consumed during interpretation — a self-contained record of "what governed this cycle,"
- **NOT executable CLASS state** — nothing reads it to make an economic decision; CLASS / `SPEC-ECON-003` remain the sole authority over live configuration,
- **NOT something Interpretation may subsequently resolve, refresh, or recompute** — once written it is frozen with the cycle,
- **versioned** via `schema_version` so the Economic Engine can evolve without schema churn on this table, and so old interpretations stay self-describing under whatever shape was current when they were materialized,
- **NOT a foreign key** into any other domain's table; `policy.policy_uuid` and `policy.version` are stored as informational lineage values only.

#### Cross-domain reference rule

Per `INV-ARC-021` §V.7, the only legal cross-domain FK targets are shared anchors (`class_id`, `seat_id`, `user_id`). `interpretation_cycle_record` therefore:

- MAY hold `class_id` (and `seat_id` where a per-seat record is warranted) as a real anchor,
- holds `payroll_cycle_id` as the economic-cycle identity supplied by the completion FEAT,
- MUST NOT hold an internal FK to another domain's version table (e.g., no `engine_version_id`, no `policy_versions.id`),
- captures the governing economic inputs as a **versioned informational projection** (`reference_configuration` JSONB) so the record is self-describing without a cross-domain join.

#### Immutability

- One record per completed cycle. Append-only; never updated or recomputed.
- Reversals and corrections are reflected in the cycle in which they occur, not by rewriting a prior cycle's record.

---

## X. Edge Case Decisions

1. **Reversals and corrections affect the cycle in which they occur**: they are never applied by rewriting a completed cycle's `interpretation_cycle_record`. A materialized cycle record is immutable (§VII, §IX). On-demand (non-materialized) Interpretation of an open window naturally reflects the latest corrected truth for that window.
2. **Late data does not trigger recomputation of a closed cycle**: a completed `interpretation_cycle_record` is never updated. Facts that arrive after a cycle closes are reflected in the cycle in which they land, not by revising history.
3. **No fabricated data**: Incomplete logs result in incomplete interpretation, not guesses.
4. **Simulations never persist**: Hypothetical data must not contaminate any read cache or the cycle record.
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
| Materialize Cycle Interpretation | SPECIFIED, cycle-bound (§VIII, §IX) | Persistence surface present: `interpretation_cycle_record` table + model + migration `b3d7f1a9c2e4` + schema certification (slice 8.1). Execution path absent: no materialization writer, so no row is written; invoked only as a declared side effect of `FEAT-PROD-004`, which is not built. |
| Generate Simulation | Authorized (§VIII) | No simulation surface. |
| Trend indicators with prior cycle-record source | Authorized (§V) | No prior cycle-record source available yet; `compute_trends` always receives `previous_snapshot=None` and returns `stable`. Unblocked once `interpretation_cycle_record` accrues. |

### XIII.b KNOWN NONCOMPLIANCE — Runtime Violates v1.2 Doctrine

| Element | Doctrinal Requirement | Runtime Behavior |
|---|---|---|
| ~~FEAT name for Compute~~ | ~~Compute Interpretation FEAT is `FEAT-ITR-001` under the Interpretation domain namespace.~~ | **RESOLVED.** Registered as `FEAT-ITR-001` under the `"Interpretation"` domain in `app/feats/base.py`. Consumer sites (`app/utils/analytics_engine.py`, `app/routes/analytics.py`) updated in the same slice. |
| Historical Configuration Binding | §VII requires historical windows to be evaluated against their authoritative historical configuration. | **Contract resolved (§VII, §VIII, §IX):** cycle-bound materialization persists the governing reference values in an immutable `interpretation_cycle_record`, so cycles produced under the contract are self-describing and never reinterpreted. Runtime remains noncompliant only until the record is built; pre-contract cycles are declared **not replayable**, tracked toward zero. |
| Completed-cycle window discipline | §VII requires completed cycles only. | Runtime accepts arbitrary caller-supplied windows without enforcement. |
| Output Property Declaration (INV-ITR-012) | Every output SHALL declare Semantic Kind, Subject / Observation Basis / Aggregation, and Reference Dependency. | Current outputs declare none of these. |
| Provenance via canonical fields (INV-ITR-015) | Classification of Ledger events uses `mechanism`, `feat_code`, `correlation_id`, reversal linkage, and authoritative source-domain event tables. `Transaction.type` is not authoritative. | `Transaction.type` is consulted in some current calculations. |
| Source Domain Precedence (INV-ITR-016) | Authoritative facts consumed directly from owning domains. | `participation_rate` derives from Ledger + Attendance without domain-fact preference; other metrics similar. |
| Threshold Ownership (INV-ITR-017) | Every threshold has an explicit semantic owner; computation and presentation layers do not invent them locally. | **RESOLVED (slice 8.4d).** The duplicated V1 thresholds are retired: `ANALYTICS_POLICY_DEFAULTS`, `analytics_engine.py`, and `app/services/analytics/builders.py` are deleted. The Interpretation surface (SPEC-ITR-001) declares no numeric thresholds; the page presents contract-bound observations and non-prescriptive guiding questions only. |

### XIII.c UNRESOLVED — Cross-Domain Ownership Questions Affecting Interpretation

Items in this section are not Interpretation-owned and cannot be resolved by amending DOM-ITR-001. They are recorded here only so downstream SPEC-ITR-001 work knows what it cannot assume.

| Element | Status |
|---|---|
| Overdraft / NSF fee assessment ownership | **RESOLVED (SPEC-ECON-003 §4.6.1.1).** LEDGER executes the money movement (posts the fee debit) and stays domain-blind (`DOM-LED-001` §II); OBLIGATIONS owns the fine as Economic Context — the NSF fee is an immediate obligation (`DOM-OBL-001` §II.C), recorded by the originating business FEAT's cross-domain orchestration, not by the Ledger primitive. An `AssessmentEvent` (NSF_FEE ASSESSMENT + PAYMENT settled by the fee debit) is now produced, so obligation-outcome observations can include overdraft / NSF. Scope: charged only for a failed purchase or obligation — never for transfers (lateral) or penalties (admin adjustments). Interpretation consumes the OBLIGATIONS fact per INV-ITR-016 and still does not itself decide ownership. |
| ~~Current runtime `suggested_action` alert content~~ | **RESOLVED (slice 8.4d) — by deletion.** The prescriptive alert content, its `generate_alerts` producer, and the V1 analytics engine and dashboard builder that carried it are removed from runtime. The teacher Interpretation page now renders DOM-ITR observations plus non-prescriptive guiding questions only; it prescribes no teacher action. |
