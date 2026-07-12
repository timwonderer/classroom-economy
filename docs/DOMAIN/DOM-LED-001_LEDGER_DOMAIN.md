# DOM-LED-001: Ledger Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-LED-001 | 2.0 | 2026-04-22 | 1.0 | Constitutional |

---

## I. Purpose

This document defines the Ledger domain as the absolute sovereign of monetary truth, transactional history, and balance derivation. It provides the mathematical proof of balance for all other domains and ensures the immutable integrity of the classroom economy.

## II. Scope

This domain governs the lifecycle of **money movement**, **transactional event logs**, and **balance derivation**.

**Ledger is domain-blind.** It possesses no knowledge of the economic meaning behind transactions (e.g., rent, payroll, or store items). It treats all financial events as abstract credits or debits.

This domain does not own:
- **Economic Context**: Owned by the domain requesting the transaction (e.g., Obligations, Attendance).
- **Class Scoping**: Ledger does not own `join_code`. Isolation is inherited via the `seat_id`.
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
| **Transaction Status** | Authoritative Event State | The current lifecycle position (PENDING, POSTED, VOID). |
| **Idempotency Lock** | System Guard | A globally unique write constraint against duplicate intent. |
| **Posted Balance Snapshot** | Cache | An optimized view of spendable funds; re-derivable from events. |
| **Spendable Balance** | Derived State | The authoritative sum of all `POSTED` transactions. |

## VII. Invariants

- **INV-LED-001: Seat-Scoped Sovereignty**. All financial state shall be anchored to a `seat_id`. Economic isolation is inherited from the seat's class membership; no `join_code` is required in storage.
- **INV-LED-002: Immutable Posted Truth**. Once a transaction enters the `POSTED` state, its `amount`, `seat_id`, and `correlation_id` are unchangeable.
- **INV-LED-003: Append-Only Corrections**. Status mutations for the purpose of "reversing" are prohibited. Reversals must be recorded as **new** transactions referencing an `original_transaction_id`.
- **INV-LED-004: Zero-Sum Transfers**. All transactions sharing a `correlation_id` MUST net to zero within a single atomic database write.
- **INV-LED-005: Spendable Authority**. Only `POSTED` transactions contribute to the authoritative spendable balance. `PENDING` totals are derived but shall never be used for automated solvency gates.
- **INV-LED-006: Global Idempotency**. The `idempotency_key` MUST be globally unique across the entire system.
- **INV-LED-007: Event-Log Fallback**. The `Posted Balance Snapshot` is a cache. If the cache is missing or inconsistent, the balance MUST be recomputed by summing the `POSTED` transaction log for that `seat_id`.
- **INV-LED-008: Atomic Multi-Row Integrity**. Any operation involving multiple entries (e.g., transfers) MUST be committed atomically.
- **INV-LED-009: Signed Magnitude**. Direction is defined strictly by sign: **Positive (+) = Credit**, **Negative (-) = Debit**.
- **INV-LED-010: Domain Blindness**. The `category` field classifies **operational provenance** (e.g., SYSTEM, MANUAL, ADJUSTMENT) and must not be used to encode business meaning (e.g., "RENT").
- **INV-LED-011: Reversal Uniqueness**. A `POSTED` transaction may be the target of at most **one** reversal transaction.

## VIII. Schema Contract

### 1. `ledger_transaction`

The canonical, immutable record of financial intent and execution.

- `id` (PK)
- `seat_id` (FK to seats)
- `amount_cents` (Integer; Signed)
- `status` (Enum: `PENDING`, `POSTED`, `VOID`)
- `category` (Enum: `SYSTEM`, `MANUAL`, `ADJUSTMENT`) [Operational Provenance]
- `correlation_id` (UUID; Nullable) [Atomic Grouping Key]
- `external_reference_id` (String; Nullable) [Cross-domain link]
- `idempotency_key` (String; Unique)
- `original_transaction_id` (FK to self; Nullable) [Reversal link]
- `created_at` (Timestamp)
- `posted_at` (Timestamp; Nullable)

### 2. `ledger_balance_snapshot`

An optimization for rapid solvency checks.

- `seat_id` (PK; Unique)
- `posted_balance_cents` (Integer; Authoritative spendable amount)
- `last_event_id` (FK to `ledger_transaction`)
- `updated_at` (Timestamp)

## IX. Derived / Cross-Domain Rules

- **Solvency Check**: Any domain requiring a "solvency check" (e.g., Store) must query the `Spendable Balance`. Ledger provides the truth; the caller decides if the amount is sufficient.
- **Pending Logic**: `PENDING` totals are derived on-demand from the transaction log for UI display. They are never stored in the authoritative snapshot.
- **Reversal Chaining**: Chained reversals (reversing a reversal) are prohibited. Corrections of corrections shall be handled as fresh `ADJUSTMENT` transactions.

## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
