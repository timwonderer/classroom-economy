# SPEC-LED-001: Ledger Verification Proof Surfaces

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-LED-001 | 1.0 | 2026-09-01 | New | Normative |

## I. Purpose

Define the read-only Ledger proof surfaces consumed by Operations verification.
These surfaces expose Ledger-owned conclusions without transferring Ledger
reconstruction logic or authority to Operations.

## II. Scope and Authority

This specification is subordinate to `DOM-LED-001` and governs only Ledger
verification reads. It does not define verifier scheduling, Operations state
aggregation, external status publication, schema migrations, or runtime
implementation.

Operations MAY consume these results but MUST NOT reimplement Ledger
reconstruction SQL, group arbitrary Ledger rows, or infer Ledger invariants
independently.

## III. Common Contract

Every surface MUST:

- require canonical scope inputs before querying;
- be pure and read-only, with no settlement, repair, projection update, or
  lifecycle mutation;
- use canonical `ledger_transaction` history and Ledger-owned semantics;
- return bounded structured evidence, not ORM rows or unrestricted payloads;
- distinguish `PASS`, `FAIL`, and `UNAVAILABLE`;
- report `UNAVAILABLE` when required history, cursor, posting state, or proof
  inputs are missing or cannot be established;
- keep identifiers, amounts, and row-level diagnostics inside Ledger unless an
  explicitly authorized internal consumer requires them.

`FAIL` means the requested Ledger proposition was disproved. `UNAVAILABLE`
means Ledger could not lawfully establish the proposition. Neither may be
converted to `PASS` by a caller.

## IV. Proof Surfaces

### 4.1 `reconstruct_posted_balance`

```text
reconstruct_posted_balance(
    class_id,
    seat_id,
    account_type,
    through_posting_sequence?
)
```

The surface reconstructs the posted balance from canonical posted Ledger
history for exactly `(class_id, seat_id, account_type)`. It MUST NOT read or
depend on `ledger_balance_snapshot`.

When `through_posting_sequence` is supplied, the reconstruction includes every
canonical posted transaction in scope with `posting_sequence` less than or
equal to that boundary. When omitted, Ledger MUST resolve the applicable
canonical boundary according to its posting contract; it MUST NOT substitute a
wall-clock timestamp or transaction ID.

The internal result contains the reconstructed cents, boundary, evidence
completeness, and bounded diagnostic code. The Operations-facing result is a
bounded proof outcome and comparison metadata only; it does not expose seat
identifiers, transaction identifiers, or transaction-level amounts to external
adapters.

### 4.2 `reconstruct_available_balance`

```text
reconstruct_available_balance(
    class_id,
    seat_id,
    account_type
)
```

The surface reconstructs available balance from canonical Ledger history:

```text
posted balance through the applicable posting boundary
+ pending non-void Ledger delta in the same scope
```

It MUST NOT call `get_available_balance()` or any projection-based normal read,
and MUST NOT read `ledger_balance_snapshot` as an input to the reconstruction.
The pending inclusion and correction rules are Ledger-owned and must be applied
consistently with `DOM-LED-001`.

The result MUST identify whether both posted-history and pending-evidence
components were complete. Missing evidence produces `UNAVAILABLE`, not zero or
`PASS`.

### 4.3 `verify_transfer`

```text
verify_transfer(class_id, correlation_id)
```

The surface evaluates the transfer contract in `DOM-LED-001` for one
class-scoped transfer correlation. It MUST use `correlation_id` as the
canonical transfer-operation identity and MUST NOT use descriptions,
`original_transaction_id`, transaction IDs, or global aggregation to identify
the legs.

The proof evaluates, without exposing row-level detail to external consumers:

- exactly two Ledger legs;
- one shared `class_id` and `seat_id`;
- one debit and one credit across permitted account types;
- equal absolute `amount_cents` and signed total zero;
- correlation non-reuse for another transfer pair;
- atomic creation and posting consistency.

The result MUST be `UNAVAILABLE` when the correlation, posting evidence, or
atomicity evidence cannot be established. A malformed or disproven transfer
contract is `FAIL`, not `UNAVAILABLE`.

## V. Evidence and Cost

These surfaces are safe for scheduled verification because they are read-only,
class-scoped, and do not trigger settlement. Reconstruction may be more
expensive than the normal projection read and may require indexed access to
canonical Ledger history. Physical indexes, caching, batching, and cadence are
implementation decisions outside this specification.

Ledger MAY retain richer internal diagnostics for operator investigation, but
the proof result consumed by Operations MUST remain bounded and must not contain
tenant detail, PII, credentials, raw query output, or arbitrary diagnostic
payloads.

## VI. Non-Goals

This specification does not:

- create a Ledger verifier runner;
- define DOM-OPS correctness-state mapping;
- define external status semantics;
- authorize writes to snapshots or transactions;
- replace the canonical Ledger transaction or balance contracts.

## VII. Dependencies

- `DOM-LED-001_LEDGER_DOMAIN.md`
- `DOM-OPS-001_OPERATIONS_DOMAIN.md` (consumer boundary only)
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
