# DOM-CORE-002: Canonical Schema Definition

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-CORE-002     | 1.6     | 2026-07-15     | 1.5        | Constitutional |

---

## I. Purpose

To define the **canonical runtime schema** of the system as a direct expression of domain authority.

This document defines the **only valid set of runtime tables**, their responsibilities, and their structural constraints.

---

## II. Scope

This document applies to all runtime tables supporting:

- Identity and class binding
- Economic activity and financial recording
- Attendance and mobility tracking
- Obligation lifecycle and entitlement issuance
- Store interaction and redemption
- Operational observability and audit
- Interpretation and analytics
- Support and communication systems

---

## III. Authority

Foundational. Subordinate to `INV-CORE-000`, `INV-CORE-001`, and `DOM-CORE-000`.

### Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/DOMAIN/DOM-CORE-000_DOMAIN_FOUNDATION.md`

This document is the authoritative definition of the V2 runtime schema.

- The runtime schema **consists exclusively of the tables defined in this document**.
- Any deviation in implementation is considered **non-compliant**.
- The presence of additional tables in the database does not grant them validity.

---

## IV. Global Schema Invariants

### 1. Seat-Scoped Isolation

All class-scoped state is anchored to:

- `seat_id` (actor scope)
- `class_id` (universe boundary)

No table relies on indirect or inferred scope.

---

### 2. Domain Ownership

Each table has exactly one owning domain.

- Only the owning domain defines constraints and mutation authority
- Cross-domain access does not imply shared ownership

---

### 3. Event-Log Authority

Authoritative state is represented as:

- Immutable event records, or
- Explicit state tables derived from those events

No implicit state exists.

---

### 4. Domain Blindness (Ledger Constraint)

The Ledger domain does not encode business meaning.

- No policy identifiers
- No product abstractions
- No domain-specific classification beyond operational category

---

### 5. No Label-Based Authority

Fields such as:

- `block`
- `period`
- any human-readable grouping label

are not used for:

- scoping
- uniqueness constraints
- identity resolution

Labels are metadata only.

---

### 6. Global Idempotency

All write operations include:

- `idempotency_key`

The system guarantees:

- no duplicate side effects
- deterministic replay safety

---

### 7. Class Scope Resolution

`join_code` is a user-facing alias only.

- It is not used for internal scoping
- All internal relationships resolve through `class_id`

---

## V. Canonical Domain Tables

---

### 1. Identity & Class Binding (DOM-IDEN-001)

**Purpose:** Define global identity and class-local actor binding.

**Tables:**

- `users` — global login principal; `user_role ∈ {STUDENT, TEACHER, SYSADMIN}`
- `seats` — class-local participant binding; `role ∈ {STUDENT, TEACHER}`
- `classes` — class universe anchor; `class_id` (UUID) is the canonical boundary
- `identity_profiles` — display identity; one-to-one with `seats`

**Composition tables** (EXTINCT TABLES - FOR REMOVAL):

- `user_invite_tokens` — short-lived provisioning tokens for teacher account creation; CASCADE-deleted on first use
> In V2, teacher self create accounts without invite code. This table is now obsolete.

- `user_recovery_tokens` — time-limited credential recovery tokens; CASCADE-deleted on redemption
> In V2, teacher account is recovered by student consensus model per DOM-IDEN-003_TEACHER_IDENTITY_ARCHITECTURE. Student account is recovered by teacher-issued recovery code per DOM-IDEN-002_STUDENT_IDENTITY_ARCHITECTURE. This table is now obsolete

**Invariant:** `User.user_role = SYSADMIN` is the sole expression of system-administrator
identity. No separate `system_admins`, `admin_credentials`, or
`system_admin_credentials` table may define identity authority.

**Migration note:** Legacy split credential tables such as `teacher_credentials` and
`system_admin_credentials` are migration artifacts only. They do not define runtime
authority in v2 and must not be treated as canonical schema surfaces.

**Recovery and authentication tables** (owned by DOM-IDEN-003):

- `recovery_requests` — teacher credential recovery lifecycle; at most one pending per user
- `student_recovery_codes` — per-student verification codes; child of `recovery_requests`, CASCADE-deleted
- `passkey_credentials` — WebAuthn/FIDO2 credential bindings; owned by `users.id`

---

### 2. Class Configuration (DOM-CLASS-001)

**Purpose:** Define class-level directives, feature enablement, and class-owned configuration.

**Tables:**

- `class_features`
- `economic-engine` — class-level economic configuration and projection state

Policy definition tables — `rent_settings`, `payroll_settings`, `payroll_rewards`, `payroll_fines`, `hall_pass_settings`, `store_items`, `store_item_visibility`, and insurance policy definitions — are **not** Class Configuration authority. They are stored in the Policies repository (`DOM-POL-001`) as immutable, append-only version rows. Policies does not originate mutations; the domain that initiates a change (Class Config UI submissions, insurance authoring, store curation, etc.) submits a new definition and Policies records it under a new `policy_uuid`. The consuming operational domain — `DOM-OBL-001` for rent, `DOM-PROD-001` for payroll and hall-pass, `DOM-STORE-001` for store/entitlements, the Insurance operational flow for insurance — reads the current `policy_uuid` and owns only the operational facts that result (bill cycles, payroll events, hall-pass logs, entitlement events, etc.). See `DOM-POL-001` §V and §X.

`banking_settings` (savings APY, overdraft fees, interest calculation, disbursement schedule) is **not** a policy repository concern. Its content is inherently Class Configuration → `economic-engine` business, governed by `DOM-CLASS-001` (schema ownership) and `DOM-CLASS-002` (economy governance: interest formulas, overdraft behavior). Class-level economic evolution is versioned under `DOM-CLASS-003` (policy_versions / policy_transitions), not through the Policies repository.

**Prohibited:** No persisted compute-result caches (e.g., `payroll_cache`). Computed values are derived on read from authoritative event tables or recomputed by services.

---

### 3. Productivity & Payroll (DOM-PROD-001)

**Purpose:** Record productivity participation facts, approved hall-pass consumption, and payroll business events.

**Tables:**

- `attendance_sessions`
- `hall_pass_logs`
- `payroll_event`

---

### 4. Obligations & Entitlements (DOM-OBL-001)

**Purpose:** Manage seat-scoped debt lifecycle and recurring reminder state.

**Tables:**

- `bill_cycles`
- `assessment_events`
- `obligation_satisfaction`

---

### 5. Ledger & Money (DOM-LED-001)

**Purpose:** Record all monetary movement.

**Tables:**

- `ledger_transaction`
- `ledger_balance_snapshot`

**Constraints:**

- Anchored to `seat_id`
- Does not store `join_code`
- Enforces `idempotency_key`
- Remains domain-blind

---

### 6. Store & Redemption (DOM-STORE-001)

**Purpose:** Manage entitlement grant lineage, entitlement exercise lineage, and pending entitlement actions.

**Tables:**

- `entitlement_events`
- `pending_actions`

---

### 7. Operations & Observability (DOM-OPS-001)

**Purpose:** Record system behavior, health, and audit trace.

**Tables:**

- `operational_events`
- `audit_events`
- `chain_heads`
- `incident_events`
- `incident_summary`
- `alert_events`
- `invariant_run_events`
- `job_events`
- `health_check_events`

---

### 8. Interpretation (DOM-ITR-001)

**Purpose:** Derive behavioral and structural insights.

**Tables:**

- `interpretation_snapshots`
- `interpretation_annotations`

**Constraint:**

- Read-only domain

---

### 9. Support & Communication (DOM-SUP-001)

**Purpose:** Manage issue lifecycle and system communication.

**Tables:**

- `issues`
- `issue_status_history`
- `issue_resolution_actions`
- `ticket_correlation_pack`
- `announcements`
- `issue_categories`

---

### 10. Economic Policy (DOM-CLASS-003)

**Purpose:** Record policy versioning and transition lifecycle.

**Tables:**

- `policy_versions`
- `policy_transitions`

---

### 11. Policies (DOM-POL-001)

**Purpose:** Serve as an append-only, immutable repository of class-scoped policy definitions that other domains reference by `policy_uuid`. Policies is the newest domain in the list and does **not** own mutation flows — it stores the immutable version references that operational and configuration domains produce and consume. The act of "changing rent" lives in the domain that initiates it; Policies just records the resulting immutable definition row and hands back a stable `policy_uuid`.

**Tables (per `DOM-POL-001` §X boundary attribution):**

- `rent_settings` — rent policy definitions (rate, cycle length, effective boundaries) as append-only version rows; consumed by `DOM-OBL-001`
- `payroll_settings`, `payroll_rewards`, `payroll_fines` — payroll policy definitions (wage rate, frequency, reward/fine catalog); consumed by `DOM-PROD-001`
- `hall_pass_settings` — hall-pass policy definitions (allowed destinations, limits); consumed by `DOM-PROD-001` at grant time
- `store_items`, `store_item_visibility` — purchasable / rent-linked entitlement offering definitions and per-class visibility; consumed by `DOM-STORE-001`
- Insurance policy definitions (see Insurance-domain specs for exact table); consumed by the Insurance operational flow

**Not in this repository:**

- `banking_settings` — Class Configuration → `economic-engine` concern (interest, overdraft). See `DOM-CLASS-001` and `DOM-CLASS-002`.

**Boundary notes:**

- Policies does not originate mutations. Other domains submit definitions through Policies; each submission creates a new `policy_uuid` (see `DOM-POL-001` §VI, Insert and Availability Contract).
- Rows are immutable after insert. Replacement is a new row, never an in-place edit. Mutable-singleton settings blobs are prohibited under `DOM-CLASS-003` §V.
- Downstream domains reference `policy_uuid` as a non-FK provenance locator and freeze any terms they need for standalone executability (see `DOM-POL-001` §V.A, §IX).
- Rent example: Class Configuration owns the `rent` feature flag (`class_features`); Policies stores the immutable `rent_settings` version rows; Obligations (`DOM-OBL-001`) owns `bill_cycles` and `assessment_events` (the recurring act of charging rent) and references the current rent `policy_uuid` for provenance.
- Payroll example: Class Configuration owns the `payroll` feature flag; Policies stores `payroll_settings` / `payroll_rewards` / `payroll_fines` version rows; `DOM-PROD-001` owns `payroll_event` and references the current payroll `policy_uuid` at run time.
- Hall-pass example: Class Configuration owns the `hall_pass` feature flag; Policies stores `hall_pass_settings` version rows; `DOM-PROD-001` owns `hall_pass_logs` and reads the current hall-pass `policy_uuid` at grant time to constrain what may be written.

---

## VI. Explicit Prohibitions

The following do not exist in the V2 schema:

1. Separate identity tables for roles (e.g., `students`, `teachers`)
2. Label-based scoping tables
3. Cross-domain mutation through direct table access
4. Business meaning encoded in the Ledger domain
5. Duplicate authority paths for the same concept
6. Internal scoping via `class_id` only; `join_code` is ingress-only alias metadata

---

## VII. Compliance

Only the tables defined in this document are valid within the V2 system.

No additional tables may be introduced without amendment to this document.

---

## VIII. Amendment

Any modification to the canonical schema requires:

- Version increment
- Updated Effective Date
- Explicit justification tied to domain authority
