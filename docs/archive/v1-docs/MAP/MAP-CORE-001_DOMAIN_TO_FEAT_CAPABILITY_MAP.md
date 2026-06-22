# MAP-CORE-001: Domain to FEAT Capability Map

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| MAP-CORE-001     | 1.0     | 2026-04-23     | N/A        | Informative     |

---

## I. Purpose

This document maps the **Domain Layer** (Rules & State) to the **Feature Execution (FEAT) Layer** (Workflows). It defines the functional role of each domain and identifies the primary orchestrators required to deliver application features.

---

## II. The Orchestration Principle

- **Domains** are passive; they define what is allowed and hold the truth.
- **FEATs** are active; they orchestrate multiple domains to fulfill a user intent.
- **Rules**:
    1. A Domain MUST NOT call another Domain directly.
    2. A FEAT MUST manage the transaction boundary (Ledger entry + Domain update).
    3. A FEAT MUST resolve Identity context before execution.

---

## III. Domain Functional Roles & Required FEATs

### 1. Identity & Binding (`DOM-IDEN`)
- **Role**: Gatekeeper of Credential and Context.
- **Critical FEATs**:
    - `FEAT-IDEN-LOGIN`: Authenticates `user_id` and restores `last_active_seat_id`.
    - `FEAT-IDEN-CLAIM`: Binds a `user_id` to a roster-provided `seat_id`.
    - `FEAT-IDEN-RECOVER`: Self-serve credential rebinding.

### 2. Class Configuration (`DOM-CLASS`)
- **Role**: Provider of "Directives" (The Law of the Classroom).
- **Critical FEATs**:
    - `FEAT-CLASS-INIT`: Sets up a new economic universe.
    - `FEAT-CLASS-POLICY`: Updates rates (Rent, Wages) and toggles features.

### 3. Ledger & Money (`DOM-LED`)
- **Role**: Atomic accounting engine. Domain-blind math.
- **Critical FEATs**:
    - `FEAT-MONEY-POST`: The atomic "Move Money" orchestrator used by other FEATs.
    - `FEAT-MONEY-TRANSFER`: Peer-to-peer student transfers.

### 4. Obligations & Assessments (`DOM-OBL`)
- **Role**: Lifecycle manager for "Future Money" (Debts/Rights).
- **Critical FEATs**:
    - `FEAT-OBL-ASSESS`: Triggers periodic assessments (Rent, Insurance Premiums).
    - `FEAT-OBL-PAY`: Coordinates Ledger move + Obligation status update (PAID).

### 5. Attendance & Hall Passes (`DOM-ATT`)
- **Role**: Physical presence and mobility tracker.
- **Critical FEATs**:
    - `FEAT-ATT-TAP`: Marks session state + Optional wage trigger via `FEAT-MONEY-POST`.
    - `FEAT-ATT-PASS`: Verifies quota/entitlement + Issues hall pass.

### 6. Store & Entitlements (`DOM-STORE`)
- **Role**: Catalog management and perk fulfillment.
- **Critical FEATs**:
    - `FEAT-STORE-BUY`: Checks balance + Deducts funds + Creates Entitlement.
    - `FEAT-STORE-REDEEM`: Consumes a purchased perk/item.

### 7. Operations (`DOM-OPS`)
- **Role**: Observability and failure management.
- **Critical FEATs**:
    - `FEAT-OPS-AUDIT`: Specialized high-integrity logging for sensitive mutations.
    - `FEAT-OPS-INCIDENT`: Captures state on failure and manages the alert lifecycle.

### 8. Interpretation (`DOM-ITR`)
- **Role**: Meaning layer and insight generator.
- **Critical FEATs**:
    - `FEAT-ITR-ANALYZE`: Computes behavioral and structural signals at cycle-end.

### 9. Support (`DOM-SUP`)
- **Role**: Communication and dispute resolution.
- **Critical FEATs**:
    - `FEAT-SUP-ISSUE`: Files a dispute + Snapshots context via `DOM-OPS`.
    - `FEAT-SUP-ANNOUNCE`: Publishes context-aware messages to seats.

---

## IV. FEAT Constitutional Standards (Preview)

Every FEAT listed above must adhere to the upcoming **FEAT Constitutional Directive**:
1. **Context-First**: Resolve `seat_id` before domain logic.
2. **Atomic**: All-or-nothing execution.
3. **Idempotent**: Safe to retry on network failure.
4. **Audit-Logged**: Every FEAT execution must leave a trace in `DOM-OPS`.
