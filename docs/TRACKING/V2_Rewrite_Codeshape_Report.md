# Classroom Token Hub — V2 Rewrite: Architecture Report

**Branch:** `codex/v2.0`  
**As of:** 2026-05-11  
**Status:** Active stabilization; pre-launch

---

## 1. What This System Is

Classroom Token Hub (CTH) is a classroom banking simulation where teachers run one or more class periods (isolated economic universes), and students earn payroll, pay rent, buy items, transfer funds, and interact with insurance and attendance workflows.

Runtime stack observed in code:

- Flask app factory (`app/__init__.py`)
- SQLAlchemy ORM models (`app/models.py`)
- Blueprints in `app/routes/` (`admin`, `student`, `api`, `system_admin`, `analytics`, `docs`, `main`, `recovery`)
- Alembic migrations (`migrations/`)
- Pytest test suite (`tests/`)

---

## 2. Why V2 Exists (Grounded in Existing Docs and Code)

The v2 rewrite is a response to documented architecture violations in prior/legacy patterns, including:

1. GET routes performing writes (`INV-ARC-007` violations)
2. Route-local business logic and mutation orchestration
3. Teacher/global scope being used where class scope should be authoritative
4. Incomplete separation between identity, domain authority, and mutation execution

This is captured in:

- `docs/SPECS/V2_CAPABILITY-BASED_ARCHITECTURE_REBUILD.md`
- `docs/archive/v1-development/tracking/V2_Compliance_Validation_Report.md`
- `docs/TRACKING/V2_Full_compliance_migration_plan.md`

The rewrite direction is intentionally constitutional: **INV → DOM → FEAT**.

---

## 3. Normative Authority Stack

### 3.1 INV (Invariants)

Core and architecture invariants are defined under:

- `docs/INVARIANT/CORE/`
- `docs/INVARIANT/ARCHITECTURE/`

Key rules enforced by design:

- Strict class isolation (`join_code` / `class_id`)
- Capability-based permission evaluation at request time
- No cross-domain mutation shortcuts
- GET handlers must be pure (`INV-ARC-007`)
- Explicit mutation command boundaries (`INV-ARC-006`)

### 3.2 DOM (Domains)

Domain authority docs in:

- `docs/DOMAIN/`

`DOM-CORE-001` and `DOM-CORE-002` establish:

- Sovereign domain ownership of tables/state
- Canonical runtime schema target (44 tables)
- Domain contracts and boundaries

### 3.3 FEAT (Feature Execution Layer)

Execution contract in:

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`

FEATs are the only legal mutation path, and must:

1. Resolve context (`user_id`, `seat_id`, `class_id`)
2. Perform read-only validation guards first
3. Execute mutations atomically in one transaction boundary
4. Emit auditable execution traces

---

## 4. Code Shape Snapshot (Current Reality)

### 4.1 Top-level runtime structure

- `app/routes/` — HTTP surfaces
- `app/services/` — domain-bounded service logic
- `app/feats/` — mutation orchestration and FEAT wrappers
- `app/access/` — scoped context model + scope factory
- `app/utils/` — compatibility and helper modules
- `app/models.py` — active mixed-era model layer (legacy + v2 canonical transition)

### 4.2 FEAT layer (actual files)

Observed in `app/feats/`:

- `admin_adjustment_feat.py`
- `insurance_claim_feat.py`
- `insurance_purchase_feat.py`
- `rent_cycle_feat.py`
- `rent_payment_feat.py`
- `store_purchase_feat.py`
- `transaction_void_feat.py`
- `transfer_feat.py`
- `base.py`

### 4.3 Services layer (actual files)

Observed in `app/services/`:

- `access_policy_service.py`
- `attendance_service.py`
- `audit_service.py`
- `balance_service.py`
- `identity_service.py`
- `ledger_service.py`
- `obligations_service.py`
- `store_service.py`
- `tlcp.py`

### 4.4 Scope model in code

`app/access/scope.py` defines a concrete request scope shape:

- `class_id`
- `join_code`
- `actor_id`
- `role`
- `teacher_id`
- `block`
- `seat_id`

`app/access/scope_factory.py` resolves/stores class context from runtime/session state.

---

## 5. Identity Architecture (Target vs Transitional Runtime)

Canonical target (from docs):

1. **User** = global auth/security identity
2. **Seat** = class-local actor identity
3. **Class** = economy universe boundary
4. **IdentityProfile** = human-facing display identity

Authoritative references:

- `docs/SPECS/V2_STUDENT_IDENTITY_ARCHITECTURE.md`
- `docs/DOMAIN/DOM-IDEN-001_IDENTITY_CLASS_BINDING_DOMAIN.md`

Observed transitional runtime:

- `User`, `Seat`, and `ClassEconomy` classes are present
- Legacy auth models (`Admin`, `Student`, etc.) still exist and remain active in many paths
- Dual-scoped columns still exist broadly (legacy keys + v2 keys in same model/tables during migration)

Implication: this branch is in an intentional mixed-state migration lane, not at canonical end-state yet.

---

## 6. FEAT Enforcement Mechanism (Actual Implementation)

`app/feats/base.py` currently provides the enforcement spine:

- `FEAT_REGISTRY`
- `FEATContext` context manager
- `requires_feat_context()` decorator
- `feat_shell()` legacy containment wrapper
- SQLAlchemy mutation tripwires (`before_flush` / `before_commit` support via init hooks)
- guard reason enums and correlation/idempotency handling

Behavioral intent in code:

- Mutation should occur under active FEAT context only
- Non-FEAT writes are warned/blocked by integrity checks
- Blast-radius and idempotency checks are explicit

Notable tracked gap from compliance report:

- `FEAT-OBL-002` usage exists in `rent_cycle_feat.py`, but registry mismatch was flagged as a critical failure in compliance tracking.

---

## 7. Domain Summary (From Constitutional Domain Docs)

Per `DOM-CORE-001`, v2 formalizes nine domains:

1. Identity & Class Binding
2. Class Configuration
3. Attendance & Hall Passes
4. Obligations & Assessments
5. Ledger & Money
6. Store & Entitlements
7. Operations
8. Interpretation
9. Support & Communication

Key domain-design justifications:

- Domain sovereignty: one owner per truth boundary
- Event-log authority for critical state
- Clear split between directives (policy) vs execution facts
- Ledger blindness to business semantics (money as abstract debits/credits)
- Cross-domain coordination only at FEAT boundary

---

## 8. Ledger and Money Authority

Docs:

- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
- `docs/SPECS/V2_BANKING_LEDGER_SETTLEMENT_PLAN.md`

Grounded current design direction:

- `ledger_service` is intended mutation authority for transaction writes
- Balance snapshots/caches are non-authoritative optimization layers
- Idempotency and correlation are first-class for safety/replay control
- Future rebuild plan targets strict `class_id + seat_id + account_type` ledger authority and incremental settlement

---

## 9. Guardrails (What Prevents Regression)

### 9.1 Architectural guardrails

- Invariant hierarchy (INV/DOM/FEAT docs) defines non-negotiable boundaries
- FEAT-only mutation model (constitutional requirement)
- Class/seat scoping model as default query boundary

### 9.2 Runtime guardrails

- FEAT context checks in `app/feats/base.py`
- scoped access checks via `app/services/access_policy_service.py`
- scope objects in `app/access/`

### 9.3 Tracking/validation guardrails

- `docs/archive/v1-development/tracking/V2_Compliance_Validation_Report.md`
- `docs/TRACKING/V2_Full_compliance_migration_plan.md`
- ongoing wave gates and explicit invariant compliance audits

---

## 10. Current Compliance Reality (Not Just Target-State)

From `V2_Compliance_Validation_Report.md`:

- 13 PASS, 2 PARTIAL, 1 critical FAIL (for validated claims at report date)
- Explicit P0/P1 findings remain, including GET mutation violations and FEAT registry/execution inconsistencies

Interpretation:

- The v2 constitutional layer is largely defined and partially enforced in runtime
- The branch remains an active migration/stabilization branch, with known non-compliances tracked and prioritized

---

## 11. Migration Program Status (Waves)

`V2_Full_compliance_migration_plan.md` defines a 12-wave program:

- Waves 1–2 foundational/squash work
- Waves 3–10 domain-by-domain canonicalization
- Wave 11 hardening/post-launch completion
- Wave 12 final validation against DOM-CORE-002 exact target

The plan explicitly states this is a **clean break** path, with staged retirement of legacy artifacts as each domain ports.

---

## 12. Most Important Grounded Takeaways for New Contributors

1. **This is not a greenfield system** — it is a constitutional rebuild inside a live codebase with transitional dual-scoped structures.
2. **Authority hierarchy is the design center** — INV rules drive DOM ownership; FEAT governs legal mutation.
3. **`seat_id` + `class_id` is the target runtime activity anchor** — `join_code` is public alias; legacy keys remain in transition paths.
4. **GET purity is a central correctness rule** — write-on-read is treated as an architectural violation, not style issue.
5. **The FEAT framework is real in code today** — `app/feats/base.py` enforces context, boundaries, and mutation integrity.
6. **Compliance is actively tracked with explicit defect lists** — use tracking docs before assuming a subsystem is fully ported.
7. **The docs in `docs/` are not decorative** — they are being used as constitutional references for implementation and verification gates.

---

## 13. Primary Source Index (Read First)

### Constitutional documents

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-000_EXECUTION_MODEL.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md`

### Domain architecture

- `docs/DOMAIN/DOM-CORE-001_DOMAIN_AUTHORITY_SUMMARY.md`
- `docs/DOMAIN/DOM-CORE-002_CANONICAL_SCHEMA_DEFINITION.md`
- `docs/DOMAIN/DOM-IDEN-001_IDENTITY_CLASS_BINDING_DOMAIN.md`
- `docs/DOMAIN/DOM-LED-001_LEDGER_DOMAIN.md`
- `docs/DOMAIN/DOM-OBL-001_OBLIGATIONS_DOMAIN.md`

### FEAT contract

- `docs/FEATURE-EXECUTION/FEAT-CORE-000_FEATURE_EXECUTION_CONSTITUTIONAL_DIRECTIVE.md`

### Build specs and transition plans

- `docs/SPECS/V2_CAPABILITY-BASED_ARCHITECTURE_REBUILD.md`
- `docs/SPECS/V2_STUDENT_IDENTITY_ARCHITECTURE.md`
- `docs/SPECS/V2_AUTHORITY_EXTRACTION_PLAN.md`
- `docs/SPECS/V2_ADMIN_ROUTE_REFACTOR.md`
- `docs/SPECS/V2_BANKING_LEDGER_SETTLEMENT_PLAN.md`
- `docs/SPECS/V2_Temporal_Architecture_Rebuild_Plan.md`
- `docs/SPECS/V2_SESSION_MUTATION_SAFETY.md`
- `docs/SPECS/V2_CLASS_ID_INVARIANT_BACKLOG.md`

### Tracking and status

- `docs/archive/v1-development/tracking/V2_Compliance_Validation_Report.md`
- `docs/TRACKING/V2_Full_compliance_migration_plan.md`

---

## 14. Closing Statement

The ongoing v2 rewrite is best understood as a constitutional architecture migration, not a normal incremental refactor. The strongest lens for reading the code is:

1. Which invariant is this path implementing?
2. Which domain owns this state?
3. Is the mutation executing through a FEAT-compliant boundary?
4. Is scope anchored to class/seat rather than legacy/global identifiers?

Using that lens against current code shape explains both what is already robust in `codex/v2.0` and what remains in active remediation.
