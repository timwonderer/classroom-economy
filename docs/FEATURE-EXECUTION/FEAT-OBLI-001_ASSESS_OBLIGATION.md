# FEAT-OBLI-001: Assess Obligation

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-OBLI-001 | 1.1 | 2026-07-24 | 1.0 | Normative |

---

## I. Purpose

This FEAT orchestrates lawful obligation creation. It creates the immutable obligation event row with `event_type = ASSESSMENT` and, when the caller is also performing settlement in the same workflow, coordinates the lawful satisfaction handoff to `FEAT-OBL-003`.

---

## II. Execution Context

### 1. Required Inputs
* `seat_id`: The target student seat.
* `internal_ref`: Stable reference for the continuing obligation-producing relationship.
* `correlation_id`: Unique identifier for the individual liability instance.
* `source_ref`: Opaque upstream authority reference supplied by the owning domain.
* `source_version_ref`: Immutable version snapshot reference supplied by the owning domain.
* `obligation_type`: Lawful assessment category.
* `due_at`: Contractual due boundary for the assessment.
* `viewable_at`: Optional visibility boundary for the assessment.
* `idempotency_key`: Unique request identifier.

### 2. Resolved Context (MANDATORY)
* `class_id`: Resolved via `seat_id`.
* `actor_seat_id`: Resolved from the lawful caller context when required.

---

## III. Orchestration Logic

### 1. Verification Phase (Read-Only)
1. **Scope Validation**: Verify the assessment is valid for the target `seat_id` and `class_id`.
2. **Lineage Validation**: Verify the supplied `internal_ref`, `source_ref`, and `source_version_ref` are lawful for the owning domain.
3. **Temporal Validation**: Verify the requested `due_at` and `viewable_at` satisfy the authoritative temporal boundary contract.

### 2. Mutation Phase (Atomic Transaction)
1. **Assessment Recording**:
    * Call `DOM-OBL` to create an immutable `ASSESSMENT` event row.
2. **Fulfillment Attempt**:
    * If the lawful caller requests settlement in the same workflow, delegate to `FEAT-OBL-003`.
3. **Audit Trace**:
    * Emit `ACT-OBLI-001` via `DOM-OPS` with mandatory `correlation_id`.

---

## IV. Invariants & Constraints

1. **Atomic Assessment**: An obligation MUST NOT be created without an accompanying immutable assessment event.
2. **State Consistency**: If settlement is requested in the same workflow, the satisfaction FEAT MUST reference the lawful Ledger transaction for `PAYMENT` or record a waiver with no Ledger effect.
3. **Idempotency**: Retrying an assessment with the same lawful lineage and `idempotency_key` MUST NOT create duplicate assessments.

---

## V. Audit Requirements

The `DOM-OPS` audit log MUST contain:
* `correlation_id`
* `seat_id`
* `internal_ref`
* `obligation_type`
* `outcome`: (ASSESSMENT | PAYMENT | WAIVED)

---

## VI. Dependencies

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`
- `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md`
