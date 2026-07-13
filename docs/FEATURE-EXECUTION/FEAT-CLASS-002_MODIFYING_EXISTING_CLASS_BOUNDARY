# FEAT-CLASS-002: Modifying Existing Class Boundary

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
| :--- | :--- | :--- | :--- | :--- |
| FEAT-CLASS-002 | 0.1 | 2026-07-12 | N/A | Normative |

---

## I. Purpose

This FEAT defines the canonical workflow for modifying an existing Class Boundary.

Unlike FEAT-CLASS-001, this workflow SHALL execute only within an existing CanonicalContext.

This FEAT defines the constitutional interpretation of roster modifications, including:

- individual student modification;
- manual student provisioning;
- individual student removal;
- bulk roster modification.

This FEAT owns orchestration only.

Persistence and domain ownership remain delegated to their constitutional owners.

---

## II. Authority Sources

### Primary Authority

**DOM-CLASS-001**

Authorizes:

- modification within an existing Class Boundary.

### Supporting Authority

**DOM-IDEN-007**

Authorizes:

- Student Seat provisioning;
- Student Seat removal;
- IdentityProfile modification;
- claim artifact initialization;
- actor_public_id resolution.

---

## III. Execution Context

This workflow SHALL execute only within CanonicalContext.

Required:

- authenticated `user_id`
- `class_id`
- `seat_id`

Derived:

- `actor_role = teacher`

This FEAT SHALL NOT create a new Class Boundary.

---

## IV. Canonical Workflow

### IV.1 Individual Student Modification

Individual student modification SHALL update only:

- First Name;
- Last Name;
- Additional Notes.

These fields SHALL modify the existing IdentityProfile only.

Seat identity SHALL remain unchanged.

---

### IV.2 Manual Student Provisioning

Manual student provisioning SHALL provision exactly one Student Seat.

Teacher supplied inputs SHALL be limited to:

- First Name;
- Last Name;
- Additional Notes.

The following values SHALL be inherited from CanonicalContext:

- class_id;
- current Class Boundary.

Student Users SHALL NOT be provisioned.

Student account creation remains owned by FEAT-IDEN-001.

---

### IV.3 Individual Student Removal

Individual student removal SHALL delegate to the canonical deletion workflow.

The existing deletion confirmation workflow SHALL remain authoritative.

---

### IV.4 Bulk Roster Modification

Bulk roster modification SHALL operate upon an exported canonical roster template representing the current Class Boundary.

The uploaded roster SHALL be interpreted as a deterministic modification request against the exported Class Boundary.

---

## V. Canonical Interpretation

### V.1 Existing Student Resolution

Existing students SHALL be resolved exclusively using `actor_public_id`.

`actor_public_id` SHALL:

- uniquely identify an existing Student Seat;
- be immutable;
- appear exactly once;
- belong to the current Class Boundary.

Modification, duplication, or malformed values SHALL invalidate the uploaded template.

---

### V.2 Existing Student Modification

For existing students, only the following fields SHALL be interpreted:

- First Name;
- Last Name;
- Additional Notes.

These values SHALL overwrite the corresponding IdentityProfile values.

The following fields SHALL be informational only:

- Class Name;
- Section.

These fields SHALL NOT:

- modify Class configuration;
- modify Class identity;
- determine Student membership.

---

### V.3 Existing Student Removal

If an exported `actor_public_id` is absent from the uploaded roster, the omission SHALL be interpreted as an intent to remove that Student from the current Class Boundary.

Before removal, the workflow SHALL present the proposed removals for explicit teacher confirmation.

Confirmed removals SHALL delegate to the canonical seat deletion workflow.

---

### V.4 New Student Provisioning

The exported roster SHALL contain a structural boundary marker separating:

- existing Students;
- proposed new Students.

Rows below the structural boundary marker SHALL be interpreted as new Student provisioning requests.

Only the following fields SHALL be consumed:

- First Name;
- Last Name;
- Additional Notes.

All remaining values SHALL be ignored.

Each accepted row SHALL provision:

- one Student Seat;
- one IdentityProfile;
- required claim artifacts.

Student Users SHALL NOT be provisioned.

---

### V.5 Structural Boundary Marker

The structural boundary marker SHALL contain the template metadata required for validation.

The marker SHALL separate:

- existing Students; and
- proposed new Students.

Modification, removal, duplication, or corruption of the structural boundary marker SHALL invalidate the template.

---

### V.6 Duplicate Claim Names

Existing Students SHALL NOT participate in duplicate claim validation.

Duplicate validation SHALL occur only among newly provisioned Students within the current upload batch.

If duplicate claim names are detected, provisioning SHALL pause until explicit teacher resolution.

Teacher resolution SHALL provide one of the following constitutional outcomes:

1. Update claim names until uniqueness is achieved; or
2. Generate claim deduplication codes for the affected Students.

Provisioning SHALL NOT continue until one of the above outcomes has completed successfully.

---

## VI. Failure

Template validation SHALL complete before any roster modification occurs.

The workflow SHALL reject templates containing:

- invalid structural metadata;
- invalid structural boundary markers;
- duplicate `actor_public_id` values;
- modified `actor_public_id` values;
- malformed `actor_public_id` values;
- unsupported template versions.

The workflow SHALL either:

- complete successfully; or
- reject the modification request.

No partial roster modification SHALL persist.

---

## VII. Delegation

This FEAT delegates constitutional ownership to:

- DOM-CLASS-001
- DOM-IDEN-007
- FEAT-IDEN-001
- FEAT-CORE-000

---

## VIII. Constitutional Guarantees

This FEAT guarantees:

- Class Boundaries are never created by this workflow.
- Existing Student Seats are resolved exclusively by `actor_public_id`.
- IdentityProfile modification never changes Seat identity.
- Student Users are never provisioned.
- Every newly provisioned Student Seat belongs to the current Class Boundary.
- Student removal always requires explicit teacher confirmation.
- Bulk roster interpretation remains deterministic.
- Parser behavior SHALL never infer teacher intent beyond the constitutional rules defined by this FEAT.