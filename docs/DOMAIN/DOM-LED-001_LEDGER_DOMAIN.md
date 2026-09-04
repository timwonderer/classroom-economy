# DOM-LED-001: Ledger Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-LED-001 | 2.4 | 2026-09-01 | 2.3 | Constitutional |

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

The Ledger posting sequence is the canonical ordering boundary for posted-ledger reconstruction. It is distinct from `effective_at`, `posted_at`, and persistence time.

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
- **INV-LED-005: Command-Scoped Idempotency**. Ledger idempotency belongs to
  command intent, not to an individual effect row. An accepted idempotent
  command reserves its `idempotency_key` within the canonical command namespace
  and records a replay fingerprint of the immutable command attributes required
  to establish replay equivalence. A replay with the same reservation identity
  MUST return the accepted command outcome only when its replay fingerprint
  matches; a mismatch MUST fail closed. The reservation remains permanent and
  MUST NOT be released by VOID, reversal, or any later correction.
- **INV-LED-006: Snapshot Fallback**. The `Posted Balance Snapshot` is a projection. If the snapshot is missing or inconsistent, the balance MUST be rebuildable from ledger history.
- **INV-LED-007: Canonical Posting Sequence**. Every transaction admitted to canonical posted-ledger history receives one immutable `posting_sequence` assigned by the lawful Ledger posting/settlement path. The sequence is monotonically increasing within one `class_id` and is unique within that class. It does not replace business or provenance timestamps.
- **INV-LED-008: Snapshot Reconciliation Cursor**. A balance snapshot records `reconciled_through_posting_sequence`, meaning that its posted balance has considered all canonical posted-ledger transactions for its `(class_id, seat_id, account_type)` scope whose `posting_sequence` is less than or equal to that cursor.
- **INV-LED-009: Atomic Seat Settlement**. A settlement affecting one `(class_id, seat_id)` MUST lock all applicable account snapshot rows in deterministic account order, reconcile them against one settlement boundary, assign posting sequences within the same transaction, and commit or roll back the complete seat-level settlement atomically.
- **INV-LED-010: Atomic Multi-Row Integrity**. Any operation involving multiple entries (e.g., transfers) MUST be committed atomically.
- **INV-LED-011: Signed Magnitude**. Direction is defined strictly by sign: **Positive (+) = Credit**, **Negative (-) = Debit**.
- **INV-LED-012: Domain Blindness**. The `account_type` field classifies the target account and must not be used to encode business meaning (e.g., "RENT").
- **INV-LED-013: Reversal Uniqueness**. A transaction may be the target of at most **one** reversal transaction.
- **INV-LED-014: Transfer Correlation Identity**. An internal account transfer is one
  class-scoped operation identified by one `correlation_id`. It MUST contain exactly
  two `ledger_transaction` legs: one debit from the source account and one credit
  to the destination account, with equal absolute `amount_cents` values and a
  signed total of zero. The legs MUST share the same `class_id`, `seat_id`, and
  `correlation_id`, and MUST be created and committed atomically. A transfer
  `correlation_id` MUST NOT be reused to create another transfer pair. This
  invariant governs the current internal checking/savings transfer semantics;
  cross-seat transfers are not authorized by this contract.

### VII.1 Command Idempotency Semantics

The command-idempotency contract has three distinct layers:

1. **Reservation identity**: `(class_id, feat_code, idempotency_key)`. The
   `class_id` is the tenant/authority boundary, `feat_code` identifies the
   originating command family, and `idempotency_key` identifies the caller's
   command within that family. `type` and effect-level attributes MUST NOT
   expand this reservation namespace.
2. **Replay fingerprint**: the immutable command attributes required to prove
   that a retry is the same command, rather than a new command reusing an old
   key. Fingerprint attributes are compared on replay and are not uniqueness
   dimensions that make a mismatched replay lawful.
3. **Ledger effects**: one accepted reservation MAY produce one or more Ledger
   effect rows, provided all effects are produced by that command and committed
   atomically.

Every canonical Ledger command path MUST be retry-safe and MUST use a command
reservation unless an explicit Ledger contract identifies a genuine exception.
No exception may be inferred from an existing write path that happens not to
provide a key. Transfer execution is included in this coverage and MUST
provide the same command reservation identity to its atomic effects.

The physical enforcement representation—reservation table, command record, or
another structural mechanism—is intentionally deferred. The current
`ledger_transaction` uniqueness constraint is transitional evidence and does
not, by itself, define command-level idempotency.

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
- `idempotency_key` (String; Command reservation key; required for canonical
  idempotent command paths)
- `policy_id` (UUID; Frozen policy reference when applicable)
- `type` (Text; Required)
- `lineage_event_id` (FK to audit_events.id; nullable only for pre-rollout rows)
- `lineage_token` (Text)
- `lineage_version` (Integer)

### 1.1 Posting Sequence

- `posting_sequence` (Integer; required for canonical posted transactions; immutable)

`posting_sequence` is assigned only by the lawful Ledger posting/settlement path. It is monotonically increasing and unique within `class_id`. It is not derived from `id`, `timestamp`, `effective_at`, or `posted_at`, and it does not replace any of those fields.

### 2. `ledger_balance_snapshot`

An optimization for rapid solvency checks.

- composite identity `(class_id, seat_id, account_type)`
- `class_id` (FK to classes.class_id)
- `seat_id` (FK to seats.id)
- `account_type` (Enum; checking or savings)
- `posted_balance_cents` (Integer; projection of canonical posted history)
- `reconciled_through_posting_sequence` (Integer; exact reconstruction cursor)
- `last_settlement_at` (Timestamp)
- `updated_at` (Timestamp)

The canonical posted-balance assertion is:

```text
posted_balance_cents
= SUM(amount_cents)
  for canonical posted ledger transactions
  matching (class_id, seat_id, account_type)
  with posting_sequence <= reconciled_through_posting_sequence
```

The inclusion and exclusion rules for posted, void, reversal, and other transaction semantics remain those defined by the Ledger transaction lifecycle and correction invariants. The snapshot does not become monetary authority by storing this projection.

## IX. Derived / Cross-Domain Rules

- **Solvency Check**: Any domain requiring a "solvency check" (e.g., Store) must query the `Spendable Balance`. Ledger provides the truth; the caller decides if the amount is sufficient.
- **Pending Logic**: `PENDING` totals are derived on-demand from the transaction log for UI display. They are never stored on the transaction row.
- **Available Balance**: Available balance is the posted balance projection plus the pending non-void Ledger delta for the same `(class_id, seat_id, account_type)` scope.
- **Reversal Chaining**: Chained reversals are prohibited. Corrections of corrections shall be handled as fresh transactions, not updates to prior rows.



## X. Amendment

Revisions to this document must:
1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000`.
