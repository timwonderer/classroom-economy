# FEAT-CLASS-004: Feature Enablement

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-CLASS-004 | 1.0 | 2026-08-09 | N/A | Normative |

---

## I. Purpose

Define the canonical class-configuration workflow for enabling and disabling class features on an append-only timeline.

This FEAT governs:

- enabling a class feature effective at a specific time (immediate or future-dated);
- disabling a class feature effective at a specific time;
- scheduling feature state transitions for future activation (SPEC-ECON-002: future-law visibility);
- producing the feature timeline with soft deletion semantics.

This FEAT is the sole lawful writer for the `class_features` table.

---

## II. Authority

This FEAT is authorized by:

- `DOM-CLASS-001_CANONICAL_CLASS_CONFIGURATION_DOMAIN.md`
- `DOM-CLASS-002_CLASS_ECONOMY_GOVERNANCE.md`
- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `SPEC-ECON-001_ECONOMIC_ENGINE_CONFIGURATION.md`
- `SPEC-ECON-002_FUTURE_LAW_VISIBILITY.md`

This FEAT is the sole lawful orchestrator for all mutations to the `class_features` table.

---

## III. Required Context

Required canonical context:

- `user_id`
- `class_id`
- `seat_id`
- `actor_role = teacher`

The teacher seat SHALL be lawful for the class boundary.

This FEAT SHALL NOT reconstruct authority from labels, block names, join codes, or route-local state.

---

## IV. Data Model

### Owned Table: `class_features`

Primary Key: `(class_id, feature, effective_at)`

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `class_id` | UUID | FK(classes), NOT NULL | Class scope anchor |
| `feature` | String | NOT NULL | Feature identifier (e.g., 'payroll', 'rent', 'hall_pass') |
| `effective_at` | DateTime(UTC) | NOT NULL | When this state becomes/became active |
| `economic_version_id` | UUID | FK(economic_engine), nullable | Which EconomicEngine version enabled this feature (NULL = disabled) |
| `deleted_at` | DateTime(UTC) | nullable | Soft deletion timestamp (INV-ARC-016 audit lineage) |
| `created_at` | DateTime(UTC) | NOT NULL | When this configuration row was created |

**Immutability:** Once inserted, a `class_features` row is immutable (append-only timeline).

---

## V. Primitive Operations

### V.1 Enable Feature

**Command:** Enable a class feature effective at a specified time.

**Required inputs:**
- `class_id`: Class to modify
- `feature`: Feature name (e.g., 'payroll')
- `economic_version_id`: EconomicEngine version that governs this feature (NOT NULL)
- `effective_at`: When this enablement takes effect (default: canonical_now per SPEC-TIME-001)

**Preconditions:**
- `class_id` exists in `classes`
- `economic_version_id` exists in `economic_engine`
- No active feature state at the same `effective_at` for this (class_id, feature) pair
- `effective_at` is not in the past (or within allowed correction window)

**Postconditions:**
- New row inserted in `class_features`: `(class_id, feature, effective_at, economic_version_id, NULL deleted_at, created_at=now)`
- Query `get_class_feature(class_id, feature, effective_at)` returns the new row
- Soft-deleted prior versions remain in table (audit trail)

**Failure contract:**
- `DUPLICATE_STATE`: Row with same (class_id, feature, effective_at) already exists
- `INVALID_ECONOMIC_VERSION`: economic_version_id not found
- `INVALID_CLASS`: class_id not found
- `INVALID_TEMPORAL_ORDER`: effective_at violates temporal constraints

### V.2 Disable Feature

**Command:** Disable a class feature effective at a specified time (soft deletion).

**Required inputs:**
- `class_id`: Class to modify
- `feature`: Feature name
- `effective_at`: When this disablement takes effect (default: canonical_now)

**Preconditions:**
- Feature is currently active (has active row without deleted_at set)
- `effective_at` is not in the past

**Postconditions:**
- New row inserted in `class_features`: `(class_id, feature, effective_at, NULL economic_version_id, deleted_at=now, created_at=now)`
- Query `get_class_feature(class_id, feature, effective_at)` returns None for queries at or after disablement time
- Prior active version remains in table with deleted_at=NULL (audit trail)
- Soft deletion preserves referential integrity (INV-ARC-016)

**Failure contract:**
- `FEATURE_NOT_ENABLED`: No active version found
- `INVALID_CLASS`: class_id not found

---

## VI. Temporal Semantics

Per SPEC-TIME-001 and SPEC-ECON-002:

- `effective_at` determines when feature state becomes active (distinct from `created_at`)
- Example: Created Aug 20, effective Sep 1 (future-law scheduling)
- Example: Created Aug 20, effective Aug 20 (immediate activation)
- Queries use `effective_at` to determine feature state at a point in time
- Soft deletion preserves complete timeline for audit and temporal queries

---

## VII. Guarantees

This FEAT guarantees:

- class feature enablement is explicit and time-scoped;
- feature timeline is append-only and immutable;
- soft deletion preserves audit lineage (INV-ARC-016);
- future-law scheduling is supported (SPEC-ECON-002);
- no feature state mutations occur outside this FEAT.

---

## VIII. Cross-Domain Coordination

This FEAT reads from:

- `classes` — verify class exists
- `economic_engine` — verify engine version exists

This FEAT coordinates with:

- `FEAT-CLASS-005` — Economic engine transitions may require feature updates
- `FEAT-ECON-001` — Economic policy activation may trigger feature changes

---

## IX. Idempotency & Replay

Feature enablement/disablement is **naturally idempotent** on the (class_id, feature, effective_at) tuple:

- Replaying "enable payroll effective 2026-08-20" twice inserts the same primary key row (database constraint prevents duplicates)
- Queries return the same state regardless of replay count

No explicit idempotency token required for basic operations.

---
