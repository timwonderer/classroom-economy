# FEAT-CLASS-003: Insurance Policy Management

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-CLASS-003 | 0.1 | 2026-07-23 | N/A | Normative |

## I. Purpose

Define the canonical class-configuration workflow for class-level insurance enablement and economic settings.

This FEAT governs:

- toggling the insurance capability at the class level;
- maintaining class-level economic settings that insurance workflows depend on;
- producing student-visible availability notices when insurance is enabled or disabled;
- delegating insurance policy definition changes to `FEAT-POL-001`.

This FEAT owns orchestration only.

It SHALL NOT mutate insurance policy definitions, entitlement records, obligation records, or ledger records directly.

## II. Authority

This FEAT is authorized by:

- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

This FEAT is the sole lawful orchestrator for class-side insurance capability and economics changes.

## III. Required Context

Required canonical context:

- `user_id`
- `class_id`
- `seat_id`
- `actor_role = teacher`

The teacher seat SHALL be lawful for the class boundary.

This FEAT SHALL NOT reconstruct authority from labels, block names, join codes, or route-local state.

## IV. Scope and Model

Class-level insurance configuration is class-scoped enablement and economics.

The canonical class configuration SHALL capture, at minimum:

- class-level insurance enablement;
- class-level economics that insurance workflows depend on;
- teacher-facing notice state for insurance availability;
- any class-scoped settings that influence policy orchestration but are not policy definitions themselves.

This FEAT SHALL NOT add foreign keys from class configuration into entitlement, obligation, or ledger tables.

## V. Insurance Enablement

Insurance enablement SHALL:

1. toggle the insurance capability at the class level;
2. preserve existing downstream facts;
3. control whether insurance-related Policy definitions are reachable from the class UI;
4. emit teacher-visible notices about availability changes.

## VI. Economic Settings

Class-level economic settings SHALL remain under Class Configuration.

These settings MAY be consulted by insurance or rent policy workflows, but they SHALL NOT rewrite Policy definitions.

## VII. Delegation

This FEAT delegates insurance policy creation, update, retirement, and deletion to `FEAT-POL-001`.

## VIII. Guarantees

This FEAT guarantees:

- class-level insurance enablement is explicit;
- class-level economic settings remain under Class Configuration;
- Policy definitions are not mutated here;
- downstream entitlement, obligation, and ledger facts are not rewritten by this FEAT.
