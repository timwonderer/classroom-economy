# FEAT-CLASS-005: Economic Engine Evolution

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-CLASS-005 | 1.0 | 2026-08-09 | N/A | Normative |

---

## I. Purpose

Define the canonical class-configuration workflow for evolving a class's economic policy through immutable, versioned economic engines.

This FEAT governs:

- creating a new EconomicEngine version with new policy parameters;
- transitioning a class feature to use a new economic engine version;
- scheduling policy transitions for future activation (SPEC-ECON-002: future-law visibility);
- preserving complete audit trail of all economic policy versions (INV-ARC-016).

This FEAT is the sole lawful writer for the `economic_engine` table.

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

This FEAT is the sole lawful orchestrator for all mutations to the `economic_engine` table.

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

### Owned Table: `economic_engine`

Primary Key: `economic_version_id` (UUID)

| Column | Type | Constraint | Purpose |
|--------|------|-----------|---------|
| `economic_version_id` | UUID | PK, NOT NULL | Immutable version identifier |
| `class_id` | UUID | FK(classes), NOT NULL | Class this engine governs |
| `economy_policy_mode` | String | NOT NULL | Economic mode ('tight', 'default', 'comfortable') |
| `previous_version_id` | UUID | FK(economic_engine), nullable | Link to prior version (audit lineage) |
| `created_at` | DateTime(UTC) | NOT NULL | When this version was created |

**Immutability:** Once inserted, an `economic_engine` row is immutable (versioned history).

**Version Chain:** `previous_version_id` FK creates audit trail (`INV-ARC-016: Lawful Existence and Audit Lineage`).

---

## V. Primitive Operations

### V.1 Transition Economic Policy

**Command:** Create a new EconomicEngine version and link it to class features via `class_features` timeline.

**Required inputs:**
- `class_id`: Class to modify
- `new_policy_mode`: Target mode ('tight', 'default', 'comfortable')
- `effective_at`: When this policy transition takes effect (default: canonical_now per SPEC-TIME-001)
- `feature_list`: List of features affected by this transition (e.g., ['payroll', 'rent'])

**Preconditions:**
- `class_id` exists in `classes`
- `new_policy_mode` is one of ('tight', 'default', 'comfortable')
- All features in `feature_list` currently exist and are enabled
- `effective_at` is not in the past (or within allowed correction window)

**Postconditions:**
- New row inserted in `economic_engine`: `(economic_version_id=NEW_UUID, class_id, economy_policy_mode=new_policy_mode, previous_version_id=CURRENT_ENGINE_ID, created_at=now)`
- For each feature in `feature_list`: new row inserted in `class_features` linking the new engine version: `(class_id, feature, effective_at, economic_version_id=NEW_ENGINE_ID, deleted_at=NULL, created_at=now)`
- Query `get_effective_economic_engine(class_id, feature, effective_at)` returns the new engine version for all affected features
- Prior engine versions remain in table (audit trail)

**Failure contract:**
- `INVALID_POLICY_MODE`: new_policy_mode not in allowed values
- `CLASS_NOT_FOUND`: class_id not found
- `FEATURE_NOT_ENABLED`: One or more features in feature_list not currently enabled
- `INVALID_TEMPORAL_ORDER`: effective_at violates temporal constraints
- `INVALID_EFFECTIVE_AT`: effective_at is not a valid ISO 8601 datetime
- `NO_CURRENT_ENGINE`: No economic engine version found for class
- `INVALID_CONTEXT`: Missing canonical context
- `CLASS_SCOPE_MISMATCH`: class_id does not match canonical context
- `UNAUTHORIZED`: Actor is not a teacher
- `SEAT_NOT_FOUND`: Teacher seat not found
- `INVALID_FEATURE`: Feature name not in valid feature set
- `INVALID_FEATURE_LIST`: feature_list must be a non-empty list

---

## VI. Temporal Semantics

Per SPEC-TIME-001 and SPEC-ECON-002:

- `effective_at` (in `class_features`) determines when economic engine version becomes active
- `created_at` (in `economic_engine`) records when the version was authored
- Example: Engine created Aug 20, effective Sep 1 (teacher schedules policy change)
- Example: Engine created Aug 20, effective Aug 20 (immediate activation)
- Queries use `effective_at` in `class_features` to determine which engine governs at a point in time
- Version chain via `previous_version_id` preserves complete policy history

---

## VII. Guarantees

This FEAT guarantees:

- economic engine versions are immutable and versioned;
- policy transitions are time-scoped and explicit;
- complete audit trail of all policy versions preserved (INV-ARC-016);
- future-law scheduling is supported (SPEC-ECON-002);
- version chain enables temporal queries and analysis;
- no economic engine mutations occur outside this FEAT.

---

## VIII. Cross-Domain Coordination

This FEAT writes to:

- `economic_engine` — create immutable version row
- `class_features` — link features to new engine version

This FEAT reads from:

- `classes` — verify class exists
- `class_features` — verify current feature state and engine

This FEAT coordinates with:

- `FEAT-CLASS-004` — Feature enablement may trigger engine creation
- `FEAT-CLASS-001` — Class creation requires initial engine version
- `FEAT-ECON-001` — Economic policy orchestration may delegate to this FEAT

---

## IX. Atomicity & Transaction Boundary

Economic policy transitions SHALL execute atomically:

- Creation of new `economic_engine` row
- Insertion of all affected `class_features` rows linking to new engine

If any operation fails, entire transaction rolls back. Partial updates are forbidden.

---

## X. Idempotency

Policy transitions are naturally idempotent on the (class_id, feature, effective_at) tuple:

- Replaying "transition to 'default' mode effective 2026-08-20 for [payroll]" twice:
  - First replay: creates engine + class_features rows
  - Second replay: attempts to insert duplicate primary key in `class_features` (database constraint prevents duplicates)
  - Both replays result in same final state

No explicit idempotency token required for basic operations. Replay safety is guaranteed by primary key uniqueness.

---
