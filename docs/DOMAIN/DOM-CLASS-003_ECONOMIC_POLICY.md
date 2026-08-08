# DOM-CLASS-003: Economic Policy

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| DOM-CLASS-003 | 2.0 | 2026-05-20 | DOM-CLASS-002 | Constitutional |

# I. Purpose

This specification defines the constitutional governance model for class economics within Classroom Token Hub (CTH).

This specification derives its authority from `DOM-CLASS-002`, which in turn derives from `DOM-CLASS-001`. This document controls only economics-specific policy lineage, not the general policy domain. The broader policy domain owns non-economic policy versioning.

This specification establishes:
- immutable economics policy lineage,
- append-only policy evolution,
- visible future economic law,
- policy activation sovereignty,
- policy supersession legality,
- rebalancing governance,
- economic transparency requirements.

---

# II. Scope

This specification governs:
- economics policy versions,
- policy activation legality,
- economic policy mode semantics for `tight`, `default`, and `comfortable`,
- rebalance governance,
- pending future policy visibility,
- activation intent semantics.

This specification applies to:
- rent policy,
- insurance policy,
- banking policy,
- payroll policy,
- future economy-governed operational domains.

---

# III. Authority Hierarchy

This specification is subordinate to:
- INV-CORE-000
- INV-CORE-001
- INV-ARC-015
- INV-ARC-016
- DOM-CORE-001
- DOM-CLASS-002

This specification is authoritative over:
- economics policy governance,
- policy activation legality,
- economic policy evolution semantics.

This specification does NOT define:
- FEAT orchestration behavior,
- operational execution timing,
- scheduler implementation,
- route-layer mechanics.

`DOM-CLASS-002` remains authoritative for:
- Classroom Wage Index (CWI) definition and canonical derivation formulas
- Policy mode ratio bands (tight / default / comfortable) and economic climate definitions
- Solvency validation formulas (budget survival test, catastrophe stability rule)
- Analytics categories and canonical metrics
- Canonical normalization rules (monthly → weekly, semester → weekly, daily → weekly)

`SPEC-ECON-001` and `SPEC-ECON-002` remain authoritative for savings interest behavior and policy visibility behavior, respectively.

## Related Documents

- `docs/DOMAIN/DOM-CLASS-002_CLASS_ECONOMY_GOVERNANCE.md` — CWI, ratio bands, solvency rules (remains authoritative)
- `docs/SPEC/SPEC-ECON-001_SAVINGS_INTEREST_ACCRUAL_AND_DISBURSEMENT_SPECIFICATION.md` — savings interest accrual and disbursement behavior
- `SPEC-ECON-002_ECONOMIC_POLICY_VISIBILITY_AND_DISCLOSURE.md` — pending policy visibility requirements
- `FEAT-ECON-001_ECONOMIC_POLICY_TRANSITION_EXECUTION_AND_ACTIVATION_ORCHESTRATION.md` — FEAT-layer execution

---

# IV. Constitutional Principles

## ECON-CONST-001 — Economic Policy Evolution Is Append-Only

Class economics MUST evolve through lawful economics policy versions and activation events.

Direct mutation of active economics policy state is prohibited.

All economics policy evolution SHALL be represented as immutable policy lineage.

This includes:
- immediate policy changes,
- delayed policy changes,
- rebalance-generated changes,
- manual administrative policy changes.

---

## ECON-CONST-002 — Economic Policy Versions Are Immutable

Economics policy versions represent constitutional class-economy truth.

Activated policy versions MUST remain immutable.

Historical policy versions MUST remain:
- replayable,
- auditable,
- referentially stable.

Previously active policy versions MUST NOT be modified after replacement.

---

## ECON-CONST-003 — Future Economic Law Must Be Visible

Pending policy versions are considered publicly announced future economic law.

Pending future economic state MUST be visible to:
- teachers,
- affected students,
- operational domains.

Hidden future economic state is prohibited.

---

## ECON-CONST-004 — Operational Domains Own Boundary Legality

Economics policy governance MUST NOT interpret operational timing legality.

Operational domains remain sole authority over:
- cycle closure legality,
- renewal legality,
- accrual legality,
- rollover legality,
- operational boundary interpretation.

Examples:
- Rent domain owns rent cycle legality.
- Insurance domain owns renewal legality.
- Banking domain owns accrual rollover legality.

---

## ECON-CONST-005 — Policy Governance Owns Policy Lineage

Class economics governance remains sole authority over:
- policy version lineage,
- policy transition lineage,
- supersession legality,
- active policy selection,
- pending policy state.

Operational domains MUST NOT directly mutate policy lineage objects.

---

## ECON-CONST-006 — Economic Law Must Be Deterministic

Future economic transitions MUST produce deterministic outcomes.

Policy activation behavior MUST NOT depend on:
- hidden scheduler state,
- mutable delayed payloads,
- undocumented precedence rules,
- implicit operational assumptions.

---

# V. Canonical Objects

## 1. policy_versions

Represents immutable constitutional economics policy truth.

A policy version defines the exact economic rules active for a:

```
(class_id, domain)
```

during a given operational period.

Example fields:

```
id
class_id
domain
version_number
policy_payload_json
created_at
activated_at
created_by_transition_id
is_active
```

Constraints:
- exactly one active policy version per (class_id, domain)
- historical versions MUST remain immutable

---

## 2. policy_transitions

Represents append-only economics policy evolution lineage.

A policy record defines:
- source policy state,
- target policy state,
- activation intent,
- activation legality,
- lineage.

Example fields:

```
id
class_id
domain
source_policy_version_id
target_policy_version_id
activation_mode
status
created_at
created_by
applied_at
correlation_id
superseded_by_transition_id
cancelled_at
```


---

# VI. Policy States

Allowed transition states:

```
pending | applied | cancelled | superseded | failed
```

Definitions:

| State | Meaning |
|---|---|
| pending | Future economic law exists but is not yet active |
| applied | Transition lawfully activated |
| cancelled | Transition intentionally withdrawn |
| superseded | Replaced by newer lawful transition |
| failed | Transition activation failed |

---

# VII. Activation Intent

Economics governance MAY store abstract activation intent.

Allowed activation modes:

```
immediate | next_boundary | manual
```

Definitions:

| Mode | Meaning |
|---|---|
| immediate | Activate immediately |
| next_boundary | Activate at next lawful operational boundary |
| manual | Await explicit activation |

Economics governance MUST NOT encode:
- operational cycle calculations,
- renewal calculations,
- timezone legality,
- operational timing interpretation.

---

# VIII. Policy Supersession

If a newer lawful economics policy version conflicts with an existing pending version:

```
new_transition.created_at > existing_pending_transition.created_at
```

the older version MUST become `superseded`.

The newer lawful version becomes authoritative.

Supersession MUST remain append-only lineage.

Previously recorded policy versions MUST NOT be deleted.

---

# IX. Rebalance Governance

Teacher-visible rebalance operations represent grouped class economics governance actions.

Operationally:
- each selected economic change SHALL create an independent economics policy version,
- each operational domain SHALL retain sovereign activation legality,
- rebalance execution SHALL NOT collapse multiple domains into single mutable state.

Examples:
- rent economics policy version
- insurance economics policy version
- banking economics policy version

Each version remains independently governed.

---

# X. Visibility Requirements

Pending policy versions MUST remain visible through relevant operational surfaces.

Required visibility includes:
- current economic law,
- future economic law,
- activation intent,
- future economic impact.

Affected students MUST be able to view future policy changes affecting:
- obligations,
- premiums,
- pricing,
- recurring economic obligations.

---

# XI. Prohibited Architectural Patterns

The following patterns are constitutionally prohibited.

---

## 1. Hidden Deferred Mutation

Future economic state MUST NOT exist exclusively inside hidden delayed payloads.

Examples:
- `economy_pending_rebalance_json` 

---

## 2. Direct Active Policy Mutation

Active policy versions MUST NOT be mutated directly.

---

## 3. Centralized Operational Timing Interpretation

Economics governance MUST NOT determine:
- rent-cycle legality,
- insurance renewal legality,
- operational rollover legality.

---

## 4. Mutable Singleton Policy Truth

Economics governance MUST NOT rely on:
- singleton mutable settings blobs,
- mutable pending payload pointers,
- overwrite-style future-state mutation.

---

# XII. Relationship to Operational Domains

Operational domains:
- consume active policy versions,
- determine lawful activation boundaries,
- trigger lawful activation requests,
- apply operational consequences.

Operational domains do NOT:
- own policy lineage,
- mutate policy versions,
- determine policy supersession legality.

---

# XIII. Relationship to FEAT Layer

FEAT layer:
- orchestrates execution,
- enforces idempotency,
- coordinates transition application,
- records execution correlation.

FEAT layer does NOT:
- define economic law,
- define policy governance legality,
- define operational timing legality.

---

# XIV. Relationship to DOM-OPS

DOM-OPS owns:
- execution evidence,
- operational telemetry,
- retry traces,
- audit evidence,
- lawful execution observability.

DOM-OPS does NOT own economic policy truth.

---

# XV. Architectural Outcome

This model establishes:
- append-only economic governance,
- immutable economic history,
- visible future economic law,
- deterministic policy evolution,
- sovereign operational timing authority,
- replayable economic policy lineage,
- constitutional economic transparency.

Class economics governance therefore behaves as constitutional system law rather than mutable delayed configuration state.

---

## XVI. Amendment

Revisions to this document must increment the version number, update the effective date, and remain consistent with foundational documentation standards.





