# V2 Ledger Balance Contract Resolution Proposal

| Review date | Proposed target | Status |
|---|---|---|
| 2026-08-31 | Normalized posted-balance projection with exact reconciliation cursor | Proposal pending `DOM-LED-001` review; no migration authorized |

## I. Purpose

Resolve the competing v2 balance-snapshot models before invariant-verifier work or schema migration proceeds.

## II. Evidence Reviewed

- `DOM-LED-001_LEDGER_DOMAIN.md`
- `V2_BALANCE_SCOPE_AND_SETTLEMENT_CONTRACT.md`
- `V2_BANKING_LEDGER_SETTLEMENT_PLAN.md`
- `app/models.py`
- `app/utils/banking.py`
- `app/services/ledger_service.py`
- `tests/dom/class/test_banking_core.py`
- migration `a1b2c3d4e5f7_add_canonical_ledger_actor_target_fields.py`
- archived `V2_SCHEMA_COMPLIANCE_AUDIT.md`
- archived `V2_Canonical_Schema_Rebuild.md`

## III. Proposed Canonical Snapshot

The target model is one projection per:

```text
(class_id, seat_id, account_type)
```

Each projection contains:

- `posted_balance_cents`;
- an exact reconciliation cursor identifying the final included Ledger event;
- update/provenance metadata.

`ledger_transaction` remains the sole monetary source of truth. The snapshot is rebuildable and must never be verified against another projection.

Available balance remains:

```text
posted_balance_cents
+ pending non-void ledger delta
```

Reads remain pure and settlement remains an explicit, class/seat-scoped operation.

## IV. Required Cursor Semantics

`reconciled_through_transaction_id` is not yet a sufficient contract by itself. The referenced transaction must participate in a canonical total ordering that makes reconstruction deterministic.

The current runtime and schema do not define such an ordering. In particular:

- integer transaction IDs are not documented as a Ledger posting sequence;
- `timestamp`, `posted_at`, and `effective_at` have different possible meanings;
- timestamps can tie or describe late persistence rather than Ledger ordering;
- no active model field provides a canonical posting sequence.

Before adoption, `DOM-LED-001` must define one of the following explicitly:

1. an immutable Ledger posting sequence/cursor assigned by the canonical write or settlement path; or
2. a fully specified ordering over existing immutable fields, including tie-breaking and late-record rules.

Until then, neither `reconciled_through_transaction_id` nor `last_settlement_at` is a complete reproducible boundary.

## V. Settlement Atomicity Requirement

For one seat-level settlement, all applicable account snapshots for the same `(class_id, seat_id)` must be:

1. selected and locked in deterministic account order;
2. reconciled against the same settlement boundary within one database transaction;
3. updated together with the corresponding Ledger lifecycle effects;
4. committed or rolled back atomically.

Normalizing checking and savings into separate rows must not permit one account row to advance while the other remains at the prior boundary.

## VI. Option Disposition

### Option A — Split columns plus temporal boundary

Current runtime shape. Retain only as transitional evidence. It does not provide normalized account identity or an exact deterministic cursor.

### Option B — Per-account snapshot plus transaction cursor

Recommended canonical target, subject to the cursor semantics and settlement atomicity requirements in §§IV–V.

### Option C — Single balance per seat/class

Rejected for the target because current Ledger behavior and balance reads distinguish account types. Archived material is treated as historical proposal, not current authority.

## VII. Consequences Once Approved

Approval of Option B requires coordinated updates to:

- `DOM-LED-001` schema, state classification, and invariants;
- `V2_BALANCE_SCOPE_AND_SETTLEMENT_CONTRACT.md` vocabulary;
- `V2_BANKING_LEDGER_SETTLEMENT_PLAN.md` equation and settlement procedure;
- ORM model and migrations;
- ledger/balance services;
- settlement and balance tests;
- verifier reconciliation row for `posted_balance_reconciliation`.

The migration must be a clean, explicitly authorized Ledger change. No compatibility bridge should be introduced merely to preserve the competing models.

## VIII. Decision Gate

The Ledger owner must first approve:

1. Option B as the canonical snapshot identity;
2. the canonical ordering/cursor mechanism;
3. the exact posted-history reconstruction equation;
4. the atomic multi-account settlement protocol.

Until those decisions are approved, the balance verifier remains `BLOCKED — DOM-LED contract resolution required`.

## IX. Amendment

This proposal becomes normative only through an approved amendment to `DOM-LED-001` and synchronized updates to the dependent Ledger documents.
