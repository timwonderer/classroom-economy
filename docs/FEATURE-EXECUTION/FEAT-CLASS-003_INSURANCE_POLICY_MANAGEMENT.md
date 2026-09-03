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

This FEAT performs the immutable definition write, availability projection, and
retirement by invoking the **POL definition commands**
(`insurance_definition_service.create_insurance_definition` / `set_availability`)
inside its own single FEAT context. It does NOT execute a separate FEAT — a FEAT
never executes another FEAT; it composes domain commands (FEAT-CORE-000 §V.1,
INV-ARC-000 §VIII.2, INV-ARC-021 §V.2).

## VIII. Tier Groups

A **tier group** is a teacher-named set of mutually-exclusive insurance policies a
student chooses one of (e.g. a "Paycheck Protection" line offered as Basic / Mid /
Premium). A group is not its own table: membership is the `tier_group` label carried
on each `insurance_policies` row, class-scoped.

### 1. Ranks

Grouped tiers occupy the three ordinal ranks `tier_level ∈ {1, 2, 3}` = basic / mid /
premium. An ungrouped ("single") offering carries no `tier_group` (and no group
semantics attach to a bare `tier_level`). A grouped policy MUST carry a rank in
{1,2,3}; a missing or out-of-range rank fails closed.

### 2. Rank uniqueness and the three-tier cap

Within one group, at most one **available (`IN_USE`)** policy may occupy each rank,
so a group holds **at most three** active tiers. Because definitions are immutable
(an edit mints a new `policy_uuid` and retires the old — DOM-POL-001), the constraint
is over `IN_USE` rows only: retired/hidden versions never occupy a slot, and
re-adding a rank after retiring its prior tier is lawful.

Primary enforcement is this FEAT's create-time guard (reject a duplicate `IN_USE`
rank in the group, or a fourth active tier). A partial unique index
`(class_id, tier_group, tier_level) WHERE availability_state = 'IN_USE' AND
tier_group IS NOT NULL` is the concurrent-create backstop.

### 3. Mutual exclusion at purchase

A seat holds at most one active insurance coverage per `tier_group`. This extends
FEAT-OBL-004's single-active-coverage invariant from per-`policy_uuid` to
per-group: purchasing a policy whose group the seat already holds active coverage
in fails closed. Enforcement lives in FEAT-OBL-004 (the purchase authority), not here.

### 4. Rank → economic envelope (advisory)

The Economic Engine (SPEC-ECON-003 §4.5.8) provides per-tier preset envelopes
(reimbursement %, payout multiple, claims/week, window, premium band position). These
are ADVISORY presets a teacher may accept or override; they are not enforced by this
FEAT beyond the hard bounds and per-type structural CHECKs. Bundle/multi-tier discount
is out of scope for this revision.

## IX. Guarantees

This FEAT guarantees:

- class-level insurance enablement is explicit;
- class-level economic settings remain under Class Configuration;
- Policy definitions are not mutated here (a new immutable row per lawful change);
- a tier group holds at most three active tiers, one per rank;
- downstream entitlement, obligation, and ledger facts are not rewritten by this FEAT.
