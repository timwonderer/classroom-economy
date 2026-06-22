# INV-ARC-015: Temporal Model and Boundary Enforcement

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-015      | 1.0     | 2026-04-21     | N/A        | Foundational    |

---

## I. Purpose

Define the canonical temporal model for Classroom Token Hub.

This specification governs how time is interpreted, stored, and enforced across all execution paths.

---

## II. Scope

This specification applies to:

- Timestamp storage and interpretation
- Time-based capability evaluation
- Domain command execution involving time
- Temporal boundaries (e.g., day limits)
- Logging and observability

It is binding on all DOM and FEAT specifications.

---

## III. Authority Level

Foundational within the INV-ARC namespace. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and Section III.3, `Deterministic and Traceable Financial Logic`, and governed within the hierarchy described by `INV-CORE-001`.

---

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-000_EXECUTION_MODEL.md`

---

## V. Core Temporal Model

The system MUST operate under a single canonical temporal model defined as:

1. All timestamps are stored in UTC
2. All temporal evaluation is performed in class-scoped timezone
3. Class timezone is immutable for the lifetime of the class
4. Temporal interpretation of past events MUST NOT change

No deviation from this model is permitted.

---

## VI. Temporal Authority

### VI.1 Class-Scoped Time

- Each class defines a single IANA timezone.
- This timezone is authoritative for all temporal logic.

### VI.2 Prohibited Time Sources

The following MUST NOT influence system behavior:

- Client device time
- Browser locale
- Server local timezone
- Implicit or inferred offsets

---

## VII. Temporal Boundaries

### VII.1 Day Definition

A day is defined as:

> [00:00, 24:00) in class timezone

### VII.2 Boundary Enforcement

- Temporal processes MUST NOT span multiple class days.
- Boundary crossing MUST terminate active processes.
- No carryover across day boundaries is permitted.

---

## VIII. Execution Constraints

### VIII.1 Capability Evaluation

- Time-based capability checks MUST use canonical class time.
- No alternate time derivation is permitted.

### VIII.2 Command Execution

- Domain commands MUST enforce temporal boundaries.
- Commands MUST NOT reinterpret prior timestamps under new context.

---

## IX. Observability Requirements

All time-related logs MUST include:

- UTC timestamp
- Class timezone
- Derived class time

---

## X. Downstream Consequence

DOM specifications MUST:

- Treat time as class-scoped and immutable.
- Enforce boundary rules strictly.

FEAT specifications MUST:

- Not introduce alternate temporal models.
- Not bypass boundary enforcement.

---

## XI. Enforcement

The following MUST be enforced through CI and runtime guards:

- No use of non-UTC storage for timestamps
- No use of non-class time in execution paths
- No cross-boundary temporal continuation
- No mutation of class timezone

---

## XII. Final Statement

> Time is not user-relative.
> Time is not environment-relative.
> Time is class-scoped, immutable, and authoritative.

---

## XIII. Amendment

Revisions to this document must:

1. Increment the version number.
2. Update the Effective Date.
3. Maintain alignment with all INV-CORE specifications.
4. Preserve the canonical temporal model.
