# FEAT-LED-000: Canonical Monetary Resolution Workflow

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-LED-000 | 0.2 | 2026-07-18 | 0.1 | Normative |

---

> **Execution-model reconciliation (2026-09, supersedes conflicting wording below).**
> Per the higher-authority execution model (INV-ARC-000 §VIII.2, INV-ARC-021 §V.2)
> and FEAT-CORE-000 §V.1, there is **no FEAT-to-FEAT execution**. FEAT-LED-000 is
> therefore the canonical monetary-resolution **workflow expressed as Ledger domain
> commands** — `build_intended_ledger_plan` / `resolve_intended_ledger_plan` /
> `apply_resolved_ledger_plan` (plain domain functions), plus the LED-001 posting
> command — which a money-moving business FEAT composes **inside its own single FEAT
> context**. Where this document says a business FEAT "uses FEAT-LED-000" or
> "delegates to FEAT-LED-001", read that as *invokes the corresponding Ledger domain
> command*, never as executing a second FEAT.

## I. Purpose

This FEAT defines the canonical orchestration contract that resolves an intended ledger plan into a resolved ledger plan before any ledger mutation is committed.

It exists to separate:

- business intent
- intended ledger construction
- domain authority decisions
- ledger execution

This FEAT does not define business meaning, translate business intent, or construct the initial ledger plan. It defines the canonical resolution workflow that every money-moving business FEAT must use before it delegates to `FEAT-LED-001`.

The resolved plan MUST target the canonical ledger contract:

- class-scoped transaction facts
- immutable insert-only rows
- reconciliation-derived posting state
- snapshot-owned mutable settlement state

---

## II. Canonical Problem Statement

Business features can express monetary intent in many forms, and each such feature must first construct an intended ledger plan:

- a store purchase
- a rent payment
- a fine
- payroll
- an admin adjustment
- interest payout
- a savings transfer

Each of these plans must be resolved against the domains that own monetary truth and policy, and then posted as append-only ledger mutations.

This FEAT defines the canonical ledger plan resolution workflow.

---

## III. Canonical Objects

### 1. Business Intent

The originating business action and its requested money movement.

### 2. Intended Ledger Plan

An immutable representation of the ledger entries a business FEAT intends to create prior to domain resolution.

This object is not authoritative and MUST NOT be posted directly.

### 3. Domain Resolution

The set of read-only decisions returned by domain authorities that govern whether the plan may proceed, must be transformed, or must be denied.

### 4. Resolved Ledger Plan

The authoritative ledger plan after all required domain decisions have been applied.

This object is the only plan eligible for posting by `FEAT-LED-001`.

Resolved plans should carry the final ledger row shape, including:

- `class_id`
- `target_seat_id`
- `actor_seat_id`
- `mechanism`
- `amount_cents`
- `timestamp`
- `account_type`
- `description`
- `correlation_id`
- `feat_code`
- `idempotency_key`
- `policy_id`
- `type`
- lineage fields

---

## IV. Scope

This FEAT applies to all class-scoped business workflows that produce or consume a monetary plan before posting.

This FEAT does not own:

- business policy semantics
- monetary truth
- balance derivation
- ledger posting mechanics
- reversal mechanics
- domain-specific entitlement or obligation semantics

---

## V. Contract Statement

### 1. Promise

Given a resolved `seat_id`, `class_id`, `correlation_id`, `idempotency_key`, an intended ledger plan, and the relevant class-scoped policy inputs, this FEAT MUST return one of the following:

- a resolved ledger plan
- a denial with an auditable reason

### 2. Canonical Workflow

The FEAT MUST:

1. receive an intended ledger plan from the initiating business FEAT
2. resolve the intended plan against the owning domains
3. apply any authorized plan transformation
4. produce a resolved ledger plan or a denial
5. delegate final posting to `FEAT-LED-001`

### 3. Immutable Boundary

This FEAT MUST NOT:

- commit ledger mutations directly
- reinterpret domain truth
- bypass domain authority
- construct the initial intended ledger plan
- decide business meaning outside the plan provided by the initiating FEAT

---

## VI. Inputs

### 1. Required Context

- `user_id`
- `seat_id`
- `class_id`
- `correlation_id`
- `idempotency_key`

### 2. Required Business Intent

- `action_type`
- `amount`
- any business-specific metadata required to build the intended ledger plan

### 3. Required Domain Inputs

- class-scoped banking settings where monetary policy matters
- any other domain-owned read-only inputs needed to validate the plan

---

## VII. Authority Sources

This FEAT MUST derive authority only from:

1. `INV-CORE-000` for class-scoped isolation and deterministic financial logic
2. `INV-CORE-001` for capability-based evaluation at request time
3. `INV-ARC-006` for explicit command boundaries
4. `INV-ARC-008` for seat-scoped identity resolution
5. `INV-ARC-009` for domain-owned state truth
6. `INV-ARC-021` for FEAT-only cross-domain coordination
7. `DOM-CLASS-001` for banking policy inputs
8. `DOM-LED-001` for monetary truth and balance derivation

This FEAT MUST NOT invent authority from:

- route-local logic
- cached state
- prior request outcomes
- label-based heuristics
- business names alone

---

## VIII. Resolution Outcomes

### 1. ACCEPT

The intended ledger plan may proceed unchanged.

### 2. TRANSFORM

The intended ledger plan must be transformed into a different posting shape before execution.

### 3. DENY

The intended ledger plan cannot proceed under current authority.

---

## IX. Orchestration Rules

### 1. Plan Construction

The initiating business FEAT MUST express its monetary intent as an intended ledger plan before invoking this FEAT.

### 2. Domain Resolution

The FEAT MUST evaluate the intended ledger plan against the owning domains using read-only authority checks.

The FEAT MUST NOT:

- mutate domain state during resolution
- infer non-provided business meaning
- bypass a domain's authoritative decision

### 3. Finalization

The FEAT MUST convert the resolved result into a resolved ledger plan before posting.

Only the resolved ledger plan MAY be sent to `FEAT-LED-001`.

### 4. Posting Delegation

`FEAT-LED-001` remains the canonical posting boundary.

This FEAT is upstream of posting and does not replace posting authority.

---

## X. Invariants

1. **Plan Before Posting**: Every monetary action MUST be resolved into a ledger plan before posting.
2. **Domain-Owned Truth**: Only the owning domain may answer questions about its own truth.
3. **Read-Only Resolution**: Resolution MUST be side-effect free.
4. **Resolved Plan Requirement**: Only a resolved plan may be posted.
5. **Single Posting Authority**: Ledger mutation MUST occur through `FEAT-LED-001`.
6. **Business Neutrality**: This FEAT MUST remain business-domain agnostic.

---

## XI. Audit Requirements

The DOM-OPS audit record MUST contain:

- `correlation_id`
- `seat_id`
- `class_id`
- initiating business FEAT identifier
- intended ledger plan summary
- resolution outcome
- resolved plan summary or denial reason

---

## XII. Non-Goals

This FEAT does not:

- define rent semantics
- define store semantics
- define insurance semantics
- define payroll semantics
- define fine semantics
- define admin correction semantics
- define ledger reversal semantics

---

## XIII. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/FEATURE-EXECUTION/FEAT-LED-001_POST_LEDGER_TRANSACTION.md`
- `docs/DOMAIN/DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-008_IDENTITY_RESOLUTION_AND_SEAT_SCOPE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`
