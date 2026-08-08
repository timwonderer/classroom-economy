# DOM-CLASS-001: Class Configuration Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-CLASS-001 | 3.2 | 2026-08-08 | 3.1 | Constitutional |

## I. Purpose

This document defines the class-level configuration boundary for Classroom Token Hub.

Class Configuration answers:

> What class exists, who owns it, what is its operating identity, and what class-level settings define it?

This domain owns the setup that applies to the class as a whole, not the rules for individual classroom domains.

This domain also absorbs the class economy governance and class economic policy lineage previously described elsewhere. The companion class and spec files are supporting slices of this authority, not separate economic namespaces.

## II. Scope

This domain governs:

- `classes`
- `economic-engine`
- `class_features`
- class-level economic configuration
- class creation and deletion workflows

This domain does not govern domain-specific setup such as rent settings, store offerings, insurance policies, payroll rules, or banking rules.

## III. Authority Level

Tier 1 - Constitutional. This document is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `DOM-IDEN-001_CANONICAL_IDENTITY_MODEL.md`

## V. Class-Level Boundary

Class Configuration owns the class boundary and the class-level operating facts used by all other domains.

Owned class-level facts include:

- `class_id`
- `public_class_id`
- `join_code`
- teacher user identity binding
- class display name
- `section`
- `timezone`
- feature enablement
- all class-level economic configuration facts
- feature-gated UI and access state
- class creation and class deletion lifecycle

`timezone` is fixed at class creation and MUST NOT be mutated afterward.

## VI. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `classes`
- `economic-engine`
- `class_features`

`classes` establishes the canonical class boundary.
`economic-engine` stores only the canonical class-level economic configuration facts identified by `DOM-CLASS-002`.
`class_features` stores feature enablement by class.

## VII. Owned Tables

### 1. `classes`

Canonical class boundary records.

Key fields:

- `class_id`
- `join_code`
- `public_class_id`
- `display_name`
- `section`
- `timezone`
- `teacher_user_id`
- `created_at`
- `updated_at`

Rules:

- One record per class.
- `class_id` is the canonical class boundary.
- `public_class_id` is the public alias for the class.
- `join_code` is the teacher-facing or student-facing access code for the class.
- `timezone` is fixed at class creation.
- Class creation establishes the canonical class boundary and all required class-owned configuration rows.
- Class deletion removes the class record and all class-owned configuration rows.

### 2. `economic-engine`

Class-level economic setup and projection state.

Rules:

- One record per class.
- Stores canonical class-level economic configuration facts only.
- The exact persisted fields are derived from `DOM-CLASS-002` and may be refined during the reconstruction.
- The stored state is configuration truth, not operational execution truth.

### 3. `class_features`

Feature enablement by class. Its exact identity and persisted fields are derived
from the feature-state facts established during reconstruction; this document
does not create a surrogate identifier or freeze a legacy column set.

Rules:

- One row per enabled feature per class.
- Absence of a row means the feature is disabled.

## VIII. Constraints

- This domain stores class-level configuration only.
- It owns feature enablement, class identity, and all class-level economic configuration facts.
- It owns the `economic-engine` schema and its projection.
- It does not freeze any derived projection field set before the reconstruction is complete.
- It does not own rent settings, store offerings, insurance definitions, payroll rules, or banking rules.
- It does not mutate ledger, attendance, obligations, or entitlement tables.
- All class-level configuration must be scoped by `class_id`.
- `public_class_id` and `join_code` are display/access aliases and must not replace `class_id` as authority or be used for internal routing or persistence references.
- Feature enablement is class-level capability state, not domain policy state.

## IX. Derived / Cross-Domain Rules

- Other domains consume class-level configuration from this domain.
- `timezone` governs class-level temporal interpretation.
- FEAT orchestration may read class-level configuration, but it does not own it.
- `economic-engine` is a projection of class-level configuration and must not become independent policy truth.
- `economic-engine` must not be treated as an immutable legacy schema contract while reconstruction is in progress.
- Class creation and class deletion are class-level mutation workflows.
- Disabling a feature changes access and display state only; it does not rewrite downstream facts.

## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
