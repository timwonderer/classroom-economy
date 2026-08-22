# DOM-LED-001: Ledger Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-LED-001 | 2.1 | 2026-07-18 | 2.0 | Constitutional |

---

## I. Purpose

This document defines the Ledger domain as the absolute sovereign of monetary truth, transactional history, and balance derivation. It provides the mathematical proof of balance for all other domains and ensures the immutable integrity of the classroom economy.

## II. Scope

This domain governs the lifecycle of **money movement**, **transactional event logs**, and **balance derivation**.

**Ledger is domain-blind.** It possesses no knowledge of the economic meaning behind transactions (e.g., rent, payroll, or store items). It treats all financial events as abstract credits or debits.

This domain does not own:
- **Economic Context**: Owned by the domain requesting the transaction (e.g., Obligations, Attendance).
- **Class Scoping**: Ledger does not own `join_code`. Isolation is enforced explicitly via `class_id` plus seat-scoped anchors.
- **Solvency Policy**: Ledger does not decide if an overdraft is allowed; it only reports the balance. FEAT-LED-000 resolves intended ledger plans into resolved ledger plans when policy or recovery transforms are required before posting.

## III. Authority Level

Tier 1 — Constitutional. This document defines structural enforcement mechanisms and domain-specific constraints that operationalize Foundational invariants. It is subordinate to `INV-CORE-000` and `INV-CORE-001`.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `DOM-CORE-000_DOMAIN_FOUNDATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-006_COMMAND_BOUNDARY_FOR_MUTATION.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`

## V. Schema Authority Declaration

This domain is the sole schema and mutation authority over:

- `ledger_transaction` (immutable financial event log)
- `ledger_balance_snapshot` (spendable balance cache)

No other domain may define fields or mutate these tables. Mutation is permitted only through the designated `ledger_service`.

## VI. State Classification

| State | Classification | Rationale |
| :--- | :--- | :--- |
| **Ledger Transaction** | Authoritative Event | The immutable, atomic unit of money movement. |
| **Transaction Status** | Derived State | `PENDING` / `POSTED` is derived from the reconciliation watermark, not stored on the row. |
| **Idempotency Lock** | System Guard | A scoped write constraint against duplicate intent. |
| **Posted Balance Snapshot** | Projection | An optimized view of spendable funds; re-derivable from events. |
| **Spendable Balance** | Derived State | The authoritative sum of all transactions included in the latest reconciliation boundary. |

## VII. Invariants

- **INV-LED-001: Class-Bound Transaction Scope**. All financial state shall be anchored to `class_id`, `target_seat_id`, and `actor_seat_id`. Isolation is not inferred from global seat uniqueness.
- **INV-LED-002: Immutable Facts**. Once inserted, a transaction row's protected fields are immutable. No later lifecycle patching is allowed.
- **INV-LED-003: Append-Only Corrections**. Reversals and voids must be recorded as **new** transactions linked through `correlation_id` and type, not by mutating the original row.
- **INV-LED-004: Reconciliation-Derived Posting**. `PENDING` and `POSTED` are reconciliation semantics, not stored transaction state.
- **INV-LED-005: Scoped Idempotency**. The `idempotency_key` MUST be unique in the transaction's canonical scope.
- **INV-LED-006: Snapshot Fallback**. The `Posted Balance Snapshot` is a projection. If the snapshot is missing or inconsistent, the balance MUST be rebuildable from ledger history.
- **INV-LED-007: Atomic Multi-Row Integrity**. Any operation involving multiple entries (e.g., transfers) MUST be committed atomically.
- **INV-LED-008: Signed Magnitude**. Direction is defined strictly by sign: **Positive (+) = Credit**, **Negative (-) = Debit**.
- **INV-LED-009: Domain Blindness**. The `account_type` field classifies the target account and must not be used to encode business meaning (e.g., "RENT").
- **INV-LED-010: Reversal Uniqueness**. A transaction may be the target of at most **one** reversal transaction.

## VIII. Schema Contract

### 1. `ledger_transaction`

The canonical, immutable record of financial intent and execution.

- `id` (PK)
- `seat_id` (legacy compatibility anchor; retained until a separate column-removal pass)
- `target_seat_id` (FK to seats)
- `actor_seat_id` (FK to seats)
- `class_id` (FK to classes.class_id)
- `mechanism` (Enum: `SELF`, `TEACHER`, `SYSTEM`)
- `amount_cents` (Integer; Signed)
- `timestamp` (Timestamp; UTC)
- `account_type` (String or Enum; canonical account target)
- `description` (Text)
- `correlation_id` (UUID; Required)
- `feat_code` (Text; Required)
- `idempotency_key` (String; Required within scope)
- `policy_id` (UUID; Frozen policy reference when applicable)
- `type` (Text; Required)
- `lineage_event_id` (FK to audit_events.id; nullable only for pre-rollout rows)
- `lineage_token` (Text)
- `lineage_version` (Integer)

### 2. `ledger_balance_snapshot`

An optimization for rapid solvency checks.

- `seat_id` (PK; Unique)
- `class_id` (FK to classes.class_id)
- `posted_balance_cents` (Integer; Authoritative spendable amount)
- `reconciled_through_transaction_id` (FK to `ledger_transaction`)
- `last_settlement_at` (Timestamp)
- `updated_at` (Timestamp)

## IX. Derived / Cross-Domain Rules

- **Solvency Check**: Any domain requiring a "solvency check" (e.g., Store) must query the `Spendable Balance`. Ledger provides the truth; the caller decides if the amount is sufficient.
- **Pending Logic**: `PENDING` totals are derived on-demand from the transaction log for UI display. They are never stored on the transaction row.
- **Reversal Chaining**: Chained reversals are prohibited. Corrections of corrections shall be handled as fresh transactions, not updates to prior rows.



## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
