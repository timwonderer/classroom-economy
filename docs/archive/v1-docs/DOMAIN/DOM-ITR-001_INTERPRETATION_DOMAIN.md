# DOM-ITR-001: Interpretation Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-ITR-001      | 1.1     | 2026-04-22     | 1.0        | Normative       |

## I-A. Authority Level and Dependencies

Normative. Subordinate to `INV-CORE-000` and `INV-ARC-009`.

### Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`

---

## I. Purpose

The Interpretation Domain is a read-only meaning layer over authoritative system truth.

It transforms:
*   **Domain events**
*   **System configuration**

into coherent, explainable signals about:
*   **Actor behavior**
*   **System structure**

It does not mutate state, enforce policy, or define correctness.

---

## II. Domain Authority

### Interpretation OWNS Authority Over:
*   **Behavioral signal generation** (actor activity over time).
*   **Structural signal generation** (system configuration evaluation).
*   **Aggregated metrics** over defined time windows.
*   **Trend detection** and drift identification.
*   **Diagnostic explanations** of observed patterns.
*   **Simulation outputs** (non-persistent).
*   **Contextual annotations**.

### Interpretation Explicitly DOES NOT Own:
*   **Financial truth** → Ledger
*   **Obligation truth** → Obligations
*   **Attendance truth** → Attendance
*   **Entitlement balances** → Obligations / Store
*   **System correctness** → Operations
*   **Policy definition or enforcement** → Class Configuration

---

## III. Core Boundary

### Interpretation answers:
*   “What does the current system state mean?”

### It does NOT answer:

| Question | Domain |
| :--- | :--- |
| Is the system correct? | **Operations** |
| Is the system enforced properly? | **Class Configuration** |
| What should happen next? | Teacher / Policy |
| What is the truth? | Source Domains |

---

## IV. Interpretation Axes (Non-Optional)

All outputs MUST belong to exactly one axis.

### 🟦 Axis 1: Behavioral Interpretation
*   **Question**: How are actors behaving within the system?
*   **Subject**: `seat_id`
*   **Input**: Event logs (Ledger, Attendance, Obligations)
*   **Time Model**: Completed payroll cycles only
*   **Nature**: Observational
*   **Examples**: Participation rate, money velocity, engagement level, activity distribution, behavioral drift.

### 🟨 Axis 2: Structural Interpretation (Economy Health)
*   **Question**: Is the system configuration coherent relative to its economic model?
*   **Subject**: `class_id`
*   **Input**: Class Configuration + CWI
*   **Time Model**: Current configuration evaluated per completed cycle
*   **Nature**: Model-based evaluation
*   **Examples**: Pricing bounds, affordability ranges, survivability envelope, budget pressure, policy alignment.

---

## V. State Classification

| State | Classification | Justification |
| :--- | :--- | :--- |
| **Behavioral Metrics** | Derived State | From event logs. |
| **Structural Metrics** | Derived State | From config + CWI. |
| **Trend Series** | Derived State | Time-based aggregation. |
| **Drift Indicators** | Derived State | Comparative. |
| **Diagnostic Views** | Derived State | Composed interpretation. |
| **Simulation Outputs** | Derived State | Hypothetical. |
| **Interpretation Snapshots** | Cache | Performance only. |
| **Annotation Signals** | Derived State | Context only. |

---

## VI. Invariants

### General Invariants
*   **INV-ITR-001: Read-Only Enforcement**: No mutation of any domain state.
*   **INV-ITR-002: Source-of-Truth Dependency**: All outputs must derive from authoritative domains.
*   **INV-ITR-003: Deterministic Reproducibility**: Same inputs + same window → identical outputs.
*   **INV-ITR-004: No Domain Logic Reimplementation**: No re-creating Ledger, Obligations, or Attendance logic.
*   **INV-ITR-005: Correction Awareness**: All reversals, waivers, and corrections must be reflected.
*   **INV-ITR-006: Timezone Integrity**: All time logic uses `ClassTimeZone`.
*   **INV-ITR-007: Explicit Time Windows**: All outputs must define window boundaries and cycle definition.
*   **INV-ITR-008: Non-Authoritative Output**: Interpretation MUST NOT enforce policy, block actions, or mutate configuration.
*   **INV-ITR-009: Actor Dignity Constraint**: No rankings, no exposed identities, no hierarchy signals.
*   **INV-ITR-010: No Policy Authority**: Interpretation evaluates but never enforces.
*   **INV-ITR-011: Cache Integrity**: Caches must be recomputable and invalidated on change.

### Axis Invariants
*   **INV-ITR-012: Axis Exclusivity**: Every metric MUST declare exactly one axis (behavioral or structural). Prohibited: mixing actor behavior with system evaluation; deriving pricing decisions directly from behavior.
*   **INV-ITR-013: No Cross-Axis Authority**: Behavioral outputs MUST NOT define structural outputs.
    *   **Allowed**: Behavioral → suggests drift; Structural → defines bounds.
    *   **Prohibited**: “students aren’t spending → pricing is wrong” as a computed rule.

---

## VII. Temporal Model

### Primary Unit: Payroll Cycle
*   Only completed cycles are evaluated.
*   No rolling windows.
*   No partial-cycle metrics.

### Activation Rules
Interpretation begins only after at least one full completed payroll cycle.

### Reset Conditions
Interpretation MUST reset when:
*   CWI changes.
*   Policy affecting economic pressure changes.

---

## VIII. State Transitions

### Compute Interpretation
*   **Actor**: System
*   **Trigger**: produces derived output

### Materialize Snapshot
*   **Actor**: System
*   **Trigger**: writes cache

### Invalidate Snapshot
*   **Actor**: System
*   **Trigger**: marks stale

### Generate Simulation
*   **Actor**: System
*   **Trigger**: produces non-persistent output

---

## IX. Derived Schema

### `interpretation_snapshots`
*   `id`: UUID
*   `class_id`: UUID
*   `axis`: (behavioral | structural)
*   `cycle_id`: UUID
*   `metric_type`: VARCHAR
*   `window_start`: TIMESTAMPTZ
*   `window_end`: TIMESTAMPTZ
*   `computed_at`: TIMESTAMPTZ
*   `value_payload`: JSONB

### `interpretation_annotations`
*   `id`: UUID
*   `class_id`: UUID
*   `event_type`: VARCHAR
*   `timestamp`: TIMESTAMPTZ
*   `payload`: JSONB

---

## X. Edge Case Decisions

1.  **Reversals override prior signals**: Metrics must reflect the final corrected truth.
2.  **Late data triggers recomputation**: Historical snapshots must be updated.
3.  **No fabricated data**: Incomplete logs result in incomplete interpretation, not guesses.
4.  **Simulations never persist**: Hypothetical data must not contaminate the cache.
5.  **No ranking systems**: The system evaluates behavior and structure, not individuals.
6.  **Interpretation never becomes policy**: The teacher remains the final authority on configuration changes.
7.  **Behavioral and structural signals must remain separated**: As per Axis Exclusivity.

---

## XI. Design North Star

A teacher should be able to answer:
*   “What is happening in my system, and why?”

Without:
*   digging through logs
*   comparing students
*   interpreting raw data

---

## XII. Canonical Mental Model

*   **Behavior** tells you what happened.
*   **Structure** tells you what was possible.
